# Fase 26 — `student_part_helper` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `student_part_helper`, a procedural agent that produces a structured 4-section script for any of the 4 student assignment kinds (`bible_reading`, `starting_conversation`, `return_visit`, `bible_study`), hooked to the oratory point of the month, fully deterministic, with citations, in `en`/`es`/`pt`.

**Architecture:** Two new data modules in `jw-core` (`oratory_points`, `student_parts_templates`), one new agent in `jw-agents` (`student_part_helper`), one CLI command in `jw-cli` (`jw student`), one MCP tool in `jw-mcp` (`student_part_help`), 4 L1 golden cases for `jw-eval`, one user guide. Zero LLM calls; optional network only when topic_or_ref == "this week".

**Tech Stack:** Python 3.13 · `@dataclass(frozen=True)` (data modules) · `pytest` · `jw_core.parsers.reference` · `jw_core.parsers.workbook` (Fase 11) · Typer/Rich (CLI) · FastMCP (MCP tool).

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-26-student-parts-design.md`](../specs/2026-05-30-fase-26-student-parts-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/oratory_points.py`
- `packages/jw-core/src/jw_core/data/student_parts_templates.py`
- `packages/jw-core/tests/test_oratory_points.py`
- `packages/jw-core/tests/test_student_parts_templates.py`
- `packages/jw-agents/src/jw_agents/student_part_helper.py`
- `packages/jw-agents/tests/test_student_part_helper.py`
- `packages/jw-cli/src/jw_cli/commands/student.py`
- `packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_reading_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/student_part_conversation_en.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/student_part_return_visit_pt.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_study_es.yaml`
- `docs/guias/partes-del-estudiante.md`

Modifies:
- `packages/jw-agents/src/jw_agents/__init__.py` — export `student_part_helper`.
- `packages/jw-cli/src/jw_cli/main.py` (or `commands/__init__.py`) — register `student` subcommand.
- `packages/jw-mcp/src/jw_mcp/server.py` — add `student_part_help` tool.
- `docs/ROADMAP.md` — add Fase 26 entry.
- `docs/VISION_AUDIT.md` — mark VISION #2 as completed.
- `docs/README.md` — link the new guide.

---

### Task 1: Scaffold `oratory_points` data module (TDD)

**Files:**
- Create: `packages/jw-core/src/jw_core/data/oratory_points.py`
- Create: `packages/jw-core/tests/test_oratory_points.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_oratory_points.py
"""Tests for jw_core.data.oratory_points registry."""

from __future__ import annotations

from datetime import date

import pytest

from jw_core.data.oratory_points import (
    ORATORY_POINTS,
    OratoryPoint,
    brief,
    get_point,
    key_phrase,
    point_of_the_month,
    points_applicable_to,
)


def test_registry_has_50_points() -> None:
    assert len(ORATORY_POINTS) == 50


def test_points_are_numbered_1_to_50_uniquely() -> None:
    numbers = sorted(p.number for p in ORATORY_POINTS)
    assert numbers == list(range(1, 51))


def test_brief_paraphrases_under_300_chars() -> None:
    for p in ORATORY_POINTS:
        assert len(p.brief_en) <= 300, p.number
        assert len(p.brief_es) <= 300, p.number
        assert len(p.brief_pt) <= 300, p.number


def test_key_phrases_under_120_chars() -> None:
    for p in ORATORY_POINTS:
        assert len(p.key_phrase_en) <= 120
        assert len(p.key_phrase_es) <= 120
        assert len(p.key_phrase_pt) <= 120


def test_get_point_returns_canonical() -> None:
    p = get_point(1)
    assert p.number == 1


def test_get_point_raises_on_unknown() -> None:
    with pytest.raises(ValueError):
        get_point(0)
    with pytest.raises(ValueError):
        get_point(51)


def test_point_of_the_month_is_deterministic() -> None:
    # Month 1 → point 1 in our canonical mapping.
    p = point_of_the_month(date(2026, 1, 15))
    assert p.number == 1
    # Month 7 → point 25.
    assert point_of_the_month(date(2026, 7, 1)).number == 25
    # Month 12 → point 45.
    assert point_of_the_month(date(2026, 12, 31)).number == 45


def test_points_applicable_to_filters_by_kind() -> None:
    applicable = points_applicable_to("bible_reading")
    assert all("bible_reading" in p.applies_to for p in applicable)
    assert len(applicable) >= 10  # plenty of advice for reading aloud


def test_points_applicable_to_unknown_kind_returns_empty() -> None:
    assert points_applicable_to("nonsense") == []


def test_key_phrase_helper_picks_language() -> None:
    p = get_point(1)
    assert key_phrase(p, "en") == p.key_phrase_en
    assert key_phrase(p, "es") == p.key_phrase_es
    assert key_phrase(p, "pt") == p.key_phrase_pt
    # Unknown language falls back to en.
    assert key_phrase(p, "xx") == p.key_phrase_en


def test_brief_helper_picks_language() -> None:
    p = get_point(1)
    assert brief(p, "es") == p.brief_es
    assert brief(p, "xx") == p.brief_en
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-core/tests/test_oratory_points.py -v
```

Expected: FAIL — `ModuleNotFoundError: jw_core.data.oratory_points`.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-core/src/jw_core/data/oratory_points.py
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
    # Points 9-50 follow the same shape. For brevity in this plan they
    # are listed compactly below; the file commits the full text.
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-core/tests/test_oratory_points.py -v
```

Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/oratory_points.py packages/jw-core/tests/test_oratory_points.py
git commit -m "feat(jw-core): oratory_points registry (50 paraphrased entries × 3 langs)"
```

---

### Task 2: Scaffold `student_parts_templates` data module (TDD)

**Files:**
- Create: `packages/jw-core/src/jw_core/data/student_parts_templates.py`
- Create: `packages/jw-core/tests/test_student_parts_templates.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_student_parts_templates.py
"""Tests for jw_core.data.student_parts_templates."""

from __future__ import annotations

import pytest

from jw_core.data.student_parts_templates import (
    PART_TEMPLATES,
    PartTemplate,
    find_template,
    time_target_seconds_for,
)


def test_registry_has_48_templates() -> None:
    # 4 kinds × 4 audiences × 3 langs = 48
    assert len(PART_TEMPLATES) == 48


def test_every_kind_audience_language_present() -> None:
    kinds = ("bible_reading", "starting_conversation", "return_visit", "bible_study")
    audiences = ("default", "new", "religious", "atheist")
    langs = ("en", "es", "pt")
    slots = {(t.kind, t.audience, t.language) for t in PART_TEMPLATES}
    expected = {(k, a, l) for k in kinds for a in audiences for l in langs}
    assert slots == expected


def test_find_template_exact_match() -> None:
    t = find_template("bible_reading", "default", "es")
    assert t.kind == "bible_reading"
    assert t.audience == "default"
    assert t.language == "es"


def test_find_template_falls_back_to_default_audience() -> None:
    # Remove the 'new' audience entry virtually by asking for a typo-ish audience.
    # Easier path: directly exercise the fallback code path.
    # We trust the existence test; here we test that asking for an unsupported
    # audience returns the default-audience template.
    t = find_template("bible_reading", "child", "es")  # 'child' not a slot
    assert t.audience == "default"
    assert t.language == "es"


def test_find_template_falls_back_to_default_language() -> None:
    t = find_template("bible_reading", "default", "fr")
    assert t.language == "en"
    assert t.kind == "bible_reading"


def test_find_template_raises_on_unknown_kind() -> None:
    with pytest.raises(ValueError):
        find_template("invented_kind", "default", "es")


def test_time_targets_are_correct() -> None:
    assert time_target_seconds_for("bible_reading") == 240
    assert time_target_seconds_for("starting_conversation") == 180
    assert time_target_seconds_for("return_visit") == 240
    assert time_target_seconds_for("bible_study") == 300


def test_time_target_raises_on_unknown_kind() -> None:
    with pytest.raises(ValueError):
        time_target_seconds_for("nope")


def test_every_template_has_required_placeholders_declared() -> None:
    for t in PART_TEMPLATES:
        # The four script slots should contain at least one placeholder
        # together, and `required_placeholders` should be a strict subset
        # of placeholders actually present in opening/body/transition/close.
        joined = "|".join([t.opening, t.body, t.transition, t.close])
        for placeholder in t.required_placeholders:
            assert "{" + placeholder + "}" in joined, (t.kind, t.audience, t.language, placeholder)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-core/tests/test_student_parts_templates.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the templates module**

```python
# packages/jw-core/src/jw_core/data/student_parts_templates.py
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
    "bible_reading", "default", "en",
    opening="The reading today is {verse_display}. Listen for the main idea this passage drives home.",
    body="As I read, notice how the writer builds the thought. I'll apply the point '{oratory_phrase}' — {oratory_brief}",
    transition="Now, having heard those words, consider what they imply for our worship.",
    close="May this reading move us to act in harmony with what it says.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_ES_DEFAULT = _t(
    "bible_reading", "default", "es",
    opening="La lectura de hoy es {verse_display}. Atienda a la idea principal que el pasaje destaca.",
    body="Mientras leo, fíjese en cómo el escritor construye la idea. Aplicaré el punto '{oratory_phrase}' — {oratory_brief}",
    transition="Habiendo escuchado esas palabras, considere qué implican para nuestra adoración.",
    close="Que esta lectura nos mueva a actuar conforme a lo que dice.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)
_BR_PT_DEFAULT = _t(
    "bible_reading", "default", "pt",
    opening="A leitura de hoje é {verse_display}. Atente para a ideia principal que o trecho destaca.",
    body="Enquanto leio, observe como o escritor constrói o pensamento. Aplicarei o ponto '{oratory_phrase}' — {oratory_brief}",
    transition="Tendo escutado essas palavras, considere o que elas implicam para nossa adoração.",
    close="Que esta leitura nos mova a agir conforme o que diz.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"),
)

# The 'new', 'religious', 'atheist' variants differ only in the framing of
# opening/transition/close — body keeps the same '{oratory_phrase}' hook.
_BR_EN_NEW = _t("bible_reading", "new", "en",
    "Today's reading is {verse_display}. You'll hear a thought that you can apply this week.",
    "While I read, listen for the main point. I'll keep '{oratory_phrase}' in mind — {oratory_brief}",
    "What we just heard answers a real question many people have.",
    "Thank you for listening — may these words encourage you.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_EN_REL = _t("bible_reading", "religious", "en",
    "Many cherish the words we will read: {verse_display}. Let's listen together.",
    "As I read, notice the original sense. The point '{oratory_phrase}' applies — {oratory_brief}",
    "Compared with how this is often quoted, the full passage gives a fuller picture.",
    "May reading the Scriptures together build us up in faith.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_EN_ATH = _t("bible_reading", "atheist", "en",
    "Whether or not one accepts the Bible, the passage {verse_display} is worth hearing for its argument.",
    "Notice the logic of the text. I'll apply '{oratory_phrase}' so the structure is clear — {oratory_brief}",
    "Set aside belief for a moment — what claim is the writer making?",
    "Thanks for the open-minded hearing.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))

_BR_ES_NEW = _t("bible_reading", "new", "es",
    "La lectura de hoy es {verse_display}. Escuchará una idea que podrá aplicar esta semana.",
    "Mientras leo, atienda al punto principal. Tendré en cuenta '{oratory_phrase}' — {oratory_brief}",
    "Lo que acabamos de oír responde una pregunta real que muchos tienen.",
    "Gracias por escuchar; que estas palabras le animen.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_ES_REL = _t("bible_reading", "religious", "es",
    "Muchos aprecian las palabras que leeremos: {verse_display}. Escuchemos juntos.",
    "Mientras leo, observe el sentido original. Aplica el punto '{oratory_phrase}' — {oratory_brief}",
    "Comparado con la cita habitual, el pasaje completo aporta más contexto.",
    "Que leer las Escrituras juntos nos edifique en la fe.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_ES_ATH = _t("bible_reading", "atheist", "es",
    "Acepte o no la Biblia, el pasaje {verse_display} vale la pena escucharlo por su argumento.",
    "Note la lógica del texto. Aplicaré '{oratory_phrase}' para que la estructura se vea clara — {oratory_brief}",
    "Por un momento, deje a un lado la creencia: ¿qué afirma el escritor?",
    "Gracias por la escucha abierta.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))

_BR_PT_NEW = _t("bible_reading", "new", "pt",
    "A leitura de hoje é {verse_display}. Você ouvirá uma ideia que poderá aplicar nesta semana.",
    "Enquanto leio, observe o ponto principal. Manterei '{oratory_phrase}' em mente — {oratory_brief}",
    "O que acabamos de ouvir responde a uma pergunta real que muitos têm.",
    "Obrigado por escutar; que essas palavras lhe animem.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_PT_REL = _t("bible_reading", "religious", "pt",
    "Muitos apreciam as palavras que leremos: {verse_display}. Vamos escutar juntos.",
    "Enquanto leio, observe o sentido original. Aplica-se o ponto '{oratory_phrase}' — {oratory_brief}",
    "Comparado à citação habitual, o trecho completo dá mais contexto.",
    "Que ler as Escrituras juntos nos edifique na fé.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_BR_PT_ATH = _t("bible_reading", "atheist", "pt",
    "Aceitando ou não a Bíblia, o trecho {verse_display} vale a pena ser escutado pelo argumento.",
    "Note a lógica do texto. Aplicarei '{oratory_phrase}' para que a estrutura fique clara — {oratory_brief}",
    "Por um momento, deixe de lado a crença: o que o escritor afirma?",
    "Obrigado pela escuta aberta.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))


# ── STARTING CONVERSATION ───────────────────────────────────────────────


_SC_EN_DEF = _t("starting_conversation", "default", "en",
    "Hello — many today are searching for hope amid difficult news. Have you noticed that?",
    "The Bible at {verse_display} offers a thought worth comparing. As I share, I'll apply '{oratory_phrase}' — {oratory_brief}",
    "What stands out to you in that verse?",
    "Thank you for your time — I'd love to share more next week.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_EN_NEW = _t("starting_conversation", "new", "en",
    "Hi! I'm visiting neighbors with a brief encouragement. Do you have a minute?",
    "I'd like to read {verse_display} and ask you a question. Applying '{oratory_phrase}' — {oratory_brief}",
    "Have you thought about that idea before?",
    "Thanks — I'd be happy to follow up.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_EN_REL = _t("starting_conversation", "religious", "en",
    "It's good to meet someone who values the Bible. Have you ever thought about how {topic} fits with Scripture?",
    "Consider {verse_display}. With the point '{oratory_phrase}' in mind — {oratory_brief}",
    "Does that match what you've understood?",
    "Thank you for the open dialogue.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"))
_SC_EN_ATH = _t("starting_conversation", "atheist", "en",
    "I appreciate honest conversations about meaning. Even without religious assumptions, the Bible raises real questions.",
    "Take {verse_display}. Whatever your view, '{oratory_phrase}' helps engage the text — {oratory_brief}",
    "What's your honest reaction to that?",
    "Thanks for taking the question seriously.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))

_SC_ES_DEF = _t("starting_conversation", "default", "es",
    "Hola — muchos hoy buscan esperanza ante noticias difíciles. ¿Lo ha notado?",
    "La Biblia, en {verse_display}, ofrece una idea que vale la pena comparar. Aplicaré '{oratory_phrase}' — {oratory_brief}",
    "¿Qué le llama la atención de ese versículo?",
    "Gracias por su tiempo — me gustaría compartir más la próxima semana.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_ES_NEW = _t("starting_conversation", "new", "es",
    "¡Hola! Visito a los vecinos con un breve ánimo. ¿Tiene un minuto?",
    "Quisiera leer {verse_display} y hacerle una pregunta. Aplicando '{oratory_phrase}' — {oratory_brief}",
    "¿Había pensado antes en esa idea?",
    "Gracias — con gusto vuelvo otro día.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_ES_REL = _t("starting_conversation", "religious", "es",
    "Es bueno encontrar a alguien que aprecie la Biblia. ¿Ha pensado cómo encaja {topic} con la Escritura?",
    "Considere {verse_display}. Con el punto '{oratory_phrase}' en mente — {oratory_brief}",
    "¿Coincide con lo que ha entendido?",
    "Gracias por el diálogo abierto.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"))
_SC_ES_ATH = _t("starting_conversation", "atheist", "es",
    "Aprecio las conversaciones honestas sobre el sentido. Aun sin supuestos religiosos, la Biblia plantea preguntas reales.",
    "Tome {verse_display}. Sea cual sea su postura, '{oratory_phrase}' ayuda a abordar el texto — {oratory_brief}",
    "¿Cuál es su reacción honesta?",
    "Gracias por tomar la pregunta en serio.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))

_SC_PT_DEF = _t("starting_conversation", "default", "pt",
    "Olá — muitos hoje buscam esperança em meio a notícias difíceis. Você tem percebido isso?",
    "A Bíblia, em {verse_display}, oferece uma ideia que vale a pena comparar. Aplicarei '{oratory_phrase}' — {oratory_brief}",
    "O que chama sua atenção nesse versículo?",
    "Obrigado pelo seu tempo — gostaria de compartilhar mais na próxima semana.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_PT_NEW = _t("starting_conversation", "new", "pt",
    "Oi! Estou visitando vizinhos com um breve incentivo. Você tem um minuto?",
    "Eu gostaria de ler {verse_display} e fazer uma pergunta. Aplicando '{oratory_phrase}' — {oratory_brief}",
    "Você já tinha pensado nessa ideia?",
    "Obrigado — terei prazer em voltar.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))
_SC_PT_REL = _t("starting_conversation", "religious", "pt",
    "É bom encontrar alguém que valoriza a Bíblia. Você já pensou como {topic} se encaixa com a Escritura?",
    "Considere {verse_display}. Com o ponto '{oratory_phrase}' em mente — {oratory_brief}",
    "Combina com o que você tem entendido?",
    "Obrigado pelo diálogo aberto.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic"))
_SC_PT_ATH = _t("starting_conversation", "atheist", "pt",
    "Aprecio conversas honestas sobre sentido. Mesmo sem pressupostos religiosos, a Bíblia levanta perguntas reais.",
    "Tome {verse_display}. Qualquer que seja sua posição, '{oratory_phrase}' ajuda a abordar o texto — {oratory_brief}",
    "Qual sua reação honesta?",
    "Obrigado por levar a pergunta a sério.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief"))


# ── RETURN VISIT ────────────────────────────────────────────────────────


_RV_EN_DEF = _t("return_visit", "default", "en",
    "Good to see you again. Last time we touched on {prior_seed}.",
    "I brought {verse_display} to develop that thought. Today I'll apply '{oratory_phrase}' — {oratory_brief}",
    "What has come to mind since we last talked?",
    "Next time I'd like to discuss {next_visit_hook}. Would that work?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_EN_NEW = _t("return_visit", "new", "en",
    "Thanks for letting me come back. Last time we left off at {prior_seed}.",
    "Look at {verse_display} with me — the point '{oratory_phrase}' helps us read it — {oratory_brief}",
    "Has anything in your week reminded you of this?",
    "Could I share {next_visit_hook} next time?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_EN_REL = _t("return_visit", "religious", "en",
    "Last time you mentioned {prior_seed}. I've been looking forward to today.",
    "Compare your view with {verse_display}. The point '{oratory_phrase}' is useful here — {oratory_brief}",
    "What does this open up for you?",
    "Next we could examine {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_EN_ATH = _t("return_visit", "atheist", "en",
    "You raised a fair point last time about {prior_seed}. I thought about it.",
    "Look at {verse_display}. With '{oratory_phrase}' as a frame — {oratory_brief}",
    "Does that move the question for you, even a little?",
    "I'd like to bring {next_visit_hook} next time.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))

_RV_ES_DEF = _t("return_visit", "default", "es",
    "Qué gusto verlo de nuevo. La última vez tocamos {prior_seed}.",
    "Traje {verse_display} para desarrollar esa idea. Hoy aplicaré '{oratory_phrase}' — {oratory_brief}",
    "¿Qué le ha venido a la mente desde nuestra última conversación?",
    "La próxima vez quisiera tratar {next_visit_hook}. ¿Le parece?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_ES_NEW = _t("return_visit", "new", "es",
    "Gracias por permitirme volver. La última vez quedamos en {prior_seed}.",
    "Veamos {verse_display} — el punto '{oratory_phrase}' ayuda a leerlo — {oratory_brief}",
    "¿Algo en su semana le ha recordado esto?",
    "¿Podría compartir {next_visit_hook} la próxima?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_ES_REL = _t("return_visit", "religious", "es",
    "La vez pasada mencionó {prior_seed}. Tenía ganas de hablar hoy.",
    "Compare su postura con {verse_display}. El punto '{oratory_phrase}' resulta útil — {oratory_brief}",
    "¿Qué le abre eso?",
    "La próxima podríamos examinar {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_ES_ATH = _t("return_visit", "atheist", "es",
    "Planteó algo justo la última vez sobre {prior_seed}. Lo pensé.",
    "Vea {verse_display}. Con '{oratory_phrase}' como marco — {oratory_brief}",
    "¿Mueve eso la pregunta, aunque sea un poco?",
    "Me gustaría traer {next_visit_hook} la próxima.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))

_RV_PT_DEF = _t("return_visit", "default", "pt",
    "Que bom ver você de novo. Da última vez tocamos em {prior_seed}.",
    "Trouxe {verse_display} para desenvolver essa ideia. Hoje aplicarei '{oratory_phrase}' — {oratory_brief}",
    "O que veio à sua mente desde a última conversa?",
    "Na próxima gostaria de tratar {next_visit_hook}. Você concorda?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_PT_NEW = _t("return_visit", "new", "pt",
    "Obrigado por me deixar voltar. Da última vez paramos em {prior_seed}.",
    "Vamos ver {verse_display} — o ponto '{oratory_phrase}' ajuda a ler — {oratory_brief}",
    "Algo na sua semana lembrou isto?",
    "Posso compartilhar {next_visit_hook} na próxima?",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_PT_REL = _t("return_visit", "religious", "pt",
    "Da última vez você mencionou {prior_seed}. Estava ansioso por hoje.",
    "Compare sua posição com {verse_display}. O ponto '{oratory_phrase}' é útil — {oratory_brief}",
    "O que isso abre para você?",
    "Na próxima poderíamos examinar {next_visit_hook}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))
_RV_PT_ATH = _t("return_visit", "atheist", "pt",
    "Você levantou algo justo da última vez sobre {prior_seed}. Pensei nisso.",
    "Veja {verse_display}. Com '{oratory_phrase}' como moldura — {oratory_brief}",
    "Isso move a pergunta para você, mesmo que pouco?",
    "Gostaria de trazer {next_visit_hook} na próxima.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "prior_seed", "next_visit_hook"))


# ── BIBLE STUDY DEMO ────────────────────────────────────────────────────


_BS_EN_DEF = _t("bible_study", "default", "en",
    "Today we'll cover paragraph {paragraph} of {topic}. Notice what it teaches about {focus}.",
    "Read with me. After we read, I'll apply the point '{oratory_phrase}' — {oratory_brief}. The supporting text is {verse_display}.",
    "Question to consider: how does this affect what we do this week?",
    "Next time we'll work on paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph", "focus"))
_BS_EN_NEW = _t("bible_study", "new", "en",
    "We'll look at paragraph {paragraph} of {topic} — a thought you can use this week.",
    "Read with me; I'll apply '{oratory_phrase}' so the point is clear — {oratory_brief}. See also {verse_display}.",
    "What part of this answers a real question for you?",
    "Next time, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_EN_REL = _t("bible_study", "religious", "en",
    "Today paragraph {paragraph} of {topic} — see how it lines up with what you've understood.",
    "Read with me. Applying '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "Where does this match your own reading of Scripture?",
    "Next, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_EN_ATH = _t("bible_study", "atheist", "en",
    "Paragraph {paragraph} of {topic} — read it as an argument, see if it stands.",
    "We'll read together; '{oratory_phrase}' will help us examine it — {oratory_brief}. The cited text is {verse_display}.",
    "Where does the argument hold or fail?",
    "Next time, paragraph {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))

_BS_ES_DEF = _t("bible_study", "default", "es",
    "Hoy veremos el párrafo {paragraph} de {topic}. Note qué enseña sobre {focus}.",
    "Leamos juntos. Después, aplicaré el punto '{oratory_phrase}' — {oratory_brief}. El texto de apoyo es {verse_display}.",
    "Pregunta: ¿cómo afecta esto lo que haremos esta semana?",
    "La próxima trabajaremos el párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph", "focus"))
_BS_ES_NEW = _t("bible_study", "new", "es",
    "Veremos el párrafo {paragraph} de {topic} — una idea útil para esta semana.",
    "Leamos juntos; aplicaré '{oratory_phrase}' para que el punto se vea claro — {oratory_brief}. Vea también {verse_display}.",
    "¿Qué parte le contesta una pregunta real?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_ES_REL = _t("bible_study", "religious", "es",
    "Hoy, párrafo {paragraph} de {topic} — vea cómo concuerda con lo que ha entendido.",
    "Leamos juntos. Aplicando '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "¿Dónde coincide con su propia lectura?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_ES_ATH = _t("bible_study", "atheist", "es",
    "Párrafo {paragraph} de {topic} — léalo como argumento, vea si se sostiene.",
    "Leeremos juntos; '{oratory_phrase}' nos ayudará a examinarlo — {oratory_brief}. El texto citado es {verse_display}.",
    "¿Dónde se sostiene o falla el argumento?",
    "La próxima, párrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))

_BS_PT_DEF = _t("bible_study", "default", "pt",
    "Hoje veremos o parágrafo {paragraph} de {topic}. Note o que ensina sobre {focus}.",
    "Vamos ler juntos. Depois aplicarei o ponto '{oratory_phrase}' — {oratory_brief}. O texto de apoio é {verse_display}.",
    "Pergunta: como isso afeta o que faremos nesta semana?",
    "Na próxima vez trabalharemos o parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph", "focus"))
_BS_PT_NEW = _t("bible_study", "new", "pt",
    "Veremos o parágrafo {paragraph} de {topic} — uma ideia útil para esta semana.",
    "Vamos ler juntos; aplicarei '{oratory_phrase}' para que o ponto fique claro — {oratory_brief}. Veja também {verse_display}.",
    "Que parte responde a uma pergunta real para você?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_PT_REL = _t("bible_study", "religious", "pt",
    "Hoje, parágrafo {paragraph} de {topic} — veja como combina com o que entendeu.",
    "Vamos ler juntos. Aplicando '{oratory_phrase}' — {oratory_brief}. Compare {verse_display}.",
    "Onde combina com sua própria leitura?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))
_BS_PT_ATH = _t("bible_study", "atheist", "pt",
    "Parágrafo {paragraph} de {topic} — leia como argumento, veja se se sustenta.",
    "Leremos juntos; '{oratory_phrase}' nos ajudará a examinar — {oratory_brief}. Texto citado: {verse_display}.",
    "Onde o argumento se sustenta ou falha?",
    "Na próxima, parágrafo {next_paragraph}.",
    required_placeholders=("verse_display", "oratory_phrase", "oratory_brief", "topic", "paragraph", "next_paragraph"))


PART_TEMPLATES: tuple[PartTemplate, ...] = (
    _BR_EN_DEFAULT, _BR_EN_NEW, _BR_EN_REL, _BR_EN_ATH,
    _BR_ES_DEFAULT, _BR_ES_NEW, _BR_ES_REL, _BR_ES_ATH,
    _BR_PT_DEFAULT, _BR_PT_NEW, _BR_PT_REL, _BR_PT_ATH,
    _SC_EN_DEF, _SC_EN_NEW, _SC_EN_REL, _SC_EN_ATH,
    _SC_ES_DEF, _SC_ES_NEW, _SC_ES_REL, _SC_ES_ATH,
    _SC_PT_DEF, _SC_PT_NEW, _SC_PT_REL, _SC_PT_ATH,
    _RV_EN_DEF, _RV_EN_NEW, _RV_EN_REL, _RV_EN_ATH,
    _RV_ES_DEF, _RV_ES_NEW, _RV_ES_REL, _RV_ES_ATH,
    _RV_PT_DEF, _RV_PT_NEW, _RV_PT_REL, _RV_PT_ATH,
    _BS_EN_DEF, _BS_EN_NEW, _BS_EN_REL, _BS_EN_ATH,
    _BS_ES_DEF, _BS_ES_NEW, _BS_ES_REL, _BS_ES_ATH,
    _BS_PT_DEF, _BS_PT_NEW, _BS_PT_REL, _BS_PT_ATH,
)


_BY_SLOT: dict[tuple[str, str, str], PartTemplate] = {
    (t.kind, t.audience, t.language): t for t in PART_TEMPLATES
}

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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-core/tests/test_student_parts_templates.py -v
```

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/student_parts_templates.py packages/jw-core/tests/test_student_parts_templates.py
git commit -m "feat(jw-core): student_parts_templates (48 slots, 4 kinds × 4 audiences × 3 langs)"
```

---

### Task 3: Agent shell + tests for unknown-kind / placeholder-validation paths

**Files:**
- Create: `packages/jw-agents/src/jw_agents/student_part_helper.py`
- Create: `packages/jw-agents/tests/test_student_part_helper.py`

- [ ] **Step 1: Write the first failing tests (no scripture path)**

```python
# packages/jw-agents/tests/test_student_part_helper.py
"""Tests for jw_agents.student_part_helper."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from jw_agents.student_part_helper import student_part_helper


def _run(coro):
    return asyncio.run(coro)


# ── invariant: 4 findings (opening/body/transition/close) ──────────────


def test_returns_four_findings_per_call() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="esperanza",
        language="es",
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    sections = [f.metadata.get("section") for f in r.findings]
    assert sections == ["opening", "body", "transition", "close"]


def test_unknown_kind_returns_warning_no_findings() -> None:
    r = _run(student_part_helper(
        kind="invented_kind",  # type: ignore[arg-type]
        topic_or_ref="x",
        language="en",
        today=date(2026, 1, 15),
    ))
    assert r.findings == []
    assert any("kind" in w.lower() for w in r.warnings)


def test_metadata_includes_time_target_and_oratory_point() -> None:
    r = _run(student_part_helper(
        kind="starting_conversation",
        topic_or_ref="hope",
        language="en",
        oratory_point=13,
        today=date(2026, 1, 1),
    ))
    assert r.metadata["time_target_seconds"] == 180
    op = r.metadata["oratory_point_applied"]
    assert op["number"] == 13
    assert op["key_phrase"]


# ── scripture resolution ───────────────────────────────────────────────


def test_resolves_bible_reference_when_present() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="Juan 3:16",
        language="es",
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    assert "Juan" in r.metadata.get("resolved_reference", "")
    # The opening finding's text mentions the verse display.
    assert "Juan" in r.findings[0].excerpt or "Juan" in r.findings[0].summary


def test_falls_back_to_topic_when_reference_unparseable() -> None:
    r = _run(student_part_helper(
        kind="starting_conversation",
        topic_or_ref="el sentido del sufrimiento",
        language="es",
        audience="default",
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    assert r.metadata.get("resolved_reference") is None
    # Topic still appears somewhere in the script.
    joined = " ".join(f.excerpt for f in r.findings)
    # Default audience template uses {verse_display} which falls back to topic.
    assert "sufrimiento" in joined.lower() or r.metadata.get("topic") == "el sentido del sufrimiento"


# ── audience fallback ──────────────────────────────────────────────────


def test_unknown_audience_falls_back_to_default() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="Romanos 12:1",
        language="es",
        audience="child",  # type: ignore[arg-type]
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    assert r.metadata["audience_used"] == "default"


# ── oratory point selection ────────────────────────────────────────────


def test_default_oratory_point_picked_from_today_when_none() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="Juan 3:16",
        language="es",
        today=date(2026, 1, 15),  # month 1 → point 1
    ))
    assert r.metadata["oratory_point_applied"]["number"] == 1


def test_oratory_point_not_applicable_emits_warning_but_continues() -> None:
    # Point 38 only applies to starting_conversation/return_visit per the registry.
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="Juan 3:16",
        language="es",
        oratory_point=38,
        today=date(2026, 1, 15),
    ))
    assert any("does not naturally apply" in w or "no aplica" in w for w in r.warnings)
    assert len(r.findings) == 4


# ── language fallback ──────────────────────────────────────────────────


def test_unknown_language_falls_back_to_english_template() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="John 3:16",
        language="fr",
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    assert r.metadata["language"] == "fr"
    assert r.metadata["template_language_used"] == "en"


# ── 'this week' without wol returns warning ────────────────────────────


def test_this_week_without_wol_emits_warning() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="this week",
        language="es",
        oratory_point=1,
        wol=None,
        today=date(2026, 1, 15),
    ))
    assert any("workbook" in w.lower() for w in r.warnings)


# ── citation behaviour ─────────────────────────────────────────────────


def test_finding_has_verse_citation_when_reference_resolves() -> None:
    r = _run(student_part_helper(
        kind="bible_reading",
        topic_or_ref="John 3:16",
        language="en",
        oratory_point=1,
        today=date(2026, 1, 15),
    ))
    assert any(f.citation.url.startswith("https://wol.jw.org/") for f in r.findings)


def test_finding_has_topic_anchor_when_no_reference() -> None:
    r = _run(student_part_helper(
        kind="starting_conversation",
        topic_or_ref="hope amid suffering",
        language="en",
        oratory_point=13,
        today=date(2026, 1, 15),
    ))
    # No verse → at least one finding carries a topic_anchor citation.
    kinds = {f.citation.kind for f in r.findings}
    assert "topic_anchor" in kinds


def test_idempotent_with_same_today() -> None:
    args = dict(
        kind="bible_reading",
        topic_or_ref="John 3:16",
        language="en",
        oratory_point=1,
        today=date(2026, 1, 15),
    )
    a = _run(student_part_helper(**args))  # type: ignore[arg-type]
    b = _run(student_part_helper(**args))  # type: ignore[arg-type]
    assert a.to_dict() == b.to_dict()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-agents/tests/test_student_part_helper.py -v
```

Expected: FAIL — `ModuleNotFoundError: jw_agents.student_part_helper`.

- [ ] **Step 3: Implement the agent**

```python
# packages/jw-agents/src/jw_agents/student_part_helper.py
"""student_part_helper agent — compose a student-part script.

Inputs:
    kind: one of {bible_reading, starting_conversation, return_visit, bible_study}
    topic_or_ref: a Bible reference, a free topic phrase, or "this week"
    language: en/es/pt (others fall back to en for the template body)
    oratory_point: optional 1..50; if None we use point_of_the_month(today)
    audience: default/new/religious/atheist (others fall back to 'default')

Output: AgentResult with exactly 4 findings (opening/body/transition/close)
        and metadata describing what was applied.

No LLM, no network unless topic_or_ref == 'this week' and a WOLClient is
passed in. Idempotent for fixed `today`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from jw_core.clients.wol import WOLClient
from jw_core.data.oratory_points import (
    OratoryPoint,
    brief,
    get_point,
    key_phrase,
    point_of_the_month,
    points_applicable_to,
)
from jw_core.data.student_parts_templates import (
    PartTemplate,
    find_template,
    time_target_seconds_for,
)
from jw_core.parsers.reference import parse_reference

from jw_agents.base import AgentResult, Citation, Finding

_KNOWN_KINDS = {
    "bible_reading",
    "starting_conversation",
    "return_visit",
    "bible_study",
}
_KNOWN_AUDIENCES = {"default", "new", "religious", "atheist"}
_TEMPLATE_LANGS = {"en", "es", "pt"}


async def student_part_helper(
    kind: str,
    topic_or_ref: str,
    *,
    language: str = "en",
    oratory_point: int | None = None,
    audience: str = "default",
    wol: WOLClient | None = None,
    today: date | None = None,
) -> AgentResult:
    """Compose a 4-section script for a student assignment."""
    result = AgentResult(query=topic_or_ref, agent_name="student_part_helper")
    today = today or date.today()
    result.metadata["language"] = language
    result.metadata["kind"] = kind
    result.metadata["audience"] = audience

    if kind not in _KNOWN_KINDS:
        result.warnings.append(f"Unknown kind {kind!r}; expected one of {sorted(_KNOWN_KINDS)}")
        return result

    # 1. Resolve oratory point.
    point = _resolve_oratory_point(oratory_point, today, kind, result)

    # 2. Resolve audience (fall back if unknown).
    audience_used = audience if audience in _KNOWN_AUDIENCES else "default"
    if audience_used != audience:
        result.warnings.append(
            f"Audience {audience!r} unsupported; using 'default'."
        )
    result.metadata["audience_used"] = audience_used

    # 3. Resolve scripture / topic / 'this week'.
    verse_display, verse_url, topic_label = await _resolve_topic(
        topic_or_ref, language, kind, wol, today, result,
    )

    # 4. Pick template.
    tpl = find_template(kind, audience_used, language)
    template_lang_used = tpl.language
    result.metadata["template_language_used"] = template_lang_used

    # 5. Build placeholders.
    placeholders = _build_placeholders(
        verse_display=verse_display,
        topic=topic_label,
        point=point,
        language=language,
        kind=kind,
        result=result,
    )

    # 6. Render the 4 sections into Findings.
    for section_name, raw in (
        ("opening", tpl.opening),
        ("body", tpl.body),
        ("transition", tpl.transition),
        ("close", tpl.close),
    ):
        text = _safe_format(raw, placeholders)
        citation = (
            Citation(url=verse_url, title=verse_display, kind="verse")
            if verse_url
            else Citation(url="", title=topic_label or topic_or_ref, kind="topic_anchor")
        )
        result.findings.append(
            Finding(
                summary=f"{kind} · {section_name}",
                excerpt=text,
                citation=citation,
                metadata={
                    "source": "student_part_template",
                    "section": section_name,
                },
            )
        )

    # 7. Final metadata.
    result.metadata["time_target_seconds"] = time_target_seconds_for(kind)
    result.metadata["oratory_point_applied"] = {
        "number": point.number,
        "key_phrase": key_phrase(point, language),
        "category": point.category,
    }
    if topic_label:
        result.metadata["topic"] = topic_label

    return result


# ── helpers ─────────────────────────────────────────────────────────────


def _resolve_oratory_point(
    explicit: int | None,
    today: date,
    kind: str,
    result: AgentResult,
) -> OratoryPoint:
    if explicit is not None:
        try:
            point = get_point(explicit)
        except ValueError as exc:
            result.warnings.append(str(exc))
            point = point_of_the_month(today)
    else:
        point = point_of_the_month(today)

    if kind not in point.applies_to:
        applicable = ", ".join(str(p.number) for p in points_applicable_to(kind)[:5])
        result.warnings.append(
            f"Oratory point {point.number} does not naturally apply to {kind!r}; "
            f"consider one of: {applicable}…"
        )
    return point


async def _resolve_topic(
    topic_or_ref: str,
    language: str,
    kind: str,
    wol: WOLClient | None,
    today: date,
    result: AgentResult,
) -> tuple[str, str, str]:
    """Return (verse_display, verse_url, topic_label).

    - If `topic_or_ref` parses as a reference: returns the reference's display
      and WOL URL; topic_label is "".
    - If it is exactly 'this week' (case-insensitive): tries the workbook
      scraper; on success returns the matching assignment's reference; on
      failure or no `wol`, returns ("", "", topic_or_ref) with a warning.
    - Otherwise: ("", "", topic_or_ref).
    """
    if topic_or_ref.strip().lower() == "this week":
        if wol is None:
            result.warnings.append(
                "'this week' requires a WOLClient (workbook scraper) — using free topic instead."
            )
            return ("", "", topic_or_ref)
        # Lazy import to keep workbook off the import path of every consumer.
        try:
            from jw_agents.workbook_helper import workbook_helper  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"workbook_helper unavailable: {exc!r}")
            return ("", "", topic_or_ref)
        try:
            wb = await workbook_helper(today.isoformat(), language=language, wol=wol)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"workbook fetch failed: {exc!r}")
            return ("", "", topic_or_ref)
        # Find the first assignment that matches `kind` in the workbook output.
        for f in wb.findings:
            if f.metadata.get("kind") == kind and f.metadata.get("reference"):
                ref = parse_reference(str(f.metadata["reference"]))
                if ref is not None:
                    return (ref.display(), ref.wol_url(lang=language), "")
        result.warnings.append(
            f"workbook did not contain an assignment of kind={kind!r} for this week."
        )
        return ("", "", topic_or_ref)

    ref = parse_reference(topic_or_ref)
    if ref is not None:
        result.metadata["resolved_reference"] = ref.display()
        return (ref.display(), ref.wol_url(lang=language), "")
    return ("", "", topic_or_ref)


def _build_placeholders(
    *,
    verse_display: str,
    topic: str,
    point: OratoryPoint,
    language: str,
    kind: str,
    result: AgentResult,
) -> dict[str, str]:
    # `verse_display` falls back to `topic` so templates always render.
    display = verse_display or topic or "—"
    return {
        "verse_display": display,
        "verse_text": "",          # filled only when wol fetch was done; v1: empty.
        "topic": topic or "—",
        "oratory_phrase": key_phrase(point, language),
        "oratory_brief": brief(point, language),
        # return_visit-specific
        "prior_seed": result.metadata.get("prior_seed", "your last comment"),
        "next_visit_hook": result.metadata.get("next_visit_hook", "the next thought"),
        # bible_study-specific
        "paragraph": result.metadata.get("paragraph", "1"),
        "next_paragraph": result.metadata.get("next_paragraph", "2"),
        "focus": result.metadata.get("focus", topic or "the lesson"),
    }


def _safe_format(template: str, placeholders: dict[str, str]) -> str:
    """str.format that tolerates missing keys by leaving the literal placeholder."""

    class _Defaulter(dict):
        def __missing__(self, key: str) -> str:  # noqa: D401
            return "{" + key + "}"

    return template.format_map(_Defaulter(placeholders))


# Re-export for convenience.
__all__ = ["student_part_helper"]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-agents/tests/test_student_part_helper.py -v
```

Expected: 13 passed.

- [ ] **Step 5: Wire export**

Edit `packages/jw-agents/src/jw_agents/__init__.py` to add:

```python
from jw_agents.student_part_helper import student_part_helper

__all__ = [*__all__, "student_part_helper"]   # extend whatever is currently there
```

(If `__all__` doesn't exist, just append the import.)

- [ ] **Step 6: Commit**

```bash
git add packages/jw-agents/src/jw_agents/student_part_helper.py \
        packages/jw-agents/src/jw_agents/__init__.py \
        packages/jw-agents/tests/test_student_part_helper.py
git commit -m "feat(jw-agents): student_part_helper agent (4 kinds × 4 audiences × 3 langs)"
```

---

### Task 4: Verify reference resolution path passes for all three languages

**Files:**
- Modify: `packages/jw-agents/tests/test_student_part_helper.py` (extend)

- [ ] **Step 1: Append the multilingual test**

```python
def test_resolves_reference_in_en_es_pt() -> None:
    for ref_in, lang in [
        ("John 3:16", "en"),
        ("Juan 3:16", "es"),
        ("João 3:16", "pt"),
    ]:
        r = _run(student_part_helper(
            kind="bible_reading",
            topic_or_ref=ref_in,
            language=lang,
            oratory_point=1,
            today=date(2026, 1, 15),
        ))
        assert "3:16" in r.metadata["resolved_reference"], (ref_in, lang)
        assert r.findings[0].citation.url.startswith("https://wol.jw.org/")
```

- [ ] **Step 2: Run test**

```bash
uv run pytest packages/jw-agents/tests/test_student_part_helper.py -v
```

Expected: 14 passed (the original 13 + the new one).

- [ ] **Step 3: Commit**

```bash
git add packages/jw-agents/tests/test_student_part_helper.py
git commit -m "test(jw-agents): multilingual scripture resolution coverage for student_part_helper"
```

---

### Task 5: `jw student` CLI command

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/student.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py` (register command)

- [ ] **Step 1: Inspect existing CLI registration pattern**

Run: `cat packages/jw-cli/src/jw_cli/main.py | head -60`. Observe how other commands (`workbook`, `verse`, `chapter`) are registered — typically `app.command(name=...)(func)`.

- [ ] **Step 2: Implement the command module**

```python
# packages/jw-cli/src/jw_cli/commands/student.py
"""`jw student <kind> <topic_or_ref>` — compose a 4-section script for a
student assignment in Life and Ministry.

Examples:
    jw student bible_reading "Juan 3:16" --lang es
    jw student conversation  "creation" --audience atheist --lang en
    jw student revisit       "John 3:16" --lang en
    jw student study         "esperanza de resurrección" --audience new --lang es
"""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jw_agents import student_part_helper

console = Console()


_KIND_ALIAS = {
    "reading": "bible_reading",
    "bible_reading": "bible_reading",
    "conversation": "starting_conversation",
    "conv": "starting_conversation",
    "starting_conversation": "starting_conversation",
    "revisit": "return_visit",
    "return_visit": "return_visit",
    "study": "bible_study",
    "bible_study": "bible_study",
}


def student_command(
    kind: str = typer.Argument(..., help="bible_reading | conversation | revisit | study"),
    topic_or_ref: str = typer.Argument(..., help="Bible reference, topic, or 'this week'"),
    language: str = typer.Option("en", "--lang", "-l", help="ISO language (en/es/pt)"),
    audience: str = typer.Option("default", "--audience", "-a",
                                 help="default | new | religious | atheist"),
    point: int | None = typer.Option(None, "--point", "-p",
                                     help="Override oratory point 1..50 (default: auto by month)"),
    as_json: bool = typer.Option(False, "--json", help="Emit JSON instead of pretty Rich output"),
) -> None:
    """Compose a student-part script."""

    normalized_kind = _KIND_ALIAS.get(kind, kind)

    result = asyncio.run(
        student_part_helper(
            kind=normalized_kind,
            topic_or_ref=topic_or_ref,
            language=language,
            oratory_point=point,
            audience=audience,
        )
    )

    if as_json:
        console.print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    op = result.metadata.get("oratory_point_applied", {})
    header = (
        f"[bold]{normalized_kind}[/bold] · "
        f"audience=[cyan]{result.metadata.get('audience_used', '?')}[/cyan] · "
        f"target=[cyan]{result.metadata.get('time_target_seconds', '?')}s[/cyan] · "
        f"point=[cyan]{op.get('number', '?')} — {op.get('key_phrase', '?')}[/cyan]"
    )
    console.print(Panel(header, title="jw student", border_style="cyan"))

    if result.warnings:
        for w in result.warnings:
            console.print(f"[yellow]⚠[/yellow] {w}")

    table = Table(title="Script", show_lines=True)
    table.add_column("Section", style="bold")
    table.add_column("Text")
    for f in result.findings:
        table.add_row(f.metadata.get("section", "?"), f.excerpt)
    console.print(table)

    ref = result.metadata.get("resolved_reference")
    if ref:
        url = result.findings[0].citation.url if result.findings else ""
        console.print(f"[dim]Scripture:[/dim] {ref}  [link={url}]{url}[/link]")
```

- [ ] **Step 3: Register the command**

Edit `packages/jw-cli/src/jw_cli/main.py` (or `commands/__init__.py` depending on existing convention) to add:

```python
from jw_cli.commands.student import student_command
app.command(name="student")(student_command)
```

- [ ] **Step 4: Smoke-test**

```bash
uv run jw student bible_reading "Juan 3:16" --lang es --point 1
uv run jw student conversation "hope" --lang en --audience atheist
uv run jw student revisit "John 3:16" --lang en --point 13
uv run jw student study "esperanza" --lang es --audience new
```

Each should print a Rich panel + a 4-row table. Exit code 0.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/student.py packages/jw-cli/src/jw_cli/main.py
git commit -m "feat(jw-cli): jw student command for student_part_helper"
```

---

### Task 6: MCP tool `student_part_help`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`

- [ ] **Step 1: Identify the registration pattern**

Run `grep -n "@mcp.tool" packages/jw-mcp/src/jw_mcp/server.py | head -10` and pick an existing pattern (e.g. `meeting_helper`).

- [ ] **Step 2: Add the tool**

```python
# Inside packages/jw-mcp/src/jw_mcp/server.py — add near the other student/meeting tools.

from jw_agents import student_part_helper as _student_part_helper


@mcp.tool()
async def student_part_help(
    kind: str,
    topic_or_ref: str,
    language: str = "en",
    oratory_point: int | None = None,
    audience: str = "default",
) -> dict:
    """Compose a 4-section script for a Life-and-Ministry student assignment.

    `kind` is one of: bible_reading | starting_conversation | return_visit | bible_study.
    `topic_or_ref` may be a Bible reference, a free topic, or 'this week'.
    Returns the structured AgentResult serialized as dict — opening / body /
    transition / close findings plus metadata.time_target_seconds and
    metadata.oratory_point_applied.
    """
    result = await _student_part_helper(
        kind=kind,
        topic_or_ref=topic_or_ref,
        language=language,
        oratory_point=oratory_point,
        audience=audience,
    )
    return result.to_dict()
```

- [ ] **Step 3: Smoke-test via the server stub**

```bash
uv run python -c "
import asyncio
from jw_agents import student_part_helper
r = asyncio.run(student_part_helper(kind='bible_reading', topic_or_ref='Juan 3:16', language='es', oratory_point=1))
import json; print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False)[:500])
"
```

Expected: JSON with 4 findings.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py
git commit -m "feat(jw-mcp): expose student_part_help tool"
```

---

### Task 7: Golden case L1 — `bible_reading` (Spanish)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_reading_es.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_reading_es.yaml
id: l1_student_part_bible_reading_es
agent: student_part_helper
layer: l1
input:
  kind: bible_reading
  topic_or_ref: "Romanos 12:1-2"
  language: es
  audience: default
  oratory_point: 1
expected:
  min_findings: 4
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "supuestamente"
    - "tal vez"
metadata:
  topic: student_parts.bible_reading.es
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Verify it loads**

```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_case_file
c = load_case_file(Path('packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_reading_es.yaml'))
print(c.id, c.layer)
"
```

Expected: `l1_student_part_bible_reading_es l1`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_reading_es.yaml
git commit -m "test(jw-eval): L1 golden case for student_part_helper bible_reading (es)"
```

---

### Task 8: Golden case L1 — `starting_conversation` (English)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/student_part_conversation_en.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
id: l1_student_part_conversation_en
agent: student_part_helper
layer: l1
input:
  kind: starting_conversation
  topic_or_ref: "hope amid suffering"
  language: en
  audience: atheist
  oratory_point: 13
expected:
  min_findings: 4
  forbidden_keywords_in_findings:
    - "supposedly"
    - "maybe"
metadata:
  topic: student_parts.conversation.en
  added_at: 2026-05-30
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/student_part_conversation_en.yaml
git commit -m "test(jw-eval): L1 golden case for student_part_helper starting_conversation (en)"
```

---

### Task 9: Golden case L1 — `return_visit` (Portuguese)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/student_part_return_visit_pt.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
id: l1_student_part_return_visit_pt
agent: student_part_helper
layer: l1
input:
  kind: return_visit
  topic_or_ref: "João 3:16"
  language: pt
  audience: religious
  oratory_point: 27
expected:
  min_findings: 4
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "supostamente"
    - "talvez"
metadata:
  topic: student_parts.return_visit.pt
  added_at: 2026-05-30
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/student_part_return_visit_pt.yaml
git commit -m "test(jw-eval): L1 golden case for student_part_helper return_visit (pt)"
```

---

### Task 10: Golden case L1 — `bible_study` (Spanish)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_study_es.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
id: l1_student_part_bible_study_es
agent: student_part_helper
layer: l1
input:
  kind: bible_study
  topic_or_ref: "Romanos 6:23"
  language: es
  audience: new
  oratory_point: 20
expected:
  min_findings: 4
  must_have_citation: true
metadata:
  topic: student_parts.bible_study.es
  added_at: 2026-05-30
```

- [ ] **Step 2: Verify all 4 cases load**

```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_cases
cases = load_cases(Path('packages/jw-eval/fixtures/golden_qa'), layers=['l1'])
student_cases = [c for c in cases if c.agent == 'student_part_helper']
print(f'student_part_helper cases: {len(student_cases)}')
assert len(student_cases) == 4
"
```

Expected: `student_part_helper cases: 4`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/student_part_bible_study_es.yaml
git commit -m "test(jw-eval): L1 golden case for student_part_helper bible_study (es)"
```

---

### Task 11: Wire `student_part_helper` into the jw-eval agent dispatcher

**Files:**
- Modify: whichever file in `packages/jw-eval/src/jw_eval/` maps agent names to callables (likely `suite.py` or `layers/structural.py`).

- [ ] **Step 1: Locate the dispatcher**

Run: `grep -rn "agent_name\|_AGENTS\b\|agent_callable\|verse_explainer" packages/jw-eval/src --include='*.py'`.

- [ ] **Step 2: Register the agent in the dispatcher**

Inside the agent-callable factory (whatever its current name) add a branch for `student_part_helper`. Pseudocode:

```python
elif case.agent == "student_part_helper":
    from jw_agents import student_part_helper

    async def _run(input_dict):
        return await student_part_helper(
            kind=input_dict["kind"],
            topic_or_ref=input_dict["topic_or_ref"],
            language=input_dict.get("language", "en"),
            oratory_point=input_dict.get("oratory_point"),
            audience=input_dict.get("audience", "default"),
        )
    # then sync-wrap if needed:
    return lambda d: asyncio.run(_run(d))
```

- [ ] **Step 3: Run the 4 new L1 cases**

```bash
uv run jw eval --layer 1 --filter agent=student_part_helper
```

Expected: 4 pass, 0 fail.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-eval/src/jw_eval
git commit -m "feat(jw-eval): dispatch student_part_helper in L1 runner"
```

---

### Task 12: Author guide `docs/guias/partes-del-estudiante.md`

**Files:**
- Create: `docs/guias/partes-del-estudiante.md`

- [ ] **Step 1: Write the guide**

```markdown
# Asistente de partes del estudiante (Vida y Ministerio)

Genera un guion estructurado de **4 secciones** (apertura / cuerpo / transición / cierre) para cualquiera de las cuatro asignaciones típicas del estudiante en la reunión de Vida y Ministerio, ajustado al **punto de oratoria del mes**.

## Tipos de asignación

| `kind` | Tiempo objetivo | Cuándo |
|---|---|---|
| `bible_reading` | 4 min | Lectura de la Biblia |
| `starting_conversation` | 3 min | Empezar conversación |
| `return_visit` | 4 min | Revisita |
| `bible_study` | 5 min | Demostración de estudio |

## CLI

```bash
# Lectura de la Biblia, español, punto explícito
jw student bible_reading "Romanos 12:1-2" --lang es --point 1

# Empezar conversación, ateo, punto auto por mes
jw student conversation "el sentido del sufrimiento" --audience atheist --lang es

# Revisita, religioso
jw student revisit "Juan 3:16" --audience religious --lang es

# Estudio bíblico, persona nueva
jw student study "esperanza de resurrección" --audience new --lang es

# JSON para canalizar a otro proceso
jw student bible_reading "Juan 3:16" --lang es --json
```

## Audiencias

- `default` — neutral.
- `new` — alguien que no conoce la Biblia.
- `religious` — alguien con trasfondo religioso.
- `atheist` — alguien sin compromiso religioso.

Si pasa una audiencia desconocida, el agente cae a `default` y deja un warning.

## Punto de oratoria

El folleto **Mejore su predicación** (`th`) tiene ~50 puntos. Cada mes el toolkit asume un punto activo (1 en enero, 5 en febrero, 9 en marzo, …). Override con `--point N`.

Lista completa en `jw_core.data.oratory_points.ORATORY_POINTS`.

## Modo "this week"

Cuando `topic_or_ref` es exactamente `this week`, el agente delega en el scraper del workbook (Fase 11) para localizar la asignación de la semana actual. Requiere red — si no hay `WOLClient` o el scraping falla, el guion se compone con tema libre y un warning.

## MCP

Herramienta `student_part_help(kind, topic_or_ref, language="en", oratory_point=None, audience="default")` disponible en `jw-mcp`. Devuelve `AgentResult.to_dict()`.

## Lo que el agente NO hace

- No reescribe la prosa: produce **plantillas** rellenadas; el LLM downstream redacta.
- No respeta automáticamente el tiempo: `time_target_seconds` es informativo.
- No registra quién recibió qué asignación.
- No reproduce la letra completa del libro `th`: usa paráfrasis ≤300 chars.
```

- [ ] **Step 2: Commit**

```bash
git add docs/guias/partes-del-estudiante.md
git commit -m "docs(guias): student_part_helper user guide"
```

---

### Task 13: Update `ROADMAP.md` and `VISION_AUDIT.md`

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/README.md`

- [ ] **Step 1: ROADMAP entry**

In `docs/ROADMAP.md`, find the section listing Fases 22-32 and update Fase 26:

```markdown
### Fase 26 — Asistente de partes del estudiante V&M ✅

- Estado: completado (YYYY-MM-DD).
- 4 tipos de asignación: bible_reading, starting_conversation, return_visit, bible_study.
- 4 audiencias × 3 idiomas → 48 plantillas en `jw_core.data.student_parts_templates`.
- Registro de 50 puntos de oratoria en `jw_core.data.oratory_points` (paráfrasis ≤300 chars).
- Agente `jw_agents.student_part_helper` · CLI `jw student` · tool MCP `student_part_help`.
- 4 golden cases L1 (uno por kind) en `packages/jw-eval/fixtures/golden_qa/l1`.
- Guía: [`docs/guias/partes-del-estudiante.md`](guias/partes-del-estudiante.md).
```

- [ ] **Step 2: VISION_AUDIT entry**

In `docs/VISION_AUDIT.md`, mark VISION #2 as completed and reference Fase 26.

- [ ] **Step 3: README link**

Add a bullet to the user guides section of `docs/README.md`:

```markdown
- [Partes del estudiante](guias/partes-del-estudiante.md) — guion 4-sección para lectura, conversación, revisita y estudio.
```

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md docs/VISION_AUDIT.md docs/README.md
git commit -m "docs: mark Fase 26 (student parts) complete in ROADMAP and VISION_AUDIT"
```

---

### Task 14: Full regression + CI sanity

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest packages/jw-core/tests packages/jw-agents/tests packages/jw-eval/tests -x -q
```

Expected: 0 failures. New tests added: 11 (oratory_points) + 9 (templates) + 14 (agent) = **34 new tests**.

- [ ] **Step 2: Run jw-eval L1 over all student cases**

```bash
uv run jw eval --layer 1 --filter agent=student_part_helper
```

Expected: 4 pass / 0 fail.

- [ ] **Step 3: Manual CLI smoke**

```bash
uv run jw student bible_reading "Juan 3:16" --lang es
uv run jw student conversation "hope" --lang en --audience atheist
uv run jw student revisit "João 3:16" --lang pt --point 27
uv run jw student study "resurrección" --lang es --audience new
```

Each shows a Rich panel + 4-row table.

- [ ] **Step 4: MCP smoke**

```bash
uv run python -c "
import asyncio, json
from jw_agents import student_part_helper
r = asyncio.run(student_part_helper(kind='bible_reading', topic_or_ref='Juan 3:16', language='es', oratory_point=1))
print('findings:', len(r.findings))
print('time_target:', r.metadata['time_target_seconds'])
print('point:', r.metadata['oratory_point_applied'])
"
```

- [ ] **Step 5: Push and open PR**

```bash
git push -u origin feature/fase-26-student-parts
gh pr create --title "feat: Fase 26 — student_part_helper" \
             --body "Spec: docs/superpowers/specs/2026-05-30-fase-26-student-parts-design.md"
```

---

## Self-review

| Check | Status |
|---|---|
| Spec referenced at top of plan? | yes |
| TDD order (test first, run-to-fail, implement, run-to-pass)? | yes — every task that creates code uses it |
| File map exhaustive? | yes — every new file + every modify listed |
| Code samples are full enough to paste verbatim? | yes — oratory_points has all 50 entries inline; templates has all 48 slots inline |
| No LLM in critical path? | confirmed — agent is pure template + parse_reference |
| No network in tests? | confirmed — `wol=None`; "this week" path tested only for warning emission |
| `today` is injectable? | yes — every test fixes `today=date(2026, 1, 15)` |
| Copyright safety on `th` content? | enforced by test_brief_paraphrases_under_300_chars + paraphrase-only policy |
| 4 golden cases (one per kind)? | yes — tasks 7-10 |
| New tool documented in guide? | yes — task 12 |
| Audit updated? | yes — task 13 |

## Execution choice

Recommended path: **superpowers:executing-plans** (linear). The 14 tasks have a natural dependency chain (data → agent → CLI/MCP → fixtures → docs); parallelizing yields little because each later task imports what the earlier one wrote.

Alternative: **superpowers:subagent-driven-development** — possible to delegate Tasks 7-10 (golden case YAMLs) to a parallel sub-agent after Task 6, but the savings are minimal.

Stop conditions:
- If Task 1 fails the length tests on the paraphrases → tighten the offending entry, never increase the 300-char limit.
- If Task 3 tests for `parse_reference` ordering fail on a particular language → check `parsers/reference.py`; this is the documented edge case for accent-collisions in the spec.
- If `jw eval --filter agent=student_part_helper` returns 0 cases → verify the dispatcher branch added in Task 11 actually matches the agent string `student_part_helper` exactly.
