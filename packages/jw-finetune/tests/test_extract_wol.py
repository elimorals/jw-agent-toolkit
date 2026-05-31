"""Tests for WOL article extraction (uses a fake WOLClient)."""

from __future__ import annotations

import pytest
from jw_finetune.data.extract import extract_from_wol_article


class FakeWOLClient:
    """Returns the same HTML for any URL; only `fetch` and `aclose` are used."""

    def __init__(self, html: str) -> None:
        self._html = html
        self.closed = False
        self.fetched: list[str] = []

    async def fetch(self, url: str, **kw) -> str:
        self.fetched.append(url)
        return self._html

    async def aclose(self) -> None:
        self.closed = True


_SAMPLE_ARTICLE_HTML = """
<html>
  <head><title>El Reino de Dios — Atalaya</title></head>
  <body>
    <article id="article">
      <h1>El Reino de Dios</h1>
      <p id="p1" data-pid="1">El Reino de Dios es el gobierno celestial de Jehová mencionado en Daniel 2:44.</p>
      <p id="p2" data-pid="2">Este Reino traerá paz mundial conforme a Mateo 24:14 y otros pasajes proféticos.</p>
    </article>
  </body>
</html>
"""


@pytest.mark.asyncio
async def test_extract_from_wol_article_basic() -> None:
    client = FakeWOLClient(_SAMPLE_ARTICLE_HTML)
    records = await extract_from_wol_article(
        "https://wol.jw.org/es/wol/d/r4/lp-s/example",
        language_hint="es",
        wol_client=client,
    )
    assert len(records) >= 1
    assert records[0].language == "es"
    assert records[0].source_path.startswith("https://wol.jw.org/")
    # The fake client was reused, not closed (caller owns it)
    assert not client.closed
    assert client.fetched == ["https://wol.jw.org/es/wol/d/r4/lp-s/example"]


@pytest.mark.asyncio
async def test_extract_from_wol_article_one_shot_client_is_closed() -> None:
    """If no client is passed, we don't have a way to assert close() — just verify it runs."""
    # We patch WOLClient with our fake by monkeypatching the import inside.
    from jw_finetune.data import extract as ext_mod

    fake_instances: list[FakeWOLClient] = []

    class _Stub:
        def __init__(self, *a, **kw):
            inst = FakeWOLClient(_SAMPLE_ARTICLE_HTML)
            fake_instances.append(inst)
            self._inst = inst

        async def fetch(self, url: str, **kw) -> str:
            return await self._inst.fetch(url, **kw)

        async def aclose(self) -> None:
            await self._inst.aclose()

    # Monkeypatch the imported WOLClient symbol via sys.modules
    import jw_core.clients.wol as wol_mod

    orig = wol_mod.WOLClient
    wol_mod.WOLClient = _Stub  # type: ignore[assignment]
    try:
        records = await ext_mod.extract_from_wol_article(
            "https://wol.jw.org/es/wol/d/r4/lp-s/example",
            language_hint="es",
        )
    finally:
        wol_mod.WOLClient = orig

    assert len(records) >= 1
    assert fake_instances[0].closed is True


@pytest.mark.asyncio
async def test_extract_from_wol_article_filters_short(monkeypatch) -> None:
    html_with_short = """
    <html><body><article id="article">
      <p id="p1" data-pid="1">x</p>
      <p id="p2" data-pid="2">Este párrafo sí tiene contenido suficiente para pasar el filtro de longitud mínima.</p>
    </article></body></html>
    """
    client = FakeWOLClient(html_with_short)
    records = await extract_from_wol_article(
        "https://wol.jw.org/x",
        language_hint="es",
        wol_client=client,
        min_chars=30,
    )
    # Only the long paragraph survives
    assert all(len(r.text) >= 30 for r in records)
