"""Catálogo curado de periodos bíblicos según la cronología JW.

Las fechas vienen del Estudio Perspicaz de las Escrituras (Insight on
the Scriptures, vol. 1, "Chronology") y de la Tabla de tiempos bíblicos
publicada por la Watch Tower Bible and Tract Society. Difieren en
puntos clave del consenso académico:

- Destrucción de Jerusalén: 607 a.E.C. (JW) vs 587/586 a.E.C. (académico).
- 70 años de exilio babilónico: 607-537 a.E.C. (JW lee Jeremías 25:11-12,
  29:10 de forma literal).
- Período del Imperio Persa: 537-331 a.E.C.

Si la Watch Tower publica una revisión cronológica, actualizar esta
constante; el resto del pipeline no requiere cambios.
"""
from __future__ import annotations

from jw_brain.imports.bible.models import BibleKgPeriod

ALL_PERIODS: tuple[BibleKgPeriod, ...] = (
    BibleKgPeriod(
        slug="patriarchal",
        name="Era Patriarcal",
        start_year_bce=2018,
        end_year_bce=1657,
        description=(
            "Desde el llamamiento de Abraham (2018 a.E.C.) hasta la entrada "
            "de Jacob y su familia en Egipto (1728 a.E.C.) y la subsecuente "
            "esclavitud que culmina con Moisés (1657 a.E.C.)."
        ),
    ),
    BibleKgPeriod(
        slug="egyptian_exile",
        name="Cautiverio Egipcio",
        start_year_bce=1728,
        end_year_bce=1513,
        description=(
            "Periodo desde la inmigración de Jacob a Egipto hasta el éxodo "
            "bajo Moisés en 1513 a.E.C."
        ),
    ),
    BibleKgPeriod(
        slug="judges",
        name="Era de los Jueces",
        start_year_bce=1467,
        end_year_bce=1117,
        description=(
            "Desde la conquista de Canaán bajo Josué hasta la unción del "
            "rey Saúl. Periodo descentralizado bajo jueces sucesivos."
        ),
    ),
    BibleKgPeriod(
        slug="united_kingdom",
        name="Reino Unido de Israel",
        start_year_bce=1117,
        end_year_bce=997,
        description=(
            "Reinados de Saúl, David y Salomón. Construcción del primer "
            "templo (1034 a.E.C.). División del reino tras la muerte de Salomón."
        ),
    ),
    BibleKgPeriod(
        slug="divided_kingdom",
        name="Reino Dividido",
        start_year_bce=997,
        end_year_bce=607,
        description=(
            "Reino del norte (Israel, 10 tribus) cae ante Asiria en 740 a.E.C. "
            "Reino del sur (Judá) cae ante Babilonia en 607 a.E.C., comenzando "
            "el cautiverio babilónico."
        ),
    ),
    BibleKgPeriod(
        slug="babylonian_exile",
        name="Cautiverio Babilónico",
        start_year_bce=607,
        end_year_bce=537,
        description=(
            "70 años de exilio en Babilonia, conforme a la profecía de "
            "Jeremías 25:11-12 y 29:10. Concluye con el decreto de Ciro "
            "permitiendo el retorno a Judá."
        ),
    ),
    BibleKgPeriod(
        slug="persian_era",
        name="Era del Imperio Persa",
        start_year_bce=537,
        end_year_bce=331,
        description=(
            "Reconstrucción del templo bajo Zorobabel (515 a.E.C.). Misiones "
            "de Esdras (468 a.E.C.) y Nehemías (455 a.E.C.). Concluye con la "
            "conquista de Alejandro Magno."
        ),
    ),
    BibleKgPeriod(
        slug="hellenistic_era",
        name="Era Helenística",
        start_year_bce=331,
        end_year_bce=63,
        description=(
            "Dominio sucesivo de los sucesores de Alejandro (Ptolomeos, "
            "Seléucidas). Revuelta macabea (167 a.E.C.). Concluye con la "
            "conquista romana de Pompeyo."
        ),
    ),
    BibleKgPeriod(
        slug="roman_era",
        name="Era del Imperio Romano",
        start_year_bce=63,
        end_year_ce=33,
        description=(
            "Dominio romano sobre Judea. Nacimiento de Jesús (probable 2 a.E.C.), "
            "ministerio (29-33 E.C.) y muerte (33 E.C.)."
        ),
    ),
    BibleKgPeriod(
        slug="early_christian_era",
        name="Era del Cristianismo Primitivo",
        start_year_bce=None,
        end_year_ce=100,
        description=(
            "Desde Pentecostés del 33 E.C. hasta aproximadamente el año 100 E.C. "
            "(muerte del apóstol Juan). Cobertura del libro de Hechos y las "
            "cartas apostólicas."
        ),
    ),
)
"""Tupla immutable de periodos en orden cronológico (más antiguo primero)."""

_BY_SLUG: dict[str, BibleKgPeriod] = {p.slug: p for p in ALL_PERIODS}


def get_period(slug: str) -> BibleKgPeriod | None:
    """Devuelve el periodo con el slug dado, o None si no existe."""
    return _BY_SLUG.get(slug)
