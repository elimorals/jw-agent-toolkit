"""Visual fingerprint: era detection + visual anomalies (Fase 70).

Heuristics applied to a VLM caption + raw OCR text. Conservative: we
prefer false negatives (no anomaly flagged) over false positives
(wrongly flagging a real image as suspicious).
"""

from __future__ import annotations

import re


def detect_apparent_era(
    vlm_description: str, ocr_text: str
) -> str | None:
    """Detect the apparent decade from layout / copyright hints.

    Returns one of the canonical strings ("1970s", ..., "2020s") or None
    when no signal is strong enough.
    """
    bag = f"{vlm_description}\n{ocr_text}".lower()
    # Copyright year markers
    m = re.search(r"\bcopyright[^\d]*(19\d{2}|20\d{2})", bag)
    if m:
        year = int(m.group(1))
        decade = year // 10 * 10
        return f"{decade}s"
    m = re.search(r"©\s*(19\d{2}|20\d{2})", bag)
    if m:
        year = int(m.group(1))
        return f"{year // 10 * 10}s"

    # Stylistic markers from VLM caption
    style_markers: tuple[tuple[str, str], ...] = (
        ("serif heavy", "1970s"),
        ("fluffy clouds", "1970s"),
        ("primary colors bold", "1980s"),
        ("pixelated logo", "1990s"),
        ("modern clean layout", "2010s"),
        ("flat ui", "2020s"),
    )
    for marker, decade in style_markers:
        if marker in bag:
            return decade
    return None


def detect_apparent_publication(
    vlm_description: str, ocr_text: str
) -> str | None:
    """Detect which JW publication the image purports to be from."""
    bag = f"{vlm_description}\n{ocr_text}"
    titles = [
        ("Atalaya", "Atalaya"),
        ("Watchtower", "Watchtower"),
        ("Despertad", "Despertad"),
        ("Awake!", "Awake!"),
        ("Sentinela", "Sentinela"),
        ("¡Despertad!", "Despertad"),
    ]
    for needle, canonical in titles:
        if needle in bag:
            return canonical
    return None


def detect_visual_anomalies(
    vlm_description: str, ocr_text: str
) -> list[str]:
    """List of suspected anomalies that suggest manipulation.

    Each anomaly is a short label. Empty list = no concerning signal.
    """
    bag = f"{vlm_description}\n{ocr_text}".lower()
    anomalies: list[str] = []

    # Font / typography inconsistencies
    if "font mismatch" in bag or "different font" in bag:
        anomalies.append("font_mismatch")
    if "wrong font" in bag:
        anomalies.append("wrong_font")

    # Logo manipulation
    if "logo modified" in bag or "altered logo" in bag:
        anomalies.append("logo_modified")
    if "wrong logo proportions" in bag:
        anomalies.append("logo_proportions")

    # Layout inconsistencies
    if "inconsistent layout" in bag or "misaligned" in bag:
        anomalies.append("layout_inconsistent")

    # Color anomalies
    if "non-canonical color" in bag or "wrong colors" in bag:
        anomalies.append("color_off")

    # Composition artifacts
    if "image looks edited" in bag or "photoshop" in bag:
        anomalies.append("edited_composition")

    return anomalies


def assess_layout_consistency(
    vlm_description: str, ocr_text: str
) -> str:
    """Return 'consistent' / 'inconsistent' / 'unknown'."""
    anomalies = detect_visual_anomalies(vlm_description, ocr_text)
    if any(
        a in anomalies
        for a in (
            "layout_inconsistent",
            "font_mismatch",
            "logo_modified",
            "edited_composition",
        )
    ):
        return "inconsistent"
    if vlm_description.strip():
        return "consistent"
    return "unknown"
