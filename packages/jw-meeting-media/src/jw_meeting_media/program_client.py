"""MeetingProgramClient: cliente HTTP + parser HTML para el programa
semanal de reuniones JW desde wol.jw.org.

Diseñado clean-room: el parser identifica estructura HTML semántica
del WOL (article > div.bodyTxt + h2/h3/div) inspeccionada via
DevTools del browser sobre la página pública, no via lectura de M³.

URL pattern (público, documentado en F1):
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}

Resource y lp_tag por idioma vienen del registry de F1.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from jw_core.languages import get_language
from jw_core.parsers.reference import parse_all_references

from jw_meeting_media.models import (
    MediaKind,
    MediaRef,
    MeetingItem,
    MeetingKind,
    MeetingProgram,
    MeetingSection,
)

if TYPE_CHECKING:
    pass


class MeetingProgramClient:
    """Cliente para descubrir y parsear el programa semanal."""

    BASE = "https://wol.jw.org"

    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http
        self._owned = http is None
        if self._owned:
            self._http = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                headers={"User-Agent": "jw-agent-toolkit/F57"},
            )

    def build_week_url(self, *, language: str, year: int, week: int) -> str:
        """Construye URL del workbook para idioma+año+semana."""
        meta = get_language(language)
        resource = meta.wol_resource  # r1, r4, r5...
        lp_tag = meta.lp_tag  # lp-e, lp-s, lp-t...
        return f"{self.BASE}/{language}/wol/meetings/{resource}/{lp_tag}/{year}/{week}"

    async def fetch_week(
        self,
        *,
        language: str,
        year: int,
        week: int,
        kind: MeetingKind = MeetingKind.MIDWEEK,
    ) -> MeetingProgram:
        url = self.build_week_url(language=language, year=year, week=week)
        assert self._http is not None
        resp = await self._http.get(url)
        resp.raise_for_status()
        week_start = date.fromisocalendar(year, week, 1)
        return self.parse_html(
            resp.text,
            language=language,
            week_start=week_start,
            kind=kind,
            source_url=url,
        )

    def parse_html(
        self,
        html: str,
        *,
        language: str,
        week_start: date,
        kind: MeetingKind,
        source_url: str,
    ) -> MeetingProgram:
        """Parsea el HTML del workbook semanal.

        Estrategia (observada en el WOL público):
          - <article> contiene un <div class="bodyTxt"> con todo el contenido.
          - Section headers son h2 dentro de divs marcadores (clases dc-icon--gem/wheat/sheep).
          - Items son h3 con título numerado o canción.
          - Cada item es seguido por divs/parrafos con detalle textual y refs.
        """
        soup = BeautifulSoup(html, "lxml")
        article = soup.find("article")
        sections: list[MeetingSection] = []
        if article is None:
            return MeetingProgram(
                language=language,
                week_start=week_start,
                kind=kind,
                sections=[],
                source_url=source_url,
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

        body = article.find("div", class_="bodyTxt") or article
        sections = self._walk_body(body, language=language)

        return MeetingProgram(
            language=language,
            week_start=week_start,
            kind=kind,
            sections=sections,
            source_url=source_url,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _walk_body(self, body: Tag, *, language: str) -> list[MeetingSection]:
        """Recorre top-level children del bodyTxt agrupando por section/item.

        Algoritmo:
          - Estado actual: section, item.
          - Si encontramos un h2 (directo o dentro de un div header), abrir nueva section.
          - Si encontramos un h3, abrir nuevo item dentro de la section activa
            (o crear un "intro" implícito si aún no hay section).
          - Otros nodos (div, p) se acumulan en buffer del item actual para
            extraer refs bíblicas y media.
        """
        sections: list[MeetingSection] = []
        current_section: MeetingSection | None = None
        current_item: MeetingItem | None = None
        item_buffer: list[Tag] = []
        section_counter = 0
        item_counter = 0

        def _flush_item() -> None:
            nonlocal current_item, item_buffer
            if current_item is None:
                return
            self._enrich_item(current_item, item_buffer, language=language)
            if current_section is not None:
                current_section.items.append(current_item)
            current_item = None
            item_buffer = []

        def _flush_section() -> None:
            nonlocal current_section
            _flush_item()
            if current_section is not None and current_section.items:
                sections.append(current_section)
            current_section = None

        for child in body.children:
            if not isinstance(child, Tag):
                continue

            # Detectar section header: h2 directo o div con h2 hijo + clase
            # "dc-icon--gem|wheat|sheep" o similar
            h2 = child if child.name == "h2" else child.find("h2") if child.name == "div" else None
            if h2 is not None and self._is_section_header(child, h2):
                _flush_section()
                section_counter += 1
                current_section = MeetingSection(
                    section_id=f"sec-{section_counter}",
                    title=h2.get_text(strip=True),
                    items=[],
                )
                item_counter = 0
                continue

            # Detectar item header: h3 (puede ser canción o item numerado)
            if child.name == "h3":
                _flush_item()
                # Si no hay sección activa, abrir una sección "intro" implícita
                if current_section is None:
                    section_counter += 1
                    current_section = MeetingSection(
                        section_id=f"sec-{section_counter}",
                        title="Apertura",
                        items=[],
                    )
                item_counter += 1
                title = child.get_text(" ", strip=True)
                current_item = MeetingItem(
                    item_id=f"i-{section_counter}-{item_counter}",
                    title=title[:300] or f"item {item_counter}",
                    position=item_counter,
                    bible_refs=[],
                    media_refs=[],
                )
                # also stash the h3 itself for media/refs extraction
                item_buffer.append(child)
                continue

            # Acumular contenido al item activo
            if current_item is not None:
                item_buffer.append(child)
            elif current_section is not None:
                # Contenido antes del primer item: descartar
                pass
            else:
                # Pre-section content (title page); skip
                pass

        _flush_section()
        return sections

    def _is_section_header(self, container: Tag, h2: Tag) -> bool:
        """Detecta si un h2 es un section header (TESOROS/SEAMOS/NUESTRA VIDA).

        Heurística clean-room: section headers tienen icon classes
        distintivas en el WOL público (dc-icon--gem, dc-icon--wheat,
        dc-icon--sheep) y suelen estar wrapped in divs con esas classes.
        Fallback: cualquier h2 que esté en un div del top-level del
        bodyTxt y cuyo título esté en mayúsculas.
        """
        container_classes = container.get("class") or []
        h2_classes = h2.get("class") or []
        all_classes = set(container_classes) | set(h2_classes)
        # Iconos conocidos en el layout WOL público
        for cls in all_classes:
            if cls.startswith("dc-icon--"):
                return True
        # Fallback heurístico: h2 directo con texto en mayúsculas (la página
        # del título tiene un h2 con la cita bíblica también en mayúsculas
        # pero está dentro de un <header>, no de un div top-level del
        # bodyTxt — por eso filtramos al nivel del container).
        if container.name == "div":
            text = h2.get_text(strip=True)
            if text and text == text.upper() and len(text) > 3:
                return True
        return False

    def _enrich_item(
        self,
        item: MeetingItem,
        nodes: list[Tag],
        *,
        language: str,
    ) -> None:
        """Extrae bible_refs y media_refs de los nodos buffereados."""
        combined_text_chunks: list[str] = []
        for node in nodes:
            combined_text_chunks.append(node.get_text(" ", strip=True))
            for ref in self._extract_media_refs(node, language=language):
                item.media_refs.append(ref)
        combined_text = " ".join(combined_text_chunks)
        if combined_text:
            try:
                item.bible_refs.extend(parse_all_references(combined_text))
            except Exception:
                pass

    def _extract_media_refs(self, node: Tag, *, language: str) -> list[MediaRef]:
        out: list[MediaRef] = []
        seen_urls: set[str] = set()

        for a in node.find_all("a", href=True):
            href = a["href"]
            absolute = href if href.startswith("http") else self.BASE + href
            if absolute in seen_urls:
                continue
            if "/wol/mp/" in href:
                seen_urls.add(absolute)
                out.append(
                    MediaRef(
                        kind=MediaKind.VIDEO,
                        title=a.get_text(strip=True) or "media",
                        url=absolute,
                        language=language,
                    )
                )
            elif "/wol/d/" in href and "lp-" in href:
                # documento JWPUB referenciado
                seen_urls.add(absolute)
                out.append(
                    MediaRef(
                        kind=MediaKind.JWPUB,
                        title=a.get_text(strip=True) or "document",
                        url=absolute,
                        language=language,
                    )
                )

        for img in node.find_all("img"):
            src = img.get("src", "")
            if not src:
                continue
            absolute = src if src.startswith("http") else self.BASE + src
            if absolute in seen_urls:
                continue
            if (
                "cms-imgp" in src
                or "imgp.jw-cdn.org" in src
                or "/wol/mp/" in src
            ):
                seen_urls.add(absolute)
                # Imágenes servidas vía /wol/mp/ son URLs de thumbnail oficial,
                # tratables como image refs.
                kind = MediaKind.IMAGE
                out.append(
                    MediaRef(
                        kind=kind,
                        title=img.get("alt", "") or "illustration",
                        url=absolute,
                        language=language,
                    )
                )
        return out

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
