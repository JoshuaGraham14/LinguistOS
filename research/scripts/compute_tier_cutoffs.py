"""Compute per-language 33rd / 67th percentile Zipf-lemma cutoffs.

Runs over the reference verb-lemma lists in
``research/evaluation/lexicon/reference_lemmas/{lang}.txt`` and prints
``TIER_CUTOFFS`` values ready to be pasted into
``research/evaluation/lexicon/frequency.py``.

Freezing the printed values in source is the pre-registration ritual:
tiers are then defined by the reference distribution at the time of freezing,
not re-derived each run.

Usage
-----
::

    python -m research.scripts.compute_tier_cutoffs
"""

from __future__ import annotations

import logging
import statistics
from pathlib import Path

logging.getLogger("verbecc").setLevel(logging.WARNING)

REF_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "lexicon" / "reference_lemmas"


def _quantile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolation quantile; matches numpy's default."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    idx = q * (len(sorted_values) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = idx - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def main() -> None:
    from research.evaluation.lexicon.frequency import verb_zipf

    print("TIER_CUTOFFS: dict[str, tuple[float, float]] = {")
    for lang in ("es", "en"):
        path = REF_DIR / f"{lang}.txt"
        lemmas = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        scores = sorted(verb_zipf(v, lang) for v in lemmas)

        p33 = _quantile(scores, 1 / 3)
        p67 = _quantile(scores, 2 / 3)
        mean = statistics.fmean(scores)
        median = statistics.median(scores)

        print(f'    "{lang}": ({p33:.3f}, {p67:.3f}),  # n={len(scores)} '
              f'mean={mean:.2f} median={median:.2f} '
              f'min={min(scores):.2f} max={max(scores):.2f}')
    print("}")


if __name__ == "__main__":
    main()
