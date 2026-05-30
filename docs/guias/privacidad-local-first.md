# Privacidad y local-first (Módulo 11 — Fase 18)

> Cubre el ítem #11 de [VISION.md](../VISION.md): modelo Ollama local opcional, cifrado de notas/RAG, auditoría que nada salga del dispositivo sin opt-in.

## Pilar 1 — Cifrado de campo

`jw_core/privacy/encryption.py` ofrece `FieldEncryptor` que envuelve `cryptography.Fernet`:

```python
from jw_core.privacy import FieldEncryptor, generate_key, derive_key_from_password

key = generate_key()                            # urlsafe base64, 32-byte
# o reproducible a partir de passphrase:
key = derive_key_from_password("mi-secreto")

enc = FieldEncryptor(key=key)
token = enc.encrypt("contenido sensible")
assert enc.decrypt(token) == "contenido sensible"
```

**Key sources (orden de preferencia):**
1. `FieldEncryptor(key=...)` explícito.
2. Env var `JW_PRIVACY_KEY=<urlsafe-b64>`.
3. None → modo no-op con warning. El store de notas/RAG funciona igual; el usuario decide cuándo activar.

**Para qué se integra:**
- Wrappear `PersonalNoteStore` (Módulo 4) y `RevisitStore` (Módulo 2) con `FieldEncryptor` en columnas `body`, `notes`. Patrón típico: `INSERT (..., enc.encrypt(body), ...)`, `SELECT (... enc.decrypt(body))`.
- RAG store: cifrar los `text` antes de persistir y descifrar al rehidratar (post-busqueda BM25 se queda en memoria).

## Pilar 2 — Auditoría de telemetría

`audit_telemetry_outflow()` revisa al runtime:
- `JW_TELEMETRY_ENABLED` debe estar **unset** o `0`.
- Tercera-parte vars como `OTEL_EXPORTER_OTLP_ENDPOINT`, `DATADOG_API_KEY`, `NEW_RELIC_LICENSE_KEY` no deben estar configuradas.

```python
from jw_core.privacy import audit_telemetry_outflow, is_offline_mode

report = audit_telemetry_outflow()
print("offline mode:", report.is_offline)
for f in report.findings:
    print(f["severity"], "—", f["key"], ":", f["message"])
for r in report.recommendations:
    print("→", r)
```

**CLI candidate (lo expondremos como `jw privacy audit`):**
```
$ jw privacy audit
offline mode: True
info — JW_TELEMETRY_ENABLED: OK
info — telemetry.enabled: False
```

## Pilar 3 — Ollama opcional

`OllamaAdapter` habla con un servidor Ollama local en `http://localhost:11434` (override `JW_OLLAMA_HOST`):

```python
import asyncio
from jw_core.privacy import OllamaAdapter

adapter = OllamaAdapter(model="llama3.1")
if asyncio.run(adapter.is_available()):
    text = asyncio.run(adapter.generate("Summarise: ..."))
```

**Cuando Ollama está disponible**, cualquier agente puede usarlo en lugar de Claude para una síntesis local — el contrato (`generate(prompt) -> str`) es el mismo. Ideal para territorios donde el coste o la privacidad descartan APIs cloud.

**Streaming:**
```python
async for chunk in adapter.generate_stream("explica el versículo 1 de Génesis"):
    print(chunk, end="")
```

## Verificación

`packages/jw-core/tests/test_privacy_module.py` — 8 tests:

- Modo no-op cuando no hay key.
- Roundtrip encrypt → decrypt con `cryptography` cuando disponible.
- `derive_key_from_password` determinista por (password, salt fija) y diferente entre passwords.
- `is_offline_mode` true por default, false con env var.
- `audit_telemetry_outflow` detecta keys de terceros y los reporta en recomendaciones.

```bash
uv run pytest packages/jw-core/tests/test_privacy_module.py -v
```

## Política

VISION.md prohíbe almacenamiento centralizado de notas sin cifrado E2E. Este módulo provee las primitivas; la **política** está en los stores:

- Por defecto cleartext (más fácil de bootstrap).
- Cuando `JW_PRIVACY_KEY` está set, todos los stores deben pasar por `FieldEncryptor`.

Sigue siendo on-device-only; cualquier sync (Módulo futuro) debe usar la misma key derivada para preservar E2E.

## Pendiente

- Wrappear `PersonalNoteStore` y `RevisitStore` con `FieldEncryptor` cuando hay key.
- Comando CLI `jw privacy audit` + `jw privacy key:generate`.
- Sync E2E multi-dispositivo con clave compartida via QR.
