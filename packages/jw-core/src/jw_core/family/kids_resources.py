"""Children's resources — catalog from 'Learn From the Great Teacher' (lf).

We ship the lesson titles (public information) + their scripture anchors +
age bands. The full body text is in the published book (downloadable via
`pub_media.get_publication("lf", language=...)`), so we don't redistribute
prose; we provide an INDEX that maps to it.

Age bands follow the publication's own segmentation:
  - 'younger': 3-7 years
  - 'middle' : 8-11
  - 'older'  : 12-15
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KidsLesson:
    chapter: int
    title: dict[str, str]
    topic: str  # canonical topic key
    age_bands: tuple[str, ...] = ("middle",)
    scripture_anchors: tuple[str, ...] = ()
    publication: str = "lf"  # JW symbol for the Great Teacher book


GREAT_TEACHER_LESSONS: list[KidsLesson] = [
    KidsLesson(
        chapter=1,
        title={"en": "A Teacher Greater Than Any Other", "es": "Un Maestro como ningún otro", "pt": "Um Mestre como nenhum outro"},
        topic="jesus",
        age_bands=("younger", "middle"),
        scripture_anchors=("John 1:14", "Matthew 28:18"),
    ),
    KidsLesson(
        chapter=3,
        title={"en": "Who is Jehovah?", "es": "¿Quién es Jehová?", "pt": "Quem é Jeová?"},
        topic="jehovah",
        age_bands=("younger", "middle"),
        scripture_anchors=("Psalm 83:18", "Exodus 3:15"),
    ),
    KidsLesson(
        chapter=8,
        title={"en": "Why Should We Obey God?", "es": "¿Por qué debemos obedecer a Dios?", "pt": "Por que devemos obedecer a Deus?"},
        topic="obedience",
        age_bands=("middle", "older"),
        scripture_anchors=("Ecclesiastes 12:13", "1 Samuel 15:22"),
    ),
    KidsLesson(
        chapter=10,
        title={"en": "Why Did Jesus Die for Us?", "es": "¿Por qué murió Jesús por nosotros?", "pt": "Por que Jesus morreu por nós?"},
        topic="ransom",
        age_bands=("middle", "older"),
        scripture_anchors=("John 3:16", "Romans 5:12"),
    ),
    KidsLesson(
        chapter=13,
        title={"en": "How Can You Show Love?", "es": "¿Cómo puedes demostrar amor?", "pt": "Como você pode mostrar amor?"},
        topic="love",
        age_bands=("younger", "middle"),
        scripture_anchors=("1 John 4:8", "John 13:34-35"),
    ),
    KidsLesson(
        chapter=22,
        title={"en": "How to Resist Temptation", "es": "Cómo resistir la tentación", "pt": "Como resistir à tentação"},
        topic="temptation",
        age_bands=("middle", "older"),
        scripture_anchors=("1 Corinthians 10:13", "James 1:14-15"),
    ),
    KidsLesson(
        chapter=29,
        title={"en": "How to Be Truly Happy", "es": "Cómo ser verdaderamente feliz", "pt": "Como ser verdadeiramente feliz"},
        topic="happiness",
        age_bands=("younger", "middle", "older"),
        scripture_anchors=("Acts 20:35", "Psalm 144:15"),
    ),
    KidsLesson(
        chapter=35,
        title={"en": "Where Are the Dead?", "es": "¿Dónde están los muertos?", "pt": "Onde estão os mortos?"},
        topic="death",
        age_bands=("middle", "older"),
        scripture_anchors=("Ecclesiastes 9:5", "John 11:11-14"),
    ),
    KidsLesson(
        chapter=46,
        title={"en": "Why God Allows Suffering", "es": "Por qué Dios permite el sufrimiento", "pt": "Por que Deus permite o sofrimento"},
        topic="suffering",
        age_bands=("older",),
        scripture_anchors=("James 1:13", "Romans 5:12"),
    ),
]


# Quick lookup by canonical topic.
LESSON_BY_TOPIC: dict[str, list[KidsLesson]] = {}
for lesson in GREAT_TEACHER_LESSONS:
    LESSON_BY_TOPIC.setdefault(lesson.topic, []).append(lesson)


def list_lessons_for_age(age_band: str, *, language: str = "en") -> list[dict[str, object]]:
    """Return the lessons appropriate for `age_band`, localized."""
    items = []
    for lesson in GREAT_TEACHER_LESSONS:
        if age_band not in lesson.age_bands:
            continue
        items.append(
            {
                "chapter": lesson.chapter,
                "title": lesson.title.get(language, lesson.title["en"]),
                "topic": lesson.topic,
                "scripture_anchors": list(lesson.scripture_anchors),
                "publication": lesson.publication,
                "age_bands": list(lesson.age_bands),
            }
        )
    return items


def pick_lesson_by_topic(topic: str, *, language: str = "en") -> dict[str, object] | None:
    """Return the first lesson whose topic key matches (case-insensitive)."""
    candidates = LESSON_BY_TOPIC.get(topic.lower())
    if not candidates:
        return None
    lesson = candidates[0]
    return {
        "chapter": lesson.chapter,
        "title": lesson.title.get(language, lesson.title["en"]),
        "topic": lesson.topic,
        "scripture_anchors": list(lesson.scripture_anchors),
        "publication": lesson.publication,
        "age_bands": list(lesson.age_bands),
    }
