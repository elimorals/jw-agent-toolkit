"""Data models for the fine-tune pipeline.

These are intentionally frozen dataclasses: records flow through extract →
dedupe → chunk → synth → format stages, and we want any accidental
mutation to fail loudly. The `extra` dict is a string-keyed escape hatch
for per-source metadata that isn't worth a first-class field.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PublicationKind = Literal[
    "watchtower",  # w / wp (Atalaya — edición estudio o pública)
    "awake",       # g (¡Despertad!)
    "book",        # libros (lff, jy, sjj, bh, rr, ...)
    "brochure",    # folletos
    "bible",       # NWT u otra traducción
    "article",     # artículo WOL suelto
    "workbook",    # mwb (Vida y Ministerio Cristianos)
    "broadcast",   # transcripción JW Broadcasting (futuro)
    "user-note",   # JW Library user note (personal-study preset)
    "objection",   # objection catalog entry
    "other",
]

SourceKind = Literal["jwpub", "epub", "wol-article", "wol-bible", "raw-text"]


@dataclass(frozen=True)
class ParagraphRecord:
    """Una unidad de texto extraída de una publicación JW.

    Inmutable para que pase libremente por el pipeline sin riesgo de mutación.
    Los campos opcionales tienen defaults vacíos para que los parsers con menos
    metadata no necesiten conocer todos los campos.
    """

    text: str
    pub_code: str
    language: str  # ISO 639-1 ("es", "en") o "und" si desconocido
    kind: PublicationKind
    source_path: str  # ruta local absoluta/relativa o URL
    doc_id: str = ""  # MEPS doc id si está disponible
    section_ref: str = ""  # "w24 12 p.7", "lff lección 5", etc.
    paragraph_pid: int | None = None
    spine_index: int | None = None  # solo EPUB
    extra: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceSpec:
    """Especificación de una fuente de datos para el recipe.

    `pub_code_hint` y `publication_kind_hint` permiten al usuario sobreescribir
    la detección automática del parser cuando esta sea ambigua o incorrecta.
    """

    kind: SourceKind
    path: str  # ruta a archivo local o URL
    language: str  # idioma esperado (puede sobreescribir el detectado)
    pub_code_hint: str = ""
    publication_kind_hint: PublicationKind | None = None
