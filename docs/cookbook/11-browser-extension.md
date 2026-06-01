# Extensión de navegador para wol.jw.org

> **Tiempo estimado**: 15 minutos
> **Requisitos**: Node 22+ + pnpm. Backend local corriendo (REST API).
> **Slug URL**: `/cookbook/11-browser-extension`

## ¿Qué construyes?

Una extensión Chrome/Edge/Firefox que añade botones inline a cada versículo en wol.jw.org: **📖 Explicar**, **🔗 Refs cruzadas**, **📝 Obsidian**. Toda la lógica corre 100% local — la extensión llama a `localhost:8765`, nunca a un servidor externo.

## Código (copy-pasteable)

```python
# test
# Verify the manifest.json shipped with apps/wol-browser-extension is v3.
import json
from pathlib import Path

# Locate the repo root from this recipe path.
repo = Path(__file__).resolve()
for _ in range(8):
    if (repo / ".git").exists():
        break
    repo = repo.parent

manifest = repo / "apps" / "wol-browser-extension" / "manifest.json"
assert manifest.exists()
data = json.loads(manifest.read_text(encoding="utf-8"))
assert data["manifest_version"] == 3
assert "host_permissions" in data
# Critical: the only allowed network target is the local API.
for perm in data["host_permissions"]:
    assert "localhost" in perm or "127.0.0.1" in perm, perm
```

## Por qué funciona

La extensión (Fase 48) ya está construida y vive en `apps/wol-browser-extension/`. Esta receta solo verifica el manifest. Para correrla:

```bash
cd apps/wol-browser-extension
pnpm install && pnpm build
# Cargar dist/ en chrome://extensions/ → "Load unpacked"
```

Y arranca el backend:

```bash
jw mcp serve  # default :8765
```

## Variaciones

- Modo Firefox: la misma extensión carga sin cambios.
- Customizar qué selectores se enriquecen: editar `src/verse_detector.ts`.
- Añadir botón nuevo: extender `src/button_injector.ts` + endpoint en `jw-mcp`.

## Próximo paso

→ [12 — Capacitor mobile app](12-capacitor-app.md)
