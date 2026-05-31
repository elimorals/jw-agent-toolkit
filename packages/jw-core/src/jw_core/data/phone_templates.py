"""Plantillas para predicación telefónica (`kind=phone`).

Diferencias clave con cartas:
  - `time_target_seconds = 75` (objetivo orientativo, no enforced).
  - `word_count_target = 0`. La métrica es tiempo, no palabras.
  - El opener pide permiso para hablar 1-2 minutos (registro oral).
  - Closing siempre incluye una pregunta abierta para invitar respuesta.
"""

from __future__ import annotations

from jw_core.data.letter_templates import AUDIENCES, TOPIC_FAMILIES, LetterTemplate


def _t(en: str, es: str, pt: str) -> dict[str, str]:
    return {"en": en, "es": es, "pt": pt}


_PHONE_TIME = 75


_DEFAULT_GENERIC = LetterTemplate(
    opener=_t(
        en="Good morning — my name is __. I'm calling neighbors briefly "
           "to share one short Bible thought. Do you have about a minute?",
        es="Buenos días, mi nombre es __. Estoy llamando brevemente a "
           "personas de la zona para compartir un pensamiento bíblico "
           "corto. ¿Tiene aproximadamente un minuto?",
        pt="Bom dia, meu nome é __. Estou ligando rapidamente para "
           "compartilhar um breve pensamento bíblico. O senhor tem cerca "
           "de um minuto?",
    ),
    bridge=_t(
        en="Many today wonder where to find practical guidance. The "
           "Bible verse I have in mind addresses exactly that.",
        es="Muchas personas hoy se preguntan dónde hallar guía práctica. "
           "El versículo bíblico que tengo en mente trata justamente "
           "ese tema.",
        pt="Muitas pessoas hoje se perguntam onde encontrar orientação "
           "prática. O versículo bíblico que tenho em mente trata "
           "exatamente disso.",
    ),
    closing=_t(
        en="What do you think — does that thought match your experience?",
        es="¿Qué piensa usted: encaja ese pensamiento con su experiencia?",
        pt="O que o senhor acha: esse pensamento combina com sua "
           "experiência?",
    ),
    suggested_scripture="Psalm 37:11",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_NEW_GENERIC = LetterTemplate(
    opener=_t(
        en="Hi — I won't take much of your time. Quick Bible-based "
           "thought, would that be okay?",
        es="Hola, no le quitaré mucho tiempo. Un pensamiento bíblico "
           "breve, ¿le parece bien?",
        pt="Olá, não tomarei muito do seu tempo. Um pensamento bíblico "
           "breve, tudo bem?",
    ),
    bridge=_t(
        en="The Bible has a record of guiding lives over thousands of "
           "years. One verse can already give a fresh angle.",
        es="La Biblia tiene un historial de guiar vidas por miles de "
           "años. Un solo versículo ya puede dar otro ángulo.",
        pt="A Bíblia tem um histórico de guiar vidas por milhares de "
           "anos. Um versículo já pode dar um ângulo novo.",
    ),
    closing=_t(
        en="Would you ever consider exploring more, in your own time?",
        es="¿Consideraría explorar más, a su propio ritmo?",
        pt="O senhor consideraria explorar mais, no seu próprio ritmo?",
    ),
    suggested_scripture="Isaiah 48:17",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_RELIGIOUS_GENERIC = LetterTemplate(
    opener=_t(
        en="Good day — I'm calling to share a brief Bible reflection with "
           "people of faith. Have you got a moment?",
        es="Buen día. Llamo para compartir una breve reflexión bíblica "
           "con personas de fe. ¿Tiene un momento?",
        pt="Bom dia. Estou ligando para compartilhar uma breve reflexão "
           "bíblica com pessoas de fé. O senhor tem um momento?",
    ),
    bridge=_t(
        en="Even familiar passages reveal new layers on careful reading. "
           "The thought I'd share takes thirty seconds.",
        es="Incluso pasajes familiares revelan capas nuevas al releerlos. "
           "El pensamiento que quiero compartir toma medio minuto.",
        pt="Mesmo passagens conhecidas revelam camadas novas ao serem "
           "relidas. O pensamento leva meio minuto.",
    ),
    closing=_t(
        en="Has anything in this passage stood out to you before?",
        es="¿Ha notado antes algo destacable en este pasaje?",
        pt="O senhor já notou algo nesse pasaje antes?",
    ),
    suggested_scripture="John 17:3",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_ATHEIST_GENERIC = LetterTemplate(
    opener=_t(
        en="Hi — I'm not selling anything. Just a one-minute Bible-based "
           "thought, no assumptions about your views. Okay?",
        es="Hola, no vendo nada. Solo un pensamiento bíblico de un "
           "minuto, sin presuponer sus creencias. ¿Le parece?",
        pt="Olá, não estou vendendo nada. Só um pensamento bíblico de "
           "um minuto, sem supor suas crenças. Tudo bem?",
    ),
    bridge=_t(
        en="If a designer exists, evidence should be findable. Romans "
           "1:20 makes that exact claim — open to scrutiny.",
        es="Si existe un diseñador, debería haber evidencia. Romanos "
           "1:20 afirma justamente eso — abierto al examen.",
        pt="Se existe um designer, deveria haver evidência. Romanos "
           "1:20 afirma exatamente isso — aberto ao exame.",
    ),
    closing=_t(
        en="What would you count as good evidence?",
        es="¿Qué consideraría usted como buena evidencia?",
        pt="O que o senhor consideraria como boa evidência?",
    ),
    suggested_scripture="Romans 1:20",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_GRIEVING_GENERIC = LetterTemplate(
    opener=_t(
        en="Hi — I'll be brief. I have one Bible thought that's brought "
           "comfort to many in grief. May I share it?",
        es="Hola, seré breve. Tengo un pensamiento bíblico que ha "
           "consolado a muchos en el duelo. ¿Puedo compartirlo?",
        pt="Olá, serei breve. Tenho um pensamento bíblico que tem "
           "consolado muitos no luto. Posso compartilhar?",
    ),
    bridge=_t(
        en="Loss doesn't have to be the final word. The verse I'm "
           "thinking of speaks gently and concretely.",
        es="La pérdida no tiene por qué ser la última palabra. El "
           "versículo en el que pienso habla con ternura y de modo "
           "concreto.",
        pt="A perda não precisa ser a última palavra. O versículo no "
           "qual penso fala com ternura e de modo concreto.",
    ),
    closing=_t(
        en="Has that resonated, even a little?",
        es="¿Le resuena algo, aunque sea un poco?",
        pt="Isso ressoa, mesmo que um pouco?",
    ),
    suggested_scripture="Revelation 21:4",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_YOUNG_GENERIC = LetterTemplate(
    opener=_t(
        en="Hey — quick call, one Bible thought, under a minute. Cool?",
        es="Hola, llamada breve, un pensamiento bíblico, menos de un "
           "minuto. ¿Te parece?",
        pt="Oi, ligação rápida, um pensamento bíblico, menos de um "
           "minuto. Tudo bem?",
    ),
    bridge=_t(
        en="A lot hits at once when you're young — identity, future, "
           "what counts. Bible has practical takes.",
        es="A los jóvenes se les viene mucho de golpe — identidad, "
           "futuro, qué importa. La Biblia tiene enfoques prácticos.",
        pt="Quando se é jovem, vem muita coisa de uma vez — identidade, "
           "futuro, o que importa. A Bíblia tem enfoques práticos.",
    ),
    closing=_t(
        en="Anything in that resonate with you?",
        es="¿Algo de eso te resuena?",
        pt="Algo disso ressoa em você?",
    ),
    suggested_scripture="Ecclesiastes 12:1",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


_PARENTS_GENERIC = LetterTemplate(
    opener=_t(
        en="Hi — I'm a parent too. One short Bible thought on raising "
           "kids today, may I share it?",
        es="Hola, también tengo responsabilidades de crianza. Un "
           "pensamiento bíblico breve sobre criar hoy, ¿se lo comparto?",
        pt="Olá, também crio filhos. Um pensamento bíblico breve sobre "
           "criação hoje, posso compartilhar?",
    ),
    bridge=_t(
        en="The Bible's family advice is surprisingly practical. One "
           "verse holds up under everyday pressure.",
        es="Los consejos bíblicos sobre familia son sorprendentemente "
           "prácticos. Un versículo aguanta la presión del día a día.",
        pt="Os conselhos bíblicos sobre família são surpreendentemente "
           "práticos. Um versículo aguenta a pressão do dia a dia.",
    ),
    closing=_t(
        en="What's been the hardest part for your home lately?",
        es="¿Qué ha sido lo más difícil últimamente en su hogar?",
        pt="Qual tem sido a parte mais difícil em casa ultimamente?",
    ),
    suggested_scripture="Proverbs 22:6",
    suggested_jw_link="https://www.jw.org/",
    time_target_seconds=_PHONE_TIME,
    word_count_target=0,
)


PHONE_TEMPLATES: dict[tuple[str, str], LetterTemplate] = {
    ("default", "generic"):  _DEFAULT_GENERIC,
    ("new", "generic"):      _NEW_GENERIC,
    ("religious", "generic"):_RELIGIOUS_GENERIC,
    ("atheist", "generic"):  _ATHEIST_GENERIC,
    ("grieving", "generic"): _GRIEVING_GENERIC,
    ("young", "generic"):    _YOUNG_GENERIC,
    ("parents", "generic"):  _PARENTS_GENERIC,
}


def get_phone_template(audience: str, topic_family: str) -> LetterTemplate:
    """Igual semántica de fallback que `get_template` en letter_templates."""

    aud = audience if audience in AUDIENCES else "default"
    fam = topic_family if topic_family in TOPIC_FAMILIES else "generic"
    if (aud, fam) in PHONE_TEMPLATES:
        return PHONE_TEMPLATES[(aud, fam)]
    if (aud, "generic") in PHONE_TEMPLATES:
        return PHONE_TEMPLATES[(aud, "generic")]
    return PHONE_TEMPLATES[("default", "generic")]
