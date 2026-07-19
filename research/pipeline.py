"""Research experiment pipeline: generate, evaluate, and store metrics."""

from __future__ import annotations

import json
import os
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from research.evaluation.distribution import (
    EXPERIMENT_GROUP_METRIC_NAMES,
    group_metrics_for_run,
)
from research.evaluation.distribution.base import BaseGroupMetric
from research.evaluation.rollups import aggregate_sentence_eval_rollups
from research.evaluation.sentence import DEFAULT_EVALUATORS
from research.evaluation.sentence.base import BaseEvaluator


def _merge_evaluators(
    defaults: list[BaseEvaluator],
    extras: list[BaseEvaluator] | None,
) -> list[BaseEvaluator]:
    """Concatenate defaults + extras, dropping duplicates by ``.name``."""
    if not extras:
        return list(defaults)
    seen: set[str] = {ev.name for ev in defaults}
    merged: list[BaseEvaluator] = list(defaults)
    for ev in extras:
        if ev.name in seen:
            continue
        merged.append(ev)
        seen.add(ev.name)
    return merged
from research.fixtures.mock_outputs import get_mock_candidates
from research.generation import GENERATOR_REGISTRY
from research.generation.base import BaseGenerator
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    get_cost_telemetry,
    reset_cost_telemetry,
)
from research.generation.cluster_batch_sizes import resolve_hf_batch_size
from research.generation.constrained_hf import ConstrainedHFGenerator
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
    raw = method_config.config or {}
    kwargs: dict[str, object] = {
        "model": run_config.model,
        "temperature": run_config.temperature,
    }
    if "num_beams" in raw:
        kwargs["num_beams"] = int(raw["num_beams"])
    if "bias_strength" in raw:
        kwargs["bias_strength"] = float(raw["bias_strength"])
    if "neurologic_lambda" in raw:
        kwargs["neurologic_lambda"] = float(raw["neurologic_lambda"])
    if "neurologic_alpha" in raw:
        kwargs["neurologic_alpha"] = int(raw["neurologic_alpha"])
    if "rich_grouping" in raw:
        kwargs["rich_grouping"] = bool(raw["rich_grouping"])
    if "use_prefix_automaton" in raw:
        kwargs["use_prefix_automaton"] = bool(raw["use_prefix_automaton"])
    if "no_repeat_ngram_size" in raw:
        kwargs["no_repeat_ngram_size"] = int(raw["no_repeat_ngram_size"])
    if "min_new_tokens" in raw:
        kwargs["min_new_tokens"] = int(raw["min_new_tokens"])
    if "length_penalty" in raw:
        kwargs["length_penalty"] = float(raw["length_penalty"])
    return cls(**kwargs)


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


def _clear_experiment_group_metrics(session, experiment_id: int) -> None:
    """Remove pooled experiment-scope group metrics (when skipped on a run)."""
    if not EXPERIMENT_GROUP_METRIC_NAMES:
        return
    session.query(ExperimentMetric).filter(
        ExperimentMetric.experiment_id == experiment_id,
        ExperimentMetric.metric_name.in_(EXPERIMENT_GROUP_METRIC_NAMES),
    ).delete(synchronize_session="fetch")


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
    total_metrics = len(group_metrics)
    cs_commit_every = 500
    for metric_idx, metric in enumerate(group_metrics, start=1):
        print(
            f"    Group metric {metric_idx}/{total_metrics}: "
            f"{metric.name} ({metric.scope})...",
            flush=True,
        )
        if metric.scope == "constraint_set":
            total_cs = len(by_cs)
            for cs_idx, (cs_id, group) in enumerate(by_cs.items(), start=1):
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
                if cs_idx % cs_commit_every == 0:
                    session.commit()
                    print(
                        f"      {metric.name}: {cs_idx}/{total_cs} cells",
                        flush=True,
                    )
            session.commit()
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


def _constraint_generation_job(
    cs: ConstraintSet,
    *,
    run_config: MethodRunConfig,
    samples_per_case: int,
) -> dict[str, Any]:
    constraints = dict(cs.constraints)
    if cs.expected_form is not None:
        constraints["expected_form"] = cs.expected_form
    return {
        "keyword": cs.keyword,
        "translation": cs.translation,
        "constraints": constraints,
        "num_candidates": samples_per_case,
        "target_language": cs.target_language,
        "cefr_level": cs.cefr_level,
        "sentence_length": run_config.sentence_length,
        "explicit_subject_required": run_config.explicit_subject_required,
    }


def _store_generated_sentences(
    session,
    *,
    experiment: Experiment,
    constraint_set: ConstraintSet,
    candidate_pairs: list[tuple[dict[str, str], str]],
    method_config: MethodConfig,
    run_config: MethodRunConfig,
    live: bool,
) -> int:
    stored = 0
    for i, (cand, resolved_length) in enumerate(candidate_pairs):
        session.add(
            GeneratedSentence(
                experiment_id=experiment.id,
                constraint_set_id=constraint_set.id,
                sentence=cand["sentence"],
                translation=cand["translation"],
                sample_index=i,
                generation_meta={
                    "method": method_config.method,
                    "live": live,
                    "sentence_length": run_config.sentence_length,
                    "resolved_sentence_length": resolved_length,
                    "explicit_subject_required": run_config.explicit_subject_required,
                    "constraints": dict(constraint_set.constraints),
                },
            )
        )
        stored += 1
    return stored


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


def _write_cost_log(
    *,
    path: Path,
    experiment: Experiment,
    benchmark_name: str,
    method_config: MethodConfig,
    run_config: MethodRunConfig,
    session,
    cells: int,
    newly_stored: int,
    gen_wall_s: float,
    gen_calls: int,
    hf_batch_size: int,
) -> None:
    """Write generation-only cost summary JSON (latency + token means)."""
    sentences = (
        session.query(GeneratedSentence)
        .filter_by(experiment_id=experiment.id)
        .order_by(GeneratedSentence.id)
        .all()
    )
    texts = [s.sentence or "" for s in sentences]
    gen_tokens_mean = None
    gen_tokens_total = None
    telemetry = get_cost_telemetry()
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(run_config.model, trust_remote_code=True)
        if texts:
            enc = tok(texts, add_special_tokens=False)
            lengths = [len(ids) for ids in enc["input_ids"]]
            gen_tokens_total = int(sum(lengths))
            gen_tokens_mean = float(gen_tokens_total) / len(lengths)
    except Exception as exc:  # pragma: no cover - best-effort on cluster
        print(f"  Cost tokenisation skipped: {exc}", flush=True)

    raw_cfg = method_config.config or {}
    beams = int(raw_cfg.get("num_beams") or 1)
    n = max(newly_stored, 1)
    payload = {
        "arm_label": os.environ.get("COST_ARM_LABEL", "").strip() or None,
        "benchmark": benchmark_name,
        "method": method_config.name,
        "generator": method_config.method,
        "model": run_config.model,
        "num_beams": beams,
        "lora_adapter": os.environ.get("LORA_ADAPTER_PATH", "").strip() or None,
        "hf_batch_size": hf_batch_size,
        "experiment_id": experiment.id,
        "cells": cells,
        "sentences": len(sentences),
        "newly_stored": newly_stored,
        "gen_calls": gen_calls,
        "gen_wall_s": round(gen_wall_s, 4),
        "ms_per_sentence": round(1000.0 * gen_wall_s / n, 2),
        "sentences_per_s": round(n / gen_wall_s, 4) if gen_wall_s > 0 else None,
        "gen_tokens_mean": None if gen_tokens_mean is None else round(gen_tokens_mean, 3),
        "gen_tokens_total": gen_tokens_total,
        "prompt_tokens_mean": (
            None
            if telemetry["prompt_tokens_mean"] is None
            else round(telemetry["prompt_tokens_mean"], 3)
        ),
        "prompt_tokens_per_sentence": (
            round(telemetry["prompt_tokens_total"] / n, 3)
            if telemetry["prompt_tokens_total"]
            else None
        ),
        "prompt_tokens_total": telemetry["prompt_tokens_total"],
        "prompt_sequences": telemetry["prompt_sequences"],
        "model_generate_calls": telemetry["model_generate_calls"],
        "calls_per_cell": 1,
        "decode_work_proxy": None,
    }
    if gen_tokens_mean is not None:
        payload["decode_work_proxy"] = round(float(beams) * gen_tokens_mean, 3)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"  Wrote cost log → {path}", flush=True)


def run_experiment(
    *,
    benchmark_name: str,
    method_name: str,
    live: bool = False,
    evaluate: bool = True,
    metrics: bool = True,
    experiment_group_metrics: bool = True,
    resume: bool = False,
    resume_experiment_id: int | None = None,
    extra_evaluators: list[BaseEvaluator] | None = None,
) -> None:
    """Run a full experiment: generate, evaluate, compute metrics, print summary.

    When ``resume`` / ``resume_experiment_id`` is set, generation skips constraint
    sets that already have ``samples_per_case`` sentences stored, then re-runs
    evaluators and group metrics over the full experiment.

    Set ``experiment_group_metrics=False`` on large multi-cell benchmarks to skip
    pooled experiment-scope distribution metrics (notably experiment-wide Self-BLEU).
    Per-cell (constraint_set) metrics and sentence roll-ups are unchanged.

    Pass ``extra_evaluators`` to run one or more opt-in per-sentence evaluators
    alongside ``DEFAULT_EVALUATORS``. Optional evaluators are intended for
    small dev/smoke runs only; the primary integration path for the
    naturalness scorers is offline rescore against per-arm DBs.
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

            work_queue: list[tuple[ConstraintSet, str]] = []
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
                work_queue.append((cs, label))

            use_hf_batch = (
                live
                and isinstance(generator, (BaselineHFGenerator, ConstrainedHFGenerator))
                and not run_config.is_random_length
            )
            if isinstance(generator, ConstrainedHFGenerator):
                hf_profile = "beam"
            else:
                hf_profile = "heavy" if samples_needed > 1 else "json"
            hf_batch_size = resolve_hf_batch_size(
                model_id=run_config.model,
                profile=hf_profile,
                yaml_override=run_config.hf_batch_size,
            )

            if use_hf_batch and work_queue:
                print(
                    f"\n  HF padded batching enabled "
                    f"(batch_size={hf_batch_size}, profile={hf_profile})",
                    flush=True,
                )

            cost_log_path = os.environ.get("RESEARCH_COST_LOG", "").strip()
            cost_warmup = (
                os.environ.get("RESEARCH_COST_WARMUP", "").strip().lower()
                in {"1", "true", "yes"}
            )
            gen_wall_s = 0.0
            gen_calls = 0

            def _process_candidate_pairs(
                cs: ConstraintSet,
                label: str,
                candidate_pairs: list[tuple[dict[str, str], str]],
            ) -> None:
                nonlocal total_stored, newly_stored
                if not candidate_pairs:
                    print(f"    No candidates generated for {cs.keyword}")
                    return
                stored = _store_generated_sentences(
                    session,
                    experiment=experiment,
                    constraint_set=cs,
                    candidate_pairs=candidate_pairs,
                    method_config=method_config,
                    run_config=run_config,
                    live=live,
                )
                total_stored += stored
                newly_stored += stored
                session.commit()
                print(f"    Stored {stored} sentences")

            if use_hf_batch:
                resolved = run_config.sentence_length
                if cost_warmup and work_queue:
                    warm_chunk = work_queue[: min(hf_batch_size, len(work_queue))]
                    warm_jobs = [
                        _constraint_generation_job(
                            cs,
                            run_config=run_config,
                            samples_per_case=samples_needed,
                        )
                        for cs, _ in warm_chunk
                    ]
                    print(
                        f"\n  Cost warm-up: {len(warm_jobs)} cells "
                        "(excluded from timing and storage)",
                        flush=True,
                    )
                    generator.generate_many(warm_jobs, batch_size=hf_batch_size)
                # Exclude warm-up telemetry and begin the measured region.
                reset_cost_telemetry()
                for batch_start in range(0, len(work_queue), hf_batch_size):
                    chunk = work_queue[batch_start : batch_start + hf_batch_size]
                    batch_end = batch_start + len(chunk)
                    print(
                        f"\n  HF batch [{batch_end}/{len(work_queue)}] "
                        f"cells {batch_start + 1}-{batch_end}",
                        flush=True,
                    )
                    jobs = [
                        _constraint_generation_job(
                            cs,
                            run_config=run_config,
                            samples_per_case=samples_needed,
                        )
                        for cs, _ in chunk
                    ]
                    t_gen = time.perf_counter()
                    batches = generator.generate_many(
                        jobs,
                        batch_size=hf_batch_size,
                    )
                    gen_wall_s += time.perf_counter() - t_gen
                    gen_calls += 1
                    for (cs, label), candidates in zip(chunk, batches):
                        pairs = [(cand, resolved) for cand in candidates]
                        _process_candidate_pairs(cs, label, pairs)
            else:
                for cs, label in work_queue:
                    if live:
                        t_gen = time.perf_counter()
                        candidate_pairs = _generate_live_candidates(
                            generator,
                            cs=cs,
                            run_config=run_config,
                            samples_per_case=samples_needed,
                            rng=rng,
                        )
                        gen_wall_s += time.perf_counter() - t_gen
                        gen_calls += 1
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
                    _process_candidate_pairs(cs, label, candidate_pairs)

            print(
                f"\n  Generation done: skipped_complete_sets={skipped_sets} "
                f"newly_stored={newly_stored} total_sentences={total_stored}"
            )
            if cost_log_path and newly_stored > 0:
                ms_per = 1000.0 * gen_wall_s / newly_stored
                print(
                    f"  Cost timing: gen_wall_s={gen_wall_s:.3f} "
                    f"gen_calls={gen_calls} ms/sentence={ms_per:.1f}",
                    flush=True,
                )

            total_evals = 0
            if evaluate:
                evaluators = _merge_evaluators(DEFAULT_EVALUATORS, extra_evaluators)
                if extra_evaluators:
                    extra_names = [
                        ev.name
                        for ev in extra_evaluators
                        if ev.name not in {d.name for d in DEFAULT_EVALUATORS}
                    ]
                    if extra_names:
                        print(
                            "  Optional evaluators enabled: "
                            + ", ".join(extra_names),
                            flush=True,
                        )
                print("\n  Running per-sentence evaluators...")
                total_evals = _evaluate_sentences(
                    session,
                    experiment,
                    evaluators,
                )
                print(f"  Stored {total_evals} sentence evaluations")

            total_group_metrics = 0
            total_rollups = 0
            if metrics:
                group_metrics = group_metrics_for_run(
                    include_experiment_scope=experiment_group_metrics,
                )
                if not experiment_group_metrics:
                    _clear_experiment_group_metrics(session, experiment.id)
                    print(
                        "  Skipping experiment-scope group metrics "
                        "(per-cell metrics only)",
                        flush=True,
                    )
                print("\n  Computing distribution metrics...")
                total_group_metrics = _compute_and_store_group_metrics(
                    session, experiment, group_metrics
                )
                print(f"  Stored {total_group_metrics} group metric rows")
                if evaluate:
                    print("\n  Rolling up per-sentence scores...")
                    total_rollups = aggregate_sentence_eval_rollups(session, experiment.id)
                    print(f"  Stored {total_rollups} rollup metric rows")

            experiment.status = "completed"
            experiment.completed_at = datetime.now(timezone.utc)
            session.commit()

            if cost_log_path:
                _write_cost_log(
                    path=Path(cost_log_path),
                    experiment=experiment,
                    benchmark_name=benchmark.name,
                    method_config=method_config,
                    run_config=run_config,
                    session=session,
                    cells=len(constraint_sets),
                    newly_stored=newly_stored,
                    gen_wall_s=gen_wall_s,
                    gen_calls=gen_calls,
                    hf_batch_size=hf_batch_size if use_hf_batch else 1,
                )

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
