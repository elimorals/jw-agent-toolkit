"""Bible quiz generator — age-bracketed.

Two layers:

  - Static `quiz_pool_for_age(age_band)` — curated, hand-written questions
    for known childhood favourites (Adam, Noah, David, Jesus' birth, etc.).
  - `generate_quiz` mixes static questions with verses pulled live from
    the WOL client when an LLM/agent wants them — but at this layer we
    only return STATIC questions so unit tests don't hit the network.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class QuizQuestion:
    prompt: dict[str, str]
    answer: dict[str, str]
    options: dict[str, list[str]] = field(default_factory=dict)
    scripture_ref: str = ""
    difficulty: str = "easy"
    age_band: str = "middle"
    topic: str = ""


_QUESTIONS: list[QuizQuestion] = [
    # ── younger band ─────────────────────────────────────────────
    QuizQuestion(
        prompt={
            "en": "Who was the first man Jehovah created?",
            "es": "¿Quién fue el primer hombre que creó Jehová?",
            "pt": "Quem foi o primeiro homem que Jeová criou?",
        },
        answer={"en": "Adam", "es": "Adán", "pt": "Adão"},
        options={"en": ["Adam", "Noah", "Abraham", "Moses"]},
        scripture_ref="Genesis 2:7",
        difficulty="easy",
        age_band="younger",
        topic="creation",
    ),
    QuizQuestion(
        prompt={
            "en": "How many people went into Noah's ark?",
            "es": "¿Cuántas personas entraron al arca de Noé?",
            "pt": "Quantas pessoas entraram na arca de Noé?",
        },
        answer={"en": "8", "es": "8", "pt": "8"},
        options={"en": ["6", "7", "8", "12"]},
        scripture_ref="1 Peter 3:20",
        difficulty="easy",
        age_band="younger",
        topic="noah",
    ),
    QuizQuestion(
        prompt={
            "en": "Where was Jesus born?",
            "es": "¿Dónde nació Jesús?",
            "pt": "Onde Jesus nasceu?",
        },
        answer={"en": "Bethlehem", "es": "Belén", "pt": "Belém"},
        scripture_ref="Luke 2:4-7",
        difficulty="easy",
        age_band="younger",
        topic="jesus",
    ),
    QuizQuestion(
        prompt={
            "en": "What is God's personal name?",
            "es": "¿Cuál es el nombre personal de Dios?",
            "pt": "Qual é o nome pessoal de Deus?",
        },
        answer={"en": "Jehovah", "es": "Jehová", "pt": "Jeová"},
        scripture_ref="Psalm 83:18",
        difficulty="easy",
        age_band="middle",
        topic="jehovah",
    ),
    QuizQuestion(
        prompt={
            "en": "Who fought Goliath with a sling?",
            "es": "¿Quién venció a Goliat con una honda?",
            "pt": "Quem derrotou Golias com uma funda?",
        },
        answer={"en": "David", "es": "David", "pt": "Davi"},
        scripture_ref="1 Samuel 17:50",
        difficulty="easy",
        age_band="middle",
        topic="courage",
    ),
    QuizQuestion(
        prompt={
            "en": "Which apostle wrote most of the New Testament letters?",
            "es": "¿Qué apóstol escribió la mayoría de las cartas del Nuevo Testamento?",
            "pt": "Qual apóstolo escreveu a maioria das cartas do Novo Testamento?",
        },
        answer={"en": "Paul", "es": "Pablo", "pt": "Paulo"},
        scripture_ref="2 Peter 3:15-16",
        difficulty="medium",
        age_band="middle",
        topic="paul",
    ),
    QuizQuestion(
        prompt={
            "en": "What language did Jesus most likely speak day to day?",
            "es": "¿Qué idioma habló cotidianamente Jesús?",
            "pt": "Que idioma Jesus falava no dia a dia?",
        },
        answer={"en": "Aramaic", "es": "Arameo", "pt": "Aramaico"},
        scripture_ref="Mark 5:41",
        difficulty="medium",
        age_band="older",
        topic="bible_languages",
    ),
    QuizQuestion(
        prompt={
            "en": "Who was caught up to the 'third heaven'?",
            "es": "¿Quién fue arrebatado al 'tercer cielo'?",
            "pt": "Quem foi arrebatado ao 'terceiro céu'?",
        },
        answer={"en": "Paul", "es": "Pablo", "pt": "Paulo"},
        scripture_ref="2 Corinthians 12:2",
        difficulty="hard",
        age_band="older",
        topic="paul",
    ),
]


# Expanded corpus (Gap 10): per-age curated questions sourced from publicly
# known Bible facts. Hand-vetted, no LLM in the loop.
_QUESTIONS.extend(
    [
        # Younger
        QuizQuestion(
            prompt={
                "en": "Which woman became the mother of all living?",
                "es": "¿Quién fue la madre de todos los humanos?",
                "pt": "Quem foi a mãe de todos os viventes?",
            },
            answer={"en": "Eve", "es": "Eva", "pt": "Eva"},
            options={"en": ["Sarah", "Rebekah", "Eve", "Rachel"]},
            scripture_ref="Genesis 3:20",
            age_band="younger",
            topic="creation",
        ),
        QuizQuestion(
            prompt={
                "en": "What city did the walls fall down at the sound of trumpets?",
                "es": "¿En qué ciudad cayeron las murallas al sonar las trompetas?",
                "pt": "Em que cidade os muros caíram ao som das trombetas?",
            },
            answer={"en": "Jericho", "es": "Jericó", "pt": "Jericó"},
            options={"en": ["Jericho", "Babylon", "Nineveh", "Jerusalem"]},
            scripture_ref="Joshua 6:20",
            age_band="younger",
            topic="joshua",
        ),
        QuizQuestion(
            prompt={
                "en": "How many days did Jonah spend inside the great fish?",
                "es": "¿Cuántos días pasó Jonás dentro del gran pez?",
                "pt": "Quantos dias Jonas passou dentro do grande peixe?",
            },
            answer={"en": "3", "es": "3", "pt": "3"},
            options={"en": ["1", "3", "7", "40"]},
            scripture_ref="Jonah 1:17",
            age_band="younger",
            topic="jonah",
        ),
        QuizQuestion(
            prompt={
                "en": "What kind of bread did Jehovah send the Israelites in the wilderness?",
                "es": "¿Qué pan envió Jehová a los israelitas en el desierto?",
                "pt": "Que pão Jeová enviou aos israelitas no deserto?",
            },
            answer={"en": "Manna", "es": "Maná", "pt": "Maná"},
            options={"en": ["Bread of life", "Manna", "Unleavened cake", "Honey"]},
            scripture_ref="Exodus 16:31",
            age_band="younger",
            topic="exodus",
        ),
        QuizQuestion(
            prompt={
                "en": "Which Bible character lived inside a fish for three days?",
                "es": "¿Qué personaje bíblico vivió tres días dentro de un pez?",
                "pt": "Que personagem viveu três dias dentro de um peixe?",
            },
            answer={"en": "Jonah", "es": "Jonás", "pt": "Jonas"},
            scripture_ref="Matthew 12:40",
            age_band="younger",
            topic="jonah",
        ),
        # Middle
        QuizQuestion(
            prompt={
                "en": "How many tribes did Israel originally have?",
                "es": "¿Cuántas tribus tenía originalmente Israel?",
                "pt": "Quantas tribos Israel tinha originalmente?",
            },
            answer={"en": "12", "es": "12", "pt": "12"},
            options={"en": ["7", "10", "12", "70"]},
            scripture_ref="Genesis 49:28",
            difficulty="medium",
            age_band="middle",
            topic="israel",
        ),
        QuizQuestion(
            prompt={
                "en": "Who built the ark before the Flood?",
                "es": "¿Quién construyó el arca antes del Diluvio?",
                "pt": "Quem construiu a arca antes do Dilúvio?",
            },
            answer={"en": "Noah", "es": "Noé", "pt": "Noé"},
            options={"en": ["Adam", "Enoch", "Noah", "Methuselah"]},
            scripture_ref="Genesis 6:14",
            age_band="middle",
            topic="noah",
        ),
        QuizQuestion(
            prompt={
                "en": "What is the first commandment Jesus said was the greatest?",
                "es": "¿Cuál es el primer mandamiento que Jesús dijo era el más grande?",
                "pt": "Qual o primeiro mandamento que Jesus disse ser o maior?",
            },
            answer={
                "en": "Love Jehovah with all your heart",
                "es": "Ama a Jehová con toda tu alma",
                "pt": "Amar a Jeová com toda a alma",
            },
            scripture_ref="Matthew 22:37",
            difficulty="medium",
            age_band="middle",
            topic="commandments",
        ),
        QuizQuestion(
            prompt={
                "en": "How many days did Jesus appear after His resurrection?",
                "es": "¿Cuántos días se apareció Jesús después de su resurrección?",
                "pt": "Por quantos dias Jesus apareceu após a ressurreição?",
            },
            answer={"en": "40", "es": "40", "pt": "40"},
            options={"en": ["7", "30", "40", "50"]},
            scripture_ref="Acts 1:3",
            difficulty="medium",
            age_band="middle",
            topic="resurrection",
        ),
        QuizQuestion(
            prompt={
                "en": "Which apostle walked on water with Jesus?",
                "es": "¿Qué apóstol caminó sobre el agua con Jesús?",
                "pt": "Qual apóstolo andou sobre as águas com Jesus?",
            },
            answer={"en": "Peter", "es": "Pedro", "pt": "Pedro"},
            options={"en": ["John", "Peter", "Andrew", "James"]},
            scripture_ref="Matthew 14:29",
            age_band="middle",
            topic="peter",
        ),
        # Older
        QuizQuestion(
            prompt={
                "en": "Which prophet was carried to heaven in a chariot of fire?",
                "es": "¿Qué profeta fue llevado al cielo en un carro de fuego?",
                "pt": "Que profeta foi levado ao céu num carro de fogo?",
            },
            answer={"en": "Elijah", "es": "Elías", "pt": "Elias"},
            options={"en": ["Elijah", "Elisha", "Isaiah", "Daniel"]},
            scripture_ref="2 Kings 2:11",
            difficulty="medium",
            age_band="older",
            topic="prophets",
        ),
        QuizQuestion(
            prompt={
                "en": "In whose reign did the Babylonian exile begin?",
                "es": "¿En el reinado de quién comenzó el exilio babilónico?",
                "pt": "Em qual reinado começou o exílio babilônico?",
            },
            answer={
                "en": "Nebuchadnezzar / Zedekiah",
                "es": "Nabucodonosor / Sedequías",
                "pt": "Nabucodonosor / Zedequias",
            },
            scripture_ref="2 Kings 25:7",
            difficulty="hard",
            age_band="older",
            topic="exile",
        ),
        QuizQuestion(
            prompt={
                "en": "What did Daniel refuse to eat at the king's table?",
                "es": "¿Qué se negó Daniel a comer en la mesa del rey?",
                "pt": "Que Daniel se recusou a comer à mesa do rei?",
            },
            answer={"en": "The king's delicacies", "es": "Los manjares del rey", "pt": "Os manjares do rei"},
            scripture_ref="Daniel 1:8",
            age_band="older",
            topic="daniel",
        ),
        QuizQuestion(
            prompt={
                "en": "What city was Jesus born in, per the prophecy in Micah?",
                "es": "¿En qué ciudad nació Jesús según la profecía de Miqueas?",
                "pt": "Em que cidade Jesus nasceu, segundo a profecia de Miqueias?",
            },
            answer={"en": "Bethlehem", "es": "Belén", "pt": "Belém"},
            scripture_ref="Micah 5:2",
            difficulty="medium",
            age_band="older",
            topic="prophecy",
        ),
        QuizQuestion(
            prompt={
                "en": "Which book ends with 'Maranatha!' meaning 'O Lord, come!'?",
                "es": "¿Qué libro termina con 'Marán Atá!' que significa '¡Señor nuestro, ven!'?",
                "pt": "Qual livro termina com 'Marana-ta!' que significa 'Vem, Senhor'?",
            },
            answer={"en": "1 Corinthians", "es": "1 Corintios", "pt": "1 Coríntios"},
            scripture_ref="1 Corinthians 16:22",
            difficulty="hard",
            age_band="older",
            topic="pauline_epistles",
        ),
        QuizQuestion(
            prompt={
                "en": "How many books does the Christian Greek Scriptures contain?",
                "es": "¿Cuántos libros tiene la Escrituras Griegas Cristianas?",
                "pt": "Quantos livros tem as Escrituras Gregas Cristãs?",
            },
            answer={"en": "27", "es": "27", "pt": "27"},
            options={"en": ["20", "27", "39", "66"]},
            scripture_ref="",
            difficulty="medium",
            age_band="older",
            topic="canon",
        ),
    ]
)


def quiz_pool_for_age(age_band: str) -> list[QuizQuestion]:
    return [q for q in _QUESTIONS if q.age_band == age_band]


def generate_quiz(
    *,
    age_band: str = "middle",
    n_questions: int = 5,
    language: str = "en",
    seed: int | None = None,
) -> list[dict[str, object]]:
    pool = quiz_pool_for_age(age_band) or _QUESTIONS
    rng = random.Random(seed)
    chosen = rng.sample(pool, k=min(n_questions, len(pool)))
    return [
        {
            "prompt": q.prompt.get(language, q.prompt["en"]),
            "answer": q.answer.get(language, q.answer["en"]),
            "options": q.options.get(language, q.options.get("en", [])),
            "scripture_ref": q.scripture_ref,
            "difficulty": q.difficulty,
            "topic": q.topic,
        }
        for q in chosen
    ]


# ── Procedural fill-in-the-blank generator ───────────────────────────────


def generate_fill_blank_question(
    verse_text: str,
    *,
    reference: str = "",
    language: str = "en",
    seed: int | None = None,
) -> dict[str, str]:
    """Build a fill-in-the-blank quiz question from a verse text.

    Picks the longest non-stopword word as the blank and surfaces both
    the masked prompt and the original answer.
    """
    rng = random.Random(seed)
    tokens = [t for t in verse_text.split() if t]
    candidates = [t for t in tokens if len(t) > 4 and t.lower() not in _STOPWORDS.get(language, _STOPWORDS["en"])]
    if not candidates:
        candidates = tokens
    word = rng.choice(candidates)
    masked = verse_text.replace(word, "____", 1)
    prompts = {
        "en": "Fill in the blank from",
        "es": "Complete el espacio en",
        "pt": "Preencha o espaço em",
    }
    return {
        "prompt": f"{prompts.get(language, prompts['en'])} {reference}: {masked}",
        "answer": word.strip(",.;:\"'()"),
        "scripture_ref": reference,
        "difficulty": "easy",
    }


_STOPWORDS: dict[str, set[str]] = {
    "en": {"the", "and", "for", "with", "that", "this", "from", "into", "have", "their", "your", "will", "would"},
    "es": {"que", "para", "como", "esta", "este", "esos", "esas", "sino", "pero", "ellos", "vuestro", "nuestro"},
    "pt": {"que", "para", "como", "esta", "este", "esses", "essas", "mas", "ele", "vosso", "nosso"},
}
