"""Pydantic schemas for request/response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

LanguageCode = Literal["es", "he", "fr"]
VocabTag = Literal["noun", "verb", "adjective", "adverb", "preposition", "other"]


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


class VocabCreate(BaseModel):
    workspace_id: int
    word: str = Field(min_length=1, max_length=255)
    translation: str = Field(min_length=1, max_length=255)
    tags: list[VocabTag] = Field(default_factory=list)


class VocabUpdate(BaseModel):
    word: str | None = Field(default=None, min_length=1, max_length=255)
    translation: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[VocabTag] | None = None
    learned: bool | None = None


class VocabOut(BaseModel):
    id: int
    workspace_id: int
    word: str
    translation: str
    tags: list[VocabTag]
    learned: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class VocabListResponse(BaseModel):
    items: list[VocabOut]
