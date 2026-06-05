# Reunión-en-vivo: jw-meeting-media (Fase 57)

> Descubre, descarga y presenta media para reuniones congregacionales
> de Testigos de Jehová.

## Atribución clean-room

`jw-meeting-media` está **inspirado por** las features del proyecto
[M³ (sircharlo/meeting-media-manager)](https://github.com/sircharlo/meeting-media-manager),
pero **implementado clean-room desde cero**. NO contiene código
portado del upstream AGPL-3.0; las funcionalidades se reimplementaron
observando README, AGENTS.md, comportamiento público de la app
publicada y estructura HTML pública del WOL. Resultado: GPL-3.0-only
compatible con el resto del toolkit.

Si alguna duda surge en code-review sobre origen de una pieza, el
detalle de la política clean-room está documentado en el plan
`docs/superpowers/plans/2026-06-04-fase-57-jw-meeting-media-plan.md`,
sección "DISCLAIMER LEGAL".

## Instalación

```bash
uv add 'jw-meeting-media[all]'
```

Para video thumbnails también necesitas `ffmpeg` en el PATH:

```bash
brew install ffmpeg        # macOS
sudo apt install ffmpeg    # Debian/Ubuntu
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

Tras `jw mcp serve` (que levanta REST en `localhost:8765`):

```bash
curl -X POST 'http://localhost:8765/presenter/sessions?language=es&year=2026&week=23&kind=midweek'
# {"session_id": "abc-123"}

curl http://localhost:8765/presenter/sessions/abc-123/state
# {"queue": [...], "cursor": 0, "playing": false, ...}

curl -X POST http://localhost:8765/presenter/sessions/abc-123/play
curl -X POST http://localhost:8765/presenter/sessions/abc-123/next
```

## Uso presenter Tauri

1. Abre la app desktop (`apps/desktop` build).
2. Lanza la ventana `presenter` (declarada en `tauri.conf.json`).
3. La URL acepta query params: `presenter.html?language=es&year=2026&week=23&kind=midweek`.
4. Atajos de teclado:
   - **Espacio**: play/pause
   - **Flecha derecha**: next
   - **Flecha izquierda**: prev
   - **Escape**: stop

## Uso MCP

Cuatro tools expuestas a clientes MCP:

```
@jw-agent-toolkit meeting_discover_week
  language: es
  year: 2026
  week: 23

@jw-agent-toolkit meeting_download_media
  language: es
  year: 2026
  week: 23

@jw-agent-toolkit meeting_list_programs

@jw-agent-toolkit meeting_open_presenter
  language: es
  year: 2026
  week: 23
```

## Limitaciones de F57 MVP

- Sin integración Zoom (screen share).
- Sin integración OBS Studio (scene switching).
- Sin sync cloud (Dropbox/OneDrive).
- Sin background music con auto-stop.
- Sin multi-monitor automático (Tauri 2.x: feature manual).
- Sin drag-and-drop UI para añadir media extra.
- Sin catálogo Memorial / eventos especiales.

Esas features quedan para sprints posteriores.

## Privacy y red

- Descarga de jw.org únicamente (User-Agent identifica al toolkit).
- Storage 100% local en `~/.jw-agent-toolkit/meetings/`.
- Sin telemetría externa, sin tracking.
- Cumple los términos de uso de jw.org (acceso público al contenido
  oficial — análogo a un navegador).

## Arquitectura

Diagrama de dependencias:

```
MeetingProgramClient ──▶ jw_core.languages / parsers.reference
        │
        ▼
   MeetingProgram (Pydantic) ──▶ MeetingStorage (sqlite)
        │
        ▼
   MediaResolver ──▶ jw_core.clients.PubMediaClient (F2)
        │
        ▼
   Downloader (httpx + sha256 cache)
        │
        ▼
   PresenterManager (in-memory FSM) ──▶ REST `/presenter/*`
                                            │
                                            ▼
                                  Tauri presenter window (vanilla JS)
```

Ver también `docs/conceptos/programa-semanal-mwb-w.md` para los
detalles del HTML del WOL que el parser navega.
