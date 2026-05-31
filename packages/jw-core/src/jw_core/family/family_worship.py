"""Family worship — weekly plan generator.

Given:
  - the children's ages
  - the parents' preferences (topic / scripture)
  - the number of weeks ahead to plan

We produce a structured plan with: theme, opening prayer prompt, main
scripture, secondary readings, activity hook, suggested song.

No prose synthesis — only structured hooks. The LLM wraps it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from jw_core.family.kids_resources import (
    LESSON_BY_TOPIC,
    KidsLesson,
)


@dataclass
class FamilyWorshipPlan:
    week_of: str
    theme: str
    main_scripture: str
    secondary_scriptures: list[str] = field(default_factory=list)
    main_lesson: KidsLesson | None = None
    activity_hook: str = ""
    song_suggestion: int | None = None
    age_target: str = "middle"
    language: str = "en"

    def to_dict(self) -> dict[str, object]:
        return {
            "week_of": self.week_of,
            "theme": self.theme,
            "main_scripture": self.main_scripture,
            "secondary_scriptures": self.secondary_scriptures,
            "lesson_chapter": self.main_lesson.chapter if self.main_lesson else None,
            "lesson_title": self.main_lesson.title.get(self.language, "") if self.main_lesson else "",
            "lesson_publication": self.main_lesson.publication if self.main_lesson else "",
            "activity_hook": self.activity_hook,
            "song_suggestion": self.song_suggestion,
            "age_target": self.age_target,
            "language": self.language,
        }


_AGE_TOPIC_PRIORITY: dict[str, tuple[str, ...]] = {
    "younger": ("jehovah", "love", "happiness", "jesus"),
    "middle": ("obedience", "ransom", "love", "happiness", "temptation"),
    "older": ("temptation", "suffering", "death", "obedience", "ransom"),
}


def suggest_topics_for_age(age_band: str) -> list[str]:
    return list(_AGE_TOPIC_PRIORITY.get(age_band, _AGE_TOPIC_PRIORITY["middle"]))


_ACTIVITY_TEMPLATES: dict[str, dict[str, str]] = {
    "en": {
        "younger": "Read the lesson aloud, then draw what you learned.",
        "middle": "Read the lesson together. Each child shares one example from their week.",
        "older": "Read the lesson. Discuss a real-life situation where this applies.",
    },
    "es": {
        "younger": "Lean la lección y luego dibujen lo aprendido.",
        "middle": "Lean la lección. Cada niño comparte un ejemplo de su semana.",
        "older": "Lean la lección. Discutan una situación real donde aplique.",
    },
    "pt": {
        "younger": "Leiam a lição em voz alta, depois desenhem o que aprenderam.",
        "middle": "Leiam a lição. Cada criança compartilha um exemplo da semana.",
        "older": "Leiam a lição. Discutam uma situação real onde isso se aplica.",
    },
}


def plan_family_worship(
    *,
    weeks: int = 4,
    start_date: date | str | None = None,
    age_band: str = "middle",
    language: str = "en",
    topic_overrides: list[str] | None = None,
) -> list[FamilyWorshipPlan]:
    """Generate `weeks` of family worship plans for an age band."""
    if start_date is None:
        start_date = date.today()
    elif isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    topics = topic_overrides or suggest_topics_for_age(age_band)
    out: list[FamilyWorshipPlan] = []
    cursor = start_date
    for i in range(weeks):
        topic = topics[i % len(topics)]
        candidates = LESSON_BY_TOPIC.get(topic, [])
        lesson = candidates[0] if candidates else None
        theme = lesson.title.get(language, lesson.title["en"]) if lesson else topic.title()
        main_scripture = lesson.scripture_anchors[0] if (lesson and lesson.scripture_anchors) else ""
        secondary = list(lesson.scripture_anchors[1:3]) if lesson else []
        activity = _ACTIVITY_TEMPLATES.get(language, _ACTIVITY_TEMPLATES["en"]).get(age_band, "")
        out.append(
            FamilyWorshipPlan(
                week_of=cursor.isoformat(),
                theme=theme,
                main_scripture=main_scripture,
                secondary_scriptures=secondary,
                main_lesson=lesson,
                activity_hook=activity,
                song_suggestion=_song_for_topic(topic),
                age_target=age_band,
                language=language,
            )
        )
        cursor += timedelta(days=7)
    return out


def _song_for_topic(topic: str) -> int | None:
    """Hand-curated mapping topic → JW song number (Sing Out Joyfully)."""
    table = {
        "jesus": 9,
        "jehovah": 2,
        "love": 18,
        "obedience": 45,
        "ransom": 14,
        "happiness": 73,
        "temptation": 38,
        "death": 49,
        "suffering": 145,
    }
    return table.get(topic)
