# Guía: setup en macOS

> Si clonas el repo bajo `~/Documents` (o `~/Desktop`) en macOS, el venv estándar `.venv/` falla silenciosamente al importar paquetes editables. Aquí está el porqué y la receta de bootstrap correcta.

## Síntoma

Tras un `uv sync --all-packages` aparentemente exitoso:

```bash
$ uv pip show jw-finetune
Name: jw-finetune
Version: 0.1.0
Editable project location: /Users/<tú>/Documents/.../packages/jw-finetune

$ uv run jw-finetune --help
ModuleNotFoundError: No module named 'jw_finetune'
```

Lo mismo para `jw-core`, `jw-rag`, `jw-mcp`, cualquier paquete del workspace.

## Causa raíz

macOS aplica automáticamente el flag de filesystem `UF_HIDDEN` a **dot-directorios** (`.algo/`) creados en ubicaciones indexadas por Spotlight como `~/Documents` o `~/Desktop`. Como `.venv/` empieza por `.` y vive bajo `~/Documents`, hereda el flag — y todos los archivos creados dentro también, incluidos los `_editable_impl_*.pth` que uv/hatchling generan para los paquetes editables.

CPython 3.8+ filtra deliberadamente los `.pth` marcados como hidden ([cpython#113659](https://github.com/python/cpython/issues/113659)). El path al `src/` del paquete editable nunca entra a `sys.path` → `ModuleNotFoundError`.

No es un bug de uv ni de hatchling. Issue de tracking upstream: [astral-sh/uv#16977](https://github.com/astral-sh/uv/issues/16977).

## Solución

Usar `venv/` (sin dot) como almacenamiento físico y un symlink `.venv → venv` para que uv siga encontrándolo en su path por defecto:

```bash
rm -rf .venv venv
uv venv venv --python 3.13
ln -s venv .venv
uv sync --all-packages
```

`.gitignore` del repo ya cubre tanto `venv/` como `.venv/`.

A partir de aquí `uv run jw-mcp`, `uv run jw verse`, `uv run jw-finetune studio` etc. funcionan con normalidad — y, sobre todo, **siguen funcionando** después de cualquier futuro `uv sync`, sin tener que volver a tocar nada.

## Por qué funciona

macOS aplica `UF_HIDDEN` a archivos nuevos heredando del directorio padre. Si el padre es `venv/` (sin dot → sin flag), los archivos hijos se crean sin flag. CPython los lee normalmente.

El symlink `.venv → venv` permite que uv siga usando su path por defecto. uv resuelve symlinks correctamente y opera sobre `venv/`; los `.pth` se escriben físicamente en `venv/lib/python3.13/site-packages/` y permanecen visibles.

## Verificación rápida

```bash
# Estos archivos deben mostrar flag "-" (no "hidden") en la columna O:
ls -lO venv/lib/python3.13/site-packages/_editable_impl_jw_*.pth

# Y este import debe imprimir OK + ruta a packages/jw-finetune/src/...
.venv/bin/python -c "import jw_finetune; print('OK', jw_finetune.__file__)"
```

## ¿No estás en macOS?

Ignora esta guía. El comportamiento es exclusivo de macOS sobre paths indexados por Spotlight (`~/Documents`, `~/Desktop`). En Linux, Windows, o en macOS fuera de esas carpetas, `.venv/` funciona directamente.

## Workarounds alternativos

Si por alguna razón no puedes usar el symlink:

- **Mover el repo fuera de `~/Documents`** (p. ej. `~/dev/jw-agent-toolkit/`) — también escapa de la regla.
- **`chflags nohidden .venv/lib/python3.13/site-packages/*.pth`** tras cada `uv sync`/`uv run` — parche manual, hay que rehacerlo constantemente porque macOS vuelve a aplicar el flag a cualquier archivo nuevo bajo un dot-dir. No recomendado.
