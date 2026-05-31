# Fase 32 — `life_topics` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea-a-tarea. Pasos con checkbox (`- [ ]`).

**Goal:** Construir `life_topics`, un agente estrictamente informativo sobre temas sensibles y generales de la vida, que jamás sustituye la consejería pastoral. Devuelve material publicado + disclaimer + redirect a ancianos cuando corresponde.

**Architecture:** Datos en `jw-core` (registry + disclaimers), agente en `jw-agents`, comando en `jw-cli`, tool en `jw-mcp`, golden cases en `jw-eval`.

**Tech Stack:** Python 3.13 · dataclasses (registry) · `TopicIndexClient` (Fase 4) · `CDNClient` (Fase 1) · `WOLClient` · `parse_article` · pytest async · Typer + Rich.

**Spec:** [`docs/superpowers/specs/2026-05-30-fase-32-life-topics-design.md`](../specs/2026-05-30-fase-32-life-topics-design.md).

---

## File map

Creates:
- `packages/jw-core/src/jw_core/data/life_topics.py`
- `packages/jw-core/src/jw_core/data/life_disclaimers.py`
- `packages/jw-core/tests/test_life_topics_data.py`
- `packages/jw-core/tests/test_life_disclaimers.py`
- `packages/jw-agents/src/jw_agents/life_topics.py`
- `packages/jw-agents/tests/test_life_topics.py`
- `packages/jw-cli/src/jw_cli/commands/life.py`
- `packages/jw-cli/tests/test_life_cmd.py`
- `packages/jw-mcp/tests/test_life_topic_tool.py`
- `packages/jw-eval/fixtures/golden_qa/l1/life_topics_anxiety_es.yaml`
- `packages/jw-eval/fixtures/golden_qa/l1/life_topics_parenting_en.yaml`
- `packages/jw-eval/fixtures/golden_qa/l3/life_topics_grief_en.yaml`
- `packages/jw-eval/fixtures/golden_qa/l3/life_topics_doubts_es.yaml`
- `docs/guias/temas-de-vida.md`

Modifies:
- `packages/jw-cli/src/jw_cli/main.py` — registra `app.command(name="life")`.
- `packages/jw-mcp/src/jw_mcp/server.py` — registra tool `life_topic_info`.
- `packages/jw-eval/src/jw_eval/cli.py` — añade `life_topics` al `default_agent_registry()`.
- `docs/README.md` — link al nuevo guide.
- `docs/ROADMAP.md` — bloque Fase 32.
- `docs/VISION_AUDIT.md` — fila Fase 32.

---

### Task 1: Datos — registry de temas de vida

**Files:**
- Create: `packages/jw-core/src/jw_core/data/life_topics.py`
- Create: `packages/jw-core/tests/test_life_topics_data.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_life_topics_data.py
"""Tests for jw_core.data.life_topics — registry + alias resolution."""

from __future__ import annotations

import pytest

from jw_core.data.life_topics import REGISTRY, LifeTopic, resolve_topic


def test_registry_has_expected_topics() -> None:
    ids = {t.topic_id for t in REGISTRY}
    assert {
        "anxiety",
        "grief",
        "marriage_conflict",
        "depression_signs",
        "addictions",
        "doubts_in_faith",
        "parenting",
        "loneliness",
        "conflict_with_brother",
    } <= ids


def test_every_topic_has_three_languages() -> None:
    for t in REGISTRY:
        assert {"en", "es", "pt"} <= set(t.labels.keys()), f"{t.topic_id} missing labels"
        assert {"en", "es", "pt"} <= set(t.aliases.keys()), f"{t.topic_id} missing aliases"


def test_family_is_sensitive_or_general() -> None:
    for t in REGISTRY:
        assert t.family in {"sensitive", "general"}


def test_sensitive_set_matches_spec() -> None:
    sensitive = {t.topic_id for t in REGISTRY if t.family == "sensitive"}
    assert sensitive == {
        "anxiety",
        "grief",
        "marriage_conflict",
        "depression_signs",
        "addictions",
        "doubts_in_faith",
    }


def test_resolve_topic_by_canonical_label_es() -> None:
    topic = resolve_topic("Ansiedad", language="es")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_by_alias_en() -> None:
    topic = resolve_topic("worry", language="en")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_accent_insensitive_pt() -> None:
    topic = resolve_topic("solidao", language="pt")
    assert topic is not None
    assert topic.topic_id == "loneliness"


def test_resolve_topic_cross_language_fallback() -> None:
    # User typed Spanish word but said language=en — still resolves.
    topic = resolve_topic("ansiedad", language="en")
    assert topic is not None
    assert topic.topic_id == "anxiety"


def test_resolve_topic_unknown_returns_none() -> None:
    assert resolve_topic("qwertypotato", language="en") is None


def test_each_topic_has_at_least_one_anchor_and_query() -> None:
    for t in REGISTRY:
        assert t.topic_anchors, f"{t.topic_id} has no topic_anchors"
        assert t.search_query, f"{t.topic_id} has empty search_query"


def test_life_topic_dataclass_is_frozen() -> None:
    t = REGISTRY[0]
    with pytest.raises(Exception):  # FrozenInstanceError
        t.topic_id = "x"  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-core/tests/test_life_topics_data.py -v
```
Expected: FAIL — `jw_core.data.life_topics` does not exist.

- [ ] **Step 3: Implement the registry**

```python
# packages/jw-core/src/jw_core/data/life_topics.py
"""Vocabulario controlado de temas de vida para el agente `life_topics`.

Tres familias de datos puros, sin red ni LLM:

  LifeTopic           dataclass frozen
  REGISTRY            list[LifeTopic] — 9 temas iniciales
  resolve_topic(...)  alias-aware lookup en es/en/pt + fallback cross-lang

Esta tabla es deliberadamente conservadora. Cada tema añadido debe
considerarse caso por caso — los temas marcados `family='sensitive'`
disparan automáticamente el redirect a ancianos en el agente, así que
añadir uno "general" cuando debería ser sensible es un riesgo pastoral.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Literal

LifeTopicFamily = Literal["sensitive", "general"]


@dataclass(frozen=True)
class LifeTopic:
    topic_id: str
    family: LifeTopicFamily
    labels: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, list[str]] = field(default_factory=dict)
    topic_anchors: list[str] = field(default_factory=list)
    search_query: str = ""


def _strip(s: str) -> str:
    """Lowercase + strip accents, for fuzzy matching."""
    nf = unicodedata.normalize("NFD", s)
    return "".join(c for c in nf if unicodedata.category(c) != "Mn").lower().strip()


REGISTRY: list[LifeTopic] = [
    LifeTopic(
        topic_id="anxiety",
        family="sensitive",
        labels={"en": "Anxiety", "es": "Ansiedad", "pt": "Ansiedade"},
        aliases={
            "en": ["anxiety", "worry", "stress", "fear", "anxious"],
            "es": ["ansiedad", "preocupacion", "estres", "miedo", "nervios"],
            "pt": ["ansiedade", "preocupacao", "estresse", "medo"],
        },
        topic_anchors=["Anxiety", "Worry"],
        search_query="anxiety overcome",
    ),
    LifeTopic(
        topic_id="grief",
        family="sensitive",
        labels={"en": "Grief", "es": "Duelo", "pt": "Luto"},
        aliases={
            "en": ["grief", "loss", "death of a loved one", "mourning", "bereavement"],
            "es": ["duelo", "perdida", "muerte de un ser querido", "luto"],
            "pt": ["luto", "perda", "morte de um ente querido"],
        },
        topic_anchors=["Death", "Resurrection", "Comfort"],
        search_query="death of a loved one comfort",
    ),
    LifeTopic(
        topic_id="marriage_conflict",
        family="sensitive",
        labels={
            "en": "Marriage conflict",
            "es": "Conflicto matrimonial",
            "pt": "Conflito conjugal",
        },
        aliases={
            "en": ["marriage conflict", "arguing with spouse", "marriage problem"],
            "es": ["conflicto matrimonial", "problemas de pareja", "discusiones con conyuge"],
            "pt": ["conflito conjugal", "problemas no casamento"],
        },
        topic_anchors=["Marriage", "Husband", "Wife"],
        search_query="marriage problems peace",
    ),
    LifeTopic(
        topic_id="depression_signs",
        family="sensitive",
        labels={"en": "Depression", "es": "Depresión", "pt": "Depressão"},
        aliases={
            "en": ["depression", "sadness", "hopelessness", "down"],
            "es": ["depresion", "tristeza profunda", "desesperanza"],
            "pt": ["depressao", "tristeza profunda", "desesperanca"],
        },
        topic_anchors=["Depression", "Discouragement"],
        search_query="depression discouragement encouragement",
    ),
    LifeTopic(
        topic_id="addictions",
        family="sensitive",
        labels={"en": "Addictions", "es": "Adicciones", "pt": "Vícios"},
        aliases={
            "en": ["addiction", "addictions", "habit", "smoking", "alcohol", "drugs"],
            "es": ["adicciones", "adiccion", "vicio", "tabaco", "alcohol", "drogas"],
            "pt": ["vicios", "vicio", "habito", "fumo", "alcool", "drogas"],
        },
        topic_anchors=["Habits", "Self-Control"],
        search_query="overcoming bad habits",
    ),
    LifeTopic(
        topic_id="doubts_in_faith",
        family="sensitive",
        labels={
            "en": "Doubts in faith",
            "es": "Dudas en la fe",
            "pt": "Dúvidas na fé",
        },
        aliases={
            "en": ["doubt", "doubts", "doubting", "weak faith", "lost faith"],
            "es": ["dudas", "dudo", "fe debil", "perdi la fe"],
            "pt": ["duvidas", "duvido", "fe fraca", "perdi a fe"],
        },
        topic_anchors=["Faith", "Trust in God"],
        search_query="strengthen your faith",
    ),
    LifeTopic(
        topic_id="parenting",
        family="general",
        labels={
            "en": "Parenting",
            "es": "Crianza de los hijos",
            "pt": "Criação dos filhos",
        },
        aliases={
            "en": ["parenting", "raising children", "discipline kids", "teen"],
            "es": ["crianza", "educar a los hijos", "disciplina", "adolescentes"],
            "pt": ["criacao", "educar os filhos", "disciplina", "adolescentes"],
        },
        topic_anchors=["Children", "Family"],
        search_query="raising children family",
    ),
    LifeTopic(
        topic_id="loneliness",
        family="general",
        labels={"en": "Loneliness", "es": "Soledad", "pt": "Solidão"},
        aliases={
            "en": ["loneliness", "lonely", "alone", "isolation"],
            "es": ["soledad", "solo", "sola", "aislamiento"],
            "pt": ["solidao", "sozinho", "isolamento"],
        },
        topic_anchors=["Friendship", "Loneliness"],
        search_query="loneliness friendship",
    ),
    LifeTopic(
        topic_id="conflict_with_brother",
        family="general",
        labels={
            "en": "Conflict with a brother",
            "es": "Conflicto con un hermano",
            "pt": "Conflito com um irmão",
        },
        aliases={
            "en": ["conflict with a brother", "argument with brother", "offended by brother"],
            "es": ["conflicto con un hermano", "ofensa de un hermano", "discusion con hermano"],
            "pt": ["conflito com um irmao", "ofensa de um irmao"],
        },
        topic_anchors=["Forgiveness", "Peace"],
        search_query="forgive a brother reconcile",
    ),
]


def resolve_topic(query: str, language: str = "en") -> LifeTopic | None:
    """Map a free-form `query` to a canonical LifeTopic, alias-aware.

    Order:
      1. Match against `aliases[language]` (accent-insensitive, lowercased).
      2. Match against `labels[language]`.
      3. Cross-language fallback: try every alias list.

    Returns `None` if nothing matches — the agent then emits a generic
    disclaimer and no redirect (we don't know whether the topic is
    sensitive, so we don't presume).
    """
    normalized = _strip(query)
    if not normalized:
        return None

    for topic in REGISTRY:
        for alias in topic.aliases.get(language, []):
            if _strip(alias) == normalized:
                return topic
        label = topic.labels.get(language, "")
        if label and _strip(label) == normalized:
            return topic

    # Cross-language fallback.
    for topic in REGISTRY:
        for lang_aliases in topic.aliases.values():
            for alias in lang_aliases:
                if _strip(alias) == normalized:
                    return topic
        for label in topic.labels.values():
            if _strip(label) == normalized:
                return topic

    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-core/tests/test_life_topics_data.py -v
```
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/life_topics.py packages/jw-core/tests/test_life_topics_data.py
git commit -m "feat(jw-core): life topics registry (9 topics, en/es/pt, sensitive vs general)"
```

---

### Task 2: Datos — disclaimer + elders redirect text

**Files:**
- Create: `packages/jw-core/src/jw_core/data/life_disclaimers.py`
- Create: `packages/jw-core/tests/test_life_disclaimers.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-core/tests/test_life_disclaimers.py
from __future__ import annotations

import pytest

from jw_core.data.life_disclaimers import (
    DISCLAIMERS,
    ELDERS_REDIRECTS,
    get_disclaimer,
    get_elders_redirect,
)


def test_disclaimer_has_three_languages() -> None:
    assert get_disclaimer("general", "en")
    assert get_disclaimer("general", "es")
    assert get_disclaimer("general", "pt")


def test_disclaimer_general_and_sensitive_share_text() -> None:
    assert get_disclaimer("general", "es") == get_disclaimer("sensitive", "es")


def test_disclaimer_unknown_lang_falls_back_to_english() -> None:
    text = get_disclaimer("general", "fr")
    assert "Watchtower" in text or "published" in text.lower()


def test_elders_redirect_sensitive_only() -> None:
    for lang in ("en", "es", "pt"):
        redirect = get_elders_redirect(lang)
        assert "elders" in redirect.lower() or "ancianos" in redirect.lower() or "anciaos" in redirect.lower() or "ancião" in redirect.lower() or "anciao" in redirect.lower()


def test_elders_redirect_falls_back_to_english() -> None:
    text = get_elders_redirect("xx")
    assert text == get_elders_redirect("en")


def test_no_redirect_mentions_medical_professional_by_role() -> None:
    """Pastoral boundary: redirect must not push to therapists/doctors.

    Coherent with the design — agent stays inside the spiritual
    chain (family, elders), not the medical system.
    """
    forbidden = ["therapist", "psychologist", "psychiatrist", "doctor", "terapeuta", "psicologo", "psiquiatra", "medico"]
    for lang in ("en", "es", "pt"):
        text = get_elders_redirect(lang).lower()
        for word in forbidden:
            assert word not in text, f"{lang}: redirect must not name {word!r}"


def test_no_disclaimer_mentions_medical_professional() -> None:
    forbidden = ["therapist", "psychologist", "terapeuta", "psicologo"]
    for fam in ("general", "sensitive"):
        for lang in ("en", "es", "pt"):
            text = get_disclaimer(fam, lang).lower()
            for word in forbidden:
                assert word not in text
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-core/tests/test_life_disclaimers.py -v
```
Expected: FAIL — module missing.

- [ ] **Step 3: Implement disclaimers**

```python
# packages/jw-core/src/jw_core/data/life_disclaimers.py
"""Bilingual disclaimer + elders-redirect text for the `life_topics` agent.

These strings are part of the agent's contract — every AgentResult of
`life_topics` includes at least the disclaimer. Sensitive topics also
include the elders redirect.

Pastoral boundary: the redirect intentionally does NOT name medical
professionals (therapists, doctors). The agent stays inside the
spiritual chain (family, elders). This is a design commitment, not an
oversight — see spec, section "Disclaimers and pastoral boundary".
"""

from __future__ import annotations

from typing import Literal

LifeTopicFamily = Literal["sensitive", "general"]


DISCLAIMERS: dict[tuple[str, str], str] = {
    ("general", "en"): (
        "This information is published material from the Watchtower. "
        "It is not personal counseling. For your specific situation, "
        "speak with your family and the elders of your congregation."
    ),
    ("general", "es"): (
        "Esta es información publicada por la Watchtower. No es consejería "
        "personal. Para tu situación específica, conversa con tu familia y con "
        "los ancianos de tu congregación."
    ),
    ("general", "pt"): (
        "Estas são informações publicadas pela Sociedade Torre de Vigia. "
        "Não é aconselhamento pessoal. Para a sua situação específica, "
        "converse com a sua família e com os anciãos da sua congregação."
    ),
}
# Sensitive topics share the same disclaimer prose; what changes is that
# the agent ALSO emits an elders_redirect Finding for them.
DISCLAIMERS[("sensitive", "en")] = DISCLAIMERS[("general", "en")]
DISCLAIMERS[("sensitive", "es")] = DISCLAIMERS[("general", "es")]
DISCLAIMERS[("sensitive", "pt")] = DISCLAIMERS[("general", "pt")]


ELDERS_REDIRECTS: dict[str, str] = {
    "en": (
        "If what you are going through is difficult, you are not alone. "
        "The elders of your congregation are willing to help (1 Peter 5:1-3) "
        "and your family can pray with you. This page is only published information."
    ),
    "es": (
        "Si lo que vives ahora es difícil, no estás solo. Los ancianos de "
        "tu congregación están dispuestos a ayudarte (1 Pedro 5:1-3) y "
        "tu familia puede orar contigo. Esta página es solo información publicada."
    ),
    "pt": (
        "Se o que você está vivendo agora é difícil, você não está só. "
        "Os anciãos da sua congregação estão dispostos a ajudar (1 Pedro 5:1-3) "
        "e a sua família pode orar com você. Esta página é apenas informação publicada."
    ),
}


def get_disclaimer(family: LifeTopicFamily | str, language: str) -> str:
    """Lookup the disclaimer for (family, language), falling back to (general, en)."""
    key = (family if family in {"general", "sensitive"} else "general", language)
    if key in DISCLAIMERS:
        return DISCLAIMERS[key]
    return DISCLAIMERS[(key[0], "en")] if (key[0], "en") in DISCLAIMERS else DISCLAIMERS[("general", "en")]


def get_elders_redirect(language: str) -> str:
    """Return the elders-redirect text, falling back to English on unknown lang."""
    return ELDERS_REDIRECTS.get(language, ELDERS_REDIRECTS["en"])
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-core/tests/test_life_disclaimers.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-core/src/jw_core/data/life_disclaimers.py packages/jw-core/tests/test_life_disclaimers.py
git commit -m "feat(jw-core): bilingual disclaimer + elders redirect (no medical professionals named)"
```

---

### Task 3: Agent — happy path con stubs (sensitive)

**Files:**
- Create: `packages/jw-agents/src/jw_agents/life_topics.py`
- Create: `packages/jw-agents/tests/test_life_topics.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-agents/tests/test_life_topics.py
"""Tests for the life_topics agent — fully stubbed, zero network."""

from __future__ import annotations

from typing import Any

import pytest

from jw_agents.life_topics import life_topics


# --- Stubs ----------------------------------------------------------


class StubTopicIndex:
    def __init__(self, subjects: dict[str, Any] | None = None) -> None:
        self._subjects = subjects or {}
        self.searched: list[tuple[str, str]] = []

    async def search_subjects(self, anchor: str, *, language: str = "E", limit: int = 1) -> list[dict[str, Any]]:
        self.searched.append((anchor, language))
        if anchor in self._subjects:
            return [{"docid": f"doc-{anchor}", "title": anchor, "wol_url": f"https://wol.jw.org/{anchor}", "score": 100, "snippet": "", "subtype": "subject", "original_rank": 0}]
        return []

    async def get_subject_page(self, docid: str, *, language: str = "en"):
        anchor = docid.removeprefix("doc-")
        payload = self._subjects[anchor]

        class _Sub:
            heading = payload["heading"]
            citations = payload["citations"]
            is_top_level = True

        class _Page:
            title = anchor
            source_url = f"https://wol.jw.org/{anchor}"
            subheadings = [_Sub()]
            see_also: list[str] = []
            total_citations = len(payload["citations"])
            style = "default"

        return _Page()

    async def aclose(self) -> None: ...


class StubCDN:
    def __init__(self, results: list[dict[str, Any]] | None = None) -> None:
        self._results = results or []
        self.calls: list[tuple[str, str, str]] = []

    async def search(self, query: str, *, filter_type: str = "all", language: str = "E", limit: int = 10) -> dict[str, Any]:
        self.calls.append((query, filter_type, language))
        return {"results": self._results[:limit]}

    async def aclose(self) -> None: ...


SAMPLE_ARTICLE_HTML = """
<html><head><title>How to Cope With Anxiety</title></head>
<body>
<article>
  <p id="p1" data-pid="1">The Bible acknowledges that we all face worry at times.</p>
  <p id="p2" data-pid="2">Jesus said: "Stop being anxious about your life." — Matthew 6:25.</p>
  <p id="p3" data-pid="3">Prayer is one of the strongest tools we have.</p>
</article>
</body></html>
"""


class StubWOL:
    def __init__(self, html: str = SAMPLE_ARTICLE_HTML) -> None:
        self._html = html
        self.fetched: list[str] = []

    async def fetch(self, url: str) -> str:
        self.fetched.append(url)
        return self._html

    async def aclose(self) -> None: ...


class _Citation:
    def __init__(self, text: str, kind: str = "bible") -> None:
        self.text = text
        self.kind = kind


# --- Tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_sensitive_topic_emits_disclaimer_and_redirect() -> None:
    topic = StubTopicIndex(
        subjects={
            "Anxiety": {
                "heading": "Anxiety — How to Cope",
                "citations": [_Citation("Philippians 4:6, 7"), _Citation("1 Peter 5:7")],
            }
        }
    )
    cdn = StubCDN(
        results=[
            {
                "title": "How to Cope With Anxiety",
                "links": {"wol": "https://wol.jw.org/articles/anxiety-1"},
            }
        ]
    )
    wol = StubWOL()

    result = await life_topics(
        "ansiedad", language="es", topic=topic, cdn=cdn, wol=wol
    )

    sources = [f.metadata.get("source") for f in result.findings]
    assert "topic_index_entry" in sources
    assert "cdn_search" in sources
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
    assert result.metadata["topic_id"] == "anxiety"
    assert result.metadata["family"] == "sensitive"
    assert result.metadata["language"] == "es"


@pytest.mark.asyncio
async def test_general_topic_does_not_emit_redirect() -> None:
    topic = StubTopicIndex(
        subjects={
            "Children": {
                "heading": "Raising Children",
                "citations": [_Citation("Ephesians 6:4")],
            }
        }
    )
    cdn = StubCDN(results=[{"title": "Family Help", "links": {"wol": "https://wol.jw.org/articles/family-1"}}])
    wol = StubWOL()

    result = await life_topics("parenting", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]

    assert "disclaimer" in sources
    assert "elders_redirect" not in sources
    assert result.metadata["family"] == "general"


@pytest.mark.asyncio
async def test_unknown_topic_emits_warning_and_generic_disclaimer_only() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN()
    wol = StubWOL()

    result = await life_topics("qwertyzzz", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]

    assert sources == ["disclaimer"]
    assert "elders_redirect" not in sources
    assert any("No matching life topic" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_cdn_error_does_not_kill_disclaimer() -> None:
    class BrokenCDN:
        async def search(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("network boom")

        async def aclose(self) -> None: ...

    topic = StubTopicIndex()
    wol = StubWOL()

    result = await life_topics(
        "anxiety", language="en", topic=topic, cdn=BrokenCDN(), wol=wol
    )
    sources = [f.metadata.get("source") for f in result.findings]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources  # still sensitive
    assert any("network boom" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_cdn_uses_publications_filter_and_topic_search_query() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    await life_topics("loneliness", language="en", topic=topic, cdn=cdn, wol=wol)
    assert cdn.calls, "CDN.search was not called"
    query, filt, lang = cdn.calls[0]
    assert filt == "publications"
    assert query == "loneliness friendship"
    assert lang == "E"


@pytest.mark.asyncio
async def test_excerpts_are_capped_per_article() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(
        results=[
            {"title": "Article", "links": {"wol": "https://wol.jw.org/x"}},
        ]
    )
    wol = StubWOL()
    result = await life_topics(
        "anxiety", language="en",
        topic=topic, cdn=cdn, wol=wol,
        max_excerpts_per_article=2,
    )
    excerpts = [f for f in result.findings if f.metadata.get("source") == "cdn_search"]
    assert len(excerpts) <= 2


@pytest.mark.asyncio
async def test_finding_order_disclaimer_before_redirect() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    result = await life_topics("grief", language="en", topic=topic, cdn=cdn, wol=wol)
    sources = [f.metadata.get("source") for f in result.findings]
    assert sources[-2:] == ["disclaimer", "elders_redirect"]


@pytest.mark.asyncio
async def test_no_bible_quotation_fabrication() -> None:
    """Excerpts must come from article HTML — never synthesized.

    We give the agent an HTML that does NOT contain Hebrews 4:13 and
    assert that no Finding text mentions it.
    """
    topic = StubTopicIndex()
    cdn = StubCDN(
        results=[{"title": "Article", "links": {"wol": "https://wol.jw.org/x"}}]
    )
    html_without_hebrews = "<html><body><article><p data-pid='1'>Anxiety is common.</p></article></body></html>"
    wol = StubWOL(html=html_without_hebrews)
    result = await life_topics("anxiety", language="en", topic=topic, cdn=cdn, wol=wol)
    for f in result.findings:
        assert "Hebrews 4:13" not in (f.excerpt or "")
        assert "Hebrews 4:13" not in f.summary


@pytest.mark.asyncio
async def test_language_fr_falls_back_to_english_disclaimer() -> None:
    topic = StubTopicIndex()
    cdn = StubCDN(results=[])
    wol = StubWOL()
    result = await life_topics("anxiety", language="fr", topic=topic, cdn=cdn, wol=wol)
    disclaimer = next(f for f in result.findings if f.metadata.get("source") == "disclaimer")
    assert "Watchtower" in disclaimer.excerpt
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-agents/tests/test_life_topics.py -v
```
Expected: FAIL — module `jw_agents.life_topics` missing.

- [ ] **Step 3: Implement the agent**

```python
# packages/jw-agents/src/jw_agents/life_topics.py
"""life_topics agent — informative answers on sensitive personal topics.

This agent is DELIBERATELY different from research_topic and
conversation_assistant:

  - It serves a user asking *for themselves*, not researching for a class
    or preparing a witness conversation.
  - Every AgentResult includes a `disclaimer` Finding. The disclaimer is
    part of the agent's CONTRACT, not a doc-only note.
  - Topics marked `family=sensitive` ALSO carry an `elders_redirect`
    Finding pointing the user to local elders / family.
  - The agent NEVER fabricates Scripture; it only relays excerpts that
    appear verbatim in the matched articles.

If no published material matches, the result is empty of excerpts but
the disclaimer is still present. The agent never invents pastoral counsel.
"""

from __future__ import annotations

from typing import Any

from jw_core.clients.cdn import CDNClient
from jw_core.clients.topic_index import TopicIndexClient
from jw_core.clients.wol import WOLClient
from jw_core.data.life_disclaimers import get_disclaimer, get_elders_redirect
from jw_core.data.life_topics import LifeTopic, resolve_topic
from jw_core.languages import get_language
from jw_core.parsers.article import parse_article

from jw_agents.base import AgentResult, Citation, Finding


async def life_topics(
    query: str,
    *,
    language: str = "en",
    top_articles: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 2,
    topic: TopicIndexClient | None = None,
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
) -> AgentResult:
    """Surface published material on a life topic + mandatory disclaimer.

    Args:
        query: Free-form user input ("anxiety" / "ansiedad" / "ansiedade").
        language: ISO code ("en", "es", "pt"). Other ISOs fall back to English
            for disclaimer text but the topic registry still tries cross-lang.
        top_articles: how many CDN search hits to consider.
        fetch_top_k: of those, how many to actually fetch + parse.
        max_excerpts_per_article: paragraph cap per article.

    Returns:
        AgentResult with findings ordered: topic_index_entry → cdn_search →
        disclaimer → elders_redirect.

        Empty results are still valid; the disclaimer is the floor.
    """
    result = AgentResult(query=query, agent_name="life_topics")
    result.metadata["language"] = language

    matched = resolve_topic(query, language=language)

    # Track which clients we own so we can close them cleanly.
    owned_topic = topic is None
    owned_cdn = cdn is None
    owned_wol = wol is None
    topic = topic if topic is not None else TopicIndexClient()
    cdn = cdn if cdn is not None else CDNClient()
    wol = wol if wol is not None else WOLClient()

    try:
        if matched is None:
            result.warnings.append(f"No matching life topic for query: {query!r}")
            _append_disclaimer(result, family="general", language=language)
            return result

        result.metadata["topic_id"] = matched.topic_id
        result.metadata["family"] = matched.family

        try:
            jw_lang = get_language(language).jw_code
        except KeyError:
            jw_lang = "E"

        await _surface_topic_index(result, matched, topic=topic, jw_lang=jw_lang, language=language)
        await _surface_cdn_articles(
            result,
            matched,
            cdn=cdn,
            wol=wol,
            jw_lang=jw_lang,
            top_articles=top_articles,
            fetch_top_k=fetch_top_k,
            max_excerpts_per_article=max_excerpts_per_article,
        )

        _append_disclaimer(result, family=matched.family, language=language)
        if matched.family == "sensitive":
            _append_elders_redirect(result, language=language)
        return result
    finally:
        if owned_topic:
            await topic.aclose()
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()


async def _surface_topic_index(
    result: AgentResult,
    matched: LifeTopic,
    *,
    topic: TopicIndexClient,
    jw_lang: str,
    language: str,
) -> None:
    for anchor in matched.topic_anchors:
        try:
            hits = await topic.search_subjects(anchor, language=jw_lang, limit=1)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Topic anchor {anchor!r} failed: {exc}")
            continue
        if not hits:
            continue
        docid = hits[0].get("docid") or ""
        if not docid:
            continue
        try:
            page = await topic.get_subject_page(docid, language=language)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Subject {anchor!r} fetch failed: {exc}")
            continue
        for sh in list(page.subheadings)[:3]:
            citations_text = "; ".join(getattr(c, "text", "") for c in sh.citations[:6])
            result.findings.append(
                Finding(
                    summary=f"{page.title} → {sh.heading}",
                    excerpt=citations_text,
                    citation=Citation(
                        url=page.source_url,
                        title=f"{page.title}: {sh.heading}",
                        kind="topic_subheading",
                    ),
                    metadata={
                        "source": "topic_index_entry",
                        "anchor": anchor,
                        "topic_id": matched.topic_id,
                    },
                )
            )


async def _surface_cdn_articles(
    result: AgentResult,
    matched: LifeTopic,
    *,
    cdn: CDNClient,
    wol: WOLClient,
    jw_lang: str,
    top_articles: int,
    fetch_top_k: int,
    max_excerpts_per_article: int,
) -> None:
    try:
        data = await cdn.search(
            matched.search_query,
            filter_type="publications",
            language=jw_lang,
            limit=top_articles,
        )
    except Exception as exc:  # noqa: BLE001
        result.warnings.append(f"CDN search failed: {exc}")
        return

    items = _flatten(data, limit=top_articles)
    fetched = 0
    for item in items:
        if fetched >= fetch_top_k:
            break
        url = _wol_url(item)
        if not url:
            continue
        try:
            html = await wol.fetch(url)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Fetch failed for {url}: {exc}")
            continue
        article = parse_article(html)
        title = article.title or item.get("title", "")
        for i, paragraph in enumerate(article.paragraphs[:max_excerpts_per_article]):
            result.findings.append(
                Finding(
                    summary=f"Excerpt from “{title}”",
                    excerpt=paragraph,
                    citation=Citation(
                        url=url,
                        title=title,
                        kind="article",
                        metadata={"paragraph_index": i + 1},
                    ),
                    metadata={
                        "source": "cdn_search",
                        "topic_id": matched.topic_id,
                    },
                )
            )
        fetched += 1


def _append_disclaimer(result: AgentResult, *, family: str, language: str) -> None:
    text = get_disclaimer(family, language)
    result.findings.append(
        Finding(
            summary="Pastoral boundary",
            excerpt=text,
            citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
            metadata={"source": "disclaimer", "family": family},
        )
    )


def _append_elders_redirect(result: AgentResult, *, language: str) -> None:
    text = get_elders_redirect(language)
    result.findings.append(
        Finding(
            summary="Talk to your elders and family",
            excerpt=text,
            citation=Citation(
                url="",
                title="Elders redirect (1 Peter 5:1-3)",
                kind="elders_redirect",
            ),
            metadata={"source": "elders_redirect"},
        )
    )


def _flatten(data: dict[str, Any], *, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in data.get("results", []):
        if not isinstance(r, dict):
            continue
        if r.get("type") == "group":
            out.extend(x for x in r.get("results", []) if isinstance(x, dict))
        else:
            out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


def _wol_url(item: dict[str, Any]) -> str | None:
    links = item.get("links", {}) or {}
    return links.get("wol") or links.get("jw.org") or None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-agents/tests/test_life_topics.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-agents/src/jw_agents/life_topics.py packages/jw-agents/tests/test_life_topics.py
git commit -m "feat(jw-agents): life_topics agent with mandatory disclaimer + sensitive-topic elders redirect"
```

---

### Task 4: CLI command `jw life`

**Files:**
- Create: `packages/jw-cli/src/jw_cli/commands/life.py`
- Create: `packages/jw-cli/tests/test_life_cmd.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py`

- [ ] **Step 1: Write the failing test (smoke via Typer's CliRunner)**

```python
# packages/jw-cli/tests/test_life_cmd.py
from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from jw_cli.main import app


@pytest.fixture
def fake_life_topics(monkeypatch):
    """Patch the agent inside the command module to a deterministic stub."""
    from jw_agents.base import AgentResult, Citation, Finding

    async def fake(query: str, *, language: str = "en", **kwargs: Any) -> AgentResult:
        ar = AgentResult(query=query, agent_name="life_topics")
        ar.metadata["language"] = language
        ar.metadata["topic_id"] = "anxiety"
        ar.metadata["family"] = "sensitive"
        ar.findings.append(
            Finding(
                summary="Excerpt from “How to Cope With Anxiety”",
                excerpt="Trust in Jehovah brings peace.",
                citation=Citation(url="https://wol.jw.org/x", title="How to Cope", kind="article"),
                metadata={"source": "cdn_search"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Pastoral boundary",
                excerpt="This is published material. Speak with elders.",
                citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
                metadata={"source": "disclaimer", "family": "sensitive"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Talk to your elders",
                excerpt="The elders of your congregation are willing to help.",
                citation=Citation(url="", title="Elders redirect", kind="elders_redirect"),
                metadata={"source": "elders_redirect"},
            )
        )
        return ar

    monkeypatch.setattr("jw_cli.commands.life.life_topics", fake)


def test_life_cmd_renders_disclaimer_and_redirect(fake_life_topics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["life", "anxiety", "--lang", "en"])
    assert res.exit_code == 0, res.output
    assert "Trust in Jehovah" in res.output
    assert "elders" in res.output.lower()
    assert "Speak with elders" in res.output or "published material" in res.output.lower()


def test_life_cmd_json_output_contains_all_sources(fake_life_topics) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["life", "anxiety", "--lang", "en", "--json"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    sources = [f["metadata"].get("source") for f in data["findings"]]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-cli/tests/test_life_cmd.py -v
```
Expected: FAIL — no `life` command yet.

- [ ] **Step 3: Implement the CLI command**

```python
# packages/jw-cli/src/jw_cli/commands/life.py
"""`jw life` — informational answers on life topics with citations + boundary.

This is a thin wrapper around `jw_agents.life_topics`. It never tries to
"polish" the disclaimer or hide the redirect — printing them faithfully is
part of the agent's contract.
"""

from __future__ import annotations

import asyncio
import json as _json

import typer
from jw_agents.life_topics import life_topics
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def life_cmd(
    query: str = typer.Argument(..., help='Topic or alias (e.g. "anxiety", "ansiedad", "luto").'),
    lang: str = typer.Option("en", "--lang", "-l", help="ISO language: en, es, pt."),
    top_articles: int = typer.Option(5, "--top", help="Max CDN search hits to consider."),
    fetch_top_k: int = typer.Option(3, "--fetch", help="Max articles to actually parse."),
    max_excerpts_per_article: int = typer.Option(2, "--excerpts", help="Paragraphs per article."),
    json: bool = typer.Option(False, "--json", help="Emit JSON dump of AgentResult."),
) -> None:
    """Show published material on a life topic plus the mandatory pastoral disclaimer."""

    async def run() -> None:
        result = await life_topics(
            query,
            language=lang,
            top_articles=top_articles,
            fetch_top_k=fetch_top_k,
            max_excerpts_per_article=max_excerpts_per_article,
        )

        if json:
            console.print_json(_json.dumps(result.to_dict()))
            return

        # Header
        topic_id = result.metadata.get("topic_id", "—")
        family = result.metadata.get("family", "—")
        console.print(
            Panel(
                f"[bold]Topic:[/bold] {topic_id}\n[bold]Family:[/bold] {family}\n[bold]Language:[/bold] {lang}",
                title="life_topics",
                border_style="cyan",
            )
        )

        # Sections: excerpts first, then disclaimer/redirect at the bottom.
        excerpts = [f for f in result.findings if f.metadata.get("source") in {"topic_index_entry", "cdn_search"}]
        disclaimers = [f for f in result.findings if f.metadata.get("source") == "disclaimer"]
        redirects = [f for f in result.findings if f.metadata.get("source") == "elders_redirect"]

        if excerpts:
            table = Table(title="Published material")
            table.add_column("#", justify="right", style="dim")
            table.add_column("Source")
            table.add_column("Summary")
            table.add_column("Excerpt")
            for i, f in enumerate(excerpts, 1):
                table.add_row(
                    str(i),
                    f.metadata.get("source", ""),
                    f.summary[:50],
                    (f.excerpt or "")[:100],
                )
            console.print(table)
            for f in excerpts:
                if f.citation.url:
                    console.print(f"[dim]→ {f.citation.url}[/dim]")
        else:
            console.print("[yellow]No matching published material.[/yellow]")

        for f in disclaimers:
            console.print(Panel(f.excerpt, title="Disclaimer", border_style="yellow"))
        for f in redirects:
            console.print(Panel(f.excerpt, title="Talk to your family and elders", border_style="magenta"))

        for w in result.warnings:
            console.print(f"[yellow]warn:[/yellow] {w}")

    asyncio.run(run())
```

- [ ] **Step 4: Wire `jw life` into `main.py`**

Edit `packages/jw-cli/src/jw_cli/main.py`:

1. In the `from jw_cli.commands import (...)` block (around line 16), add `life,`.
2. After the existing `app.command(...)` lines (around line 45), append:

```python
app.command(name="life")(life.life_cmd)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest packages/jw-cli/tests/test_life_cmd.py -v
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-cli/src/jw_cli/commands/life.py packages/jw-cli/tests/test_life_cmd.py packages/jw-cli/src/jw_cli/main.py
git commit -m "feat(jw-cli): jw life command — informational topic with disclaimer + redirect"
```

---

### Task 5: MCP tool `life_topic_info`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Create: `packages/jw-mcp/tests/test_life_topic_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/jw-mcp/tests/test_life_topic_tool.py
from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.asyncio
async def test_life_topic_info_returns_dict_with_disclaimer(monkeypatch) -> None:
    from jw_agents.base import AgentResult, Citation, Finding

    async def fake(query: str, *, language: str = "en", **_: Any) -> AgentResult:
        ar = AgentResult(query=query, agent_name="life_topics")
        ar.metadata["topic_id"] = "anxiety"
        ar.metadata["family"] = "sensitive"
        ar.findings.append(
            Finding(
                summary="Disclaimer",
                excerpt="Speak with elders.",
                citation=Citation(url="", title="Disclaimer", kind="disclaimer"),
                metadata={"source": "disclaimer", "family": "sensitive"},
            )
        )
        ar.findings.append(
            Finding(
                summary="Redirect",
                excerpt="Talk to your family.",
                citation=Citation(url="", title="Redirect", kind="elders_redirect"),
                metadata={"source": "elders_redirect"},
            )
        )
        return ar

    monkeypatch.setattr("jw_mcp.server.life_topics_agent", fake)

    from jw_mcp.server import life_topic_info

    out = await life_topic_info("ansiedad", language="es")
    sources = [f["metadata"].get("source") for f in out["findings"]]
    assert "disclaimer" in sources
    assert "elders_redirect" in sources
    assert out["metadata"]["topic_id"] == "anxiety"


@pytest.mark.asyncio
async def test_life_topic_info_unknown_topic_still_has_disclaimer(monkeypatch) -> None:
    from jw_mcp.server import life_topic_info

    out = await life_topic_info("zzzzzqqq", language="en")
    # The real agent runs here (stubs not used). It must still emit a disclaimer.
    sources = [f["metadata"].get("source") for f in out["findings"]]
    assert "disclaimer" in sources
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest packages/jw-mcp/tests/test_life_topic_tool.py -v
```
Expected: FAIL — `life_topic_info` does not exist.

- [ ] **Step 3: Register the MCP tool**

Append near the other agent tools in `packages/jw-mcp/src/jw_mcp/server.py`:

```python
from jw_agents.life_topics import life_topics as life_topics_agent  # noqa: E402


@mcp.tool()
async def life_topic_info(
    topic_or_alias: str,
    language: str = "en",
    top_articles: int = 5,
    fetch_top_k: int = 3,
    max_excerpts_per_article: int = 2,
) -> dict[str, Any]:
    """Information on a life topic with verifiable citations and a mandatory disclaimer.

    Maps `topic_or_alias` (in any of en/es/pt) to a canonical topic, surfaces
    Topic Index entries + published article excerpts, and ALWAYS emits a
    `disclaimer` Finding. For sensitive topics (anxiety, grief, marriage_conflict,
    depression_signs, addictions, doubts_in_faith), also emits an `elders_redirect`
    Finding pointing the user to family and congregation elders.

    The agent does not provide pastoral counseling. The LLM consumer of this tool
    is expected to preserve both the disclaimer and (when present) the redirect
    in any final answer.
    """
    result = await life_topics_agent(
        topic_or_alias,
        language=language,
        top_articles=top_articles,
        fetch_top_k=fetch_top_k,
        max_excerpts_per_article=max_excerpts_per_article,
    )
    return result.to_dict()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest packages/jw-mcp/tests/test_life_topic_tool.py -v
```
Expected: 2 passed (note: the second test runs the real agent, so the test machine needs network OR the test must be marked `@pytest.mark.network` and skipped in CI — see note below).

> **Note on the second test**: if `pytest -m "not network"` is the default, mark it:
>
> ```python
> @pytest.mark.network
> @pytest.mark.asyncio
> async def test_life_topic_info_unknown_topic_still_has_disclaimer(...) -> None: ...
> ```
>
> Better: re-stub `cdn` and `wol` clients via dependency injection in `life_topic_info` — but the signature stays clean if we just keep the test marked. Keep it marked.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/server.py packages/jw-mcp/tests/test_life_topic_tool.py
git commit -m "feat(jw-mcp): expose life_topic_info tool with disclaimer + redirect contract"
```

---

### Task 6: Register agent in `jw-eval`

**Files:**
- Modify: `packages/jw-eval/src/jw_eval/cli.py`

- [ ] **Step 1: Add agent to `default_agent_registry()`**

In `default_agent_registry()`, alongside the other agents:

```python
from jw_agents.life_topics import life_topics  # type: ignore[import-not-found]
...
_wrap("life_topics", life_topics)
```

The existing `_wrap` already handles the `fn(**inp)` invocation. `life_topics(query, language=...)` matches that shape if the YAML `input` maps to `{"query": ..., "language": ...}`.

- [ ] **Step 2: Smoke-check the registry**

```bash
uv run python -c "from jw_eval.cli import default_agent_registry; print('life_topics' in default_agent_registry())"
```
Expected: `True`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/src/jw_eval/cli.py
git commit -m "feat(jw-eval): register life_topics agent in default registry"
```

---

### Task 7: Golden case L1 — anxiety_es (sensible)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/life_topics_anxiety_es.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/life_topics_anxiety_es.yaml
id: l1_life_topics_anxiety_es
agent: life_topics
layer: l1
input:
  query: "ansiedad"
  language: "es"
expected:
  min_findings: 2
  must_have_source: disclaimer
  must_have_citation: true
  forbidden_keywords_in_findings:
    - "terapeuta"
    - "psicólogo"
    - "psiquiatra"
    - "supuestamente"
metadata:
  topic: life.anxiety
  family: sensitive
  notes: >
    Sensitive topic must emit both disclaimer + elders_redirect.
    The forbidden_keywords protect the pastoral boundary — the agent
    must not name medical professionals.
  added_by: elias
  added_at: 2026-05-30
```

> The L1 structural evaluator (Task 4 of Fase 22) does not natively check for "must have TWO sources", but `must_have_source` covers `disclaimer`, and the `forbidden_keywords_in_findings` covers the boundary. To assert `elders_redirect` is present we add a second L1 case below for general topics that asserts its **absence**.

- [ ] **Step 2: Verify it loads**

```bash
uv run python -c "
from pathlib import Path
from jw_eval.loader import load_cases
print([c.id for c in load_cases(Path('packages/jw-eval/fixtures/golden_qa'), layers=['l1']) if 'life' in c.id])
"
```
Expected: `['l1_life_topics_anxiety_es']`.

- [ ] **Step 3: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/life_topics_anxiety_es.yaml
git commit -m "test(jw-eval): L1 golden case life_topics anxiety_es (sensitive, must have disclaimer)"
```

---

### Task 8: Golden case L1 — parenting_en (general)

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l1/life_topics_parenting_en.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
# packages/jw-eval/fixtures/golden_qa/l1/life_topics_parenting_en.yaml
id: l1_life_topics_parenting_en
agent: life_topics
layer: l1
input:
  query: "parenting"
  language: "en"
expected:
  min_findings: 1
  must_have_source: disclaimer
  forbidden_keywords_in_findings:
    - "therapist"
    - "psychologist"
    - "psychiatrist"
    - "elders of your congregation are willing"
metadata:
  topic: life.parenting
  family: general
  notes: >
    General topic — disclaimer required but NO elders_redirect.
    The forbidden phrase "elders of your congregation are willing" is a
    quote from the elders_redirect text; if it appears in a Finding the
    agent emitted a redirect for a non-sensitive topic.
  added_by: elias
  added_at: 2026-05-30
```

> Rationale for the forbidden phrase: the L1 structural layer doesn't have a "must NOT have source" assertion, so we encode the boundary as a forbidden keyword string — the elders_redirect prose. If a general-family case ever emits the redirect, the case will fail.

- [ ] **Step 2: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l1/life_topics_parenting_en.yaml
git commit -m "test(jw-eval): L1 golden case life_topics parenting_en (general, must NOT redirect)"
```

---

### Task 9: Golden case L3 — grief_en

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l3/life_topics_grief_en.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
# packages/jw-eval/fixtures/golden_qa/l3/life_topics_grief_en.yaml
id: l3_life_topics_grief_en
agent: life_topics
layer: l3
input:
  query: "grief"
  language: "en"
expected:
  golden_answer: |
    The Bible offers real comfort to those grieving the death of a loved one.
    Ecclesiastes 9:5 explains that the dead are unconscious — they are not
    suffering. Jehovah promises a resurrection on a paradise earth
    (John 5:28, 29; Acts 24:15), so the parting is not forever. While this
    information is from published Watchtower material, your family and the
    elders of your congregation are willing to comfort you personally.
  expected_keywords_any:
    - "resurrection"
    - "Ecclesiastes 9:5"
    - "elders"
  expected_keywords_none:
    - "will be reunited"
    - "guaranteed to see them again"
    - "therapist"
    - "professional grief counseling"
metadata:
  topic: life.grief
  family: sensitive
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l3/life_topics_grief_en.yaml
git commit -m "test(jw-eval): L3 golden case life_topics grief_en (sensitive, resurrection hope)"
```

---

### Task 10: Golden case L3 — doubts_es

**Files:**
- Create: `packages/jw-eval/fixtures/golden_qa/l3/life_topics_doubts_es.yaml`

- [ ] **Step 1: Write the fixture**

```yaml
# packages/jw-eval/fixtures/golden_qa/l3/life_topics_doubts_es.yaml
id: l3_life_topics_doubts_es
agent: life_topics
layer: l3
input:
  query: "dudas en la fe"
  language: "es"
expected:
  golden_answer: |
    Tener dudas no es una señal de que tu fe ha terminado. La Biblia anima
    a examinar las cosas con cuidado (Hechos 17:11) y a fortalecer la fe
    comparando lo que se enseña con las Escrituras. Esta es información
    publicada por la Watchtower; tu familia y los ancianos de tu congregación
    están dispuestos a conversar contigo y ayudarte (1 Pedro 5:1-3).
  expected_keywords_any:
    - "Hechos 17:11"
    - "ancianos"
    - "Escrituras"
  expected_keywords_none:
    - "profesional de salud mental"
    - "terapia"
    - "abandonar la fe"
metadata:
  topic: life.doubts_in_faith
  family: sensitive
  added_by: elias
  added_at: 2026-05-30
```

- [ ] **Step 2: Commit**

```bash
git add packages/jw-eval/fixtures/golden_qa/l3/life_topics_doubts_es.yaml
git commit -m "test(jw-eval): L3 golden case life_topics doubts_es (sensitive, examine + elders)"
```

---

### Task 11: User guide

**Files:**
- Create: `docs/guias/temas-de-vida.md`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the guide**

````markdown
# Temas de vida (`life_topics`)

> Fase 32 — asistente informativo. Spec: `docs/superpowers/specs/2026-05-30-fase-32-life-topics-design.md`.

## Para qué sirve

Cuando alguien necesita saber **qué publicó la Watchtower** sobre un tema personal — ansiedad, duelo, conflicto matrimonial, soledad, dudas en la fe — y quiere material con citas verificables.

## Esto NO es consejería

(Esta sección no es decorativa. Es parte del contrato de la herramienta.)

`life_topics` es un agregador informativo. **No** sustituye:

- A los ancianos de tu congregación (1 Pedro 5:1-3).
- A tu familia.
- A cualquier profesional médico que estés viendo.

Cada respuesta del agente incluye, **siempre**, un `disclaimer` Finding. Para temas marcados como *sensibles* (ansiedad, duelo, conflicto matrimonial, depresión, adicciones, dudas en la fe), también incluye un `elders_redirect` Finding. El LLM consumidor debe preservarlos.

## Temas iniciales

| Tema | Familia | Idiomas |
|---|---|---|
| anxiety | sensible | en/es/pt |
| grief | sensible | en/es/pt |
| marriage_conflict | sensible | en/es/pt |
| depression_signs | sensible | en/es/pt |
| addictions | sensible | en/es/pt |
| doubts_in_faith | sensible | en/es/pt |
| parenting | general | en/es/pt |
| loneliness | general | en/es/pt |
| conflict_with_brother | general | en/es/pt |

## Uso CLI

```bash
jw life "anxiety" --lang en
jw life "ansiedad" --lang es
jw life "luto" --lang pt --top 3 --fetch 2
jw life "parenting" --lang en --json
```

## Uso vía MCP

Herramienta: `life_topic_info(topic_or_alias: str, language: str = "en") -> dict`.

```python
out = await life_topic_info("ansiedad", language="es")
# out["findings"] incluye al menos un source='disclaimer'
# y, si es sensible, un source='elders_redirect'
```

## Cómo se resuelven los alias

El agente normaliza acentos y minúsculas; primero busca el alias en el idioma indicado, luego hace fallback cross-language. Si nada matches, devuelve solo el disclaimer genérico.

## Lo que el agente NO hace

- No genera versículos de la Biblia "de memoria". Solo cita los que aparecen en los artículos retornados o como referencias del Topic Index.
- No sugiere terapeutas, psicólogos ni médicos por nombre.
- No guarda lo que el usuario consulta. Stateless.
- No genera "consejo personalizado". Solo agrega excerpts de material publicado.

## Si no hay material

Devuelve `warnings` describiendo el fallo + disclaimer. Eso es válido. El próximo paso correcto es el ser humano, no más automatización.

## Política de cambios

- Añadir un tema nuevo a `REGISTRY` (`jw_core/data/life_topics.py`) requiere también: actualizar disclaimers si la familia es nueva, añadir mínimo 1 golden case L1 + 1 L3, documentar aquí.
- Cambiar la familia de un tema (de `general` a `sensitive` o viceversa) requiere PR independiente con justificación.
- El texto del `elders_redirect` deliberadamente NO menciona profesionales médicos por nombre. Cambiar eso es un PR de política, no de código.
````

- [ ] **Step 2: Add link from `docs/README.md`**

In the "Guías por tema" list, in alphabetical position:

```markdown
- [Temas de vida](guias/temas-de-vida.md) — Asistente `life_topics`: información con citas + redirect a ancianos en temas sensibles.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guias/temas-de-vida.md docs/README.md
git commit -m "docs(life): user guide for life_topics agent, with pastoral boundary section"
```

---

### Task 12: Update VISION_AUDIT.md + ROADMAP.md

**Files:**
- Modify: `docs/VISION_AUDIT.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Add row to VISION_AUDIT.md summary table**

Insert after the Fase 31 row (or at the bottom of the relevant table):

```markdown
| Fase 32 (life topics) | ✅ Nuevo | `life_topics` agente + tool MCP + registry 9 temas |
```

- [ ] **Step 2: Append Fase 32 block to ROADMAP.md**

After the Fase 31 section:

````markdown
## Fase 32 — Asistente informativo de temas de vida ✅

> Tier 4 capa UX / nicho. Spec: `docs/superpowers/specs/2026-05-30-fase-32-life-topics-design.md`.

- ✅ Registry de 9 temas (anxiety, grief, marriage_conflict, depression_signs, addictions, doubts_in_faith, parenting, loneliness, conflict_with_brother) con aliases en `en/es/pt`.
- ✅ Disclaimer bilingüe + elders_redirect (sin mencionar profesionales médicos por nombre — boundary deliberada).
- ✅ Agente `life_topics` con disclaimer obligatorio + redirect en temas sensibles.
- ✅ Pipeline: Topic Index → CDN `filter='publications'` → parse_article → previews.
- ✅ Comando CLI `jw life "<query>" --lang en|es|pt`.
- ✅ Tool MCP `life_topic_info`.
- ✅ Golden cases en `jw-eval`: 2 L1 (anxiety_es, parenting_en) + 2 L3 (grief_en, doubts_es).
- ✅ Guía `docs/guias/temas-de-vida.md`.

### Boundary explícita

- El agente nunca fabrica citas bíblicas; solo enlaza versículos presentes en el material matched.
- El agente nunca sustituye consejería pastoral.
- Sin persistencia: stateless por diseño.
- Lista de temas sensibles cerrada — añadir temas requiere PR independiente con justificación.

### Cobertura de tests

- ✅ 11 tests en `packages/jw-core/tests/test_life_topics_data.py`.
- ✅ 7 tests en `packages/jw-core/tests/test_life_disclaimers.py`.
- ✅ 9 tests en `packages/jw-agents/tests/test_life_topics.py`.
- ✅ 2 tests en `packages/jw-cli/tests/test_life_cmd.py`.
- ✅ 2 tests en `packages/jw-mcp/tests/test_life_topic_tool.py`.
- ✅ Suite global sin regresiones.
````

- [ ] **Step 3: Commit**

```bash
git add docs/VISION_AUDIT.md docs/ROADMAP.md
git commit -m "docs(roadmap): land Fase 32 — life_topics with pastoral boundary"
```

---

### Task 13: Final audit — full suite green + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Lint + format**

```bash
uv run ruff check packages/jw-core packages/jw-agents packages/jw-cli packages/jw-mcp packages/jw-eval
uv run ruff format --check packages/jw-core packages/jw-agents packages/jw-cli packages/jw-mcp packages/jw-eval
```
Expected: zero violations.

- [ ] **Step 2: Run the entire test suite**

```bash
uv run pytest packages/ -v --tb=short -m "not network"
```
Expected: previous 551 + ~31 new tests green. No regressions.

- [ ] **Step 3: Eval L1 for life_topics**

```bash
uv run jw eval --layer 1 --filter-agent life_topics
```
Expected: both L1 cases (`anxiety_es`, `parenting_en`) reach the structural evaluator. If Fase 22 is also being rolled out, this verifies the registry hook works.

- [ ] **Step 4: Manual CLI smoke with stubs**

Run a quick interactive check:

```bash
uv run python -c "
import asyncio
from jw_agents.life_topics import life_topics

async def main():
    # Sensible — falls back to live clients; expects internet.
    r = await life_topics('grief', language='en', fetch_top_k=1, top_articles=3)
    sources = [f.metadata.get('source') for f in r.findings]
    assert 'disclaimer' in sources
    assert 'elders_redirect' in sources
    print('OK — sensitive topic emits both disclaimer and redirect.')
    print('Sources:', sources)
    print('Warnings:', r.warnings)

asyncio.run(main())
"
```
Expected: output ends with `OK — sensitive topic emits both disclaimer and redirect.`. If offline, the assertion still passes because both are appended regardless of network errors.

- [ ] **Step 5: Final commit if doc polish needed**

If small doc tweaks: `docs(life): polish`. Otherwise stop here.

---

## Self-review

### Coverage of the spec

| Spec section | Plan task |
|---|---|
| Disclaimers and pastoral boundary | Tasks 2, 7, 8, 9, 10, 11 (`forbidden_keywords` + guide section) |
| Registry of life topics | Task 1 |
| Disclaimer + redirect data store | Task 2 |
| Agent pipeline | Task 3 |
| CLI `jw life` | Task 4 |
| MCP `life_topic_info` | Task 5 |
| jw-eval integration | Task 6 |
| Golden cases (2 L1 + 2 L3) | Tasks 7, 8, 9, 10 |
| User guide | Task 11 |
| VISION_AUDIT + ROADMAP | Task 12 |
| Final audit | Task 13 |

### Non-negotiables honored

- **No LLM critical path**: every step is procedural (resolve → topic_index → CDN → parse → append disclaimer).
- **Citations verifiable**: every excerpt Finding carries `citation.url` from the resolved wol URL.
- **Local-first**: stateless; no `~/.jw-agent-toolkit/` writes.
- **No network in tests**: all 9 agent tests use stubs. The 1 MCP test that doesn't is marked `network`.
- **en/es/pt**: registry, disclaimers, golden cases all cover the three languages.
- **Spanish prose, English identifiers**: spec + plan + guide in Spanish; code in English.
- **Hatchling/src/Python 3.13/GPL-3.0**: no new packages; reuses existing.

### Type consistency

- `LifeTopic.family: Literal["sensitive", "general"]` matches `DISCLAIMERS` key type and the `forbidden_keywords` check.
- `AgentResult.findings[*].metadata["source"]` values are drawn from a fixed vocabulary: `topic_index_entry | cdn_search | disclaimer | elders_redirect`. The CLI rendering, the MCP tool return, and the eval `must_have_source` all reference the same vocabulary.

### Non-obvious decisions reaffirmed

1. **`filter_type='publications'`** instead of the brief's `'articles'` — because the existing `CDNClient` doesn't expose `'articles'`. Documented in the spec.
2. **L1 cases use forbidden_keywords for boundary enforcement** — because the L1 evaluator has no native "must NOT have source X" assertion; encoding the redirect prose as a forbidden phrase is the cleanest way to assert its absence in the parenting case.
3. **Disclaimer text is identical for sensitive and general families** — the difference is the presence of the redirect Finding, not the disclaimer prose. Less duplication, clearer contract.

## Execution choice

Plan completo. Dos opciones:

1. **Subagent-driven (recomendado)** — `superpowers:subagent-driven-development` para correr cada tarea con review entre pasos.
2. **Inline** — `superpowers:executing-plans` para ejecutar dentro de esta sesión.

¿Cuál prefieres?
