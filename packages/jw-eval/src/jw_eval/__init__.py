"""jw-eval — doctrinal regression eval suite.

Public API:
    from jw_eval import Suite, GoldenCase, LayerResult, SuiteReport
"""

from jw_eval.models import GoldenCase, LayerResult, SuiteReport

__all__ = ["GoldenCase", "LayerResult", "Suite", "SuiteReport"]


def __getattr__(name: str):  # pragma: no cover - thin re-export
    if name == "Suite":
        from jw_eval.suite import Suite

        return Suite
    raise AttributeError(f"module 'jw_eval' has no attribute {name!r}")
