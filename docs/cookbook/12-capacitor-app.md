# App móvil con Capacitor + jw-core JS

> **Tiempo estimado**: 30 minutos
> **Requisitos**: Fase 47 MVP (`@jw-agent-toolkit/core`).
> **Slug URL**: `/cookbook/12-capacitor-app`

## ¿Qué construyes?

Una app móvil iOS/Android con Capacitor que resuelve referencias bíblicas
client-side usando `@jw-agent-toolkit/core` (port TS mínimo del `jw-core`).
El backend Python opcional (`jw-mcp`) sigue siendo el host remoto cuando
necesitas RAG, fine-tuning u otras tareas que viven solo en Python.

## Código (copy-pasteable)

```python
# test
# Esta receta verifica que el paquete @jw-agent-toolkit/core (Fase 47 MVP)
# está listo para ser declarado como dependencia de un proyecto Capacitor.
# La validación corre offline contra los archivos del monorepo: lee el
# package.json del paquete, confirma su nombre, lee el fixture golden
# compartido para mostrar qué referencias quedan cubiertas, y arma un
# package.json de ejemplo que un consumer mobile usaría.
import json
from pathlib import Path

monorepo = Path(__file__).resolve().parent.parent.parent
pkg_meta = json.loads(
    (monorepo / "packages" / "jw-core-js" / "package.json").read_text(encoding="utf-8")
)
assert pkg_meta["name"] == "@jw-agent-toolkit/core"
assert pkg_meta["main"].startswith("./dist/")
assert pkg_meta["types"].endswith(".d.ts")

# The shared golden fixture is the parity contract — both the Python parser
# and the TS port pass every row. A Capacitor app can rely on the same
# parser to resolve user input client-side.
golden = json.loads(
    (monorepo / "shared" / "data" / "bible_references_golden.json").read_text(
        encoding="utf-8"
    )
)
sample = [c["input"] for c in golden["cases"][:5]]
assert "Juan 3:16" in sample

# A mobile project would declare the dep like this — version reflects the
# MVP cut shipped today (0.1.0-mvp).
mobile_pkg = {
    "name": "my-jw-mobile",
    "dependencies": {
        "@capacitor/core": "^6.0.0",
        "@capacitor/ios": "^6.0.0",
        "@capacitor/android": "^6.0.0",
        "@jw-agent-toolkit/core": pkg_meta["version"],
    },
}
assert "@jw-agent-toolkit/core" in mobile_pkg["dependencies"]
print(
    "MVP version:",
    pkg_meta["version"],
    "covers",
    len(golden["cases"]),
    "golden refs",
)
```

## Por qué funciona

La Fase 47 MVP portea el subset crítico de `jw-core` a TypeScript:

1. **`parseReference` / `parseAllReferences`** — corazón del parser
   bíblico, con el mismo regex master longest-first que la versión Python.
2. **`BibleRef.wolUrl(lang, pub?)`** — construye la URL canónica de
   wol.jw.org para cualquier referencia, en cualquiera de las tres lenguas
   soportadas hoy (en/es/pt).
3. **Tabla `BOOKS`** — los 66 libros con sus nombres y abreviaturas.
4. **`toCanonical` / `explain`** — mapeo de Fase 46 entre tradiciones de
   numeración (nwt ↔ masoretic ↔ lxx ↔ vulgate).

Eso cubre la mayor parte de los casos JS/móvil sin embebido de Python.
Cuando el usuario necesita RAG sobre su corpus, fine-tuning, o el resto
del toolkit, una llamada HTTPS al `jw-mcp` remoto sigue siendo la salida.

## Variaciones

- **Offline-first** con SQLite (`capacitor-sqlite`) para la Biblia cacheada
  por capítulo. `BibleRef.wolUrl` da la clave canónica para la cache.
- **Background sync** con `jw-mcp` REST cuando hay red — el endpoint
  `verse_markdown` ya está expuesto y la app móvil lo consume igual que la
  extensión WOL.
- **Voice over** con TTS nativo de la plataforma (no necesita F34
  audio-premium).
- **Deep links**: un `jwlibrary://` o un `https://wol.jw.org/...`
  generado por `BibleRef.wolUrl` abre la NWT en la app oficial de JW
  Library si está instalada.

## Próximo paso

Recetas terminadas. Para ideas avanzadas, ver
[docs/VISION.md](../VISION.md) y los issues abiertos del repo. Si quieres
empujar el port TS más allá del MVP (parsers HTML, JWPUB con Web Crypto,
HTTP clients), consulta [la guía de Fase 47](../guias/jw-core-js.md) con
la tabla por bucket de lo pendiente.
