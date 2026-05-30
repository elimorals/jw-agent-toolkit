# Guía — Conductor de estudio bíblico personal

> Fase 24. Acompaña la preparación de cada lección del libro de estudio
> actual («Disfruta de la vida para siempre», `lff`) y registra el ciclo
> de vida del estudiante: lecciones, metas y notas privadas cifradas.

## Qué hace

- `jw study lesson <pub> <ch> --lang es` — genera preguntas de anticipación
  por párrafo, lista versículos clave y temas del Índice Temático.
- `jw study log <student> <pub> <ch> [--status …] [--note …] [--goal …]`
  — registra progreso. La nota se cifra al guardar.
- `jw study progress <student>` — vista de ciclo de vida.
- `jw study lessons <pub>` — inventario del libro.
- `jw study goals` — taxonomía controlada de metas.
- `jw study directory set <alias> <nombre>` — alias→nombre opt-in.

## Qué NO hace

- No sustituye al conductor humano ni a los ancianos.
- No envía nada a la nube. Todo local, en `~/.jw-agent-toolkit/`.
- No mantiene un directorio de hermanos: `student_id` es un alias.
- No genera texto con LLM. Las preguntas vienen de plantillas
  determinísticas en `jw_core.data.study_prompts`.

## Privacidad

1. **Passphrase**: la primera vez se le pide. Si la pierde, los datos
   guardados **no son recuperables**. Por diseño.
2. **Salt persistente** en `~/.jw-agent-toolkit/study_progress.salt`.
3. **Cifrado**: Fernet con clave derivada por PBKDF2-HMAC-SHA256.
4. **Detector de crisis**: si una nota contiene palabras como
   «suicidio», «abuso», el CLI imprime una advertencia recomendando
   contactar a los ancianos o a un profesional. La nota igualmente se
   guarda — no bloquea.
5. **MCP**: las tools de progreso exigen `JW_STUDY_PASSPHRASE` en el
   entorno. Sin variable, devuelven `{"error": "..."}` y no tocan el
   disco.

## Flujo recomendado

```bash
# 1. Preparar la lección 1 (idioma español)
jw study lesson lff 1 --lang es

# 2. Registrar avance del estudiante "amelia2024"
export JW_STUDY_PASSPHRASE='...'  # solo en esta sesión
jw study log amelia2024 lff 1 --status completed \
    --note "Receptiva al tema del nombre de Dios" \
    --goal attend_meetings

# 3. Ver ciclo de vida
jw study progress amelia2024
```

## Configuración

| Variable | Default | Para qué |
|---|---|---|
| `JW_STUDY_DB`        | `~/.jw-agent-toolkit/study_progress.db`   | Ruta del SQLite. |
| `JW_STUDY_SALT`      | `~/.jw-agent-toolkit/study_progress.salt` | Salt persistente. |
| `JW_STUDY_PASSPHRASE`| (sin default)                              | Required para `log`. |
| `JW_STUDY_DIRECTORY` | `~/.jw-agent-toolkit/study_directory.json` | Alias→nombre opt-in. |

## Recuperación ante errores

- Passphrase olvidada → no hay recuperación. Borre `study_progress.db`
  y `study_progress.salt`, empiece de nuevo. (Considere ese trade-off
  antes de adoptar la herramienta.)
- JWPUB no registrado en `meps_catalog` → fallback automático a WOL.
- Cambio de pub de estudio (2027+): edite `study_books.REGISTRY`.
