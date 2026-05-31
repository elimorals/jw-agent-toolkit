"""`jw gen` CLI subcommands.

Three commands: `image`, `audio`, `video`. All three follow the same shape:

    1. Parse flags into a GenerationRequest (with WatermarkConfig).
    2. Run safety.evaluate(request) → SafetyDecision.
    3. If voice_clone requested, run refuse_voice_cloning_without_double_optin
       with interactive prompt.
    4. Resolve provider via factory.get_provider(kind, provider=...).
    5. Show cost estimate; if above threshold, confirm.
    6. Provider returns raw path.
    7. policy.finalize_output(raw, request, dest, provider) → result.
    8. Echo result.

The CLI is also where `--no-visible-watermark` and `--realistic-people`
hand off audit-trail responsibility.
"""

from __future__ import annotations

import os
from pathlib import Path

import typer

from jw_gen.audit import audit_log_path
from jw_gen.factory import NoProviderAvailable, get_provider
from jw_gen.i18n import get_message
from jw_gen.models import GenerationRequest, Language, WatermarkConfig
from jw_gen.policy import PolicyError, finalize_output
from jw_gen.safety import (
    SafetyRefused,
    evaluate,
    refuse_voice_cloning_without_double_optin,
)

gen_app = typer.Typer(
    name="gen",
    help="Generate illustrative content for personal use.",
    no_args_is_help=True,
)


def _build_watermark(no_visible: bool, no_watermark: bool) -> WatermarkConfig:
    if no_watermark:
        return WatermarkConfig(mode="off")
    if no_visible:
        return WatermarkConfig(mode="metadata-only")
    return WatermarkConfig()


def _confirm_cost(cost_usd: float, lang: Language) -> bool:
    threshold = float(os.environ.get("JW_GEN_COST_CONFIRM_THRESHOLD_USD", "1.0"))
    if cost_usd < threshold:
        return True
    answer = typer.prompt(get_message("cli.cost_confirm", lang=lang, usd=cost_usd))
    return answer.strip().lower() in {"y", "yes", "si", "sí", "sim", "s"}


def _run(
    *,
    kind: str,
    prompt: str,
    lang: str,
    out: Path,
    provider_name: str | None,
    no_visible_watermark: bool,
    no_watermark: bool,
    realistic_people: bool,
    voice_clone: bool,
    input_audio: Path | None,
) -> None:
    if no_watermark and not os.environ.get("JW_GEN_ALLOW_NO_WATERMARK"):
        typer.echo(
            "error: --no-watermark requires env JW_GEN_ALLOW_NO_WATERMARK=1 (audit-logged).",
            err=True,
        )
        raise typer.Exit(code=2)

    request = GenerationRequest(
        prompt=prompt,
        kind=kind,  # type: ignore[arg-type]
        lang=lang,  # type: ignore[arg-type]
        watermark=_build_watermark(no_visible_watermark, no_watermark),
        realistic_people_optin=realistic_people,
        voice_clone_source=input_audio if voice_clone else None,
    )

    # 1) Safety
    decision = evaluate(request)
    if not decision.allow:
        typer.echo(
            get_message(decision.reason or "safety.refuse.logo", lang=request.lang),
            err=True,
        )
        raise typer.Exit(code=10)

    # 2) Voice clone double opt-in (audio only)
    if voice_clone:
        if input_audio is None:
            typer.echo("error: --voice-clone requires --input AUDIO_PATH", err=True)
            raise typer.Exit(code=11)
        try:
            refuse_voice_cloning_without_double_optin(
                audio_src=input_audio,
                voice_clone_flag=True,
                interactive_confirm=lambda q: typer.prompt(q).strip().lower() in {"si", "sí", "yes", "y", "sim", "s"},
                lang=request.lang,
            )
        except SafetyRefused as exc:
            typer.echo(get_message(exc.reason, lang=request.lang), err=True)
            raise typer.Exit(code=12) from exc

    # 3) Provider routing
    try:
        provider = get_provider(kind, provider=provider_name)  # type: ignore[arg-type]
    except NoProviderAvailable as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=13) from exc

    # 4) Cost confirm
    cost = provider.cost_estimate(request)
    if not _confirm_cost(cost.usd, lang=request.lang):
        typer.echo("aborted by user")
        raise typer.Exit(code=14)

    # 5) Generate
    try:
        raw_path = provider.generate(request.model_copy(update={"prompt": decision.augmented_prompt or request.prompt}))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"provider failed: {exc!r}", err=True)
        raise typer.Exit(code=15) from exc

    # 6) Finalize
    try:
        result = finalize_output(
            raw_path=raw_path,
            request=request,
            dest=out,
            provider=provider.name,
        )
    except PolicyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=16) from exc

    typer.echo(f"OK {result.output_path}")
    typer.echo(f"  disclaimer: {result.disclaimer_path}")
    typer.echo(f"  audit:      {audit_log_path()}#audit_id={result.audit_id}")


@gen_app.command("image")
def gen_image(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
    realistic_people: bool = typer.Option(False, "--realistic-people"),
) -> None:
    _run(
        kind="image",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=realistic_people,
        voice_clone=False,
        input_audio=None,
    )


@gen_app.command("audio")
def gen_audio(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    voice_clone: bool = typer.Option(False, "--voice-clone"),
    input_audio: Path | None = typer.Option(None, "--input"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
) -> None:
    _run(
        kind="audio",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=False,
        voice_clone=voice_clone,
        input_audio=input_audio,
    )


@gen_app.command("video")
def gen_video(
    prompt: str = typer.Option(..., "--prompt"),
    out: Path = typer.Option(..., "--out"),
    lang: str = typer.Option("es", "--lang"),
    provider: str | None = typer.Option(None, "--provider"),
    duration: float = typer.Option(6.0, "--duration"),
    no_visible_watermark: bool = typer.Option(False, "--no-visible-watermark"),
    no_watermark: bool = typer.Option(False, "--no-watermark"),
    realistic_people: bool = typer.Option(False, "--realistic-people"),
) -> None:
    _ = duration  # passed via extras if a provider needs it
    _run(
        kind="video",
        prompt=prompt,
        lang=lang,
        out=out,
        provider_name=provider,
        no_visible_watermark=no_visible_watermark,
        no_watermark=no_watermark,
        realistic_people=realistic_people,
        voice_clone=False,
        input_audio=None,
    )
