"""JWMonitorCallback — emits structured events for the F2 dashboard.

Persists events as JSONL under `workspace/events.jsonl`. The F2 dashboard
tails that file via WebSocket. The event schema is flat and stable so
the consumer can evolve independently of the producer.

When `transformers` is installed (i.e., the GPU stack), this class
subclasses `transformers.TrainerCallback` so we pick up new callback
hooks automatically as the library evolves. When transformers isn't
available (data-prep-only install), we fall back to a plain class —
duck typing still works for any trainer that calls our methods.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Use the toolkit's structured logging helper when available so training
# events also surface in the consolidated jw-* observability stream.
try:
    from jw_core.observability.logging_setup import (  # type: ignore[import-not-found]
        log_event as _toolkit_log_event,
    )
    _HAS_TOOLKIT_OBS = True
except ImportError:
    _toolkit_log_event = None  # type: ignore[assignment]
    _HAS_TOOLKIT_OBS = False


# Subclass TrainerCallback when available so we inherit any new hooks.
try:
    from transformers import TrainerCallback  # type: ignore[import-not-found]
    _CALLBACK_BASE: type = TrainerCallback
except ImportError:
    _CALLBACK_BASE = object


class JWMonitorCallback(_CALLBACK_BASE):  # type: ignore[misc, valid-type]
    """Append-only event log for the training run."""

    def __init__(self, workspace: Path | str) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.events_path = self.workspace / "events.jsonl"
        self._t_start = time.time()

    def _emit(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", time.time())
        event.setdefault("elapsed", round(time.time() - self._t_start, 3))
        try:
            with self.events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.warning("JWMonitorCallback failed to write event: %s", e)

        # Also publish to the toolkit's structured logging stream if the
        # user opted in via `jw_core.observability.configure_logging`. This
        # is fire-and-forget; failures are logged at debug level only.
        if _HAS_TOOLKIT_OBS and _toolkit_log_event is not None:
            try:
                _toolkit_log_event(
                    logger,
                    event=f"jw_finetune.{event.get('kind', 'log')}",
                    **{k: v for k, v in event.items() if k != "kind"},
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("toolkit log_event failed: %s", e)

    # HuggingFace TrainerCallback API surface (duck-typed).
    def on_train_begin(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
        self._emit({"kind": "train_begin"})

    def on_step_end(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
        logs = kw.get("logs") or {}
        self._emit({"kind": "step", "step": getattr(state, "global_step", -1), **logs})

    def on_log(
        self,
        args: Any,
        state: Any,
        control: Any,
        logs: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        self._emit({
            "kind": "log",
            "step": getattr(state, "global_step", -1),
            **(logs or {}),
        })

    def on_evaluate(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
        metrics = kw.get("metrics") or {}
        self._emit({"kind": "evaluate", "step": getattr(state, "global_step", -1), **metrics})

    def on_save(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
        self._emit({"kind": "save", "step": getattr(state, "global_step", -1)})

    def on_train_end(self, args: Any, state: Any, control: Any, **kw: Any) -> None:
        self._emit({"kind": "train_end", "global_step": getattr(state, "global_step", -1)})
