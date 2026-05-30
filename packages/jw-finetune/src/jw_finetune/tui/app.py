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


def _build_jw_library_theme() -> Any:
    """JW Library-inspired dark palette (eggplant + lavender)."""
    from textual.theme import Theme  # type: ignore[import-not-found]

    return Theme(
        name="jw-library",
        primary="#A78BB8",     # lavender — brand accent (icon, active tab)
        secondary="#7B6A92",   # muted purple
        accent="#C8AAD9",      # light lilac — highlights / hover
        foreground="#F2F2F2",  # body text
        background="#1F1730",  # deep eggplant — screen background
        surface="#352940",     # cards / containers
        panel="#42344E",       # sunken panels
        success="#7BC97E",
        warning="#F2C94C",
        error="#EB5757",
        dark=True,
    )


def build_wizard_app() -> Any:
    """Construct the Textual wizard app. Lazy-imports textual.

    Full editable wizard: 7 real screens (choose_preset, name, sources,
    base_model, hyperparams, synth, review) + done. Inputs prefill from
    the recipe and persist back to state when navigating with Ctrl+N/P.
    """
    _require_textual()
    from textual.app import App, ComposeResult  # type: ignore[import-not-found]
    from textual.binding import Binding  # type: ignore[import-not-found]
    from textual.containers import Horizontal, Vertical  # type: ignore[import-not-found]
    from textual.widgets import (  # type: ignore[import-not-found]
        Button, ContentSwitcher, Footer, Header, Input, Label, Static,
    )

    class WizardApp(App):  # type: ignore[misc]
        CSS = """
        Screen { background: $background; }
        #title { padding: 1 2; color: $primary; text-style: bold; }
        ContentSwitcher { padding: 1 2; }
        .step-title { color: $accent; text-style: bold; padding-bottom: 1; }
        .hint { color: $secondary; padding-top: 1; }
        .form-row { height: 3; padding-bottom: 1; }
        .form-label { width: 18; padding: 1 1 0 0; color: $primary; }
        .source-input { width: 1fr; }
        .source-lang { width: 10; margin-left: 1; }
        .source-add { width: 14; margin-left: 1; }
        .num-input { width: 22; }
        #preset_body, #sources_view, #review_body, #done_body {
            padding: 0 1;
        }
        """
        # Ctrl-* shortcuts fire even when an Input is focused. The bare-key
        # variants (n/p/s/q/d) are kept for the read-only screens (choose_preset,
        # review, done) where no Input has focus.
        BINDINGS = [
            Binding("ctrl+n", "next_step", "Next"),
            Binding("ctrl+p", "prev_step", "Prev"),
            Binding("ctrl+s", "save_recipe", "Save"),
            Binding("ctrl+d", "delete_source", "Del src"),
            Binding("ctrl+q", "quit", "Quit"),
            Binding("n", "next_step", "Next", show=False),
            Binding("p", "prev_step", "Prev", show=False),
            Binding("s", "save_recipe", "Save", show=False),
            Binding("q", "quit", "Quit", show=False),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.state = WizardState()

        def compose(self) -> ComposeResult:  # type: ignore[no-untyped-def]
            yield Header(show_clock=True)
            yield Label("jw-finetune wizard", id="title")
            with ContentSwitcher(initial="choose_preset", id="switcher"):
                with Vertical(id="choose_preset"):
                    yield Static("Paso 1 / 7 — Selecciona un preset", classes="step-title")
                    yield Static("", id="preset_body")
                with Vertical(id="name"):
                    yield Static("Paso 2 / 7 — Nombre del recipe", classes="step-title")
                    yield Static("Identificador corto: letras/números/guiones.", classes="hint")
                    yield Input(placeholder="my-jw-recipe", id="name_input")
                    yield Static("Enter o Ctrl+N: siguiente · Ctrl+P: anterior", classes="hint")
                with Vertical(id="sources"):
                    yield Static("Paso 3 / 7 — Fuentes de datos", classes="step-title")
                    yield Static("", id="sources_view")
                    with Horizontal(classes="form-row"):
                        yield Input(
                            placeholder="/ruta/archivo.jwpub o https://wol.jw.org/...",
                            id="source_path",
                            classes="source-input",
                        )
                        yield Input(placeholder="es", id="source_lang", classes="source-lang")
                        yield Button("Añadir", id="add_btn", variant="primary", classes="source-add")
                    yield Static(
                        "Enter añade · Ctrl+D borra último · Ctrl+N siguiente · Ctrl+P anterior",
                        classes="hint",
                    )
                with Vertical(id="base_model"):
                    yield Static("Paso 4 / 7 — Modelo base", classes="step-title")
                    yield Static("HuggingFace id (ej. unsloth/Llama-3.1-8B-Instruct).", classes="hint")
                    yield Input(id="base_model_input")
                    yield Static("Enter o Ctrl+N: siguiente · Ctrl+P: anterior", classes="hint")
                with Vertical(id="hyperparams"):
                    yield Static("Paso 5 / 7 — Hiperparámetros", classes="step-title")
                    with Horizontal(classes="form-row"):
                        yield Label("Epochs:", classes="form-label")
                        yield Input(id="hp_epochs", classes="num-input")
                    with Horizontal(classes="form-row"):
                        yield Label("LoRA rank:", classes="form-label")
                        yield Input(id="hp_lora_rank", classes="num-input")
                    with Horizontal(classes="form-row"):
                        yield Label("Learning rate:", classes="form-label")
                        yield Input(id="hp_lr", classes="num-input")
                    with Horizontal(classes="form-row"):
                        yield Label("Max seq len:", classes="form-label")
                        yield Input(id="hp_seq_len", classes="num-input")
                    with Horizontal(classes="form-row"):
                        yield Label("Batch size:", classes="form-label")
                        yield Input(id="hp_batch", classes="num-input")
                    yield Static(
                        "Vacío = mantener valor del preset. Ctrl+N: siguiente · Ctrl+P: anterior",
                        classes="hint",
                    )
                with Vertical(id="synth"):
                    yield Static("Paso 6 / 7 — Síntesis Q&A (solo SFT)", classes="step-title")
                    with Horizontal(classes="form-row"):
                        yield Label("Provider:", classes="form-label")
                        yield Input(placeholder="anthropic | ollama", id="synth_provider", classes="num-input")
                    with Horizontal(classes="form-row"):
                        yield Label("Modelo:", classes="form-label")
                        yield Input(placeholder="claude-haiku-4-5-20251001", id="synth_model")
                    with Horizontal(classes="form-row"):
                        yield Label("Q&A por chunk:", classes="form-label")
                        yield Input(id="synth_qa", classes="num-input")
                    yield Static(
                        "Ignorado si task=cpt. Ctrl+N: siguiente · Ctrl+P: anterior",
                        classes="hint",
                    )
                with Vertical(id="review"):
                    yield Static("Paso 7 / 7 — Revisión final", classes="step-title")
                    yield Static("", id="review_body")
                with Vertical(id="done"):
                    yield Static("", id="done_body")
            yield Footer()

        def on_mount(self) -> None:
            self.register_theme(_build_jw_library_theme())
            self.theme = "jw-library"
            self._render()

        # ── input / key handlers ─────────────────────────────────────

        def on_key(self, event) -> None:  # type: ignore[no-untyped-def]
            """In choose_preset, digits 1-9 select a preset and advance."""
            if self.state.step != "choose_preset":
                return
            if not (event.key.isdigit() and event.key != "0"):
                return
            idx = int(event.key) - 1
            presets = list_presets()
            if 0 <= idx < len(presets):
                self.state.select_preset(presets[idx])
                self._render()
                event.stop()

        def on_input_submitted(self, event) -> None:  # type: ignore[no-untyped-def]
            """Enter on the source_path input adds the source; elsewhere advances."""
            if self.state.step == "sources" and event.input.id == "source_path":
                self._add_source_from_inputs()
                return
            self.action_next_step()

        def on_button_pressed(self, event) -> None:  # type: ignore[no-untyped-def]
            if event.button.id == "add_btn" and self.state.step == "sources":
                self._add_source_from_inputs()

        # ── actions ──────────────────────────────────────────────────

        def action_next_step(self) -> None:
            self._save_current_step()
            if self.state.step == "choose_preset" and self.state.recipe is None:
                self.state.select_preset(list_presets()[0])
            elif self.state.step != "review":
                self.state.next_step()
            # From review, advancing is a no-op; explicit Ctrl+S saves and
            # transitions to "done".
            self._render()

        def action_prev_step(self) -> None:
            self._save_current_step()
            self.state.prev_step()
            self._render()

        def action_save_recipe(self) -> None:
            self._save_current_step()
            if self.state.recipe is None:
                return
            self.state.review()
            if self.state.errors:
                # Jump to review so the user can see the validation errors.
                self.state.step = "review"
                self._render()
                return
            out = Path("./recipe.yaml")
            recipe_to_yaml(self.state.recipe, out)
            self.state.step = "done"
            self._render()

        def action_delete_source(self) -> None:
            if (
                self.state.step == "sources"
                and self.state.recipe is not None
                and self.state.recipe.sources
            ):
                self.state.remove_source(len(self.state.recipe.sources) - 1)
                self._render_sources()

        # ── persistence between steps ────────────────────────────────

        def _save_current_step(self) -> None:
            """Read the current step's Inputs back into the wizard state."""
            if self.state.recipe is None:
                return
            step = self.state.step
            if step == "name":
                v = self._input_value("#name_input")
                if v:
                    self.state.update_name(v)
            elif step == "base_model":
                self.state.update_base_model(self._input_value("#base_model_input"))
            elif step == "hyperparams":
                self.state.update_hyperparams(
                    epochs=self._safe_int("#hp_epochs"),
                    lora_rank=self._safe_int("#hp_lora_rank"),
                    learning_rate=self._safe_float("#hp_lr"),
                    max_seq_len=self._safe_int("#hp_seq_len"),
                    batch_size=self._safe_int("#hp_batch"),
                )
            elif step == "synth":
                self.state.update_synth(
                    provider=self._input_value("#synth_provider") or None,
                    model=self._input_value("#synth_model") or None,
                    qa_per_chunk=self._safe_int("#synth_qa"),
                )

        def _load_current_step(self) -> None:
            """Prefill the current step's Inputs from the recipe."""
            r = self.state.recipe
            if r is None:
                return
            step = self.state.step
            if step == "name":
                self._set_input("#name_input", r.name)
            elif step == "base_model":
                self._set_input("#base_model_input", r.base_model)
            elif step == "hyperparams":
                self._set_input("#hp_epochs", str(r.epochs))
                self._set_input("#hp_lora_rank", str(r.lora_rank))
                self._set_input("#hp_lr", str(r.learning_rate))
                self._set_input("#hp_seq_len", str(r.max_seq_len))
                self._set_input("#hp_batch", str(r.batch_size))
            elif step == "synth":
                self._set_input("#synth_provider", r.synth_provider or "")
                self._set_input("#synth_model", r.synth_model or "")
                self._set_input("#synth_qa", str(r.qa_per_chunk))

        # ── small helpers ────────────────────────────────────────────

        def _input_value(self, selector: str) -> str:
            try:
                return self.query_one(selector, Input).value.strip()
            except Exception:  # noqa: BLE001
                return ""

        def _set_input(self, selector: str, value: str) -> None:
            try:
                self.query_one(selector, Input).value = value
            except Exception:  # noqa: BLE001
                pass

        def _safe_int(self, selector: str) -> int | None:
            v = self._input_value(selector)
            try:
                return int(v) if v else None
            except ValueError:
                return None

        def _safe_float(self, selector: str) -> float | None:
            v = self._input_value(selector)
            try:
                return float(v) if v else None
            except ValueError:
                return None

        def _add_source_from_inputs(self) -> None:
            if self.state.recipe is None:
                return
            path = self._input_value("#source_path")
            if not path:
                return
            default_lang = (
                self.state.recipe.languages[0] if self.state.recipe.languages else "es"
            )
            lang = self._input_value("#source_lang") or default_lang
            self.state.add_source(_detect_source_kind(path), path, lang)
            self._set_input("#source_path", "")
            self._set_input("#source_lang", "")
            try:
                self.query_one("#source_path", Input).focus()
            except Exception:  # noqa: BLE001
                pass
            self._render_sources()

        # ── rendering ────────────────────────────────────────────────

        def _render(self) -> None:
            try:
                self.query_one("#switcher", ContentSwitcher).current = self.state.step
            except Exception:  # noqa: BLE001
                # Not yet mounted (headless test path) — skip.
                return
            if self.state.step == "choose_preset":
                self._render_choose_preset()
            elif self.state.step == "sources":
                self._render_sources()
            elif self.state.step == "review":
                self._render_review()
            elif self.state.step == "done":
                self._render_done()
            self._load_current_step()
            self._auto_focus()

        def _render_choose_preset(self) -> None:
            body = self.query_one("#preset_body", Static)
            presets = list_presets()
            current = self.state.recipe.name if self.state.recipe else None
            lines = []
            for i, name in enumerate(presets, start=1):
                r = get_preset(name)
                marker = "▸" if name == current else " "
                lines.append(
                    f"  {marker} [{i}] {name}  ({r.task}, {','.join(r.languages)})"
                )
            lines += [
                "",
                f"Pulsa 1-{len(presets)} para elegir · Ctrl+N: siguiente (default = primero) · Ctrl+Q: salir",
            ]
            body.update("\n".join(lines))

        def _render_sources(self) -> None:
            body = self.query_one("#sources_view", Static)
            if self.state.recipe is None or not self.state.recipe.sources:
                body.update(
                    "(sin fuentes — escribe una ruta o URL abajo y pulsa Enter o Añadir)"
                )
                return
            lines = [f"Fuentes ({len(self.state.recipe.sources)}):"]
            for i, s in enumerate(self.state.recipe.sources, start=1):
                lines.append(
                    f"  [{i}] {s.kind:<11}  {s.language:<4}  {s.path}"
                )
            body.update("\n".join(lines))

        def _render_review(self) -> None:
            self.state.review()
            body = self.query_one("#review_body", Static)
            lines: list[str] = []
            if self.state.recipe is not None:
                r = self.state.recipe
                lines += [
                    f"  name         : {r.name}",
                    f"  task         : {r.task}",
                    f"  languages    : {r.languages}",
                    f"  base_model   : {r.base_model}",
                    f"  epochs       : {r.epochs}",
                    f"  lora_rank    : {r.lora_rank}",
                    f"  learning_rate: {r.learning_rate}",
                    f"  max_seq_len  : {r.max_seq_len}",
                    f"  batch_size   : {r.batch_size}",
                    f"  sources      : {len(r.sources)} archivo(s)",
                ]
                for s in r.sources:
                    lines.append(f"     - {s.kind} ({s.language}) {s.path}")
                if r.task == "sft":
                    lines += [
                        f"  qa_style     : {r.qa_style}",
                        f"  synth        : {r.synth_provider}/{r.synth_model or '(default)'}",
                        f"  qa_per_chunk : {r.qa_per_chunk}",
                    ]
            if self.state.errors:
                lines += ["", "Errores:"]
                lines += [f"  ✗ {e}" for e in self.state.errors]
                lines += ["", "Ctrl+P: corregir · Ctrl+Q: salir"]
            else:
                lines += [
                    "",
                    "✓ Recipe válido.",
                    "Ctrl+S: guardar ./recipe.yaml · Ctrl+P: editar · Ctrl+Q: salir",
                ]
            body.update("\n".join(lines))

        def _render_done(self) -> None:
            body = self.query_one("#done_body", Static)
            out = Path("./recipe.yaml").resolve()
            body.update(
                f"✓ Recipe guardado en:\n  {out}\n\n"
                "Siguiente paso:\n"
                "  jw-finetune prepare --recipe-file recipe.yaml \\\n"
                "                      -s <ruta a un .jwpub o .epub>\n\n"
                "Ctrl+Q o q para salir."
            )

        def _auto_focus(self) -> None:
            focus_map = {
                "name": "#name_input",
                "sources": "#source_path",
                "base_model": "#base_model_input",
                "hyperparams": "#hp_epochs",
                "synth": "#synth_provider",
            }
            sel = focus_map.get(self.state.step)
            if sel is None:
                return
            try:
                self.query_one(sel, Input).focus()
            except Exception:  # noqa: BLE001
                pass

    return WizardApp()


def _detect_source_kind(path: str) -> str:
    """Map a path or URL to a SourceKind. Defaults to 'jwpub'."""
    p = path.lower().strip()
    if p.endswith(".jwpub"):
        return "jwpub"
    if p.endswith(".epub"):
        return "epub"
    if p.endswith(".txt") or p.endswith(".md"):
        return "raw-text"
    if "wol.jw.org" in p and ("/b/r" in p or "nwt" in p):
        return "wol-bible"
    if "wol.jw.org" in p:
        return "wol-article"
    return "jwpub"


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
            self.register_theme(_build_jw_library_theme())
            self.theme = "jw-library"
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
