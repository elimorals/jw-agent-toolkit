"""Personalization + memory + accessibility (Module 12)."""

from jw_core.personalization.accessibility import (
    easy_read,
    high_contrast_palette,
    increase_legibility,
)
from jw_core.personalization.memory import (
    MemoryEntry,
    SessionMemory,
    load_memory_for_user,
    save_memory_for_user,
)
from jw_core.personalization.profile import (
    UserProfile,
    UserProfileStore,
    default_profile,
)
from jw_core.personalization.tone import (
    TONE_TEMPLATES,
    adjust_tone,
)

__all__ = [
    "MemoryEntry",
    "SessionMemory",
    "TONE_TEMPLATES",
    "UserProfile",
    "UserProfileStore",
    "adjust_tone",
    "default_profile",
    "easy_read",
    "high_contrast_palette",
    "increase_legibility",
    "load_memory_for_user",
    "save_memory_for_user",
]
