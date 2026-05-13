"""CLI: run baseline GPT generation, evaluate, and store results in SQLite.

Usage:
    python -m research.run_experiment                 # mock data + eval + metrics
    python -m research.run_experiment --live           # calls OpenAI for real
    python -m research.run_experiment --live --samples 5
    python -m research.run_experiment --no-eval        # skip per-sentence evaluation (still metrics)
    python -m research.run_experiment --no-metrics     # skip group metrics + roll-ups
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone

from research.analysis import aggregate_sentence_eval_rollups
from research.db.database import SessionLocal, init_db
from research.db.models import (
    ConstraintSet,
    Experiment,
    ExperimentMetric,
    GeneratedSentence,
    SentenceEvaluation,
)
from research.evaluation.base import BaseEvaluator
from research.evaluation.grammar import GrammarEvaluator
from research.evaluation.group import DEFAULT_GROUP_METRICS, BaseGroupMetric
from research.generation.baseline_gpt import generate as gpt_generate

DEFAULT_EVALUATORS: list[BaseEvaluator] = [GrammarEvaluator()]

# ── Hardcoded constraint sets for Phase 1 ────────────────────────────────────

PHASE1_CONSTRAINT_SETS: list[dict[str, str]] = [
    {"keyword": "comer", "translation": "to eat", "tense": "past", "person": "1st", "number": "plural"},
    {"keyword": "vivir", "translation": "to live", "tense": "future", "person": "3rd", "number": "singular"},
    {"keyword": "hablar", "translation": "to speak", "tense": "present", "person": "2nd", "number": "singular"},
    {"keyword": "escribir", "translation": "to write", "tense": "past", "person": "3rd", "number": "plural"},
    {"keyword": "correr", "translation": "to run", "tense": "present", "person": "1st", "number": "singular"},
]

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


def _ensure_constraint_sets(session) -> list[ConstraintSet]:
    """Insert constraint sets if they don't exist yet, return all of them."""
    existing = session.query(ConstraintSet).all()
    if existing:
        return existing

    sets = []
    for cs in PHASE1_CONSTRAINT_SETS:
        row = ConstraintSet(
            keyword=cs["keyword"],
            translation=cs["translation"],
            tense=cs["tense"],
            person=cs["person"],
            number=cs["number"],
            target_language="es",
        )
        session.add(row)
        sets.append(row)
    session.commit()
    return sets


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
        .filter_by(experiment_id=experiment.id)
        .all()
    )
    total = 0
    for sent in sentences:
        cs = sent.constraint_set
        constraints = {
            "keyword": cs.keyword,
            "translation": cs.translation,
            "tense": cs.tense,
            "person": cs.person,
            "number": cs.number,
            "target_language": cs.target_language,
            "cefr_level": cs.cefr_level,
        }
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
    """Run distribution-level metrics; write experiment_metrics only (not sentence_evaluations)."""
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
    live: bool = False,
    samples_per_case: int = 3,
    evaluate: bool = True,
    metrics: bool = True,
) -> None:
    init_db()
    session = SessionLocal()

    try:
        constraint_sets = _ensure_constraint_sets(session)

        experiment = Experiment(
            name=f"baseline_gpt_{'live' if live else 'mock'}",
            method="baseline_gpt",
            samples_per_case=samples_per_case,
            config={"live": live, "model": "gpt-4o", "temperature": 0.7},
            status="running",
        )
        session.add(experiment)
        session.commit()

        total_stored = 0

        for cs in constraint_sets:
            print(f"\n  Constraint set: {cs.keyword} + {cs.tense} + {cs.person} + {cs.number}")

            if live:
                candidates = gpt_generate(
                    keyword=cs.keyword,
                    translation=cs.translation,
                    tense=cs.tense,
                    person=cs.person,
                    number=cs.number,
                    num_candidates=samples_per_case,
                    target_language=cs.target_language,
                    cefr_level=cs.cefr_level,
                )
            else:
                candidates = MOCK_OUTPUTS.get(cs.keyword, [])[:samples_per_case]

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
                    generation_meta={"method": "baseline_gpt", "live": live},
                )
                session.add(gen)
                total_stored += 1

            session.commit()
            print(f"    Stored {len(candidates)} sentences")

        # ── Evaluation (Stage 1) ─────────────────────────────────────────
        total_evals = 0
        if evaluate:
            print("\n  Running per-sentence evaluators...")
            total_evals = _evaluate_sentences(
                session, experiment, DEFAULT_EVALUATORS
            )
            print(f"  Stored {total_evals} sentence evaluations")

        # ── Metrics: distribution (Stage 2b) then roll-ups (Stage 2a) ─────
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

        # ── Print summary ────────────────────────────────────────────────
        print("\n" + "=" * 60)
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
    parser = argparse.ArgumentParser(description="Run a baseline GPT experiment")
    parser.add_argument("--live", action="store_true", help="Call OpenAI API (requires OPENAI_API_KEY)")
    parser.add_argument("--samples", type=int, default=3, help="Samples per constraint set (default: 3)")
    parser.add_argument("--no-eval", action="store_true", help="Skip per-sentence evaluation (still runs group metrics)")
    parser.add_argument("--no-metrics", action="store_true", help="Skip group metrics and roll-ups")
    args = parser.parse_args()

    mode = "LIVE (calling OpenAI)" if args.live else "MOCK (canned data)"
    print(f"\n  Running experiment: baseline_gpt [{mode}]\n")

    run(
        live=args.live,
        samples_per_case=args.samples,
        evaluate=not args.no_eval,
        metrics=not args.no_metrics,
    )


if __name__ == "__main__":
    main()
