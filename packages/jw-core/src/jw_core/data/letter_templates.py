"""Plantillas de carta de predicación + resolver de familia temática.

Diseño:
  - 7 audiencias × 8 familias temáticas = hasta 56 combinaciones. No las
    rellenamos todas; usamos cadena de fallback
    (audience, family) → (audience, 'generic') → ('default', 'generic').
  - Prose escrita por el autor del paquete (paráfrasis neutra). No copia
    de wol.jw.org / jw.org.
  - `time_target_seconds` se ignora en cartas (0). `word_count_target`
    es 150 — meta indicativa, no enforced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AUDIENCES: tuple[str, ...] = (
    "default",
    "new",
    "religious",
    "atheist",
    "grieving",
    "young",
    "parents",
)

TOPIC_FAMILIES: tuple[str, ...] = (
    "family",
    "suffering",
    "hope",
    "science",
    "peace",
    "identity",
    "addictions",
    "generic",
)


@dataclass(frozen=True)
class LetterTemplate:
    """Scaffold con tres bloques de prosa + scripture + jw.org sugeridos."""

    opener: dict[str, str]
    bridge: dict[str, str]
    closing: dict[str, str]
    suggested_scripture: str
    suggested_jw_link: str
    time_target_seconds: int = 0
    word_count_target: int = 150


TOPIC_FAMILY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "es": {
        "family": [
            "familia",
            "matrimonio",
            "esposo",
            "esposa",
            "hijos",
            "padres",
            "madre",
            "padre",
            "hijo",
            "hija",
            "pareja",
        ],
        "suffering": ["sufrimiento", "dolor", "duelo", "muerte", "enfermedad", "perdí", "perdida", "luto", "tristeza"],
        "hope": ["esperanza", "futuro", "paraíso", "reino", "resurrección", "promesa"],
        "science": ["ciencia", "evolución", "creación", "universo", "diseño", "diseñador"],
        "peace": ["paz", "guerra", "ansiedad", "estrés", "tranquilidad", "preocupación", "miedo"],
        "identity": ["identidad", "propósito", "vida", "sentido", "valor"],
        "addictions": ["adicción", "vicio", "alcohol", "drogas", "tabaco", "fumar"],
    },
    "en": {
        "family": [
            "family",
            "marriage",
            "husband",
            "wife",
            "child",
            "children",
            "parent",
            "mother",
            "father",
            "spouse",
        ],
        "suffering": ["suffering", "pain", "grief", "death", "illness", "loss", "mourning", "sad", "sorrow"],
        "hope": ["hope", "future", "paradise", "kingdom", "resurrection", "promise"],
        "science": ["science", "evolution", "creation", "universe", "design", "designer"],
        "peace": ["peace", "war", "anxiety", "stress", "calm", "worry", "fear"],
        "identity": ["identity", "purpose", "life", "meaning", "value"],
        "addictions": ["addiction", "habit", "alcohol", "drugs", "tobacco", "smoking"],
    },
    "pt": {
        "family": ["família", "casamento", "marido", "esposa", "filho", "filhos", "filha", "pai", "mãe", "parceiro"],
        "suffering": ["sofrimento", "dor", "luto", "morte", "doença", "perdi", "perda", "tristeza"],
        "hope": ["esperança", "futuro", "paraíso", "reino", "ressurreição", "promessa"],
        "science": ["ciência", "evolução", "criação", "universo", "design", "designer"],
        "peace": ["paz", "guerra", "ansiedade", "estresse", "calma", "preocupação", "medo"],
        "identity": ["identidade", "propósito", "vida", "sentido", "valor"],
        "addictions": ["dependência", "vício", "álcool", "drogas", "tabaco", "fumar"],
    },
}


def resolve_topic_family(text: str, language: str) -> str:
    """Devuelve la familia temática que mejor matchee `text`.

    Algoritmo: lower-case, split en palabras, contar matches por familia.
    Mayor recuento gana; empate → orden de declaración en TOPIC_FAMILIES.
    Sin matches → 'generic'.
    Lengua desconocida → 'en'.
    """

    lang = language.lower() if language else "en"
    if lang not in TOPIC_FAMILY_KEYWORDS:
        lang = "en"

    haystack = " " + (text or "").lower() + " "
    counts: dict[str, int] = {}
    for family, words in TOPIC_FAMILY_KEYWORDS[lang].items():
        n = 0
        for w in words:
            # \b-word boundary search; accept accents.
            if re.search(rf"(?<!\w){re.escape(w.lower())}(?!\w)", haystack):
                n += 1
        if n:
            counts[family] = n
    if not counts:
        return "generic"
    # Tie-break by declaration order in TOPIC_FAMILIES.
    return max(counts.keys(), key=lambda f: (counts[f], -TOPIC_FAMILIES.index(f)))


def _t(en: str, es: str, pt: str) -> dict[str, str]:
    return {"en": en, "es": es, "pt": pt}


# ── Plantillas base por audiencia (clave family='generic') ────────────────
#
# Cada plantilla genérica está completamente paraphraseada; no contiene
# texto bíblico ni párrafos de jw.org.

_DEFAULT_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — I'm writing to share a brief Bible-based thought I "
        "found meaningful, in case it's useful to you too.",
        es="Hola: Le escribo para compartir un breve pensamiento bíblico "
        "que me pareció valioso, por si le resulta de interés.",
        pt="Olá: Escrevo para compartilhar um breve pensamento bíblico que me pareceu valioso, caso lhe interesse.",
    ),
    bridge=_t(
        en="Many people today wonder where to find reliable guidance for "
        "everyday questions. The Bible offers practical, timeless answers.",
        es="Hoy en día muchas personas se preguntan dónde encontrar guía "
        "confiable para las preguntas de la vida diaria. La Biblia "
        "ofrece respuestas prácticas y atemporales.",
        pt="Muitas pessoas hoje se perguntam onde encontrar orientação "
        "confiável para as questões do dia a dia. A Bíblia oferece "
        "respostas práticas e atemporais.",
    ),
    closing=_t(
        en="If this thought caught your attention, you might enjoy exploring the linked article. Wishing you well.",
        es="Si este pensamiento le llamó la atención, podría disfrutar "
        "leyendo el artículo enlazado. Le deseo lo mejor.",
        pt="Se esse pensamento lhe chamou a atenção, você poderá gostar de ler o artigo no link. Desejo-lhe o melhor.",
    ),
    suggested_scripture="Psalm 37:11",
    suggested_jw_link="https://www.jw.org/",
    word_count_target=150,
)


_NEW_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — perhaps we haven't met. I want to share a short Bible thought with my neighbors.",
        es="Hola: Es posible que no nos conozcamos. Quería compartir un breve pensamiento bíblico con mis vecinos.",
        pt="Olá: É possível que ainda não nos conheçamos. Gostaria de "
        "compartilhar um breve pensamento bíblico com meus vizinhos.",
    ),
    bridge=_t(
        en="The Bible has shaped the lives of millions across centuries. "
        "Even a single verse can offer fresh perspective.",
        es="La Biblia ha moldeado la vida de millones a lo largo de los "
        "siglos. Incluso un solo versículo puede dar perspectiva nueva.",
        pt="A Bíblia tem moldado a vida de milhões ao longo dos séculos. "
        "Mesmo um único versículo pode dar uma nova perspectiva.",
    ),
    closing=_t(
        en="If you'd like to explore further, the linked page is a good starting point. Kind regards.",
        es="Si quisiera profundizar, la página enlazada es un buen punto de partida. Un saludo cordial.",
        pt="Se desejar aprofundar, a página no link é um bom ponto de partida. Atenciosamente.",
    ),
    suggested_scripture="Isaiah 48:17",
    suggested_jw_link="https://www.jw.org/",
)


_RELIGIOUS_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — as someone who values faith, you may appreciate a Bible-based reflection I'd like to share.",
        es="Hola: Como persona que valora la fe, quizá aprecie una reflexión bíblica que quiero compartir.",
        pt="Olá: Como alguém que valoriza a fé, talvez aprecie uma reflexão bíblica que gostaria de compartilhar.",
    ),
    bridge=_t(
        en="Often the same passage rewards a fresh, careful reading. The "
        "thought below highlights a detail that's easy to miss.",
        es="A menudo, un mismo pasaje recompensa una lectura cuidadosa. El "
        "pensamiento siguiente destaca un detalle fácil de pasar por alto.",
        pt="Muitas vezes, a mesma passagem recompensa uma leitura cuidadosa. "
        "O pensamento a seguir destaca um detalhe fácil de passar batido.",
    ),
    closing=_t(
        en="Whatever your tradition, I hope this brings encouragement. With respect.",
        es="Sea cual sea su tradición, espero que esto le sea de aliento. Con respeto.",
        pt="Seja qual for sua tradição, espero que isso traga ânimo. Com respeito.",
    ),
    suggested_scripture="John 17:3",
    suggested_jw_link="https://www.jw.org/",
)


_ATHEIST_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — I won't assume your views. I just wanted to share a "
        "well-stated thought that I think holds up to scrutiny.",
        es="Hola: No daré por sentadas sus creencias. Solo quería "
        "compartir un pensamiento bien planteado que, a mi juicio, "
        "resiste el análisis.",
        pt="Olá: Não vou assumir suas crenças. Só queria compartilhar um "
        "pensamento bem formulado que, na minha opinião, resiste à "
        "análise.",
    ),
    bridge=_t(
        en="Whether or not a Designer exists is a question worth thinking "
        "about carefully. The article linked discusses evidence and "
        "reasoning — you can judge for yourself.",
        es="Si existe o no un Diseñador es una pregunta que vale la pena "
        "considerar con cuidado. El artículo enlazado expone evidencia "
        "y razonamiento — usted decide.",
        pt="Se existe ou não um Designer é uma pergunta que vale a pena "
        "examinar com cuidado. O artigo no link expõe evidência e "
        "raciocínio — você decide.",
    ),
    closing=_t(
        en="Thanks for considering it. I don't expect a reply — just leaving the thought.",
        es="Gracias por considerarlo. No espero respuesta — solo dejo el pensamiento.",
        pt="Obrigado por considerar. Não espero resposta — apenas deixo o pensamento.",
    ),
    suggested_scripture="Romans 1:20",
    suggested_jw_link="https://www.jw.org/",
)


_GRIEVING_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — I learned that grief can quietly shape a life. I'm sending this thought with care.",
        es="Hola: He aprendido que el duelo y la pérdida moldean la vida "
        "en silencio. Le envío este pensamiento con cariño.",
        pt="Olá: Aprendi que o luto e a perda moldam a vida em silêncio. Envio este pensamento com carinho.",
    ),
    bridge=_t(
        en="The Bible doesn't dismiss grief; it speaks gently to it. The verse below has comforted many.",
        es="La Biblia no descarta el duelo: le habla con ternura. El "
        "versículo enlazado ha consolado a muchas personas.",
        pt="A Bíblia não despreza o luto: fala-lhe com ternura. O versículo abaixo já consolou muitas pessoas.",
    ),
    closing=_t(
        en="Take whatever pace feels right. With warm regards.",
        es="Vaya al ritmo que le parezca bien. Le envío un saludo cálido.",
        pt="Vá no ritmo que lhe parecer certo. Envio um abraço.",
    ),
    suggested_scripture="Revelation 21:4",
    suggested_jw_link="https://www.jw.org/",
)


_YOUNG_GENERIC = LetterTemplate(
    opener=_t(
        en="Hey — quick note. Found a Bible thought worth two minutes; passing it along.",
        es="Hola: Mensaje breve. Encontré un pensamiento bíblico que vale dos minutos; te lo paso.",
        pt="Oi: Mensagem rápida. Achei um pensamento bíblico que vale dois minutos; te encaminho.",
    ),
    bridge=_t(
        en="A lot of life questions hit you at once when you're young. "
        "The verse linked has practical ideas, no pressure.",
        es="A los jóvenes les llegan muchas preguntas a la vez. El "
        "versículo enlazado tiene ideas prácticas, sin presión.",
        pt="Quando se é jovem, muitas perguntas chegam de uma vez. O "
        "versículo no link tem ideias práticas, sem pressão.",
    ),
    closing=_t(
        en="Hope your week's good. Cheers.",
        es="Espero que tengas buena semana. Saludos.",
        pt="Boa semana. Abraço.",
    ),
    suggested_scripture="Ecclesiastes 12:1",
    suggested_jw_link="https://www.jw.org/",
)


_PARENTS_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — as a fellow parent (or carer), I wanted to share a "
        "short Bible-based thought that's helped my family.",
        es="Hola: Como persona con responsabilidades de crianza, quería "
        "compartir un breve pensamiento bíblico que nos ha ayudado en "
        "casa.",
        pt="Olá: Como pessoa com responsabilidades de criação, queria "
        "compartilhar um breve pensamento bíblico que tem ajudado "
        "em casa.",
    ),
    bridge=_t(
        en="Raising children today asks a lot. A timeless principle can be the calm anchor on a noisy day.",
        es="Criar hijos hoy exige mucho. Un principio atemporal puede ser el ancla en un día agitado.",
        pt="Criar filhos hoje exige muito. Um princípio atemporal pode ser a âncora num dia agitado.",
    ),
    closing=_t(
        en="Whatever your day looks like, hope this lands at a good time. Take care.",
        es="Sea como sea el día, espero que esto le llegue en buen momento. Cuídese.",
        pt="Seja como for o dia, espero que isso chegue em bom momento. Cuide-se.",
    ),
    suggested_scripture="Proverbs 22:6",
    suggested_jw_link="https://www.jw.org/",
)


# ── Variantes específicas (family != 'generic') ──────────────────────────

_GRIEVING_SUFFERING = LetterTemplate(
    opener=_t(
        en="Hello — losing someone we love changes everything. I'm writing with care, not pressure.",
        es="Hola: La pérdida de un ser querido y el duelo lo cambian todo. Le escribo con cariño y sin presión.",
        pt="Olá: A perda de alguém que amamos e o luto mudam tudo. Escrevo com carinho e sem pressão.",
    ),
    bridge=_t(
        en="Many find that one short Bible promise is a doorway through "
        "the heaviest days. The verse linked is that doorway for many.",
        es="Muchas personas descubren que una breve promesa bíblica es "
        "una puerta en los días más pesados. El versículo enlazado "
        "es esa puerta para muchos.",
        pt="Muitas pessoas descobrem que uma breve promessa bíblica é "
        "uma porta nos dias mais pesados. O versículo no link é essa "
        "porta para muitos.",
    ),
    closing=_t(
        en="No reply expected. Just leaving hope in the mail.",
        es="No espero respuesta. Solo dejo esperanza en el correo.",
        pt="Sem esperar resposta. Só deixo esperança no correio.",
    ),
    suggested_scripture="Revelation 21:4",
    suggested_jw_link="https://www.jw.org/finder?wtlocale=E&docid=502200080",
)


_ATHEIST_SCIENCE = LetterTemplate(
    opener=_t(
        en="Hello — quick thought from an evidence angle. No assumptions about your beliefs.",
        es="Hola: Un breve pensamiento desde el ángulo de la evidencia. Sin presuponer sus creencias.",
        pt="Olá: Um pensamento rápido desde a ótica da evidência. Sem supor suas crenças.",
    ),
    bridge=_t(
        en="The fine-tuning of physical constants — and the elegance of "
        "biological systems — is the kind of pattern Romans 1:20 "
        "describes. Worth examining the data without prior commitment.",
        es="El ajuste fino de las constantes físicas — y la elegancia de "
        "los sistemas biológicos — es el tipo de patrón que describe "
        "Romanos 1:20. Vale la pena examinar los datos sin compromiso.",
        pt="O ajuste fino das constantes físicas — e a elegância dos "
        "sistemas biológicos — é o tipo de padrão descrito em Romanos "
        "1:20. Vale a pena examinar os dados sem compromisso.",
    ),
    closing=_t(
        en="Up to you what to make of it. Thanks for reading.",
        es="Usted decide qué hacer con esto. Gracias por leer.",
        pt="Cabe a você decidir. Obrigado por ler.",
    ),
    suggested_scripture="Romans 1:20",
    suggested_jw_link="https://www.jw.org/",
)


_PARENTS_FAMILY = LetterTemplate(
    opener=_t(
        en="Hello — as a fellow parent, I'm sharing a short Bible thought about raising kids in today's world.",
        es="Hola: Como persona con responsabilidades de crianza, le "
        "comparto un breve pensamiento bíblico sobre criar hijos hoy.",
        pt="Olá: Como pessoa que cria filhos, compartilho um breve pensamento bíblico sobre criação hoje.",
    ),
    bridge=_t(
        en="The Bible's family principles are practical: communication, "
        "consistency, and patient love. The linked article gathers "
        "real-life examples.",
        es="Los principios bíblicos sobre la familia son prácticos: "
        "comunicación, coherencia y amor paciente. El artículo "
        "enlazado reúne ejemplos reales.",
        pt="Os princípios bíblicos sobre a família são práticos: "
        "comunicação, coerência e amor paciente. O artigo no link "
        "reúne exemplos reais.",
    ),
    closing=_t(
        en="Wishing your home well.",
        es="Le deseo lo mejor para su hogar.",
        pt="Desejo o melhor para o seu lar.",
    ),
    suggested_scripture="Ephesians 6:4",
    suggested_jw_link="https://www.jw.org/finder?wtlocale=E&docid=502200126",
)


TEMPLATES: dict[tuple[str, str], LetterTemplate] = {
    # default
    ("default", "generic"): _DEFAULT_GENERIC,
    # new
    ("new", "generic"): _NEW_GENERIC,
    # religious
    ("religious", "generic"): _RELIGIOUS_GENERIC,
    # atheist
    ("atheist", "generic"): _ATHEIST_GENERIC,
    ("atheist", "science"): _ATHEIST_SCIENCE,
    # grieving
    ("grieving", "generic"): _GRIEVING_GENERIC,
    ("grieving", "suffering"): _GRIEVING_SUFFERING,
    # young
    ("young", "generic"): _YOUNG_GENERIC,
    # parents
    ("parents", "generic"): _PARENTS_GENERIC,
    ("parents", "family"): _PARENTS_FAMILY,
}


def get_template(audience: str, topic_family: str) -> LetterTemplate:
    """Lookup con fallback en cadena.

    1. (audience, topic_family)
    2. (audience, 'generic')
    3. ('default', 'generic')
    """

    aud = audience if audience in AUDIENCES else "default"
    fam = topic_family if topic_family in TOPIC_FAMILIES else "generic"
    if (aud, fam) in TEMPLATES:
        return TEMPLATES[(aud, fam)]
    if (aud, "generic") in TEMPLATES:
        return TEMPLATES[(aud, "generic")]
    return TEMPLATES[("default", "generic")]


def list_audiences() -> list[str]:
    """Lista ordenada de audiencias soportadas (default primero)."""

    return list(AUDIENCES)


def list_topic_families() -> list[str]:
    """Lista ordenada de familias temáticas soportadas."""

    return list(TOPIC_FAMILIES)
