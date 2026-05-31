"""Plantillas para predicación en carrito (`kind=cart`).

Características:
  - Tiempo objetivo: 30 segundos (`time_target_seconds=30`).
  - Opener = pregunta corta (orientada a curiosidad).
  - Bridge = 1-2 réplicas posibles (la persona contesta sí / no / no sé).
  - Closing = invitación a tomar una publicación o leer la URL sugerida.
  - Sin presión: cart witnessing es pasivo por diseño.
"""

from __future__ import annotations

from jw_core.data.letter_templates import AUDIENCES, TOPIC_FAMILIES, LetterTemplate


def _t(en: str, es: str, pt: str) -> dict[str, str]:
    return {"en": en, "es": es, "pt": pt}


_CART_TIME = 30


_DEFAULT_GENERIC = LetterTemplate(
    opener=_t(
        en="Have you ever wondered what the Bible really teaches about "
           "the future?",
        es="¿Se ha preguntado alguna vez qué enseña realmente la Biblia "
           "sobre el futuro?",
        pt="O senhor já se perguntou o que a Bíblia realmente ensina "
           "sobre o futuro?",
    ),
    bridge=_t(
        en="Many say 'I'm not religious' — that's fine. The Bible has "
           "practical thoughts, not just religious ones.",
        es="Muchos dicen: «No soy religioso». Está bien. La Biblia "
           "tiene pensamientos prácticos, no solo religiosos.",
        pt="Muitos dizem: «Não sou religioso». Tudo bem. A Bíblia tem "
           "pensamentos práticos, não só religiosos.",
    ),
    closing=_t(
        en="Feel free to take this — no obligation.",
        es="Llévese esto si gusta, sin compromiso.",
        pt="Leve isto se quiser, sem compromisso.",
    ),
    suggested_scripture="Psalm 37:11",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_NEW_GENERIC = LetterTemplate(
    opener=_t(
        en="Hi — have you seen what the Bible really says about hope?",
        es="Hola, ¿ha visto lo que dice realmente la Biblia sobre la "
           "esperanza?",
        pt="Olá, o senhor já viu o que a Bíblia realmente diz sobre a "
           "esperança?",
    ),
    bridge=_t(
        en="It's free to look. One verse at a time.",
        es="Mirarlo es gratis. Un versículo a la vez.",
        pt="É grátis dar uma olhada. Um versículo de cada vez.",
    ),
    closing=_t(
        en="Take a brochure if you'd like.",
        es="Llévese un folleto si gusta.",
        pt="Leve um folheto, se quiser.",
    ),
    suggested_scripture="Isaiah 48:17",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_RELIGIOUS_GENERIC = LetterTemplate(
    opener=_t(
        en="As a believer, have you ever asked what Jesus really meant "
           "in a particular verse?",
        es="Como creyente, ¿se ha preguntado qué quiso decir Jesús "
           "realmente en algún versículo?",
        pt="Como crente, o senhor já se perguntou o que Jesus realmente "
           "quis dizer em algum versículo?",
    ),
    bridge=_t(
        en="Sometimes the original wording opens a window.",
        es="A veces el sentido original abre una ventana.",
        pt="Às vezes o sentido original abre uma janela.",
    ),
    closing=_t(
        en="Have a look at this if you'd like.",
        es="Eche un vistazo si gusta.",
        pt="Dê uma olhada se quiser.",
    ),
    suggested_scripture="John 17:3",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_ATHEIST_GENERIC = LetterTemplate(
    opener=_t(
        en="If you don't read the Bible, what would change your mind?",
        es="Si usted no lee la Biblia, ¿qué le haría cambiar de opinión?",
        pt="Se o senhor não lê a Bíblia, o que faria mudar de ideia?",
    ),
    bridge=_t(
        en="Honest answer: evidence and reasoning. That's what these "
           "publications focus on.",
        es="Respuesta honesta: evidencia y razonamiento. En eso se "
           "enfocan estas publicaciones.",
        pt="Resposta honesta: evidência e raciocínio. É nisso que estas "
           "publicações se concentram.",
    ),
    closing=_t(
        en="Take a copy — judge for yourself.",
        es="Tome una copia, juzgue usted mismo.",
        pt="Leve uma cópia, julgue por si mesmo.",
    ),
    suggested_scripture="Romans 1:20",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_GRIEVING_GENERIC = LetterTemplate(
    opener=_t(
        en="Have you ever wondered if the dead will live again?",
        es="¿Se ha preguntado si los muertos volverán a vivir?",
        pt="O senhor já se perguntou se os mortos voltarão a viver?",
    ),
    bridge=_t(
        en="The Bible gives a real, hope-shaped answer.",
        es="La Biblia da una respuesta real, con forma de esperanza.",
        pt="A Bíblia dá uma resposta real, em forma de esperança.",
    ),
    closing=_t(
        en="Free brochure if you want it.",
        es="Folleto gratis si lo quiere.",
        pt="Folheto grátis se quiser.",
    ),
    suggested_scripture="Acts 24:15",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_YOUNG_GENERIC = LetterTemplate(
    opener=_t(
        en="Quick question — what gives life meaning to you?",
        es="Pregunta rápida: ¿qué le da sentido a tu vida?",
        pt="Pergunta rápida: o que dá sentido à sua vida?",
    ),
    bridge=_t(
        en="The Bible asks the same thing — and answers it.",
        es="La Biblia hace la misma pregunta y la responde.",
        pt="A Bíblia faz a mesma pergunta e responde.",
    ),
    closing=_t(
        en="Grab one if it's relevant.",
        es="Toma uno si te interesa.",
        pt="Pegue um se for relevante.",
    ),
    suggested_scripture="Ecclesiastes 12:1",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


_PARENTS_GENERIC = LetterTemplate(
    opener=_t(
        en="As a parent, have you ever wished for clearer guidance?",
        es="Como persona con responsabilidades de crianza, ¿ha deseado "
           "alguna vez una guía más clara?",
        pt="Como pessoa que cria filhos, o senhor já desejou uma "
           "orientação mais clara?",
    ),
    bridge=_t(
        en="Bible principles are remarkably practical.",
        es="Los principios bíblicos son sorprendentemente prácticos.",
        pt="Os princípios bíblicos são surpreendentemente práticos.",
    ),
    closing=_t(
        en="Take a copy for the family.",
        es="Llévese una copia para la familia.",
        pt="Leve uma cópia para a família.",
    ),
    suggested_scripture="Proverbs 22:6",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_CART_TIME,
    word_count_target=0,
)


CART_TEMPLATES: dict[tuple[str, str], LetterTemplate] = {
    ("default", "generic"):   _DEFAULT_GENERIC,
    ("new", "generic"):       _NEW_GENERIC,
    ("religious", "generic"): _RELIGIOUS_GENERIC,
    ("atheist", "generic"):   _ATHEIST_GENERIC,
    ("grieving", "generic"):  _GRIEVING_GENERIC,
    ("young", "generic"):     _YOUNG_GENERIC,
    ("parents", "generic"):   _PARENTS_GENERIC,
}


def get_cart_template(audience: str, topic_family: str) -> LetterTemplate:
    """Fallback en cadena idéntico al de letter / phone."""

    aud = audience if audience in AUDIENCES else "default"
    fam = topic_family if topic_family in TOPIC_FAMILIES else "generic"
    if (aud, fam) in CART_TEMPLATES:
        return CART_TEMPLATES[(aud, fam)]
    if (aud, "generic") in CART_TEMPLATES:
        return CART_TEMPLATES[(aud, "generic")]
    return CART_TEMPLATES[("default", "generic")]
