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

### Drag-and-drop en el presenter (F57.14)

La sidebar izquierda muestra la cola completa con números. Tres
gestos están soportados:

- **Click** sobre un item: salta el cursor a ese punto del programa
  (POST `/presenter/sessions/{sid}/jump?index=N`).
- **Arrastrar** un item de la cola sobre otro: reordena el
  programa (POST `/presenter/sessions/{sid}/reorder` con
  `{from_index, to_index}`). El cursor se ajusta automáticamente
  para no perder el ítem activo.
- **Drop** desde el explorador del SO al recuadro punteado de la
  parte inferior: añade el archivo (imagen, video o audio) al final
  de la cola como `MeetingItem` ad-hoc (POST
  `/presenter/sessions/{sid}/add`). En Tauri 2 se usa el path
  absoluto del FS expuesto por `file.path`.

### Monitor externo (F57.15)

En la Sala del Reino, el laptop conectado al proyector tiene dos
salidas: la pantalla del laptop (operador) y el proyector externo
(audiencia). Clic en **🖥 Monitor** del sidebar para abrir el
selector y mover el presenter al proyector.

- El menú lista todos los monitores detectados con su resolución
  y marca el primario.
- Marca/desmarca **Fullscreen** antes de elegir destino (por
  defecto activado).
- Clic sobre un monitor: la ventana presenter salta a ese monitor,
  recupera focus y entra a fullscreen si la opción está marcada.
- Si solo hay 1 monitor (o no se detectan), el menú muestra el
  estado pero no rompe la app: simplemente no hay destino al que
  mover.

Implementación: Tauri 2 expone dos commands custom
(`list_monitors`, `move_presenter_to_monitor`) declarados en
`apps/desktop/src-tauri/src/main.rs` e invocados desde
`presenter.js` vía `window.__TAURI__.core.invoke`. Fuera de Tauri
(p.ej. `vite dev` preview standalone) el selector se oculta
automáticamente.

## Multi-congregación (F57.16)

Un mismo install puede gestionar varias congregaciones simultáneamente
(p.ej. dos asignaciones en idiomas distintos), manteniendo programas y
descargas aisladas por congregación.

### Registry TOML

Las congregaciones se registran en
`~/.jw-agent-toolkit/meetings/congregations.toml`:

```toml
[congregations.norte]
language = "es"
weekend_kind = "weekend"
midweek_kind = "midweek"
notes = "Sala del Reino Norte"

[congregations.sur]
language = "en"
notes = "Spanish-English bilingual"
```

Cada congregación tiene su propio cache dedicado en
`~/.jw-agent-toolkit/meetings/<name>/{meetings.db,media/...}`. La
congregación implícita `default` mantiene el layout legacy
(`~/.jw-agent-toolkit/meetings/` directo) para compatibilidad con
installs pre-F57.16.

### CLI `jw meeting congregation`

```bash
# Registrar
jw meeting congregation add norte --language es --notes "Sala Norte"
jw meeting congregation add sur --language en

# Listar
jw meeting congregation list
#   norte [es] — Sala Norte
#   sur [en]

# Resolver la congregación por defecto (depende del estado del registry)
jw meeting congregation default
# multiple congregations registered (['norte', 'sur']); specify --congregation NAME

# Eliminar
jw meeting congregation remove sur
```

### Flag `--congregation` en discover/download/list

Todos los comandos del programa aceptan `--congregation NAME` (o `-c`):

```bash
# Descarga aislada por congregación
jw meeting discover --congregation norte --year 2026 --week 23
jw meeting download --congregation norte --year 2026 --week 23

# Listado por congregación
jw meeting list --congregation norte
```

Reglas de resolución:

- Si solo hay 1 congregación registrada, se usa automáticamente.
- Si hay varias y no se especifica `--congregation`, el comando falla
  con error explícito.
- Si NO hay registry, se usa la congregación implícita `default` y se
  acepta `--language` directamente (compat legacy).
- El `language` de cada congregación actúa como default cuando se omite
  `--language` en `discover`/`download`.

### MCP tools nuevos

```
@jw-agent-toolkit meeting_list_congregations
@jw-agent-toolkit meeting_add_congregation
  name: norte
  language: es
  notes: Sala Norte
```

Las tools existentes (`meeting_discover_week`, `meeting_download_media`,
`meeting_list_programs`) ahora aceptan un parámetro opcional
`congregation: str`. El payload de respuesta incluye un campo
`congregation` con el nombre resuelto.

## Uso MCP

Seis tools expuestas a clientes MCP:

```
@jw-agent-toolkit meeting_discover_week
  language: es
  year: 2026
  week: 23
  congregation: norte    # opcional (F57.16)

@jw-agent-toolkit meeting_download_media
  language: es
  year: 2026
  week: 23
  congregation: norte    # opcional (F57.16)

@jw-agent-toolkit meeting_list_programs
  congregation: norte    # opcional (F57.16)

@jw-agent-toolkit meeting_open_presenter
  language: es
  year: 2026
  week: 23

@jw-agent-toolkit meeting_list_congregations          # F57.16

@jw-agent-toolkit meeting_add_congregation            # F57.16
  name: norte
  language: es
```

## Limitaciones de F57 MVP

- Sin integración Zoom (screen share).
- Sin integración OBS Studio (scene switching).
- Sin sync cloud (Dropbox/OneDrive).
- Sin background music con auto-stop.
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
