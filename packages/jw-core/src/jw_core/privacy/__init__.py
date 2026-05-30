"""Privacy + local-first primitives (Module 11)."""

from jw_core.privacy.encryption import (
    EncryptionError,
    FieldEncryptor,
    derive_key_from_password,
    generate_key,
)
from jw_core.privacy.ollama_adapter import (
    OllamaAdapter,
    OllamaError,
    ollama_available,
)
from jw_core.privacy.telemetry_audit import (
    TelemetryAuditResult,
    audit_telemetry_outflow,
    is_offline_mode,
)

__all__ = [
    "EncryptionError",
    "FieldEncryptor",
    "OllamaAdapter",
    "OllamaError",
    "TelemetryAuditResult",
    "audit_telemetry_outflow",
    "derive_key_from_password",
    "generate_key",
    "is_offline_mode",
    "ollama_available",
]
