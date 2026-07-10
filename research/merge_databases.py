"""Merge per-job SQLite run databases into the canonical research.db.

Cluster jobs can set ``RESEARCH_DB`` to an isolated file (e.g.
``research/runs/diagnostic_5a.db``). After they finish, this module copies
experiments and related rows into the main database, remapping foreign keys by
stable names rather than numeric ids.

Usage:
    python -m research.merge_databases research/runs/d5a.db research/runs/d5b.db
    python -m research.merge_databases --target research/research.db research/runs/*.db
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session, joinedload, sessionmaker

from research.benchmarks.loader import load_benchmark
from research.db.database import create_engine_for_path, get_db_path, init_db
from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    MethodConfig,
    SentenceEvaluation,
)
from research.methods.loader import load_method_config_by_name


@dataclass
class MergeStats:
    experiments_merged: int = 0
    sentences_added: int = 0
    evaluations_added: int = 0
    metrics_added: int = 0
    skipped_experiments: list[str] = field(default_factory=list)


def _session_for(path: Path) -> Session:
    engine = create_engine_for_path(path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


_RESEARCH_DIR = Path(__file__).resolve().parent
_BENCHMARKS_DIR = _RESEARCH_DIR / "benchmarks"


def _ensure_benchmark(target: Session, source_bm: Benchmark) -> Benchmark:
    row = target.query(Benchmark).filter_by(name=source_bm.name).first()
    if row is None:
        yaml_path = _BENCHMARKS_DIR / f"{source_bm.name}.yaml"
        if yaml_path.exists():
            return load_benchmark(target, yaml_path)
        row = Benchmark(
            name=source_bm.name,
            language=source_bm.language,
            description=source_bm.description,
            mock_only=source_bm.mock_only,
            created_at=source_bm.created_at,
        )
        target.add(row)
        target.flush()
    elif not row.constraint_sets:
        yaml_path = _BENCHMARKS_DIR / f"{source_bm.name}.yaml"
        if yaml_path.exists():
            return load_benchmark(target, yaml_path)
    return row


def _ensure_method_config(target: Session, source_mc: MethodConfig) -> MethodConfig:
    row = target.query(MethodConfig).filter_by(name=source_mc.name).first()
    if row is not None:
        return row
    return load_method_config_by_name(target, source_mc.name)


def _map_constraint_set(
    target: Session,
    *,
    target_benchmark_id: int,
    source_cs: ConstraintSet,
) -> ConstraintSet:
    candidates = (
        target.query(ConstraintSet)
        .filter_by(benchmark_id=target_benchmark_id, keyword=source_cs.keyword)
        .all()
    )
    for row in candidates:
        if row.constraints == source_cs.constraints and row.translation == source_cs.translation:
            return row
    raise ValueError(
        f"No matching constraint set in target DB for keyword={source_cs.keyword!r} "
        f"constraints={source_cs.constraints!r}"
    )


def _ensure_experiment(
    target: Session,
    *,
    source_exp: Experiment,
    target_benchmark: Benchmark,
    target_method: MethodConfig,
) -> Experiment:
    row = target.query(Experiment).filter_by(name=source_exp.name).first()
    if row is not None:
        return row
    row = Experiment(
        benchmark_id=target_benchmark.id,
        method_config_id=target_method.id,
        name=source_exp.name,
        status=source_exp.status,
        created_at=source_exp.created_at,
        completed_at=source_exp.completed_at,
    )
    target.add(row)
    target.flush()
    return row


def merge_database(source_path: Path, target_path: Path) -> MergeStats:
    """Merge all experiments from *source_path* into *target_path*."""
    source_path = source_path.resolve()
    target_path = target_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    init_db(target_path)
    stats = MergeStats()
    source = _session_for(source_path)
    target = _session_for(target_path)

    try:
        source_experiments = (
            source.query(Experiment)
            .options(
                joinedload(Experiment.benchmark).joinedload(Benchmark.constraint_sets),
                joinedload(Experiment.method_config),
            )
            .order_by(Experiment.id)
            .all()
        )
        for source_exp in source_experiments:
            if source_exp.benchmark is None or source_exp.method_config is None:
                stats.skipped_experiments.append(source_exp.name)
                continue

            target_bm = _ensure_benchmark(target, source_exp.benchmark)
            target_mc = _ensure_method_config(target, source_exp.method_config)
            target_exp = _ensure_experiment(
                target,
                source_exp=source_exp,
                target_benchmark=target_bm,
                target_method=target_mc,
            )

            cs_map: dict[int, ConstraintSet] = {}

            def _target_cs(source_cs_id: int) -> ConstraintSet:
                if source_cs_id not in cs_map:
                    source_cs = source.get(ConstraintSet, source_cs_id)
                    if source_cs is None:
                        raise ValueError(f"Missing constraint set id={source_cs_id} in source DB")
                    cs_map[source_cs_id] = _map_constraint_set(
                        target,
                        target_benchmark_id=target_bm.id,
                        source_cs=source_cs,
                    )
                return cs_map[source_cs_id]

            existing_keys = {
                (row.constraint_set_id, row.sample_index)
                for row in target.query(GeneratedSentence)
                .filter_by(experiment_id=target_exp.id)
                .all()
            }

            sentence_map: dict[int, GeneratedSentence] = {}
            for source_sent in (
                source.query(GeneratedSentence)
                .filter_by(experiment_id=source_exp.id)
                .order_by(GeneratedSentence.id)
                .all()
            ):
                target_cs = _target_cs(source_sent.constraint_set_id)
                key = (target_cs.id, source_sent.sample_index)
                if key in existing_keys:
                    existing = (
                        target.query(GeneratedSentence)
                        .filter_by(
                            experiment_id=target_exp.id,
                            constraint_set_id=target_cs.id,
                            sample_index=source_sent.sample_index,
                        )
                        .one()
                    )
                    sentence_map[source_sent.id] = existing
                    continue

                target_sent = GeneratedSentence(
                    experiment_id=target_exp.id,
                    constraint_set_id=target_cs.id,
                    sentence=source_sent.sentence,
                    translation=source_sent.translation,
                    sample_index=source_sent.sample_index,
                    generation_meta=source_sent.generation_meta,
                    created_at=source_sent.created_at,
                )
                target.add(target_sent)
                target.flush()
                existing_keys.add(key)
                sentence_map[source_sent.id] = target_sent
                stats.sentences_added += 1

            existing_eval_keys = {
                (row.sentence_id, row.evaluator_name)
                for row in target.query(SentenceEvaluation)
                .join(GeneratedSentence)
                .filter(GeneratedSentence.experiment_id == target_exp.id)
                .all()
            }
            for source_eval in (
                source.query(SentenceEvaluation)
                .join(GeneratedSentence)
                .filter(GeneratedSentence.experiment_id == source_exp.id)
                .order_by(SentenceEvaluation.id)
                .all()
            ):
                target_sent = sentence_map.get(source_eval.sentence_id)
                if target_sent is None:
                    continue
                key = (target_sent.id, source_eval.evaluator_name)
                if key in existing_eval_keys:
                    continue
                target.add(
                    SentenceEvaluation(
                        sentence_id=target_sent.id,
                        evaluator_name=source_eval.evaluator_name,
                        score=source_eval.score,
                        details=source_eval.details,
                        created_at=source_eval.created_at,
                    )
                )
                stats.evaluations_added += 1

            existing_metric_keys = {
                (row.metric_name, row.scope, row.constraint_set_id)
                for row in target.query(ExperimentMetric)
                .filter_by(experiment_id=target_exp.id)
                .all()
            }
            for source_metric in (
                source.query(ExperimentMetric)
                .filter_by(experiment_id=source_exp.id)
                .order_by(ExperimentMetric.id)
                .all()
            ):
                target_cs_id = None
                if source_metric.constraint_set_id is not None:
                    target_cs_id = _target_cs(source_metric.constraint_set_id).id
                key = (source_metric.metric_name, source_metric.scope, target_cs_id)
                if key in existing_metric_keys:
                    continue
                target.add(
                    ExperimentMetric(
                        experiment_id=target_exp.id,
                        metric_name=source_metric.metric_name,
                        value=source_metric.value,
                        scope=source_metric.scope,
                        constraint_set_id=target_cs_id,
                        breakdown=source_metric.breakdown,
                        created_at=source_metric.created_at,
                    )
                )
                stats.metrics_added += 1

            target_exp.status = source_exp.status
            target_exp.completed_at = source_exp.completed_at
            stats.experiments_merged += 1

        target.commit()
        return stats
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge run SQLite DBs into research.db")
    parser.add_argument(
        "sources",
        nargs="+",
        type=Path,
        help="Per-job database files to merge",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Canonical database (default: research/research.db)",
    )
    args = parser.parse_args()

    target_path = args.target if args.target is not None else get_db_path()
    total = MergeStats()
    for source in args.sources:
        print(f"Merging {source} -> {target_path}")
        stats = merge_database(source, target_path)
        total.experiments_merged += stats.experiments_merged
        total.sentences_added += stats.sentences_added
        total.evaluations_added += stats.evaluations_added
        total.metrics_added += stats.metrics_added
        total.skipped_experiments.extend(stats.skipped_experiments)
        print(
            f"  +{stats.experiments_merged} experiments, "
            f"+{stats.sentences_added} sentences, "
            f"+{stats.evaluations_added} evals, "
            f"+{stats.metrics_added} metrics"
        )

    print(
        f"Done: {total.experiments_merged} experiments, "
        f"{total.sentences_added} sentences, "
        f"{total.evaluations_added} evals, "
        f"{total.metrics_added} metrics"
    )
    if total.skipped_experiments:
        print("Skipped:", ", ".join(total.skipped_experiments))


if __name__ == "__main__":
    main()
