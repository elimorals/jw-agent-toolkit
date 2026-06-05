"""SpeakerNameMapper: cosine similarity over enrolled voiceprints.

Toma un embedding de voz (extraído del audio diarizado por el provider
ASR, p.ej. whisperx en F64.8) y devuelve el nombre real más probable, o
`None` si la similitud cae bajo el umbral configurable.

Convención de signo: cosine similarity ∈ [-1, 1]; default threshold 0.75
es un balance razonable para embeddings ECAPA-TDNN / pyannote-segmentation.
"""

from __future__ import annotations

import numpy as np

from jw_core.audio.speakers.voiceprint_store import VoiceprintStore


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class SpeakerNameMapper:
    """Identify a speaker by matching a query embedding against enrollments.

    Parameters
    ----------
    store : VoiceprintStore
        Backing store (sqlite). The mapper reads `list_all()` per call;
        callers transcribing many segments should cache the result if
        latency matters.
    similarity_threshold : float
        Min cosine similarity to accept a match. Below → `identify()`
        returns `None` so the caller can fall back to the anonymous
        `SPEAKER_xx` label.
    """

    def __init__(
        self,
        *,
        store: VoiceprintStore,
        similarity_threshold: float = 0.75,
    ) -> None:
        self.store = store
        self.similarity_threshold = similarity_threshold

    def identify(self, embedding: np.ndarray) -> str | None:
        """Return the closest enrolled name, or None if below threshold."""
        best_name: str | None = None
        best_score = -1.0
        for vp in self.store.list_all():
            score = _cosine_similarity(embedding, vp.embedding)
            if score > best_score:
                best_score = score
                best_name = vp.name
        if best_score < self.similarity_threshold:
            return None
        return best_name
