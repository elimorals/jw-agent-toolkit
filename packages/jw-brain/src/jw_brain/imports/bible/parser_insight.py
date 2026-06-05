"""Parser procedural del Insight on the Scriptures (símbolo `it`).

Clasifica cada entrada del JWPUB ya descifrado (por
`jw_core.parsers.jwpub.parse_jwpub`) en `person` o `place` usando un
catálogo curado de headwords. Las entradas sin clasificación se descartan
silenciosamente: F58 prioriza precisión sobre cobertura — los conceptos
teológicos no encajan en el grafo persona/lugar/pasaje y se ignoran aquí.

Decisión de diseño (F58.7):
- La clasificación usa `JwpubDocument.title`, NO `meps_document_id`. Las
  `meps_document_id` se derivan de la publication formula y pueden variar
  entre ediciones (it-1/it-2/it consolidado, distintos años).
- El catálogo es estático, frozenset, ASCII lowercase. Aliases unicode
  (e.g. "Moisés" para español) se añaden explícitamente para no romper
  comparaciones con `.lower()` de cabezales no-inglés.
- Sin LLMs en el path crítico: regex + BeautifulSoup sobre XHTML ya
  descifrado.
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Iterator
from dataclasses import dataclass

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from jw_brain.imports.bible.models import InsightEntry, InsightKind
from jw_core.models import JwpubDocument, JwpubMetadata

# ── Catálogos de clasificación ──────────────────────────────────────────
#
# Notas:
# - lowercase, sin punctuación. La normalización ocurre en
#   `classify_entry_kind`, así que los miembros del set se comparan
#   directamente con la versión normalizada del headword.
# - Cobertura inicial F58.7: figuras bíblicas mayores y geografías de las
#   eras patriarcal a romana. La cobertura completa se hidrata después
#   desde un dataset externo (fuera del alcance de F58).

PERSON_HEADWORDS: frozenset[str] = frozenset(
    {
        # Patriarcas / pre-monarquía
        "abraham",
        "isaac",
        "jacob",
        "joseph",
        "moses",
        "moisés",  # español
        "aaron",
        "joshua",
        "samuel",
        "ruth",
        # Monarcas unidos
        "saul",
        "david",
        "solomon",
        # Profetas mayores y menores
        "elijah",
        "elisha",
        "isaiah",
        "jeremiah",
        "ezekiel",
        "daniel",
        "esther",
        # Nuevo Testamento — Jesús y apóstoles
        "jesus",
        "peter",
        "paul",
        "john",
        "james",
        "matthew",
        "mark",
        "luke",
    }
)

PLACE_HEADWORDS: frozenset[str] = frozenset(
    {
        # Geografías mayores AT
        "jerusalem",
        "babylon",
        "babylonia",
        "egypt",
        "canaan",
        "israel",
        "judah",
        "samaria",
        # Geografías NT
        "galilee",
        "judea",
        "nazareth",
        "bethlehem",
        # Imperios / centros greco-romanos
        "rome",
        "athens",
        "ephesus",
        "antioch",
    }
)


_PUNCT_STRIP = ".,;:"


def classify_entry_kind(headword: str) -> InsightKind | None:
    """Mapea un headword al tipo de entrada. None ⇒ descartar.

    Normaliza con `strip()` + `rstrip(_PUNCT_STRIP)` + `lower()` antes de
    comparar contra los catálogos.
    """
    key = headword.strip().rstrip(_PUNCT_STRIP).lower()
    if not key:
        return None
    if key in PERSON_HEADWORDS:
        return "person"
    if key in PLACE_HEADWORDS:
        return "place"
    return None


# ── Extractores XHTML ───────────────────────────────────────────────────

# Anchor con `class="b"` (bible link): captura href y texto visible.
# Tolerante a otros atributos antes/después de `class` y `href`.
_BIBLE_LINK_RE = re.compile(
    r'<a[^>]*class="b"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
    r"|"
    r'<a[^>]*href="([^"]+)"[^>]*class="b"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)


def _extract_first_mention(text: str) -> tuple[str, str]:
    """Devuelve `(raw_text, href)` de la primera mención bíblica.

    Si no hay `<a class="b">`, devuelve `("", "")`. Esto permite que el
    parser emita un `InsightEntry` aunque la primera referencia no esté
    presente (e.g. cabezales sin ancla todavía linkificada).
    """
    match = _BIBLE_LINK_RE.search(text)
    if not match:
        return ("", "")
    # El regex tiene dos alternativas; toma la primera no-None.
    href = match.group(1) or match.group(3) or ""
    raw = match.group(2) or match.group(4) or ""
    return (raw.strip(), href.strip())


def _first_paragraph_excerpt(text: str, max_chars: int = 500) -> str:
    """Devuelve el texto plano del primer `<p>` truncado a `max_chars`.

    Si el documento no tiene `<p>`, cae al texto plano completo.
    Sin elipsis: el truncado es duro porque el excerpt va a un campo
    Pydantic ya documentado como "primeros ~500 chars".
    """
    with warnings.catch_warnings():
        # Insight es XHTML válido pero usamos html.parser intencionalmente
        # (lxml es opcional). Silenciamos el warning local de bs4.
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(text, "html.parser")
    first_p = soup.find("p")
    if first_p is not None:
        plain = first_p.get_text(strip=True)
    else:
        plain = soup.get_text(strip=True)
    if len(plain) <= max_chars:
        return plain
    return plain[:max_chars]


# ── Parser ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InsightParser:
    """Itera entradas Insight clasificadas desde un JWPUB ya descifrado.

    No abre el JWPUB: el caller debe pasar el `JwpubMetadata` devuelto
    por `jw_core.parsers.jwpub.parse_jwpub` (que descifra el contenido).
    Esto mantiene el parser desacoplado del crypto y testeable con
    `JwpubMetadata` sintéticos en memoria.
    """

    symbol: str
    meps_language: int

    def iter_entries(self, metadata: JwpubMetadata) -> Iterator[InsightEntry]:
        """Genera un `InsightEntry` por cada documento clasificable.

        Documentos sin título, con texto vacío o con headword fuera del
        catálogo se omiten silenciosamente.
        """
        for doc in metadata.documents:
            entry = self._build_entry(doc)
            if entry is not None:
                yield entry

    def _build_entry(self, doc: JwpubDocument) -> InsightEntry | None:
        title = (doc.title or "").strip()
        if not title:
            return None
        kind = classify_entry_kind(title)
        if kind is None:
            return None

        text = doc.text or ""
        raw, href = _extract_first_mention(text)
        excerpt = _first_paragraph_excerpt(text) if text else ""

        return InsightEntry(
            headword=title,
            document_id=doc.meps_document_id,
            symbol=self.symbol,
            meps_language=self.meps_language,
            kind=kind,
            first_mention_raw=raw,
            first_mention_href=href,
            aliases=(),
            text_excerpt=excerpt,
        )
