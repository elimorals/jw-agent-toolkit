"""Modelos intermediarios entre parser y loader del bible KG.

Diferencia clave con NodeTypeSpec: estos son Pydantic _data carriers_
(no schema-on-read del backend). El loader los aplana al formato
`upsert_node(node_type, canonical_id, properties)` esperado por
GraphBackend Protocol.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

InsightKind = Literal["person", "place"]
"""Tipos de entrada que el parser Insight reconoce. `period` se hidrata
desde el catálogo curado, no desde Insight (las entradas son inestables)."""

EraSlug = Literal[
    "patriarchal",
    "egyptian_exile",
    "judges",
    "united_kingdom",
    "divided_kingdom",
    "babylonian_exile",
    "persian_era",
    "hellenistic_era",
    "roman_era",
    "early_christian_era",
]


class InsightEntry(BaseModel):
    """Una cabecera del Insight on the Scriptures con metadata cruda
    todavía sin proyectar al schema del KG."""

    model_config = ConfigDict(frozen=True)

    headword: str = Field(description="Cabezal exacto del artículo")
    document_id: int = Field(description="MEPSDocumentId dentro del JWPUB")
    symbol: str = Field(description="Símbolo de la publicación, p.ej. it-1")
    meps_language: int
    kind: InsightKind
    first_mention_raw: str = Field(default="", description="Texto de la referencia, p.ej. 'Gen. 11:26'")
    first_mention_href: str = Field(default="", description="href WOL relativo")
    aliases: tuple[str, ...] = Field(default=())
    text_excerpt: str = Field(default="", description="Primeros ~500 chars del artículo")


class BibleKgPerson(BaseModel):
    """Persona bíblica ya proyectada al schema del KG."""

    model_config = ConfigDict(frozen=True)

    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    aliases: tuple[str, ...] = ()
    era: EraSlug | None = None
    first_mention_book: int | None = Field(default=None, ge=1, le=66)
    first_mention_chapter: int | None = None
    first_mention_verse: int | None = None
    description_excerpt: str = ""
    source_url: str = ""

    @property
    def canonical_id(self) -> str:
        return f"person:{self.slug}"


class BibleKgPlace(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    region: str = ""
    modern_name: str = ""
    latitude: float | None = None
    longitude: float | None = None
    eras_active: tuple[EraSlug, ...] = ()
    source_url: str = ""

    @property
    def canonical_id(self) -> str:
        return f"place:{self.slug}"


class BibleKgPeriod(BaseModel):
    model_config = ConfigDict(frozen=True)

    slug: EraSlug
    name: str
    start_year_bce: int | None = Field(
        default=None,
        description="Año a. E.C. de inicio (positivo). None si la fecha JW no es precisa.",
    )
    end_year_bce: int | None = None
    end_year_ce: int | None = Field(
        default=None,
        description="Año E.C. de fin para periodos que cruzan el cambio de era.",
    )
    description: str = ""

    @property
    def canonical_id(self) -> str:
        return f"period:{self.slug}"


class BibleKgPassage(BaseModel):
    """Una BibleRef materializada como nodo del KG para tejer edges
    `MENTIONED_IN_PASSAGE` entre personas/lugares."""

    model_config = ConfigDict(frozen=True)

    book_num: int = Field(ge=1, le=66)
    chapter: int = Field(ge=1)
    verse_start: int | None = Field(default=None, ge=1)
    verse_end: int | None = Field(default=None, ge=1)
    mentions_people: tuple[str, ...] = Field(default=(), description="canonical_ids")
    mentions_places: tuple[str, ...] = Field(default=())
    period_slug: EraSlug | None = None

    @property
    def canonical_id(self) -> str:
        if self.verse_start is None:
            return f"passage:{self.book_num}:{self.chapter}"
        if self.verse_end is None or self.verse_end == self.verse_start:
            return f"passage:{self.book_num}:{self.chapter}:{self.verse_start}"
        return f"passage:{self.book_num}:{self.chapter}:{self.verse_start}-{self.verse_end}"
