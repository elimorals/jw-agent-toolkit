"""Placeholder — filled in Task 6."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class ConstrainedCaller(Protocol):  # pragma: no cover - replaced in Task 6
    async def is_available(self) -> bool: ...

    async def generate(
        self,
        prompt: str,
        *,
        grammar: str | None = None,
        json_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> str: ...


def get_default_constrained_caller(*_args: Any, **_kwargs: Any) -> Any:  # pragma: no cover
    raise NotImplementedError("filled in Task 6")
