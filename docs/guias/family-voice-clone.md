---
title: "TTS con voz familiar consentida (Fase 76)"
description: "TTS con voz de un familiar (con consentimiento) para uso personal no comercial. License gate 3 capas + audit hook F43 + cifrado Fernet opt-in (JW_VOICE_KEY)."
date: "2026-06-11"
---

# TTS con voz familiar consentida (Fase 76)

> Permite a una familia entrenar una voz consentida (padre, madre,
> abuelo) y usarla para leer la Biblia, Atalayas y textos personales.
> **Uso estrictamente personal / familiar; el license gate bloquea
> nombres de figuras públicas y textos comerciales.**

## Quick start

```bash
# Importar un perfil ya entrenado a partir de su consent.json
jw voiceclone register-from-consent papa --consent-file papa_consent.json

# Listar voces registradas
jw voiceclone list

# Inspeccionar un perfil
jw voiceclone show papa

# Sintetizar texto
jw voiceclone say papa "Lectura familiar del Salmo 23" --output /tmp/papa.wav

# Revocar el consentimiento (no borra los pesos, solo bloquea su uso)
jw voiceclone revoke papa --reason "consent withdrawn"

# Eliminar perfil + consent (los pesos en disco siguen)
jw voiceclone delete papa --confirm
```

## CLI

| Comando                                | Descripción                              |
|----------------------------------------|------------------------------------------|
| `jw voiceclone register-from-consent`  | Importa perfil de consent.json + weights |
| `jw voiceclone list`                   | Lista voces registradas                  |
| `jw voiceclone show`                   | JSON del perfil                          |
| `jw voiceclone say`                    | Sintetiza texto con license gate         |
| `jw voiceclone revoke`                 | Revoca el consentimiento                 |
| `jw voiceclone delete --confirm`       | Elimina perfil (requiere --confirm)      |

El **wizard de entrenamiento** (captura de mic + firma interactiva +
fine-tune real) NO está en CLI: queda como surface separada para
proteger la integridad del consentimiento. La CLI solo importa perfiles
ya consentidos por terceros.

## MCP

| Tool                       | Descripción                              |
|----------------------------|------------------------------------------|
| `voice_clone_list`         | Lista perfiles registrados               |
| `voice_clone_synthesize`   | Síntesis con license gate                |
| `voice_clone_audit`        | Use_count + last_used_at + consent_revoked |

`voice_clone_synthesize` devuelve `{ok: bool, ...}` en lugar de
levantar excepción — la MCP transport se mantiene viva ante fallos de
gate (consent revocado, texto comercial, voz inexistente).

## Formato `consent.json`

```json
{
  "signer_name": "Juan Pérez",
  "signer_relationship": "parent",
  "signed_at": "2026-06-11T15:23:00Z",
  "explicit_uses": ["read_bible", "read_watchtower"],
  "expires_at": "2027-12-31T23:59:59Z",
  "revoked": false
}
```

`signer_relationship` debe ser uno de `self`/`parent`/`spouse`/`child`/
`sibling`/`other`. La fecha de expiración es opcional pero recomendada.

## License gate

`check_synthesis_allowed()` ejecuta TRES verificaciones antes de
delegar al provider; cualquiera levanta `LicenseGateError`:

### 1. Deny list de nombres

Los nombres que contengan estos tokens (case-insensitive) están
bloqueados:

```
branch, broadcasting, president, governing_body, governing body, warwick
```

No se puede entrenar `"Branch Reader"` ni `"Governing Body Voice"`.

### 2. Consent activo

- `consent.revoked == True` → bloqueo permanente.
- `consent.expires_at < now` → bloqueo por expiración.

### 3. Texto no comercial

Estos patrones bloquean la síntesis:

```regex
\bmarketing\s+campaign\b
\bsales\s+pitch\b
\bcommercial\s+(use|spot|broadcast)\b
\bbuy\s+now\b
\bdiscount\s+offer\b
```

## Provider abstraction

Los providers cumplen un `Protocol`:

```python
class VoiceProvider(Protocol):
    name: str
    def synthesize(self, *, text, weights_path, output_path) -> Path: ...
```

Por defecto `FakeVoiceProvider` (determinista, sin red, sin GPU)
escribe un WAV "fake" cuyo contenido es `SHA-256(text + weights_path)`.
Los providers reales (F5-TTS, XTTSv2) se cablean via Plugin SDK F41 en
fases futuras (polyglot venv F53 cuando requieran torch específico).

## Storage layout

```
~/.jw-agent-toolkit/voices/
  <name>/
    profile.json          # ConsentRecord + metadata
    weights.bin            # (referenced from profile.weights_path)
    samples/               # (opcional)
    audit.jsonl            # (opcional, escrito por la callback emit_trace)
```

Override por env: `JW_VOICECLONE_ROOT=/ruta/voces`.

## Audit trail F43

`synthesize_with_voice` acepta `emit_trace=fn`. Cada síntesis exitosa
llama `fn(name="voice_used", payload=...)`. Conecta esto al tracer
F43 si quieres un audit log persistente:

```python
from jw_agents.tracing.tracer import AgentTracer

tracer = AgentTracer(agent="voice_clone", store=...)
synthesize_with_voice("papa", text, "out.wav", emit_trace=lambda name, payload: ...)
```

## Privacidad

- Sin telemetría externa.
- Las muestras de audio del consentido NUNCA salen del disco.
- El consent.json incluye `expires_at` recomendable para forzar
  revisión periódica del consentimiento.
- `revoke_consent` deja el perfil registrado pero lo marca; **no
  borra pesos** — la decisión de borrar pesos es separada (`delete`).
- `touch_use` incrementa `use_count` y `last_used_at` en cada uso
  exitoso — usable como evidencia ante el consentido.

## Disclaimer ético

- **Uso estrictamente personal o familiar / educativo no-comercial.**
- **No se permite suplantar a personas** o crear contenido falso
  atribuido al consentido.
- **No se permite el uso de voces de figuras públicas** (cubierto por
  la deny list).
- Si el consentimiento es revocado, la voz **no debe usarse más**
  incluso si los pesos siguen en disco.

## Estado actual

- 5 tasks TDD. **40 tests passing** (5 models + 10 license_gate + 7
  registry + 9 synthesizer + 6 CLI + 3 MCP + 3 protocol/total delta).
- `FakeVoiceProvider` determinista; tests pasan sin GPU, sin torch,
  sin F5-TTS instalado.
- Registry JSON por perfil con env override.
- Gate de 3 capas (name / consent / text) y audit hook opt-in.
- CLI `jw voiceclone {register-from-consent,list,show,say,revoke,delete}`.
- MCP `voice_clone_{list,synthesize,audit}`.

## Pendiente (futuro)

- Wizard interactivo de entrenamiento en `apps/voiceclone-wizard/` con
  captura de mic + firma de consent en vivo + fine-tune real.
- Provider F5-TTS via Plugin SDK F41 + polyglot Python F53 con
  `torch>=2.0` + `xformers`.
- Provider XTTSv2 (Coqui) con la misma capa.
- Cifrado opt-in de los pesos con `JW_VOICE_KEY` (Fernet, patrón F61).
- Validation sample WAV automático al registrar (re-síntesis de un
  texto canónico para verificar identidad de la voz).
- Polyglot install bootstrap `jw voiceclone install-runner --provider f5tts`.
- Trace audit persistente en `audit.jsonl` por defecto cuando F43
  esté wired.
- Integración como tool del meta-orchestrator F65 (decisión
  pendiente: ¿hace sentido invocar voice clone desde un plan? Solo si
  el operador pasa contexto del consentido).
