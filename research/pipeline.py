"""Research experiment pipeline: generate, evaluate, and store metrics."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import joinedload

from research.benchmarks.loader import load_benchmark
from research.db.database import SessionLocal, init_db
from research.db.models import (
    Benchmark,
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    MethodConfig,
    SentenceEvaluation,
)
from research.evaluation.distribution import DEFAULT_GROUP_METRICS
from research.evaluation.distribution.base import BaseGroupMetric
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence import DEFAULT_EVALUATORS
from research.evaluation.sentence.base import BaseEvaluator
from research.fixtures.mock_outputs import get_mock_candidates
from research.generation import GENERATOR_REGISTRY
from research.generation.base import BaseGenerator
from research.methods.loader import load_method_config_by_name
from research.methods.run_config import MethodRunConfig

_RESEARCH_DIR = Path(__file__).resolve().parent
_BENCHMARKS_DIR = _RESEARCH_DIR / "benchmarks"


def _resolve_benchmark(session, name: str) -> Benchmark:
    """Load a benchmark by name — reads from YAML on first use, then cached in DB."""
    yaml_path = _BENCHMARKS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No benchmark YAML found at {yaml_path}")
    return load_benchmark(session, yaml_path)


def _resolve_method_config(session, name: str) -> MethodConfig:
    """Load a method preset by ``name`` (searches methods/baseline/, individual/, etc.)."""
    return load_method_config_by_name(session, name)


def _experiment_name(
    *,
    benchmark: Benchmark,
    method_config: MethodConfig,
    live: bool,
) -> str:
    """Unique, human-readable experiment id stored on ``experiments.name``."""
    mode = "live" if live else "mock"
    return f"{benchmark.name}__{method_config.name}__{mode}"


def _build_generator(run_config: MethodRunConfig, method_config: MethodConfig) -> BaseGenerator:
    """Instantiate a generator from a MethodConfig row."""
    cls = GENERATOR_REGISTRY.get(method_config.method)
    if cls is None:
        raise ValueError(
            f"Unknown generation method '{method_config.method}'. "
            f"Available: {', '.join(GENERATOR_REGISTRY)}"
        )
    return cls(
        model=run_config.model,
        temperature=run_config.temperature,
    )


def _resolved_length_from_sentence(sent: GeneratedSentence) -> str:
    """Band used for length evaluation (per-sentence when preset is random)."""
    meta = sent.generation_meta or {}
    return str(
        meta.get("resolved_sentence_length")
        or meta.get("sentence_length")
        or "short"
    )


def _clear_sentence_evaluations(session, experiment_id: int) -> int:
    """Remove sentence_evaluations for all sentences in an experiment."""
    sentence_ids = [
        row[0]
        for row in session.query(GeneratedSentence.id)
        .filter_by(experiment_id=experiment_id)
        .all()
    ]
    if not sentence_ids:
        return 0
    return session.query(SentenceEvaluation).filter(
        SentenceEvaluation.sentence_id.in_(sentence_ids)
    ).delete(synchronize_session="fetch")


def _evaluate_sentences(
    session,
    experiment: Experiment,
    evaluators: list[BaseEvaluator],
) -> int:
    """Run all evaluators against every sentence in the experiment.

    Idempotent per experiment: existing sentence_evaluations for this
    experiment's sentences are deleted before new rows are inserted.

    Returns the total number of evaluation rows created.
    """
    _clear_sentence_evaluations(session, experiment.id)

    sentences = (
        session.query(GeneratedSentence)
        .options(joinedload(GeneratedSentence.constraint_set))
        .filter_by(experiment_id=experiment.id)
        .all()
    )
    total = 0
    for sent in sentences:
        constraints = sent.constraint_set.to_constraints_dict()
        constraints["sentence_length"] = _resolved_length_from_sentence(sent)
        for evaluator in evaluators:
            result = evaluator.evaluate(
                sentence=sent.sentence,
                translation=sent.translation,
                constraints=constraints,
            )
            session.add(SentenceEvaluation(
                sentence_id=sent.id,
                evaluator_name=evaluator.name,
                score=result.score,
                details=result.details,
            ))
            total += 1
    session.commit()
    return total


def _compute_and_store_group_metrics(
    session,
    experiment: Experiment,
    group_metrics: list[BaseGroupMetric],
) -> int:
    """Run distribution-level metrics; write experiment_metrics only.

    Idempotent: existing rows for this experiment whose metric_name is in
    group_metrics are deleted before insert.
    """
    metric_names = [m.name for m in group_metrics]
    if metric_names:
        session.query(ExperimentMetric).filter(
            ExperimentMetric.experiment_id == experiment.id,
            ExperimentMetric.metric_name.in_(metric_names),
        ).delete(synchronize_session="fetch")

    sentences = (
        session.query(GeneratedSentence)
        .options(joinedload(GeneratedSentence.evaluations))
        .filter_by(experiment_id=experiment.id)
        .all()
    )
    if not sentences:
        return 0

    by_cs: dict[int, list[GeneratedSentence]] = defaultdict(list)
    for s in sentences:
        by_cs[s.constraint_set_id].append(s)

    inserted = 0
    for metric in group_metrics:
        if metric.scope == "constraint_set":
            for cs_id, group in by_cs.items():
                result = metric.compute(group)
                session.add(
                    ExperimentMetric(
                        experiment_id=experiment.id,
                        metric_name=metric.name,
                        value=result.value,
                        scope="constraint_set",
                        constraint_set_id=cs_id,
                        breakdown=result.details,
                    )
                )
                inserted += 1
        else:
            result = metric.compute(sentences)
            session.add(
                ExperimentMetric(
                    experiment_id=experiment.id,
                    metric_name=metric.name,
                    value=result.value,
                    scope="experiment",
                    constraint_set_id=None,
                    breakdown=result.details,
                )
            )
            inserted += 1
    session.commit()
    return inserted


def _assert_live_allowed(benchmark: Benchmark, *, live: bool) -> None:
    """Reject live generation on fixture benchmarks (mock_only in YAML)."""
    if live and benchmark.mock_only:
        raise ValueError(
            f"Benchmark '{benchmark.name}' is mock_only and cannot be run with --live. "
            "Use mock mode for evaluator fixtures, or remove mock_only from the YAML."
        )


def _generate_live_candidates(
    generator: BaseGenerator,
    *,
    cs: ConstraintSet,
    run_config: MethodRunConfig,
    samples_per_case: int,
    rng: random.Random,
) -> list[tuple[dict[str, str], str]]:
    """Return (candidate, resolved_sentence_length) pairs for one constraint set."""
    constraints = dict(cs.constraints)
    if cs.expected_form is not None:
        constraints["expected_form"] = cs.expected_form

    common = dict(
        keyword=cs.keyword,
        translation=cs.translation,
        constraints=constraints,
        target_language=cs.target_language,
        cefr_level=cs.cefr_level,
        explicit_subject_required=run_config.explicit_subject_required,
    )
    out: list[tuple[dict[str, str], str]] = []

    if run_config.is_random_length:
        for _ in range(samples_per_case):
            resolved = run_config.resolve_length(rng)
            batch = generator.generate(
                **common,
                num_candidates=1,
                sentence_length=resolved,
            )
            for cand in batch:
                out.append((cand, resolved))
    else:
        resolved = run_config.sentence_length
        batch = generator.generate(
            **common,
            num_candidates=samples_per_case,
            sentence_length=resolved,
        )
        for cand in batch:
            out.append((cand, resolved))

    return out


def _sentence_counts_by_constraint_set(
    session,
    experiment_id: int,
) -> dict[int, int]:
    """Map constraint_set_id -> number of stored sentences for an experiment."""
    rows = (
        session.query(
            GeneratedSentence.constraint_set_id,
            GeneratedSentence.id,
        )
        .filter_by(experiment_id=experiment_id)
        .all()
    )
    counts: dict[int, int] = defaultdict(int)
    for cs_id, _sent_id in rows:
        counts[int(cs_id)] += 1
    return dict(counts)


def _resolve_resume_experiment(
    session,
    *,
    benchmark: Benchmark,
    method_config: MethodConfig,
    live: bool,
    resume_experiment_id: int | None,
    resume: bool,
) -> Experiment | None:
    """Return an existing experiment to continue, or None for a fresh run."""
    expected_name = _experiment_name(
        benchmark=benchmark,
        method_config=method_config,
        live=live,
    )
    if resume_experiment_id is not None:
        experiment = session.query(Experiment).filter_by(id=resume_experiment_id).first()
        if experiment is None:
            raise ValueError(f"No experiment with id={resume_experiment_id}")
        if experiment.benchmark_id != benchmark.id:
            raise ValueError(
                f"Experiment {resume_experiment_id} benchmark_id="
                f"{experiment.benchmark_id} does not match '{benchmark.name}'"
            )
        if experiment.method_config_id != method_config.id:
            raise ValueError(
                f"Experiment {resume_experiment_id} method_config_id="
                f"{experiment.method_config_id} does not match '{method_config.name}'"
            )
        return experiment

    if not resume:
        return None

    return (
        session.query(Experiment)
        .filter(
            Experiment.benchmark_id == benchmark.id,
            Experiment.method_config_id == method_config.id,
            Experiment.name == expected_name,
            Experiment.status.in_(("running", "failed")),
        )
        .order_by(Experiment.id.desc())
        .first()
    )


def run_experiment(
    *,
    benchmark_name: str,
    method_name: str,
    live: bool = False,
    evaluate: bool = True,
    metrics: bool = True,
    resume: bool = False,
    resume_experiment_id: int | None = None,
) -> None:
    """Run a full experiment: generate, evaluate, compute metrics, print summary.

    When ``resume`` / ``resume_experiment_id`` is set, generation skips constraint
    sets that already have ``samples_per_case`` sentences stored, then re-runs
    evaluators and group metrics over the full experiment.
    """
    init_db()
    session = SessionLocal()

    try:
        benchmark = _resolve_benchmark(session, benchmark_name)
        _assert_live_allowed(benchmark, live=live)
        method_config = _resolve_method_config(session, method_name)
        run_config = MethodRunConfig.from_method_config(method_config)
        generator = _build_generator(run_config, method_config)
        rng = random.Random()

        constraint_sets = (
            session.query(ConstraintSet)
            .filter_by(benchmark_id=benchmark.id)
            .order_by(ConstraintSet.id)
            .all()
        )

        existing = _resolve_resume_experiment(
            session,
            benchmark=benchmark,
            method_config=method_config,
            live=live,
            resume_experiment_id=resume_experiment_id,
            resume=resume,
        )
        if existing is not None:
            experiment = existing
            experiment.status = "running"
            experiment.completed_at = None
            session.commit()
            print(
                f"  Resuming experiment id={experiment.id} ({experiment.name})",
                flush=True,
            )
        else:
            if resume or resume_experiment_id is not None:
                print(
                    "  Resume requested but no matching incomplete experiment found; "
                    "starting a new run.",
                    flush=True,
                )
            experiment = Experiment(
                benchmark_id=benchmark.id,
                method_config_id=method_config.id,
                name=_experiment_name(
                    benchmark=benchmark,
                    method_config=method_config,
                    live=live,
                ),
                status="running",
            )
            session.add(experiment)
            session.commit()

        try:
            already_by_cs = _sentence_counts_by_constraint_set(session, experiment.id)
            samples_needed = method_config.samples_per_case
            total_stored = sum(already_by_cs.values())
            skipped_sets = 0
            newly_stored = 0

            for cs in constraint_sets:
                label = f"{cs.keyword} + {cs.tense} + {cs.person} + {cs.number}"
                existing_n = already_by_cs.get(cs.id, 0)
                if existing_n >= samples_needed:
                    skipped_sets += 1
                    print(f"\n  Constraint set: {label}")
                    print(
                        f"    Skip (already have {existing_n}/{samples_needed} sentences)"
                    )
                    continue

                print(f"\n  Constraint set: {label}")
                if existing_n:
                    print(
                        f"    Incomplete ({existing_n}/{samples_needed}); regenerating full batch"
                    )
                    (
                        session.query(GeneratedSentence)
                        .filter_by(experiment_id=experiment.id, constraint_set_id=cs.id)
                        .delete(synchronize_session="fetch")
                    )
                    session.commit()
                    total_stored -= existing_n

                if live:
                    candidate_pairs = _generate_live_candidates(
                        generator,
                        cs=cs,
                        run_config=run_config,
                        samples_per_case=samples_needed,
                        rng=rng,
                    )
                else:
                    mock_batch = get_mock_candidates(benchmark.name, cs.keyword)[
                        : samples_needed
                    ]
                    candidate_pairs = []
                    for cand in mock_batch:
                        resolved = (
                            run_config.resolve_length(rng)
                            if run_config.is_random_length
                            else run_config.sentence_length
                        )
                        candidate_pairs.append((cand, resolved))

                if not candidate_pairs:
                    print(f"    No candidates generated for {cs.keyword}")
                    continue

                for i, (cand, resolved_length) in enumerate(candidate_pairs):
                    gen = GeneratedSentence(
                        experiment_id=experiment.id,
                        constraint_set_id=cs.id,
                        sentence=cand["sentence"],
                        translation=cand["translation"],
                        sample_index=i,
                        generation_meta={
                            "method": method_config.method,
                            "live": live,
                            "sentence_length": run_config.sentence_length,
                            "resolved_sentence_length": resolved_length,
                            "explicit_subject_required": run_config.explicit_subject_required,
                            "constraints": dict(cs.constraints),
                        },
                    )
                    session.add(gen)
                    total_stored += 1
                    newly_stored += 1

                session.commit()
                print(f"    Stored {len(candidate_pairs)} sentences")

            print(
                f"\n  Generation done: skipped_complete_sets={skipped_sets} "
                f"newly_stored={newly_stored} total_sentences={total_stored}"
            )

            total_evals = 0
            if evaluate:
                print("\n  Running per-sentence evaluators...")
                total_evals = _evaluate_sentences(
                    session,
                    experiment,
                    DEFAULT_EVALUATORS,
                )
                print(f"  Stored {total_evals} sentence evaluations")

            total_group_metrics = 0
            total_rollups = 0
            if metrics:
                print("\n  Computing distribution metrics...")
                total_group_metrics = _compute_and_store_group_metrics(
                    session, experiment, DEFAULT_GROUP_METRICS
                )
                print(f"  Stored {total_group_metrics} group metric rows")
                if evaluate:
                    print("\n  Rolling up per-sentence scores...")
                    total_rollups = aggregate_sentence_eval_rollups(session, experiment.id)
                    print(f"  Stored {total_rollups} rollup metric rows")

            experiment.status = "completed"
            experiment.completed_at = datetime.now(timezone.utc)
            session.commit()

        except Exception:
            experiment.status = "failed"
            experiment.completed_at = datetime.now(timezone.utc)
            session.commit()
            raise

        print("\n" + "=" * 60)
        print(f"  Benchmark:    {benchmark.name} (id={benchmark.id})")
        print(f"  Method:       {method_config.name} [{method_config.method}] (id={method_config.id})")
        print(f"  Experiment:   {experiment.name} (id={experiment.id})")
        print(f"  Status:       {experiment.status}")
        print(f"  Constraints:  {len(constraint_sets)}")
        print(f"  Sentences:       {total_stored}")
        print(f"  Sentence evals:  {total_evals}")
        print(f"  Group metrics:   {total_group_metrics}")
        print(f"  Roll-up metrics: {total_rollups}")
        print("=" * 60)

        # Full listing is fine for small benches; skip dump for huge grids.
        if len(constraint_sets) <= 50:
            print("\n  Stored sentences:\n")
            for cs in constraint_sets:
                sentences = (
                    session.query(GeneratedSentence)
                    .filter_by(experiment_id=experiment.id, constraint_set_id=cs.id)
                    .order_by(GeneratedSentence.sample_index)
                    .all()
                )
                if sentences:
                    print(f"  [{cs.keyword} + {cs.tense} + {cs.person} + {cs.number}]")
                    for s in sentences:
                        evals = (
                            session.query(SentenceEvaluation)
                            .filter_by(sentence_id=s.id)
                            .all()
                        )
                        scores = {e.evaluator_name: e.score for e in evals}
                        score_str = (
                            "  " + "  ".join(f"[{k}: {v}]" for k, v in scores.items())
                            if scores else ""
                        )
                        print(f"    {s.sample_index}: {s.sentence}{score_str}")
                        print(f"       {s.translation}")
                    print()

    finally:
        session.close()
