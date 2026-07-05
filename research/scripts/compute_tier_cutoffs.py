"""Print frozen TIER_CUTOFFS from the committed verb census metadata.

Reads ``research/evaluation/lexicon/census/{lang}_meta.yaml`` produced by
``research/scripts/build_verb_census.py``.

Usage::

    python -m research.scripts.compute_tier_cutoffs
"""

from __future__ import annotations

from pathlib import Path

import yaml

CENSUS_DIR = Path(__file__).resolve().parents[1] / "evaluation" / "lexicon" / "census"


def main() -> None:
    print("TIER_CUTOFFS: dict[str, tuple[float, float]] = {")
    for lang in ("es", "en"):
        meta_path = CENSUS_DIR / f"{lang}_meta.yaml"
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        cut = meta["tier_cutoffs"]
        low_upper = cut["low_upper"]
        high_lower = cut["high_lower"]
        print(
            f'    "{lang}": ({low_upper}, {high_lower}),  '
            f"# n={meta['n_verbs']}, min={meta['zipf_min']}, max={meta['zipf_max']}, "
            f"mean={meta['zipf_mean']}"
        )
    print("}")


if __name__ == "__main__":
    main()
