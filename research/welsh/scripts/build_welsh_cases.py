"""Build the Welsh gold case table from the n=150 verb manifest + Eurfa.

Mirrors the Spanish experiment-verb pattern: each row is one eval cell with
frozen gold form(s) from an external lexicon (here Eurfa, not verbecc).

Grid (42 cells / verb):
  - synthetic: present / past / imperfect × 6 persons
  - periphrastic: present / past / imperfect / future × 6 persons
    (person on aux; lexical contribution is the verbnoun; soft-mutated after
    gwneud past)

Usage::

    python -m research.welsh.scripts.build_welsh_cases
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from research.welsh.mutation import soft_mutate
from research.welsh.scripts.select_welsh_verbs import (
    DATA_DIR,
    DEFAULT_EURFA,
    MANIFEST_DIR,
    PERSONS,
    _load_eurfa,
    _preferred_surface,
)

DEFAULT_MANIFEST = MANIFEST_DIR / "manifest_welsh_n150.csv"
DEFAULT_OUT = MANIFEST_DIR / "welsh_cases_n150.csv"
DEFAULT_SUMMARY = MANIFEST_DIR / "welsh_cases_n150_summary.json"

# (construction, tense_key, aux_lemma|None, eurfa_tense_for_lexical_or_None, particle)
# For synthetic, gold comes from lexical eurfa_tense.
# For periphrastic, aux forms from aux_lemma@aux_tense; lexical gold is verbnoun.
GRID: tuple[tuple[str, str, str | None, str | None, str], ...] = (
    ("synthetic", "present", None, "pres", ""),
    ("synthetic", "past", None, "past", ""),
    ("synthetic", "imperfect", None, "imperf", ""),
    ("periphrastic", "present", "bod", "pres", "yn"),
    ("periphrastic", "past", "gwneud", "past", ""),
    ("periphrastic", "imperfect", "bod", "imperf", "yn"),
    ("periphrastic", "future", "bod", "fut", "yn"),
)

PERSON_TO_PN: dict[str, tuple[str, str]] = {
    "1s": ("1st", "singular"),
    "2s": ("2nd", "singular"),
    "3s": ("3rd", "singular"),
    "1p": ("1st", "plural"),
    "2p": ("2nd", "plural"),
    "3p": ("3rd", "plural"),
}


def _surfaces_for(frame: pd.DataFrame) -> list[str]:
    """Preferred surface first, then other unique surfaces as alts."""
    if frame.empty:
        return []
    primary = _preferred_surface(frame)
    seen: list[str] = []
    if primary:
        seen.append(primary)
    for surf in frame["surface"].astype(str):
        if surf and surf not in seen:
            seen.append(surf)
    return seen


def _index_eurfa(verbs: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    """lemma -> tense -> subframe."""
    out: dict[str, dict[str, pd.DataFrame]] = defaultdict(dict)
    for (lemma, tense), g in verbs.groupby(["lemma", "tense"], dropna=False, sort=False):
        tkey = "" if pd.isna(tense) else str(tense)
        out[str(lemma)][tkey] = g
    return out


def _person_frame(frame: pd.DataFrame, person: str) -> pd.DataFrame:
    return frame[frame["number"].astype(str) == person]


def build_cases(manifest: pd.DataFrame, eurfa_verbs: pd.DataFrame) -> pd.DataFrame:
    by_lemma = _index_eurfa(eurfa_verbs)
    rows: list[dict] = []
    errors: list[str] = []

    for _, verb in manifest.iterrows():
        lemma = str(verb["lemma"])
        verbnoun = str(verb["verbnoun"])
        tense_map = by_lemma.get(lemma, {})
        infin = tense_map.get("infin", pd.DataFrame())
        vn_forms = _surfaces_for(infin)
        if not vn_forms:
            errors.append(f"{lemma}: missing infin/verbnoun")
            continue
        if verbnoun and verbnoun not in vn_forms:
            # Manifest verbnoun should be the preferred form; keep it primary.
            vn_forms = [verbnoun] + [v for v in vn_forms if v != verbnoun]
        vn_primary = vn_forms[0]

        for construction, tense, aux_lemma, aux_or_lex_tense, particle in GRID:
            for person in PERSONS:
                probed_person, probed_number = PERSON_TO_PN[person]
                cell_id = f"{construction}_{tense}_{person}"
                row: dict = {
                    "lemma": lemma,
                    "enlemma": verb.get("enlemma", ""),
                    "verbnoun": vn_primary,
                    "lang": "cy",
                    "zipf": verb.get("zipf", ""),
                    "tier": verb.get("tier", ""),
                    "freq_rank": verb.get("freq_rank", ""),
                    "cell_id": cell_id,
                    "construction": construction,
                    "tense": tense,
                    "person": person,
                    "probed_person": probed_person,
                    "probed_number": probed_number,
                    "particle": particle,
                    "requires_soft_mutation": False,
                    "aux_lemma": "",
                    "aux_gold": "",
                    "aux_gold_alts": "",
                    "gold": "",
                    "gold_alts": "",
                    "match_forms": "",
                    "seed": verb.get("seed", ""),
                    "experiment": verb.get("experiment", ""),
                }

                if construction == "synthetic":
                    assert aux_or_lex_tense is not None
                    lex = tense_map.get(aux_or_lex_tense, pd.DataFrame())
                    forms = _surfaces_for(_person_frame(lex, person))
                    if not forms:
                        errors.append(f"{lemma}: missing synthetic {aux_or_lex_tense}/{person}")
                        continue
                    row["gold"] = forms[0]
                    row["gold_alts"] = "|".join(forms[1:])
                    row["match_forms"] = "|".join(forms)
                else:
                    assert aux_lemma and aux_or_lex_tense
                    aux_map = by_lemma.get(aux_lemma, {})
                    aux_frame = aux_map.get(aux_or_lex_tense, pd.DataFrame())
                    aux_forms = _surfaces_for(_person_frame(aux_frame, person))
                    if not aux_forms:
                        errors.append(
                            f"{aux_lemma}: missing aux {aux_or_lex_tense}/{person} "
                            f"(needed by {lemma})"
                        )
                        continue
                    row["aux_lemma"] = aux_lemma
                    row["aux_gold"] = aux_forms[0]
                    row["aux_gold_alts"] = "|".join(aux_forms[1:])

                    if tense == "past":
                        # gwneud + soft-mutated verbnoun
                        mutated = soft_mutate(vn_primary)
                        mut_alts = [soft_mutate(v) for v in vn_forms]
                        # Also accept radical VN (models sometimes omit mutation).
                        lexical_forms: list[str] = []
                        for w in [mutated, *mut_alts, *vn_forms]:
                            if w and w not in lexical_forms:
                                lexical_forms.append(w)
                        row["requires_soft_mutation"] = True
                        row["gold"] = mutated  # primary expected lexical piece
                        row["gold_alts"] = "|".join(lexical_forms[1:])
                    else:
                        # bod + yn + radical verbnoun
                        row["gold"] = vn_primary
                        row["gold_alts"] = "|".join(vn_forms[1:])
                        lexical_forms = list(vn_forms)

                    # Forms the sentence should contain for a full peri hit:
                    # any aux alt + any lexical alt (+ particle checked separately).
                    match_bits = list(dict.fromkeys([*aux_forms, *lexical_forms]))
                    row["match_forms"] = "|".join(match_bits)

                rows.append(row)

    if errors:
        # Fail hard: a gold table with holes is worse than no table.
        preview = "\n  ".join(errors[:20])
        more = f"\n  … and {len(errors) - 20} more" if len(errors) > 20 else ""
        raise SystemExit(f"Gold build failed ({len(errors)} gaps):\n  {preview}{more}")

    return pd.DataFrame(rows)


def summarise(cases: pd.DataFrame) -> dict:
    n_verbs = int(cases["lemma"].nunique())
    return {
        "n_rows": int(len(cases)),
        "n_verbs": n_verbs,
        "cells_per_verb": int(len(cases) // n_verbs) if n_verbs else 0,
        "tiers": {k: int(v) for k, v in cases.drop_duplicates("lemma").groupby("tier").size().items()},
        "by_construction_tense": {
            f"{c}/{t}": int(n)
            for (c, t), n in cases.groupby(["construction", "tense"]).size().items()
        },
        "soft_mutation_rows": int(cases["requires_soft_mutation"].sum()),
        "empty_gold": int((cases["gold"].astype(str).str.len() == 0).sum()),
        "empty_aux_on_peri": int(
            (
                (cases["construction"] == "periphrastic")
                & (cases["aux_gold"].astype(str).str.len() == 0)
            ).sum()
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--eurfa", type=Path, default=DEFAULT_EURFA)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = ap.parse_args()

    if not args.manifest.is_file():
        raise SystemExit(f"Missing manifest: {args.manifest}")
    if not args.eurfa.is_file():
        raise SystemExit(f"Missing Eurfa: {args.eurfa}")

    manifest = pd.read_csv(args.manifest)
    eurfa = _load_eurfa(args.eurfa)
    cases = build_cases(manifest, eurfa)
    summary = summarise(cases)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Keep empty strings (not NaN) for optional fields so audits/diffs stay clean.
    cases = cases.fillna("")
    cases.to_csv(args.out, index=False, quoting=csv.QUOTE_MINIMAL)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {args.out} ({summary['n_rows']} rows, {summary['n_verbs']} verbs)")
    print(f"Wrote {args.summary}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
