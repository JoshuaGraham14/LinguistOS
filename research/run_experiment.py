"""CLI: run a method config against a benchmark, evaluate, and store results.

Usage:
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default
    python -m research.run_experiment --benchmark spanish_basic --method individual_default --live
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-eval
    python -m research.run_experiment --benchmark spanish_basic --method baseline_default --no-metrics
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.orm import joinedload

load_dotenv(Path(__file__).resolve().parent / ".env")

from research.benchmarks.loader import load_benchmark
from research.methods.loader import load_method_config
from research.evaluation.rollups import aggregate_sentence_eval_rollups
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
from research.evaluation.sentence import DEFAULT_EVALUATORS
from research.evaluation.sentence.base import BaseEvaluator
from research.generation import GENERATOR_REGISTRY
from research.generation.base import BaseGenerator

MOCK_OUTPUTS: dict[str, list[dict[str, str]]] = {
    "comer": [
        {"sentence": "Nosotros comimos pizza anoche.", "translation": "We ate pizza last night."},
        {"sentence": "Comimos en el restaurante nuevo.", "translation": "We ate at the new restaurant."},
        {"sentence": "Ayer comimos paella juntos.", "translation": "Yesterday we ate paella together."},
    ],
    "vivir": [
        {"sentence": "Ella vivirá en Madrid.", "translation": "She will live in Madrid."},
        {"sentence": "Él vivirá cerca del parque.", "translation": "He will live near the park."},
        {"sentence": "Vivirá con su familia.", "translation": "He/She will live with his/her family."},
    ],
    "hablar": [
        {"sentence": "Tú hablas muy rápido.", "translation": "You speak very fast."},
        {"sentence": "Hablas español muy bien.", "translation": "You speak Spanish very well."},
        {"sentence": "Tú hablas con tu madre.", "translation": "You speak with your mother."},
    ],
    "escribir": [
        {"sentence": "Ellos escribieron una carta.", "translation": "They wrote a letter."},
        {"sentence": "Escribieron el informe ayer.", "translation": "They wrote the report yesterday."},
        {"sentence": "Ellos escribieron poemas.", "translation": "They wrote poems."},
    ],
    "correr": [
        {"sentence": "Yo corro en el parque.", "translation": "I run in the park."},
        {"sentence": "Corro todas las mañanas.", "translation": "I run every morning."},
        {"sentence": "Yo corro con mi perro.", "translation": "I run with my dog."},
    ],
}

_BENCHMARKS_DIR = Path(__file__).resolve().parent / "benchmarks"
_METHODS_DIR = Path(__file__).resolve().parent / "methods"


def _resolve_benchmark(session, name: str) -> Benchmark:
    """Load a benchmark by name — reads from YAML on first use, then cached in DB."""
    yaml_path = _BENCHMARKS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No benchmark YAML found at {yaml_path}")
    return load_benchmark(session, yaml_path)


def _resolve_method_config(session, name: str) -> MethodConfig:
    """Load a method config by name — reads from YAML on first use."""
    yaml_path = _METHODS_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"No method YAML found at {yaml_path}")
    return load_method_config(session, yaml_path)


def _build_generator(method_config: MethodConfig) -> BaseGenerator:
    """Instantiate a generator from a MethodConfig row."""
    cls = GENERATOR_REGISTRY.get(method_config.method)
    if cls is None:
        raise ValueError(
            f"Unknown generation method '{method_config.method}'. "
            f"Available: {', '.join(GENERATOR_REGISTRY)}"
        )
    config = method_config.config or {}
    return cls(
        model=config.get("model", "gpt-5.4-nano"),
        temperature=config.get("temperature", 0.7),
    )


def _evaluate_sentences(
    session,
    experiment: Experiment,
    evaluators: list[BaseEvaluator],
) -> int:
    """Run all evaluators against every sentence in the experiment.

    Returns the total number of evaluation rows created.
    """
    sentences = (
        session.query(GeneratedSentence)
        .options(joinedload(GeneratedSentence.constraint_set))
        .filter_by(experiment_id=experiment.id)
        .all()
    )
    total = 0
    for sent in sentences:
        constraints = sent.constraint_set.to_constraints_dict()
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
    """Run distribution-level metrics; write experiment_metrics only (not sentence_evaluations).

    Idempotent: existing group-metric rows for this experiment are deleted first
    (identified as rows whose ``metric_name`` does NOT start with ``mean::``).
    """
    metric_names = [m.name for m in group_metrics]
    if metric_names:
        session.query(ExperimentMetric).filter(
            ExperimentMetric.experiment_id == experiment.id,
            ExperimentMetric.metric_name.in_(metric_names),
        ).delete(synchronize_session="fetch")

    sentences = (
        session.query(GeneratedSentence)
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


def run(
    *,
    benchmark_name: str,
    method_name: str,
    live: bool = False,
    evaluate: bool = True,
    metrics: bool = True,
) -> None:
    init_db()
    session = SessionLocal()

    try:
        benchmark = _resolve_benchmark(session, benchmark_name)
        method_config = _resolve_method_config(session, method_name)
        generator = _build_generator(method_config)

        constraint_sets = (
            session.query(ConstraintSet)
            .filter_by(benchmark_id=benchmark.id)
            .all()
        )

        experiment = Experiment(
            benchmark_id=benchmark.id,
            method_config_id=method_config.id,
            name=f"{method_config.method}_{benchmark.name}_{'live' if live else 'mock'}",
            status="running",
        )
        session.add(experiment)
        session.commit()

        try:
            total_stored = 0

            for cs in constraint_sets:
                print(f"\n  Constraint set: {cs.keyword} + {cs.tense} + {cs.person} + {cs.number}")

                if live:
                    candidates = generator.generate(
                        keyword=cs.keyword,
                        translation=cs.translation,
                        tense=cs.tense,
                        person=cs.person,
                        number=cs.number,
                        num_candidates=method_config.samples_per_case,
                        target_language=cs.target_language,
                        cefr_level=cs.cefr_level,
                    )
                else:
                    candidates = MOCK_OUTPUTS.get(cs.keyword, [])[:method_config.samples_per_case]

                if not candidates:
                    print(f"    No candidates generated for {cs.keyword}")
                    continue

                for i, cand in enumerate(candidates):
                    gen = GeneratedSentence(
                        experiment_id=experiment.id,
                        constraint_set_id=cs.id,
                        sentence=cand["sentence"],
                        translation=cand["translation"],
                        sample_index=i,
                        generation_meta={"method": method_config.method, "live": live},
                    )
                    session.add(gen)
                    total_stored += 1

                session.commit()
                print(f"    Stored {len(candidates)} sentences")

            # ── Evaluation (Stage 1) ─────────────────────────────────────
            total_evals = 0
            if evaluate:
                print("\n  Running per-sentence evaluators...")
                total_evals = _evaluate_sentences(
                    session, experiment, DEFAULT_EVALUATORS
                )
                print(f"  Stored {total_evals} sentence evaluations")

            # ── Metrics: distribution (Stage 2b) then roll-ups (Stage 2a) ─
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

        # ── Print summary ────────────────────────────────────────────────
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


def main():
    parser = argparse.ArgumentParser(description="Run a generation experiment")
    parser.add_argument("--benchmark", type=str, required=True,
                        help="Benchmark name (matches <name>.yaml in benchmarks/)")
    parser.add_argument("--method", type=str, required=True,
                        help="Method config name (matches <name>.yaml in methods/)")
    parser.add_argument("--live", action="store_true", help="Call OpenAI API (requires OPENAI_API_KEY)")
    parser.add_argument("--no-eval", action="store_true", help="Skip per-sentence evaluation (still runs group metrics)")
    parser.add_argument("--no-metrics", action="store_true", help="Skip group metrics and roll-ups")
    args = parser.parse_args()

    mode = "LIVE (calling OpenAI)" if args.live else "MOCK (canned data)"
    print(f"\n  Running experiment: {args.method} / {args.benchmark} [{mode}]\n")

    run(
        benchmark_name=args.benchmark,
        method_name=args.method,
        live=args.live,
        evaluate=not args.no_eval,
        metrics=not args.no_metrics,
    )


if __name__ == "__main__":
    main()
