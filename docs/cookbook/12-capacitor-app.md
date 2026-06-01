# App móvil con Capacitor + jw-core JS

> **Tiempo estimado**: 30 minutos
> **Requisitos**: Fase 47 (`jw-core-js-minimal`) — pendiente.
> **Slug URL**: `/cookbook/12-capacitor-app`

## ¿Qué construyes?

Una app móvil iOS/Android con Capacitor que resuelve referencias bíblicas client-side usando `@jw-agent-toolkit/core` (port TS mínimo del jw-core). El backend Python opcional sigue siendo `jw-mcp` corriendo en el servidor.

## Código (copy-pasteable)

```python
# test skip-until-fase=47
# Esta receta requiere Fase 47 (port TS de jw-core). Se actualizará al cerrar F47.
import json

# When F47 ships, this block will validate a package.json declaring
# @jw-agent-toolkit/core as a dependency.
fake_pkg = {
    "name": "my-jw-mobile",
    "dependencies": {
        "@capacitor/core": "^6.0.0",
        "@jw-agent-toolkit/core": "^0.1.0",
    },
}
assert "@jw-agent-toolkit/core" in fake_pkg["dependencies"]
```

## Por qué funciona

F47 portea los 3 módulos críticos a TypeScript:

1. `parse_reference` — corazón del parser bíblico.
2. `WOLClient.get_bible_chapter` — fetcher de la NWT.
3. `parsers.article` — HTML → Article structured.

Eso cubre el 80% de los casos JS/móvil sin necesidad de embedded Python.

## Variaciones

- **Offline-first** con SQLite (capacitor-sqlite) para Biblia cacheada.
- **Background sync** con `jw-mcp` REST cuando hay red.
- **Voice over** con TTS nativo (no necesita F34 audio-premium).

## Próximo paso

Recetas terminadas. Para ideas avanzadas, ver [docs/VISION.md](../VISION.md) y los issues abiertos del repo.
