"""Suite dispatcher — loads cases, routes to layer evaluators, returns SuiteReport."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jw_eval.judges.embeddings import EmbeddingsJudge
from jw_eval.judges.llm import LLMJudge, get_default_caller
from jw_eval.layers.citations import evaluate_citations_live, evaluate_citations_snapshot
from jw_eval.layers.semantic import evaluate_semantic
from jw_eval.layers.structural import evaluate_structural
from jw_eval.loader import load_cases
from jw_eval.models import GoldenCase, LayerName, LayerResult, SuiteReport

AgentRegistry = dict[str, Callable[[dict[str, Any]], Any]]


class Suite:
    def __init__(
        self,
        cases_root: Path,
        snapshots_root: Path,
        agent_registry: AgentRegistry,
        live_fetcher: Callable[[str], str] | None = None,
        embeddings_judge: EmbeddingsJudge | None = None,
        llm_judge: LLMJudge | None = None,
    ) -> None:
        self.cases_root = cases_root
        self.snapshots_root = snapshots_root
        self.agents = agent_registry
        self.live_fetcher = live_fetcher
        self.embeddings_judge = embeddings_judge
        self.llm_judge = llm_judge

    def _resolve_agent(self, name: str):
        agent = self.agents.get(name)
        if agent is None:
            def _err(_: dict[str, Any]):
                raise RuntimeError(f"agent {name!r} not registered")
            return _err
        return agent

    def _evaluate(self, case: GoldenCase, live: bool) -> LayerResult:
        agent = self._resolve_agent(case.agent)
        if case.layer == "l1":
            return evaluate_structural(case, agent)
        if case.layer == "l2":
            if live and self.live_fetcher is not None:
                return evaluate_citations_live(case, agent, fetcher=self.live_fetcher)
            return evaluate_citations_snapshot(case, agent, snapshots_root=self.snapshots_root)
        if case.layer == "l3":
            if self.embeddings_judge is None:
                self.embeddings_judge = EmbeddingsJudge()
            if self.llm_judge is None:
                try:
                    caller = get_default_caller()
                except Exception:  # noqa: BLE001 - bad env var should not crash suite
                    caller = None
                self.llm_judge = LLMJudge(caller=caller) if caller is not None else None
            return evaluate_semantic(
                case,
                agent,
                embeddings_judge=self.embeddings_judge,
                llm_judge=self.llm_judge,
            )
        return LayerResult(case_id=case.id, layer=case.layer, verdict="error", reasons=["unknown layer"])

    def run(
        self,
        layers: list[LayerName],
        agent_filter: str | None = None,
        live: bool = False,
    ) -> SuiteReport:
        started = datetime.now(UTC)
        cases = load_cases(self.cases_root, layers=layers)
        if agent_filter:
            cases = [c for c in cases if c.agent == agent_filter]
        results = [self._evaluate(c, live=live) for c in cases]
        finished = datetime.now(UTC)
        return SuiteReport(
            started_at=started,
            finished_at=finished,
            layers_run=list(layers),
            results=results,
            summary=SuiteReport.summarize(results),
        )
