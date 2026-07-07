"""Label-aware paradigm slot scoring for Diagnostic 2A (and re-scoring saved runs).

Metrics per indicative paradigm call (6 persons):
  * strict — correct form in the correct slot (label-aware or positional lines)
  * perfect_paradigm — all 6 strict slots correct
  * unordered_assignment — walk gold slots yo→ellos; each match consumes one unused
    model output line (position-free; shared yo/él forms need two separate lines)
  * form_presence — share of distinct gold surface forms that appear anywhere
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from research.generation.baseline_hf import _strip_thinking

SCORING_VERSION = "label_aware_v3"

_EDGE_PUNCT = ".,;:!?\"'«»""''¡¿()[]{}"

# Longer labels first so ``él/ella`` wins over ``él``.
_LINE_LABEL_TO_SLOT: tuple[tuple[str, int], ...] = (
    ("él/ella", 2),
    ("nosotros", 3),
    ("nosotras", 3),
    ("vosotros", 4),
    ("vosotras", 4),
    ("nosotros/nosotras", 3),
    ("vosotros/vosotras", 4),
    ("ellos/ellas", 5),
    ("yo", 0),
    ("tú", 1),
    ("tu", 1),
    ("él", 2),
    ("ella", 2),
    ("ellos", 5),
    ("ellas", 5),
)

_PRONOUN_TOKENS = frozenset({
    "yo", "tú", "tu", "él", "ella", "nosotros", "nosotras",
    "vosotros", "vosotras", "ellos", "ellas",
})


def normalize_form(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip(_EDGE_PUNCT).casefold()


def tokenize_spanish(text: str) -> list[str]:
    text = _strip_thinking(text)
    return re.findall(r"[\w\u00C0-\u024F]+", text, flags=re.UNICODE)


def first_token(text: str) -> str:
    cleaned = _strip_thinking(text).strip()
    cleaned = cleaned.split("\n", 1)[0].strip()
    cleaned = re.sub(r"^(answer|response|respuesta)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = cleaned.strip("\"'` ")
    match = re.search(r"[\w'\-]+", cleaned, flags=re.UNICODE)
    return match.group(0) if match else cleaned


def verb_token_from_line(line: str) -> str | None:
    """Extract the conjugated verb from one output line (skip leading pronoun)."""
    cleaned = re.sub(r"^[-*•\d.)\s]+", "", line.strip())
    if not cleaned:
        return None
    for label, _ in _LINE_LABEL_TO_SLOT:
        if _line_starts_with_label(cleaned, label):
            cleaned = cleaned[len(label):].lstrip(":.,/ ) ")
            break
    toks = re.findall(r"[\w\u00C0-\u024F]+", cleaned, flags=re.UNICODE)
    while toks and toks[0].casefold() in _PRONOUN_TOKENS:
        toks.pop(0)
    return toks[0] if toks else None


def _line_starts_with_label(line: str, label: str) -> bool:
    low = line.casefold()
    lab = label.casefold()
    if not low.startswith(lab):
        return False
    if len(low) == len(lab):
        return True
    return low[len(lab)] in ":.,/ )"


def parse_label_aware_slots(raw: str) -> list[str | None]:
    """Map model output to six ordered slots (yo … ellos)."""
    slots: list[str | None] = [None] * 6
    lines = [ln.strip() for ln in _strip_thinking(raw).splitlines() if ln.strip()]
    unlabeled: list[str] = []

    for line in lines:
        cleaned = re.sub(r"^[-*•\d.)\s]+", "", line).strip()
        matched = False
        for label, idx in _LINE_LABEL_TO_SLOT:
            if _line_starts_with_label(cleaned, label):
                rest = cleaned[len(label):].lstrip(":.,/ ) ")
                token = first_token(rest) if rest else verb_token_from_line(cleaned)
                if token:
                    slots[idx] = token
                matched = True
                break
        if not matched:
            unlabeled.append(cleaned)

    if all(s is None for s in slots) and lines:
        for i, line in enumerate(lines[:6]):
            slots[i] = verb_token_from_line(line)
        return slots

    empty_indices = [i for i, s in enumerate(slots) if s is None]
    for idx, line in zip(empty_indices, unlabeled, strict=False):
        slots[idx] = verb_token_from_line(line)

    return slots


def parse_line_forms(raw: str) -> list[str | None]:
    """One conjugated verb per output line (first six lines), ignoring labels."""
    lines = [ln.strip() for ln in _strip_thinking(raw).splitlines() if ln.strip()]
    forms = [verb_token_from_line(line) for line in lines[:6]]
    while len(forms) < 6:
        forms.append(None)
    return forms


def unordered_assignment_match(
    expected: list[str],
    output_forms: list[str | None],
) -> tuple[int, list[bool], list[int | None]]:
    """Match gold slots to model lines; each output form can be used at most once."""
    used = [False] * len(output_forms)
    assignment_flags = [False] * len(expected)
    matched_output_idx: list[int | None] = [None] * len(expected)
    hits = 0

    for gi, gold in enumerate(expected):
        gold_norm = normalize_form(gold)
        for oi, form in enumerate(output_forms):
            if used[oi] or form is None:
                continue
            if normalize_form(form) == gold_norm:
                used[oi] = True
                assignment_flags[gi] = True
                matched_output_idx[gi] = oi
                hits += 1
                break

    return hits, assignment_flags, matched_output_idx


def score_indicative_paradigm(
    *,
    expected: list[str],
    person_labels: list[str],
    raw: str,
) -> dict[str, Any]:
    """Score one six-person paradigm call."""
    parsed_slots = parse_label_aware_slots(raw)
    output_forms = parse_line_forms(raw)
    token_norms = {normalize_form(t) for t in tokenize_spanish(raw)}
    assignment_hits, assignment_flags, assignment_matched_line = unordered_assignment_match(
        expected, output_forms
    )

    per_person: list[dict[str, Any]] = []
    strict_hits = 0

    for i, (label, gold, parsed) in enumerate(
        zip(person_labels, expected, parsed_slots, strict=True)
    ):
        parsed_norm = normalize_form(parsed) if parsed else None
        strict_match = parsed_norm == normalize_form(gold)
        if strict_match:
            strict_hits += 1
        oi = assignment_matched_line[i]
        per_person.append(
            {
                "person": label,
                "expected": gold,
                "parsed": parsed,
                "strict_match": strict_match,
                "assignment_match": assignment_flags[i],
                "assignment_matched_line": oi,
                "assignment_matched_form": output_forms[oi] if oi is not None else None,
            }
        )

    unique_gold = {normalize_form(g) for g in expected}
    unique_found = {g for g in unique_gold if g in token_norms}
    n_slots = len(expected)

    strict_recall = strict_hits / n_slots
    assignment_recall = assignment_hits / n_slots
    form_presence_recall = len(unique_found) / len(unique_gold)

    return {
        "scoring_version": SCORING_VERSION,
        "parsed_slots": parsed_slots,
        "output_forms": output_forms,
        "per_person": per_person,
        "strict_slots_correct": strict_hits,
        "strict_slots_total": n_slots,
        "strict_slot_recall": round(strict_recall, 4),
        "perfect_paradigm": strict_hits == n_slots,
        "assignment_slots_correct": assignment_hits,
        "assignment_slots_total": n_slots,
        "unordered_assignment_recall": round(assignment_recall, 4),
        "unique_forms_expected": len(unique_gold),
        "unique_forms_found": len(unique_found),
        "form_presence_recall": round(form_presence_recall, 4),
        "missing": [p["expected"] for p in per_person if not p["strict_match"]],
        "correct": strict_hits == n_slots,
    }


def score_participle_form(*, expected: str, raw: str) -> dict[str, Any]:
    """Score a single-form participle call (strict first token)."""
    token = first_token(raw)
    norm = normalize_form(token)
    gold_norm = normalize_form(expected)
    correct = norm == gold_norm
    return {
        "scoring_version": SCORING_VERSION,
        "raw": raw.strip(),
        "parsed_token": token,
        "strict_slots_correct": 1 if correct else 0,
        "strict_slots_total": 1,
        "strict_slot_recall": 1.0 if correct else 0.0,
        "perfect_paradigm": correct,
        "assignment_slots_correct": 1 if correct else 0,
        "assignment_slots_total": 1,
        "unordered_assignment_recall": 1.0 if correct else 0.0,
        "unique_forms_expected": 1,
        "unique_forms_found": 1 if correct else 0,
        "form_presence_recall": 1.0 if correct else 0.0,
        "correct": correct,
    }
