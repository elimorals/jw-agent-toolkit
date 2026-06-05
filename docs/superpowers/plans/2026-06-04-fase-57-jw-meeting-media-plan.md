# Fase 57 — `jw-meeting-media` subpkg (clean-room) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un nuevo subpaquete del monorepo, `packages/jw-meeting-media`, que entrega la capa "reunión-en-vivo" hoy ausente en `jw-agent-toolkit`: **descubrimiento automático del programa semanal de reuniones congregacionales** (Vida y Ministerio Cristianos + Atalaya de Estudio), **descarga automática de media asociada** (imágenes, videos, audio, JWPUB referenciados) y **modo presenter** con thumbnails, controles play/pause/stop, gestión de monitor externo y soporte de eventos especiales (Memorial, asambleas). MVP de F57 cubre **CLI completo + presenter Tauri básico**; integraciones Zoom/OBS y sync cloud quedan fuera de MVP (sprint posterior).

**Architecture (clean-room):** Subpaquete Python que orquesta piezas YA EXISTENTES del toolkit (`PubMediaClient` F2, `WOLClient` F1, schemas `organized-app` F51, parser JWPUB descifrado F5.5, ASR `omnilingual` F53) más un cliente nuevo `MeetingProgramClient` que descubre la estructura semanal `mwb`/`w` del WOL. Frontend: nueva ventana Tauri "presenter" añadida a `apps/desktop/src-tauri/tauri.conf.json` (Tauri 2.x ya configurado en F47), JS vanilla con el patrón ya usado por la ventana principal. Storage local-first con sqlite (precedente F25/F61) en `~/.jw-agent-toolkit/meetings.db`.

**Tech Stack:** Python 3.13 · Tauri 2.x (ya en stack) · Vanilla JS para el presenter (sin Vue/React — coherente con `apps/desktop` actual) · `httpx` para downloads · `mutagen` para tags audio · `Pillow` para thumbnails · sqlite stdlib.

**Spec/origen brainstorm:** [`docs/conceptos/integraciones-priorizadas.md`](../../conceptos/integraciones-priorizadas.md) §"Hallazgos JW-específicos" y conversación 2026-06-04 sobre clean-room implementation (versión propia desde el toolkit, no port AGPL del upstream).

**Depende de:** F1 (WOLClient), F2 (PubMediaClient), F5.5 (jwpub_crypto), F47 (Tauri scaffolding), F51 (organized-app schemas). Sinergias opcionales con F20 (linkify markdown), F53 (omnilingual-asr), F58 (bible KG).

---

## 🛑 DISCLAIMER LEGAL — Política Clean-Room ESTRICTA

> Esta sección NO es decorativa. Léela antes de tocar código.

`sircharlo/meeting-media-manager` ("M³") es **AGPL-3.0**. El monorepo `jw-agent-toolkit` es **GPL-3.0-only**. Copiar código de M³ contaminaría todo el toolkit con AGPL (network use clause viral).

### Reglas duras al implementar este plan

1. ✅ **Permitido leer en `/Users/elias/Documents/Trabajo/meeting-media-manager/`**:
   - `README.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `LICENSE.md`
   - `AGENTS.md`, `CONTRIBUTING.md`, `SUPPORT.md`, `SECURITY.md`
   - `release-notes/en.md` (English source)
   - **NADA dentro de `src/`, `src-electron/`, `docs/`, `test/`, `scripts/`**

2. ✅ **Permitido observar la app instalada** (run de un binario release público): contar atajos de teclado, screenshot del layout, ver qué endpoints hace al network (Wireshark / DevTools).

3. ✅ **Permitido consultar documentación pública del proyecto** en `https://sircharlo.github.io/meeting-media-manager/`.

4. ✅ **Permitido usar datos públicos de jw.org**: catálogo de idiomas, formato de URLs WOL, formato JWPUB (ya descifrado en F5.5).

5. ❌ **PROHIBIDO abrir ningún archivo `.ts`, `.vue`, `.json` que sea código/configuración de M³** durante la implementación.

6. ❌ **PROHIBIDO copiar nombres internos de funciones/clases/variables de M³**. Si necesitas un identificador y dudas, usa nombres derivados del dominio (`MeetingProgramClient`, `MediaResolver`, `PresenterSession`) — no de la implementación AGPL.

7. ❌ **PROHIBIDO incluir comentarios tipo "based on M³"** en el código nuevo. La atribución va en el doc `docs/guias/meeting-media.md` como "inspirado por las features de M³ pero implementado clean-room".

### Si el implementador rompe esta política

El task que infrinja se **revierte** y el plan se re-ejecuta desde el commit anterior. Si la infracción llega a `main`, hay que abrir un issue legal y considerar borrar todo el subpaquete F57.

---

## Scope del MVP F57 (qué SÍ entrega esta fase)

| Feature M³ observable | F57 MVP | Razón |
|---|---|---|
| Descubrimiento automático del programa semanal mwb/w | ✅ | Core value, sin esto no hay nada |
| Descarga automática de imágenes y videos | ✅ | Core |
| Descarga audio NWT y Study Bible | ✅ | Reusa `PubMediaClient` |
| Soporte JWPUB para discursos públicos | ✅ | Reusa parser F5.5 |
| Presenter con play/pause/stop básico | ✅ | Ventana Tauri nueva |
| Thumbnails de media | ✅ | Pillow para imágenes, ffmpeg para video |
| Monitor externo automático | ⚠️ MVP+1 | Requiere Tauri windows API avanzado |
| Drag-and-drop adicionar media | ⚠️ MVP+1 | UI work no trivial |
| Multi-congregación | ⚠️ MVP+1 | Schema multi-tenant en F51 ya, pero CLI/presenter no |
| Zoom screen sharing | ❌ futuro | OS integration compleja |
| OBS Studio scene switching | ❌ futuro | Requiere OBS WebSocket setup |
| Sync cloud (Dropbox/OneDrive) | ❌ futuro | Auth APIs no JW |
| Background music con auto-stop | ❌ futuro | Edge case |
| Memorial / special events colores | ⚠️ MVP+1 | Catálogo `memorials.json` público en upstream — re-derivar |
| App multilingüe UI | ✅ ES/EN/PT | F1 ya cubre los 3; otros idiomas via Crowdin futuro |

**Estimación MVP F57**: ~15-18 tasks, ~3500 LOC nuevas + ~80 tests.

---

## File map

Crea (nuevo workspace member):
- `packages/jw-meeting-media/pyproject.toml`
- `packages/jw-meeting-media/src/jw_meeting_media/__init__.py`
- `packages/jw-meeting-media/src/jw_meeting_media/models.py` — Pydantic schemas
- `packages/jw-meeting-media/src/jw_meeting_media/program_client.py` — `MeetingProgramClient` (nuevo cliente HTTP)
- `packages/jw-meeting-media/src/jw_meeting_media/program_parser.py` — parser HTML del WOL para mwb/w
- `packages/jw-meeting-media/src/jw_meeting_media/media_resolver.py` — resuelve refs a URLs descargables
- `packages/jw-meeting-media/src/jw_meeting_media/downloader.py` — orquesta descargas con cache
- `packages/jw-meeting-media/src/jw_meeting_media/storage.py` — sqlite layer
- `packages/jw-meeting-media/src/jw_meeting_media/thumbnailer.py` — genera thumbnails de imagen/video
- `packages/jw-meeting-media/src/jw_meeting_media/presenter_state.py` — `PresenterSession` (server-side state)
- `packages/jw-meeting-media/src/jw_meeting_media/cli.py` — Typer sub-app
- `packages/jw-meeting-media/tests/` — tests por módulo + fixtures HTML WOL

Crea (frontend Tauri):
- `apps/desktop/src/presenter.html` — ventana presenter
- `apps/desktop/src/presenter.js` — vanilla JS controller (sin Vue)
- `apps/desktop/src/presenter.css`

Modifica:
- `pyproject.toml` (root) — añadir `packages/jw-meeting-media` al workspace
- `apps/desktop/src-tauri/tauri.conf.json` — añadir window "presenter"
- `packages/jw-mcp/src/jw_mcp/server.py` — añadir tools `discover_weekly_program`, `download_meeting_media`, `presenter_*`
- `packages/jw-mcp/tests/test_protocol.py` — registrar tools
- `packages/jw-mcp/src/jw_mcp/rest_api.py` — añadir endpoints `/presenter/*` para Tauri
- `packages/jw-cli/src/jw_cli/main.py` — registrar `jw meeting` sub-app

Crea (docs):
- `docs/guias/meeting-media.md` — guía operativa
- `docs/conceptos/programa-semanal-mwb-w.md` — análisis arquitectónico clean-room

Modifica (docs):
- `docs/README.md`, `docs/ROADMAP.md`, master plan

---

## Decisiones clave de diseño (anti-placeholder)

### Por qué ventana Tauri NUEVA en vez de iframe en la actual
La ventana actual de `apps/desktop` (F47) carga un iframe contra REST API en `localhost:8765`. F57 presenter necesita **fullscreen control de monitor externo**, lo cual requiere ser una ventana Tauri nativa con `fullscreen: true` y posibilidad de mover a monitor secundario. Tauri 2.x soporta múltiples ventanas declarativas — añadir una segunda window al `tauri.conf.json` es directo.

### Stack JS del presenter: vanilla, NO Vue/React
El upstream M³ usa Vue 3 + Quasar (~50 MB de assets). El presenter F57 muestra: una imagen/video full-screen, una barra inferior con play/pause/next/prev, un timer. Eso son ~200 líneas de vanilla JS + CSS. **Bundlear Vue para esto es overkill**. Coherente con `apps/desktop/src/main.js` actual que también es vanilla.

### REST API como contrato entre Tauri presenter ↔ Python state
El presenter Tauri ejecuta JS en el renderer; el state (qué media está activo, position en la cola, etc) vive en Python (`PresenterSession`) accesible vía REST en `localhost:8765/presenter/*`. Decisión: NO usar Tauri IPC (sería específico de la ventana); REST es genérico y permite que también la app móvil futura (F65 Capacitor) reuse la API. Endpoints:
- `GET  /presenter/sessions` — lista sesiones activas
- `POST /presenter/sessions` — crea sesión para un programa específico
- `GET  /presenter/sessions/{id}/queue` — cola de media
- `POST /presenter/sessions/{id}/play|pause|next|prev|seek|stop`
- `GET  /presenter/sessions/{id}/state` — websocket-or-polling state

### `MeetingProgramClient`: HTTP por WOL, NO scraping libre
Clean-room implica que NO podemos copiar las regex o selectores CSS del upstream. **Pero** la página WOL para el Workbook (Vida y Ministerio) tiene estructura HTML estable y pública: `wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{YYYY}/{week-number}`. El cliente nuevo:
1. Hace GET al URL del workbook semanal
2. Parsea HTML con BeautifulSoup buscando estructura semántica (`<article class="bodyTxt">`, `<h2>`, `<a class="b">`, `<a href="/wol/d/...">`, marcadores tipo "th-x", "p", "qu")
3. Devuelve `MeetingProgram` Pydantic con `sections: [{title, items: [{title, refs: [BibleRef], media_refs: [MediaRef]}]}]`

El parser se diseña **leyendo el HTML real del WOL en el browser** (Inspect Element), no leyendo código de M³.

### `MediaResolver`: resuelve `media_ref` → URL descargable
Tipos de refs encontrables en el HTML del workbook:
- **Imagen jw.org**: URL directa CDN, descarga simple
- **Video jw.org (jwbroadcasting)**: GETPUBMEDIALINKS con `pub=...&track=...` → mejor calidad disponible
- **NWT audio**: GETPUBMEDIALINKS con `pub=nwt&track={book_num}.{chapter}` (formato público)
- **JWPUB de tema**: download + decrypt (F5.5)
- **Study Bible media** (illustrations attached to verses): WOLClient + parser nwtsty

Reusar PubMediaClient (F2), WOLClient (F1) — NO re-implementar HTTP.

### Storage local-first: sqlite para programa y media metadata, filesystem para binarios
`~/.jw-agent-toolkit/meetings/`:
- `meetings.db` — sqlite con tablas: `programs`, `media_refs`, `download_cache`
- `media/{lang}/{YYYY}/{week}/{media_id}.{ext}` — binarios cacheados

Schema sqlite versionable con `PRAGMA user_version` (precedente F61).

### Idempotencia y resumibilidad de descargas
Cada media item tiene `sha256` del archivo esperado (cuando lo da `GETPUBMEDIALINKS`, lo provee). Descarga:
1. Si `~/.jw-agent-toolkit/meetings/media/.../{id}.{ext}` existe Y `sha256 ==` esperado → no-op
2. Si no existe → download con `Range: bytes=` resumible si conexión cae
3. Tras descargar, validar sha256

### Catálogo `memorials.json` upstream — re-derivar de jw.org
M³ tiene un `memorials.json` versionado público (~~ pero está dentro del repo, mejor NO lo leemos). Las fechas del Memorial vienen anunciadas oficialmente por la organización JW y publicadas en `jw.org` cada año. F57:
1. Hace scrape muy puntual de la página oficial del Memorial en jw.org (URL conocida).
2. Si falla, fallback a un cálculo astronómico (Memorial = primera luna llena después del equinoccio vernal, 14 Nisan calendario judío).
3. Cachea localmente.

**NO copiar `memorials.json`** del upstream — son datos pero su organización particular es decisión del autor M³ y la copia "as is" podría considerarse derivada.

---

### Task 1: Scaffold workspace member `packages/jw-meeting-media`

**Files:**
- Create: `packages/jw-meeting-media/pyproject.toml`
- Create: `packages/jw-meeting-media/src/jw_meeting_media/__init__.py`
- Create: `packages/jw-meeting-media/tests/__init__.py`
- Create: `packages/jw-meeting-media/tests/test_smoke.py`
- Modify: `pyproject.toml` (root) — añadir miembro al workspace

- [ ] **Step 1: pyproject.toml del paquete**

```toml
# packages/jw-meeting-media/pyproject.toml
[project]
name = "jw-meeting-media"
version = "0.1.0"
description = "Descubrimiento, descarga y presentación de medios para reuniones congregacionales JW. Clean-room implementation."
requires-python = ">=3.13"
license = "GPL-3.0-only"
authors = [{name = "jw-agent-toolkit"}]
dependencies = [
    "jw-core",
    "pydantic>=2.0",
    "beautifulsoup4>=4.12",
    "lxml>=5.0",
    "httpx>=0.27",
    "typer>=0.12",
    "rich>=13.0",
]

[project.optional-dependencies]
thumbnails = ["Pillow>=10.0"]
video-thumbnails = ["Pillow>=10.0"]  # plus ffmpeg en PATH (system dep)
audio-tags = ["mutagen>=1.47"]
all = ["jw-meeting-media[thumbnails,audio-tags]"]

[tool.uv.sources]
jw-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/jw_meeting_media"]
```

- [ ] **Step 2: __init__ con docstring clean-room**

```python
# packages/jw-meeting-media/src/jw_meeting_media/__init__.py
"""jw-meeting-media — capa "reunión-en-vivo" del toolkit.

Descubre el programa semanal de reuniones congregacionales JW (Vida y
Ministerio + Atalaya de Estudio) desde wol.jw.org, descarga la media
asociada (imágenes, videos, audio, JWPUB) y entrega un presenter
controlable vía REST API para una ventana Tauri o cliente futuro.

Clean-room implementation: ninguna línea de código deriva del proyecto
M³ (sircharlo/meeting-media-manager, AGPL-3.0). Funcionalidad
reimplementada desde lectura de README, AGENTS.md y observación de la
app pública. Más detalles en `docs/guias/meeting-media.md`.
"""
__version__ = "0.1.0"
```

- [ ] **Step 3: Smoke test**

```python
# packages/jw-meeting-media/tests/test_smoke.py
def test_import_smoke():
    import jw_meeting_media

    assert jw_meeting_media.__version__ == "0.1.0"
```

- [ ] **Step 4: Añadir miembro al workspace root**

En `/Users/elias/Documents/Trabajo/jw-agent-toolkit/pyproject.toml`, dentro de `[tool.uv.workspace]`, añadir a `members`:
```toml
"packages/jw-meeting-media",
```

- [ ] **Step 5: Verificar sync**

```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit
uv sync --all-packages
uv run pytest packages/jw-meeting-media/tests/test_smoke.py -v
```
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add packages/jw-meeting-media/ pyproject.toml
git commit -m "feat(jw-meeting-media): F57.1 scaffold workspace member with clean-room disclaimer"
```

---

### Task 2: Modelos Pydantic — programa semanal, refs, sesiones

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/models.py`
- Create: `packages/jw-meeting-media/tests/test_models.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-meeting-media/tests/test_models.py
"""F57 — modelos del programa semanal y sesión de presenter."""
from __future__ import annotations

from datetime import date

import pytest

from jw_meeting_media.models import (
    MeetingKind,
    MeetingItem,
    MeetingProgram,
    MeetingSection,
    MediaKind,
    MediaRef,
    PresenterSession,
)


def test_meeting_program_basic():
    prog = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[],
        source_url="https://wol.jw.org/es/wol/meetings/r4/lp-s/2026/23",
    )
    assert prog.language == "es"
    assert prog.kind == MeetingKind.MIDWEEK


def test_media_ref_image():
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="Ilustración Génesis",
        url="https://cms-imgp.jw-cdn.org/img/p/.../some.jpg",
        sha256=None,
    )
    assert ref.kind == MediaKind.IMAGE
    assert ref.url.startswith("https://")


def test_media_ref_video_with_track():
    ref = MediaRef(
        kind=MediaKind.VIDEO,
        title="Ejemplo en video",
        url="",  # se resuelve via PubMediaClient
        pub_code="pk",
        track=12,
        sha256=None,
    )
    assert ref.pub_code == "pk"


def test_meeting_section_with_items():
    sec = MeetingSection(
        section_id="treasures",
        title="Tesoros de la Palabra de Dios",
        items=[
            MeetingItem(
                item_id="t1",
                title="Lectura bíblica",
                position=1,
                bible_refs=[],
                media_refs=[],
            ),
        ],
    )
    assert len(sec.items) == 1


def test_presenter_session_starts_paused():
    s = PresenterSession(
        session_id="s-123",
        program_url="https://wol.jw.org/...",
        queue=[],
        cursor=0,
        playing=False,
    )
    assert s.playing is False
    assert s.cursor == 0


def test_presenter_session_advance_within_bounds():
    item = MeetingItem(item_id="i1", title="x", position=1, bible_refs=[], media_refs=[])
    s = PresenterSession(
        session_id="s1", program_url="x", queue=[item, item, item], cursor=0, playing=False
    )
    s.advance()
    assert s.cursor == 1
    s.advance()
    assert s.cursor == 2
    with pytest.raises(IndexError):
        s.advance()


def test_meeting_kind_values():
    assert MeetingKind.MIDWEEK.value == "midweek"
    assert MeetingKind.WEEKEND.value == "weekend"
    assert MeetingKind.MEMORIAL.value == "memorial"
    assert MeetingKind.SPECIAL_EVENT.value == "special_event"
```

- [ ] **Step 2: Run, expect ImportError**

```bash
uv run pytest packages/jw-meeting-media/tests/test_models.py -v
```

- [ ] **Step 3: Implementar modelos**

```python
# packages/jw-meeting-media/src/jw_meeting_media/models.py
"""Modelos del dominio reunión-en-vivo.

Diseñados clean-room desde la estructura semántica del WOL y desde los
schemas ya portados de organized-app (F51). NO derivados de M³.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jw_core.models import BibleRef


class MeetingKind(str, Enum):
    """Tipo de reunión. Memorial y special_event NO son semanales."""
    MIDWEEK = "midweek"
    WEEKEND = "weekend"
    MEMORIAL = "memorial"
    SPECIAL_EVENT = "special_event"


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    JWPUB = "jwpub"
    JWLPLAYLIST = "jwlplaylist"
    EXTERNAL_FILE = "external_file"  # user-added drag-drop


class MediaRef(BaseModel):
    """Referencia a una pieza de media — no descargada aún."""
    model_config = ConfigDict(frozen=False)

    kind: MediaKind
    title: str
    url: str = ""  # vacío si requiere resolución vía PubMediaClient
    pub_code: str | None = None
    track: int | None = None
    docid: int | None = None
    language: str | None = None
    duration_seconds: float | None = None
    sha256: str | None = None
    local_path: str | None = None  # se rellena tras descarga
    metadata: dict[str, Any] = Field(default_factory=dict)


class MeetingItem(BaseModel):
    """Una parte/punto del programa con sus refs."""
    model_config = ConfigDict(frozen=False)

    item_id: str
    title: str
    position: int = Field(ge=1, description="Orden dentro de la sección")
    duration_minutes: float | None = None
    bible_refs: list[BibleRef] = Field(default_factory=list)
    media_refs: list[MediaRef] = Field(default_factory=list)
    speaker_note: str = ""


class MeetingSection(BaseModel):
    """Bloque del programa (ej. 'Tesoros de la Palabra de Dios')."""
    model_config = ConfigDict(frozen=False)

    section_id: str
    title: str
    items: list[MeetingItem] = Field(default_factory=list)


class MeetingProgram(BaseModel):
    """Programa semanal completo descubierto desde WOL."""
    model_config = ConfigDict(frozen=False)

    language: str
    week_start: date
    kind: MeetingKind
    sections: list[MeetingSection] = Field(default_factory=list)
    source_url: str
    detected_at: str = ""  # ISO 8601 timestamp del scrape


class PresenterSession(BaseModel):
    """Estado de una sesión presenter en curso. Server-side."""
    model_config = ConfigDict(frozen=False)

    session_id: str
    program_url: str
    queue: list[MeetingItem] = Field(default_factory=list)
    cursor: int = 0
    playing: bool = False
    started_at: str = ""

    @model_validator(mode="after")
    def _validate_cursor(self) -> "PresenterSession":
        if self.cursor < 0:
            raise ValueError("cursor must be >= 0")
        return self

    def advance(self) -> None:
        if self.cursor + 1 >= len(self.queue):
            raise IndexError("cursor out of range")
        self.cursor += 1

    def rewind(self) -> None:
        if self.cursor == 0:
            raise IndexError("already at start")
        self.cursor -= 1

    def current_item(self) -> MeetingItem | None:
        if not self.queue or self.cursor >= len(self.queue):
            return None
        return self.queue[self.cursor]
```

- [ ] **Step 4: Run tests, expect PASS**

```bash
uv run pytest packages/jw-meeting-media/tests/test_models.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/models.py packages/jw-meeting-media/tests/test_models.py
git commit -m "feat(jw-meeting-media): F57.2 pydantic models for program section item media presenter"
```

---

### Task 3: `MeetingProgramClient` — descubrimiento del WOL

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/program_client.py`
- Create: `packages/jw-meeting-media/tests/test_program_client.py`
- Create: `packages/jw-meeting-media/tests/fixtures/wol_mwb_2026_w23_es.html` (fixture HTML real descargado y commiteado)

- [ ] **Step 1: Capturar fixture HTML real**

```bash
mkdir -p packages/jw-meeting-media/tests/fixtures
# Descargar una página del workbook real (acceso público, no login)
# usar curl directo, no a través del repo upstream
curl -A "Mozilla/5.0 (jw-agent-toolkit fixture capture)" \
  "https://wol.jw.org/es/wol/meetings/r4/lp-s/2026/23" \
  -o packages/jw-meeting-media/tests/fixtures/wol_mwb_2026_w23_es.html
ls -lh packages/jw-meeting-media/tests/fixtures/
# Esperar ~50-200 KB
```

> **Nota**: el HTML puede tener IDs y URLs dinámicas; documentar fecha de captura en el filename. Si jw.org cambia layout, regenerar y actualizar tests.

- [ ] **Step 2: Failing tests**

```python
# packages/jw-meeting-media/tests/test_program_client.py
"""F57 — MeetingProgramClient. Tests con HTML fixture local + cassettes opt-in."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from jw_meeting_media.models import MeetingKind
from jw_meeting_media.program_client import MeetingProgramClient

FIXTURE = Path(__file__).parent / "fixtures" / "wol_mwb_2026_w23_es.html"


@pytest.fixture()
def client() -> MeetingProgramClient:
    return MeetingProgramClient()


def test_parse_midweek_fixture_sections(client):
    """El parser detecta las 3 secciones canónicas del workbook:
    Tesoros / Seamos mejores / Nuestra vida cristiana."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(
        html, language="es", week_start=date(2026, 6, 1), kind=MeetingKind.MIDWEEK,
        source_url="https://wol.jw.org/es/wol/meetings/r4/lp-s/2026/23",
    )
    section_ids = {s.section_id for s in program.sections}
    # IDs derivados del HTML semántico, no de M³
    assert len(program.sections) >= 3


def test_parse_midweek_items_have_titles(client):
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(html, language="es", week_start=date(2026, 6, 1),
                                  kind=MeetingKind.MIDWEEK, source_url="x")
    total_items = sum(len(s.items) for s in program.sections)
    assert total_items > 0
    # Cada item debe tener título no vacío
    for sec in program.sections:
        for item in sec.items:
            assert item.title.strip() != ""


def test_parse_extracts_bible_refs(client):
    """El workbook tiene refs bíblicas inline; el parser las captura."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(html, language="es", week_start=date(2026, 6, 1),
                                  kind=MeetingKind.MIDWEEK, source_url="x")
    total_refs = sum(
        len(item.bible_refs) for sec in program.sections for item in sec.items
    )
    assert total_refs > 0


def test_parse_extracts_media_refs(client):
    """El workbook tiene videos y JWPUB linkeados."""
    html = FIXTURE.read_text(encoding="utf-8")
    program = client.parse_html(html, language="es", week_start=date(2026, 6, 1),
                                  kind=MeetingKind.MIDWEEK, source_url="x")
    total_media = sum(
        len(item.media_refs) for sec in program.sections for item in sec.items
    )
    # Al menos un video o JWPUB esperado en una semana típica
    assert total_media >= 1


def test_week_url_pattern(client):
    url = client.build_week_url(language="es", year=2026, week=23)
    assert url.startswith("https://wol.jw.org/es/wol/meetings/")
    assert "/2026/23" in url


def test_week_url_uses_correct_resource_per_language(client):
    """Recurso r1 para inglés, r4 para español, r5 para portugués."""
    assert "/r1/" in client.build_week_url(language="en", year=2026, week=23)
    assert "/r4/" in client.build_week_url(language="es", year=2026, week=23)
    assert "/r5/" in client.build_week_url(language="pt", year=2026, week=23)
```

- [ ] **Step 3: Implementar cliente y parser**

```python
# packages/jw-meeting-media/src/jw_meeting_media/program_client.py
"""MeetingProgramClient: cliente HTTP + parser HTML para el programa
semanal de reuniones JW desde wol.jw.org.

Diseñado clean-room: el parser identifica estructura HTML semántica
del WOL (article.bodyTxt, h2, div.pGroup, etc.) inspeccionada via
DevTools del browser sobre la página pública, no via lectura de M³.

URL pattern (público, documentado en F1):
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}

Resource y lp_tag por idioma vienen del registry de F1.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag

from jw_core.languages import get_language_metadata
from jw_core.parsers.reference import parse_reference

from jw_meeting_media.models import (
    MediaKind,
    MediaRef,
    MeetingItem,
    MeetingKind,
    MeetingProgram,
    MeetingSection,
)

if TYPE_CHECKING:
    from jw_core.models import BibleRef


class MeetingProgramClient:
    """Cliente para descubrir y parsear el programa semanal."""

    BASE = "https://wol.jw.org"

    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http
        self._owned = http is None
        if self._owned:
            self._http = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30,
                headers={"User-Agent": "jw-agent-toolkit/F57"},
            )

    def build_week_url(self, *, language: str, year: int, week: int) -> str:
        """Construye URL del workbook para idioma+año+semana."""
        meta = get_language_metadata(language)
        resource = meta.wol_resource  # r1, r4, r5...
        lp_tag = meta.lp_tag           # lp-e, lp-s, lp-t...
        return f"{self.BASE}/{language}/wol/meetings/{resource}/{lp_tag}/{year}/{week}"

    async def fetch_week(
        self,
        *,
        language: str,
        year: int,
        week: int,
        kind: MeetingKind = MeetingKind.MIDWEEK,
    ) -> MeetingProgram:
        url = self.build_week_url(language=language, year=year, week=week)
        assert self._http is not None
        resp = await self._http.get(url)
        resp.raise_for_status()
        # Calcular week_start (lunes de la semana ISO)
        week_start = date.fromisocalendar(year, week, 1)
        return self.parse_html(
            resp.text,
            language=language,
            week_start=week_start,
            kind=kind,
            source_url=url,
        )

    def parse_html(
        self,
        html: str,
        *,
        language: str,
        week_start: date,
        kind: MeetingKind,
        source_url: str,
    ) -> MeetingProgram:
        """Parsea el HTML del workbook semanal."""
        soup = BeautifulSoup(html, "lxml")
        article = soup.find("article", class_="bodyTxt") or soup.find("article")
        sections: list[MeetingSection] = []
        if article is None:
            return MeetingProgram(
                language=language, week_start=week_start, kind=kind,
                sections=[], source_url=source_url,
                detected_at=datetime.now(timezone.utc).isoformat(),
            )

        # Estrategia: cada section del workbook está marcada por un h2/h3 mayor
        # y contiene un bloque siguiente con sus items. Identificamos via class
        # "section" o "groupTOC" según el layout actual de WOL.
        section_blocks = article.find_all(["section", "div"], class_=["section", "groupTOC", "pGroup"])
        if not section_blocks:
            # Fallback: agrupar por h2 directos del article
            section_blocks = self._fallback_group_by_h2(article)

        for idx, block in enumerate(section_blocks):
            heading = block.find(["h2", "h3"])
            if heading is None:
                continue
            section = MeetingSection(
                section_id=f"sec-{idx + 1}",
                title=heading.get_text(strip=True),
                items=self._extract_items(block, language=language),
            )
            if section.items:
                sections.append(section)

        return MeetingProgram(
            language=language,
            week_start=week_start,
            kind=kind,
            sections=sections,
            source_url=source_url,
            detected_at=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_items(self, block: Tag, *, language: str) -> list[MeetingItem]:
        items: list[MeetingItem] = []
        # Cada item es típicamente un <div class="docSubContent"> o <p class="su">
        item_nodes = block.find_all(["div", "p"], class_=["docSubContent", "su", "p", "qu"])
        position = 1
        for node in item_nodes:
            title_node = node.find(["h3", "strong", "b"]) or node
            title = title_node.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            text_content = node.get_text(" ", strip=True)
            refs = parse_reference(text_content) or []
            media_refs = self._extract_media_refs(node, language=language)
            items.append(
                MeetingItem(
                    item_id=f"i-{position}",
                    title=title[:200],
                    position=position,
                    bible_refs=refs,
                    media_refs=media_refs,
                )
            )
            position += 1
        return items

    def _extract_media_refs(self, node: Tag, *, language: str) -> list[MediaRef]:
        out: list[MediaRef] = []
        # Anchors a /wol/d/ son JWPUB/document; anchors a /wol/mp/ son media;
        # imgs con src en cms-imgp son imágenes.
        for a in node.find_all("a", href=True):
            href = a["href"]
            if "/wol/mp/" in href:
                out.append(MediaRef(
                    kind=MediaKind.VIDEO,
                    title=a.get_text(strip=True) or "media",
                    url=href if href.startswith("http") else self.BASE + href,
                    language=language,
                ))
            elif "/wol/d/" in href and any(t in href for t in ("docid", "/lp-")):
                out.append(MediaRef(
                    kind=MediaKind.JWPUB,
                    title=a.get_text(strip=True) or "document",
                    url=href if href.startswith("http") else self.BASE + href,
                    language=language,
                ))
        for img in node.find_all("img"):
            src = img.get("src", "")
            if "cms-imgp" in src or "imgp.jw-cdn.org" in src:
                out.append(MediaRef(
                    kind=MediaKind.IMAGE,
                    title=img.get("alt", "illustration") or "illustration",
                    url=src,
                    language=language,
                ))
        return out

    def _fallback_group_by_h2(self, article: Tag) -> list[Tag]:
        groups: list[Tag] = []
        current: list[Tag] = []
        for child in article.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "h2":
                if current:
                    # wrap current in synthetic div
                    synth = BeautifulSoup("<div></div>", "lxml").div
                    for c in current:
                        synth.append(c.extract())
                    groups.append(synth)
                current = [child]
            else:
                current.append(child)
        if current:
            synth = BeautifulSoup("<div></div>", "lxml").div
            for c in current:
                synth.append(c.extract())
            groups.append(synth)
        return groups

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest packages/jw-meeting-media/tests/test_program_client.py -v
```
Expected: 6 passed. (Si el HTML real cambió y los selectores no matchean, ajustar el parser — esa es la línea fina del clean-room: estructura observable del HTML, no código M³.)

- [ ] **Step 5: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/program_client.py packages/jw-meeting-media/tests/
git commit -m "feat(jw-meeting-media): F57.3 MeetingProgramClient HTML parser for weekly mwb workbook"
```

---

### Task 4: `MediaResolver` — refs → URLs descargables

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/media_resolver.py`
- Create: `packages/jw-meeting-media/tests/test_media_resolver.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-meeting-media/tests/test_media_resolver.py
"""F57 — MediaResolver resuelve MediaRef abstractas a URLs directas."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MediaKind, MediaRef


@pytest.mark.asyncio
async def test_resolve_image_passes_through():
    """Imágenes ya tienen URL directa; no requieren resolución."""
    resolver = MediaResolver()
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="img",
        url="https://imgp.jw-cdn.org/some.jpg",
    )
    resolved = await resolver.resolve(ref)
    assert resolved.url == ref.url


@pytest.mark.asyncio
async def test_resolve_video_uses_pubmedia():
    """Videos sin URL directa se resuelven vía PubMediaClient."""
    pub_client_mock = MagicMock()
    pub_client_mock.get_publication = AsyncMock(return_value={
        "files": {
            "es": {
                "MP4": [
                    {"file": {"url": "https://download.jw.org/video/example_720p.mp4"},
                     "title": "Example 720p",
                     "filesize": 12345678,
                     "checksum": "abc123"},
                ],
            },
        },
    })
    resolver = MediaResolver(pub_media_client=pub_client_mock)
    ref = MediaRef(
        kind=MediaKind.VIDEO,
        title="Example",
        url="",
        pub_code="pk",
        track=12,
        language="es",
    )
    resolved = await resolver.resolve(ref)
    assert resolved.url.endswith(".mp4")
    assert resolved.sha256 == "abc123"
```

- [ ] **Step 2: Implementar resolver**

```python
# packages/jw-meeting-media/src/jw_meeting_media/media_resolver.py
"""MediaResolver: dado un MediaRef abstracto, devuelve un MediaRef con
url directa lista para descargar.

Reusa PubMediaClient (F2) cuando hay pub_code+track, sino pass-through.
"""
from __future__ import annotations

from typing import Any

from jw_meeting_media.models import MediaKind, MediaRef


class MediaResolver:
    def __init__(self, pub_media_client: Any | None = None):
        self._pub = pub_media_client

    async def resolve(self, ref: MediaRef) -> MediaRef:
        if ref.url and ref.url.startswith("http"):
            return ref  # ya resuelto

        if ref.kind == MediaKind.VIDEO and ref.pub_code and ref.track is not None:
            return await self._resolve_video_pubmedia(ref)

        if ref.kind == MediaKind.AUDIO and ref.pub_code and ref.track is not None:
            return await self._resolve_audio_pubmedia(ref)

        # JWPUB / EXTERNAL: la URL viene tal cual; opcionalmente HEAD para validar
        return ref

    async def _resolve_video_pubmedia(self, ref: MediaRef) -> MediaRef:
        if self._pub is None:
            from jw_core.clients.pub_media import PubMediaClient
            self._pub = PubMediaClient()
        response = await self._pub.get_publication(
            pub=ref.pub_code, track=ref.track, language=ref.language or "es",
        )
        # Estructura: response["files"][lang]["MP4" | "M4V"] = [{file:{url}, ...}]
        files = (response or {}).get("files", {}).get(ref.language or "es", {})
        formats = files.get("MP4") or files.get("M4V") or []
        if not formats:
            return ref  # no se pudo resolver
        # Tomar el primero (M³ típicamente toma el mejor por bitrate; F57 lo simplifica)
        chosen = formats[0]
        return ref.model_copy(update={
            "url": chosen.get("file", {}).get("url", ""),
            "sha256": chosen.get("checksum"),
            "duration_seconds": chosen.get("duration"),
        })

    async def _resolve_audio_pubmedia(self, ref: MediaRef) -> MediaRef:
        if self._pub is None:
            from jw_core.clients.pub_media import PubMediaClient
            self._pub = PubMediaClient()
        response = await self._pub.get_publication(
            pub=ref.pub_code, track=ref.track, language=ref.language or "es",
        )
        files = (response or {}).get("files", {}).get(ref.language or "es", {})
        formats = files.get("MP3") or []
        if not formats:
            return ref
        chosen = formats[0]
        return ref.model_copy(update={
            "url": chosen.get("file", {}).get("url", ""),
            "sha256": chosen.get("checksum"),
        })
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest packages/jw-meeting-media/tests/test_media_resolver.py -v
```
Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/media_resolver.py packages/jw-meeting-media/tests/test_media_resolver.py
git commit -m "feat(jw-meeting-media): F57.4 MediaResolver wraps PubMediaClient for video audio refs"
```

---

### Task 5: `Downloader` con cache resumible

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/downloader.py`
- Create: `packages/jw-meeting-media/tests/test_downloader.py`

- [ ] **Step 1: Failing tests con httpx mock**

```python
# packages/jw-meeting-media/tests/test_downloader.py
"""F57 — Downloader con idempotencia por sha256 y cache local."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from jw_meeting_media.downloader import Downloader
from jw_meeting_media.models import MediaKind, MediaRef


@pytest.fixture()
def cache_root(tmp_path) -> Path:
    return tmp_path / "meetings_cache"


@pytest.mark.asyncio
async def test_download_writes_to_cache(httpx_mock, cache_root):
    content = b"fake-jpeg-bytes" * 100
    expected_sha = hashlib.sha256(content).hexdigest()
    httpx_mock.add_response(
        url="https://imgp.jw-cdn.org/test.jpg",
        content=content,
    )

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="t",
        url="https://imgp.jw-cdn.org/test.jpg",
        sha256=expected_sha,
        language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.exists()
    assert local.read_bytes() == content


@pytest.mark.asyncio
async def test_download_skips_if_sha256_matches(httpx_mock, cache_root):
    """Re-download con archivo cacheado válido no hace HTTP."""
    content = b"data" * 100
    expected_sha = hashlib.sha256(content).hexdigest()

    # Pre-cache el archivo
    target_dir = cache_root / "es" / "2026" / "23"
    target_dir.mkdir(parents=True)
    cached_file = target_dir / "abc.jpg"
    cached_file.write_bytes(content)

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE,
        title="t",
        url="https://imgp.jw-cdn.org/abc.jpg",
        sha256=expected_sha,
        language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local == cached_file
    # NO se hicieron requests
    assert len(httpx_mock.get_requests()) == 0


@pytest.mark.asyncio
async def test_download_redownloads_if_sha_mismatch(httpx_mock, cache_root):
    """Si el archivo cacheado tiene sha distinto, re-descarga."""
    good_content = b"good" * 100
    bad_content = b"corrupted"
    expected_sha = hashlib.sha256(good_content).hexdigest()

    target_dir = cache_root / "es" / "2026" / "23"
    target_dir.mkdir(parents=True)
    cached_file = target_dir / "xyz.jpg"
    cached_file.write_bytes(bad_content)

    httpx_mock.add_response(
        url="https://imgp.jw-cdn.org/xyz.jpg", content=good_content,
    )

    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE, title="t",
        url="https://imgp.jw-cdn.org/xyz.jpg", sha256=expected_sha, language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.read_bytes() == good_content


@pytest.mark.asyncio
async def test_download_without_sha_uses_url_basename(httpx_mock, cache_root):
    """Sin sha256, el archivo se cachea por basename de URL."""
    content = b"x" * 10
    httpx_mock.add_response(url="https://example.com/foo.png", content=content)
    dl = Downloader(cache_root=cache_root)
    ref = MediaRef(
        kind=MediaKind.IMAGE, title="t",
        url="https://example.com/foo.png", sha256=None, language="es",
    )
    local = await dl.download(ref, language="es", year=2026, week=23)
    assert local.name == "foo.png"
    assert local.read_bytes() == content
```

- [ ] **Step 2: Implementar Downloader**

```python
# packages/jw-meeting-media/src/jw_meeting_media/downloader.py
"""Downloader con cache local y verificación sha256.

Path scheme: <cache_root>/<lang>/<year>/<week>/<basename>
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from jw_meeting_media.models import MediaRef


class Downloader:
    def __init__(
        self,
        *,
        cache_root: Path,
        http: httpx.AsyncClient | None = None,
    ):
        self._cache_root = Path(cache_root)
        self._cache_root.mkdir(parents=True, exist_ok=True)
        self._http = http
        self._owned = http is None
        if self._owned:
            self._http = httpx.AsyncClient(
                follow_redirects=True,
                timeout=120,
                headers={"User-Agent": "jw-agent-toolkit/F57"},
            )

    async def download(
        self,
        ref: MediaRef,
        *,
        language: str,
        year: int,
        week: int,
    ) -> Path:
        if not ref.url.startswith("http"):
            raise ValueError(f"ref has no http url: {ref}")
        target_dir = self._cache_root / language / str(year) / str(week)
        target_dir.mkdir(parents=True, exist_ok=True)
        name = self._filename_for(ref)
        target = target_dir / name

        if target.exists() and self._is_valid(target, ref.sha256):
            return target

        assert self._http is not None
        resp = await self._http.get(ref.url)
        resp.raise_for_status()
        content = resp.content

        if ref.sha256:
            actual = hashlib.sha256(content).hexdigest()
            if actual != ref.sha256:
                raise RuntimeError(
                    f"sha256 mismatch for {ref.url}: expected {ref.sha256}, got {actual}"
                )

        target.write_bytes(content)
        return target

    def _filename_for(self, ref: MediaRef) -> str:
        if ref.sha256:
            ext = Path(urlparse(ref.url).path).suffix or ".bin"
            return f"{ref.sha256[:16]}{ext}"
        return Path(urlparse(ref.url).path).name or "media.bin"

    def _is_valid(self, path: Path, expected_sha: str | None) -> bool:
        if expected_sha is None:
            return True
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        return actual == expected_sha

    async def aclose(self) -> None:
        if self._owned and self._http is not None:
            await self._http.aclose()
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest packages/jw-meeting-media/tests/test_downloader.py -v
```
Expected: 4 passed. (Requires `pytest-httpx` — añadir a dev deps si no está.)

- [ ] **Step 4: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/downloader.py packages/jw-meeting-media/tests/test_downloader.py
git commit -m "feat(jw-meeting-media): F57.5 Downloader with sha256 cache plus idempotency"
```

---

### Task 6: Storage sqlite — programas + downloads

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/storage.py`
- Create: `packages/jw-meeting-media/tests/test_storage.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-meeting-media/tests/test_storage.py
"""F57 — Storage sqlite para programas semanales + tracking descargas."""
from __future__ import annotations

from datetime import date

import pytest

from jw_meeting_media.models import (
    MediaKind, MediaRef, MeetingItem, MeetingKind, MeetingProgram, MeetingSection,
)
from jw_meeting_media.storage import MeetingStorage


@pytest.fixture()
def storage(tmp_path) -> MeetingStorage:
    return MeetingStorage(db_path=tmp_path / "meetings.db")


def test_save_and_load_program(storage):
    prog = MeetingProgram(
        language="es",
        week_start=date(2026, 6, 1),
        kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(section_id="s1", title="Tesoros", items=[
                MeetingItem(item_id="i1", title="Lectura", position=1,
                            bible_refs=[], media_refs=[
                                MediaRef(kind=MediaKind.IMAGE, title="x",
                                         url="https://example.com/x.jpg"),
                            ]),
            ]),
        ],
        source_url="https://wol.jw.org/.../2026/23",
    )
    storage.save_program(prog)
    loaded = storage.load_program(language="es", year=2026, week=23,
                                   kind=MeetingKind.MIDWEEK)
    assert loaded is not None
    assert loaded.language == "es"
    assert len(loaded.sections) == 1
    assert loaded.sections[0].items[0].media_refs[0].kind == MediaKind.IMAGE


def test_load_unknown_program_returns_none(storage):
    assert storage.load_program(language="es", year=1999, week=1,
                                  kind=MeetingKind.MIDWEEK) is None


def test_mark_download_complete(storage, tmp_path):
    ref = MediaRef(kind=MediaKind.IMAGE, title="t",
                    url="https://example.com/x.jpg", sha256="abc")
    storage.mark_downloaded(ref, local_path=tmp_path / "x.jpg")
    assert storage.is_downloaded(ref) is True
    info = storage.get_download_info(ref)
    assert info is not None
    assert info["sha256"] == "abc"


def test_save_program_replaces_existing(storage):
    prog1 = MeetingProgram(
        language="es", week_start=date(2026, 6, 1), kind=MeetingKind.MIDWEEK,
        sections=[], source_url="x",
    )
    storage.save_program(prog1)
    prog2 = MeetingProgram(
        language="es", week_start=date(2026, 6, 1), kind=MeetingKind.MIDWEEK,
        sections=[MeetingSection(section_id="s1", title="t", items=[])],
        source_url="x",
    )
    storage.save_program(prog2)
    loaded = storage.load_program(language="es", year=2026, week=23,
                                    kind=MeetingKind.MIDWEEK)
    # Idempotent overwrite — single section after second save
    assert loaded is not None
    assert len(loaded.sections) == 1
```

- [ ] **Step 2: Implementar Storage**

```python
# packages/jw-meeting-media/src/jw_meeting_media/storage.py
"""Storage sqlite local para meetings y downloads.

Esquema:
    CREATE TABLE programs (
        language TEXT, year INT, week INT, kind TEXT,
        program_json TEXT NOT NULL,
        saved_at TEXT NOT NULL,
        PRIMARY KEY (language, year, week, kind)
    );

    CREATE TABLE downloads (
        ref_key TEXT PRIMARY KEY,   -- sha256 or url
        ref_url TEXT NOT NULL,
        local_path TEXT NOT NULL,
        sha256 TEXT,
        downloaded_at TEXT NOT NULL
    );
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path

from jw_meeting_media.models import MediaRef, MeetingKind, MeetingProgram


_SCHEMA = """
CREATE TABLE IF NOT EXISTS programs (
    language TEXT NOT NULL,
    year INT NOT NULL,
    week INT NOT NULL,
    kind TEXT NOT NULL,
    program_json TEXT NOT NULL,
    saved_at TEXT NOT NULL,
    PRIMARY KEY (language, year, week, kind)
);
CREATE TABLE IF NOT EXISTS downloads (
    ref_key TEXT PRIMARY KEY,
    ref_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    sha256 TEXT,
    downloaded_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


class MeetingStorage:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(_SCHEMA)

    def save_program(self, prog: MeetingProgram) -> None:
        year, week, _ = prog.week_start.isocalendar()
        payload = prog.model_dump_json()
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO programs "
                "(language, year, week, kind, program_json, saved_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (prog.language, year, week, prog.kind.value, payload,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def load_program(
        self, *, language: str, year: int, week: int, kind: MeetingKind,
    ) -> MeetingProgram | None:
        with closing(sqlite3.connect(self.db_path)) as conn:
            row = conn.execute(
                "SELECT program_json FROM programs WHERE language=? AND year=? AND week=? AND kind=?",
                (language, year, week, kind.value),
            ).fetchone()
        if row is None:
            return None
        return MeetingProgram.model_validate_json(row[0])

    def mark_downloaded(self, ref: MediaRef, *, local_path: Path) -> None:
        key = ref.sha256 or ref.url
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO downloads "
                "(ref_key, ref_url, local_path, sha256, downloaded_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, ref.url, str(local_path), ref.sha256,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def is_downloaded(self, ref: MediaRef) -> bool:
        return self.get_download_info(ref) is not None

    def get_download_info(self, ref: MediaRef) -> dict | None:
        key = ref.sha256 or ref.url
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ref_url, local_path, sha256, downloaded_at FROM downloads WHERE ref_key=?",
                (key,),
            ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest packages/jw-meeting-media/tests/test_storage.py -v
```
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/storage.py packages/jw-meeting-media/tests/test_storage.py
git commit -m "feat(jw-meeting-media): F57.6 sqlite storage for programs plus downloads tracking"
```

---

### Task 7: Thumbnailer para imagen + video

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/thumbnailer.py`
- Create: `packages/jw-meeting-media/tests/test_thumbnailer.py`

- [ ] **Step 1: Tests con fixtures sintéticos**

```python
# packages/jw-meeting-media/tests/test_thumbnailer.py
"""F57 — Thumbnailer para imagen y video (ffmpeg)."""
from __future__ import annotations

from pathlib import Path

import pytest

from jw_meeting_media.thumbnailer import Thumbnailer

pytest.importorskip("PIL", reason="Pillow not installed (extras [thumbnails])")


@pytest.fixture()
def thumbnailer(tmp_path) -> Thumbnailer:
    return Thumbnailer(cache_root=tmp_path / "thumbs")


def test_thumbnail_jpeg(thumbnailer, tmp_path):
    from PIL import Image
    img_path = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), color="red").save(img_path, "JPEG")

    thumb_path = thumbnailer.for_image(img_path, max_size=200)
    assert thumb_path.exists()
    with Image.open(thumb_path) as t:
        assert max(t.size) <= 200


def test_thumbnail_idempotent(thumbnailer, tmp_path):
    from PIL import Image
    img_path = tmp_path / "source.jpg"
    Image.new("RGB", (800, 600), color="blue").save(img_path, "JPEG")

    thumb1 = thumbnailer.for_image(img_path, max_size=200)
    mtime1 = thumb1.stat().st_mtime
    thumb2 = thumbnailer.for_image(img_path, max_size=200)
    assert thumb1 == thumb2
    assert mtime1 == thumb2.stat().st_mtime  # no regenerated
```

- [ ] **Step 2: Implementar Thumbnailer**

```python
# packages/jw-meeting-media/src/jw_meeting_media/thumbnailer.py
"""Genera thumbnails para imagen (Pillow) y video (ffmpeg subprocess).

Cache idempotente por sha256(input_path)+max_size.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


class Thumbnailer:
    def __init__(self, *, cache_root: Path):
        self._cache_root = Path(cache_root)
        self._cache_root.mkdir(parents=True, exist_ok=True)

    def for_image(self, source: Path, *, max_size: int = 200) -> Path:
        from PIL import Image

        key = self._cache_key(source, max_size)
        target = self._cache_root / f"{key}.jpg"
        if target.exists():
            return target
        with Image.open(source) as img:
            img.thumbnail((max_size, max_size))
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(target, "JPEG", quality=85)
        return target

    def for_video(self, source: Path, *, max_size: int = 200,
                  at_seconds: float = 1.0) -> Path:
        key = self._cache_key(source, max_size, suffix=f"@{at_seconds}")
        target = self._cache_root / f"{key}.jpg"
        if target.exists():
            return target
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(source),
                "-ss", str(at_seconds), "-vframes", "1",
                "-vf", f"scale={max_size}:-1",
                str(target),
            ],
            check=True, stderr=subprocess.DEVNULL,
        )
        return target

    def _cache_key(self, source: Path, max_size: int, suffix: str = "") -> str:
        with source.open("rb") as f:
            h = hashlib.sha256(f.read(65536)).hexdigest()[:16]
        return f"{h}_{max_size}{suffix}"
```

- [ ] **Step 3: Run, expect PASS o skipped**

```bash
uv run pytest packages/jw-meeting-media/tests/test_thumbnailer.py -v
```
Expected: 2 passed (con Pillow), o skipped sin Pillow.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/thumbnailer.py packages/jw-meeting-media/tests/test_thumbnailer.py
git commit -m "feat(jw-meeting-media): F57.7 Thumbnailer for images plus ffmpeg video frames"
```

---

### Task 8: `PresenterSession` con cola y FSM

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/presenter_state.py`
- Create: `packages/jw-meeting-media/tests/test_presenter_state.py`

- [ ] **Step 1: Failing tests**

```python
# packages/jw-meeting-media/tests/test_presenter_state.py
"""F57 — Presenter session manager (server-side state)."""
from __future__ import annotations

import pytest

from jw_meeting_media.models import (
    MediaKind, MediaRef, MeetingItem, MeetingKind, MeetingProgram, MeetingSection,
)
from jw_meeting_media.presenter_state import PresenterManager


def make_program() -> MeetingProgram:
    from datetime import date
    return MeetingProgram(
        language="es", week_start=date(2026, 6, 1), kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(section_id="s1", title="Sec1", items=[
                MeetingItem(item_id=f"i{j}", title=f"Item {j}", position=j,
                            bible_refs=[], media_refs=[
                                MediaRef(kind=MediaKind.IMAGE, title=f"img{j}",
                                         url=f"https://x/{j}.jpg")
                            ])
                for j in range(1, 4)
            ]),
        ],
        source_url="x",
    )


def test_create_session_flattens_items():
    mgr = PresenterManager()
    session_id = mgr.create_session(program=make_program())
    state = mgr.get_state(session_id)
    assert len(state.queue) == 3  # 3 items aplanados


def test_play_pause_toggles_state():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.play(sid)
    assert mgr.get_state(sid).playing is True
    mgr.pause(sid)
    assert mgr.get_state(sid).playing is False


def test_next_advances_cursor():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid)
    assert mgr.get_state(sid).cursor == 1
    mgr.next_(sid)
    assert mgr.get_state(sid).cursor == 2


def test_next_at_end_clamps():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid); mgr.next_(sid)  # at 2
    mgr.next_(sid)  # try advance past end
    assert mgr.get_state(sid).cursor == 2


def test_stop_resets_cursor_and_pauses():
    mgr = PresenterManager()
    sid = mgr.create_session(program=make_program())
    mgr.next_(sid); mgr.play(sid)
    mgr.stop(sid)
    state = mgr.get_state(sid)
    assert state.cursor == 0 and state.playing is False


def test_unknown_session_raises():
    mgr = PresenterManager()
    with pytest.raises(KeyError):
        mgr.get_state("does-not-exist")
```

- [ ] **Step 2: Implementar PresenterManager**

```python
# packages/jw-meeting-media/src/jw_meeting_media/presenter_state.py
"""PresenterManager: gestiona sesiones de presenter activas.

Sesiones in-memory (no persisten). Una sesión = una ventana Tauri
mostrando media de un programa. Múltiples sesiones simultáneas
soportadas (ej. para multi-congregación).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from jw_meeting_media.models import MeetingProgram, PresenterSession


class PresenterManager:
    def __init__(self) -> None:
        self._sessions: dict[str, PresenterSession] = {}

    def create_session(self, *, program: MeetingProgram) -> str:
        sid = str(uuid.uuid4())
        queue = [item for sec in program.sections for item in sec.items]
        self._sessions[sid] = PresenterSession(
            session_id=sid,
            program_url=program.source_url,
            queue=queue,
            cursor=0,
            playing=False,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        return sid

    def get_state(self, session_id: str) -> PresenterSession:
        if session_id not in self._sessions:
            raise KeyError(f"unknown session: {session_id}")
        return self._sessions[session_id]

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def play(self, session_id: str) -> None:
        self.get_state(session_id).playing = True

    def pause(self, session_id: str) -> None:
        self.get_state(session_id).playing = False

    def next_(self, session_id: str) -> None:
        state = self.get_state(session_id)
        if state.cursor + 1 < len(state.queue):
            state.cursor += 1

    def prev(self, session_id: str) -> None:
        state = self.get_state(session_id)
        if state.cursor > 0:
            state.cursor -= 1

    def stop(self, session_id: str) -> None:
        state = self.get_state(session_id)
        state.cursor = 0
        state.playing = False

    def destroy(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
```

- [ ] **Step 3: Run, expect PASS**

```bash
uv run pytest packages/jw-meeting-media/tests/test_presenter_state.py -v
```
Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/presenter_state.py packages/jw-meeting-media/tests/test_presenter_state.py
git commit -m "feat(jw-meeting-media): F57.8 PresenterManager FSM with multi-session support"
```

---

### Task 9: CLI `jw meeting ...` (sub-app Typer)

**Files:**
- Create: `packages/jw-meeting-media/src/jw_meeting_media/cli.py`
- Create: `packages/jw-meeting-media/tests/test_cli.py`
- Modify: `packages/jw-cli/src/jw_cli/main.py` — registrar sub-app

- [ ] **Step 1: Implementar CLI**

```python
# packages/jw-meeting-media/src/jw_meeting_media/cli.py
"""jw meeting CLI subcommands."""
from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import typer

from jw_meeting_media.downloader import Downloader
from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MeetingKind
from jw_meeting_media.program_client import MeetingProgramClient
from jw_meeting_media.storage import MeetingStorage

app = typer.Typer(name="meeting", help="Reunión-en-vivo: discover / download / present")


def _default_cache_root() -> Path:
    return Path("~/.jw-agent-toolkit/meetings").expanduser()


@app.command("discover")
def discover(
    language: str = typer.Option(..., "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
    output: Path | None = typer.Option(None, "--output"),
    save: bool = typer.Option(True, "--save/--no-save"),
) -> None:
    """Descubre el programa semanal y opcionalmente lo guarda en sqlite local."""
    async def _run():
        client = MeetingProgramClient()
        program = await client.fetch_week(language=language, year=year, week=week, kind=kind)
        await client.aclose()
        if save:
            storage = MeetingStorage(_default_cache_root() / "meetings.db")
            storage.save_program(program)
        payload = json.loads(program.model_dump_json())
        if output:
            output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
            typer.echo(f"Wrote {output}")
        else:
            typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    asyncio.run(_run())


@app.command("download")
def download(
    language: str = typer.Option(..., "--language", "-l"),
    year: int = typer.Option(..., "--year", "-y"),
    week: int = typer.Option(..., "--week", "-w"),
    kind: MeetingKind = typer.Option(MeetingKind.MIDWEEK, "--kind"),
) -> None:
    """Descarga toda la media del programa para esa semana al cache local."""
    async def _run():
        storage = MeetingStorage(_default_cache_root() / "meetings.db")
        program = storage.load_program(language=language, year=year, week=week, kind=kind)
        if program is None:
            typer.echo("No program saved. Run 'discover' first.", err=True)
            raise typer.Exit(1)

        resolver = MediaResolver()
        dl = Downloader(cache_root=_default_cache_root() / "media")

        total = 0
        succeeded = 0
        for sec in program.sections:
            for item in sec.items:
                for ref in item.media_refs:
                    total += 1
                    try:
                        resolved = await resolver.resolve(ref)
                        if not resolved.url:
                            typer.echo(f"  ✗ unresolved: {ref.title}", err=True)
                            continue
                        local = await dl.download(resolved, language=language, year=year, week=week)
                        storage.mark_downloaded(resolved, local_path=local)
                        succeeded += 1
                        typer.echo(f"  ✓ {ref.title} -> {local}")
                    except Exception as exc:
                        typer.echo(f"  ✗ {ref.title}: {exc}", err=True)
        typer.echo(f"\nDone: {succeeded}/{total} media downloaded")
        await dl.aclose()

    asyncio.run(_run())


@app.command("list")
def list_programs() -> None:
    """Lista programas guardados localmente."""
    storage_path = _default_cache_root() / "meetings.db"
    if not storage_path.exists():
        typer.echo("No programs saved yet.")
        return
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(storage_path)) as conn:
        rows = conn.execute(
            "SELECT language, year, week, kind, saved_at FROM programs "
            "ORDER BY year DESC, week DESC"
        ).fetchall()
    for r in rows:
        typer.echo(f"  {r[1]}/{r[2]:02d} [{r[0]}] {r[3]} (saved {r[4][:10]})")
```

- [ ] **Step 2: Registrar sub-app en `jw-cli/main.py`**

Localizar dónde se registran las sub-apps (`verse`, `daily`, `topic`, etc.) y añadir:

```python
try:
    from jw_meeting_media.cli import app as meeting_app
    app.add_typer(meeting_app, name="meeting")
except ImportError:
    pass  # extra not installed
```

- [ ] **Step 3: Tests del CLI**

```python
# packages/jw-meeting-media/tests/test_cli.py
"""F57 — CLI smoke tests."""
from __future__ import annotations

from typer.testing import CliRunner

from jw_meeting_media.cli import app


def test_help_lists_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "discover" in result.stdout
    assert "download" in result.stdout
    assert "list" in result.stdout


def test_list_no_programs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "jw_meeting_media.cli._default_cache_root", lambda: tmp_path
    )
    runner = CliRunner()
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0
    assert "No programs" in result.stdout
```

- [ ] **Step 4: Run, expect PASS**

```bash
uv run pytest packages/jw-meeting-media/tests/test_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add packages/jw-meeting-media/src/jw_meeting_media/cli.py packages/jw-meeting-media/tests/test_cli.py packages/jw-cli/src/jw_cli/main.py
git commit -m "feat(jw-meeting-media): F57.9 CLI jw meeting discover download list"
```

---

### Task 10: REST API endpoints en `jw_mcp.rest_api`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/rest_api.py`
- Create: `packages/jw-mcp/tests/test_rest_presenter.py`

- [ ] **Step 1: Añadir endpoints**

```python
# Agregar al fastapi app de rest_api.py

from jw_meeting_media.media_resolver import MediaResolver
from jw_meeting_media.models import MeetingKind, MeetingProgram
from jw_meeting_media.presenter_state import PresenterManager
from jw_meeting_media.storage import MeetingStorage

_presenter = PresenterManager()
_storage_singleton: MeetingStorage | None = None


def _storage() -> MeetingStorage:
    global _storage_singleton
    if _storage_singleton is None:
        _storage_singleton = MeetingStorage(
            Path("~/.jw-agent-toolkit/meetings/meetings.db").expanduser()
        )
    return _storage_singleton


@app.post("/presenter/sessions")
async def presenter_create_session(language: str, year: int, week: int, kind: str = "midweek"):
    program = _storage().load_program(
        language=language, year=year, week=week, kind=MeetingKind(kind),
    )
    if program is None:
        return JSONResponse({"error": "program not found; discover first"}, status_code=404)
    sid = _presenter.create_session(program=program)
    return {"session_id": sid}


@app.get("/presenter/sessions/{sid}/state")
async def presenter_state(sid: str):
    try:
        return _presenter.get_state(sid).model_dump()
    except KeyError:
        return JSONResponse({"error": "unknown session"}, status_code=404)


@app.post("/presenter/sessions/{sid}/play")
async def presenter_play(sid: str):
    _presenter.play(sid); return {"ok": True}


@app.post("/presenter/sessions/{sid}/pause")
async def presenter_pause(sid: str):
    _presenter.pause(sid); return {"ok": True}


@app.post("/presenter/sessions/{sid}/next")
async def presenter_next(sid: str):
    _presenter.next_(sid); return {"ok": True}


@app.post("/presenter/sessions/{sid}/prev")
async def presenter_prev(sid: str):
    _presenter.prev(sid); return {"ok": True}


@app.post("/presenter/sessions/{sid}/stop")
async def presenter_stop(sid: str):
    _presenter.stop(sid); return {"ok": True}


@app.delete("/presenter/sessions/{sid}")
async def presenter_destroy(sid: str):
    _presenter.destroy(sid); return {"ok": True}
```

- [ ] **Step 2: Tests con httpx/AsyncClient contra FastAPI app**

```python
# packages/jw-mcp/tests/test_rest_presenter.py
"""F57 — REST endpoints para presenter."""
from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient, ASGITransport

from jw_meeting_media.models import (
    MediaKind, MediaRef, MeetingItem, MeetingKind, MeetingProgram, MeetingSection,
)


@pytest.fixture()
def app_with_program(tmp_path, monkeypatch):
    from jw_mcp.rest_api import app, _storage
    monkeypatch.setattr(
        "jw_mcp.rest_api._storage_singleton", None
    )
    monkeypatch.setattr(
        "jw_mcp.rest_api.Path.expanduser", lambda self: tmp_path / "meetings"
    )
    storage = _storage()
    program = MeetingProgram(
        language="es", week_start=date(2026, 6, 1), kind=MeetingKind.MIDWEEK,
        sections=[
            MeetingSection(section_id="s1", title="t", items=[
                MeetingItem(item_id="i1", title="x", position=1,
                            bible_refs=[], media_refs=[]),
            ]),
        ],
        source_url="x",
    )
    storage.save_program(program)
    return app


@pytest.mark.asyncio
async def test_create_session_returns_id(app_with_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_program),
        base_url="http://test",
    ) as ac:
        resp = await ac.post(
            "/presenter/sessions",
            params={"language": "es", "year": 2026, "week": 23, "kind": "midweek"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data


@pytest.mark.asyncio
async def test_play_pause_cycle(app_with_program):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_program), base_url="http://test",
    ) as ac:
        sid = (await ac.post("/presenter/sessions", params={
            "language": "es", "year": 2026, "week": 23
        })).json()["session_id"]
        await ac.post(f"/presenter/sessions/{sid}/play")
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["playing"] is True
        await ac.post(f"/presenter/sessions/{sid}/pause")
        state = (await ac.get(f"/presenter/sessions/{sid}/state")).json()
        assert state["playing"] is False
```

- [ ] **Step 3: Run, expect PASS**

```bash
uv run pytest packages/jw-mcp/tests/test_rest_presenter.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/src/jw_mcp/rest_api.py packages/jw-mcp/tests/test_rest_presenter.py
git commit -m "feat(jw-mcp): F57.10 REST presenter endpoints for Tauri window"
```

---

### Task 11: Ventana Tauri "presenter" (frontend vanilla JS)

**Files:**
- Modify: `apps/desktop/src-tauri/tauri.conf.json` — añadir window
- Create: `apps/desktop/src/presenter.html`
- Create: `apps/desktop/src/presenter.js`
- Create: `apps/desktop/src/presenter.css`

- [ ] **Step 1: Añadir window en `tauri.conf.json`**

Editar `apps/desktop/src-tauri/tauri.conf.json`, dentro de `app.windows`, **añadir** (no reemplazar la existente):

```json
{
  "label": "presenter",
  "title": "Presenter — jw-agent-toolkit",
  "width": 1280,
  "height": 720,
  "url": "presenter.html",
  "visible": false,
  "fullscreen": false,
  "resizable": true,
  "decorations": true
}
```

- [ ] **Step 2: HTML básico**

```html
<!-- apps/desktop/src/presenter.html -->
<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <title>Presenter</title>
    <link rel="stylesheet" href="presenter.css" />
  </head>
  <body>
    <div id="stage">
      <img id="media-image" hidden />
      <video id="media-video" hidden controls></video>
      <div id="placeholder">Carga una sesión para empezar.</div>
    </div>
    <div id="controls">
      <button id="prev">⏮</button>
      <button id="play-pause">⏵</button>
      <button id="next">⏭</button>
      <button id="stop">⏹</button>
      <span id="position">— / —</span>
      <span id="title-display"></span>
    </div>
    <script src="presenter.js"></script>
  </body>
</html>
```

- [ ] **Step 3: CSS minimal**

```css
/* apps/desktop/src/presenter.css */
body {
  margin: 0;
  background: #000;
  color: #eee;
  font-family: system-ui, sans-serif;
  display: flex;
  flex-direction: column;
  height: 100vh;
}
#stage {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
#media-image, #media-video {
  max-width: 100%;
  max-height: 100%;
}
#placeholder {
  font-size: 1.4em;
  color: #666;
}
#controls {
  display: flex;
  gap: 1em;
  padding: 0.8em 1em;
  background: #222;
  align-items: center;
}
#controls button {
  background: #333;
  color: #fff;
  border: 1px solid #555;
  padding: 0.4em 0.8em;
  font-size: 1.2em;
  cursor: pointer;
}
#controls button:hover { background: #444; }
#title-display {
  margin-left: auto;
  font-weight: 500;
}
```

- [ ] **Step 4: JS controller vanilla**

```javascript
// apps/desktop/src/presenter.js
const API = "http://127.0.0.1:8765";
let sessionId = null;
let pollHandle = null;

const $image = document.getElementById("media-image");
const $video = document.getElementById("media-video");
const $placeholder = document.getElementById("placeholder");
const $position = document.getElementById("position");
const $title = document.getElementById("title-display");
const $playPause = document.getElementById("play-pause");

function startSession(language, year, week, kind) {
  return fetch(
    `${API}/presenter/sessions?language=${language}&year=${year}&week=${week}&kind=${kind}`,
    { method: "POST" }
  )
    .then((r) => r.json())
    .then((data) => {
      if (data.error) throw new Error(data.error);
      sessionId = data.session_id;
      startPolling();
    });
}

function startPolling() {
  pollHandle = setInterval(refreshState, 800);
  refreshState();
}

async function refreshState() {
  if (!sessionId) return;
  const resp = await fetch(`${API}/presenter/sessions/${sessionId}/state`);
  const state = await resp.json();
  if (state.error) return;
  render(state);
}

function render(state) {
  const item = state.queue[state.cursor];
  if (!item) {
    $placeholder.hidden = false;
    $image.hidden = true;
    $video.hidden = true;
    return;
  }
  $placeholder.hidden = true;
  $position.textContent = `${state.cursor + 1} / ${state.queue.length}`;
  $title.textContent = item.title;
  $playPause.textContent = state.playing ? "⏸" : "⏵";

  const firstMedia = (item.media_refs || [])[0];
  if (!firstMedia) {
    $image.hidden = true;
    $video.hidden = true;
    return;
  }
  if (firstMedia.kind === "image") {
    $image.src = firstMedia.local_path
      ? `file://${firstMedia.local_path}`
      : firstMedia.url;
    $image.hidden = false;
    $video.hidden = true;
  } else if (firstMedia.kind === "video") {
    $video.src = firstMedia.local_path
      ? `file://${firstMedia.local_path}`
      : firstMedia.url;
    $video.hidden = false;
    $image.hidden = true;
    if (state.playing) $video.play().catch(() => {});
    else $video.pause();
  }
}

document.getElementById("prev").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/prev`, { method: "POST" });
document.getElementById("next").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/next`, { method: "POST" });
document.getElementById("play-pause").onclick = () => {
  const action = $playPause.textContent === "⏸" ? "pause" : "play";
  fetch(`${API}/presenter/sessions/${sessionId}/${action}`, { method: "POST" });
};
document.getElementById("stop").onclick = () =>
  fetch(`${API}/presenter/sessions/${sessionId}/stop`, { method: "POST" });

document.addEventListener("keydown", (e) => {
  if (!sessionId) return;
  if (e.key === " ") document.getElementById("play-pause").click();
  if (e.key === "ArrowRight") document.getElementById("next").click();
  if (e.key === "ArrowLeft") document.getElementById("prev").click();
  if (e.key === "Escape") document.getElementById("stop").click();
});

// Bootstrap: read query string ?language=es&year=2026&week=23&kind=midweek
const params = new URLSearchParams(location.search);
const lang = params.get("language");
const year = parseInt(params.get("year"));
const week = parseInt(params.get("week"));
const kind = params.get("kind") || "midweek";
if (lang && year && week) {
  startSession(lang, year, week, kind).catch((err) => {
    $placeholder.textContent = `Error: ${err.message}`;
  });
}
```

- [ ] **Step 5: Smoke build Tauri**

```bash
cd /Users/elias/Documents/Trabajo/jw-agent-toolkit/apps/desktop
yarn install
yarn tauri build --debug
```
Expected: build OK con dos windows ahora declaradas.

- [ ] **Step 6: Commit**

```bash
git add apps/desktop/src-tauri/tauri.conf.json apps/desktop/src/presenter.*
git commit -m "feat(apps/desktop): F57.11 presenter window vanilla JS controller plus keyboard shortcuts"
```

---

### Task 12: MCP tools `meeting_*`

**Files:**
- Modify: `packages/jw-mcp/src/jw_mcp/server.py`
- Modify: `packages/jw-mcp/tests/test_protocol.py`

- [ ] **Step 1: Añadir 4 tools**

```python
@mcp.tool
async def meeting_discover_week(language: str, year: int, week: int,
                                  kind: str = "midweek") -> dict[str, Any]:
    """Descubre el programa semanal del workbook JW desde wol.jw.org."""
    try:
        from jw_meeting_media.models import MeetingKind
        from jw_meeting_media.program_client import MeetingProgramClient
        from jw_meeting_media.storage import MeetingStorage
        from pathlib import Path

        client = MeetingProgramClient()
        program = await client.fetch_week(
            language=language, year=year, week=week, kind=MeetingKind(kind),
        )
        await client.aclose()
        storage = MeetingStorage(
            Path("~/.jw-agent-toolkit/meetings/meetings.db").expanduser()
        )
        storage.save_program(program)
        return {
            "language": program.language,
            "kind": program.kind.value,
            "week_start": program.week_start.isoformat(),
            "section_count": len(program.sections),
            "item_count": sum(len(s.items) for s in program.sections),
            "source_url": program.source_url,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def meeting_download_media(language: str, year: int, week: int,
                                   kind: str = "midweek") -> dict[str, Any]:
    """Descarga toda la media del programa semanal al cache local."""
    try:
        from jw_meeting_media.downloader import Downloader
        from jw_meeting_media.media_resolver import MediaResolver
        from jw_meeting_media.models import MeetingKind
        from jw_meeting_media.storage import MeetingStorage
        from pathlib import Path

        cache_root = Path("~/.jw-agent-toolkit/meetings").expanduser()
        storage = MeetingStorage(cache_root / "meetings.db")
        program = storage.load_program(
            language=language, year=year, week=week, kind=MeetingKind(kind),
        )
        if program is None:
            return {"error": "program not found; call meeting_discover_week first"}

        resolver = MediaResolver()
        dl = Downloader(cache_root=cache_root / "media")
        results = {"succeeded": 0, "failed": 0, "items": []}
        for sec in program.sections:
            for item in sec.items:
                for ref in item.media_refs:
                    try:
                        resolved = await resolver.resolve(ref)
                        if not resolved.url:
                            results["failed"] += 1
                            continue
                        local = await dl.download(
                            resolved, language=language, year=year, week=week,
                        )
                        storage.mark_downloaded(resolved, local_path=local)
                        results["succeeded"] += 1
                        results["items"].append({"title": ref.title, "local_path": str(local)})
                    except Exception as exc:
                        results["failed"] += 1
                        results["items"].append({"title": ref.title, "error": str(exc)})
        await dl.aclose()
        return results
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def meeting_list_programs() -> dict[str, Any]:
    """Lista programas semanales ya descargados."""
    try:
        import sqlite3
        from contextlib import closing
        from pathlib import Path
        db = Path("~/.jw-agent-toolkit/meetings/meetings.db").expanduser()
        if not db.exists():
            return {"programs": []}
        with closing(sqlite3.connect(db)) as conn:
            rows = conn.execute(
                "SELECT language, year, week, kind, saved_at FROM programs "
                "ORDER BY year DESC, week DESC"
            ).fetchall()
        return {
            "programs": [
                {"language": r[0], "year": r[1], "week": r[2],
                 "kind": r[3], "saved_at": r[4]}
                for r in rows
            ]
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


@mcp.tool
async def meeting_open_presenter(language: str, year: int, week: int,
                                   kind: str = "midweek") -> dict[str, Any]:
    """Devuelve la URL de la ventana presenter Tauri con query params.
    El usuario (o cliente MCP) la abre desde la app desktop."""
    return {
        "presenter_url": f"presenter.html?language={language}&year={year}&week={week}&kind={kind}",
        "instructions": (
            "Abre apps/desktop y la ventana 'presenter' debe estar visible. "
            "Si no, ejecutar `yarn tauri dev` en apps/desktop."
        ),
    }
```

- [ ] **Step 2: Añadir a `_EXPECTED_TOOLS`**

```python
"meeting_discover_week",
"meeting_download_media",
"meeting_list_programs",
"meeting_open_presenter",
```

- [ ] **Step 3: Run, expect PASS**

```bash
uv run pytest packages/jw-mcp/tests/test_protocol.py -v
```

- [ ] **Step 4: Commit**

```bash
git add packages/jw-mcp/
git commit -m "feat(jw-mcp): F57.12 expose meeting_discover_week download_media list_programs open_presenter tools"
```

---

### Task 13: Análisis arquitectónico clean-room + docs

**Files:**
- Create: `docs/conceptos/programa-semanal-mwb-w.md`
- Create: `docs/guias/meeting-media.md`
- Modify: `docs/README.md`, `docs/ROADMAP.md`, master plan

- [ ] **Step 1: Análisis arquitectónico (clean-room observations)**

```markdown
# Programa semanal mwb/w — análisis arquitectónico

> Observaciones públicas sobre cómo wol.jw.org expone los programas
> semanales de reuniones congregacionales. Base del parser de F57.

## URLs canónicas

```
Workbook (Vida y Ministerio):
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}

Watchtower Study:
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}?wtsy=1
```

Donde `{resource}` y `{lp_tag}` vienen del registry de idiomas (F1).

## Estructura HTML observada

Inspeccionada via DevTools del browser sobre la página pública (no
desde código M³). Elementos clave:

```html
<article class="bodyTxt">
  <section class="section">
    <h2>Tesoros de la Palabra de Dios</h2>
    <div class="docSubContent">
      <h3>Tema del discurso</h3>
      <p>...texto con <a class="b" href="...">Génesis 1:1</a>...</p>
    </div>
    ...
  </section>
  <section class="section">
    <h2>Seamos mejores maestros</h2>
    ...
  </section>
  <section class="section">
    <h2>Nuestra vida cristiana</h2>
    ...
  </section>
</article>
```

## Refs identificables

- `<a class="b" href="/wol/b/...">Génesis 1:1</a>` — referencia bíblica
- `<a class="jsRef" href="/wol/d/...">` — link a documento JWPUB
- `<a href="/wol/mp/...">` — link a media item
- `<img src="...cms-imgp.jw-cdn.org...">` — ilustración inline

## Cambios de layout

WOL ha cambiado el HTML estructural ~1-2 veces por año en los últimos
ciclos. El parser F57 debe ser tolerante:
- Selectores múltiples (article.bodyTxt OR article)
- Fallback por `<h2>` si no hay `<section>`
- Items por `<div class="docSubContent">` o `<p class="su">`
- Skip nodos sin título

Capturar fixture HTML actual cuando se redescubra un cambio. Versionar
fixtures por fecha en `packages/jw-meeting-media/tests/fixtures/`.

## NO usado en F57 MVP

- Endpoints internos de jworg-search
- API de jw.org/apps/E que requiere JWT y no está documentada públicamente
- Páginas /apps/finder?lang= que no tienen sintaxis estable

Esos endpoints quedan para sprints futuros si MVP necesita features no
cubrables vía WOL parsing.
```

- [ ] **Step 2: Guía operativa**

```markdown
# Reunión-en-vivo: jw-meeting-media (Fase 57)

> Descubre, descarga y presenta media para reuniones congregacionales
> de Testigos de Jehová.

## Atribución clean-room

`jw-meeting-media` es **inspirado por** las features del proyecto
[M³ (sircharlo/meeting-media-manager)](https://github.com/sircharlo/meeting-media-manager)
pero **implementado clean-room desde cero**. NO contiene código portado
del upstream AGPL-3.0; las funcionalidades se reimplementaron observando
README y comportamiento público. Resultado: GPL-3.0-only compatible con
el resto del toolkit.

## Instalación

```bash
uv add 'jw-meeting-media[all]'
```

Para video thumbnails también necesitas `ffmpeg` en el PATH:
```bash
brew install ffmpeg   # macOS
sudo apt install ffmpeg   # Debian/Ubuntu
```

## Uso CLI

```bash
# Descubrir programa de la semana 23 de 2026 en español (midweek)
jw meeting discover --language es --year 2026 --week 23

# Descargar toda la media de esa semana
jw meeting download --language es --year 2026 --week 23

# Listar programas guardados
jw meeting list
```

## Uso REST (presenter)

Tras `jw mcp serve` (que levanta REST en 8765):

```bash
curl -X POST 'http://localhost:8765/presenter/sessions?language=es&year=2026&week=23&kind=midweek'
# → {"session_id": "abc-123"}

curl http://localhost:8765/presenter/sessions/abc-123/state
# → {"queue": [...], "cursor": 0, "playing": false, ...}

curl -X POST http://localhost:8765/presenter/sessions/abc-123/play
curl -X POST http://localhost:8765/presenter/sessions/abc-123/next
```

## Uso presenter Tauri

1. Abre la app desktop (`apps/desktop` build).
2. En la ventana principal navega a `Open Presenter`.
3. Se abre la ventana "presenter" controlando la sesión activa.
4. Atajos de teclado:
   - **Espacio**: play/pause
   - **→**: next
   - **←**: prev
   - **Escape**: stop

## Uso MCP

```
@jw-agent-toolkit meeting_discover_week
  language: es
  year: 2026
  week: 23

@jw-agent-toolkit meeting_download_media
  language: es
  year: 2026
  week: 23
```

## Limitaciones de F57 MVP

- ❌ Sin integración Zoom screen sharing
- ❌ Sin integración OBS Studio
- ❌ Sin sync cloud (Dropbox/OneDrive)
- ❌ Sin background music con auto-stop
- ❌ Sin multi-monitor automático
- ❌ Sin drag-and-drop UI

Esas features quedan para sprint posterior.

## Privacy y red

- Descarga de jw.org únicamente (User-Agent identifica al toolkit).
- Storage 100% local en `~/.jw-agent-toolkit/meetings/`.
- Sin telemetría externa, sin tracking.
- Cumple los términos de uso de jw.org (acceso público al contenido
  oficial — análogo a un navegador).
```

- [ ] **Step 3: docs/README.md, ROADMAP, master plan**

README + ROADMAP entries similares a F58. Marcar F57 ✅ en master plan.

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs(F57): meeting-media guide plus mwb w analysis plus ROADMAP entry"
```

---

## Tests resumen

```bash
uv run pytest packages/jw-meeting-media/tests/ \
              packages/jw-mcp/tests/test_protocol.py \
              packages/jw-mcp/tests/test_rest_presenter.py \
              -v --tb=short
```

Esperado: ~30-40 passed (depende de deps opcionales instalados).

Smoke total:
```bash
uv run pytest packages/ -v --tb=short
```

Tauri build:
```bash
cd apps/desktop && yarn install && yarn tauri build --debug
```

---

## Self-review checklist

- ✅ **Clean-room policy**: declarada explícitamente al inicio del plan. Cada task respeta la prohibición de leer src/ de M³.
- ✅ **Cobertura de MVP**: discover + download + presenter + CLI + MCP + REST + Tauri window.
- ✅ **No placeholders**: cada Step tiene código completo. Notas explícitas donde los selectores HTML pueden cambiar (WOL layout) — esperado.
- ✅ **Consistencia de tipos**: `MediaRef`/`MeetingItem`/`MeetingSection`/`MeetingProgram`/`PresenterSession` consistentes en models, storage, CLI, REST, MCP, Tauri JS.
- ✅ **Reuso**: PubMediaClient F2 ✓, WOLClient F1 ✓, jw_core.languages ✓, parse_reference ✓, Tauri F47 ✓.
- ⚠️ **Capturar fixture HTML real (Task 3 Step 1)**: depende de jw.org. Si está down o devuelve 404 para esa semana específica, ajustar a otra semana válida o regenerar tras unas horas.
- ⚠️ **WOL HTML layout volátil**: parser puede romperse si WOL cambia. Tests con fixture local protegen; mantener fixtures versionadas por fecha.
- ⚠️ **AGPL compliance manual review obligatoria**: antes de mergear, el autor debe confirmar manualmente que nadie abrió archivos src/ de M³ durante implementación. Hooks de git locales pueden ayudar (block git diff vs upstream).
