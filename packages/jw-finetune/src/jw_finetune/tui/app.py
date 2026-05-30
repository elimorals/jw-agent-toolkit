"""Textual TUI app: recipe wizard + live training monitor inline.

Two screens:
  * WizardScreen — step-by-step recipe builder backed by `wizard.WizardState`
  * MonitorScreen — tails events.jsonl and shows live loss + system metrics
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

from jw_finetune.recipes.base import recipe_to_yaml
from jw_finetune.recipes.presets import get_preset, list_presets
from jw_finetune.tui.wizard import WizardState


def _require_textual() -> None:
    try:
        import textual  # noqa: F401  # type: ignore[import-not-found]
    except ImportError as e:
        raise ImportError(
            "textual required: install with `--extra tui`"
        ) from e


def build_wizard_app() -> Any:
    """Construct the Textual wizard app. Lazy-imports textual."""
    _require_textual()
    from textual.app import App, ComposeResult  # type: ignore[import-not-found]
    from textual.binding import Binding  # type: ignore[import-not-found]
    from textual.containers import Horizontal, Vertical  # type: ignore[import-not-found]
    from textual.widgets import (  # type: ignore[import-not-found]
        Button, Footer, Header, Input, Label, ListItem, ListView, Static,
    )

    class WizardApp(App):  # type: ignore[misc]
        CSS = """
        Screen { background: $surface; }
        #title { padding: 1 2; color: $accent; text-style: bold; }
        #body { padding: 1 2; }
        #footer-help { padding: 1 2; color: $text-muted; }
        .stat-row { padding: 0 1; }
        """
        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("n", "next_step", "Next"),
            Binding("p", "prev_step", "Prev"),
            Binding("s", "save_recipe", "Save"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.state = WizardState()
            self.preset_list: ListView | None = None
            self.body: Static | None = None

        def compose(self) -> ComposeResult:  # type: ignore[no-untyped-def]
            yield Header(show_clock=True)
            yield Label("jw-finetune wizard", id="title")
            yield Static("", id="body")
            yield Footer()

        def on_mount(self) -> None:
            self.body = self.query_one("#body", Static)
            self._render()

        def _render(self) -> None:
            assert self.body is not None
            if self.state.step == "choose_preset":
                lines = ["Selecciona un preset (escribe el número y Enter):", ""]
                for i, name in enumerate(list_presets(), start=1):
                    r = get_preset(name)
                    lines.append(f"  [{i}] {name}  ({r.task}, {','.join(r.languages)})")
                lines.append("")
                lines.append("Atajos: n=siguiente, p=anterior, s=guardar, q=salir")
                self.body.update("\n".join(lines))
            elif self.state.step == "review":
                self.state.review()
                lines = ["Revisión final:", ""]
                if self.state.recipe is not None:
                    r = self.state.recipe
                    lines += [
                        f"  name       : {r.name}",
                        f"  task       : {r.task}",
                        f"  languages  : {r.languages}",
                        f"  base_model : {r.base_model}",
                        f"  epochs     : {r.epochs}",
                        f"  lora_rank  : {r.lora_rank}",
                        f"  sources    : {len(r.sources)} archivo(s)",
                    ]
                if self.state.errors:
                    lines += ["", "Errores:"]
                    lines += [f"  ✗ {e}" for e in self.state.errors]
                else:
                    lines += ["", "✓ recipe válido — presiona 's' para guardar."]
                self.body.update("\n".join(lines))
            elif self.state.step == "done":
                self.body.update("✓ Listo. Pulsa 'q' para salir.")
            else:
                self.body.update(
                    f"Paso: {self.state.step}\n\n"
                    "Esta versión MVP del wizard se completa con presets directamente.\n"
                    "Para personalización avanzada usa `jw-finetune init` y edita el YAML."
                )

        def action_next_step(self) -> None:
            if self.state.step == "choose_preset" and self.state.recipe is None:
                # Default to first preset if user didn't select
                self.state.select_preset(list_presets()[0])
            self.state.next_step()
            self._render()

        def action_prev_step(self) -> None:
            self.state.prev_step()
            self._render()

        def action_save_recipe(self) -> None:
            if self.state.recipe is None:
                return
            self.state.review()
            if self.state.errors:
                self._render()
                return
            out = Path("./recipe.yaml")
            recipe_to_yaml(self.state.recipe, out)
            self.state.step = "done"
            self._render()

    return WizardApp()


def build_monitor_app(events_path: Path) -> Any:
    """Build a Textual monitor app that tails events.jsonl in-terminal."""
    _require_textual()
    from textual.app import App, ComposeResult  # type: ignore[import-not-found]
    from textual.binding import Binding  # type: ignore[import-not-found]
    from textual.widgets import Footer, Header, Static  # type: ignore[import-not-found]

    class MonitorApp(App):  # type: ignore[misc]
        BINDINGS = [Binding("q", "quit", "Quit")]
        CSS = """
        #stats { padding: 1 2; height: auto; }
        #log { padding: 1 2; }
        """

        def __init__(self) -> None:
            super().__init__()
            self.events_path = events_path
            self.last_pos = 0
            self.events: deque[dict[str, Any]] = deque(maxlen=200)
            self.last_loss: float | None = None
            self.last_step: int | None = None
            self.stats_widget: Static | None = None
            self.log_widget: Static | None = None

        def compose(self) -> ComposeResult:  # type: ignore[no-untyped-def]
            yield Header(show_clock=True)
            yield Static("waiting…", id="stats")
            yield Static("", id="log")
            yield Footer()

        def on_mount(self) -> None:
            self.stats_widget = self.query_one("#stats", Static)
            self.log_widget = self.query_one("#log", Static)
            self.set_interval(0.5, self._poll)

        def _poll(self) -> None:
            if not self.events_path.exists():
                return
            try:
                size = self.events_path.stat().st_size
            except OSError:
                return
            if size < self.last_pos:
                self.last_pos = 0
            if size == self.last_pos:
                return
            with self.events_path.open("r", encoding="utf-8") as f:
                f.seek(self.last_pos)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self._consume(ev)
                self.last_pos = f.tell()
            self._render()

        def _consume(self, ev: dict[str, Any]) -> None:
            self.events.append(ev)
            if "loss" in ev:
                try:
                    self.last_loss = float(ev["loss"])
                except (TypeError, ValueError):
                    pass
            if "step" in ev:
                try:
                    self.last_step = int(ev["step"])
                except (TypeError, ValueError):
                    pass

        def _render(self) -> None:
            assert self.stats_widget is not None and self.log_widget is not None
            loss_s = f"{self.last_loss:.4f}" if self.last_loss is not None else "n/a"
            step_s = str(self.last_step) if self.last_step is not None else "n/a"
            self.stats_widget.update(
                f"step: {step_s}    loss: {loss_s}    events: {len(self.events)}"
            )
            # Show last 30 events compactly
            lines = []
            for ev in list(self.events)[-30:]:
                kind = ev.get("kind", "?")
                step = ev.get("step", "")
                loss = ev.get("loss")
                loss_str = f"loss={loss:.4f}" if isinstance(loss, (int, float)) else ""
                lines.append(f"  {kind:<14} step={step:<6} {loss_str}")
            self.log_widget.update("\n".join(lines) or "no events yet")

    return MonitorApp()
