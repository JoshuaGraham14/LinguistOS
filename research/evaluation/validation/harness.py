"""Score naturalness_pairs.yaml with the perplexity + judge evaluators.

Produces (a) a JSONL of raw per-sentence results, (b) a Markdown report
summarizing pairwise PPL accuracy and judge–human agreement, and (c) an
exit-code signal on the promotion gate.

The harness is deliberately small: it takes evaluator instances so tests
can inject fakes, and it never touches the experiments database.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.validation.pairs_loader import (
    HumanLabel,
    ValidationPair,
    ValidationSet,
)

# --- Promotion gate thresholds --------------------------------------------
# PPL: fraction of pairs where the preferred sentence has strictly lower
# perplexity than the dispreferred one. The rare-but-correct pair is
# excluded from this rate (documented limitation).
PPL_MIN_PAIRWISE_ACCURACY = 0.75

# Judge: fraction of sentences whose predicted numeric axes are within
# ±1 of the human label. Averaged across grammaticality, naturalness, and
# semantic_coherence.
JUDGE_NUMERIC_MIN_WITHIN_ONE = 0.85
# Judge: exact-match rate for the categorical target_form_use across all
# labelled sentences.
JUDGE_TFU_MIN_EXACT_MATCH = 0.80


@dataclass(frozen=True)
class SentenceScoreRow:
    pair_id: str
    category: str
    side: str  # "natural" | "awkward"
    sentence: str
    ppl_score: float | None
    ppl_perplexity: float | None
    ppl_error: str | None
    judge_grammaticality: int | None
    judge_naturalness: int | None
    judge_semantic_coherence: int | None
    judge_target_form_use: str | None
    judge_flags: tuple[str, ...] | None
    judge_rationale: str | None
    judge_error: str | None
    human: HumanLabel


@dataclass(frozen=True)
class PairwiseRow:
    pair_id: str
    category: str
    preferred_side: str
    preferred_ppl: float | None
    dispreferred_ppl: float | None
    ppl_correct: bool | None
    ppl_delta: float | None  # dispreferred - preferred (positive = correct direction)


@dataclass(frozen=True)
class PPLResult:
    total_pairs: int
    scoreable_pairs: int
    correct: int
    pairwise_accuracy: float | None
    excluded_categories: tuple[str, ...]
    per_pair: tuple[PairwiseRow, ...]


@dataclass(frozen=True)
class JudgeAxisResult:
    axis: str
    total_labels: int
    within_one: int
    exact: int
    mean_abs_err: float | None
    within_one_rate: float | None
    exact_match_rate: float | None


@dataclass(frozen=True)
class JudgeResult:
    total_sentences: int
    parsed_sentences: int
    axis_results: dict[str, JudgeAxisResult]
    numeric_within_one_rate: float | None
    target_form_use_exact_rate: float | None


@dataclass(frozen=True)
class HarnessReport:
    validation_version: int
    prompt_version: str
    ppl_model_id: str | None
    judge_model_id: str | None
    rows: tuple[SentenceScoreRow, ...]
    ppl: PPLResult
    judge: JudgeResult

    def as_dict(self) -> dict[str, Any]:
        def _row_dict(row: SentenceScoreRow) -> dict[str, Any]:
            return {
                "pair_id": row.pair_id,
                "category": row.category,
                "side": row.side,
                "sentence": row.sentence,
                "ppl_score": row.ppl_score,
                "ppl_perplexity": row.ppl_perplexity,
                "ppl_error": row.ppl_error,
                "judge_grammaticality": row.judge_grammaticality,
                "judge_naturalness": row.judge_naturalness,
                "judge_semantic_coherence": row.judge_semantic_coherence,
                "judge_target_form_use": row.judge_target_form_use,
                "judge_flags": list(row.judge_flags) if row.judge_flags else None,
                "judge_rationale": row.judge_rationale,
                "judge_error": row.judge_error,
                "human": row.human.as_dict(),
            }

        return {
            "validation_version": self.validation_version,
            "prompt_version": self.prompt_version,
            "ppl_model_id": self.ppl_model_id,
            "judge_model_id": self.judge_model_id,
            "ppl": {
                "total_pairs": self.ppl.total_pairs,
                "scoreable_pairs": self.ppl.scoreable_pairs,
                "correct": self.ppl.correct,
                "pairwise_accuracy": self.ppl.pairwise_accuracy,
                "excluded_categories": list(self.ppl.excluded_categories),
                "per_pair": [
                    {
                        "pair_id": p.pair_id,
                        "category": p.category,
                        "preferred_side": p.preferred_side,
                        "preferred_ppl": p.preferred_ppl,
                        "dispreferred_ppl": p.dispreferred_ppl,
                        "ppl_correct": p.ppl_correct,
                        "ppl_delta": p.ppl_delta,
                    }
                    for p in self.ppl.per_pair
                ],
            },
            "judge": {
                "total_sentences": self.judge.total_sentences,
                "parsed_sentences": self.judge.parsed_sentences,
                "numeric_within_one_rate": self.judge.numeric_within_one_rate,
                "target_form_use_exact_rate": self.judge.target_form_use_exact_rate,
                "axis_results": {
                    axis: {
                        "total_labels": r.total_labels,
                        "within_one": r.within_one,
                        "exact": r.exact,
                        "mean_abs_err": r.mean_abs_err,
                        "within_one_rate": r.within_one_rate,
                        "exact_match_rate": r.exact_match_rate,
                    }
                    for axis, r in self.judge.axis_results.items()
                },
            },
            "rows": [_row_dict(r) for r in self.rows],
        }


# --- Runner ---------------------------------------------------------------


PPL_EXCLUDED_CATEGORIES: tuple[str, ...] = ("rare_but_correct",)


def _score_one(
    evaluator: BaseEvaluator | None,
    sentence: str,
    constraints: dict[str, Any],
) -> EvaluationResult | None:
    if evaluator is None:
        return None
    return evaluator.evaluate(
        sentence=sentence,
        translation="",
        constraints=constraints,
    )


def _extract_ppl(result: EvaluationResult | None) -> tuple[float | None, float | None, str | None, str | None]:
    if result is None:
        return None, None, None, None
    details = result.details or {}
    if "error" in details and details.get("error"):
        return None, None, str(details["error"]), details.get("model_id")
    return (
        float(result.score),
        float(details.get("perplexity")) if details.get("perplexity") is not None else None,
        None,
        details.get("model_id"),
    )


def _extract_judge(
    result: EvaluationResult | None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    if result is None:
        return None, None, None
    details = result.details or {}
    if "error" in details and details.get("error"):
        return None, str(details["error"]), details.get("model_id")
    return details, None, details.get("model_id")


def _compute_ppl_result(
    rows: list[SentenceScoreRow],
    pair_lookup: dict[str, ValidationPair],
) -> PPLResult:
    per_pair: list[PairwiseRow] = []
    scoreable = 0
    correct = 0
    for pair_id, pair in pair_lookup.items():
        nat_row = next((r for r in rows if r.pair_id == pair_id and r.side == "natural"), None)
        awk_row = next((r for r in rows if r.pair_id == pair_id and r.side == "awkward"), None)
        preferred = pair.preferred
        preferred_row = nat_row if preferred == "natural" else awk_row
        dispreferred_row = awk_row if preferred == "natural" else nat_row
        preferred_ppl = preferred_row.ppl_perplexity if preferred_row else None
        dispreferred_ppl = dispreferred_row.ppl_perplexity if dispreferred_row else None

        if pair.category in PPL_EXCLUDED_CATEGORIES:
            per_pair.append(
                PairwiseRow(
                    pair_id=pair_id,
                    category=pair.category,
                    preferred_side=preferred,
                    preferred_ppl=preferred_ppl,
                    dispreferred_ppl=dispreferred_ppl,
                    ppl_correct=None,
                    ppl_delta=None,
                )
            )
            continue

        if (
            preferred_ppl is None
            or dispreferred_ppl is None
            or not math.isfinite(preferred_ppl)
            or not math.isfinite(dispreferred_ppl)
        ):
            per_pair.append(
                PairwiseRow(
                    pair_id=pair_id,
                    category=pair.category,
                    preferred_side=preferred,
                    preferred_ppl=preferred_ppl,
                    dispreferred_ppl=dispreferred_ppl,
                    ppl_correct=None,
                    ppl_delta=None,
                )
            )
            continue

        ppl_correct = preferred_ppl < dispreferred_ppl
        per_pair.append(
            PairwiseRow(
                pair_id=pair_id,
                category=pair.category,
                preferred_side=preferred,
                preferred_ppl=preferred_ppl,
                dispreferred_ppl=dispreferred_ppl,
                ppl_correct=ppl_correct,
                ppl_delta=dispreferred_ppl - preferred_ppl,
            )
        )
        scoreable += 1
        if ppl_correct:
            correct += 1

    accuracy = (correct / scoreable) if scoreable else None
    return PPLResult(
        total_pairs=len(pair_lookup),
        scoreable_pairs=scoreable,
        correct=correct,
        pairwise_accuracy=accuracy,
        excluded_categories=PPL_EXCLUDED_CATEGORIES,
        per_pair=tuple(per_pair),
    )


def _compute_judge_result(rows: list[SentenceScoreRow]) -> JudgeResult:
    parsed_rows = [r for r in rows if r.judge_error is None and r.judge_grammaticality is not None]
    axis_names = ("grammaticality", "naturalness", "semantic_coherence")
    axis_results: dict[str, JudgeAxisResult] = {}
    total_within_one_num = 0
    total_within_one_den = 0
    for axis in axis_names:
        within_one = 0
        exact = 0
        abs_errs: list[float] = []
        for r in parsed_rows:
            predicted = getattr(r, f"judge_{axis}")
            human = getattr(r.human, axis)
            if predicted is None:
                continue
            diff = abs(int(predicted) - int(human))
            abs_errs.append(diff)
            if diff <= 1:
                within_one += 1
            if diff == 0:
                exact += 1
        n = len(abs_errs)
        axis_results[axis] = JudgeAxisResult(
            axis=axis,
            total_labels=n,
            within_one=within_one,
            exact=exact,
            mean_abs_err=(sum(abs_errs) / n) if n else None,
            within_one_rate=(within_one / n) if n else None,
            exact_match_rate=(exact / n) if n else None,
        )
        total_within_one_num += within_one
        total_within_one_den += n

    tfu_total = 0
    tfu_exact = 0
    for r in parsed_rows:
        if r.judge_target_form_use is None:
            continue
        tfu_total += 1
        if r.judge_target_form_use == r.human.target_form_use:
            tfu_exact += 1

    return JudgeResult(
        total_sentences=len(rows),
        parsed_sentences=len(parsed_rows),
        axis_results=axis_results,
        numeric_within_one_rate=(
            total_within_one_num / total_within_one_den if total_within_one_den else None
        ),
        target_form_use_exact_rate=(tfu_exact / tfu_total) if tfu_total else None,
    )


def run_validation(
    vset: ValidationSet,
    *,
    ppl_evaluator: BaseEvaluator | None,
    judge_evaluator: BaseEvaluator | None,
) -> HarnessReport:
    """Score every sentence in the validation set once with each evaluator."""
    rows: list[SentenceScoreRow] = []
    pair_lookup: dict[str, ValidationPair] = {p.pair_id: p for p in vset.pairs}
    ppl_model_id: str | None = None
    judge_model_id: str | None = None

    for pair in vset.pairs:
        for side in ("natural", "awkward"):
            sentence = pair.natural.text if side == "natural" else pair.awkward.text
            human = pair.natural.human_label if side == "natural" else pair.awkward.human_label
            constraints = pair.constraints_for(side)

            ppl_res = _score_one(ppl_evaluator, sentence, constraints)
            ppl_score, ppl_perp, ppl_err, ppl_model = _extract_ppl(ppl_res)
            ppl_model_id = ppl_model_id or ppl_model

            judge_res = _score_one(judge_evaluator, sentence, constraints)
            judge_details, judge_err, judge_model = _extract_judge(judge_res)
            judge_model_id = judge_model_id or judge_model

            rows.append(
                SentenceScoreRow(
                    pair_id=pair.pair_id,
                    category=pair.category,
                    side=side,
                    sentence=sentence,
                    ppl_score=ppl_score,
                    ppl_perplexity=ppl_perp,
                    ppl_error=ppl_err,
                    judge_grammaticality=(
                        int(judge_details["grammaticality"]) if judge_details else None
                    ),
                    judge_naturalness=(
                        int(judge_details["naturalness"]) if judge_details else None
                    ),
                    judge_semantic_coherence=(
                        int(judge_details["semantic_coherence"]) if judge_details else None
                    ),
                    judge_target_form_use=(
                        str(judge_details["target_form_use"]) if judge_details else None
                    ),
                    judge_flags=(
                        tuple(judge_details.get("flags") or ()) if judge_details else None
                    ),
                    judge_rationale=(
                        str(judge_details.get("rationale") or "") if judge_details else None
                    ),
                    judge_error=judge_err,
                    human=human,
                )
            )

    ppl_summary = _compute_ppl_result(rows, pair_lookup)
    judge_summary = _compute_judge_result(rows)

    return HarnessReport(
        validation_version=vset.version,
        prompt_version=vset.prompt_version,
        ppl_model_id=ppl_model_id,
        judge_model_id=judge_model_id,
        rows=tuple(rows),
        ppl=ppl_summary,
        judge=judge_summary,
    )


# --- Promotion gate -------------------------------------------------------


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: tuple[str, ...]


def evaluate_promotion_gate(
    report: HarnessReport,
    *,
    require_ppl: bool = True,
    require_judge: bool = True,
) -> GateResult:
    """Apply the promotion criteria described in the plan.

    ``require_ppl``/``require_judge`` allow scoring only one evaluator at
    a time (e.g. when the judge is skipped because ``OPENAI_API_KEY`` is
    unset).
    """
    reasons: list[str] = []

    if require_ppl:
        acc = report.ppl.pairwise_accuracy
        if acc is None:
            reasons.append("ppl: no scoreable pairs")
        elif acc < PPL_MIN_PAIRWISE_ACCURACY:
            reasons.append(
                f"ppl: pairwise accuracy {acc:.2%} < required "
                f"{PPL_MIN_PAIRWISE_ACCURACY:.0%}"
            )

    if require_judge:
        within_one = report.judge.numeric_within_one_rate
        tfu_rate = report.judge.target_form_use_exact_rate
        if within_one is None or tfu_rate is None:
            reasons.append("judge: no parsed sentences")
        else:
            if within_one < JUDGE_NUMERIC_MIN_WITHIN_ONE:
                reasons.append(
                    f"judge: numeric within-one {within_one:.2%} < required "
                    f"{JUDGE_NUMERIC_MIN_WITHIN_ONE:.0%}"
                )
            if tfu_rate < JUDGE_TFU_MIN_EXACT_MATCH:
                reasons.append(
                    f"judge: target_form_use exact-match {tfu_rate:.2%} < required "
                    f"{JUDGE_TFU_MIN_EXACT_MATCH:.0%}"
                )

    return GateResult(passed=not reasons, reasons=tuple(reasons))


# --- Report writers -------------------------------------------------------


def write_jsonl(report: HarnessReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in report.rows:
            fh.write(
                json.dumps(
                    {
                        "pair_id": row.pair_id,
                        "category": row.category,
                        "side": row.side,
                        "sentence": row.sentence,
                        "ppl_score": row.ppl_score,
                        "ppl_perplexity": row.ppl_perplexity,
                        "ppl_error": row.ppl_error,
                        "judge_grammaticality": row.judge_grammaticality,
                        "judge_naturalness": row.judge_naturalness,
                        "judge_semantic_coherence": row.judge_semantic_coherence,
                        "judge_target_form_use": row.judge_target_form_use,
                        "judge_flags": list(row.judge_flags) if row.judge_flags else None,
                        "judge_rationale": row.judge_rationale,
                        "judge_error": row.judge_error,
                        "human": row.human.as_dict(),
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")


def _fmt_pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, float) else "n/a"


def render_markdown(report: HarnessReport, gate: GateResult) -> str:
    lines: list[str] = []
    lines.append("# Naturalness evaluators — validation report")
    lines.append("")
    lines.append(
        f"- Validation set version: {report.validation_version}"
    )
    lines.append(f"- Judge prompt version: {report.prompt_version}")
    lines.append(f"- PPL model id: `{report.ppl_model_id or 'n/a'}`")
    lines.append(f"- Judge model id: `{report.judge_model_id or 'n/a'}`")
    lines.append("")

    lines.append("## Promotion gate")
    lines.append("")
    lines.append(f"- Result: **{'PASS' if gate.passed else 'FAIL'}**")
    if gate.reasons:
        lines.append("- Failure reasons:")
        for r in gate.reasons:
            lines.append(f"  - {r}")
    lines.append("")

    lines.append("## Perplexity pairwise accuracy")
    lines.append("")
    lines.append(
        f"- Scoreable pairs: {report.ppl.scoreable_pairs} / {report.ppl.total_pairs} "
        f"(excluded categories: {', '.join(report.ppl.excluded_categories) or 'none'})"
    )
    lines.append(f"- Pairwise accuracy: {_fmt_pct(report.ppl.pairwise_accuracy)}")
    lines.append(f"- Threshold: {_fmt_pct(PPL_MIN_PAIRWISE_ACCURACY)}")
    lines.append("")
    lines.append("| pair_id | category | preferred PPL | dispreferred PPL | Δ (dis − pref) | correct |")
    lines.append("|---|---|---:|---:|---:|:---:|")
    for p in report.ppl.per_pair:
        pref = f"{p.preferred_ppl:.2f}" if isinstance(p.preferred_ppl, float) else "—"
        disp = f"{p.dispreferred_ppl:.2f}" if isinstance(p.dispreferred_ppl, float) else "—"
        delta = f"{p.ppl_delta:+.2f}" if isinstance(p.ppl_delta, float) else "—"
        correct = "✓" if p.ppl_correct is True else ("✗" if p.ppl_correct is False else "excluded")
        lines.append(f"| {p.pair_id} | {p.category} | {pref} | {disp} | {delta} | {correct} |")
    lines.append("")

    lines.append("## Judge–human agreement")
    lines.append("")
    lines.append(
        f"- Parsed responses: {report.judge.parsed_sentences} / {report.judge.total_sentences}"
    )
    lines.append(
        f"- Overall numeric within-one: {_fmt_pct(report.judge.numeric_within_one_rate)} "
        f"(threshold {_fmt_pct(JUDGE_NUMERIC_MIN_WITHIN_ONE)})"
    )
    lines.append(
        f"- target_form_use exact match: {_fmt_pct(report.judge.target_form_use_exact_rate)} "
        f"(threshold {_fmt_pct(JUDGE_TFU_MIN_EXACT_MATCH)})"
    )
    lines.append("")
    lines.append("| axis | mean|err| | within-one | exact |")
    lines.append("|---|---:|---:|---:|")
    for axis, r in report.judge.axis_results.items():
        mae = f"{r.mean_abs_err:.2f}" if isinstance(r.mean_abs_err, float) else "—"
        lines.append(
            f"| {axis} | {mae} | {_fmt_pct(r.within_one_rate)} | {_fmt_pct(r.exact_match_rate)} |"
        )
    lines.append("")

    lines.append("## Per-sentence rows")
    lines.append("")
    lines.append(
        "| pair_id | side | judge (G/N/S) | human (G/N/S) | judge TFU | human TFU |"
    )
    lines.append("|---|---|---|---|---|---|")
    for row in report.rows:
        j = (
            f"{row.judge_grammaticality}/"
            f"{row.judge_naturalness}/{row.judge_semantic_coherence}"
            if row.judge_error is None
            else f"error: {row.judge_error[:24]}"
        )
        h = (
            f"{row.human.grammaticality}/{row.human.naturalness}/"
            f"{row.human.semantic_coherence}"
        )
        lines.append(
            f"| {row.pair_id} | {row.side} | {j} | {h} | "
            f"{row.judge_target_form_use or '—'} | {row.human.target_form_use} |"
        )
    return "\n".join(lines) + "\n"


def write_markdown(report: HarnessReport, gate: GateResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report, gate), encoding="utf-8")


def write_summary_json(report: HarnessReport, gate: GateResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = report.as_dict()
    payload["gate"] = {
        "passed": gate.passed,
        "reasons": list(gate.reasons),
        "thresholds": {
            "ppl_min_pairwise_accuracy": PPL_MIN_PAIRWISE_ACCURACY,
            "judge_numeric_min_within_one": JUDGE_NUMERIC_MIN_WITHIN_ONE,
            "judge_tfu_min_exact_match": JUDGE_TFU_MIN_EXACT_MATCH,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


__all__ = [
    "GateResult",
    "HarnessReport",
    "JUDGE_NUMERIC_MIN_WITHIN_ONE",
    "JUDGE_TFU_MIN_EXACT_MATCH",
    "JudgeAxisResult",
    "JudgeResult",
    "PPLResult",
    "PPL_EXCLUDED_CATEGORIES",
    "PPL_MIN_PAIRWISE_ACCURACY",
    "PairwiseRow",
    "SentenceScoreRow",
    "evaluate_promotion_gate",
    "run_validation",
    "write_jsonl",
    "write_markdown",
    "write_summary_json",
]
