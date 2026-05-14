"""Research models: constraint sets, experiments, sentences, evaluations, metrics."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from research.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Benchmark(Base):
    """A named, reusable collection of constraint sets for repeatable experiments."""

    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    constraint_sets: Mapped[list["ConstraintSet"]] = relationship(
        back_populates="benchmark", cascade="all, delete-orphan"
    )
    experiments: Mapped[list["Experiment"]] = relationship(
        back_populates="benchmark"
    )


class ConstraintSet(Base):
    """A bundle of morpho-syntactic constraints (e.g. comer + past + 1pl)."""

    __tablename__ = "constraint_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int] = mapped_column(
        ForeignKey("benchmarks.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    tense: Mapped[str] = mapped_column(String(64), nullable=False)
    person: Mapped[str] = mapped_column(String(16), nullable=False)
    number: Mapped[str] = mapped_column(String(16), nullable=False)
    target_language: Mapped[str] = mapped_column(String(16), nullable=False, default="es")
    translation: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    cefr_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    extra_constraints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    benchmark: Mapped["Benchmark"] = relationship(back_populates="constraint_sets")
    sentences: Mapped[list["GeneratedSentence"]] = relationship(
        back_populates="constraint_set", cascade="all, delete-orphan"
    )


class Experiment(Base):
    """One experiment run: a method + config applied to a set of constraints."""

    __tablename__ = "experiments"
    __table_args__ = (Index("ix_experiment_status", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark_id: Mapped[int | None] = mapped_column(
        ForeignKey("benchmarks.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    samples_per_case: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    benchmark: Mapped["Benchmark | None"] = relationship(back_populates="experiments")
    sentences: Mapped[list["GeneratedSentence"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["ExperimentMetric"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class GeneratedSentence(Base):
    """A single sentence produced by a generator for a specific constraint set."""

    __tablename__ = "generated_sentences"
    __table_args__ = (
        Index("ix_sentence_experiment", "experiment_id"),
        Index("ix_sentence_constraint_set", "constraint_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    constraint_set_id: Mapped[int] = mapped_column(
        ForeignKey("constraint_sets.id", ondelete="CASCADE"), nullable=False
    )
    sentence: Mapped[str] = mapped_column(Text, nullable=False)
    translation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sample_index: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    experiment: Mapped[Experiment] = relationship(back_populates="sentences")
    constraint_set: Mapped[ConstraintSet] = relationship(back_populates="sentences")
    evaluations: Mapped[list[SentenceEvaluation]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )


class SentenceEvaluation(Base):
    """A score assigned to a generated sentence by a specific evaluator."""

    __tablename__ = "sentence_evaluations"
    __table_args__ = (
        Index("ix_evaluation_sentence", "sentence_id"),
        Index("ix_evaluation_evaluator", "evaluator_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sentence_id: Mapped[int] = mapped_column(
        ForeignKey("generated_sentences.id", ondelete="CASCADE"), nullable=False
    )
    evaluator_name: Mapped[str] = mapped_column(String(128), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    sentence: Mapped[GeneratedSentence] = relationship(back_populates="evaluations")


class ExperimentMetric(Base):
    """Experiment-level or constraint-set-scoped aggregate / distribution metric."""

    __tablename__ = "experiment_metrics"
    __table_args__ = (
        Index("ix_metric_experiment", "experiment_id"),
        Index("ix_metric_scope_cs", "scope", "constraint_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    experiment_id: Mapped[int] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False)
    constraint_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("constraint_sets.id", ondelete="CASCADE"), nullable=True
    )
    breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    experiment: Mapped[Experiment] = relationship(back_populates="metrics")
