"""Few-shot exemplar pool: loading, selection, and prompt formatting.

Direction 5 (in-context learning). Two selection strategies:

* **static**  — a fixed set of K demonstrations spread across tenses, shown
  on every prompt regardless of the target cell. Simple and fully
  reproducible; the model never sees the target tense specifically.
* **dynamic** — K demonstrations whose tense matches the target cell's
  tense (back-filled from other tenses only if the pool is short). Teaches
  the exact morphological pattern being requested.

The pool is disjoint from the smoke5 test verbs, and any exemplar sharing
the target verb is dropped, so a demonstration can never leak the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POOL_PATH = (
    Path(__file__).resolve().parent
    / "fewshot_exemplars"
    / "spanish_fewshot_pool.yaml"
)

# Fixed tense order for round-robin static selection and stable ordering.
_TENSE_ORDER: tuple[str, ...] = (
    "present",
    "preterite",
    "imperfect",
    "future",
    "conditional",
    "participle",
)

_TENSE_GLOSS: dict[str, str] = {
    "present": "present tense",
    "preterite": "preterite (simple past) tense",
    "imperfect": "imperfect (past habitual) tense",
    "future": "future tense",
    "conditional": "conditional tense",
    "participle": "past participle",
}

_PERSON_GLOSS: dict[tuple[str, str], str] = {
    ("1st", "singular"): "1st person singular",
    ("2nd", "singular"): "2nd person singular",
    ("3rd", "singular"): "3rd person singular",
    ("1st", "plural"): "1st person plural",
    ("2nd", "plural"): "2nd person plural",
    ("3rd", "plural"): "3rd person plural",
}


@dataclass(frozen=True)
class Exemplar:
    """One worked demonstration: a morphology cell and its natural sentence."""

    verb: str
    translation: str
    tense: str
    sentence: str
    expected_form: str
    person: str | None = None
    number: str | None = None

    def morph_label(self) -> str:
        """Human-readable gloss of the grammatical target for the prompt."""
        if self.tense == "participle" or not (self.person and self.number):
            return _TENSE_GLOSS.get(self.tense, self.tense)
        slot = _PERSON_GLOSS.get(
            (self.person, self.number), f"{self.person} {self.number}"
        )
        return f"{_TENSE_GLOSS.get(self.tense, self.tense)}, {slot}"


def _tense_rank(tense: str) -> int:
    try:
        return _TENSE_ORDER.index(tense)
    except ValueError:
        return len(_TENSE_ORDER)


@lru_cache(maxsize=8)
def load_exemplar_pool(path: str | None = None) -> tuple[Exemplar, ...]:
    """Load exemplars from *path* (defaults to the bundled Spanish pool)."""
    pool_path = Path(path) if path else DEFAULT_POOL_PATH
    with pool_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    raw = data.get("exemplars", [])
    pool: list[Exemplar] = []
    for item in raw:
        pool.append(
            Exemplar(
                verb=str(item["verb"]).strip(),
                translation=str(item.get("translation", "")).strip(),
                tense=str(item["tense"]).strip(),
                sentence=str(item["sentence"]).strip(),
                expected_form=str(item.get("expected_form", "")).strip(),
                person=(str(item["person"]).strip() if item.get("person") else None),
                number=(str(item["number"]).strip() if item.get("number") else None),
            )
        )
    return tuple(pool)


def _eligible(pool: tuple[Exemplar, ...], exclude_verb: str | None) -> list[Exemplar]:
    """Drop exemplars sharing the target verb (leakage guard)."""
    if not exclude_verb:
        return list(pool)
    key = exclude_verb.strip().casefold()
    return [ex for ex in pool if ex.verb.casefold() != key]


def select_static(
    pool: tuple[Exemplar, ...],
    k: int,
    *,
    exclude_verb: str | None = None,
) -> list[Exemplar]:
    """Fixed K demonstrations spread across tenses (round-robin, deterministic).

    The same K exemplars are returned for every cell (target verb aside), so
    the demonstration block is constant across the whole benchmark.
    """
    eligible = _eligible(pool, exclude_verb)
    by_tense: dict[str, list[Exemplar]] = {}
    for ex in eligible:
        by_tense.setdefault(ex.tense, []).append(ex)
    ordered_tenses = sorted(by_tense, key=_tense_rank)
    picked: list[Exemplar] = []
    depth = 0
    while len(picked) < k and ordered_tenses:
        progressed = False
        for tense in ordered_tenses:
            bucket = by_tense[tense]
            if depth < len(bucket):
                picked.append(bucket[depth])
                progressed = True
                if len(picked) >= k:
                    break
        if not progressed:
            break
        depth += 1
    return picked[:k]


def select_dynamic(
    pool: tuple[Exemplar, ...],
    constraints: dict[str, Any],
    k: int,
    *,
    exclude_verb: str | None = None,
) -> list[Exemplar]:
    """K demonstrations matching the target tense, back-filled if short.

    Matching-tense exemplars come first (in pool order, which is person-
    ordered); if fewer than K exist, the remainder is filled from other
    tenses in a stable order. Deterministic.
    """
    eligible = _eligible(pool, exclude_verb)
    target_tense = str(constraints.get("tense") or "").strip()
    matching = [ex for ex in eligible if ex.tense == target_tense]
    others = [ex for ex in eligible if ex.tense != target_tense]
    others.sort(key=lambda ex: (_tense_rank(ex.tense), ex.verb))
    return (matching + others)[:k]


def select_exemplars(
    pool: tuple[Exemplar, ...],
    mode: str,
    k: int,
    *,
    constraints: dict[str, Any] | None = None,
    exclude_verb: str | None = None,
) -> list[Exemplar]:
    """Dispatch to the static or dynamic selection strategy."""
    if mode == "static":
        return select_static(pool, k, exclude_verb=exclude_verb)
    if mode == "dynamic":
        return select_dynamic(
            pool, constraints or {}, k, exclude_verb=exclude_verb
        )
    raise ValueError(f"Unknown few-shot mode: {mode!r} (expected static|dynamic)")


def format_demonstration_block(exemplars: list[Exemplar]) -> str:
    """Render selected exemplars as a labelled preamble for the prompt."""
    if not exemplars:
        return ""
    lines = [
        "Study these worked examples of the task, then complete the final "
        "request below.",
        "",
    ]
    for idx, ex in enumerate(exemplars, start=1):
        gloss = ex.morph_label()
        verb_gloss = (
            f"{ex.verb} (to {ex.translation})"
            if ex.translation and not ex.translation.startswith("to ")
            else f"{ex.verb} ({ex.translation})"
        )
        lines.append(f"Example {idx} — {verb_gloss}, {gloss}:")
        lines.append(ex.sentence)
        lines.append("")
    lines.append("---")
    return "\n".join(lines).strip()
