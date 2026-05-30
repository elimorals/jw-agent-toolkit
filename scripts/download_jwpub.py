"""Try to download a JWPUB file via the pub-media API."""
import asyncio
from pathlib import Path

from jw_core.clients.pub_media import PubMediaClient

OUT_DIR = Path("data/jwpub_test")
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    client = PubMediaClient()
    # Try 'fg' (Good News brochure) — small and openly available.
    for pub_code in ("fg", "ti"):
        print(f"\n=== Trying pub={pub_code!r} format=JWPUB lang=E ===")
        try:
            pub = await client.get_publication(
                pub_code, language="E", file_format="JWPUB"
            )
        except Exception as e:
            print(f"  catalog failed: {e}")
            continue
        files = pub.files_by_format("JWPUB")
        if not files:
            print(f"  no JWPUB available for {pub_code!r}")
            continue
        f = files[0]
        print(f"  found: {f.filename}  ({f.size_bytes:,} bytes)  url={f.url[:80]}")
        dest = OUT_DIR / f.filename
        if dest.exists() and dest.stat().st_size == f.size_bytes:
            print(f"  already cached at {dest}")
        else:
            print(f"  downloading to {dest} ...")
            await client.download(f, dest)
            print(f"  saved {dest.stat().st_size:,} bytes")
    await client.aclose()


asyncio.run(main())
