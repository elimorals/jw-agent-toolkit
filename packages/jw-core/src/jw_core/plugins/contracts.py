"""Five Protocols + EntryPointSpec dataclass.

Protocols are `runtime_checkable` and structural — third-party plugins
don't need to import anything from jw-agent-toolkit, they just need to
match the shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class EntryPointSpec:
    """Lazy descriptor for one entry point."""

    name: str
    group: str
    module: str
    attr: str
    dist_name: str
    dist_version: str

    @property
    def namespaced_name(self) -> str:
        return f"{self.dist_name}:{self.name}"

    def resolve(self) -> Any:
        mod = import_module(self.module)
        return getattr(mod, self.attr)


@runtime_checkable
class AgentPlugin(Protocol):
    """A pluggable agent. Required: `__name__: str` + async `__call__(**kwargs)`."""

    __name__: str

    def __call__(self, **kwargs: Any) -> Any: ...


@runtime_checkable
class ParserPlugin(Protocol):
    """A pluggable document parser."""

    def __call__(
        self,
        raw: bytes | str,
        *,
        source_url: str | None = None,
    ) -> Any: ...


@runtime_checkable
class EmbedderPlugin(Protocol):
    """Mirrors jw_rag.embed_providers.factory.EmbedProvider for plugin registration."""

    name: str
    target: str
    dim: int

    def is_available(self) -> bool: ...

    def embed(self, texts: list[str]) -> Any: ...


@runtime_checkable
class VLMProviderPlugin(Protocol):
    """Mirrors jw_core.vision.VLMProvider."""

    name: str

    def is_available(self) -> bool: ...

    def describe(self, image_bytes: bytes, *, language: str = "en") -> str: ...


@runtime_checkable
class GenProviderPlugin(Protocol):
    """Mirrors jw_gen.GenerationProvider."""

    name: str

    def is_available(self) -> bool: ...

    def generate(self, prompt: str, *, max_tokens: int = 128) -> str: ...
