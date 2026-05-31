"""Registry of the ~50 oratory points from the JW publication
'Improve in the Ministry / Mejore su predicación' (th).

This module stores ONLY:
  - The canonical point number (1-50, the order printed in the book).
  - A short paraphrase of the title (`key_phrase_*`, ≤120 chars).
  - A brief paraphrase of the counsel (`brief_*`, ≤300 chars).
  - The category (preparation/delivery/content).
  - Which student-assignment kinds the point naturally applies to.

It does NOT store the verbatim text of the book. Tests in
test_oratory_points.py enforce length limits and (optionally) a blacklist
of literal phrases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

Category = Literal["preparation", "delivery", "content"]
StudentKind = Literal[
    "bible_reading",
    "starting_conversation",
    "return_visit",
    "bible_study",
]

ALL_KINDS: tuple[StudentKind, ...] = (
    "bible_reading",
    "starting_conversation",
    "return_visit",
    "bible_study",
)


@dataclass(frozen=True)
class OratoryPoint:
    """One paraphrased entry from the 'th' improvement booklet."""

    number: int
    key_phrase_en: str
    key_phrase_es: str
    key_phrase_pt: str
    brief_en: str
    brief_es: str
    brief_pt: str
    category: Category
    applies_to: tuple[StudentKind, ...]


def _p(
    number: int,
    *,
    en: tuple[str, str],
    es: tuple[str, str],
    pt: tuple[str, str],
    category: Category,
    applies_to: tuple[StudentKind, ...] = ALL_KINDS,
) -> OratoryPoint:
    return OratoryPoint(
        number=number,
        key_phrase_en=en[0],
        brief_en=en[1],
        key_phrase_es=es[0],
        brief_es=es[1],
        key_phrase_pt=pt[0],
        brief_pt=pt[1],
        category=category,
        applies_to=applies_to,
    )


ORATORY_POINTS: tuple[OratoryPoint, ...] = (
    _p(
        1,
        en=("Choice of words",
            "Use words your audience understands; avoid jargon and undefined terms."),
        es=("Elección de palabras",
            "Use palabras que su audiencia entienda; evite jerga y términos sin definir."),
        pt=("Escolha das palavras",
            "Use palavras que sua audiência entenda; evite jargão e termos não definidos."),
        category="content",
    ),
    _p(
        2,
        en=("Pronunciation",
            "Pronounce each word clearly so listeners need not strain to follow."),
        es=("Pronunciación",
            "Pronuncie cada palabra con claridad para que los oyentes no se esfuercen."),
        pt=("Pronúncia",
            "Pronuncie cada palavra claramente para que ouvintes não se esforcem."),
        category="delivery",
        applies_to=("bible_reading", "return_visit", "bible_study"),
    ),
    _p(
        3,
        en=("Fluency",
            "Avoid hesitations and filler words; speak in complete thought units."),
        es=("Fluidez",
            "Evite vacilaciones y muletillas; hable en unidades de pensamiento completas."),
        pt=("Fluência",
            "Evite hesitações e palavras de preenchimento; fale em unidades completas."),
        category="delivery",
    ),
    _p(
        4,
        en=("Pausing",
            "Pause before and after key thoughts to let them sink in."),
        es=("Pausas",
            "Haga pausas antes y después de las ideas clave para que se asienten."),
        pt=("Pausas",
            "Faça pausas antes e depois das ideias-chave para que sejam absorvidas."),
        category="delivery",
    ),
    _p(
        5,
        en=("Sense stress",
            "Stress the words that carry the main thought of the sentence."),
        es=("Énfasis correcto",
            "Acentúe las palabras que llevan la idea principal de la oración."),
        pt=("Ênfase correta",
            "Acentue as palavras que carregam a ideia principal da frase."),
        category="delivery",
        applies_to=("bible_reading", "return_visit", "bible_study"),
    ),
    _p(
        6,
        en=("Modulation",
            "Vary pitch, pace, and volume to keep the audience engaged."),
        es=("Modulación",
            "Varíe el tono, el ritmo y el volumen para mantener la atención."),
        pt=("Modulação",
            "Varie tom, ritmo e volume para manter o interesse."),
        category="delivery",
    ),
    _p(
        7,
        en=("Enthusiasm",
            "Speak with warmth and conviction; show you believe what you say."),
        es=("Entusiasmo",
            "Hable con calidez y convicción; demuestre que cree lo que dice."),
        pt=("Entusiasmo",
            "Fale com calor e convicção; mostre que acredita no que diz."),
        category="delivery",
    ),
    _p(
        8,
        en=("Feeling",
            "Reflect the emotion suited to the content — joy, urgency, comfort."),
        es=("Sentimiento",
            "Refleje la emoción adecuada al contenido: gozo, urgencia, consuelo."),
        pt=("Sentimento",
            "Reflita a emoção adequada ao conteúdo — alegria, urgência, conforto."),
        category="delivery",
    ),
    _p(9, en=("Gestures", "Use natural gestures that match the words."),
       es=("Gestos", "Use gestos naturales que acompañen las palabras."),
       pt=("Gestos", "Use gestos naturais que acompanhem as palavras."),
       category="delivery"),
    _p(10, en=("Eye contact", "Look at individuals, not over their heads."),
       es=("Contacto visual", "Mire a las personas, no por encima de su cabeza."),
       pt=("Contato visual", "Olhe para as pessoas, não acima da cabeça delas."),
       category="delivery"),
    _p(11, en=("Posture", "Stand or sit upright; project openness and confidence."),
       es=("Postura", "Adopte una postura erguida; proyecte apertura y confianza."),
       pt=("Postura", "Adote postura ereta; transmita abertura e confiança."),
       category="delivery"),
    _p(12, en=("Appropriate appearance", "Dress in a way that does not distract from your message."),
       es=("Apariencia apropiada", "Vístase de modo que no distraiga del mensaje."),
       pt=("Aparência apropriada", "Vista-se de modo que não distraia da mensagem."),
       category="preparation"),
    _p(13, en=("Opening words", "Catch interest in the first sentences; raise a question or need."),
       es=("Palabras iniciales", "Capte interés en las primeras frases; plantee una pregunta o necesidad."),
       pt=("Palavras iniciais", "Capte interesse nas primeiras frases; levante questão ou necessidade."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(14, en=("Concluding words", "End by recapping the main point and inviting a next step."),
       es=("Palabras finales", "Termine resumiendo la idea principal e invitando a un siguiente paso."),
       pt=("Palavras finais", "Termine resumindo a ideia principal e convidando para próximo passo."),
       category="content"),
    _p(15, en=("Logical development", "Order points so each one prepares the next."),
       es=("Desarrollo lógico", "Ordene los puntos de modo que cada uno prepare el siguiente."),
       pt=("Desenvolvimento lógico", "Ordene os pontos para que cada um prepare o próximo."),
       category="content"),
    _p(16, en=("Main points stand out", "Make sure the audience can identify the few main points."),
       es=("Puntos principales bien definidos", "Asegúrese de que la audiencia identifique los pocos puntos principales."),
       pt=("Pontos principais bem definidos", "Garanta que a audiência identifique os poucos pontos principais."),
       category="content"),
    _p(17, en=("Repetition for emphasis", "Restate key thoughts in slightly different words."),
       es=("Repetición para enfatizar", "Reformule ideas clave con palabras ligeramente distintas."),
       pt=("Repetição para enfatizar", "Reformule ideias-chave com palavras ligeiramente diferentes."),
       category="content"),
    _p(18, en=("Effective questions", "Use questions that invite reflection, not just yes/no answers."),
       es=("Preguntas eficaces", "Use preguntas que inviten a reflexionar, no solo sí/no."),
       pt=("Perguntas eficazes", "Use perguntas que convidem à reflexão, não apenas sim/não."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(19, en=("Illustrations that teach", "Pick illustrations the audience can relate to."),
       es=("Ilustraciones que enseñan", "Use ilustraciones con las que la audiencia se identifique."),
       pt=("Ilustrações que ensinam", "Use ilustrações com as quais a audiência se identifique."),
       category="content"),
    _p(20, en=("Practical value", "Show how the material helps daily life."),
       es=("Valor práctico", "Muestre cómo el material ayuda en la vida diaria."),
       pt=("Valor prático", "Mostre como o material ajuda no dia a dia."),
       category="content"),
    _p(21, en=("Convincing argument", "Build a reasoned case, not bare assertion."),
       es=("Argumentación convincente", "Construya un razonamiento, no afirmaciones sueltas."),
       pt=("Argumentação convincente", "Construa um raciocínio, não afirmações soltas."),
       category="content"),
    _p(22, en=("Accurate information", "Cite facts and scriptures correctly; verify before speaking."),
       es=("Información exacta", "Cite hechos y textos correctamente; verifique antes de hablar."),
       pt=("Informação precisa", "Cite fatos e textos corretamente; verifique antes de falar."),
       category="preparation"),
    _p(23, en=("Use of the Bible", "Make Scripture the centerpiece, not a footnote."),
       es=("Uso de la Biblia", "Haga del texto bíblico el centro, no un apéndice."),
       pt=("Uso da Bíblia", "Faça do texto bíblico o centro, não um apêndice."),
       category="content"),
    _p(24, en=("Introducing scriptures", "Set up each verse so the listener knows why it matters."),
       es=("Cómo presentar los textos", "Presente cada versículo de modo que se vea por qué importa."),
       pt=("Como introduzir textos", "Apresente cada versículo para que se veja por que importa."),
       category="content"),
    _p(25, en=("Reading scriptures with feeling", "Read the verse so its emotion comes through."),
       es=("Leer con sentimiento", "Lea el versículo de modo que se perciba su emoción."),
       pt=("Ler com sentimento", "Leia o versículo de modo que se perceba sua emoção."),
       category="delivery",
       applies_to=("bible_reading", "return_visit", "bible_study")),
    _p(26, en=("Applying the scripture", "Connect the verse to the listener's situation."),
       es=("Aplicar el texto", "Conecte el versículo con la situación del oyente."),
       pt=("Aplicar o texto", "Conecte o versículo à situação do ouvinte."),
       category="content"),
    _p(27, en=("Reasoning with audience", "Engage in a dialogue, not a monologue."),
       es=("Razonar con la audiencia", "Entable un diálogo, no un monólogo."),
       pt=("Raciocinar com a audiência", "Estabeleça diálogo, não monólogo."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(28, en=("Tact", "Express truth without abrasiveness or condescension."),
       es=("Tacto", "Exprese la verdad sin aspereza ni condescendencia."),
       pt=("Tato", "Expresse a verdade sem aspereza ou condescendência."),
       category="content"),
    _p(29, en=("Empathy", "Acknowledge feelings before correcting ideas."),
       es=("Empatía", "Reconozca los sentimientos antes de corregir ideas."),
       pt=("Empatia", "Reconheça sentimentos antes de corrigir ideias."),
       category="content"),
    _p(30, en=("Sincere interest", "Listen actively; respond to what the person actually said."),
       es=("Interés sincero", "Escuche activamente; responda a lo que la persona dijo."),
       pt=("Interesse sincero", "Escute ativamente; responda ao que a pessoa disse."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(31, en=("Common ground", "Find a point of agreement before introducing differences."),
       es=("Puntos en común", "Encuentre acuerdo antes de presentar diferencias."),
       pt=("Pontos em comum", "Encontre concordância antes de apresentar diferenças."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(32, en=("Stirring motivation", "Help the listener want to act on what was discussed."),
       es=("Motivación que mueve", "Ayude al oyente a querer actuar sobre lo dicho."),
       pt=("Motivação que move", "Ajude o ouvinte a querer agir sobre o dito."),
       category="content"),
    _p(33, en=("Adapting to audience", "Adjust depth and vocabulary to your listener."),
       es=("Adaptarse a la audiencia", "Ajuste profundidad y vocabulario al oyente."),
       pt=("Adaptar-se à audiência", "Ajuste profundidade e vocabulário ao ouvinte."),
       category="content"),
    _p(34, en=("Effective transitions", "Move smoothly from one point to the next."),
       es=("Transiciones eficaces", "Mueva el tema fluidamente de un punto al siguiente."),
       pt=("Transições eficazes", "Mova o tema fluidamente de um ponto a outro."),
       category="content"),
    _p(35, en=("Direct address", "Speak TO the audience, not ABOUT a topic."),
       es=("Dirigirse al oyente", "Hable AL oyente, no SOBRE un tema."),
       pt=("Dirigir-se ao ouvinte", "Fale AO ouvinte, não SOBRE um tema."),
       category="content"),
    _p(36, en=("Genuine warmth", "Smile naturally; let your concern be visible."),
       es=("Calidez auténtica", "Sonría naturalmente; deje ver su interés."),
       pt=("Calor genuíno", "Sorria naturalmente; deixe ver seu interesse."),
       category="delivery"),
    _p(37, en=("Respect for views", "Acknowledge the value the listener sees in their position."),
       es=("Respeto por las creencias", "Reconozca el valor que el oyente ve en su postura."),
       pt=("Respeito pelas crenças", "Reconheça o valor que o ouvinte vê na sua posição."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(38, en=("Avoiding contention", "Defuse, don't escalate, when disagreement arises."),
       es=("Evitar contiendas", "Desactive, no escale, cuando surja desacuerdo."),
       pt=("Evitar contendas", "Desative, não escale, quando surgir desacordo."),
       category="content",
       applies_to=("starting_conversation", "return_visit")),
    _p(39, en=("Constructive feedback", "Praise specific strengths; tie suggestions to one point."),
       es=("Crítica constructiva", "Elogie fortalezas concretas; ate sugerencias a un punto."),
       pt=("Crítica construtiva", "Elogie fortalezas concretas; ligue sugestões a um ponto."),
       category="preparation"),
    _p(40, en=("Personal preparation", "Allot enough study time; rehearse aloud at least once."),
       es=("Preparación personal", "Dedique tiempo suficiente; ensaye en voz alta al menos una vez."),
       pt=("Preparação pessoal", "Dedique tempo suficiente; ensaie em voz alta pelo menos uma vez."),
       category="preparation"),
    _p(41, en=("Goal of the part", "Be clear in advance what you want the listener to take away."),
       es=("Meta de la parte", "Tenga claro de antemano qué quiere que el oyente se lleve."),
       pt=("Meta da parte", "Tenha claro de antemão o que quer que o ouvinte leve."),
       category="preparation"),
    _p(42, en=("Use of notes", "Use brief, glanceable notes — not a manuscript."),
       es=("Uso de notas", "Use notas breves a las que pueda mirar de reojo, no un texto."),
       pt=("Uso de notas", "Use anotações breves de relance, não um texto."),
       category="preparation",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(43, en=("Visual aids", "Choose visuals (videos, brochures) that reinforce the point."),
       es=("Apoyos visuales", "Elija recursos visuales (videos, folletos) que refuercen el punto."),
       pt=("Apoios visuais", "Escolha recursos visuais (vídeos, folhetos) que reforcem o ponto."),
       category="preparation",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(44, en=("Confidence in the message", "Speak as one who knows the message is true."),
       es=("Confianza en el mensaje", "Hable como quien sabe que el mensaje es verdad."),
       pt=("Confiança na mensagem", "Fale como quem sabe que a mensagem é verdade."),
       category="delivery"),
    _p(45, en=("Spiritual heart", "Let your love for Jehovah show; pray about your preparation."),
       es=("Corazón espiritual", "Deje ver su amor por Jehová; ore por su preparación."),
       pt=("Coração espiritual", "Deixe ver seu amor por Jeová; ore pela sua preparação."),
       category="preparation"),
    _p(46, en=("Personal observations", "Add brief, modest personal experience when it illustrates."),
       es=("Observaciones personales", "Añada experiencia personal breve y modesta cuando ilustre."),
       pt=("Observações pessoais", "Adicione experiência pessoal breve e modesta quando ilustrar."),
       category="content",
       applies_to=("starting_conversation", "return_visit", "bible_study")),
    _p(47, en=("Naturalness in delivery", "Sound like yourself, not a reciter."),
       es=("Naturalidad", "Suene como usted mismo, no como un recitador."),
       pt=("Naturalidade", "Soe como você mesmo, não como um recitador."),
       category="delivery"),
    _p(48, en=("Conviction", "Phrase statements so the listener senses certainty, not opinion."),
       es=("Convicción", "Exprese ideas de modo que se perciba certeza, no opinión."),
       pt=("Convicção", "Expresse ideias de modo que se perceba certeza, não opinião."),
       category="delivery"),
    _p(49, en=("Building faith in God's word", "Direct attention back to Scripture as the source."),
       es=("Edificar fe en la Palabra", "Lleve la atención de vuelta a las Escrituras como fuente."),
       pt=("Edificar fé na Palavra", "Leve a atenção de volta às Escrituras como fonte."),
       category="content"),
    _p(50, en=("Building up the listener", "End by leaving the listener encouraged, not lectured."),
       es=("Edificar al oyente", "Termine dejando al oyente animado, no aleccionado."),
       pt=("Edificar o ouvinte", "Termine deixando o ouvinte animado, não repreendido."),
       category="content"),
)


_BY_NUMBER: dict[int, OratoryPoint] = {p.number: p for p in ORATORY_POINTS}


def get_point(number: int) -> OratoryPoint:
    """Look up a point by its canonical number."""
    if number not in _BY_NUMBER:
        raise ValueError(f"Unknown oratory point number: {number} (valid: 1..50)")
    return _BY_NUMBER[number]


def points_applicable_to(kind: str) -> list[OratoryPoint]:
    """Filter points whose `applies_to` includes `kind`. Unknown kind → []."""
    if kind not in ALL_KINDS:
        return []
    return [p for p in ORATORY_POINTS if kind in p.applies_to]


_MONTH_TO_POINT_START: dict[int, int] = {
    1: 1, 2: 5, 3: 9, 4: 13, 5: 17, 6: 21,
    7: 25, 8: 29, 9: 33, 10: 37, 11: 41, 12: 45,
}


def point_of_the_month(d: date, *, language: str = "en") -> OratoryPoint:
    """Return the canonical 'first point of the month' for date `d`.

    The mapping is static (see `_MONTH_TO_POINT_START`). If a congregation
    runs a different cycle, the caller should pass `oratory_point=N` to the
    student-part agent instead of relying on this helper.
    """
    return get_point(_MONTH_TO_POINT_START[d.month])


def key_phrase(point: OratoryPoint, language: str) -> str:
    """Return the localized key phrase. Unknown language → en."""
    return {
        "en": point.key_phrase_en,
        "es": point.key_phrase_es,
        "pt": point.key_phrase_pt,
    }.get(language, point.key_phrase_en)


def brief(point: OratoryPoint, language: str) -> str:
    """Return the localized brief. Unknown language → en."""
    return {
        "en": point.brief_en,
        "es": point.brief_es,
        "pt": point.brief_pt,
    }.get(language, point.brief_en)
