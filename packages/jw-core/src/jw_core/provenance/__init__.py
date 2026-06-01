"""Content provenance — Layer 2 fidelity tracking.

Answers: "is the text my agent used still the same as what's live on
wol.jw.org right now?". Complements `citations.validator` (Fase 23 — L0/L1:
URL resolves, doc_id in catalog) and `nli` (Fase 39 — L3: entailment).
"""

from __future__ import annotations

from jw_core.provenance.errors import (
    MissingProvenanceError,
    ProvenanceError,
    ProvenanceFetchError,
)
from jw_core.provenance.hashing import canonicalize_text, content_sha256
from jw_core.provenance.models import (
    ProvenanceRecord,
    ProvenanceReport,
    ProvenanceVerdict,
)
from jw_core.provenance.propagation import stamp_citation, stamp_finding_text
from jw_core.provenance.validator import ProvenanceValidator

__all__ = [
    "MissingProvenanceError",
    "ProvenanceError",
    "ProvenanceFetchError",
    "ProvenanceRecord",
    "ProvenanceReport",
    "ProvenanceValidator",
    "ProvenanceVerdict",
    "canonicalize_text",
    "content_sha256",
    "stamp_citation",
    "stamp_finding_text",
]
