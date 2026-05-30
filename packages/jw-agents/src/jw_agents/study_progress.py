"""StudentProgress — local-only encryptable store for the study-book lifecycle.

VISION rule: "No tracker de hermanos sin opt-in". This IS a tracker, so:
  - First-run requires an explicit y/N consent + passphrase.
  - student_id is an alias (regex `^[a-z0-9_-]{3,32}$`), never a real name.
  - Free-text `notes` are Fernet-encrypted at rest with a key derived
    from the user's passphrase (PBKDF2-HMAC-SHA256, persistent salt).
  - Storage is ON DEVICE only. No sync. No telemetry.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class LessonStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED   = "completed"
    SKIPPED     = "skipped"


class GoalKind(str, Enum):
    ATTEND_MEETINGS         = "attend_meetings"
    DROP_ADDICTION_SMOKING  = "drop_addiction_smoking"
    DROP_ADDICTION_ALCOHOL  = "drop_addiction_alcohol"
    DROP_ADDICTION_OTHER    = "drop_addiction_other"
    PRAY_DAILY              = "pray_daily"
    FAMILY_WORSHIP          = "family_worship"
    BAPTISM                 = "baptism"
    OTHER                   = "other"


class StudentGoal(BaseModel):
    kind: GoalKind
    note: str = ""
    set_at_iso: str
    achieved_at_iso: str | None = None
    target_iso: str | None = None


class LessonRow(BaseModel):
    student_id: str = Field(pattern=r"^[a-z0-9_-]{3,32}$")
    book_pub: str
    lesson: int = Field(ge=1)
    status: LessonStatus = LessonStatus.NOT_STARTED
    notes: str = ""
    goals: list[StudentGoal] = []
    started_at_iso: str | None = None
    completed_at_iso: str | None = None
    attended_meetings_count: int = 0
    baptism_target_iso: str | None = None
    updated_at_iso: str
