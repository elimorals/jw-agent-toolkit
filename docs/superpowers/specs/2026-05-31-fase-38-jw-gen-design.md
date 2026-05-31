# Fase 38 — `jw-gen`: séptimo paquete (generación ilustrativa con difusión)

> **Fecha**: 2026-05-31
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 4 (UX / nuevo paquete)
> **Depende de**: ninguna fase técnica (paquete aislado). **Política aprobada por el usuario** (ver sección "Policy and safety boundaries").
> **Documento padre**: [`2026-05-31-fases-33-38-overview.md`](2026-05-31-fases-33-38-overview.md)
> **Predecesores**: Fases 0-32 (1649 tests verdes en CI) + Fases 33-37 (mejoras de recuperación/multimodalidad).

## Motivación

Las primeras 37 fases construyeron capacidad de **recuperación, síntesis y razonamiento** sobre el corpus oficial. Fase 38 abre la primera capacidad que **produce contenido nuevo** en lugar de recuperarlo: ilustraciones, audio de ambiente y fragmentos de video para apoyar **presentaciones personales y discursos** (estudio bíblico, parte de la Reunión Vida y Ministerio, discurso público, repaso familiar).

Esto introduce un tipo de riesgo **cualitativamente distinto** al de las fases 1-37:

- El toolkit nunca generó pixels ni audio nuevo; sólo manipulaba contenido oficial.
- Los outputs sintéticos pueden ser **confundidos con material oficial JW** si se distribuyen mal.
- Voces y caras generadas tocan privacidad y dignidad de hermanos reales.
- Los pesos y APIs de modelos generativos viven fuera del control del proyecto.

El objetivo de esta fase es **abrir esa capacidad sin abrir la puerta al mal uso**. Por eso la política y los filtros de seguridad son LOAD-BEARING: forman parte del contrato técnico, no son disclaimer.

## Objetivos (en orden de prioridad)

1. **Política técnica blindada**: cada archivo escrito a disco lleva watermark visible + metadata EXIF/XMP + disclaimer.txt hermano. No hay ruta de código que escriba un output sin pasar por `policy.assert_personal_use(...)`.
2. **Safety filters anti-emulación**: prompts que intenten emular logos JW, clonar voces sin doble opt-in, o producir rostros fotorrealistas sin opt-in son rechazados **antes** de llamar al provider (ahorra coste, ahorra riesgo).
3. **Multi-provider con API-first**: imagen, audio y video con providers comerciales como default; locales opcionales. Cada provider tiene un fake hermano determinista para tests.
4. **CLI + MCP simétricos**: `jw gen image|audio|video --prompt --provider --out` y `generate_illustration(prompt, kind, size, watermark=True)` exponen el mismo contrato.
5. **Multi-idioma desde día 1**: prompts plantilla, mensajes de error, disclaimers y filtros de keywords en en/es/pt.

## No-objetivos (boundaries vinculantes)

Estas líneas **no** las cruza Fase 38:

- **No distribuir pesos de modelos de difusión**. Si el usuario quiere ejecución local (Stable Diffusion, Flux dev, etc.) instala su propio runtime y nosotros sólo ofrecemos adapter delgado.
- **No automatizar publicación**. El paquete escribe archivos a disco. Subir a JW.org / canales oficiales / redes sociales **nunca** es responsabilidad de `jw-gen`. Cualquier integración futura con cuentas oficiales JW está fuera de scope, permanentemente.
- **No emular material oficial JW**. Logos, identidad gráfica de Watchtower / Awake! / Kingdom Hall signs / branding de jw.org son keyword-block hard.
- **No clonar voces de hermanos sin doble opt-in firmado**. `--voice-clone` requiere `input.txt` firmado hermano del audio fuente (ver `safety.refuse_voice_cloning_without_double_optin`).
- **No generar rostros fotorrealistas de personas identificables por defecto**. Default estilizado; `--realistic-people` desbloquea con warning explícito.
- **No reemplazar el material oficial en presentaciones**. Las ilustraciones son **apoyo visual**, las Escrituras y publicaciones siguen siendo la fuente.
- **No medir "calidad estética"** de outputs en CI. Eso requiere humano. CI sólo verifica policy + safety + smoke.

## Policy and safety boundaries — contrato legal y ético

Esta sección no es un disclaimer: es el contrato técnico que el resto del paquete implementa. Si un cambio futuro debilita esta sección, debe ser rechazado en code review.

### Política aprobada por el usuario (fuente única)

El usuario aprobó explícitamente esta política antes de implementar la fase:

> **"Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio. NO emulación contenido oficial JW."**

Esto se traduce en cuatro reglas duras del paquete:

1. **Personal/ilustrativo únicamente**: cada output lleva disclaimer escrito explicando uso personal. Si el usuario quiere usar el output en cualquier contexto público (red social, web, distribución impresa fuera de presentación familiar/congregacional informal), el disclaimer le recuerda que **no es contenido oficial JW**.
2. **Watermark obligatorio por defecto**: `WatermarkConfig.mode = "visible+metadata"` es el default y el único modo que se permite cuando el output va a salir del directorio `~/.jw-gen/private/`. Modos `metadata-only` y `off` requieren flag explícito `--no-visible-watermark` que loguea warning + escribe entrada en `~/.jw-gen/audit.log`.
3. **Metadata EXIF/XMP siempre**: incluso si el watermark visible se desactiva, EXIF/XMP **nunca** se desactivan. Si la librería de escritura (PIL/piexif/python-xmp-toolkit) falla, el archivo no se escribe — fail-closed.
4. **Disclaimer.txt hermano**: cada archivo generado (`out.png`) recibe un compañero (`out.png.disclaimer.txt`) en en/es/pt. Si el escritor del disclaimer falla, el archivo no se entrega.

### Safety filters (no negociables)

`safety.py` expone tres filtros que corren **antes** de cualquier llamada a provider:

| Filtro | Bloquea | Habilitable cómo |
|---|---|---|
| `refuse_jw_logo_emulation(prompt, lang)` | Prompts con keywords/intent de emular logo Watchtower, Awake!, identidad JW.org, Kingdom Hall oficial. Lista keyword multi-idioma + heurística semántica opcional. | **Nunca**. Es hard refuse. |
| `refuse_voice_cloning_without_double_optin(audio_src, signed_consent)` | Voice cloning sin `--voice-clone` + `input.txt` firmado (formato definido abajo) hermano del audio fuente. | `--voice-clone` flag **y** archivo de consentimiento firmado **y** confirmación interactiva en CLI. |
| `refuse_realistic_faces_without_optin(prompt, flag)` | Prompts que piden rostros fotorrealistas de personas identificables sin flag explícito. Default: forzar estilo (`stylized`, `painterly`, `illustration`). | `--realistic-people` flag. Loguea entrada de auditoría. |

#### Keyword block — `refuse_jw_logo_emulation`

Lista multilingüe en `safety.py` con normalización Unicode + deacento + lowercase:

- **en**: `watchtower logo`, `jw.org logo`, `awake magazine cover`, `kingdom hall sign`, `official JW emblem`, `governing body`, `bethel branch logo`, …
- **es**: `logo de la Atalaya`, `logotipo JW`, `portada de Despertad`, `letrero oficial Salón del Reino`, `emblema oficial JW`, …
- **pt**: `logo da Sentinela`, `logotipo JW`, `capa de Despertai!`, `placa oficial Salão do Reino`, `emblema oficial JW`, …

Match por **substring normalizado** + **regex de proximidad** ("watchtower" ± 3 palabras de "logo|emblem|brand|official"). Bloquea fail-closed: si en duda, refuse.

#### Doble opt-in — `refuse_voice_cloning_without_double_optin`

Para clonar la voz de un hermano (p.ej. para crear audio de prueba antes de un discurso propio), se exige:

1. Flag CLI explícito `--voice-clone`.
2. Junto al `--input audio.wav`, un archivo `audio.wav.consent.txt` con formato:

```
voice_owner: <nombre del hermano>
date: <YYYY-MM-DD>
purpose: <texto libre — uso esperado>
signature_sha256: <sha256 firmado de las 3 líneas anteriores>
```

3. Confirmación interactiva en CLI: `"¿Confirmas que <nombre> aprobó este uso? [si/no]"` (también en en/pt).
4. Si los 3 anteriores pasan, se loguea entrada en `~/.jw-gen/audit.log` con timestamp + sha256(prompt) + sha256(input) + voice_owner.

Tests pueden inyectar `signed_consent_fake_ok=True` para saltar (1)-(4) pero ese parámetro **no existe** en CLI ni en MCP — sólo en el adapter `providers/fakes.py`.

#### Anti-realismo por defecto — `refuse_realistic_faces_without_optin`

Por defecto, **todos** los prompts de imagen que mencionen personas (heurística: nombres de persona en es/en/pt + sustantivos `persona`/`person`/`pessoa`/`hermano`/`brother`/`irmão` + verbos de acción) son **augmented** con un sufijo de estilo:

```
" en estilo ilustrado, pintura suave, no fotorrealista" (es)
" in illustrated style, soft painting, not photorealistic" (en)
" em estilo ilustrado, pintura suave, não fotorrealista" (pt)
```

Si el usuario pasa `--realistic-people`, el sufijo no se añade pero el output recibe entrada explícita en `audit.log` y un disclaimer adicional `realistic-people-warning.txt`.

### Audit log

`~/.jw-gen/audit.log` es JSONL append-only con un evento por cada generación. Schema:

```json
{
  "timestamp": "2026-05-31T14:23:45Z",
  "kind": "image|audio|video",
  "provider": "nanobanana",
  "prompt_sha256": "abc123...",
  "output_path": "/Users/.../out.png",
  "watermark_mode": "visible+metadata",
  "safety_flags": {
    "logo_check": "pass",
    "voice_clone_optin": "n/a",
    "realistic_faces_optin": "n/a"
  },
  "warnings": []
}
```

El log nunca contiene el prompt en claro (sólo su hash) y nunca contiene contenido del output. Está pensado para auditoría posterior si surge una pregunta sobre uso.

## Arquitectura

Séptimo paquete del monorepo. Aislado: **no** importa nada de `jw-rag`, `jw-agents`, `jw-eval`, `jw-finetune`. Sólo puede importar `jw-core` para tipos compartidos (idiomas, paths, audit utils si surgen).

```
packages/jw-gen/
├── pyproject.toml
└── src/jw_gen/
    ├── __init__.py
    ├── policy.py                 # CARGADO OBLIGATORIO antes de cualquier escritura a disco
    ├── safety.py                 # 3 filtros no-negociables (corren antes del provider)
    ├── factory.py                # get_provider(kind, target, hardware) — API-first
    ├── audit.py                  # JSONL append-only en ~/.jw-gen/audit.log
    ├── models.py                 # WatermarkConfig, SafetyDecision, GenerationRequest, GenerationResult (Pydantic)
    ├── providers/
    │   ├── __init__.py
    │   ├── base.py               # GenerationProvider Protocol con triple-target
    │   ├── image/
    │   │   ├── nanobanana.py     # Nano Banana 2 (default)
    │   │   ├── flux2.py          # Flux 2 Pro (API)
    │   │   ├── recraft.py        # Recraft v4 (API)
    │   │   ├── ideogram.py       # Ideogram v3 (API)
    │   │   └── imagen.py         # Imagen 4 (Google Vertex / Gemini API)
    │   ├── audio/
    │   │   ├── elevenlabs.py     # ElevenLabs (TTS + voice clone con doble opt-in)
    │   │   ├── suno.py           # Suno (música)
    │   │   └── musicgen.py       # MusicGen (local + API)
    │   ├── video/
    │   │   ├── veo3.py           # Veo 3 (Gemini API)
    │   │   ├── kling.py          # Kling Video O3
    │   │   ├── seedance.py       # Seedance 2.0
    │   │   ├── higgsfield.py     # Higgsfield MCP
    │   │   └── runway.py         # Runway
    │   └── fakes.py              # Fakes deterministas para tests (todos los kinds)
    ├── prompts/
    │   ├── slide_template.md          # Plantilla slide ilustrativo
    │   ├── illustration_template.md   # Plantilla ilustración educativa
    │   └── bg_audio_template.md       # Plantilla audio de ambiente
    ├── cli.py                    # jw gen image|audio|video
    └── i18n/
        ├── en.json
        ├── es.json
        └── pt.json
└── tests/
    ├── test_policy.py             # watermark + EXIF/XMP + disclaimer (sin red)
    ├── test_safety.py             # los 3 filtros, casos positivos y negativos en en/es/pt
    ├── test_factory.py            # routing + auto-detect target
    ├── test_providers_fake.py     # cada kind con fake, smoke
    ├── test_audit.py              # JSONL append-only correcto
    ├── test_cli.py                # CliRunner contra fakes
    └── fixtures/
        ├── sample.png             # imagen base para tests de watermark
        ├── sample.wav             # audio base para tests
        └── signed_consent.txt     # consent file de ejemplo (test only)
```

### Reglas duras de diseño

1. `jw_gen` **no** importa `jw-rag`, `jw-agents`, `jw-eval`, `jw-finetune`. Aislamiento total. Sólo `jw-core` para idiomas/paths.
2. **Ningún módulo de provider escribe directamente a disco**. Devuelven `bytes` o `Path` temporal en `~/.cache/jw-gen/raw/`. La función `policy.finalize_output(raw_path, request, dest)` es la **única** que mueve a destino final tras aplicar watermark + metadata + disclaimer.
3. `safety.py` corre **antes** de `factory.get_provider(...).generate(...)`. Si refuse, no se gasta API call. Excepción: providers que tienen su propio safety endpoint (ej. OpenAI Moderations) — se llama además, no en lugar de.
4. `policy.assert_personal_use(dest)` valida que el path destino esté dentro de `~/.jw-gen/` o el usuario pasó `--out` explícito. Si pasó `--out` a directorio compartido (Dropbox/Drive detectado por path heurística), warning fuerte.
5. **Fail-closed siempre**: si watermark, metadata o disclaimer falla, el archivo no se entrega y el raw temp se borra.
6. **Tests sin red**: cada provider importa su SDK perezosamente. `providers/fakes.py` provee `FakeImageProvider`, `FakeAudioProvider`, `FakeVideoProvider` que devuelven bytes deterministas a partir de `sha256(prompt)`.
7. **Multi-idioma desde día 1**: i18n con JSON en `i18n/en.json`, `i18n/es.json`, `i18n/pt.json`. Disclaimers, mensajes de error, sufijos de prompt, todo.
8. **No dependencias pesadas en hard-deps**: PIL (`pillow`), `piexif`, `python-xmp-toolkit` son hard. SDKs de providers (`google-genai`, `openai`, `anthropic`, `elevenlabs`, etc.) van en extras `[image]`, `[audio]`, `[video]`, `[all]`.

## Providers detallados

Cada provider implementa `providers.base.GenerationProvider`:

```python
class GenerationProvider(Protocol):
    name: str
    kind: Literal["image", "audio", "video"]
    target: Literal["api", "nvidia", "mlx", "cpu"]

    def is_available(self) -> bool: ...
    def cost_estimate(self, request: GenerationRequest) -> CostHint: ...
    def generate(self, request: GenerationRequest) -> Path: ...  # devuelve raw temp path
```

### Imagen

| Provider | Target | Notas | SDK |
|---|---|---|---|
| `NanoBananaProvider` | api | Default en `kind=image`. Calidad/coste/velocidad balanceado. | `google-genai` (Gemini) |
| `Flux2Provider` | api | Premium. Fotorealismo controlado. | `fal_client` o `replicate` |
| `RecraftProvider` | api | Estilo ilustrado vectorial. Ideal para slides. | `recraft-ai` SDK |
| `IdeogramProvider` | api | Mejor con texto dentro de la imagen. | `ideogram` SDK |
| `ImagenProvider` | api | Google Vertex / Gemini API. Alternativa. | `google-genai` |

**Default routing**: `factory.get_provider("image")` → `NanoBananaProvider` si `JW_GEN_IMAGE_PROVIDER` no está set y la API key existe. Fallback: `RecraftProvider`, luego primero disponible. Si ninguno disponible: raise `NoProviderAvailable` con mensaje accionable.

### Audio

| Provider | Target | Notas | SDK |
|---|---|---|---|
| `ElevenLabsProvider` | api | TTS premium. Voice clone **solo** con doble opt-in. | `elevenlabs` |
| `SunoProvider` | api | Música completa con vocal. Bg music sólo para uso privado. | `suno` SDK / Replicate |
| `MusicGenProvider` | api/local | Generación instrumental. Opcional local vía `transformers`. | `replicate` o local |

**Default routing**: `factory.get_provider("audio")` → `ElevenLabsProvider` para TTS, `MusicGenProvider` para música ambiente. Suno requiere opt-in vía `--provider suno`.

### Video

| Provider | Target | Notas | SDK |
|---|---|---|---|
| `Veo3Provider` | api | Default. Gemini API. | `google-genai` |
| `KlingProvider` | api | Kling Video O3, ultra-realista. | `replicate` |
| `SeedanceProvider` | api | Seedance 2.0. | `replicate` |
| `HiggsfieldProvider` | api/mcp | Camera control extremo. Vía MCP. | `higgsfield-mcp` |
| `RunwayProvider` | api | Runway Gen-3+. | `runwayml` |

**Default routing**: `factory.get_provider("video")` → `Veo3Provider`. Sin local target — los modelos open-weight de video son demasiado pesados para ser default razonable.

### Fakes (tests)

`providers/fakes.py` provee:

- `FakeImageProvider`: devuelve PNG 512x512 con texto del prompt rasterizado (PIL). Determinista por `sha256(prompt)`.
- `FakeAudioProvider`: devuelve WAV de 3s con tono cuya frecuencia depende del hash del prompt.
- `FakeVideoProvider`: devuelve MP4 de 2s con 3 frames de `FakeImageProvider` y audio de `FakeAudioProvider`.

Todos cumplen `GenerationProvider.target = "cpu"`. `is_available()` siempre `True`. `cost_estimate()` siempre `CostHint(usd=0.0, time_s=0.01)`.

## Integración

### CLI (`jw-cli`)

Nuevo comando `jw gen`:

```
jw gen image --prompt "ilustración de ovejas..." --provider nanobanana --out slide_01.png
jw gen image --prompt "..." --size 1920x1080 --style illustration --lang es
jw gen audio --prompt "música suave para slide de oración" --duration 30 --out bg.wav
jw gen audio --tts "texto a hablar" --voice eleven_default --out narration.mp3
jw gen video --prompt "transición simbólica de día a noche" --duration 6 --out transition.mp4

# Flags de safety (raramente usados):
jw gen image --prompt "..." --realistic-people    # opt-in explícito
jw gen audio --tts "..." --voice-clone --input voice.wav  # requiere voice.wav.consent.txt
jw gen image --prompt "..." --no-visible-watermark  # metadata-only, loguea audit
```

Registro en `packages/jw-cli/src/jw_cli/main.py`:

```python
from jw_cli.commands import gen as gen_module
app.add_typer(gen_module.gen_app, name="gen")
```

`gen_module.gen_app` es un `typer.Typer` con subcommands `image`, `audio`, `video`. Cada subcommand: validar args → `safety.evaluate(...)` → `factory.get_provider(...)` → `policy.finalize_output(...)` → `audit.log_generation(...)`.

### MCP (`jw-mcp`)

Nueva herramienta `generate_illustration`:

```python
@mcp.tool()
def generate_illustration(
    prompt: str,
    kind: Literal["image", "audio", "video"] = "image",
    size: str = "1024x1024",
    watermark: bool = True,        # solo permite cambiar a False con env override
    lang: str = "es",
) -> dict:
    """Genera un archivo ilustrativo de uso personal con watermark + metadata + disclaimer.
    Retorna dict con path al output + path al disclaimer + audit_id."""
```

Restricción: `watermark=False` es **silenciosamente ignorado** vía MCP (un cliente MCP no puede saltarse policy). Si el llamante necesita metadata-only, debe correr CLI local con `--no-visible-watermark`.

### CI (`.github/workflows/ci.yml`)

Nuevo job `gen-policy`:

```yaml
gen-policy:
  needs: test
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: astral-sh/setup-uv@v3
    - run: uv sync --all-packages
    - run: uv run pytest packages/jw-gen/tests -m "not network"
    - name: Property test — 100 prompts ofensivos rechazados
      run: uv run pytest packages/jw-gen/tests/test_safety.py::test_jw_logo_emulation_rejected_property -v
    - name: Smoke — output siempre tiene watermark+metadata+disclaimer
      run: uv run pytest packages/jw-gen/tests/test_policy.py::test_finalize_output_always_complete_or_fails -v
```

Sin red. Usa sólo `FakeImageProvider`/`FakeAudioProvider`/`FakeVideoProvider`. La verificación de safety + policy es lo que protege; el contenido del output es irrelevante porque el filtro corre antes del provider.

### Workspace

Añadir a `pyproject.toml`:

```toml
[tool.uv.workspace]
members = [
    "packages/jw-core",
    "packages/jw-cli",
    "packages/jw-mcp",
    "packages/jw-rag",
    "packages/jw-agents",
    "packages/jw-finetune",
    "packages/jw-eval",
    "packages/jw-gen",
]

[tool.uv.sources]
jw-gen = { workspace = true }
```

Y en `[tool.pytest.ini_options].testpaths`: añadir `"packages/jw-gen/tests"`.

## Riesgos y mitigaciones

| # | Riesgo | Mitigación |
|---|---|---|
| 1 | Usuario distribuye output sin watermark y alguien lo confunde con material oficial JW | Watermark + metadata + disclaimer son fail-closed. Quitar el visible requiere flag explícito + audit log. Disclaimer.txt acompaña al archivo. |
| 2 | Provider API filtra contenido objetable que pasó nuestro filtro local | OK. Doble defensa. Si el provider rechaza, devolvemos su mensaje + sugerencia. |
| 3 | Voice clone usado para hacer audio falso de un hermano | Doble opt-in (flag + consent file firmado + confirmación interactiva). `audit.log` registra owner + sha256 input. Tests no pueden saltarlo desde CLI. |
| 4 | Prompt en otro idioma esquiva keyword block en inglés | Lista keyword en en/es/pt + normalización deacento + lowercase. Cobertura mínima 3 idiomas, ampliable vía property tests. |
| 5 | Generación de rostros reconocibles de personas reales sin consentimiento | Default estilizado. `--realistic-people` opt-in explícito + audit. No guardamos identidades. |
| 6 | Coste descontrolado en APIs | `cost_estimate()` antes de cada llamada. CLI muestra estimación + pide confirmación si supera `JW_GEN_COST_CONFIRM_THRESHOLD_USD` (default 1.0). |
| 7 | SDKs de providers cambian / breaking changes | Cada provider en su módulo aislado. Tests usan fakes. Provider real se mockea via `pytest-recording` si se quiere coverage end-to-end opcional. |
| 8 | Dependencias pesadas (Pillow, piexif, xmp-toolkit) en runtime | Pillow es hard (necesario para watermark). piexif/xmp-toolkit son hard pero ligeras. SDKs de providers en extras opcionales. |
| 9 | Audit log crece sin límite | Append-only JSONL con rotación a `audit.log.YYYY-MM.gz` mensual vía helper `audit.rotate()` (manual, no auto). |
| 10 | Heurística de "personas en el prompt" tiene falsos positivos (añade sufijo cuando no debería) | Falso positivo = imagen estilizada en lugar de fotorrealista. Riesgo bajo. Falso negativo es el riesgo real (rostros reales sin opt-in); ese lado se trata con keyword block redundante. |
| 11 | Output usado como "creatividad oficial" en presentaciones de congregación | Disclaimer.txt en es/en/pt explica: uso personal. La política de la fase fue explícitamente discutida y aprobada para "presentaciones/discursos" personales. No es responsabilidad del paquete enforcer en humanos; sí enforzar que el archivo cargue siempre la marca. |
| 12 | Higgsfield/Veo3/Suno cambian sus términos de servicio | Adapter delgado. Si un provider cae, otro reemplaza. Ningún flujo crítico del toolkit depende de jw-gen. |

## Métricas de éxito de la fase

- ✅ `uv run jw gen image --prompt "..."` produce `out.png` + `out.png.disclaimer.txt` + entrada en `~/.jw-gen/audit.log`.
- ✅ Property test: **100 prompts adversarios** (intent: emular logo Watchtower, clonar voz sin consent, generar rostro de persona identificable) → **0 outputs producidos**.
- ✅ Smoke test: 100% de outputs en `tests/` tienen watermark visible + EXIF + XMP + disclaimer hermano, en en/es/pt.
- ✅ CI `gen-policy` job verde sin red, sin API keys.
- ✅ Cobertura de tests del paquete ≥85% líneas, ≥95% en `policy.py` y `safety.py`.
- ✅ Documentación en `docs/guias/generacion-ilustrativa.md` con: política aprobada citada literalmente, ejemplos de uso, lista de keywords bloqueadas, ejemplo de consent file.
- ✅ Audit 1:1 en `docs/VISION_AUDIT.md` confirma que la política aprobada por el usuario coincide con la implementación.
- ✅ Sin regresiones: los 1649 tests previos siguen verdes.

## Cómo verificar al cerrar

```bash
# 1. Instalar
uv sync --all-packages

# 2. Tests del paquete (sin red)
uv run pytest packages/jw-gen/tests -v

# 3. Smoke con fake provider
uv run jw gen image --prompt "ilustración ovejas pastoreadas" --provider fake --out /tmp/test.png
ls /tmp/test.png /tmp/test.png.disclaimer.txt    # ambos existen
exiftool /tmp/test.png | grep -i "jw-gen"        # metadata presente

# 4. Property test de safety
uv run pytest packages/jw-gen/tests/test_safety.py -v

# 5. Verificar audit log
cat ~/.jw-gen/audit.log | jq .                   # JSONL bien formado

# 6. Intento de uso prohibido
uv run jw gen image --prompt "official Watchtower logo" --provider fake --out /tmp/bad.png
# debe salir con exit_code != 0 y NO crear /tmp/bad.png
```

## Plan de implementación (alto nivel)

Spec hijo: `docs/superpowers/plans/2026-05-31-fase-38-jw-gen-plan.md` (a escribir tras aprobar este spec).

Pasos cronológicos (TDD estricto: tests primero por sub-paso):

1. **Scaffold paquete**: `packages/jw-gen/pyproject.toml` + estructura. Workspace member en root `pyproject.toml`. CI testpath actualizado.
2. **Modelos Pydantic** (`models.py`): `WatermarkConfig`, `GenerationRequest`, `GenerationResult`, `SafetyDecision`, `CostHint`. Tests de validación.
3. **i18n bootstrap** (`i18n/{en,es,pt}.json`): disclaimers + mensajes de error + sufijos de prompt + keywords de logo block.
4. **Policy module** (`policy.py`): `apply_watermark` (PIL), `embed_metadata` (piexif + python-xmp-toolkit), `write_disclaimer_sibling`, `assert_personal_use`, `finalize_output`. Tests fail-closed.
5. **Safety module** (`safety.py`): 3 filtros con property tests (Hypothesis): prompts maliciosos en en/es/pt no pasan.
6. **Audit module** (`audit.py`): JSONL append-only + rotación. Tests determinismo timestamp via inyección.
7. **Provider base + fakes** (`providers/base.py` + `providers/fakes.py`): Protocol + 3 fakes deterministas. Tests smoke.
8. **Factory** (`factory.py`): `get_provider(kind, target=None)` con auto-detect, env override `JW_GEN_*_PROVIDER`, fallback chain. Tests sin red.
9. **Provider image — NanoBanana** (default): adapter delgado + cassette de `pytest-recording` para test opcional `-m network`.
10. **Provider image — Flux2, Recraft, Ideogram, Imagen** (uno por commit).
11. **Provider audio — ElevenLabs** (TTS default) + tests de doble opt-in voice-clone.
12. **Provider audio — Suno, MusicGen**.
13. **Provider video — Veo3** (default) + tests smoke.
14. **Provider video — Kling, Seedance, Higgsfield, Runway**.
15. **CLI** (`cli.py` + registro en `jw-cli/main.py`): subcommands `image`, `audio`, `video`. Tests con `CliRunner`.
16. **MCP tool** `generate_illustration` en `jw-mcp/server.py`. Tests del contract.
17. **Plantillas de prompt** (`prompts/{slide,illustration,bg_audio}_template.md`) con secciones en es/en/pt.
18. **CI job `gen-policy`** + property test 100 prompts adversarios.
19. **Guía** `docs/guias/generacion-ilustrativa.md` + audit 1:1 en `docs/VISION_AUDIT.md`.
20. **Verificación final**: 1649 tests previos verdes + tests nuevos verdes + smoke manual + audit log de smoke revisado.

Cada paso = 1 PR independiente con tests + sin regresiones. Total estimado: 7-10 días de trabajo enfocado, según la cantidad de providers que se integren en la primera ronda (mínimo viable: 1 imagen + 1 audio + 1 video reales + los 3 fakes = pasos 1-9, 11, 13, 15-20).
