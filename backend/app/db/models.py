"""SQLAlchemy models for users, workspaces, vocab, and practice logs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (Index("ix_workspace_owner_name", "owner_id", "name", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    emoji_or_flag: Mapped[str] = mapped_column(String(16), nullable=False, default="🌐")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    owner: Mapped[User] = relationship(back_populates="workspaces")
    vocab_items: Mapped[list["Vocab"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    practice_logs: Mapped[list["PracticeLog"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Vocab(Base):
    __tablename__ = "vocab"
    __table_args__ = (
        Index("ix_vocab_workspace_word", "workspace_id", "word"),
        Index("ix_vocab_workspace_lemma", "workspace_id", "lemma"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )

    # Legacy fields (kept until adapter retirement, see implementation_spec.md §5.3).
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    translation: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    learned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Canonical word fields (LOS-101).
    lemma: Mapped[str | None] = mapped_column(String(255), nullable=True)
    surface_form: Mapped[str | None] = mapped_column(String(255), nullable=True)
    surface_forms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    pos: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cefr: Mapped[str | None] = mapped_column(String(8), nullable=True)
    frequency_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    conjugation_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    morph_features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ipa: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gloss_primary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    glosses: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workspace: Mapped[Workspace] = relationship(back_populates="vocab_items")
    mastery: Mapped["WordMastery | None"] = relationship(
        back_populates="vocab", uselist=False, cascade="all, delete-orphan"
    )
    enrichment_jobs: Mapped[list["EnrichmentJob"]] = relationship(
        back_populates="vocab", cascade="all, delete-orphan"
    )


class WordMastery(Base):
    """Per-vocab mastery state shared across all review surfaces (LOS-901)."""

    __tablename__ = "word_mastery"
    __table_args__ = (
        Index("ix_mastery_workspace_due", "workspace_id", "next_due"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    vocab_id: Mapped[int] = mapped_column(
        ForeignKey("vocab.id"), nullable=False, unique=True, index=True
    )

    strength: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    box: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_due: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    vocab: Mapped[Vocab] = relationship(back_populates="mastery")


class EnrichmentJob(Base):
    """Async enrichment work for a captured word (LOS-106)."""

    __tablename__ = "enrichment_jobs"
    __table_args__ = (
        Index("ix_enrichment_vocab_status", "vocab_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vocab_id: Mapped[int] = mapped_column(
        ForeignKey("vocab.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    requested_fields: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    vocab: Mapped[Vocab] = relationship(back_populates="enrichment_jobs")


class Sentence(Base):
    """Persisted sentence linked to vocab atoms (LOS-501)."""

    __tablename__ = "sentences"
    __table_args__ = (Index("ix_sentence_workspace", "workspace_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="generated", nullable=False)
    source_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    links: Mapped[list["SentenceWordLink"]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan", order_by="SentenceWordLink.position"
    )


class SentenceWordLink(Base):
    """Token-level link between a sentence and a vocab atom (LOS-501)."""

    __tablename__ = "sentence_word_links"
    __table_args__ = (
        Index("ix_link_sentence_position", "sentence_id", "position"),
        Index("ix_link_vocab", "vocab_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sentence_id: Mapped[int] = mapped_column(
        ForeignKey("sentences.id"), nullable=False, index=True
    )
    vocab_id: Mapped[int] = mapped_column(
        ForeignKey("vocab.id"), nullable=False, index=True
    )
    surface_token: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="target", nullable=False)

    sentence: Mapped[Sentence] = relationship(back_populates="links")


class PracticeLog(Base):
    __tablename__ = "practice_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    vocab_id: Mapped[int | None] = mapped_column(ForeignKey("vocab.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False, default="practice")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="practice_logs")
