#!/usr/bin/env python3
"""Smoke-test a patched judge prompt on participle cells.

Compares SYSTEM_PROMPT v2 (current) vs a local v3 draft on a fixed set of
known artefact / genuine-fail pairs. Does NOT write to any experiment DB.

Usage (cluster login node is fine; OpenAI API only):
  source research/.env
  export PYTHONPATH=/vol/bitbucket/jjg25/LinguistOS
  python research/scripts/smoke_judge_participle_prompt_v3.py
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

MODEL = os.environ.get("JUDGE_MODEL", "gpt-5.4-mini")


# ---------------------------------------------------------------------------
# Current production prompt (v2) — copied verbatim from naturalness_llm_judge.py
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_V2 = """\
You are a rigorous evaluator of Spanish sentences produced by a language
model that was asked to use a specific verb form. You are not the teacher
or the generator; you are grading the sentence as a native Spanish
speaker.

Rate ONLY the Spanish sentence. Do not consider any English translation.
Do not reward the sentence merely because the expected form appears in
it. Penalise sentences that quote or list the form instead of using it
as a main verb, and sentences that are repetitions or degenerate loops.
Short but well-formed clauses are acceptable; do not penalise a sentence
for being short if it is natural and coherent.

Return a single JSON object matching this schema. No prose, no code
fences, no extra keys, no null values.

{
  "grammaticality":     integer 1..5,
  "naturalness":        integer 1..5,
  "target_form_use":    "correct_main_verb"
                      | "correct_but_not_main_verb"
                      | "wrong_agreement_or_role"
                      | "mentioned_or_quoted_only"
                      | "absent",
  "semantic_coherence": integer 1..5,
  "flags": [
    "odd_collocation" |
    "subject_verb_disagreement" |
    "tense_context_conflict" |
    "repetition_or_degeneration" |
    "mixed_language_or_meta_output"
  ],
  "rationale": string (max 240 characters, written in English)
}

Scale anchors (one worked example per level; use these as calibration
points, not exhaustive rules):

grammaticality
  5 = fully grammatical Spanish.
      Ex: "Comemos temprano cada día." — every element is well-formed.
  4 = minor grammatical issue that does not impede understanding.
      Ex: "María tiene veinte año." — missing plural on "año" is a
      clear but minor slip.
  3 = noticeable grammatical errors but meaning is recoverable.
      Ex: "Ellos escribe cartas a los abuelos." — subject-verb number
      disagreement; the meaning is still obvious.
  2 = major grammatical errors.
      Ex: "Yo comer manzana ayer." — verb uninflected and article
      missing at the same time.
  1 = ungrammatical or not a valid sentence.
      Ex: "Manzana el que corre está." — words in an invalid order;
      not a Spanish sentence.

naturalness
  5 = a native would naturally produce this sentence.
      Ex: "Vosotros obtenéis información en la biblioteca." — an
      unremarkable everyday sentence.
  4 = acceptable, slightly unusual phrasing or word choice.
      Ex: "Nosotros comemos temprano cada día." — explicit "nosotros"
      is optional and slightly marked in a neutral context.
  3 = understandable but noticeably awkward.
      Ex: "Nos comemos temprano cada día." — reflexive is grammatical
      but mildly regional; a native would often rephrase.
  2 = substantially unnatural; a native would rewrite it.
      Ex: "Hacemos una decisión difícil." — English calque; a native
      says "tomamos una decisión".
  1 = broken or incoherent.
      Ex: "Coméis coméis coméis coméis juntos." — degenerate output.
  NEVER use this axis to penalise pure grammar mistakes; use
  `grammaticality` for those.

semantic_coherence
  5 = coherent, plausible meaning.
      Ex: "Comemos temprano cada día." — a plausible everyday event.
  4 = coherent, mildly odd content.
      Ex: "Bebemos café con ajo cada mañana." — imaginable but unusual.
  3 = interpretable but implausible.
      Ex: "Como una puerta." — grammatical, but the referent is
      implausible.
  2 = strained, partially interpretable.
      Ex: "Ayer comeré en casa." — "ayer" (past) clashes with the
      future verb "comeré"; the proposition contradicts itself.
  1 = nonsensical or degenerate.
      Ex: "Coméis coméis coméis juntos." — no meaningful proposition.

target_form_use categories:
  correct_main_verb            = the expected form is the main verb of
                                 the sentence and agrees with its subject
                                 in person and number.
  correct_but_not_main_verb    = the expected form appears with correct
                                 morphology but is subordinate, not the
                                 main verb.
  wrong_agreement_or_role      = the form is present but does not agree
                                 with its subject, or is used in a role
                                 it cannot syntactically fill.
  mentioned_or_quoted_only     = the form appears in quotes, as a
                                 vocabulary item, or as a metalinguistic
                                 mention; it is not used.
  absent                       = the exact expected form does not appear.

Flag definitions (assign each independently; a sentence may have zero
or several flags):
  odd_collocation             = lexically unusual or implausible word
                                combinations (e.g. "comer una puerta",
                                "información fácil"). Lexical only.
  subject_verb_disagreement   = subject and verb differ in person or
                                number. Purely grammatical.
  tense_context_conflict      = time adverbials or context contradict
                                the tense of the main verb.
  repetition_or_degeneration  = tokens or short phrases repeat in a
                                degenerate way.
  mixed_language_or_meta_output = contains non-Spanish spans, tags such
                                as </think>, or explains itself instead
                                of producing the sentence.

Write `rationale` in English regardless of the sentence language. This
field is read by an English-speaking annotator. If you cannot produce
an English rationale, return {"error": "no_english_rationale"} instead.

Be strict but fair. If unsure between two integers, pick the lower one
for `grammaticality`, `naturalness`, and `semantic_coherence`.
"""


# ---------------------------------------------------------------------------
# Draft v3 = v2 + two clarifying blocks (haber auxiliary + participle rule)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_V3 = SYSTEM_PROMPT_V2.replace(
    "Be strict but fair. If unsure between two integers, pick the lower one\n"
    "for `grammaticality`, `naturalness`, and `semantic_coherence`.\n",
    """\
Spanish *haber*: he/has/ha/hemos/habéis/han (and past/future/conditional
forms) are Spanish auxiliaries. Sentence-initial "He" is 1sg *haber*,
NOT the English pronoun. Ex: "He comido pan." → correct_main_verb;
never flag mixed_language for "He" alone.

Participles: a past participle cannot stand alone as a predicate; it
needs a finite auxiliary (*haber*, or *ser*/*estar* for passive/
resultative). In a perfect/passive, the target participle under
haber/ser/estar counts as correct_main_verb. Bare forms like
"caminado en la calle" are NOT correct_main_verb.

Be strict but fair. If unsure between two integers, pick the lower one
for `grammaticality`, `naturalness`, and `semantic_coherence`.
""",
)


def build_user_prompt(sentence: str, expected_form: str, lemma: str) -> str:
    return "\n".join(
        [
            "Target language: Spanish",
            f"Expected verb form: {expected_form}",
            f"Lemma: {lemma}",
            "Tense: participle",
            "",
            "Sentence:",
            f'"{sentence}"',
        ]
    )


@dataclass(frozen=True)
class Case:
    id: str
    bucket: str  # artefact | genuine_fail | genuine_ok | edge
    expected_tfu: str  # what a correct judge should return
    sentence: str
    expected_form: str
    lemma: str
    note: str


# Curated from real OOD / frontier runs. No DB writes — hard-coded only.
CASES: list[Case] = [
    # --- Artefacts: correct Spanish perfects, v2 misread "He" as English ---
    Case(
        "A1",
        "artefact",
        "correct_main_verb",
        "He amonestado al niño.",
        "amonestado",
        "amonestar",
        "v2 treated He as English; should be correct perfect",
    ),
    Case(
        "A2",
        "artefact",
        "correct_main_verb",
        "He elogiado tu trabajo.",
        "elogiado",
        "elogiar",
        "v2 treated He as English; should be correct perfect",
    ),
    Case(
        "A3",
        "artefact",
        "correct_main_verb",
        "He tarareado mucho.",
        "tarareado",
        "tararear",
        "v2 treated He as English; should be correct perfect",
    ),
    Case(
        "A4",
        "artefact",
        "correct_main_verb",
        "He salido.",
        "salido",
        "salir",
        "short but grammatical perfect; should not be mixed-language",
    ),
    # --- Genuine fails: bare participle / no finite auxiliary ---
    Case(
        "G1",
        "genuine_fail",
        "correct_but_not_main_verb",
        "caminado en la calle",
        "caminado",
        "caminar",
        "bare participle fragment — must NOT become correct_main_verb",
    ),
    Case(
        "G2",
        "genuine_fail",
        "correct_but_not_main_verb",
        "casado el novio de mi madre",
        "casado",
        "casar",
        "bare participle fragment — must NOT become correct_main_verb",
    ),
    Case(
        "G3",
        "genuine_fail",
        "correct_but_not_main_verb",
        "elogiado el trabajo de un amigo",
        "elogiado",
        "elogiar",
        "bare participle NP — must NOT become correct_main_verb",
    ),
    # --- Genuine OK controls (already correct under v2) ---
    Case(
        "O1",
        "genuine_ok",
        "correct_main_verb",
        "He apoyado la decisión.",
        "apoyado",
        "apoyar",
        "control: already OK under v2; must stay correct",
    ),
    Case(
        "O2",
        "genuine_ok",
        "correct_main_verb",
        "Ha envejecido mucho.",
        "envejecido",
        "envejecer",
        "control: Ha-initial (no English homograph); must stay correct",
    ),
    # --- Edge: passive / resultative ---
    Case(
        "E1",
        "edge",
        "correct_main_verb",
        "He sido humillado.",
        "humillado",
        "humillar",
        "passive under ser — should count as correct under v3 rule",
    ),
]


def call_judge(client: OpenAI, system: str, user: str) -> dict[str, Any]:
    completion = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = completion.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "bad_json", "raw": raw[:500]}


def fmt(obj: dict[str, Any]) -> str:
    tfu = obj.get("target_form_use", "?")
    g = obj.get("grammaticality", "?")
    n = obj.get("naturalness", "?")
    s = obj.get("semantic_coherence", "?")
    flags = ",".join(obj.get("flags") or []) or "-"
    rat = (obj.get("rationale") or obj.get("error") or "")[:120]
    return f"tfu={tfu:<28} G={g} N={n} S={s} flags={flags}\n         {rat}"


def main() -> int:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1

    client = OpenAI(api_key=key)
    print(f"model={MODEL}")
    print(f"cases={len(CASES)}  (v2 vs v3, {2 * len(CASES)} API calls)")
    print("=" * 88)

    rows: list[dict[str, Any]] = []
    v2_ok = v3_ok = 0
    for case in CASES:
        user = build_user_prompt(case.sentence, case.expected_form, case.lemma)
        print(f"\n[{case.id}] bucket={case.bucket}  expect={case.expected_tfu}")
        print(f"  sent: {case.sentence!r}")
        print(f"  note: {case.note}")

        v2 = call_judge(client, SYSTEM_PROMPT_V2, user)
        v3 = call_judge(client, SYSTEM_PROMPT_V3, user)
        print(f"  v2: {fmt(v2)}")
        print(f"  v3: {fmt(v3)}")

        hit2 = v2.get("target_form_use") == case.expected_tfu
        hit3 = v3.get("target_form_use") == case.expected_tfu
        v2_ok += int(hit2)
        v3_ok += int(hit3)
        print(f"  match expect: v2={'YES' if hit2 else 'NO '}  v3={'YES' if hit3 else 'NO '}")

        rows.append(
            {
                "id": case.id,
                "bucket": case.bucket,
                "sentence": case.sentence,
                "expected_tfu": case.expected_tfu,
                "v2": v2,
                "v3": v3,
                "v2_match": hit2,
                "v3_match": hit3,
            }
        )

    print("\n" + "=" * 88)
    print(f"SUMMARY  v2 matches expect: {v2_ok}/{len(CASES)}")
    print(f"SUMMARY  v3 matches expect: {v3_ok}/{len(CASES)}")

    # Bucket-level: artefacts should flip; genuine fails must not flip to correct
    arts = [r for r in rows if r["bucket"] == "artefact"]
    fails = [r for r in rows if r["bucket"] == "genuine_fail"]
    art_fixed = sum(
        1
        for r in arts
        if r["v2"].get("target_form_use") != "correct_main_verb"
        and r["v3"].get("target_form_use") == "correct_main_verb"
    )
    fail_still_wrong = sum(
        1 for r in fails if r["v3"].get("target_form_use") != "correct_main_verb"
    )
    print(f"Artefacts fixed by v3 (wrong→correct_main_verb): {art_fixed}/{len(arts)}")
    print(
        f"Genuine fails still not correct_main_verb under v3: "
        f"{fail_still_wrong}/{len(fails)}"
    )

    out = os.environ.get(
        "SMOKE_OUT",
        "/tmp/smoke_judge_participle_prompt_v3d.json",
    )
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"model": MODEL, "rows": rows}, fh, ensure_ascii=False, indent=2)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
