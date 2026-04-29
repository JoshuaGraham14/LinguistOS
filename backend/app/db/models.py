"""SQLAlchemy models for users, workspaces, vocab, and practice logs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
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
    __table_args__ = (Index("ix_vocab_workspace_word", "workspace_id", "word"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"), nullable=False, index=True
    )
    word: Mapped[str] = mapped_column(String(255), nullable=False)
    translation: Mapped[str] = mapped_column(String(255), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    learned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    workspace: Mapped[Workspace] = relationship(back_populates="vocab_items")


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
