"""End-to-end tests for the naturalness validation harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.validation.harness import (
    JUDGE_NUMERIC_MIN_WITHIN_ONE,
    JUDGE_TFU_MIN_EXACT_MATCH,
    PPL_EXCLUDED_CATEGORIES,
    PPL_MIN_PAIRWISE_ACCURACY,
    evaluate_promotion_gate,
    render_markdown,
    run_validation,
    write_jsonl,
    write_markdown,
    write_summary_json,
)
from research.evaluation.validation.pairs_loader import load_validation_pairs


class _OraclePPL(BaseEvaluator):
    """Preferred sentence always gets lower PPL — 100% pairwise accuracy."""

    @property
    def name(self) -> str:
        return "fluency_perplexity"

    def evaluate(self, sentence, translation, constraints):
        side = constraints.get("pair_side")
        # Lower NLL for the preferred side; higher for the dispreferred side.
        # We stamp perplexity directly so the harness sees a stable delta.
        if side == "natural":
            mean_nll, perp = 1.0, 2.718
        else:
            mean_nll, perp = 3.0, 20.085
        return EvaluationResult(
            score=1.0 if side == "natural" else 0.1,
            details={
                "mean_nll": mean_nll,
                "perplexity": perp,
                "token_count": 7,
                "model_id": "test/oracle-ppl",
                "revision": None,
                "dtype": "float32",
                "device": "cpu",
                "scorer_version": "test",
            },
        )


class _BadPPL(BaseEvaluator):
    """Always ranks the awkward sentence as lower PPL — 0% accuracy."""

    @property
    def name(self) -> str:
        return "fluency_perplexity"

    def evaluate(self, sentence, translation, constraints):
        side = constraints.get("pair_side")
        if side == "natural":
            return EvaluationResult(
                score=0.1,
                details={
                    "mean_nll": 3.0,
                    "perplexity": 20.085,
                    "token_count": 7,
                    "model_id": "test/bad-ppl",
                    "revision": None,
                    "dtype": "float32",
                    "device": "cpu",
                    "scorer_version": "test",
                },
            )
        return EvaluationResult(
            score=0.9,
            details={
                "mean_nll": 0.5,
                "perplexity": 1.65,
                "token_count": 7,
                "model_id": "test/bad-ppl",
                "revision": None,
                "dtype": "float32",
                "device": "cpu",
                "scorer_version": "test",
            },
        )


class _OracleJudge(BaseEvaluator):
    """Returns the human labels back exactly — 100% agreement."""

    def __init__(self, model_id: str = "test/oracle-judge") -> None:
        self._model_id = model_id

    @property
    def name(self) -> str:
        return "naturalness_llm_judge"

    def evaluate(self, sentence, translation, constraints):
        # Access the pair via the stored constraint fields; the harness gives
        # us the sentence text and pair_side. We recover the labels by loading
        # the YAML lazily inside the fake for each call.
        from research.evaluation.validation.pairs_loader import load_validation_pairs

        vset = load_validation_pairs()
        pair_id = constraints["pair_id"]
        side = constraints["pair_side"]
        pair = next(p for p in vset.pairs if p.pair_id == pair_id)
        sentence_ref = pair.natural if side == "natural" else pair.awkward
        label = sentence_ref.human_label
        return EvaluationResult(
            score=label.naturalness / 5.0,
            details={
                "grammaticality": label.grammaticality,
                "naturalness": label.naturalness,
                "target_form_use": label.target_form_use,
                "semantic_coherence": label.semantic_coherence,
                "flags": list(label.flags),
                "rationale": "Oracle agrees with the authored label.",
                "model_id": self._model_id,
                "prompt_version": "v1",
                "raw_response": "{}",
            },
        )


class _NoisyJudge(BaseEvaluator):
    """Judge always returns naturalness=3 with target_form_use=absent — poor agreement."""

    @property
    def name(self) -> str:
        return "naturalness_llm_judge"

    def evaluate(self, sentence, translation, constraints):
        return EvaluationResult(
            score=3 / 5,
            details={
                "grammaticality": 3,
                "naturalness": 3,
                "target_form_use": "absent",
                "semantic_coherence": 3,
                "flags": [],
                "rationale": "Noisy fake — always returns 3s.",
                "model_id": "test/noisy-judge",
                "prompt_version": "v1",
                "raw_response": "{}",
            },
        )


# --- Tests ---------------------------------------------------------------


def test_run_validation_generates_row_per_sentence():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=_OraclePPL(), judge_evaluator=_OracleJudge())
    assert len(report.rows) == 2 * len(vset)
    assert report.validation_version == vset.version
    assert report.prompt_version == vset.prompt_version
    assert report.ppl_model_id == "test/oracle-ppl"
    assert report.judge_model_id == "test/oracle-judge"


def test_oracle_ppl_gives_perfect_accuracy_and_excludes_rare_category():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=_OraclePPL(), judge_evaluator=None)
    total = len(vset)
    excluded = sum(1 for p in vset.pairs if p.category in PPL_EXCLUDED_CATEGORIES)
    assert report.ppl.total_pairs == total
    assert report.ppl.scoreable_pairs == total - excluded
    assert report.ppl.correct == total - excluded
    assert report.ppl.pairwise_accuracy == 1.0
    excluded_rows = [
        p for p in report.ppl.per_pair if p.category in PPL_EXCLUDED_CATEGORIES
    ]
    assert excluded_rows and all(r.ppl_correct is None for r in excluded_rows)


def test_bad_ppl_fails_gate():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=_BadPPL(), judge_evaluator=None)
    assert report.ppl.pairwise_accuracy == 0.0
    gate = evaluate_promotion_gate(report, require_ppl=True, require_judge=False)
    assert not gate.passed
    assert any("ppl" in r for r in gate.reasons)


def test_oracle_judge_gives_perfect_agreement_and_passes_gate():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=None, judge_evaluator=_OracleJudge())
    assert report.judge.parsed_sentences == 2 * len(vset)
    assert report.judge.numeric_within_one_rate == 1.0
    assert report.judge.target_form_use_exact_rate == 1.0
    gate = evaluate_promotion_gate(report, require_ppl=False, require_judge=True)
    assert gate.passed, gate.reasons


def test_noisy_judge_fails_gate():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=None, judge_evaluator=_NoisyJudge())
    gate = evaluate_promotion_gate(report, require_ppl=False, require_judge=True)
    assert not gate.passed
    reasons_blob = " ".join(gate.reasons)
    assert "target_form_use" in reasons_blob or "numeric within-one" in reasons_blob


def test_both_oracles_pass_combined_gate():
    vset = load_validation_pairs()
    report = run_validation(
        vset, ppl_evaluator=_OraclePPL(), judge_evaluator=_OracleJudge()
    )
    gate = evaluate_promotion_gate(report, require_ppl=True, require_judge=True)
    assert gate.passed, gate.reasons


def test_thresholds_are_in_range():
    for v in (
        PPL_MIN_PAIRWISE_ACCURACY,
        JUDGE_NUMERIC_MIN_WITHIN_ONE,
        JUDGE_TFU_MIN_EXACT_MATCH,
    ):
        assert 0.0 < v <= 1.0


def test_writers_produce_expected_artifacts(tmp_path: Path):
    vset = load_validation_pairs()
    report = run_validation(
        vset, ppl_evaluator=_OraclePPL(), judge_evaluator=_OracleJudge()
    )
    gate = evaluate_promotion_gate(report)

    raw = tmp_path / "raw.jsonl"
    summary = tmp_path / "summary.json"
    md = tmp_path / "report.md"

    write_jsonl(report, raw)
    write_summary_json(report, gate, summary)
    write_markdown(report, gate, md)

    assert raw.exists() and summary.exists() and md.exists()

    with raw.open() as fh:
        lines = [json.loads(line) for line in fh if line.strip()]
    assert len(lines) == 2 * len(vset)
    assert {"pair_id", "side", "human"} <= set(lines[0])

    parsed = json.loads(summary.read_text(encoding="utf-8"))
    assert parsed["gate"]["passed"] is True
    assert parsed["ppl"]["pairwise_accuracy"] == 1.0
    assert parsed["judge"]["numeric_within_one_rate"] == 1.0

    md_text = md.read_text(encoding="utf-8")
    assert md_text.startswith("# Naturalness evaluators")
    assert "Promotion gate" in md_text
    # Both tables present.
    assert "## Perplexity pairwise accuracy" in md_text
    assert "## Judge–human agreement" in md_text


def test_render_markdown_notes_failure_reasons_when_gate_fails():
    vset = load_validation_pairs()
    report = run_validation(vset, ppl_evaluator=_BadPPL(), judge_evaluator=None)
    gate = evaluate_promotion_gate(report, require_ppl=True, require_judge=False)
    md = render_markdown(report, gate)
    assert "**FAIL**" in md
    assert "Failure reasons" in md
