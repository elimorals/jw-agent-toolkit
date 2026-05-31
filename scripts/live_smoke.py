"""Live smoke against jw.org / wol.jw.org / b.jw-cdn.org / data.jw-api.org.

Verifica que los 6 clientes HTTP del toolkit (CDN, WOL, Mediator, PubMedia,
TopicIndex, Weblang) siguen recibiendo respuestas válidas de los endpoints
reales. Esta es la contraparte EN VIVO de los 1641 tests offline.

Diseño:

- Cada check es independiente y bounded por timeout corto.
- El script captura excepciones por check; un fallo NO aborta los demás.
- Salida JSON estructurada en stdout para que el workflow CI la parse y
  abra issues granulares (uno por check fallido).
- Exit code: 0 si TODOS pasan, 1 si CUALQUIERA falla. Esto permite que
  `gh workflow` marque el job como failed.

Uso local:

    uv run --no-sync python scripts/live_smoke.py
    uv run --no-sync python scripts/live_smoke.py --json    # solo JSON
    uv run --no-sync python scripts/live_smoke.py --check cdn.search

En CI: ver .github/workflows/live-smoke.yml.

Por qué no es un test:

Los tests son OFFLINE por contrato — usan MockTransport, fakes y
cassettes congeladas. Este script es la única pieza del repo que toca
red real, intencionalmente, fuera del flujo de testing.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from jw_core.clients.factory import build_clients

# ─── Per-check timeout: jw.org is usually fast; we cap aggressively so
# the whole smoke completes in <60s even when one endpoint is slow. ────
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass
class CheckResult:
    name: str
    ok: bool
    duration_ms: int
    detail: str  # short human summary, e.g. "312 langs"
    error: str | None = None  # exception type+msg when ok=False


@dataclass
class SmokeReport:
    timestamp_utc: str
    overall_ok: bool
    checks: list[CheckResult]

    def to_json(self) -> str:
        return json.dumps(
            {
                "timestamp_utc": self.timestamp_utc,
                "overall_ok": self.overall_ok,
                "checks": [asdict(c) for c in self.checks],
            },
            indent=2,
        )


# ─── Individual checks ──────────────────────────────────────────────────


async def _check_cdn_search(suite: Any) -> str:
    """CDN search hits b.jw-cdn.org/apis/search with JWT auth."""
    resp = await suite.cdn.search("Trinity", filter_type="all", language="E", limit=3)
    hits = resp.get("results") or resp.get("Hits") or []
    return f"{len(hits)} hits for 'Trinity'"


async def _check_wol_homepage(suite: Any) -> str:
    """WOL today homepage — entry point for daily text and weekly content."""
    url, html = await suite.wol.get_today_homepage(language="E")
    if not html or len(html) < 100:
        raise RuntimeError(f"homepage too short: {len(html)} bytes (url={url})")
    return f"{len(html)} bytes HTML from {url[:60]}..."


async def _check_mediator_languages(suite: Any) -> str:
    """Mediator language registry — drives Tier-2 multi-language URL building."""
    langs = await suite.mediator.list_languages(in_language="E")
    if len(langs) < 100:
        raise RuntimeError(f"too few languages returned: {len(langs)}")
    return f"{len(langs)} languages"


async def _check_pub_media(suite: Any) -> str:
    """Pub-media for the Bible Teach brochure — well-known stable publication."""
    pub = await suite.pub_media.get_publication(
        pub_code="bh", language="E", file_format="EPUB"
    )
    # Publication.files is a list[PubMediaFile].
    files = getattr(pub, "files", []) or []
    if not files:
        raise RuntimeError("no files returned for bh / E / EPUB")
    return f"{len(files)} file(s) for bh/E (e.g. {files[0].filename or files[0].url[-30:]})"


async def _check_topic_index(suite: Any) -> str:
    """Topic index search — authoritative for apologetics queries."""
    subjects = await suite.topic_index.search_subjects("Trinity", language="E", limit=3)
    if not subjects:
        raise RuntimeError("zero subjects for 'Trinity'")
    top_title = subjects[0].get("title") if isinstance(subjects[0], dict) else getattr(subjects[0], "title", "?")
    return f"{len(subjects)} subjects (top: {top_title!r})"


async def _check_weblang(suite: Any) -> str:
    """www.jw.org/{iso}/languages — full registry with sign-language flags."""
    wlangs = await suite.weblang.list_languages(in_language_iso="en")
    if len(wlangs) < 500:
        raise RuntimeError(f"too few weblang entries: {len(wlangs)}")
    return f"{len(wlangs)} languages"


CHECKS: dict[str, Callable[[Any], Awaitable[str]]] = {
    "cdn.search": _check_cdn_search,
    "wol.homepage": _check_wol_homepage,
    "mediator.languages": _check_mediator_languages,
    "pub_media": _check_pub_media,
    "topic_index.search": _check_topic_index,
    "weblang": _check_weblang,
}


# ─── Runner ─────────────────────────────────────────────────────────────


async def _run_check(
    name: str, fn: Callable[[Any], Awaitable[str]], suite: Any, timeout: float
) -> CheckResult:
    started = datetime.now(timezone.utc)
    try:
        detail = await asyncio.wait_for(fn(suite), timeout=timeout)
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return CheckResult(name=name, ok=True, duration_ms=duration_ms, detail=detail)
    except asyncio.TimeoutError:
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return CheckResult(
            name=name,
            ok=False,
            duration_ms=duration_ms,
            detail="",
            error=f"TimeoutError after {timeout}s",
        )
    except Exception as exc:  # noqa: BLE001 — we want the type name in the report
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        return CheckResult(
            name=name,
            ok=False,
            duration_ms=duration_ms,
            detail="",
            error=f"{type(exc).__name__}: {exc}",
        )


async def run_smoke(
    *,
    only: list[str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> SmokeReport:
    """Run every check (or a subset). Returns the report. Never raises."""
    suite = build_clients()
    selected = (
        {k: CHECKS[k] for k in only if k in CHECKS} if only else dict(CHECKS)
    )
    if not selected:
        return SmokeReport(
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            overall_ok=False,
            checks=[],
        )
    results = await asyncio.gather(
        *(_run_check(name, fn, suite, timeout) for name, fn in selected.items()),
        return_exceptions=False,
    )
    return SmokeReport(
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        overall_ok=all(r.ok for r in results),
        checks=list(results),
    )


def _print_human(report: SmokeReport) -> None:
    print()
    print(f"=== LIVE SMOKE — jw.org endpoints @ {report.timestamp_utc} ===")
    for c in report.checks:
        emoji = "✓" if c.ok else "✗"
        info = c.detail if c.ok else (c.error or "")
        print(f"{emoji} {c.name:22s} ({c.duration_ms:5d}ms)  {info}")
    print()
    status = "ALL GREEN" if report.overall_ok else "AT LEAST ONE FAILURE"
    print(f">>> {status} <<<")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--json", action="store_true", help="emit JSON to stdout (no human output)"
    )
    parser.add_argument(
        "--check",
        action="append",
        choices=list(CHECKS.keys()),
        help="run only the named check (repeatable)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"per-check timeout in seconds (default {DEFAULT_TIMEOUT_SECONDS})",
    )
    args = parser.parse_args()

    try:
        report = asyncio.run(
            run_smoke(only=args.check, timeout=args.timeout)
        )
    except Exception:  # noqa: BLE001
        # Should not happen — run_smoke is defensive — but better to ship
        # a JSON error than silently exit non-zero.
        print(
            json.dumps(
                {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "overall_ok": False,
                    "fatal": traceback.format_exc(),
                }
            )
        )
        return 1

    if args.json:
        print(report.to_json())
    else:
        _print_human(report)

    return 0 if report.overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
