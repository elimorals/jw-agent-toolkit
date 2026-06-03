---
title: "Polyglot Python: venv per feature"
description: "Patrón arquitectónico de F53 para usar librerías ML pesadas con cadencias de soporte Python distintas a la del monorepo."
date: "2026-06-02"
---

# Concepto — Polyglot Python: venv per feature

> Patrón arquitectónico introducido en Fase 53 (Omnilingual ASR) para
> permitir que el toolkit use librerías ML pesadas con cadencias de
> soporte de Python distintas a la suya, sin atar la versión de todo el
> monorepo a la dep más lenta.

## El problema

El ecosistema ML de Python tiene una larga cola de soporte para
versiones nuevas del intérprete. Cuando CPython lanza una versión
(3.13), las librerías pesadas (`fairseq2`, partes de `torch`,
`tensorflow`, `flash-attn`, librerías CUDA específicas) tardan meses o
años en publicar wheels cp313. Algunas nunca lo hacen.

El monorepo del toolkit ya estaba en Python 3.13 cuando llegó Fase 53.
Migrar a 3.12 por una sola librería habría sido una regresión:

- 11 paquetes del workspace bumped down.
- Features 3.13-only (algunas anotaciones de tipos, `type` aliases PEP
  695, mejoras de `typing`) tendrían que rehacerse.
- Devs y CI saltando entre versiones por feature.

## La alternativa elegida: subprocess + venv dedicado

```
┌─────────────────────────────────────────────────────────┐
│ toolkit (Python 3.13)                                    │
│   - 1500 tests in ~25s                                   │
│   - import omnilingual_asr  ← NO. Imposible en 3.13.    │
│                                                          │
│   Provider abstracto:                                    │
│   class OmnilingualProvider(ASRProvider):                │
│     def transcribe(audio, *, language):                  │
│       subprocess.run([                                   │
│         self.venv_python,    # ~/.jw-core/.../python     │
│         WORKER_SCRIPT,        # omnilingual_worker.py    │
│         "--audio", audio,                                │
│         "--lang", flores,                                │
│       ])                                                 │
│       return TranscriptionResult.from_json(stdout)       │
└──────────────────────────────────────┬──────────────────┘
                                       │
                                       │ subprocess fork
                                       ▼
┌─────────────────────────────────────────────────────────┐
│ ~/.jw-core/omnilingual/venv  (Python 3.12)               │
│   - Standalone, NO importa jw_core                       │
│   - Solo `omnilingual-asr` + torch + fairseq2            │
│                                                          │
│   omnilingual_worker.py:                                 │
│     from omnilingual_asr.models.inference.pipeline ...   │
│     pipeline = ASRInferencePipeline(model_card=...)      │
│     result = pipeline.transcribe([audio], lang=[...])    │
│     print(json.dumps({"text": ..., "language": ...}))    │
└─────────────────────────────────────────────────────────┘
```

## Por qué funciona

### 1. Contrato JSON cruza el process boundary

El worker recibe args CLI y emite UN OBJETO JSON a stdout. Nada más.
Errores van a stderr con `return code != 0`. El padre los parsea.

Eso desacopla los runtimes: el worker puede actualizar fairseq2,
cambiar de torch 2.8 a 2.9, mover modelos — el padre no se entera
mientras el contrato JSON se respete.

### 2. El worker es Python puro

`omnilingual_worker.py` **no importa nada de `jw_core`**. Es un script
standalone (~60 LOC). Eso vuelve el venv 3.12 mínimo: solo carga lo
que la lib externa necesita.

Si quisiéramos compartir código entre worker y padre, tendríamos que
empaquetar `jw_core` en formato compatible con ambas versiones de
Python. Mucho mejor mantener el worker pequeño.

### 3. Bootstrap declarativo

El provider tiene `install()` que crea el venv. El usuario corre
`jw omnilingual install` una vez. El comando:

```python
def install(self, python312_executable=None):
    py312 = python312_executable or shutil.which("python3.12")
    subprocess.run([py312, "-m", "venv", str(self.venv_dir)])
    pip = self.venv_dir / "bin" / "pip"
    subprocess.run([str(pip), "install", "omnilingual-asr",
                    "torch==2.8.0", "torchaudio==2.8.0"])
```

`torch==2.8.0 torchaudio==2.8.0` aparece pinned porque el resolver
libre pickea `torchaudio==2.11.0` contra `torch==2.8.0` — incompatibles
ABI, segfault al import. Este tipo de hard-pin va en el código del
provider, no en pyproject.toml del toolkit, porque es específico del
runtime del worker.

### 4. Detección runtime, no build-time

```python
def is_available(self) -> bool:
    if not self.venv_python.is_file():
        return False
    check = subprocess.run(
        [str(self.venv_python), "-c", "import omnilingual_asr"],
        capture_output=True, timeout=10,
    )
    return check.returncode == 0
```

El factory pregunta esto antes de enrutar a este provider. Si el
usuario nunca corrió `install`, el factory cae al siguiente provider
(Deepgram, Whisper) sin mensaje de error obvio. Si necesita un mensaje
claro, llamar a `provider.transcribe()` lanza
`TranscriptionError("Omnilingual venv not found at ... Run jw omnilingual install")`.

## Cuándo NO usar este patrón

- **Cuando la latencia importa.** El cold-start del intérprete 3.12
  añade ~300 ms por llamada. En batch (ASR de un audio de 5 min) es
  invisible. En hot path (streaming, autocompletado), es un asesino.
- **Cuando el contrato JSON no captura todo.** Si necesitas streaming
  bidireccional, cancellation, file handles compartidos, el subprocess
  se vuelve frágil. En esos casos, IPC más rico (Unix sockets, gRPC) o
  in-process son mejores.
- **Cuando el venv pesa más que el beneficio.** Omnilingual mete ~3 GB
  de wheels para ofrecer 1672 idiomas — relación favorable. Pero si
  fuera una lib que pesa 5 GB para cubrir 10 idiomas más que Whisper,
  meterla en un venv aparte podría no valer la pena.

## Cuándo SÍ usar este patrón

- **Una lib pesada que tu base de código necesita esporádicamente y
  tiene restricciones de versión Python.** Caso típico: ASR/TTS
  state-of-the-art, modelos de visión, librerías CUDA específicas.
- **Cuando quieres aislar fallos.** Si el modelo segfaultea, el
  subprocess muere pero el toolkit sigue corriendo. En in-process el
  segfault se lleva todo.
- **Cuando quieres que múltiples versiones de la lib coexistan.** Cada
  feature/provider con su propio venv puede tener una versión distinta
  sin conflict resolution.

## Generalización

El patrón es transferible a otras libs que llegarán en el futuro:

```
~/.jw-core/
├── omnilingual/venv      ← Python 3.12, fairseq2, torch 2.8
├── flash-attn/venv       ← Python 3.11, CUDA 12 builds
├── transformer-deploy/   ← Python 3.12, TRT-LLM
└── jw-finetune-trt/      ← Python 3.10, deepspeed pinned
```

Cada uno con un provider en el toolkit que sabe cómo llamarlos. El
toolkit se mantiene en `requires-python = ">=3.13"`.

## Trade-off con la integración profunda

F55 (wire-up integration) hace que `get_asr_provider(language="qu")`
elija Omnilingual automáticamente. Para el usuario el subprocess es
invisible. Eso es ideal: la complejidad arquitectónica del polyglot
está oculta detrás de un factory simple.

Pero la complejidad no desaparece — el costo se paga al debug:

- **Stack traces parten en el process boundary.** Un error en
  `pipeline.transcribe()` aparece en stderr del worker como
  `pipeline failure: <repr>`. El padre lo re-raisea como
  `TranscriptionError("...exit code 3: pipeline failure: ...")`. No hay
  Python traceback completo.
- **Profiling es discontinuo.** `cProfile` en el toolkit no ve los
  ciclos gastados dentro del worker. Profiling end-to-end requiere
  añadir `time.perf_counter()` antes/después del subprocess.
- **Setup es manual.** `jw omnilingual install` no se corre en CI por
  defecto (3 GB de wheels). Los tests del provider usan `subprocess`
  mockeado.

Estos costos son aceptables porque:

1. El provider ya capa errores con mensajes claros (`venv not found`,
   `not importable`).
2. Los profiling tools (Linux `perf`, py-spy con `--full-filenames`,
   `strace`) sí cruzan el boundary.
3. CI cubre el flow del lado padre exhaustivamente (16 tests con
   subprocess mockeado).

## Referencias

- Fase 53 — `docs/guias/omnilingual-asr.md` — implementación end-to-end.
- Fase 55 — `docs/guias/multilingual-wire-up.md` — cómo se integra al
  factory automático.
- `packages/jw-core/src/jw_core/audio/asr_providers/omnilingual.py`
  — el provider Python 3.13 que dispara el worker.
- `packages/jw-core/src/jw_core/audio/asr_providers/omnilingual_worker.py`
  — el worker Python 3.12 minimal.
