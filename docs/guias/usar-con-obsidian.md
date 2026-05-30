---
title: Usar el toolkit con Obsidian (second brain)
audiencia: usuarios finales
fase: 20
---

# Guía: usar el toolkit con Obsidian

> Cómo montar el flujo de "second brain" extremo a extremo: vault Obsidian + jw-agent-toolkit + JW Library + agente LLM. Conceptos en [`conceptos/integracion-obsidian.md`](../conceptos/integracion-obsidian.md). Referencia API en [`referencia/integraciones.md`](../referencia/integraciones.md).

## Lo que vas a tener al final

- Cualquier referencia bíblica que escribas en una nota de Obsidian se convierte automáticamente (a comando o al guardar) en `[Juan 3:16](jwlibrary:///finder?bible=43003016&wtlocale=S)`.
- Cualquier cita "Lee Mateo 24:14" en tus notas se vuelve un enlace clickable que abre la app JW Library en el verso exacto.
- Tus notas de JW Library (todas las que has guardado en la app) aparecen como archivos `.md` en `<vault>/JW Library/`.
- Un agente LLM (Claude Desktop, Claude Code) ve **todo simultáneamente**: tus notas Obsidian + tus notas JW Library + el corpus público de jw.org + las publicaciones JWPUB que tengas descargadas.

## Pre-requisitos

1. **jw-agent-toolkit instalado**: `uv sync` desde la raíz del repo, todos los paquetes editables.
2. **Obsidian** instalado en el mismo equipo que el toolkit.
3. **(Opcional) JW Library app** instalada — para que los `jwlibrary://` clickables abran el verso. En macOS desde Mac App Store; en Windows desde Microsoft Store.
4. **Node + pnpm** para compilar el plugin (`brew install node pnpm` en macOS).

## Paso 1: arrancar la REST API del toolkit

```bash
cd /path/to/jw-agent-toolkit
uv pip install fastapi uvicorn
uv run uvicorn jw_mcp.rest_api:app --host 127.0.0.1 --port 8765 --reload
```

Confirma con:

```bash
curl -s http://127.0.0.1:8765/healthz
# {"status":"ok"}
```

Mantén esa terminal abierta. (En la siguiente fase de infra esto se mete en `launchd`/`systemd`/`Task Scheduler`.)

## Paso 2: compilar e instalar el plugin Obsidian

```bash
cd apps/obsidian-jw-bridge
pnpm install
pnpm run build           # genera main.js
```

Copia los 3 archivos (`main.js`, `manifest.json`, opcional `styles.css`) a:

```
<TU_VAULT>/.obsidian/plugins/jw-agent-toolkit-bridge/
```

Crea el directorio si no existe. Luego en Obsidian:

1. **Settings → Community plugins → Browse** (si nunca has instalado uno) → cierra el modal.
2. **Settings → Community plugins** → toggle **Installed → JW Agent Toolkit Bridge** → on.
3. **Settings → JW Agent Toolkit Bridge** → confirma que **Toolkit REST API URL** apunta a `http://localhost:8765`.

Ejecuta el comando **JW Bridge: Check bridge health** desde la paleta (`Cmd-P` / `Ctrl-P`) → debería decir "Bridge OK ✓".

## Paso 3: linkify tu primera nota

Abre una nota que tenga referencias bíblicas en texto plano:

```markdown
# Estudio del jueves
Mateo 24:14 nos enseña sobre la obra de predicar.
Juan 3:16 muestra el amor de Dios.
Romanos 8:28-30 — los propósitos divinos.
```

Comando paleta: **JW Bridge: Linkify current note**. Después:

```markdown
# Estudio del jueves
[Mat. 24:14](jwlibrary:///finder?bible=40024014&wtlocale=S) nos enseña sobre la obra de predicar.
[Juan 3:16](jwlibrary:///finder?bible=43003016&wtlocale=S) muestra el amor de Dios.
[Rom. 8:28-30](jwlibrary:///finder?bible=45008028-45008030&wtlocale=S) — los propósitos divinos.
```

Click en cualquier enlace → JW Library se abre en el verso exacto.

Variantes: **Linkify selection** trabaja solo en lo seleccionado; **Linkify entire vault** procesa cada `.md` del vault (toma 1-2 s por 100 archivos).

## Paso 4: insertar un verso con quote callout

Posiciona el cursor donde quieras pegar el verso → **JW Bridge: Insert Bible verse at cursor…** → escribe `Juan 3:16` → Enter. Resultado:

```markdown
> [!quote] [Juan 3:16](jwlibrary:///finder?bible=43003016&wtlocale=S)
> Porque tanto amó Dios al mundo que dio a su Hijo unigénito, para que todo el que ejerce fe en él no sea destruido, sino que tenga vida eterna.
```

Cambia el template en **Settings → Verse template** entre `link`, `blockquote`, `callout`, `callout-collapsed`, `plain`.

## Paso 5: importar tus notas de JW Library al vault

1. En la app JW Library: **Ajustes → Copia de seguridad → Guardar copia de seguridad**.
2. Mueve el `UserDataBackup_...jwlibrary` a una ruta accesible.
3. En Obsidian: **JW Bridge: Export JW Library backup into vault…** → pega el path completo del `.jwlibrary` → Enter.

Resultado en tu vault:

```
<vault>/JW Library/
├── bible/
│   ├── 01/chapter-001/01001-Inicio.md
│   ├── 40/chapter-024/40024-Predicacion.md
│   └── 43/chapter-003/43003-Amor-de-Dios.md
└── publications/
    └── w24/2024-04-articulo-estudio.md
```

Cada archivo lleva frontmatter completo:

```markdown
---
title: "Amor de Dios"
note_id: 10
guid: "g-1"
source_backup: "UserDataBackup_2024-11-15.jwlibrary"
book: 43
chapter: 3
created: "2024-11-10"
last_modified: "2024-11-15"
tags:
  - Favorito
  - Sermón
---

# Amor de Dios

> [!quote] [Juan 3](jwlibrary:///finder?bible=43003001&wtlocale=S)

Juan 3:16 muestra la profundidad del amor divino…
```

Estas notas son ahora ciudadanos de primera clase en Obsidian: Dataview puede consultarlas, backlinks funcionan, búsqueda full-text las cubre.

## Paso 6: convertir notas viejas con `jwpub://`

Si tienes notas migradas de Watchtower Library o Logos que aún contienen `jwpub://b/40:24:14-40:24:14`, ejecuta **JW Bridge: Convert jwpub:// links in current note**. Los links se actualizan en su lugar:

```markdown
[Mat 24:14](jwpub://b/40:24:14-40:24:14)
              ↓
[Mat 24:14](jwlibrary:///finder?bible=40024014)
```

## Paso 7: indexar el vault al RAG (para el agente LLM)

**JW Bridge: Index this vault into the toolkit RAG store**. Notification:

```
Indexed: 142 new, 0 updated, 0 deleted, 0 unchanged.
```

A partir de aquí, cualquier llamada a `semantic_search` desde el agente LLM (vía MCP o REST) verá tus notas como contexto. Re-ejecutar el comando es incremental: solo procesa archivos modificados (mtime + content_hash).

Filtros disponibles vía REST/MCP: `require_tag="ministerio"` para indexar solo notas con ese tag de frontmatter.

## Paso 8: configurar Claude Desktop para que vea todo

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jw-agent-toolkit": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/elias/Documents/Trabajo/jw-agent-toolkit",
        "run",
        "jw-mcp"
      ]
    }
  }
}
```

Reinicia Claude Desktop. Pregunta:

> "Busca en mis notas y en jw.org todo lo que tengo sobre el amor de Dios en Juan, y devuélveme un resumen con citas linkeadas a JW Library."

El agente puede:

1. Llamar `semantic_search` → recibe chunks de tus `vault_note`, `user_note` (backup JW), `bible_chapter`, `jwpub_document`.
2. Sintetizar el resumen.
3. Para cada referencia bíblica que cite, llamar `linkify_markdown_text` o construir directamente con `build_bible_url`.
4. Devolver markdown listo para pegar en una nueva nota Obsidian.

## Paso 9 (opcional): auto-linkify al guardar

**Settings → JW Agent Toolkit Bridge → Auto-linkify on save → ON**. Cada vez que modificas un `.md`, el plugin re-ejecuta `linkify` en background con debounce 800 ms. Útil mientras escribes mucho.

## Comandos de referencia

| Comando | Atajo sugerido | Acción |
|---|---|---|
| Linkify selection | — | Convierte refs en el texto seleccionado |
| Linkify current note | `Cmd-Shift-L` | Convierte la nota activa |
| Linkify entire vault | — | Procesa todos los `.md` |
| Convert jwpub:// links in current note | — | Actualiza enlaces legacy |
| Insert Bible verse at cursor… | `Cmd-Shift-V` | Modal → fetch + insert |
| Export JW Library backup into vault… | — | Modal → backup → `.md` |
| Index this vault into the toolkit RAG store | — | Sync incremental al RAG |
| Check bridge health | — | Ping a `/healthz` |

(Los atajos los configuras tú en **Settings → Hotkeys**.)

## Solución de problemas

| Síntoma | Probable causa | Cómo arreglar |
|---|---|---|
| "Bridge unreachable" | REST no está corriendo | `uvicorn jw_mcp.rest_api:app --port 8765` |
| Linkify no convierte una ref | Idioma incorrecto en settings | Verifica **Default language (ISO)** |
| El enlace abre la app pero no navega al verso | App JW Library no actualizada / no instalada | Reinstala desde Microsoft/Mac App Store |
| Export backup crea archivos sin contenido | El `.jwlibrary` está corrupto o vacío | Re-exporta desde la app |
| Auto-linkify duplica enlaces | `[texto](url)` ya estaba con jwlibrary diferente | Es by design — el plugin no toca refs ya enlazadas |
| Index vault ignora notas | Frontmatter `tags` no coincide con `require_tag` | Quita `require_tag` o ajusta los tags |

## Rendimiento esperado

- Linkify de 1 nota promedio (200 refs): ~50 ms.
- Linkify del vault (1000 notas, 5 refs c/u): ~5 s.
- Index incremental del vault con cambios: ~200 ms por nota nueva.
- Export de backup con 500 notas: ~2 s.
- Health check: ~10 ms.

## Lo que aún no está y por qué

- **Sync inverso de vault → backup `.jwlibrary`**: técnicamente factible (escribir un SQLite + ZIP) pero invalidaría el sync con cuenta JW. Decisión consciente: el flujo es one-way (`backup → vault`), nunca a la inversa.
- **Auto-suggest in-editor**: el plugin original sugiere links mientras escribes con `/b`. Lo recreamos como modal por ahora; el suggester completo requiere extender el sistema de autocompletado de Obsidian, no trivial.
- **Templates custom**: solo los 5 built-in. Para añadir el tuyo, edita `markdown.render_verse_block` y añade el case.

## Próximos pasos

- Si usas iCloud/Drive/Dropbox para sincronizar tu vault entre devices, el plugin compilado se sincroniza con él. Solo necesitas el toolkit corriendo localmente en cada device.
- Si quieres correr el toolkit en otro servidor: cambia **Toolkit REST API URL** apuntando a su IP. CORS está habilitado por defecto.
- Si quieres integrar con bots Telegram/WhatsApp/Discord: ya existen los adapters en `packages/jw-mcp/src/jw_mcp/bots/` que reusan los mismos endpoints REST.
