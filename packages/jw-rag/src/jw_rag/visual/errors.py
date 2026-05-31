"""Errors specific to the visual RAG subsystem.

`ConfigError` is raised when the user asks for a real visual embedder but no
GPU/MLX backend is reachable. Message must be actionable and include the
exact install command.

`VisualStoreMismatchError` is raised by `VisualVectorStore.load()` when the
persisted store on disk was produced by a different model/revision/patch_size
than the embedder passed at load time.
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """No usable hardware for ColPali/ColQwen2 visual embeddings.

    Message includes the install commands for NVIDIA (`uv sync --extra visual`)
    and Apple Silicon (`uv sync --extra visual-mlx`), plus the env var to
    disable the subsystem entirely (`JW_VISUAL_ENABLED=0`).
    """


class VisualStoreMismatchError(RuntimeError):
    """On-disk store was produced by a different model/revision/patch_size."""
