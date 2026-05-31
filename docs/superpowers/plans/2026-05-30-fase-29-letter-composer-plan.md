# Fase 29 — `letter_composer` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `letter_composer`, a stateless agent that produces structured scaffolds for letter / phone / cart witnessing. Three template modules in `jw-core`, one orchestrator in `jw-agents`, one CLI command, one MCP tool, three eval golden cases, one user guide.

**Architecture:** Plantilla `(audience, topic_family)` → fallback en cadena → `LetterTemplate` → cuatro `Finding`s ordenados (`opener · bridge · scripture · closing`). Sin red obligatoria. Sin PII persistente. Copyright-safe (prose paráfrasis propia).

**Tech Stack:** Python 3.13 · dataclasses (templates) · pytest · Typer (CLI) · Rich (output) · FastMCP (tool) · Hatchling.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-29-letter-composer-design.md`](../specs/2026-05-30-fase-29-letter-composer-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/letter_templates.py`
- `packages/jw-core/src/jw_core/data/phone_templates.py`
- `packages/jw-core/src/jw_core/data/cart_templates.py`
- `packages/jw-core/tests/test_letter_templates.py`
- `packages/jw-agents/src/jw_agents/letter_composer.py`
- `packages/jw-agents/tests/test_letter_composer.py`
- `packages/jw-cli/src/jw_cli/commands/letter.py`
- `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_letter_grieving_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_phone_default_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_cart_parents_en.yaml`
- `docs/guias/compositor-de-predicacion.md`

Modifies:
- `packages/jw-agents/src/jw_agents/__init__.py` — re-export `letter_composer`.
- `packages/jw-cli/src/jw_cli/main.py` — register `letter` command.
- `packages/jw-mcp/src/jw_mcp/server.py` — register `compose_witnessing` tool.
- `docs/VISION_AUDIT.md` — add Fase 29 row.
- `docs/ROADMAP.md` — add Fase 29 section.
- `docs/README.md` (optional) — link to new guide.

---

### Task 1: Add `LetterTemplate` dataclass + topic-family resolver (`letter_templates.py`)

**Files:**
- Create: `packages/jw-core/src/jw_core/data/letter_templates.py`
- Create: `packages/jw-core/tests/test_letter_templates.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_letter_templates.py
"""Tests for letter / phone / cart templates and topic-family resolver."""

from __future__ import annotations

import pytest

from jw_core.data.letter_templates import (
    AUDIENCES,
    TOPIC_FAMILIES,
    LetterTemplate,
    get_template,
    list_audiences,
    list_topic_families,
    resolve_topic_family,
)


def test_letter_template_dataclass_minimal() -> None:
    t = LetterTemplate(
        opener={"en": "Hi.", "es": "Hola.", "pt": "Olá."},
        bridge={"en": "Bridge.", "es": "Puente.", "pt": "Ponte."},
        closing={"en": "Bye.", "es": "Adiós.", "pt": "Tchau."},
        suggested_scripture="John 3:16",
        suggested_jw_link="https://www.jw.org/",
    )
    assert t.opener["es"] == "Hola."
    assert t.time_target_seconds == 0
    assert t.word_count_target == 150


def test_resolve_topic_family_keyword_match_es() -> None:
    assert resolve_topic_family("perdí a mi esposo", "es") == "family"
    assert resolve_topic_family("tengo mucha ansiedad", "es") == "peace"
    assert resolve_topic_family("¿existe esperanza?", "es") == "hope"
    assert resolve_topic_family("vicio del alcohol", "es") == "addictions"


def test_resolve_topic_family_keyword_match_en() -> None:
    assert resolve_topic_family("my marriage is failing", "en") == "family"
    assert resolve_topic_family("design in the universe", "en") == "science"


def test_resolve_topic_family_fallback_to_generic() -> None:
    assert resolve_topic_family("totally unrelated text", "es") == "generic"
    assert resolve_topic_family("", "es") == "generic"


def test_resolve_topic_family_unknown_language_falls_back_to_en() -> None:
    # Unknown lang code → use English keyword map.
    assert resolve_topic_family("hope for the future", "xx") == "hope"


def test_resolve_topic_family_case_insensitive() -> None:
    assert resolve_topic_family("ESPERANZA Y PAZ", "es") in {"hope", "peace"}


def test_get_template_returns_specific_when_present() -> None:
    t = get_template("grieving", "suffering")
    assert isinstance(t, LetterTemplate)
    # Opener must mention the audience-specific tone keyword:
    assert "duelo" in t.opener["es"].lower() or "pérdida" in t.opener["es"].lower()


def test_get_template_falls_back_to_audience_generic() -> None:
    # An audience exists but no specific family → audience generic.
    t = get_template("young", "addictions")
    assert isinstance(t, LetterTemplate)


def test_get_template_falls_back_to_default_generic() -> None:
    # Bad audience → default generic.
    t = get_template("nonexistent_audience", "nonexistent_family")
    assert isinstance(t, LetterTemplate)


def test_every_audience_has_a_generic_template() -> None:
    for aud in AUDIENCES:
        t = get_template(aud, "generic")
        assert isinstance(t, LetterTemplate), aud
        for lang in ("en", "es", "pt"):
            assert t.opener.get(lang), f"{aud} missing opener[{lang}]"
            assert t.bridge.get(lang), f"{aud} missing bridge[{lang}]"
            assert t.closing.get(lang), f"{aud} missing closing[{lang}]"


def test_list_audiences_includes_default_first() -> None:
    auds = list_audiences()
    assert auds[0] == "default"
    assert set(auds) == set(AUDIENCES)


def test_list_topic_families_covers_8_documented() -> None:
    fams = set(list_topic_families())
    assert {
        "family", "suffering", "hope", "science",
        "peace", "identity", "addictions", "generic",
    } <= fams
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py -v`
Expected: ImportError — `jw_core.data.letter_templates` not found.

- [ ] **Step 3: Implement letter templates**

```python
# packages/jw-core/src/jw_core/data/letter_templates.py
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
from dataclasses import dataclass, field

AUDIENCES: tuple[str, ...] = (
    "default", "new", "religious", "atheist",
    "grieving", "young", "parents",
)

TOPIC_FAMILIES: tuple[str, ...] = (
    "family", "suffering", "hope", "science",
    "peace", "identity", "addictions", "generic",
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
        "family":     ["familia", "matrimonio", "esposo", "esposa", "hijos", "padres",
                       "madre", "padre", "hijo", "hija", "pareja"],
        "suffering":  ["sufrimiento", "dolor", "duelo", "muerte", "enfermedad",
                       "perdí", "perdida", "luto", "tristeza"],
        "hope":       ["esperanza", "futuro", "paraíso", "reino", "resurrección",
                       "promesa"],
        "science":    ["ciencia", "evolución", "creación", "universo", "diseño",
                       "diseñador"],
        "peace":      ["paz", "guerra", "ansiedad", "estrés", "tranquilidad",
                       "preocupación", "miedo"],
        "identity":   ["identidad", "propósito", "vida", "sentido", "valor"],
        "addictions": ["adicción", "vicio", "alcohol", "drogas", "tabaco", "fumar"],
    },
    "en": {
        "family":     ["family", "marriage", "husband", "wife", "child", "children",
                       "parent", "mother", "father", "spouse"],
        "suffering":  ["suffering", "pain", "grief", "death", "illness", "loss",
                       "mourning", "sad", "sorrow"],
        "hope":       ["hope", "future", "paradise", "kingdom", "resurrection",
                       "promise"],
        "science":    ["science", "evolution", "creation", "universe", "design",
                       "designer"],
        "peace":      ["peace", "war", "anxiety", "stress", "calm", "worry", "fear"],
        "identity":   ["identity", "purpose", "life", "meaning", "value"],
        "addictions": ["addiction", "habit", "alcohol", "drugs", "tobacco",
                       "smoking"],
    },
    "pt": {
        "family":     ["família", "casamento", "marido", "esposa", "filho", "filhos",
                       "filha", "pai", "mãe", "parceiro"],
        "suffering":  ["sofrimento", "dor", "luto", "morte", "doença", "perdi",
                       "perda", "tristeza"],
        "hope":       ["esperança", "futuro", "paraíso", "reino", "ressurreição",
                       "promessa"],
        "science":    ["ciência", "evolução", "criação", "universo", "design",
                       "designer"],
        "peace":      ["paz", "guerra", "ansiedade", "estresse", "calma",
                       "preocupação", "medo"],
        "identity":   ["identidade", "propósito", "vida", "sentido", "valor"],
        "addictions": ["dependência", "vício", "álcool", "drogas", "tabaco",
                       "fumar"],
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
        pt="Olá: Escrevo para compartilhar um breve pensamento bíblico que "
           "me pareceu valioso, caso lhe interesse.",
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
        en="If this thought caught your attention, you might enjoy "
           "exploring the linked article. Wishing you well.",
        es="Si este pensamiento le llamó la atención, podría disfrutar "
           "leyendo el artículo enlazado. Le deseo lo mejor.",
        pt="Se esse pensamento lhe chamou a atenção, você poderá gostar "
           "de ler o artigo no link. Desejo-lhe o melhor.",
    ),
    suggested_scripture="Psalm 37:11",
    suggested_jw_link="https://www.jw.org/",
    word_count_target=150,
)


_NEW_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — perhaps we haven't met. I want to share a short Bible "
           "thought with my neighbors.",
        es="Hola: Es posible que no nos conozcamos. Quería compartir un "
           "breve pensamiento bíblico con mis vecinos.",
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
        en="If you'd like to explore further, the linked page is a good "
           "starting point. Kind regards.",
        es="Si quisiera profundizar, la página enlazada es un buen punto "
           "de partida. Un saludo cordial.",
        pt="Se desejar aprofundar, a página no link é um bom ponto de "
           "partida. Atenciosamente.",
    ),
    suggested_scripture="Isaiah 48:17",
    suggested_jw_link="https://www.jw.org/",
)


_RELIGIOUS_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — as someone who values faith, you may appreciate a "
           "Bible-based reflection I'd like to share.",
        es="Hola: Como persona que valora la fe, quizá aprecie una "
           "reflexión bíblica que quiero compartir.",
        pt="Olá: Como alguém que valoriza a fé, talvez aprecie uma "
           "reflexão bíblica que gostaria de compartilhar.",
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
        en="Whatever your tradition, I hope this brings encouragement. "
           "With respect.",
        es="Sea cual sea su tradición, espero que esto le sea de aliento. "
           "Con respeto.",
        pt="Seja qual for sua tradição, espero que isso traga ânimo. "
           "Com respeito.",
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
        en="Thanks for considering it. I don't expect a reply — just "
           "leaving the thought.",
        es="Gracias por considerarlo. No espero respuesta — solo dejo el "
           "pensamiento.",
        pt="Obrigado por considerar. Não espero resposta — apenas deixo o "
           "pensamento.",
    ),
    suggested_scripture="Romans 1:20",
    suggested_jw_link="https://www.jw.org/",
)


_GRIEVING_GENERIC = LetterTemplate(
    opener=_t(
        en="Hello — I learned that grief can quietly shape a life. I'm "
           "sending this thought with care.",
        es="Hola: He aprendido que el duelo y la pérdida moldean la vida "
           "en silencio. Le envío este pensamiento con cariño.",
        pt="Olá: Aprendi que o luto e a perda moldam a vida em silêncio. "
           "Envio este pensamento com carinho.",
    ),
    bridge=_t(
        en="The Bible doesn't dismiss grief; it speaks gently to it. The "
           "verse below has comforted many.",
        es="La Biblia no descarta el duelo: le habla con ternura. El "
           "versículo enlazado ha consolado a muchas personas.",
        pt="A Bíblia não despreza o luto: fala-lhe com ternura. O "
           "versículo abaixo já consolou muitas pessoas.",
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
        en="Hey — quick note. Found a Bible thought worth two minutes; "
           "passing it along.",
        es="Hola: Mensaje breve. Encontré un pensamiento bíblico que vale "
           "dos minutos; te lo paso.",
        pt="Oi: Mensagem rápida. Achei um pensamento bíblico que vale "
           "dois minutos; te encaminho.",
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
        en="Raising children today asks a lot. A timeless principle can "
           "be the calm anchor on a noisy day.",
        es="Criar hijos hoy exige mucho. Un principio atemporal puede "
           "ser el ancla en un día agitado.",
        pt="Criar filhos hoje exige muito. Um princípio atemporal pode "
           "ser a âncora num dia agitado.",
    ),
    closing=_t(
        en="Whatever your day looks like, hope this lands at a good time. "
           "Take care.",
        es="Sea como sea el día, espero que esto le llegue en buen "
           "momento. Cuídese.",
        pt="Seja como for o dia, espero que isso chegue em bom momento. "
           "Cuide-se.",
    ),
    suggested_scripture="Proverbs 22:6",
    suggested_jw_link="https://www.jw.org/",
)


# ── Variantes específicas (family != 'generic') ──────────────────────────

_GRIEVING_SUFFERING = LetterTemplate(
    opener=_t(
        en="Hello — losing someone we love changes everything. I'm "
           "writing with care, not pressure.",
        es="Hola: Perder a un ser querido lo cambia todo. Le escribo con "
           "cariño y sin presión.",
        pt="Olá: Perder alguém que amamos muda tudo. Escrevo com carinho "
           "e sem pressão.",
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
        en="Hello — quick thought from an evidence angle. No assumptions "
           "about your beliefs.",
        es="Hola: Un breve pensamiento desde el ángulo de la evidencia. "
           "Sin presuponer sus creencias.",
        pt="Olá: Um pensamento rápido desde a ótica da evidência. Sem "
           "supor suas crenças.",
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
        en="Hello — as a fellow parent, I'm sharing a short Bible thought "
           "about raising kids in today's world.",
        es="Hola: Como persona con responsabilidades de crianza, le "
           "comparto un breve pensamiento bíblico sobre criar hijos hoy.",
        pt="Olá: Como pessoa que cria filhos, compartilho um breve "
           "pensamento bíblico sobre criação hoje.",
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/letter_templates.py packages/jw-core/tests/test_letter_templates.py
git commit -m "feat(jw-core): letter templates + topic-family resolver (Fase 29)"
```

---

### Task 2: Add `phone_templates.py` reusing the model

**Files:**
- Create: `packages/jw-core/src/jw_core/data/phone_templates.py`
- Modify: `packages/jw-core/tests/test_letter_templates.py` — add tests for phone.

- [ ] **Step 1: Append failing tests**

Append to `packages/jw-core/tests/test_letter_templates.py`:

```python
from jw_core.data.phone_templates import (
    PHONE_TEMPLATES,
    get_phone_template,
)


def test_phone_template_has_time_target_75s() -> None:
    t = get_phone_template("default", "generic")
    assert t.time_target_seconds == 75
    assert t.word_count_target == 0


def test_phone_every_audience_has_generic() -> None:
    from jw_core.data.letter_templates import AUDIENCES

    for aud in AUDIENCES:
        t = get_phone_template(aud, "generic")
        for lang in ("en", "es", "pt"):
            assert t.opener.get(lang)
            assert t.bridge.get(lang)
            assert t.closing.get(lang)


def test_phone_fallback_chain() -> None:
    t = get_phone_template("nonexistent", "nonexistent")
    assert t is PHONE_TEMPLATES[("default", "generic")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py::test_phone_template_has_time_target_75s -v`
Expected: ImportError.

- [ ] **Step 3: Implement phone templates**

```python
# packages/jw-core/src/jw_core/data/phone_templates.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py -v`
Expected: all green (16 passed total).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/phone_templates.py packages/jw-core/tests/test_letter_templates.py
git commit -m "feat(jw-core): phone witnessing templates with 75s time target"
```

---

### Task 3: Add `cart_templates.py`

**Files:**
- Create: `packages/jw-core/src/jw_core/data/cart_templates.py`
- Modify: `packages/jw-core/tests/test_letter_templates.py` — add cart tests.

- [ ] **Step 1: Append failing tests**

```python
from jw_core.data.cart_templates import CART_TEMPLATES, get_cart_template


def test_cart_template_has_time_target_30s() -> None:
    t = get_cart_template("default", "generic")
    assert t.time_target_seconds == 30
    assert t.word_count_target == 0


def test_cart_every_audience_has_generic() -> None:
    from jw_core.data.letter_templates import AUDIENCES

    for aud in AUDIENCES:
        t = get_cart_template(aud, "generic")
        for lang in ("en", "es", "pt"):
            assert t.opener.get(lang)
            assert t.bridge.get(lang)
            assert t.closing.get(lang)


def test_cart_opener_is_a_question() -> None:
    # Cart witnessing opens with one short question.
    t = get_cart_template("default", "generic")
    assert "?" in t.opener["es"]
    assert "?" in t.opener["en"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py::test_cart_template_has_time_target_30s -v`
Expected: ImportError.

- [ ] **Step 3: Implement cart templates**

```python
# packages/jw-core/src/jw_core/data/cart_templates.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-core/tests/test_letter_templates.py -v`
Expected: all green (19 passed total).

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/cart_templates.py packages/jw-core/tests/test_letter_templates.py
git commit -m "feat(jw-core): cart witnessing templates with 30s time target"
```

---

### Task 4: Build the `letter_composer` agent (basic, sin Topic Index)

**Files:**
- Create: `packages/jw-agents/src/jw_agents/letter_composer.py`
- Create: `packages/jw-agents/tests/test_letter_composer.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_letter_composer.py
"""Unit tests for the letter_composer agent.

All tests are sync-friendly via `asyncio.run`; no network is required.
"""

from __future__ import annotations

import asyncio

import pytest

from jw_agents.letter_composer import letter_composer


def _run(**kwargs):
    return asyncio.run(letter_composer(**kwargs))


def test_compose_letter_returns_4_sections_in_order() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza para una madre en duelo",
        audience="grieving",
    )
    sections = [f.metadata.get("section") for f in result.findings]
    assert sections[:4] == ["opener", "bridge", "scripture", "closing"]


def test_compose_letter_metadata_contains_required_fields() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    md = result.metadata
    assert md["kind"] == "letter"
    assert md["audience"] == "default"
    assert md["language"] == "es"
    assert md["word_count_target"] == 150
    assert md["time_target_seconds"] == 0
    assert md["topic_family"] == "hope"


def test_compose_phone_has_time_target_75s() -> None:
    result = _run(
        kind="phone",
        language="es",
        topic_or_question="ansiedad",
        audience="default",
    )
    assert result.metadata["time_target_seconds"] == 75
    assert result.metadata["word_count_target"] == 0


def test_compose_cart_has_time_target_30s() -> None:
    result = _run(
        kind="cart",
        language="en",
        topic_or_question="family",
        audience="parents",
    )
    assert result.metadata["time_target_seconds"] == 30


def test_scripture_finding_carries_wol_url() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    scrip = next(f for f in result.findings if f.metadata.get("section") == "scripture")
    assert scrip.citation.url.startswith("https://wol.jw.org/")
    assert scrip.metadata["source"] == "verse_text"


def test_territory_hint_inserted_in_opener_only() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
        territory_hint="Lima, Perú",
    )
    opener = next(f for f in result.findings if f.metadata.get("section") == "opener")
    assert "Lima, Perú" in opener.summary
    bridge = next(f for f in result.findings if f.metadata.get("section") == "bridge")
    assert "Lima, Perú" not in bridge.summary


def test_jw_link_override_wins_over_template_default() -> None:
    custom = "https://www.jw.org/custom/path"
    result = _run(
        kind="letter",
        language="en",
        topic_or_question="hope",
        audience="default",
        jw_link=custom,
    )
    assert result.metadata["jw_link_suggested"] == custom
    closing = next(f for f in result.findings if f.metadata.get("section") == "closing")
    assert closing.citation.url == custom


def test_audience_fallback_to_default_when_unknown() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="no_such_audience",
    )
    # No exception; warning emitted; metadata captures effective audience.
    assert result.metadata["audience"] == "default"
    assert any("audience" in w.lower() for w in result.warnings)


def test_topic_family_fallback_to_generic_when_no_match() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="zzz totally unrelated zzz",
        audience="default",
    )
    assert result.metadata["topic_family"] == "generic"


def test_unknown_language_warns_and_uses_english() -> None:
    result = _run(
        kind="letter",
        language="xx",
        topic_or_question="hope",
        audience="default",
    )
    opener = next(f for f in result.findings if f.metadata.get("section") == "opener")
    # English fallback prose is present.
    assert "Hello" in opener.summary
    assert any("language" in w.lower() for w in result.warnings)


def test_every_finding_carries_a_citation_url() -> None:
    result = _run(
        kind="letter",
        language="es",
        topic_or_question="esperanza",
        audience="default",
    )
    for f in result.findings:
        assert f.citation.url, f"empty citation in section={f.metadata.get('section')!r}"


def test_invalid_kind_raises() -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            letter_composer(
                kind="email",  # type: ignore[arg-type]
                language="es",
                topic_or_question="x",
            )
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-agents/tests/test_letter_composer.py -v`
Expected: ImportError on `jw_agents.letter_composer`.

- [ ] **Step 3: Implement the composer**

```python
# packages/jw-agents/src/jw_agents/letter_composer.py
"""letter_composer — scaffolds for letter / phone / cart witnessing.

Stateless. No network unless an optional TopicIndexClient is injected.
Produces a 4-section `AgentResult` (`opener · bridge · scripture · closing`)
plus optional 5th `topic_anchor` when a TopicIndexClient is provided.

Copyright stance: the prose in `metadata.data.letter_templates` is original
(written by the author of this package). Bible text is never copied — only
the canonical wol.jw.org URL is emitted via `Citation.url`. The LLM client
that consumes the scaffold decides what verse text (if any) to surface.

Territory hint: cosmetic only. Inserted verbatim into the opener prose.
Never used to filter content. Not stored.
"""

from __future__ import annotations

from typing import Literal

from jw_core.clients.topic_index import TopicIndexClient
from jw_core.data.cart_templates import get_cart_template
from jw_core.data.letter_templates import (
    AUDIENCES,
    LetterTemplate,
    get_template as get_letter_template,
    resolve_topic_family,
)
from jw_core.data.phone_templates import get_phone_template
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding

Kind = Literal["letter", "phone", "cart"]
KINDS: tuple[Kind, ...] = ("letter", "phone", "cart")

_SUPPORTED_LANGS = {"en", "es", "pt"}

_SCAFFOLD_URL = "https://www.jw.org/"


def _pick_template(kind: Kind, audience: str, topic_family: str) -> LetterTemplate:
    if kind == "letter":
        return get_letter_template(audience, topic_family)
    if kind == "phone":
        return get_phone_template(audience, topic_family)
    if kind == "cart":
        return get_cart_template(audience, topic_family)
    raise ValueError(f"unknown kind: {kind!r}")


def _localize(block: dict[str, str], language: str) -> str:
    return block.get(language) or block.get("en") or next(iter(block.values()), "")


def _scripture_finding(ref_text: str, language: str) -> Finding:
    ref = parse_reference(ref_text)
    if ref is None:
        return Finding(
            summary=f"Suggested scripture: {ref_text}",
            excerpt="",  # never copy bible text — copyright safety
            citation=Citation(
                url=f"https://wol.jw.org/{language}/wol/h/r1/lp-{language[0]}",
                title=ref_text,
                kind="verse",
            ),
            metadata={"source": "verse_text", "section": "scripture"},
        )
    return Finding(
        summary=f"Suggested scripture: {ref.display()}",
        excerpt="",  # copyright safety
        citation=Citation(
            url=ref.wol_url(lang=language),
            title=ref.display(),
            kind="verse",
        ),
        metadata={
            "source": "verse_text",
            "section": "scripture",
            "reference": ref.display(),
        },
    )


async def letter_composer(
    kind: Kind,
    *,
    language: str = "es",
    topic_or_question: str,
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
    topic: TopicIndexClient | None = None,
) -> AgentResult:
    """Compose a witnessing scaffold for letter / phone / cart.

    Returns 4 `Finding`s in order: opener, bridge, scripture, closing.
    Optional 5th: topic_anchor (only when `topic` is provided).
    """

    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind!r}. Allowed: {KINDS}")

    result = AgentResult(
        query=topic_or_question,
        agent_name="letter_composer",
    )

    # Resolve language (fallback en).
    lang = language.lower() if language else "en"
    if lang not in _SUPPORTED_LANGS:
        result.warnings.append(
            f"Unsupported language {language!r}; using English fallback."
        )
        lang = "en"

    # Resolve audience (fallback default).
    if audience not in AUDIENCES:
        result.warnings.append(
            f"Unknown audience {audience!r}; using 'default'. "
            f"Available: {AUDIENCES}"
        )
        eff_audience = "default"
    else:
        eff_audience = audience

    # Resolve topic family from the free-form text.
    topic_family = resolve_topic_family(topic_or_question, lang)

    template = _pick_template(kind, eff_audience, topic_family)

    # Build the four mandatory sections.
    opener_text = _localize(template.opener, lang)
    if territory_hint:
        # Cosmetic: prepend territory hint into opener prose.
        opener_text = f"({territory_hint.strip()}) {opener_text}"

    bridge_text = _localize(template.bridge, lang)
    closing_text = _localize(template.closing, lang)

    effective_jw_link = jw_link or template.suggested_jw_link

    result.findings.append(
        Finding(
            summary=opener_text,
            excerpt=opener_text,
            citation=Citation(url=_SCAFFOLD_URL, title="opener", kind="scaffold"),
            metadata={"source": "letter_template", "section": "opener"},
        )
    )
    result.findings.append(
        Finding(
            summary=bridge_text,
            excerpt=bridge_text,
            citation=Citation(url=_SCAFFOLD_URL, title="bridge", kind="scaffold"),
            metadata={"source": "letter_template", "section": "bridge"},
        )
    )
    result.findings.append(_scripture_finding(template.suggested_scripture, lang))
    result.findings.append(
        Finding(
            summary=closing_text,
            excerpt=closing_text,
            citation=Citation(
                url=effective_jw_link,
                title="closing",
                kind="scaffold",
            ),
            metadata={"source": "letter_template", "section": "closing"},
        )
    )

    # Optional 5th: topic anchor from the Publications Index.
    if topic is not None:
        try:
            hits = await topic.search_subjects(
                topic_or_question, language=lang.upper()[0], limit=1
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Topic Index search failed: {exc}")
            hits = []
        if hits:
            subj_url = hits[0].get("url") or _SCAFFOLD_URL
            title = hits[0].get("title") or topic_or_question
            result.findings.append(
                Finding(
                    summary=f"Topic anchor suggestion: {title}",
                    excerpt="",
                    citation=Citation(url=subj_url, title=title, kind="topic_subject"),
                    metadata={"source": "topic_index", "section": "topic_anchor"},
                )
            )

    # Global metadata (informational only — no PII persisted).
    result.metadata.update(
        {
            "kind": kind,
            "audience": eff_audience,
            "topic_family": topic_family,
            "language": lang,
            "word_count_target": template.word_count_target,
            "time_target_seconds": template.time_target_seconds,
            "territory_hint": territory_hint,
            "jw_link_suggested": effective_jw_link,
            "suggested_scripture": template.suggested_scripture,
        }
    )

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-agents/tests/test_letter_composer.py -v`
Expected: 12 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/letter_composer.py packages/jw-agents/tests/test_letter_composer.py
git commit -m "feat(jw-agents): letter_composer with 3 kinds × 7 audiences × 8 families"
```

---

### Task 5: Re-export from `jw_agents` package and add optional Topic Index test

**Files:**
- Modify: `packages/jw-agents/src/jw_agents/__init__.py`
- Modify: `packages/jw-agents/tests/test_letter_composer.py`

- [ ] **Step 1: Append failing test for the optional TopicIndexClient path**

```python
def test_topic_client_optional_adds_topic_anchor() -> None:
    class StubTopic:
        async def search_subjects(self, q, *, language="E", limit=1):
            return [{"url": "https://wol.jw.org/topic/x", "title": "Stub topic"}]

        async def aclose(self) -> None:
            pass

    result = asyncio.run(
        letter_composer(
            kind="letter",
            language="es",
            topic_or_question="paz",
            audience="default",
            topic=StubTopic(),  # type: ignore[arg-type]
        )
    )
    anchors = [f for f in result.findings if f.metadata.get("section") == "topic_anchor"]
    assert len(anchors) == 1
    assert anchors[0].citation.url == "https://wol.jw.org/topic/x"


def test_topic_client_failure_emits_warning_not_raise() -> None:
    class BrokenTopic:
        async def search_subjects(self, q, *, language="E", limit=1):
            raise RuntimeError("network down")

    result = asyncio.run(
        letter_composer(
            kind="letter",
            language="es",
            topic_or_question="paz",
            audience="default",
            topic=BrokenTopic(),  # type: ignore[arg-type]
        )
    )
    # Still produces a usable scaffold.
    assert len(result.findings) >= 4
    assert any("topic index" in w.lower() for w in result.warnings)


def test_letter_composer_importable_from_package_root() -> None:
    import jw_agents

    assert hasattr(jw_agents, "letter_composer")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-agents/tests/test_letter_composer.py -v`
Expected: `test_letter_composer_importable_from_package_root` fails (`AttributeError`).

- [ ] **Step 3: Re-export from `jw_agents.__init__`**

Edit `packages/jw-agents/src/jw_agents/__init__.py` and add:

```python
from jw_agents.letter_composer import letter_composer

# Append to __all__:
#   "letter_composer",
```

Concretely, locate the existing `__all__` and append `"letter_composer"`. If `__all__` doesn't exist, ensure the import line is added below other agent imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-agents/tests/test_letter_composer.py -v`
Expected: 15 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/__init__.py packages/jw-agents/tests/test_letter_composer.py
git commit -m "feat(jw-agents): re-export letter_composer + optional TopicIndex enrichment"
```

---

### Task 6: CLI command `jw letter`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/letter.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`
- Create: `packages/jw-cli/tests/test_cli_letter.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-cli/tests/test_cli_letter.py
"""Smoke tests for `jw letter` CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from jw_cli.main import app


runner = CliRunner()


def test_letter_cli_letter_kind_runs() -> None:
    result = runner.invoke(
        app,
        [
            "letter",
            "--kind", "letter",
            "--topic", "esperanza para una madre en duelo",
            "--audience", "grieving",
            "--lang", "es",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "opener" in result.output.lower()
    assert "bridge" in result.output.lower()
    assert "scripture" in result.output.lower()
    assert "closing" in result.output.lower()


def test_letter_cli_phone_kind_shows_time_target() -> None:
    result = runner.invoke(
        app,
        ["letter", "--kind", "phone", "--topic", "paz", "--lang", "es"],
    )
    assert result.exit_code == 0
    assert "75" in result.output  # time target seconds


def test_letter_cli_invalid_kind_exits_nonzero() -> None:
    result = runner.invoke(
        app,
        ["letter", "--kind", "email", "--topic", "x"],
    )
    assert result.exit_code != 0


def test_letter_cli_territory_hint_appears_in_output() -> None:
    result = runner.invoke(
        app,
        [
            "letter",
            "--kind", "letter",
            "--topic", "esperanza",
            "--lang", "es",
            "--territory", "Lima, Perú",
        ],
    )
    assert result.exit_code == 0
    assert "Lima, Perú" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-cli/tests/test_cli_letter.py -v`
Expected: command not found error from Typer.

- [ ] **Step 3: Implement the CLI command**

```python
# packages/jw-cli/src/jw_cli/commands/letter.py
"""`jw letter --kind {letter|phone|cart} --topic ... --audience ...`.

Renders the structured scaffold returned by `letter_composer` as a
Rich table. The actual prose belongs to the publisher — this is a
calibrated starting point.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_agents.letter_composer import KINDS, letter_composer

console = Console()


def letter_cmd(
    kind: str = typer.Option(
        "letter",
        "--kind", "-k",
        help="Modality: letter | phone | cart.",
    ),
    topic: str = typer.Option(
        ...,
        "--topic", "-t",
        help="Free-form topic or question for the witnessing scaffold.",
    ),
    audience: str = typer.Option(
        "default",
        "--audience", "-a",
        help="Audience profile: default | new | religious | atheist | "
             "grieving | young | parents.",
    ),
    lang: str = typer.Option(
        "es",
        "--lang", "-l",
        help="Language code: en, es, or pt.",
    ),
    territory: str | None = typer.Option(
        None,
        "--territory",
        help="Optional cosmetic territory hint inserted in the opener.",
    ),
    jw_link: str | None = typer.Option(
        None,
        "--jw-link",
        help="Optional jw.org URL to use in the closing (overrides default).",
    ),
) -> None:
    """Compose a witnessing scaffold (letter / phone / cart)."""

    if kind not in KINDS:
        console.print(
            f"[red]Unknown kind {kind!r}. Allowed: {', '.join(KINDS)}[/red]"
        )
        raise typer.Exit(code=2)

    result = asyncio.run(
        letter_composer(
            kind=kind,  # type: ignore[arg-type]
            language=lang,
            topic_or_question=topic,
            audience=audience,
            territory_hint=territory,
            jw_link=jw_link,
        )
    )

    md = result.metadata
    header_lines = [
        f"[bold]Kind:[/bold] {md['kind']}",
        f"[bold]Audience:[/bold] {md['audience']}",
        f"[bold]Topic family:[/bold] {md['topic_family']}",
        f"[bold]Language:[/bold] {md['language']}",
    ]
    if md.get("time_target_seconds"):
        header_lines.append(
            f"[bold]Time target:[/bold] ~{md['time_target_seconds']}s"
        )
    if md.get("word_count_target"):
        header_lines.append(
            f"[bold]Word count target:[/bold] ~{md['word_count_target']}"
        )
    if md.get("territory_hint"):
        header_lines.append(
            f"[bold]Territory hint:[/bold] {md['territory_hint']}"
        )
    console.print(Panel("\n".join(header_lines), title="letter_composer"))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Section", style="bold")
    table.add_column("Content")
    for f in result.findings:
        section = (f.metadata.get("section") or "—").upper()
        table.add_row(section, f.summary)
    console.print(table)

    if result.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in result.warnings:
            console.print(f"  - {w}")

    console.print(
        f"\n[blue underline]{md['jw_link_suggested']}[/blue underline]"
    )
```

- [ ] **Step 4: Register the command in `main.py`**

Edit `packages/jw-cli/src/jw_cli/main.py` and add:

```python
from jw_cli.commands.letter import letter_cmd

app.command("letter")(letter_cmd)
```

(Insert next to existing `app.command("verse")(verse_cmd)` line.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-cli/tests/test_cli_letter.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/letter.py packages/jw-cli/src/jw_cli/main.py packages/jw-cli/tests/test_cli_letter.py
git commit -m "feat(jw-cli): jw letter --kind {letter|phone|cart} with Rich output"
```

---

### Task 7: MCP tool `compose_witnessing`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_compose_witnessing_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_compose_witnessing_tool.py
"""Smoke test for the compose_witnessing MCP tool."""

from __future__ import annotations

import asyncio


def test_compose_witnessing_tool_returns_dict() -> None:
    from jw_mcp.server import compose_witnessing as _tool  # noqa: PLC0415

    result = asyncio.run(
        _tool(
            kind="letter",
            language="es",
            topic="esperanza",
            audience="default",
        )
    )
    assert isinstance(result, dict)
    assert result["agent_name"] == "letter_composer"
    assert len(result["findings"]) >= 4
    sections = [f["metadata"]["section"] for f in result["findings"][:4]]
    assert sections == ["opener", "bridge", "scripture", "closing"]


def test_compose_witnessing_tool_passes_territory_hint() -> None:
    from jw_mcp.server import compose_witnessing as _tool  # noqa: PLC0415

    result = asyncio.run(
        _tool(
            kind="phone",
            language="es",
            topic="paz",
            territory_hint="Madrid",
        )
    )
    assert result["metadata"]["territory_hint"] == "Madrid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_compose_witnessing_tool.py -v`
Expected: ImportError.

- [ ] **Step 3: Register the tool**

Locate the section of `packages/jw-mcp/src/jw_mcp/server.py` where existing tools are registered (search for `@server.tool` or `@mcp.tool`). Append:

```python
from jw_agents.letter_composer import letter_composer as _letter_composer  # near other agent imports

# ... below other tool registrations ...

@server.tool
async def compose_witnessing(
    kind: str,
    language: str = "es",
    topic: str = "",
    audience: str = "default",
    territory_hint: str | None = None,
    jw_link: str | None = None,
) -> dict[str, Any]:
    """Compose a witnessing scaffold (letter | phone | cart).

    Sections returned in order: opener, bridge, scripture, closing.
    Each carries a verifiable citation URL. No PII is persisted.

    Args:
        kind: One of 'letter', 'phone', 'cart'.
        language: 'en' | 'es' | 'pt'.
        topic: Free-form topic or question that the scaffold addresses.
        audience: 'default' | 'new' | 'religious' | 'atheist' | 'grieving' |
                  'young' | 'parents'.
        territory_hint: Optional cosmetic territory string for the opener.
        jw_link: Optional jw.org URL to use in the closing.
    """

    result = await _letter_composer(
        kind=kind,  # type: ignore[arg-type]
        language=language,
        topic_or_question=topic,
        audience=audience,
        territory_hint=territory_hint,
        jw_link=jw_link,
    )
    return result.to_dict()
```

If the file uses a different decorator convention (`@mcp.tool`, `@app.tool`, `@server.add_tool`, etc.), match the existing pattern verbatim — preserve the file's style.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest packages/jw-mcp/tests/test_compose_witnessing_tool.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_compose_witnessing_tool.py
git commit -m "feat(jw-mcp): compose_witnessing tool (letter/phone/cart)"
```

---

### Task 8: Property-based citation invariant

**Files:**
- Modify: `packages/jw-agents/tests/test_letter_composer.py`

- [ ] **Step 1: Append the property test**

```python
import itertools

from jw_core.data.letter_templates import AUDIENCES, TOPIC_FAMILIES


@pytest.mark.parametrize(
    ("kind", "audience", "family", "lang"),
    list(itertools.product(("letter", "phone", "cart"), AUDIENCES, TOPIC_FAMILIES, ("en", "es", "pt"))),
)
def test_every_combination_emits_no_empty_citation(kind, audience, family, lang) -> None:
    # Construct a topic input that resolves to `family`. For 'generic' we
    # pass an unrelated string; for others we pass the first keyword.
    if family == "generic":
        topic = "zzz_unmatched_term_zzz"
    else:
        # Pick a known keyword from the resolver map for this language.
        from jw_core.data.letter_templates import TOPIC_FAMILY_KEYWORDS

        lang_map = TOPIC_FAMILY_KEYWORDS.get(lang) or TOPIC_FAMILY_KEYWORDS["en"]
        topic = lang_map[family][0]

    result = _run(
        kind=kind,
        language=lang,
        topic_or_question=topic,
        audience=audience,
    )
    assert len(result.findings) >= 4
    for f in result.findings:
        assert f.citation.url, (
            f"empty citation for kind={kind} audience={audience} "
            f"family={family} lang={lang} section={f.metadata.get('section')}"
        )
```

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest packages/jw-agents/tests/test_letter_composer.py -v`
Expected: 3 kinds × 7 audiences × 8 families × 3 langs = 504 parametrized cases + previous tests, all green.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-agents/tests/test_letter_composer.py
git commit -m "test(jw-agents): property-based citation invariant for letter_composer"
```

---

### Task 9: Add three Fase-22 golden cases (L1) for `letter_composer`

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_letter_grieving_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_phone_default_es.yaml`
- Create: `packages/jw-eval/fixtures/golden_qa/l1/letter_composer_cart_parents_en.yaml`

- [ ] **Step 1: Write the first L1 case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/letter_composer_letter_grieving_es.yaml
id: l1_letter_composer_letter_grieving_es
agent: letter_composer
layer: l1
input:
  kind: letter
  language: es
  topic_or_question: "Una madre que perdió a su hijo"
  audience: grieving
expected:
  min_findings: 4
  must_have_source: verse_text
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "Jehová te pide"
    - "deberías sentir"
    - "olvida tu dolor"
    - "supérelo"
metadata:
  topic: ministry.letter.grieving
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Write the phone case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/letter_composer_phone_default_es.yaml
id: l1_letter_composer_phone_default_es
agent: letter_composer
layer: l1
input:
  kind: phone
  language: es
  topic_or_question: "paz mental"
  audience: default
expected:
  min_findings: 4
  must_have_source: verse_text
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "no cuelgue"
    - "es obligatorio"
    - "Dios castigará"
metadata:
  topic: ministry.phone.default
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 3: Write the cart case**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/letter_composer_cart_parents_en.yaml
id: l1_letter_composer_cart_parents_en
agent: letter_composer
layer: l1
input:
  kind: cart
  language: en
  topic_or_question: "raising kids today"
  audience: parents
expected:
  min_findings: 4
  must_have_source: verse_text
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "you must"
    - "God will punish"
    - "buy this"
metadata:
  topic: ministry.cart.parents
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 4: Register the agent in the eval runner**

The eval suite needs to know how to instantiate `letter_composer`. Locate the agent dispatcher in `packages/jw-eval/src/jw_eval/` (likely `suite.py` or a `runners.py`). Where existing agents are wired (e.g. `apologetics`, `verse_explainer`), add:

```python
elif name == "letter_composer":
    from jw_agents.letter_composer import letter_composer

    async def _run(input_dict: dict):
        return await letter_composer(
            kind=input_dict["kind"],
            language=input_dict.get("language", "es"),
            topic_or_question=input_dict["topic_or_question"],
            audience=input_dict.get("audience", "default"),
            territory_hint=input_dict.get("territory_hint"),
            jw_link=input_dict.get("jw_link"),
        )

    return _run
```

(Adapt to the exact registry style used by the suite — `_AGENT_FACTORIES` dict or `match` block.)

- [ ] **Step 5: Run eval L1 filtered to this agent**

Run: `uv run jw eval --layer 1 --filter agent=letter_composer`
Expected: 3 cases, 3 pass.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1 packages/jw-eval/src/jw_eval
git commit -m "feat(jw-eval): seed 3 L1 golden cases for letter_composer"
```

---

### Task 10: Documentation — `docs/guias/compositor-de-predicacion.md`

**Files:**
- Create: `docs/guias/compositor-de-predicacion.md`

- [ ] **Step 1: Write the user guide**

```markdown
# Compositor de carta / teléfono / carrito

> Agente: `letter_composer` (Fase 29).
> Tool MCP: `compose_witnessing`.
> CLI: `jw letter --kind {letter|phone|cart} --topic "..." --audience ... --lang ...`.

## Qué hace

Produce un **andamiaje estructurado** para tres modalidades del servicio del campo:

- **`letter`** — carta personal (~150 palabras orientativas).
- **`phone`** — guion telefónico (~75 segundos orientativos).
- **`cart`** — micro-guion de carrito (~30 segundos orientativos).

Cada salida tiene 4 secciones obligatorias: `opener · bridge · scripture · closing`. Una 5ª opcional (`topic_anchor`) se añade si se pasa `TopicIndexClient`.

## Qué NO hace

- **No** escribe la carta / la llamada por usted. Le da un punto de partida calibrado para que usted lo lea con su voz, su contexto y su buen juicio.
- **No** sustituye la consejería de los ancianos.
- **No** almacena el `territory_hint`, la audiencia, ni el tema. El toolkit es stateless por invocación.
- **No** copia texto bíblico ni párrafos de jw.org. Solo emite la **referencia + URL canónica**. El texto del versículo lo abre usted en jw.org / JW Library.

## Audiencias soportadas

| Clave | Para quién |
|---|---|
| `default` | Persona del público sin contexto previo. |
| `new` | Vecino al que aún no ha contactado. |
| `religious` | Persona de fe (cualquier denominación). |
| `atheist` | Ateo / agnóstico — registro de evidencia. |
| `grieving` | Persona en duelo / con pérdida reciente. |
| `young` | Joven / adolescente — registro coloquial. |
| `parents` | Persona con responsabilidades de crianza. |

> **Aviso**: la audiencia es una **sugerencia del publicador**, no una etiqueta asignada a la persona real. Úsela con discernimiento.

## Familias temáticas (auto-detectadas)

`family`, `suffering`, `hope`, `science`, `peace`, `identity`, `addictions`, `generic`. La función `resolve_topic_family(text, language)` mira palabras clave en el texto y elige la más representada. Si nada matchea → `generic`.

## Política de copyright

- La prosa de las plantillas en `letter_templates.py` / `phone_templates.py` / `cart_templates.py` está **escrita por el autor del paquete** (paráfrasis neutra). No es texto de jw.org.
- El bloque `scripture` **no** copia el versículo: solo emite `Citation.url` apuntando a wol.jw.org. El consumidor abre la URL y lee el texto allí.
- El enlace sugerido (`suggested_jw_link`) apunta siempre a una URL pública de jw.org.

## Política de PII

- `territory_hint` es **cosmético**. Se concatena al opener tal cual. No filtra contenido. No se persiste.
- Use solo zona / ciudad. **Nunca** dirección, nombre completo, o teléfono. El toolkit no inspecciona el valor, pero usted no debe poner PII de terceros.
- Audiencia, tema, idioma — nada se persiste. Cada invocación es independiente.

## Ejemplos

### CLI

```bash
# Carta para una madre en duelo en Lima
jw letter --kind letter \
          --topic "Una madre que perdió a su hijo" \
          --audience grieving \
          --lang es \
          --territory "Lima, Perú"

# Llamada telefónica sobre ansiedad
jw letter --kind phone --topic "ansiedad" --audience default --lang es

# Carrito para padres anglohablantes
jw letter --kind cart --topic "raising kids today" --audience parents --lang en
```

### Python

```python
import asyncio
from jw_agents.letter_composer import letter_composer

result = asyncio.run(letter_composer(
    kind="letter",
    language="es",
    topic_or_question="esperanza para una persona enferma",
    audience="grieving",
))
for f in result.findings:
    print(f.metadata["section"], "→", f.summary)
print("URL sugerido:", result.metadata["jw_link_suggested"])
print("Versículo:", result.metadata["suggested_scripture"])
```

### MCP (Claude Desktop)

```
Usuario: compose_witnessing kind=cart language=es topic="paz" audience=default
```

## Cómo se calibró

- 7 audiencias × 8 familias temáticas = hasta 56 combinaciones por modalidad.
- No están todas escritas — fallback en cadena: `(audience, family)` → `(audience, 'generic')` → `('default', 'generic')`.
- Tres familias específicas implementadas hoy: `(grieving, suffering)`, `(atheist, science)`, `(parents, family)`. PRs bienvenidos para añadir variantes.

## Para añadir una plantilla nueva

1. Edite el módulo apropiado (`letter_templates.py`, `phone_templates.py` o `cart_templates.py`).
2. Añada un `LetterTemplate` con las tres traducciones (`en`/`es`/`pt`).
3. Regístrelo en `TEMPLATES` con la clave `(audience, family)`.
4. Añada un caso L1 en `packages/jw-eval/fixtures/golden_qa/l1/` que valide la estructura.
5. Revise que pasa: `uv run jw eval --layer 1 --filter agent=letter_composer`.

## Métricas de uso

Tiempo y palabras objetivo son **datos informativos**, no reglas. El CLI los muestra con prefijo `~`. La métrica real la lleva usted: tiempo de pie en el carrito, longitud de la carta enviada.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/compositor-de-predicacion.md
git commit -m "docs(guias): compositor de predicación (Fase 29)"
```

---

### Task 11: Update ROADMAP and VISION_AUDIT

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`

- [ ] **Step 1: Add Fase 29 entry to ROADMAP**

Locate the section listing post-Fase 21 work (Fases 22-32 plan). Append (or update if a placeholder exists):

```markdown
### Fase 29 — Compositor de carta / teléfono / carrito (Tier 4) ✅

- Agente `letter_composer` con 3 modalidades × 7 audiencias × 8 familias temáticas.
- Salida estructurada (`opener · bridge · scripture · closing`), copyright-safe.
- CLI `jw letter`, tool MCP `compose_witnessing`, 3 golden cases L1.
- Guía: [`docs/guias/compositor-de-predicacion.md`](guias/compositor-de-predicacion.md).
- Spec / plan: `docs/superpowers/specs/2026-05-30-fase-29-letter-composer-design.md`.
```

- [ ] **Step 2: Add a row to VISION_AUDIT (feature #4)**

Locate the row mapping feature #4 (compositor) and replace its status with:

```markdown
| #4 Compositor carta/teléfono/carrito | ✅ Fase 29 | `jw_agents.letter_composer`, `jw letter`, `compose_witnessing` |
```

(If a different table format is used, mirror it exactly.)

- [ ] **Step 3: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md
git commit -m "docs: mark Fase 29 (letter_composer) complete in ROADMAP and VISION_AUDIT"
```

---

### Task 12: Full regression run

- [ ] **Step 1: Run all tests**

Run: `.venv/bin/python -m pytest`
Expected: every test green; **no regression** on the 551+ pre-existing tests.

- [ ] **Step 2: Run eval L1 over the whole suite**

Run: `uv run jw eval --layer 1`
Expected: every L1 case pass, including 3 new `letter_composer` cases.

- [ ] **Step 3: Smoke the CLI in all three modes / two languages**

```bash
uv run jw letter --kind letter --topic "esperanza" --audience grieving --lang es
uv run jw letter --kind phone  --topic "ansiedad"  --audience default  --lang en
uv run jw letter --kind cart   --topic "familia"   --audience parents  --lang pt
```

Expected: each prints a Rich panel + 4-row table; exit 0.

- [ ] **Step 4: Smoke the MCP tool**

Inspect the tool list:

```bash
uv run jw-mcp --list-tools | grep compose_witnessing
```

Expected: tool is registered.

- [ ] **Step 5: Commit (only if previous steps modified anything; usually no)**

If any small fix was needed during smoke, commit it:

```bash
git commit -am "fix(jw-...): minor adjustment found during Fase 29 smoke"
```

---

### Task 13: PR + audit

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feature/fase-29-letter-composer
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "Fase 29 — letter_composer (letter/phone/cart witnessing)" \
             --body "$(cat <<'EOF'
## Summary
- Agente `letter_composer` con 3 modalidades, 7 audiencias, 8 familias temáticas (resolver heurístico).
- Plantillas en `jw_core.data.{letter,phone,cart}_templates` — prosa propia, copyright-safe.
- CLI `jw letter`, tool MCP `compose_witnessing`.
- 3 golden cases L1 en `jw-eval`; guía en `docs/guias/compositor-de-predicacion.md`.
- Sin red en tests. Sin PII persistida. Stateless por invocación.

## Test plan
- [x] `.venv/bin/python -m pytest` — toda la suite verde.
- [x] `uv run jw eval --layer 1 --filter agent=letter_composer` — 3/3.
- [x] CLI smoke en es/en/pt × letter/phone/cart.
- [x] MCP tool registrada y reachable.

Spec: docs/superpowers/specs/2026-05-30-fase-29-letter-composer-design.md
Plan: docs/superpowers/plans/2026-05-30-fase-29-letter-composer-plan.md
EOF
)"
```

---

## Self-review

- ✅ TDD strict: cada task escribe el test fallando antes del código.
- ✅ Sin red en tests; el path con `TopicIndexClient` usa stubs locales.
- ✅ Citation invariant cubierto por test parametrizado (504 combinaciones).
- ✅ Política de copyright explícita: prose escrita por el autor; `excerpt` de scripture vacío.
- ✅ `territory_hint` aislado al opener; test específico que no se propaga.
- ✅ Fallback en cadena `(audience, family) → (audience, 'generic') → ('default', 'generic')` con test que toca los 3 niveles.
- ✅ Idiomas en/es/pt como dato duro; fallback a inglés con warning.
- ✅ 3 casos L1 en Fase 22 — uno por modalidad.
- ✅ Documentado: política de PII, de copyright, alcance del feature.
- ✅ Sin LLM en path crítico (resolver heurístico + lookup determinista).

## Execution choice

Subagent-driven (recomendado) o manual lineal. Las tareas son independientes salvo:

- Task 5 depende de Task 4.
- Task 6/7 dependen de Task 4-5.
- Task 9 depende de Task 4.
- Task 10/11/12/13 son finales.

Sin paralelización útil dentro del feature (todas las tareas son pequeñas). Recomendación: ejecutar lineal 1→13 en una sesión de ~3 horas + buffer para revisión de prosa de plantillas (la parte más subjetiva).

## Open question for the human

- ¿Qué granularidad de plantillas específicas (`(audience, family)`) quieres en el merge inicial? Hoy el plan tiene 3 (`grieving×suffering`, `atheist×science`, `parents×family`) más 7 genéricas por modalidad = 30 plantillas. ¿Añadimos más antes del PR, o las dejamos para PRs incrementales con su golden case cada uno?
