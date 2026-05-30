"""Run `discover_wol_resource` for every Tier-1 language and emit a patch.

Runs against jw.org live. Slow (multiple HTTP calls per language) but
deterministic. The output is a Python dict literal you paste into
`jw_core/languages.py` to update the registry.
"""

from __future__ import annotations

import asyncio

from jw_core.language_discovery import discover_wol_resource
from jw_core.languages import all_languages


async def main() -> None:
    print("# Discovered wol_resource values")
    for lang in all_languages():
        result = await discover_wol_resource(lang)
        if result.wol_resource:
            print(f"# {lang.iso}: pub-media OK, wol_resource={result.wol_resource}")
        else:
            print(f"# {lang.iso}: pub-media={result.pub_media_ok} error={result.error!r}")


if __name__ == "__main__":
    asyncio.run(main())
