#!/usr/bin/env python3
"""Niche constraint spike — Spanish + Hebrew hard cases (prototyping; not the pipeline).

Scores single-token expected_form (strict) and optional adjacent phrase sequences.
Exercise-type lines name the phenomenon under test without giving example sentences.
Results: docs/spike-results/eval_niche_constraints_spike_results.json
"""

from __future__ import annotations

import json
import string
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from research.evaluation.length_bands import token_count_in_band
from research.evaluation.sentence.expected_form import tokenize
from research.generation.baseline_gpt import build_prompt, generate

_EDGE_PUNCT = string.punctuation + "«»""''¡¿"
HE_PROCLITICS = "והשכלבמ"


@dataclass
class NicheCase:
    id: str
    language: str
    keyword: str
    translation: str
    constraints: dict[str, str]
    expected_form: str | None = None
    expected_phrase: list[str] | None = None
    exercise_type: str | None = None
    sentence_length: str = "medium"
    notes: str = ""
    manual_checks: list[str] = field(default_factory=list)


NICHE_CASES: list[NicheCase] = [
    # ── Spanish ──────────────────────────────────────────────────────────────
    NicheCase(
        id="es_si_imperf_subj",
        language="es",
        keyword="correr",
        translation="to run",
        constraints={
            "tense": "imperfect",
            "mood": "subjunctive",
            "person": "3rd",
            "number": "singular",
        },
        expected_form="corriera",
        exercise_type="conditional sentence with si-clause",
        manual_checks=[
            "si-clause uses subjunctive (not indicative)",
            "main clause conditional (not present/future)",
        ],
    ),
    NicheCase(
        id="es_pluperf_subj",
        language="es",
        keyword="comer",
        translation="to eat",
        constraints={
            "tense": "imperfect",
            "mood": "subjunctive",
            "person": "1st",
            "number": "singular",
        },
        expected_phrase=["hubiera", "comido"],
        exercise_type="compound pluperfect subjunctive",
        sentence_length="medium",
        manual_checks=[
            "auxiliary hubiera/hubiese (not había indicative)",
            "past participle agrees in number with subject if applicable",
        ],
    ),
    NicheCase(
        id="es_vosotros_imperf_subj",
        language="es",
        keyword="hablar",
        translation="to speak",
        constraints={
            "tense": "imperfect",
            "mood": "subjunctive",
            "person": "2nd",
            "number": "plural",
            "dialect": "peninsular",
        },
        expected_form="hablarais",
        manual_checks=[
            "vosotros/vosotras subject or clear 2pl peninsular (not ustedes hablaran)",
        ],
    ),
    NicheCase(
        id="es_passive_se",
        language="es",
        keyword="vender",
        translation="to sell",
        constraints={
            "tense": "present",
            "mood": "indicative",
            "person": "3rd",
            "number": "plural",
        },
        expected_form="venden",
        exercise_type="passive se",
        manual_checks=[
            "se + plural verb agreeing with following plural noun (not se vende + plural noun)",
        ],
    ),
    NicheCase(
        id="es_clitic_doubling",
        language="es",
        keyword="decir",
        translation="to say",
        constraints={
            "tense": "preterite",
            "mood": "indicative",
            "person": "1st",
            "number": "singular",
        },
        expected_phrase=["se", "lo", "dije"],
        exercise_type="clitic doubling",
        manual_checks=[
            "IO clitic before DO clitic (se/te/le + lo/la)",
            "le→se mutation before lo if applicable",
        ],
    ),
    NicheCase(
        id="es_voseo",
        language="es",
        keyword="comer",
        translation="to eat",
        constraints={
            "tense": "present",
            "mood": "indicative",
            "person": "2nd",
            "number": "singular",
            "dialect": "voseo",
        },
        expected_form="comés",
        sentence_length="short",
        manual_checks=["vos subject with voseo verb form (not tú comes)"],
    ),
    # ── Hebrew ───────────────────────────────────────────────────────────────
    NicheCase(
        id="he_hifil_future_weak",
        language="he",
        keyword="לְהוֹרִיד",
        translation="to bring down / lower",
        constraints={
            "tense": "future",
            "person": "3rd",
            "number": "singular",
            "gender": "masculine",
            "binyan": "hifil",
        },
        expected_form="יוריד",
        sentence_length="short",
        manual_checks=["hif'il future of ירד, not pa'al ירד"],
    ),
    NicheCase(
        id="he_piel_only",
        language="he",
        keyword="לְדַבֵּר",
        translation="to speak",
        constraints={
            "tense": "past",
            "person": "3rd",
            "number": "singular",
            "gender": "masculine",
            "binyan": "piel",
        },
        expected_form="דיבר",
        sentence_length="short",
        manual_checks=["pi'el past (no pa'al in modern for this root)"],
    ),
    NicheCase(
        id="he_hitpael_past",
        language="he",
        keyword="לְהִתְלַבֵּשׁ",
        translation="to get dressed",
        constraints={
            "tense": "past",
            "person": "1st",
            "number": "singular",
            "binyan": "hitpael",
        },
        expected_form="התלבשתי",
        sentence_length="short",
    ),
    NicheCase(
        id="he_hollow_future_fem",
        language="he",
        keyword="לָקוּם",
        translation="to rise / get up",
        constraints={
            "tense": "future",
            "person": "3rd",
            "number": "singular",
            "gender": "feminine",
        },
        expected_form="תקום",
        sentence_length="short",
        manual_checks=["feminine future of hollow root קום"],
    ),
    NicheCase(
        id="he_neg_imperative",
        language="he",
        keyword="לָלֶכֶת",
        translation="to go",
        constraints={
            "person": "2nd",
            "number": "singular",
            "gender": "feminine",
        },
        expected_phrase=["אל", "תלכי"],
        exercise_type="negative imperative",
        sentence_length="short",
        manual_checks=[
            "אל negator (not לא + infinitive)",
            "2sg feminine imperative form",
        ],
    ),
    NicheCase(
        id="he_object_suffix",
        language="he",
        keyword="לִרְאוֹת",
        translation="to see",
        constraints={
            "tense": "past",
            "person": "1st",
            "number": "singular",
            "gender": "masculine",
        },
        expected_form="ראיתיה",
        sentence_length="short",
        manual_checks=["object suffix -ה on verb (not separate אותה)"],
    ),
    NicheCase(
        id="he_hifil_fem_pl_present",
        language="he",
        keyword="לְהָכִין",
        translation="to prepare",
        constraints={
            "tense": "present",
            "person": "3rd",
            "number": "plural",
            "gender": "feminine",
            "binyan": "hifil",
        },
        expected_form="מכינות",
        sentence_length="short",
        manual_checks=["hif'il present feminine plural (not pa'al מכינות homograph risk)"],
    ),
]


def strip_niqqud(text: str) -> str:
    return "".join(c for c in text if not (0x0591 <= ord(c) <= 0x05C7))


def normalize_token(token: str) -> str:
    return strip_niqqud(token).strip(_EDGE_PUNCT).casefold()


def strip_he_proclitics(token: str) -> str:
    t = strip_niqqud(token)
    while t and t[0] in HE_PROCLITICS:
        t = t[1:]
    return t


def find_expected_token(sentence: str, expected_form: str) -> dict[str, Any]:
    expected_norm = normalize_token(expected_form)
    for raw in tokenize(sentence):
        norm = normalize_token(raw)
        if norm == expected_norm:
            return {"strict": True, "matched_token": raw, "match_strategy": "strict"}
        stripped = strip_he_proclitics(raw)
        if stripped and normalize_token(stripped) == expected_norm:
            return {
                "strict": False,
                "matched_token": raw,
                "match_strategy": "clitic_stripped",
            }
    return {"strict": False, "matched_token": None, "match_strategy": None}


def find_adjacent_phrase(sentence: str, phrase: list[str]) -> dict[str, Any]:
    tokens = tokenize(sentence)
    norms = [normalize_token(t) for t in tokens]
    phrase_norms = [normalize_token(p) for p in phrase]
    n = len(phrase_norms)
    for i in range(len(norms) - n + 1):
        if norms[i : i + n] == phrase_norms:
            return {
                "phrase_match": True,
                "matched_span": tokens[i : i + n],
                "start_index": i,
            }
    return {"phrase_match": False, "matched_span": None, "start_index": None}


def score_candidate(case: NicheCase, sentence: str) -> dict[str, Any]:
    out: dict[str, Any] = {"sentence": sentence}
    if case.expected_form:
        out.update(find_expected_token(sentence, case.expected_form))
        out["scoring_mode"] = "token"
    elif case.expected_phrase:
        out.update(find_adjacent_phrase(sentence, case.expected_phrase))
        out["scoring_mode"] = "phrase"
    else:
        out["scoring_mode"] = "manual_only"
    return out


def run_spike(*, samples: int = 3) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case in NICHE_CASES:
        prompt = build_prompt(
            keyword=case.keyword,
            translation=case.translation,
            constraints=case.constraints,
            num_candidates=samples,
            target_language=case.language,
            sentence_length=case.sentence_length,
            exercise_type=case.exercise_type,
        )
        candidates = generate(
            keyword=case.keyword,
            translation=case.translation,
            constraints=case.constraints,
            num_candidates=samples,
            target_language=case.language,
            sentence_length=case.sentence_length,
            exercise_type=case.exercise_type,
        )
        rows = []
        for i, cand in enumerate(candidates):
            sent = cand["sentence"]
            score = score_candidate(case, sent)
            rows.append(
                {
                    "idx": i + 1,
                    "sentence": sent,
                    "translation": cand["translation"],
                    "token_count": len(tokenize(sent)),
                    "in_length_band": token_count_in_band(
                        len(tokenize(sent)), case.sentence_length
                    ),
                    **score,
                }
            )
        results.append(
            {
                "case": asdict(case),
                "prompt": prompt,
                "candidates": rows,
                "n_returned": len(candidates),
            }
        )
    return {"cases": results, "samples_per_case": samples}


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    per_case = []
    for block in data["cases"]:
        c = block["case"]
        rows = block["candidates"]
        n = len(rows)
        if c.get("expected_form"):
            passes = sum(1 for r in rows if r.get("strict"))
            clitic = sum(
                1 for r in rows if r.get("strict") or r.get("match_strategy") == "clitic_stripped"
            )
            metric = "ef_strict"
            rate = passes / n if n else 0.0
            clitic_rate = clitic / n if n else 0.0
        elif c.get("expected_phrase"):
            passes = sum(1 for r in rows if r.get("phrase_match"))
            metric = "phrase_match"
            rate = passes / n if n else 0.0
            clitic_rate = None
        else:
            metric = "manual"
            rate = None
            clitic_rate = None
        per_case.append(
            {
                "id": c["id"],
                "language": c["language"],
                "metric": metric,
                "pass_rate": rate,
                "clitic_aware_rate": clitic_rate,
                "n": n,
            }
        )
    return {"per_case": per_case, "samples_per_case": data["samples_per_case"]}


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Niche constraint GPT spike")
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set (research/.env)", file=sys.stderr)
        sys.exit(1)

    print(
        f"Running niche constraint spike ({len(NICHE_CASES)} cases, "
        f"n={args.samples}, gpt-5.4-nano)...\n"
    )
    data = run_spike(samples=args.samples)
    summary = summarize(data)
    out_path = (
        Path(__file__).resolve().parents[2] / "docs" / "spike-results" / "eval_niche_constraints_spike_results.json"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"data": data, "summary": summary}, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
