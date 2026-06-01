# Plugin SDK — Security

## Modelo de confianza

**Realidad cruda**: un plugin corre en el proceso del toolkit con todos los privilegios. Puede leer secretos del entorno, escribir archivos, hacer red. **Esto no se mitiga** sin sandboxing real (subprocesos/wasmtime/seccomp), que excede el alcance de Fase 41.

**Postura**: el modelo de confianza es **el mismo que `pip install`**. Cualquier package Python instalable puede hacer cualquier cosa. Los plugins no son la excepción — solo son más visibles porque se descubren automáticamente.

> Instalar un plugin = ejecutar código arbitrario. Verifica la fuente.

## Mitigaciones disponibles

### 1. `JW_PLUGINS_DISABLED=1`

Desactiva discovery completo. Útil para entornos auditados / CI público que no quieren depender de plugins de terceros.

```bash
JW_PLUGINS_DISABLED=1 uv run jw plugins list  # devuelve groups vacíos
```

### 2. `JW_PLUGINS_ALLOW_LIST`

Solo carga estos nombres. Default permisivo, pero si está seteado se vuelve estricto.

```bash
JW_PLUGINS_ALLOW_LIST="trusted_a,trusted_b" uv run jw
```

### 3. `JW_PLUGINS_DENY_LIST` / `jw plugins disable`

Bloquea nombres específicos (post-incident response). `jw plugins disable` lo persiste en `~/.jw-agent-toolkit/plugins.toml`.

### 4. Trazabilidad

`verify_plugin` emite reporte con `dist_name`, `dist_version`. Auditable. El CLI lo expone en `jw plugins verify <name>`.

## Lo que NO ofrecemos

- Bloqueo de red por plugin.
- Bloqueo de FS por plugin.
- Sandboxing de imports.

Si necesitas esas garantías, no instales plugins — usa `JW_PLUGINS_DISABLED=1` y consume el toolkit puro.

## Auto-instalación

**El toolkit NUNCA corre `pip install` por su cuenta.** Los plugins llegan vía `uv add` explícito del usuario. No hay marketplace integrado, no hay descarga automática.
