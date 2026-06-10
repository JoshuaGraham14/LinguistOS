#!/usr/bin/env python3
"""E0 Hebrew scoping spike — live GPT via baseline_gpt (same prompt as Spanish pipeline)."""

from __future__ import annotations

import json
import string
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

# Repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.evaluation.length_bands import token_count_in_band
from research.evaluation.sentence.expected_form import tokenize
from research.generation.baseline_gpt import build_prompt, generate

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"
PROCLITICS = "והשכלבמ"


@dataclass
class ConstraintCase:
    id: str
    keyword: str
    expected_form: str
    translation: str
    tense: str
    person: str
    number: str
    gender: str | None
    difficulty: str


E0_CASES: list[ConstraintCase] = [
    ConstraintCase(
        id="01_infinitive_trap",
        keyword="לשאול",
        expected_form="שאלתי",
        translation="to ask",
        tense="past",
        person="1st",
        number="singular",
        gender=None,
        difficulty="Infinitive keyword — GPT may leave ל+stem instead of conjugating (Spanish dormir pattern).",
    ),
    ConstraintCase(
        id="02_present_3sg_fem",
        keyword="לכתוב",
        expected_form="כותבת",
        translation="to write",
        tense="present",
        person="3rd",
        number="singular",
        gender="feminine",
        difficulty="Present (Benoni) marks gender on verb; pro-drop common — no overt subject.",
    ),
    ConstraintCase(
        id="03_past_2sg_masc",
        keyword="לשאול",
        expected_form="שאלת",
        translation="to ask",
        tense="past",
        person="2nd",
        number="singular",
        gender="masculine",
        difficulty="2sg past — easy to produce 3sg or 1sg form without anchored subject.",
    ),
    ConstraintCase(
        id="04_past_2sg_fem_ambiguous",
        keyword="ללכת",
        expected_form="הלכת",
        translation="to go",
        tense="past",
        person="2nd",
        number="singular",
        gender="feminine",
        difficulty="הלכת is orthographically identical to 1sg past — person disambiguation needs context.",
    ),
    ConstraintCase(
        id="05_future_1pl",
        keyword="לכתוב",
        expected_form="נכתוב",
        translation="to write",
        tense="future",
        person="1st",
        number="plural",
        gender=None,
        difficulty="Future 1pl requires נ- prefix; GPT may use present or wrong person.",
    ),
    ConstraintCase(
        id="06_past_1pl",
        keyword="לאכול",
        expected_form="אכלנו",
        translation="to eat",
        tense="past",
        person="1st",
        number="plural",
        gender=None,
        difficulty="Past 1pl suffix -נו; tests plural morphology.",
    ),
    ConstraintCase(
        id="07_present_1sg_masc",
        keyword="לדבר",
        expected_form="מדבר",
        translation="to speak",
        tense="present",
        person="1st",
        number="singular",
        gender="masculine",
        difficulty="1sg present is gender-marked despite gender-neutral pronoun אני.",
    ),
    ConstraintCase(
        id="08_present_1sg_fem",
        keyword="לדבר",
        expected_form="מדברת",
        translation="to speak",
        tense="present",
        person="1st",
        number="singular",
        gender="feminine",
        difficulty="Feminine present 1sg — common GPT slip to masculine מדבר.",
    ),
    ConstraintCase(
        id="09_irregular_past_3sg_masc",
        keyword="ללכת",
        expected_form="הלך",
        translation="to go",
        tense="past",
        person="3rd",
        number="singular",
        gender="masculine",
        difficulty="Irregular suppletive past (go → went); high error rate expected.",
    ),
    ConstraintCase(
        id="10_clitic_prone_past_2sg",
        keyword="לתת",
        expected_form="נתת",
        translation="to give",
        tense="past",
        person="2nd",
        number="singular",
        gender="masculine",
        difficulty="Narrative contexts attach ו- (and); tests clitic fusion on target verb.",
    ),
]


def strip_niqqud(text: str) -> str:
    return "".join(c for c in text if not (0x0591 <= ord(c) <= 0x05C7))


def normalize_token(token: str) -> str:
    return strip_niqqud(token).casefold()


def strip_proclitics(token: str) -> str:
    t = strip_niqqud(token)
    while t and t[0] in PROCLITICS:
        t = t[1:]
    return t


def find_expected(sentence: str, expected_form: str) -> dict:
    expected_norm = normalize_token(expected_form)
    tokens = tokenize(sentence)
    for raw in tokens:
        norm = normalize_token(raw)
        if norm == expected_norm:
            return {
                "strict": True,
                "clitic_aware": True,
                "matched_token": raw,
                "match_strategy": "strict",
            }
        stripped = strip_proclitics(raw)
        if stripped and normalize_token(stripped) == expected_norm:
            return {
                "strict": False,
                "clitic_aware": True,
                "matched_token": raw,
                "match_strategy": "clitic_stripped",
                "stripped": stripped,
            }
    return {
        "strict": False,
        "clitic_aware": False,
        "matched_token": None,
        "match_strategy": None,
    }


def case_constraints(case: ConstraintCase) -> dict[str, str]:
    """Flat constraint dict validated by ``research/languages/he.yaml``."""
    out: dict[str, str] = {
        "tense": case.tense,
        "person": case.person,
        "number": case.number,
    }
    if case.gender is not None:
        out["gender"] = case.gender
    return out


def verb_tokens(sentence: str, keyword: str) -> list[str]:
    """Tokens containing keyword root or expected-form-like material."""
    kw = keyword.replace("ל", "", 1) if keyword.startswith("ל") else keyword
    out = []
    for t in tokenize(sentence):
        bare = strip_proclitics(t)
        if kw in bare or bare in kw:
            out.append(t)
    return out


def run_spike(*, samples: int = 3, sentence_length: str = "short") -> dict:
    results: list[dict] = []
    for case in E0_CASES:
        constraints = case_constraints(case)
        prompt = build_prompt(
            keyword=case.keyword,
            translation=case.translation,
            constraints=constraints,
            num_candidates=samples,
            target_language="he",
            sentence_length=sentence_length,
            explicit_subject_required=False,
        )
        candidates = generate(
            keyword=case.keyword,
            translation=case.translation,
            constraints=constraints,
            num_candidates=samples,
            target_language="he",
            sentence_length=sentence_length,
            explicit_subject_required=False,
        )
        case_rows = []
        for i, cand in enumerate(candidates):
            sent = cand["sentence"]
            tokens = tokenize(sent)
            match = find_expected(sent, case.expected_form)
            case_rows.append(
                {
                    "idx": i + 1,
                    "sentence": sent,
                    "translation": cand["translation"],
                    "token_count": len(tokens),
                    "in_length_band": token_count_in_band(len(tokens), sentence_length),
                    **match,
                    "verb_like_tokens": verb_tokens(sent, case.keyword),
                }
            )
        results.append(
            {
                "case": asdict(case),
                "prompt": prompt,
                "candidates": case_rows,
                "n_returned": len(candidates),
            }
        )
    return {
        "cases": results,
        "samples_per_case": samples,
        "sentence_length": sentence_length,
    }


def summarize(data: dict) -> dict:
    sentence_length = data.get("sentence_length", "short")
    total = 0
    strict_pass = 0
    clitic_pass = 0
    length_pass = 0
    clitic_attachments = 0
    token_counts: list[int] = []
    per_case = []
    for block in data["cases"]:
        c = block["case"]
        rows = block["candidates"]
        n = len(rows)
        total += n
        s = sum(1 for r in rows if r["strict"])
        ca = sum(1 for r in rows if r["clitic_aware"])
        lp = sum(1 for r in rows if r["in_length_band"])
        cl = sum(
            1
            for r in rows
            if r["clitic_aware"] and not r["strict"] and r["match_strategy"] == "clitic_stripped"
        )
        strict_pass += s
        clitic_pass += ca
        length_pass += lp
        clitic_attachments += cl
        token_counts.extend(r["token_count"] for r in rows)
        per_case.append(
            {
                "id": c["id"],
                "strict_rate": s / n if n else 0,
                "clitic_aware_rate": ca / n if n else 0,
                "length_rate": lp / n if n else 0,
                "mean_tokens": sum(r["token_count"] for r in rows) / n if n else 0,
                "clitic_only_fixes": cl,
                "n": n,
            }
        )
    return {
        "sentence_length": sentence_length,
        "total_candidates": total,
        "strict_pass_rate": strict_pass / total if total else 0,
        "clitic_aware_pass_rate": clitic_pass / total if total else 0,
        "length_in_band_rate": length_pass / total if total else 0,
        "mean_token_count": sum(token_counts) / len(token_counts) if token_counts else 0,
        "clitic_attachment_fixes": clitic_attachments,
        "per_case": per_case,
    }


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="E0 Hebrew GPT spike")
    parser.add_argument(
        "--length",
        choices=["short", "medium", "long"],
        default="short",
        help="Sentence length band (default: short)",
    )
    parser.add_argument("--samples", type=int, default=3, help="Candidates per case")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set (research/.env)", file=sys.stderr)
        sys.exit(1)

    print(
        f"Running E0 Hebrew spike (baseline_gpt, gpt-5.4-nano, temp=0.7, "
        f"{args.length}, n={args.samples}, language profile he.yaml)...\n"
    )
    data = run_spike(samples=args.samples, sentence_length=args.length)
    summary = summarize(data)
    out_dir = Path(__file__).resolve().parents[2] / "docs"
    json_path = out_dir / f"eval_hebrew_e0_spike_{args.length}_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"data": data, "summary": summary}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2))
    print(f"\nFull results: {json_path}")


if __name__ == "__main__":
    main()
