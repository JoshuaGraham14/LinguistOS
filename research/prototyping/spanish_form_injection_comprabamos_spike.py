#!/usr/bin/env python3
"""Single-cell form-injection spike for diversity inspection.

This mirrors the Experiment 9 "form injection only" method, but isolates one
cell so I can inspect whether the model produces varied short sentences when
the exact surface form is supplied.

Cell:
  lemma: comprar
  translation: to buy
  tense: imperfect
  person/number: 1st plural
  expected_form: comprábamos
  sentence_length: short
  n: 50

Output:
  docs/spike-results/eval_spanish_form_injection_comprabamos_qwen17b_results.json
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.distribution.distinct_ngram import DistinctNgramMetric
from research.evaluation.distribution.self_bleu import SelfBleuMetric
from research.evaluation.distribution.template_rate import TemplateRateMetric
from research.evaluation.distribution.tokens import tokenize as dist_tokenize
from research.evaluation.distribution.uniqueness import UniquenessRatioMetric
from research.evaluation.sentence.expected_form import ExpectedFormMatchEvaluator
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.evaluation.sentence.length_in_band import LengthInBandEvaluator
from research.generation.baseline_hf import FormInjectedHFGenerator
from research.generation.prompt_builder import build_prompt

MODEL_ID = "Qwen/Qwen3-1.7B"
SAMPLES = 50
BATCH_SIZE = 5
TEMPERATURE = 0.7
SENTENCE_LENGTH = "short"
EXPECTED_FORM = "comprábamos"
OUTPUT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spike-results"
    / "eval_spanish_form_injection_comprabamos_qwen17b_results.json"
)

CONSTRAINTS: dict[str, Any] = {
    "tense": "imperfect",
    "person": "1st",
    "number": "plural",
    "target_language": "es",
    "expected_form": EXPECTED_FORM,
}

_EF = ExpectedFormMatchEvaluator()
_LEN = LengthInBandEvaluator()
_LT = LanguageToolGrammarEvaluator()


@dataclass
class SentenceLike:
    sentence: str


@dataclass
class ScoredCandidate:
    sentence: str
    translation: str
    ef_pass: bool
    length_in_band: bool
    token_count: int
    grammar_pass: bool
    grammar_match_count: int
    structure: str
    opening_3gram: str


def classify_structure(sentence: str) -> str:
    tokens = [t.lower() for t in dist_tokenize(sentence)]
    if not tokens:
        return "empty"

    first = tokens[0]
    if first in {"nosotros", "nosotras"}:
        return "explicit_nosotros_subject"
    if first == EXPECTED_FORM:
        return "null_subject_verb_initial"
    if first in {"yo", "tú", "tu", "él", "ella", "usted", "ustedes", "vosotros", "vosotras", "ellos", "ellas"}:
        return f"other_pronoun_subject:{first}"
    if EXPECTED_FORM in tokens[:3]:
        return "non_pronoun_opening_then_target"
    if EXPECTED_FORM in tokens:
        return "target_later"
    return "missing_target"


def opening_3gram(sentence: str) -> str:
    tokens = dist_tokenize(sentence.lower())[:3]
    return " ".join(tokens)


def score_candidate(candidate: dict[str, str]) -> ScoredCandidate:
    sentence = candidate["sentence"]
    translation = candidate.get("translation", "")
    constraints = dict(CONSTRAINTS)
    constraints["sentence_length"] = SENTENCE_LENGTH

    ef = _EF.evaluate(sentence, translation, constraints)
    length = _LEN.evaluate(sentence, translation, constraints)
    grammar = _LT.evaluate(sentence, translation, constraints)
    return ScoredCandidate(
        sentence=sentence,
        translation=translation,
        ef_pass=bool(ef.details.get("passed")),
        length_in_band=bool(length.details.get("in_band")),
        token_count=int(length.details.get("token_count", 0)),
        grammar_pass=bool(grammar.details.get("passed")),
        grammar_match_count=int(grammar.details.get("match_count", 0)),
        structure=classify_structure(sentence),
        opening_3gram=opening_3gram(sentence),
    )


def rate(rows: list[ScoredCandidate], attr: str) -> dict[str, Any]:
    n = len(rows)
    k = sum(1 for row in rows if getattr(row, attr))
    return {"correct": k, "n": n, "pass_rate": round(k / n, 4) if n else None}


def diversity_summary(rows: list[ScoredCandidate]) -> dict[str, Any]:
    sentence_rows = [SentenceLike(row.sentence) for row in rows]
    metrics = [
        UniquenessRatioMetric("constraint_set"),
        SelfBleuMetric("constraint_set"),
        TemplateRateMetric("constraint_set"),
        DistinctNgramMetric(1, "constraint_set"),
        DistinctNgramMetric(2, "constraint_set"),
    ]
    return {
        metric.name: {
            "value": result.value,
            "details": result.details,
        }
        for metric in metrics
        for result in [metric.compute(sentence_rows)]  # keep compute once
    }


def repeated_sentence_counts(rows: list[ScoredCandidate]) -> list[dict[str, Any]]:
    counts = Counter(re.sub(r"\s+", " ", row.sentence.strip().lower()) for row in rows)
    return [
        {"sentence": sentence, "count": count}
        for sentence, count in counts.most_common()
        if count > 1
    ]


def main() -> None:
    prompt = build_prompt(
        keyword="comprar",
        translation="to buy",
        target_language="es",
        constraints=CONSTRAINTS,
        num_candidates=BATCH_SIZE,
        sentence_length=SENTENCE_LENGTH,
        cefr_level="A1",
        inject_expected_form=EXPECTED_FORM,
    )
    print("--- Representative prompt ---")
    print(prompt)
    print()

    generator = FormInjectedHFGenerator(model=MODEL_ID, temperature=TEMPERATURE)
    started = time.perf_counter()
    candidates: list[dict[str, str]] = []
    batch_idx = 0
    while len(candidates) < SAMPLES:
        batch_idx += 1
        remaining = SAMPLES - len(candidates)
        batch_n = min(BATCH_SIZE, remaining)
        print(
            f"[batch {batch_idx}] requesting {batch_n}; "
            f"collected={len(candidates)}/{SAMPLES}",
            flush=True,
        )
        batch = generator.generate(
            keyword="comprar",
            translation="to buy",
            constraints=CONSTRAINTS,
            num_candidates=batch_n,
            target_language="es",
            cefr_level="A1",
            sentence_length=SENTENCE_LENGTH,
        )
        candidates.extend(batch)
        if not batch:
            print("[warn] Batch returned no candidates; stopping early.")
            break

    scored = [score_candidate(candidate) for candidate in candidates]
    elapsed = round(time.perf_counter() - started, 2)

    structure_counts = Counter(row.structure for row in scored)
    opening_counts = Counter(row.opening_3gram for row in scored)
    summary: dict[str, Any] = {
        "parsed_candidates": len(scored),
        "elapsed_s": elapsed,
        "expected_form_match": rate(scored, "ef_pass"),
        "grammar_languagetool": rate(scored, "grammar_pass"),
        "length_in_band": rate(scored, "length_in_band"),
        "diversity": diversity_summary(scored),
        "structure_counts": dict(structure_counts.most_common()),
        "top_opening_3grams": dict(opening_counts.most_common(10)),
        "repeated_sentences": repeated_sentence_counts(scored),
    }

    payload: dict[str, Any] = {
        "model_id": MODEL_ID,
        "method": "form_injection_only_exp9_style",
        "samples": SAMPLES,
        "batch_size": BATCH_SIZE,
        "temperature": TEMPERATURE,
        "sentence_length": SENTENCE_LENGTH,
        "cell": {
            "keyword": "comprar",
            "translation": "to buy",
            "tense": "imperfect",
            "person": "1st",
            "number": "plural",
            "expected_form": EXPECTED_FORM,
            "note": (
                "comprábamos is the 1st-person plural imperfect form "
                "(nosotros/nosotras), not the singular yo form."
            ),
        },
        "prompt": prompt,
        "summary": summary,
        "candidates": [asdict(row) for row in scored],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("--- Summary ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nFull results: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
