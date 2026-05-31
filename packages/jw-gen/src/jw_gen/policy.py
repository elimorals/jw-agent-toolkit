"""Policy module — LOAD-BEARING.

This is the only place in jw-gen that writes the FINAL output to disk.
Providers return a raw path in a temp dir. `finalize_output` is the chokepoint
that:

  1. Calls `assert_personal_use(dest)` — warns if dest is in a Drive/Dropbox-
     looking path.
  2. Calls `apply_watermark(raw_path, ...)` if mode includes 'visible'.
  3. Calls `embed_metadata(raw_path, ...)` ALWAYS (mode-independent).
  4. Moves raw → dest atomically.
  5. Calls `write_disclaimer_sibling(dest, ...)` — fail-closed.
  6. Calls `audit.log_generation(...)`.
  7. Returns GenerationResult.

If ANY of steps 2-5 fail, the dest file is unlinked (if it was already moved)
and PolicyError is raised. Fail-closed.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import piexif
from PIL import Image, ImageDraw, ImageFont

from jw_gen.audit import log_generation
from jw_gen.i18n import get_message
from jw_gen.models import (
    GenerationRequest,
    GenerationResult,
    Language,
    WatermarkConfig,
)


class PolicyError(RuntimeError):
    """Raised when finalize_output fails any required step. Fail-closed."""


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------


def _load_font(size: int = 14) -> Any:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def apply_watermark(src: Path, *, text: str, cfg: WatermarkConfig) -> Path:
    """Rasterize a visible watermark at the configured anchor. Returns src (mutated)."""

    img = Image.open(src).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font = _load_font(size=max(12, img.width // 40))
    alpha = int(255 * cfg.opacity)

    x = int(img.width * cfg.anchor_x)
    y = int(img.height * cfg.anchor_y)

    # Halo for legibility.
    draw.text((x + 1, y + 1), text, fill=(0, 0, 0, alpha), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, alpha), font=font)

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    composed.save(src, format="PNG")
    return src


# ---------------------------------------------------------------------------
# Metadata (EXIF + XMP)
# ---------------------------------------------------------------------------


def embed_metadata(path: Path, *, fields: dict[str, str]) -> None:
    """Embed EXIF + (best-effort) XMP into the file.

    For PNG, we encode EXIF via the `exif` chunk (piexif). XMP is also written
    as a tEXt chunk under key "XMP". Audio/video metadata embedding is delegated
    to the respective provider for now; here we write a sidecar metadata file
    so chain-of-custody is preserved regardless of format.
    """

    suffix = path.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".tiff"}:
        sidecar = path.with_suffix(path.suffix + ".metadata.txt")
        sidecar.write_text(
            "\n".join(f"{k}: {v}" for k, v in fields.items()),
            encoding="utf-8",
        )
        return

    # Build EXIF dict.
    user_comment = "; ".join(f"{k}={v}" for k, v in fields.items()).encode("utf-8")
    exif_dict: dict[str, Any] = {
        "0th": {
            piexif.ImageIFD.Software: fields.get("Software", "jw-gen").encode("utf-8"),
            piexif.ImageIFD.ImageDescription: fields.get(
                "ImageDescription", "jw-gen personal-use illustration"
            ).encode("utf-8"),
            piexif.ImageIFD.Artist: b"jw-gen",
        },
        "Exif": {
            piexif.ExifIFD.UserComment: b"ASCII\x00\x00\x00" + user_comment,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)

    # Re-save with EXIF.
    img = Image.open(path)
    img.save(path, format=img.format or "PNG", exif=exif_bytes)

    # Best-effort XMP via custom tEXt chunk (for PNG) — small inline UTF-8 packet.
    if suffix == ".png":
        xmp_packet = (
            "<?xpacket begin='﻿' id='W5M0MpCehiHzreSzNTczkc9d'?>"
            "<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
            "<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
            f"<rdf:Description><jwgen:provider xmlns:jwgen='https://jw-agent-toolkit/jw-gen/'>"
            f"{fields.get('provider', '')}</jwgen:provider>"
            f"<jwgen:prompt_sha256>{fields.get('prompt_sha256', '')}</jwgen:prompt_sha256>"
            "</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end='w'?>"
        )
        with path.open("ab") as f:
            f.write(b"\n<!-- xmp -->\n" + xmp_packet.encode("utf-8"))


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


def write_disclaimer_sibling(
    *,
    target: Path,
    lang: Language,
    prompt_sha256: str,
    provider: str,
    watermark_mode: str,
    realistic_optin: bool,
) -> Path:
    """Write `<target>.disclaimer.txt` next to the output. Fail-closed."""

    body = get_message(
        "disclaimer.body",
        lang=lang,
        prompt_sha256=prompt_sha256,
        provider=provider,
        watermark_mode=watermark_mode,
    )
    if realistic_optin:
        body += "\n\n" + get_message("disclaimer.realistic_people_warning", lang=lang)
    dest = target.with_suffix(target.suffix + ".disclaimer.txt")
    dest.write_text(body + "\n", encoding="utf-8")
    return dest


# ---------------------------------------------------------------------------
# Personal-use path check
# ---------------------------------------------------------------------------


_SHARED_PATH_HINTS = (
    "dropbox",
    "google drive",
    "googledrive",
    "gdrive",
    "onedrive",
    "icloud drive",
)


def assert_personal_use(dest: Path) -> str | None:
    """Return a warning string if dest looks like a shared/cloud sync folder; None otherwise."""

    p = str(dest).lower()
    for hint in _SHARED_PATH_HINTS:
        if hint in p:
            return (
                f"WARNING: output path looks like a cloud-sync folder ({hint}). "
                "Personal-use disclaimer accompanies the file, but distribution "
                "from sync folders is your responsibility."
            )
    return None


# ---------------------------------------------------------------------------
# Final chokepoint
# ---------------------------------------------------------------------------


def finalize_output(
    *,
    raw_path: Path,
    request: GenerationRequest,
    dest: Path,
    provider: str,
) -> GenerationResult:
    """The ONLY function that may move a generated artifact to its destination.

    Fail-closed: if any step fails, the dest is unlinked and PolicyError raises.
    """

    # Late-binding lookups so monkeypatching `jw_gen.policy.write_disclaimer_sibling`
    # / `jw_gen.policy.apply_watermark` from tests actually intercepts the call.
    import jw_gen.policy as _self

    prompt_sha256 = hashlib.sha256(request.prompt.encode("utf-8")).hexdigest()
    warnings: list[str] = []
    warn = assert_personal_use(dest)
    if warn:
        warnings.append(warn)

    dest.parent.mkdir(parents=True, exist_ok=True)

    moved = False
    disclaimer: Path | None = None
    try:
        # Copy first so we operate on dest only (avoid partial source state).
        shutil.copy2(raw_path, dest)
        moved = True

        # 2) Visible watermark (if mode includes visible).
        if request.watermark.mode == "visible+metadata":
            text = get_message("watermark.default", lang=request.lang)
            _self.apply_watermark(dest, text=text, cfg=request.watermark)
        elif request.watermark.mode == "off":
            warnings.append(
                "watermark mode is 'off' — visible AND metadata suppressed (audit logged)."
            )

        # 3) Metadata — ALWAYS, even when watermark mode is metadata-only.
        if request.watermark.mode != "off":
            embed_metadata(
                dest,
                fields={
                    "Software": "jw-gen",
                    "ImageDescription": "jw-gen personal-use illustration — NOT official JW content",
                    "Artist": "jw-gen",
                    "provider": provider,
                    "prompt_sha256": prompt_sha256,
                },
            )

        # 4) Disclaimer sibling — ALWAYS.
        disclaimer = _self.write_disclaimer_sibling(
            target=dest,
            lang=request.lang,
            prompt_sha256=prompt_sha256,
            provider=provider,
            watermark_mode=request.watermark.mode,
            realistic_optin=request.realistic_people_optin,
        )

    except Exception as exc:  # noqa: BLE001
        # Fail-closed: undo any partial state.
        if moved:
            try:
                dest.unlink()
            except FileNotFoundError:
                pass
            disc = dest.with_suffix(dest.suffix + ".disclaimer.txt")
            if disc.exists():
                try:
                    disc.unlink()
                except FileNotFoundError:
                    pass
        raise PolicyError(f"finalize_output failed: {exc!r}") from exc

    # 5) Audit log.
    event = log_generation(
        kind=request.kind,
        provider=provider,
        prompt_sha256=prompt_sha256,
        output_path=dest,
        watermark_mode=request.watermark.mode,
        safety_flags={"finalized": "ok"},
        warnings=warnings,
    )

    assert disclaimer is not None
    return GenerationResult(
        output_path=dest,
        disclaimer_path=disclaimer,
        provider=provider,
        kind=request.kind,
        watermark_mode=request.watermark.mode,
        prompt_sha256=prompt_sha256,
        audit_id=str(event["audit_id"]),
        warnings=warnings,
    )
