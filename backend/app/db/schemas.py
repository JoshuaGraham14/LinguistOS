"""Pydantic schemas for request/response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LanguageCode = Literal["es", "he", "fr"]
VocabTag = Literal["noun", "verb", "adjective", "adverb", "preposition", "other"]
MasteryOutcome = Literal["correct", "incorrect", "skipped", "hinted"]
EnrichmentStatus = Literal["pending", "done", "failed"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    language: LanguageCode
    emoji_or_flag: str = Field(default="🌐", min_length=1, max_length=16)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class WorkspaceOut(BaseModel):
    id: int
    owner_id: int
    name: str
    language: LanguageCode
    emoji_or_flag: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MasteryOut(BaseModel):
    strength: float
    box: int
    last_reviewed_at: datetime | None
    next_due: datetime | None
    streak: int
    failures: int
    successes: int

    model_config = {"from_attributes": True}


class MasteryEvent(BaseModel):
    outcome: MasteryOutcome
    source: str = Field(default="practice", max_length=64)


class VocabCreate(BaseModel):
    """Create payload accepting both legacy and canonical shapes.

    Legacy: ``{ word, translation }`` keeps existing clients working.
    Canonical (LOS-106): ``{ surface_form }`` only is required; everything
    else is optional and may be filled by enrichment later.
    """

    workspace_id: int
    # Legacy required-pair (kept optional so canonical-only clients pass).
    word: str | None = Field(default=None, min_length=1, max_length=255)
    translation: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[VocabTag] = Field(default_factory=list)

    # Canonical fields.
    surface_form: str | None = Field(default=None, min_length=1, max_length=255)
    lemma: str | None = Field(default=None, max_length=255)
    pos: str | None = Field(default=None, max_length=32)
    cefr: str | None = Field(default=None, max_length=8)
    frequency_rank: int | None = None
    gender: str | None = Field(default=None, max_length=8)
    conjugation_class: str | None = Field(default=None, max_length=32)
    morph_features: dict[str, Any] | None = None
    ipa: str | None = Field(default=None, max_length=128)
    audio_url: str | None = Field(default=None, max_length=512)
    image_url: str | None = Field(default=None, max_length=512)
    gloss_primary: str | None = Field(default=None, max_length=255)
    glosses: list[str] | None = None
    notes: str | None = None


class VocabUpdate(BaseModel):
    word: str | None = Field(default=None, min_length=1, max_length=255)
    translation: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[VocabTag] | None = None
    learned: bool | None = None

    surface_form: str | None = Field(default=None, max_length=255)
    lemma: str | None = Field(default=None, max_length=255)
    pos: str | None = Field(default=None, max_length=32)
    cefr: str | None = Field(default=None, max_length=8)
    frequency_rank: int | None = None
    gender: str | None = Field(default=None, max_length=8)
    conjugation_class: str | None = Field(default=None, max_length=32)
    morph_features: dict[str, Any] | None = None
    ipa: str | None = Field(default=None, max_length=128)
    audio_url: str | None = Field(default=None, max_length=512)
    image_url: str | None = Field(default=None, max_length=512)
    gloss_primary: str | None = Field(default=None, max_length=255)
    glosses: list[str] | None = None
    notes: str | None = None


class VocabOut(BaseModel):
    id: int
    workspace_id: int
    word: str
    translation: str
    tags: list[VocabTag]
    learned: bool
    created_at: datetime

    lemma: str | None = None
    surface_form: str | None = None
    surface_forms: list[str] = Field(default_factory=list)
    pos: str | None = None
    cefr: str | None = None
    frequency_rank: int | None = None
    gender: str | None = None
    conjugation_class: str | None = None
    morph_features: dict[str, Any] | None = None
    ipa: str | None = None
    audio_url: str | None = None
    image_url: str | None = None
    gloss_primary: str | None = None
    glosses: list[str] = Field(default_factory=list)
    notes: str | None = None
    last_seen_at: datetime | None = None

    mastery: MasteryOut | None = None

    model_config = {"from_attributes": True}


class VocabListResponse(BaseModel):
    items: list[VocabOut]


class EnrichmentJobOut(BaseModel):
    id: int
    vocab_id: int
    status: EnrichmentStatus
    requested_fields: list[str]
    result: dict[str, Any] | None
    confidence: float | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class EnrichmentJobCreate(BaseModel):
    requested_fields: list[str] = Field(default_factory=list)
