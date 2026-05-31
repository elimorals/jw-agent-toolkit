"""Templates for the 4 student-part kinds × 4 audiences × 3 languages.

Each `PartTemplate` is a frozen dataclass with four short string fields
(`opening`, `body`, `transition`, `close`), each containing `{placeholder}`
slots that the agent fills with the resolved scripture, topic, oratory
phrase, etc.

Lookup falls back gracefully:
    (kind, audience, language) → (kind, 'default', language) →
    (kind, 'default', 'en').

Time targets are STATIC per kind. They are NOT enforced (no auto-trim);
the script just reports the target seconds for the user/LLM to verify.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["bible_reading", "starting_conversation", "return_visit", "bible_study"]
Audience = Literal["default", "new", "religious", "atheist"]
Language = Literal["en", "es", "pt"]

_KIND_TIME_SECONDS: dict[str, int] = {
    "bible_reading": 240,
    "starting_conversation": 180,
    "return_visit": 240,
    "bible_study": 300,
}


@dataclass(frozen=True)
class PartTemplate:
    kind: Kind
    audience: Audience
    language: Language
    opening: str
    body: str
    transition: str
    close: str
    time_target_seconds: int
    required_placeholders: tuple[str, ...]


def time_target_seconds_for(kind: str) -> int:
    """Static time target per kind. Raises ValueError on unknown kind."""
    if kind not in _KIND_TIME_SECONDS:
        raise ValueError(f"Unknown student-part kind: {kind!r}")
    return _KIND_TIME_SECONDS[kind]


# ── Template construction helper ────────────────────────────────────────


def _t(
    kind: Kind,
    audience: Audience,
    language: Language,
    opening: str,
    body: str,
    transition: str,
    close: str,
    required_placeholders: tuple[str, ...] = ("verse_display", "oratory_phrase"),
) -> PartTemplate:
    return PartTemplate(
        kind=kind,
        audience=audience,
        language=language,
        opening=opening,
        body=body,
        transition=transition,
        close=close,
        time_target_seconds=_KIND_TIME_SECONDS[kind],
        required_placeholders=required_placeholders,
    )


# ── BIBLE READING ───────────────────────────────────────────────────────


_BR_EN_DEFAULT = _t(
    "bible_reading",
    "default",
    "en",
    opening="The reading today is {verse_display}. Listen for the main idea this passage drives home.",
    body="As I read, notice how the writer builds the thought. I'll apply the point '{oratory_phrase}' — {oratory_brief}",
    transition="Now, having heard those words, consider what they imply for our worship.",
    close="May this reading move us to act in harmony with what it says.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_ES_DEFAULT = _t(
    "bible_reading",
    "default",
    "es",
    opening="La lectura de hoy es {verse_display}. Atienda a la idea principal que el pasaje destaca.",
    body="Mientras leo, fíjese en cómo el escritor construye la idea. Aplicaré el punto '{oratory_phrase}' — {oratory_brief}",
    transition="Habiendo escuchado esas palabras, considere qué implican para nuestra adoración.",
    close="Que esta lectura nos mueva a actuar conforme a lo que dice.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_PT_DEFAULT = _t(
    "bible_reading",
    "default",
    "pt",
    opening="A leitura de hoje é {verse_display}. Atente para a ideia principal que o trecho destaca.",
    body="Enquanto leio, observe como o escritor constrói o pensamento. Aplicarei o ponto '{oratory_phrase}' — {oratory_brief}",
    transition="Tendo escutado essas palavras, considere o que elas implicam para nossa adoração.",
    close="Que esta leitura nos mova a agir conforme o que diz.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

# The 'new', 'religious', 'atheist' variants differ only in the framing of
# opening/transition/close — body keeps the same '{oratory_phrase}' hook.
_BR_EN_NEW = _t(
    "bible_reading",
    "new",
    "en",
    "Today's reading is {verse_display}. You'll hear a thought that you can apply this week.",
    "While I read, listen for the main point. I'll keep '{oratory_phrase}' in mind — {oratory_brief}",
    "What we just heard answers a real question many people have.",
    "Thank you for listening — may these words encourage you.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_EN_REL = _t(
    "bible_reading",
    "religious",
    "en",
    "Many cherish the words we will read: {verse_display}. Let's listen together.",
    "As I read, notice the original sense. The point '{oratory_phrase}' applies — {oratory_brief}",
    "Compared with how this is often quoted, the full passage gives a fuller picture.",
    "May reading the Scriptures together build us up in faith.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_EN_ATH = _t(
    "bible_reading",
    "atheist",
    "en",
    "Whether or not one accepts the Bible, the passage {verse_display} is worth hearing for its argument.",
    "Notice the logic of the text. I'll apply '{oratory_phrase}' so the structure is clear — {oratory_brief}",
    "Set aside belief for a moment — what claim is the writer making?",
    "Thanks for the open-minded hearing.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

_BR_ES_NEW = _t(
    "bible_reading",
    "new",
    "es",
    "La lectura de hoy es {verse_display}. Escuchará una idea que podrá aplicar esta semana.",
    "Mientras leo, atienda al punto principal. Tendré en cuenta '{oratory_phrase}' — {oratory_brief}",
    "Lo que acabamos de oír responde una pregunta real que muchos tienen.",
    "Gracias por escuchar; que estas palabras le animen.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_ES_REL = _t(
    "bible_reading",
    "religious",
    "es",
    "Muchos aprecian las palabras que leeremos: {verse_display}. Escuchemos juntos.",
    "Mientras leo, observe el sentido original. Aplica el punto '{oratory_phrase}' — {oratory_brief}",
    "Comparado con la cita habitual, el pasaje completo aporta más contexto.",
    "Que leer las Escrituras juntos nos edifique en la fe.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_ES_ATH = _t(
    "bible_reading",
    "atheist",
    "es",
    "Acepte o no la Biblia, el pasaje {verse_display} vale la pena escucharlo por su argumento.",
    "Note la lógica del texto. Aplicaré '{oratory_phrase}' para que la estructura se vea clara — {oratory_brief}",
    "Por un momento, deje a un lado la creencia: ¿qué afirma el escritor?",
    "Gracias por la escucha abierta.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

_BR_PT_NEW = _t(
    "bible_reading",
    "new",
    "pt",
    "A leitura de hoje é {verse_display}. Você ouvirá uma ideia que poderá aplicar nesta semana.",
    "Enquanto leio, observe o ponto principal. Manterei '{oratory_phrase}' em mente — {oratory_brief}",
    "O que acabamos de ouvir responde a uma pergunta real que muitos têm.",
    "Obrigado por escutar; que essas palavras lhe animem.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_PT_REL = _t(
    "bible_reading",
    "religious",
    "pt",
    "Muitos apreciam as palavras que leremos: {verse_display}. Vamos escutar juntos.",
    "Enquanto leio, observe o sentido original. Aplica-se o ponto '{oratory_phrase}' — {oratory_brief}",
    "Comparado à citação habitual, o trecho completo dá mais contexto.",
    "Que ler as Escrituras juntos nos edifique na fé.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_PT_ATH = _t(
    "bible_reading",
    "atheist",
    "pt",
    "Aceitando ou não a Bíblia, o trecho {verse_display} vale a pena ser escutado pelo argumento.",
    "Note a lógica do texto. Aplicarei '{oratory_phrase}' para que a estrutura fique clara — {oratory_brief}",
    "Por um momento, deixe de lado a crença: o que o escritor afirma?",
    "Obrigado pela escuta aberta.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)


# ── STARTING CONVERSATION ───────────────────────────────────────────────


_SC_EN_DEF = _t(
    "starting_conversation",
    "default",
    "en",
    "Hello — many today are searching for hope amid difficult news. Have you noticed that?",
    "The Bible at {verse_display} offers a thought worth comparing. As I share, I'll apply '{oratory_phrase}' — {oratory_brief}",
    "What stands out to you in that verse?",
    "Thank you for your time — I'd love to share more next week.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_EN_NEW = _t(
    "starting_conversation",
    "new",
    "en",
    "Hi! I'm visiting neighbors with a brief encouragement. Do you have a minute?",
    "I'd like to read {verse_display} and ask you a question. Applying '{oratory_phrase}' — {oratory_brief}",
    "Have you thought about that idea before?",
    "Thanks — I'd be happy to follow up.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_EN_REL = _t(
    "starting_conversation",
    "religious",
    "en",
    "It's good to meet someone who values the Bible. Have you ever thought about how {topic} fits with Scripture?",
    "Consider {verse_display}. With the point '{oratory_phrase}' in mind — {oratory_brief}",
    "Does that match what you've understood?",
    "Thank you for the open dialogue.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"),
)
_SC_EN_ATH = _t(
    "starting_conversation",
    "atheist",
    "en",
    "I appreciate honest conversations about meaning. Even without religious assumptions, the Bible raises real questions.",
    "Take {verse_display}. Whatever your view, '{oratory_phrase}' helps engage the text — {oratory_brief}",
    "What's your honest reaction to that?",
    "Thanks for taking the question seriously.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

_SC_ES_DEF = _t(
    "starting_conversation",
    "default",
    "es",
    "Hola — muchos hoy buscan esperanza ante noticias difíciles. ¿Lo ha notado?",
    "La Biblia, en {verse_display}, ofrece una idea que vale la pena comparar. Aplicaré '{oratory_phrase}' — {oratory_brief}",
    "¿Qué le llama la atención de ese versículo?",
    "Gracias por su tiempo — me gustaría compartir más la próxima semana.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_ES_NEW = _t(
    "starting_conversation",
    "new",
    "es",
    "¡Hola! Visito a los vecinos con un breve ánimo. ¿Tiene un minuto?",
    "Quisiera leer {verse_display} y hacerle una pregunta. Aplicando '{oratory_phrase}' — {oratory_brief}",
    "¿Había pensado antes en esa idea?",
    "Gracias — con gusto vuelvo otro día.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_ES_REL = _t(
    "starting_conversation",
    "religious",
    "es",
    "Es bueno encontrar a alguien que aprecie la Biblia. ¿Ha pensado cómo encaja {topic} con la Escritura?",
    "Considere {verse_display}. Con el punto '{oratory_phrase}' en mente — {oratory_brief}",
    "¿Coincide con lo que ha entendido?",
    "Gracias por el diálogo abierto.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"),
)
_SC_ES_ATH = _t(
    "starting_conversation",
    "atheist",
    "es",
    "Aprecio las conversaciones honestas sobre el sentido. Aun sin supuestos religiosos, la Biblia plantea preguntas reales.",
    "Tome {verse_display}. Sea cual sea su postura, '{oratory_phrase}' ayuda a abordar el texto — {oratory_brief}",
    "¿Cuál es su reacción honesta?",
    "Gracias por tomar la pregunta en serio.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

_SC_PT_DEF = _t(
    "starting_conversation",
    "default",
    "pt",
    "Olá — muitos hoje buscam esperança em meio a notícias difíceis. Você tem percebido isso?",
    "A Bíblia, em {verse_display}, oferece uma ideia que vale a pena comparar. Aplicarei '{oratory_phrase}' — {oratory_brief}",
    "O que chama sua atenção nesse versículo?",
    "Obrigado pelo seu tempo — gostaria de compartilhar mais na próxima semana.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_PT_NEW = _t(
    "starting_conversation",
    "new",
    "pt",
    "Oi! Estou visitando vizinhos com um breve incentivo. Você tem um minuto?",
    "Eu gostaria de ler {verse_display} e fazer uma pergunta. Aplicando '{oratory_phrase}' — {oratory_brief}",
    "Você já tinha pensado nessa ideia?",
    "Obrigado — terei prazer em voltar.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_SC_PT_REL = _t(
    "starting_conversation",
    "religious",
    "pt",
    "É bom encontrar alguém que valoriza a Bíblia. Você já pensou como {topic} se encaixa com a Escritura?",
    "Considere {verse_display}. Com o ponto '{oratory_phrase}' em mente — {oratory_brief}",
    "Combina com o que você tem entendido?",
    "Obrigado pelo diálogo aberto.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"),
)
_SC_PT_ATH = _t(
    "starting_conversation",
    "atheist",
    "pt",
    "Aprecio conversas honestas sobre sentido. Mesmo sem pressupostos religiosos, a Bíblia levanta perguntas reais.",
    "Tome {verse_display}. Qualquer que seja sua posição, '{oratory_phrase}' ajuda a abordar o texto — {oratory_brief}",
    "Qual sua reação honesta?",
    "Obrigado por levar a pergunta a sério.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)


# ── RETURN VISIT ────────────────────────────────────────────────────────


_RV_EN_DEF = _t(
    "return_visit",
    "default",
    "en",
    "Good to see you again. Last time we touched on {prior_seed}.",
    "I brought {verse_display} to develop that thought. Today I'll apply '{oratory_phrase}' — {oratory_brief}",
    "What has come to mind since we last talked?",
    "Next time I'd like to discuss {next_visit_hook}. Would that work?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_EN_NEW = _t(
    "return_visit",
    "new",
    "en",
    "Thanks for letting me come back. Last time we left off at {prior_seed}.",
    "Look at {verse_display} with me — the point '{oratory_phrase}' helps us read it — {oratory_brief}",
    "Has anything in your week reminded you of this?",
    "Could I share {next_visit_hook} next time?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_EN_REL = _t(
    "return_visit",
    "religious",
    "en",
    "Last time you mentioned {prior_seed}. I've been looking forward to today.",
    "Compare your view with {verse_display}. The point '{oratory_phrase}' is useful here — {oratory_brief}",
    "What does this open up for you?",
    "Next we could examine {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_EN_ATH = _t(
    "return_visit",
    "atheist",
    "en",
    "You raised a fair point last time about {prior_seed}. I thought about it.",
    "Look at {verse_display}. With '{oratory_phrase}' as a frame — {oratory_brief}",
    "Does that move the question for you, even a little?",
    "I'd like to bring {next_visit_hook} next time.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)

_RV_ES_DEF = _t(
    "return_visit",
    "default",
    "es",
    "Qué gusto verlo de nuevo. La última vez tocamos {prior_seed}.",
    "Traje {verse_display} para desarrollar esa idea. Hoy aplicaré '{oratory_phrase}' — {oratory_brief}",
    "¿Qué le ha venido a la mente desde nuestra última conversación?",
    "La próxima vez quisiera tratar {next_visit_hook}. ¿Le parece?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_ES_NEW = _t(
    "return_visit",
    "new",
    "es",
    "Gracias por permitirme volver. La última vez quedamos en {prior_seed}.",
    "Veamos {verse_display} — el punto '{oratory_phrase}' ayuda a leerlo — {oratory_brief}",
    "¿Algo en su semana le ha recordado esto?",
    "¿Podría compartir {next_visit_hook} la próxima?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_ES_REL = _t(
    "return_visit",
    "religious",
    "es",
    "La vez pasada mencionó {prior_seed}. Tenía ganas de hablar hoy.",
    "Compare su postura con {verse_display}. El punto '{oratory_phrase}' resulta útil — {oratory_brief}",
    "¿Qué le abre eso?",
    "La próxima podríamos examinar {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_ES_ATH = _t(
    "return_visit",
    "atheist",
    "es",
    "Planteó algo justo la última vez sobre {prior_seed}. Lo pensé.",
    "Vea {verse_display}. Con '{oratory_phrase}' como marco — {oratory_brief}",
    "¿Mueve eso la pregunta, aunque sea un poco?",
    "Me gustaría traer {next_visit_hook} la próxima.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)

_RV_PT_DEF = _t(
    "return_visit",
    "default",
    "pt",
    "Que bom ver você de novo. Da última vez tocamos em {prior_seed}.",
    "Trouxe {verse_display} para desenvolver essa ideia. Hoje aplicarei '{oratory_phrase}' — {oratory_brief}",
    "O que veio à sua mente desde a última conversa?",
    "Na próxima gostaria de tratar {next_visit_hook}. Você concorda?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_PT_NEW = _t(
    "return_visit",
    "new",
    "pt",
    "Obrigado por me deixar voltar. Da última vez paramos em {prior_seed}.",
    "Vamos ver {verse_display} — o ponto '{oratory_phrase}' ajuda a ler — {oratory_brief}",
    "Algo na sua semana lembrou isto?",
    "Posso compartilhar {next_visit_hook} na próxima?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_PT_REL = _t(
    "return_visit",
    "religious",
    "pt",
    "Da última vez você mencionou {prior_seed}. Estava ansioso por hoje.",
    "Compare sua posição com {verse_display}. O ponto '{oratory_phrase}' é útil — {oratory_brief}",
    "O que isso abre para você?",
    "Na próxima poderíamos examinar {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)
_RV_PT_ATH = _t(
    "return_visit",
    "atheist",
    "pt",
    "Você levantou algo justo da última vez sobre {prior_seed}. Pensei nisso.",
    "Veja {verse_display}. Com '{oratory_phrase}' como moldura — {oratory_brief}",
    "Isso move a pergunta para você, mesmo que pouco?",
    "Gostaria de trazer {next_visit_hook} na próxima.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"),
)


# ── BIBLE STUDY DEMO ────────────────────────────────────────────────────


_BS_EN_DEF = _t(
    "bible_study",
    "default",
    "en",
    "Today we'll cover paragraph {paragraph} of {topic}. Notice what it teaches about {focus}.",
    "Read with me. After we read, I'll apply the point '{oratory_phrase}' — {oratory_brief}. The supporting text is {verse_display}.",
    "Question to consider: how does this affect what we do this week?",
    "Next time we'll work on paragraph {next_paragraph}.",
    required_placeholders=(
        "verse_display",
        "oratory_phrase",
        "oratory_brief",
        "topic",
        "paragraph",
        "next_paragraph",
        "focus",
    ),
)
_BS_EN_NEW = _t(
    "bible_study",
    "new",
    "en",
    "We'll look at paragraph {paragraph} of {topic} — a thought you can use this week.",
    "Read with me; I'll apply '{oratory_phrase}' so the point is clear — {oratory_brief}. See also {verse_display}.",
    "What part of this answers a real question for you?",
    "Next time, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_EN_REL = _t(
    "bible_study",
    "religious",
    "en",
    "Today paragraph {paragraph} of {topic} — see how it lines up with what you've understood.",
    "Read with me. Applying '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "Where does this match your own reading of Scripture?",
    "Next, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_EN_ATH = _t(
    "bible_study",
    "atheist",
    "en",
    "Paragraph {paragraph} of {topic} — read it as an argument, see if it stands.",
    "We'll read together; '{oratory_phrase}' will help us examine it — {oratory_brief}. The cited text is {verse_display}.",
    "Where does the argument hold or fail?",
    "Next time, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)

_BS_ES_DEF = _t(
    "bible_study",
    "default",
    "es",
    "Hoy veremos el párrafo {paragraph} de {topic}. Note qué enseña sobre {focus}.",
    "Leamos juntos. Después, aplicaré el punto '{oratory_phrase}' — {oratory_brief}. El texto de apoyo es {verse_display}.",
    "Pregunta: ¿cómo afecta esto lo que haremos esta semana?",
    "La próxima trabajaremos el párrafo {next_paragraph}.",
    required_placeholders=(
        "verse_display",
        "oratory_phrase",
        "oratory_brief",
        "topic",
        "paragraph",
        "next_paragraph",
        "focus",
    ),
)
_BS_ES_NEW = _t(
    "bible_study",
    "new",
    "es",
    "Veremos el párrafo {paragraph} de {topic} — una idea útil para esta semana.",
    "Leamos juntos; aplicaré '{oratory_phrase}' para que el punto se vea claro — {oratory_brief}. Vea también {verse_display}.",
    "¿Qué parte le contesta una pregunta real?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_ES_REL = _t(
    "bible_study",
    "religious",
    "es",
    "Hoy, párrafo {paragraph} de {topic} — vea cómo concuerda con lo que ha entendido.",
    "Leamos juntos. Aplicando '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "¿Dónde coincide con su propia lectura?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_ES_ATH = _t(
    "bible_study",
    "atheist",
    "es",
    "Párrafo {paragraph} de {topic} — léalo como argumento, vea si se sostiene.",
    "Leeremos juntos; '{oratory_phrase}' nos ayudará a examinarlo — {oratory_brief}. El texto citado es {verse_display}.",
    "¿Dónde se sostiene o falla el argumento?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)

_BS_PT_DEF = _t(
    "bible_study",
    "default",
    "pt",
    "Hoje veremos o parágrafo {paragraph} de {topic}. Note o que ensina sobre {focus}.",
    "Vamos ler juntos. Depois aplicarei o ponto '{oratory_phrase}' — {oratory_brief}. O texto de apoio é {verse_display}.",
    "Pergunta: como isso afeta o que faremos nesta semana?",
    "Na próxima vez trabalharemos o parágrafo {next_paragraph}.",
    required_placeholders=(
        "verse_display",
        "oratory_phrase",
        "oratory_brief",
        "topic",
        "paragraph",
        "next_paragraph",
        "focus",
    ),
)
_BS_PT_NEW = _t(
    "bible_study",
    "new",
    "pt",
    "Veremos o parágrafo {paragraph} de {topic} — uma ideia útil para esta semana.",
    "Vamos ler juntos; aplicarei '{oratory_phrase}' para que o ponto fique claro — {oratory_brief}. Veja também {verse_display}.",
    "Que parte responde a uma pergunta real para você?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_PT_REL = _t(
    "bible_study",
    "religious",
    "pt",
    "Hoje, parágrafo {paragraph} de {topic} — veja como combina com o que entendeu.",
    "Vamos ler juntos. Aplicando '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "Onde combina com sua própria leitura?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)
_BS_PT_ATH = _t(
    "bible_study",
    "atheist",
    "pt",
    "Parágrafo {paragraph} de {topic} — leia como argumento, veja se se sustenta.",
    "Leremos juntos; '{oratory_phrase}' nos ajudará a examinar — {oratory_brief}. Texto citado: {verse_display}.",
    "Onde o argumento se sustenta ou falha?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"),
)


PART_TEMPLATES: tuple[PartTemplate, ...] = (
    _BR_EN_DEFAULT,
    _BR_EN_NEW,
    _BR_EN_REL,
    _BR_EN_ATH,
    _BR_ES_DEFAULT,
    _BR_ES_NEW,
    _BR_ES_REL,
    _BR_ES_ATH,
    _BR_PT_DEFAULT,
    _BR_PT_NEW,
    _BR_PT_REL,
    _BR_PT_ATH,
    _SC_EN_DEF,
    _SC_EN_NEW,
    _SC_EN_REL,
    _SC_EN_ATH,
    _SC_ES_DEF,
    _SC_ES_NEW,
    _SC_ES_REL,
    _SC_ES_ATH,
    _SC_PT_DEF,
    _SC_PT_NEW,
    _SC_PT_REL,
    _SC_PT_ATH,
    _RV_EN_DEF,
    _RV_EN_NEW,
    _RV_EN_REL,
    _RV_EN_ATH,
    _RV_ES_DEF,
    _RV_ES_NEW,
    _RV_ES_REL,
    _RV_ES_ATH,
    _RV_PT_DEF,
    _RV_PT_NEW,
    _RV_PT_REL,
    _RV_PT_ATH,
    _BS_EN_DEF,
    _BS_EN_NEW,
    _BS_EN_REL,
    _BS_EN_ATH,
    _BS_ES_DEF,
    _BS_ES_NEW,
    _BS_ES_REL,
    _BS_ES_ATH,
    _BS_PT_DEF,
    _BS_PT_NEW,
    _BS_PT_REL,
    _BS_PT_ATH,
)


_BY_SLOT: dict[tuple[str, str, str], PartTemplate] = {(t.kind, t.audience, t.language): t for t in PART_TEMPLATES}

_KNOWN_KINDS = {"bible_reading", "starting_conversation", "return_visit", "bible_study"}


def find_template(kind: str, audience: str, language: str) -> PartTemplate:
    """Look up a template with graceful fallback.

    Fallback order:
        (kind, audience, language)
        → (kind, 'default', language)
        → (kind, 'default', 'en')
    Raises ValueError if `kind` is unknown.
    """
    if kind not in _KNOWN_KINDS:
        raise ValueError(f"Unknown student-part kind: {kind!r}")
    for slot in (
        (kind, audience, language),
        (kind, "default", language),
        (kind, "default", "en"),
    ):
        if slot in _BY_SLOT:
            return _BY_SLOT[slot]
    raise ValueError(f"No template for {kind!r} after fallbacks — registry is broken")
