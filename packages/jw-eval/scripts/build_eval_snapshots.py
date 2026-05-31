"""Build HTML snapshots for L2 cases.

Reads every l2 YAML, collects unique `expected_citations` URLs, downloads
them with WOLClient, and writes minified HTML to
packages/jw-eval/fixtures/wol_snapshots/<sha256(URL)>.html.

Run manually:
    uv run python packages/jw-eval/scripts/build_eval_snapshots.py
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
from pathlib import Path

import httpx
import yaml


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _minify(html: str) -> str:
    """Strip <script>, <style>, and runs of whitespace. Keep text + links."""

    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


async def _download(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers={"User-Agent": "jw-eval/0.1 (snapshot builder)"})
        r.raise_for_status()
        return r.text


def _collect_urls(l2_dir: Path) -> list[str]:
    urls: set[str] = set()
    for f in sorted(l2_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        for u in (data.get("expected") or {}).get("expected_citations", []) or []:
            urls.add(u)
    return sorted(urls)


async def _main(l2_dir: Path, out_dir: Path, force: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    urls = _collect_urls(l2_dir)
    n_written = 0
    for url in urls:
        dest = out_dir / f"{_digest(url)}.html"
        if dest.exists() and not force:
            continue
        print(f"GET {url}")
        try:
            body = await _download(url)
        except Exception as exc:  # noqa: BLE001
            print(f"  !! failed: {exc}")
            continue
        dest.write_text(_minify(body), encoding="utf-8")
        n_written += 1
    print(f"\n{n_written} new snapshot(s) written to {out_dir}.")
    return 0


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--l2-dir", default=str(here / "fixtures" / "golden_qa" / "l2"))
    parser.add_argument("--out-dir", default=str(here / "fixtures" / "wol_snapshots"))
    parser.add_argument("--force", action="store_true", help="re-download even if file exists")
    args = parser.parse_args()
    return asyncio.run(_main(Path(args.l2_dir), Path(args.out_dir), args.force))


if __name__ == "__main__":
    raise SystemExit(main())
