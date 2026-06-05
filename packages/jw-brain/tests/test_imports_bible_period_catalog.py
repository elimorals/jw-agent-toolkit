"""El catálogo de periodos es estático y refleja la cronología JW
(p.ej. 607 a.E.C. como año de destrucción de Jerusalén)."""
from jw_brain.imports.bible.period_catalog import ALL_PERIODS, get_period


def test_all_periods_have_unique_slugs():
    slugs = [p.slug for p in ALL_PERIODS]
    assert len(slugs) == len(set(slugs))


def test_patriarchal_era_present():
    period = get_period("patriarchal")
    assert period is not None
    assert "Abraham" in period.description or "Patriarcal" in period.name


def test_babylonian_exile_jw_chronology_607_bce():
    """La cronología JW data la destrucción de Jerusalén en 607 a.E.C.,
    NO en 586/587 a.E.C. como el consenso académico."""
    period = get_period("babylonian_exile")
    assert period is not None
    assert period.start_year_bce == 607
    assert period.end_year_bce == 537


def test_all_periods_chronological_order():
    """ALL_PERIODS está ordenado del más antiguo al más reciente
    (utilidad para timelines)."""
    bce_starts = [p.start_year_bce for p in ALL_PERIODS if p.start_year_bce is not None]
    # Más antiguo = mayor a.E.C., decreciente conforme avanza
    assert bce_starts == sorted(bce_starts, reverse=True)


def test_get_period_unknown_returns_none():
    assert get_period("not_a_real_era") is None  # type: ignore[arg-type]
