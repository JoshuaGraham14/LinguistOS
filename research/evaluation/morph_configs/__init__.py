"""Per-language morphology configs that map benchmark terms to UD features.

Adding a new language is purely additive: drop a `<lang>.yaml` next to this file
with the same keys as `es.yaml`. Evaluator code stays unchanged.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent
_REQUIRED_KEYS = ("parser", "model", "pos_filter", "tense_map", "person_map", "number_map")


def _validate(language: str, data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"Morph config for '{language}' must be a mapping")
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"Morph config for '{language}' missing required keys: {', '.join(missing)}"
        )
    if not isinstance(data["pos_filter"], list) or not data["pos_filter"]:
        raise ValueError(f"Morph config for '{language}': pos_filter must be a non-empty list")
    for map_name in ("tense_map", "person_map", "number_map"):
        if not isinstance(data[map_name], dict) or not data[map_name]:
            raise ValueError(
                f"Morph config for '{language}': {map_name} must be a non-empty mapping"
            )


@lru_cache(maxsize=None)
def load_morph_config(language: str) -> dict[str, Any]:
    """Return the validated morph config dict for *language*.

    Raises ``ValueError`` if no config exists or required keys are missing.
    Results are cached per process.
    """
    path = _CONFIG_DIR / f"{language}.yaml"
    if not path.exists():
        raise ValueError(f"No morph config for language '{language}' at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    _validate(language, data)
    return data
