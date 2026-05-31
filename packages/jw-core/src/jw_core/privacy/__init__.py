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

try:  # optional import — only succeeds with [grammar-claude] extra
    from jw_core.privacy.anthropic_adapter import AnthropicAdapter, AnthropicAdapterError
except ImportError:  # pragma: no cover
    AnthropicAdapter = None  # type: ignore[assignment,misc]
    AnthropicAdapterError = RuntimeError  # type: ignore[assignment,misc]

__all__ = [
    "AnthropicAdapter",
    "AnthropicAdapterError",
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
