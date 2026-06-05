"""F58.14 — extracción de cabezales del JWPUB del Insight del usuario.

Política de privacidad y copyright:

- El JWPUB del Insight on the Scriptures es propiedad de Watch Tower Bible
  and Tract Society of Pennsylvania. El usuario debe haberlo descargado
  oficialmente desde jw.org.
- Los cabezales extraídos (`title` de cada `JwpubDocument`) son nombres
  factuales del canon bíblico y constituyen una **lista de referencia local**,
  no una redistribución del contenido del Insight.
- La extracción se persiste en `<brain>/extracted_headwords.json` —
  **localmente** en la máquina del usuario. El toolkit no sincroniza ni
  redistribuye este archivo.
- Caso de uso primario: **auditar** qué fracción del Insight del usuario
  cubre el catálogo built-in (`PERSON_HEADWORDS ∪ EXPANDED_PERSON_HEADWORDS
  ∪ PLACE_HEADWORDS ∪ EXPANDED_PLACE_HEADWORDS`). No se usa para
  clasificación persona/lugar automática — la clasificación sigue siendo
  responsabilidad de los catálogos built-in.

API:

    from jw_brain.imports.bible.headword_extractor import (
        extract_headwords_from_jwpub,
        persist_to_brain,
        load_extracted_headwords,
    )

    headwords = extract_headwords_from_jwpub("~/jwpubs/it_E.jwpub")
    target = persist_to_brain(headwords, brain_home="~/.jw-brain/personal")
    cached = load_extracted_headwords("~/.jw-brain/personal")
"""

from __future__ import annotations

import json
from pathlib import Path

from jw_core.parsers.jwpub import parse_jwpub


_EXTRACTED_FILENAME = "extracted_headwords.json"


def extract_headwords_from_jwpub(jwpub_path: Path | str) -> list[str]:
    """Devuelve los `title` de todos los documents del JWPUB.

    Cada title del Insight es un cabezal de artículo (Abraham, Cesarea,
    Trinidad, etc.). Esta función NO clasifica; solo enumera lo que el
    JWPUB del usuario tiene como cabezal.

    Lanza `JwpubError` si el archivo no es un JWPUB válido. Documentos
    sin título se omiten silenciosamente (mismo patrón que `parse_jwpub`).
    """
    metadata = parse_jwpub(jwpub_path)
    return [doc.title for doc in metadata.documents if doc.title]


def persist_to_brain(
    headwords: list[str],
    brain_home: Path | str,
) -> Path:
    """Guarda los cabezales extraídos en `<brain>/extracted_headwords.json`.

    Los cabezales se normalizan a lowercase y se deduplican antes de
    persistir, para alinearse con la convención de los catálogos built-in.
    El archivo se sobrescribe (no se mergea con persistencias anteriores).

    Retorna el `Path` del archivo escrito. Crea el directorio brain_home
    si no existe (permite uso en tests con tmp_path puro).
    """
    brain_path = Path(brain_home).expanduser()
    target = brain_path / _EXTRACTED_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "headwords": sorted({h.strip().lower() for h in headwords if h.strip()}),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_extracted_headwords(brain_home: Path | str) -> set[str]:
    """Lee `<brain>/extracted_headwords.json`. Set vacío si no existe.

    El archivo puede no existir (brain recién creado o usuario que aún no
    ha corrido `jw brain learn-headwords`). En ese caso devolvemos set()
    sin error, para que los callers puedan unirlo a sus catálogos sin
    guard explícito.
    """
    brain_path = Path(brain_home).expanduser()
    target = brain_path / _EXTRACTED_FILENAME
    if not target.exists():
        return set()
    data = json.loads(target.read_text(encoding="utf-8"))
    return set(data.get("headwords", []))
