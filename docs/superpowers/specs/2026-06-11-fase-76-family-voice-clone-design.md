# Fase 76 — `family-voice-clone`: TTS con voz familiar consentida

> **Fecha**: 2026-06-11
> **Estado**: Diseño aprobado (pendiente de implementación)
> **Owner**: Elias
> **Tier**: 3 (voz / accesibilidad)
> **Capa**: D — Voz / accesibilidad
> **Depende de**: F34 `audio-premium` (TTS multi-provider + consent.txt pattern), F43 `agent-tracing` (audit), F61 `memoria-asistente` (perfil), F53 `polyglot-python` (venv aislado torch+xformers)
> **Documento padre**: [`2026-06-11-fases-65-76-overview.md`](2026-06-11-fases-65-76-overview.md)
> **Predecesor conceptual**: F34 `audio-premium` con voces preset (Kokoro / XTTSv2 / F5 / ElevenLabs)

## Motivación

Niños y ancianos prefieren oír la Biblia y publicaciones JW en la
voz de un familiar (padre, madre, abuelo). Hoy F34 ofrece voces
estándar (Kokoro 82M multi-idioma, XTTSv2, F5-TTS, ElevenLabs).
Ninguna es familiar.

Caso de uso típico:
- Padre que graba 5-10 min de muestras propias → cualquier capítulo
  bíblico se lee con su voz mientras el niño se duerme.
- Adulto mayor con dificultad visual prefiere oír las Atalayas en
  voz de su hijo lejano que ya consintió.
- Familia que escucha texto diario juntos en voz de la madre que
  falleció (caso emocionalmente cargado — requiere consent.txt
  documentado en vida).

## Objetivos

1. CLI `jw voiceclone train --name papa` guía paso a paso:
   - Captura muestras vía mic (3-5 grabaciones de ~30s).
   - Crea `consent.txt` interactivamente con disclaimers + firma.
   - Fine-tune F5-TTS o XTTSv2 local con LoRA si soportado.
   - Voz queda en `~/.jw-agent-toolkit/voices/{name}/` con pesos
     cifrados opt-in.
2. CLI `jw say "Juan 3:16" --voice papa` usa la voz entrenada.
3. **Audit trail F43**: cada uso de la voz emite evento JSONL
   `voice_used` con timestamp + texto sintetizado.
4. **License gate**: cada voz tiene `license: personal_family_only`
   hard-coded; CLI rechaza usos comerciales detectables (warning).
5. **Cifrado opt-in** de pesos con `JW_VOICE_KEY` (Fernet, F61
   pattern).

## No-objetivos (boundaries vinculantes)

- **No** se entrena sobre voces sin consent.txt firmado.
- **No** se exporta el modelo a cloud por defecto. Pesos quedan
  en disco local.
- **No** se entrena sobre voces de figuras públicas / oficiales JW.
  El CLI rechaza nombres tipo "branch", "broadcasting", "president"
  con lista deny.
- **No** se usa para deepfakes vocales. License gate es explícita.
- **No** se distribuye `jw voiceclone` como herramienta de
  suplantación — el README + guías marcan claramente "uso familiar
  privado".

## Decisión clave: ¿F5-TTS vs XTTSv2 vs ambos?

### Opción A — Solo F5-TTS (más reciente)

**Pros**: Estado del arte 2025; zero-shot voice cloning de alta
calidad con <1 min muestras.
**Contras**: Modelo pesado (~1.5GB); requires torch+xformers.

### Opción B — Solo XTTSv2 (Coqui)

**Pros**: Bien probado, voice cloning con <30s.
**Contras**: Calidad menor que F5-TTS para emociones; Coqui en
mantenimiento limitado.

### Opción C — Ambos vía Plugin SDK F41 (`gen_providers`)

Usuario elige al entrenar. Defaults F5-TTS si GPU disponible,
XTTSv2 si solo CPU.

### Decisión: **Opción C** (ambos vía Plugin SDK F41)

Justificación:
1. F34 audio-premium ya integra ambos.
2. Polyglot Python F53 maneja venv aislado por modelo.
3. Usuarios sin GPU mantienen capacidad.

## Arquitectura

```
              jw voiceclone train --name papa
                       │
                       ▼
       ┌────────────────────────────────────┐
       │ 1. Wizard interactivo              │
       │    - explica uso ético             │
       │    - solicita firma consent        │
       │    - graba 3-5 muestras vía mic    │
       │    - valida quality (SNR, duración)│
       └─────────────────┬──────────────────┘
                         │
                         ▼
       ┌────────────────────────────────────┐
       │ 2. Consent.txt + voice metadata    │
       │    name, license: personal_family  │
       │    consent_signed_at, signer_name  │
       └─────────────────┬──────────────────┘
                         │
                         ▼
       ┌────────────────────────────────────┐
       │ 3. Provider selection              │
       │    F5-TTS if GPU else XTTSv2       │
       │    runs in venv F53                │
       └─────────────────┬──────────────────┘
                         │
                         ▼
       ┌────────────────────────────────────┐
       │ 4. Fine-tune / LoRA training       │
       │    weights → voices/{name}/        │
       │    optional encrypt with JW_VOICE_KEY │
       └─────────────────┬──────────────────┘
                         │
                         ▼
       ┌────────────────────────────────────┐
       │ 5. Validation sample synthesis     │
       │    "Hola, soy papa. Esta es mi voz │
       │     entrenada para uso familiar."  │
       └────────────────────────────────────┘
```

## Contratos de tipos

```python
# packages/jw-core/src/jw_core/audio/voice_clone/models.py

from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

License = Literal[
    "personal_family_only",
    "personal_education_only",
]

Provider = Literal["f5tts", "xttsv2"]

class ConsentRecord(BaseModel):
    signer_name: str
    signer_relationship: Literal[
        "self", "parent", "spouse", "child", "sibling", "other"
    ]
    signed_at: datetime
    explicit_uses: list[str]            # ["read_bible", "read_watchtower"]
    expires_at: datetime | None = None
    revoked: bool = False
    revoke_reason: str | None = None

class TrainingSample(BaseModel):
    path: str
    duration_s: float
    snr_db: float
    sample_rate_hz: int
    transcript: str = ""                # opcional, mejora training

class VoiceProfile(BaseModel):
    name: str                           # "papa", "mama_2024"
    provider: Provider
    consent: ConsentRecord
    license: License = "personal_family_only"
    samples: list[TrainingSample]
    weights_path: str
    weights_encrypted: bool = False
    created_at: datetime
    last_used_at: datetime | None = None
    use_count: int = 0
    trace_audit_path: str | None = None

class TrainResult(BaseModel):
    profile: VoiceProfile
    validation_sample_path: str         # wav generado de prueba
    training_log_path: str
    duration_s: float
```

## API pública

```python
# packages/jw-core/src/jw_core/audio/voice_clone/__init__.py

from jw_core.audio.voice_clone.trainer import train_voice
from jw_core.audio.voice_clone.synthesizer import synthesize_with_voice
from jw_core.audio.voice_clone.registry import (
    list_voices, get_voice, delete_voice, revoke_consent
)
from jw_core.audio.voice_clone.models import (
    VoiceProfile, ConsentRecord, TrainingSample, TrainResult, License, Provider
)

__all__ = [
    "train_voice",
    "synthesize_with_voice",
    "list_voices",
    "get_voice",
    "delete_voice",
    "revoke_consent",
    "VoiceProfile",
    "ConsentRecord",
    "TrainingSample",
    "TrainResult",
    "License",
    "Provider",
]
```

## CLI

```bash
# Wizard de entrenamiento
jw voiceclone train --name papa

# Train no-interactivo desde grabaciones existentes
jw voiceclone train --name papa \
  --samples sample1.wav,sample2.wav,sample3.wav \
  --consent-file papa_consent.json \
  --provider f5tts

# Listar voces entrenadas
jw voiceclone list

# Usar voz en TTS
jw say "Juan 3:16" --voice papa

# Eliminar voz (borra weights + consent record)
jw voiceclone delete papa --confirm

# Revocar consent (sin borrar weights, pero impide uso)
jw voiceclone revoke papa --reason "consent withdrawn"

# Ver audit trail
jw voiceclone audit papa
```

## MCP tools

- `voice_clone_list() → list[VoiceProfile]`
- `voice_clone_synthesize(text, voice_name, language="es") → audio bytes`
- `voice_clone_audit(voice_name) → list[TraceEvent]`

**No** se expone `voice_clone_train` en MCP — el wizard es CLI-only
porque requiere captura de mic interactiva y firma de consent.

## Wizard interactivo (CLI)

```
$ jw voiceclone train --name papa

🎙 Entrenamiento de voz familiar

ESTA HERRAMIENTA SOLO DEBE USARSE CON CONSENTIMIENTO
EXPLÍCITO DE LA PERSONA CUYA VOZ SE CLONA.

Usos permitidos:
  - Lectura de Biblia y publicaciones JW para uso personal/familiar
  - Lectura de textos personales del usuario consentido

Usos PROHIBIDOS:
  - Suplantar a la persona en comunicaciones
  - Crear contenido falso atribuido a la persona
  - Distribución pública del modelo o audios

¿La persona cuya voz se clonará está presente y ha leído lo anterior? [y/N]: y

Nombre de la persona consentida: Juan Pérez
Relación con el operador: parent
Usos explícitos consentidos (separados por coma)
  [read_bible, read_watchtower, read_personal_notes]: read_bible, read_watchtower
¿Hay fecha de expiración? (YYYY-MM-DD o vacío para ninguno): 2027-12-31

📝 Generando consent.txt... ok

🎙 Vamos a grabar 3 muestras de ~30 segundos cada una.
   Necesitas un micrófono y un ambiente silencioso.
   Para cada muestra, lee el texto que aparece en pantalla.

Muestra 1/3 — texto:
  "Estaba escrito en el principio. La Palabra estaba con Dios..."
Presiona Enter para empezar a grabar (30s), Ctrl+C para cancelar:
[GRABANDO 00:30 / 00:30]
✓ Calidad: SNR 28dB, duración 31.2s — OK

Muestra 2/3 — texto:
  "Como dijo el rey David en el salmo 23..."
...

✓ 3 muestras válidas grabadas.

🧠 Iniciando entrenamiento con F5-TTS (~5 minutos en GPU, ~30 en CPU)...
   [████████████░░░░░░░░] 60%

✓ Entrenamiento completado en 4m 12s.

🔊 Sintetizando muestra de validación...
   "Hola, soy Juan Pérez. Esta es mi voz entrenada para uso familiar."
   → ~/.jw-agent-toolkit/voices/papa/validation.wav

Voz 'papa' lista para usar:
  jw say "Cualquier texto" --voice papa
```

## Consent.txt format

`~/.jw-agent-toolkit/voices/papa/consent.json`:

```json
{
  "voice_name": "papa",
  "signer_name": "Juan Pérez",
  "signer_relationship": "parent",
  "signed_at": "2026-06-11T15:23:00",
  "operator_name": "Carlos Pérez",
  "license": "personal_family_only",
  "explicit_uses": ["read_bible", "read_watchtower"],
  "expires_at": "2027-12-31T23:59:59",
  "revoked": false,
  "tool_version": "0.65.0",
  "samples_sha256": [
    "a1b2c3...", "d4e5f6...", "g7h8i9..."
  ]
}
```

Firma digital opcional via `--sign-with-gpg <key_id>` futuro.

## Polyglot Python F53

Tanto F5-TTS como XTTSv2 requieren torch + xformers + scipy + librosa
con versiones específicas:

```
~/.jw-agent-toolkit/runners/f5tts/
  .venv/                  # Python 3.11 con torch 2.4 + xformers
  state.json

~/.jw-agent-toolkit/runners/xttsv2/
  .venv/                  # Python 3.11 con TTS Coqui
  state.json
```

CLI bootstrap:
```bash
jw voiceclone install-runner --provider f5tts
jw voiceclone install-runner --provider xttsv2
```

## License gate runtime

Cada llamada a `synthesize_with_voice()`:

1. Carga `VoiceProfile`.
2. Verifica `consent.revoked == False`.
3. Verifica `expires_at` no expirado.
4. Verifica `text` no contiene tokens de uso comercial detectables
   (e.g., "speech for X corporation", "marketing campaign for X").
5. Emite evento F43 `voice_used(voice_name, text_sha256, ts)`.
6. Sintetiza.

## Plan de pruebas

| Caso                                                          | Tipo        |
|---------------------------------------------------------------|-------------|
| `ConsentRecord` Pydantic acepta campos requeridos             | Unit        |
| Consent expirado bloquea synthesize                           | Unit        |
| Consent revocado bloquea synthesize                           | Unit        |
| License gate detecta texto comercial → warning                | Unit        |
| Wizard de captura valida SNR > threshold                      | Unit        |
| FakeProvider train sin GPU produce VoiceProfile               | Integration |
| Synthesize con FakeProvider produce wav válido                | Integration |
| Audit trail F43 emite 1 evento por synthesize                 | Integration |
| Encryption opt-in con JW_VOICE_KEY funciona                   | Unit        |
| Registry list_voices excluye revocadas (opt-in)               | Unit        |
| MCP synthesize devuelve bytes correctos                       | Integration |
| Deny list rechaza nombres "branch", "broadcasting"            | Unit        |
| Wizard genera consent.json con SHA-256 de samples             | Integration |
| Polyglot runner bootstrap genera venv F5TTS                   | E2E (slow)  |

## Riesgos / mitigaciones

| Riesgo                                                  | Mitigación                                          |
|---------------------------------------------------------|-----------------------------------------------------|
| Operador clona voz sin consent real                     | Wizard explícito + consent.json + audit trail F43; mitigación organizacional, no técnica |
| Voz se usa para fraude / suplantación                   | License gate + tool README + warning legal en CLI   |
| Pesos se filtran (laptop perdido)                       | Cifrado opt-in con JW_VOICE_KEY                     |
| Niño accidentalmente entrena voz de su madre fallecida sin consent previo | Wizard rechaza si `signer_name` no presente; require live mic capture |
| Modelo overfittea, voz "robótica"                       | Min 3 muestras + 5 min total; validation sample QA  |
| Provider F5-TTS muy pesado                              | Fallback XTTSv2 automático si no GPU                |
| Polyglot install falla                                  | Mensaje claro + link a F53 troubleshooting          |

## Métricas de éxito

- **MOS subjective**: ≥3.5/5.0 en evaluación familiar (3-5 evaluadores
  que conocen la voz original).
- **Time to train**: <10 min en MacBook M1 con XTTSv2.
- **Consent compliance**: 100% de voces tienen consent.json válido.

## Wire-up

- CLI: `packages/jw-cli/src/jw_cli/commands/voiceclone.py`.
- MCP: 3 tools nuevas (síntesis + audit, no train).
- F34 audio-premium: provider nuevo `family_voice` que delegate a
  registry de voiceclone.
- F43 tracing: nuevo event kind `voice_used`.
- F61 memoria: opt-in track de voces preferidas por usuario.

## Guía resultante

`docs/guias/family-voice-clone.md` — quick start ético, wizard
walkthrough, gestión de consent, troubleshoot polyglot, FAQ
("¿puedo usarla para sermones públicos?" — NO).
