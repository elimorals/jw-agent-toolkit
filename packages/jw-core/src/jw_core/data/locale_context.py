"""Per-country cultural context for the ministry assistant.

VISION.md Module 2 / Gap 9: "Sugerencias contextuales por ubicación
(cultura local, idiomas hablados, festividades)".

Data is curated public knowledge — verified against country profiles
and JW publications about preaching in specific cultures. Adding a
country = appending one entry to `LOCALE_CONTEXTS`.

The agent doesn't make claims about doctrine in that culture — it
surfaces context the LLM can weave into the presentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LocaleContext:
    iso_3166: str  # ISO country code (2 letters)
    name: dict[str, str]
    languages: tuple[str, ...] = ()
    dominant_religions: tuple[str, ...] = ()
    sensitive_topics: tuple[str, ...] = ()  # avoid in initial conversation
    cultural_anchors: tuple[str, ...] = ()  # values commonly shared
    holidays_to_acknowledge: tuple[str, ...] = ()
    notes: dict[str, str] = field(default_factory=dict)

    def localized_name(self, language: str) -> str:
        return self.name.get(language, self.name.get("en", self.iso_3166))


LOCALE_CONTEXTS: dict[str, LocaleContext] = {
    "MX": LocaleContext(
        iso_3166="MX",
        name={"en": "Mexico", "es": "México", "pt": "México"},
        languages=("es", "es_MX", "nah", "yua", "lsm"),
        dominant_religions=("Catholic",),
        sensitive_topics=("Virgin of Guadalupe", "Day of the Dead"),
        cultural_anchors=("family ties", "respect for elders", "compadrazgo"),
        holidays_to_acknowledge=("Día de los Muertos (Nov 2)", "Día de la Virgen (Dec 12)"),
        notes={
            "en": "Catholic culture with strong family bonds; lead with practical hope.",
            "es": "Cultura católica con lazos familiares fuertes; comience con esperanza práctica.",
        },
    ),
    "BR": LocaleContext(
        iso_3166="BR",
        name={"en": "Brazil", "es": "Brasil", "pt": "Brasil"},
        languages=("pt", "pt_BR", "bzs"),
        dominant_religions=("Catholic", "Evangelical", "Spiritism", "Candomblé"),
        sensitive_topics=("Carnaval", "Iemanjá"),
        cultural_anchors=("warmth", "family", "futebol"),
        holidays_to_acknowledge=("Carnaval (Feb-Mar)", "Festas Juninas (June)"),
    ),
    "US": LocaleContext(
        iso_3166="US",
        name={"en": "United States", "es": "Estados Unidos", "pt": "Estados Unidos"},
        languages=("en", "es", "ase"),
        dominant_religions=("Christian (varied)", "None", "Catholic"),
        sensitive_topics=("politics", "patriotism"),
        cultural_anchors=("freedom", "individualism", "religious diversity"),
        holidays_to_acknowledge=("Thanksgiving (4th Thu Nov)", "Independence Day (Jul 4)"),
    ),
    "ES": LocaleContext(
        iso_3166="ES",
        name={"en": "Spain", "es": "España", "pt": "Espanha"},
        languages=("es", "ca", "eu", "gl", "lsm"),
        dominant_religions=("Catholic", "None"),
        sensitive_topics=("Holy Week processions",),
        cultural_anchors=("regional pride", "family Sundays"),
        holidays_to_acknowledge=("Semana Santa (March-April)",),
    ),
    "AR": LocaleContext(
        iso_3166="AR",
        name={"en": "Argentina", "es": "Argentina", "pt": "Argentina"},
        languages=("es", "es_AR", "lsa"),
        dominant_religions=("Catholic", "Evangelical"),
        sensitive_topics=("politics", "football rivalry"),
        cultural_anchors=("mate culture", "extended family"),
    ),
    "CO": LocaleContext(
        iso_3166="CO",
        name={"en": "Colombia", "es": "Colombia", "pt": "Colômbia"},
        languages=("es", "lsc"),
        dominant_religions=("Catholic", "Evangelical"),
        cultural_anchors=("warmth", "music", "family"),
    ),
    "PE": LocaleContext(
        iso_3166="PE",
        name={"en": "Peru", "es": "Perú", "pt": "Peru"},
        languages=("es", "qu", "ay"),
        dominant_religions=("Catholic",),
        sensitive_topics=("Inti Raymi",),
        cultural_anchors=("ancestral heritage", "Pachamama"),
    ),
    "DE": LocaleContext(
        iso_3166="DE",
        name={"en": "Germany", "es": "Alemania", "pt": "Alemanha"},
        languages=("de", "tr", "ar"),
        dominant_religions=("Catholic", "Lutheran", "None"),
        cultural_anchors=("punctuality", "directness"),
        holidays_to_acknowledge=("Weihnachten (Dec 24)",),
    ),
    "FR": LocaleContext(
        iso_3166="FR",
        name={"en": "France", "es": "Francia", "pt": "França"},
        languages=("fr", "ar"),
        dominant_religions=("Catholic", "Muslim", "None"),
        sensitive_topics=("laïcité",),
        cultural_anchors=("debate culture", "respect for ideas"),
    ),
    "IT": LocaleContext(
        iso_3166="IT",
        name={"en": "Italy", "es": "Italia", "pt": "Itália"},
        languages=("it",),
        dominant_religions=("Catholic", "None"),
        cultural_anchors=("family", "regional pride", "table sharing"),
        holidays_to_acknowledge=("Natale (Dec 25)", "Pasqua (Easter)"),
    ),
    "JP": LocaleContext(
        iso_3166="JP",
        name={"en": "Japan", "es": "Japón", "pt": "Japão"},
        languages=("ja",),
        dominant_religions=("Shinto-Buddhist syncretism", "None"),
        sensitive_topics=("ancestral worship", "Yasukuni"),
        cultural_anchors=("group harmony", "respect", "hospitality"),
        holidays_to_acknowledge=("Obon (mid-August)",),
        notes={
            "en": "Avoid confrontation; emphasize harmony and respect.",
        },
    ),
    "KR": LocaleContext(
        iso_3166="KR",
        name={"en": "South Korea", "es": "Corea del Sur", "pt": "Coreia do Sul"},
        languages=("ko",),
        dominant_religions=("None", "Christian", "Buddhist"),
        cultural_anchors=("Confucian filial piety", "education"),
        holidays_to_acknowledge=("Chuseok",),
    ),
    "CN": LocaleContext(
        iso_3166="CN",
        name={"en": "China", "es": "China", "pt": "China"},
        languages=("zh", "zh_CHS"),
        dominant_religions=("Buddhist", "Taoist", "Folk", "None"),
        sensitive_topics=("politics", "Tiananmen"),
        cultural_anchors=("family", "ancestry"),
        notes={"en": "Be discreet; ministry is restricted in many regions."},
    ),
    "PH": LocaleContext(
        iso_3166="PH",
        name={"en": "Philippines", "es": "Filipinas", "pt": "Filipinas"},
        languages=("tl", "en"),
        dominant_religions=("Catholic", "Evangelical", "INC"),
        cultural_anchors=("extended family", "bayanihan", "religious devotion"),
        holidays_to_acknowledge=("Simbang Gabi (Dec 16-24)",),
    ),
    "RU": LocaleContext(
        iso_3166="RU",
        name={"en": "Russia", "es": "Rusia", "pt": "Rússia"},
        languages=("ru",),
        dominant_religions=("Orthodox", "None"),
        sensitive_topics=("politics", "legal status of JWs"),
        cultural_anchors=("endurance", "literary tradition"),
        notes={"en": "JW activity is severely restricted in Russia (designated 'extremist'). Be cautious."},
    ),
}


def get_locale(iso_3166: str) -> LocaleContext | None:
    return LOCALE_CONTEXTS.get(iso_3166.upper())


def list_locales(language: str = "en") -> list[dict[str, object]]:
    return [
        {
            "iso_3166": ctx.iso_3166,
            "name": ctx.localized_name(language),
            "languages": list(ctx.languages),
            "religions": list(ctx.dominant_religions),
        }
        for ctx in LOCALE_CONTEXTS.values()
    ]


def context_for_presentation(iso_3166: str, *, display_language: str = "en") -> dict[str, object]:
    """Render a locale context as a dict ready to inject into a presentation."""
    ctx = get_locale(iso_3166)
    if ctx is None:
        return {"error": f"No locale context for {iso_3166!r}"}
    return {
        "country": ctx.localized_name(display_language),
        "languages": list(ctx.languages),
        "religions": list(ctx.dominant_religions),
        "sensitive_topics": list(ctx.sensitive_topics),
        "cultural_anchors": list(ctx.cultural_anchors),
        "holidays_to_acknowledge": list(ctx.holidays_to_acknowledge),
        "guidance": ctx.notes.get(display_language, ctx.notes.get("en", "")),
    }
