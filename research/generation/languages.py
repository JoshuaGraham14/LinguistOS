"""Per-language constraint schemas for prompt building and benchmark validation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_LANGUAGES_DIR = Path(__file__).resolve().parents[1] / "languages"
_DEFAULT_REQUIRED = ("tense", "person", "number")

# Benchmark YAML keys that are not morpho-syntactic constraints.
SCAFFOLD_KEYS = frozenset({
    "keyword",
    "expected_form",
    "translation",
    "cefr_level",
    "target_language",
})


def format_constraint_value(value: str) -> str:
    """Default display for a constraint value (snake_case → Title Case)."""
    if value in ("1st", "2nd", "3rd"):
        return value
    return value.replace("_", " ").title()


@dataclass(frozen=True)
class LanguageProfile:
    code: str
    name: str
    dimensions: dict[str, tuple[str, ...]]
    labels: dict[str, str]
    glosses: dict[str, dict[str, str]]
    required: tuple[str, ...]

    def label_for(self, field: str) -> str:
        if field in self.labels:
            return self.labels[field]
        return field.replace("_", " ").title()

    def gloss_for(self, field: str, value: str) -> str:
        field_glosses = self.glosses.get(field, {})
        if value in field_glosses:
            return field_glosses[value]
        return format_constraint_value(value)

    def dimension_fields(self) -> tuple[str, ...]:
        return tuple(self.dimensions.keys())

    def validate(
        self,
        constraints: dict[str, Any],
        *,
        path_hint: str = "",
    ) -> None:
        prefix = f"{path_hint}: " if path_hint else ""
        is_participle = str(constraints.get("tense", "")) == "participle"
        required_fields = self.required
        if is_participle:
            # Past-participle cells are lemma × tense only (no person/number).
            required_fields = tuple(f for f in self.required if f not in ("person", "number"))
            for banned in ("person", "number"):
                if banned in constraints:
                    raise ValueError(
                        f"{prefix}participle cells must not include '{banned}' "
                        f"for language '{self.code}'"
                    )
        for field in required_fields:
            if field not in constraints:
                raise ValueError(
                    f"{prefix}missing required constraint '{field}' for language '{self.code}'"
                )
        for field, value in constraints.items():
            if field not in self.dimensions:
                allowed = ", ".join(sorted(self.dimensions))
                raise ValueError(
                    f"{prefix}unknown constraint field '{field}' for language "
                    f"'{self.code}'. Allowed fields: {allowed}."
                )
            allowed_values = self.dimensions[field]
            str_value = str(value)
            if str_value not in allowed_values:
                allowed_list = ", ".join(allowed_values)
                raise ValueError(
                    f"{prefix}invalid value {str_value!r} for field '{field}' in language "
                    f"'{self.code}'. Allowed: {allowed_list}."
                )


def _parse_profile(data: dict[str, Any], path: Path) -> LanguageProfile:
    for key in ("code", "name", "dimensions"):
        if key not in data:
            raise ValueError(f"Language profile {path} missing required field: {key}")
    dimensions_raw = data["dimensions"]
    if not isinstance(dimensions_raw, dict) or not dimensions_raw:
        raise ValueError(f"Language profile {path}: dimensions must be a non-empty mapping")
    dimensions: dict[str, tuple[str, ...]] = {}
    for field, values in dimensions_raw.items():
        if not isinstance(values, list) or not values:
            raise ValueError(
                f"Language profile {path}: dimensions.{field} must be a non-empty list"
            )
        dimensions[field] = tuple(str(v) for v in values)
    labels = data.get("labels") or {}
    glosses = data.get("glosses") or {}
    required = tuple(data.get("required") or _DEFAULT_REQUIRED)
    return LanguageProfile(
        code=str(data["code"]),
        name=str(data["name"]),
        dimensions=dimensions,
        labels={str(k): str(v) for k, v in labels.items()},
        glosses={
            str(f): {str(k): str(v) for k, v in field_map.items()}
            for f, field_map in glosses.items()
        },
        required=required,
    )


@lru_cache(maxsize=None)
def load_language_profile(code: str) -> LanguageProfile:
    """Load and cache a language profile by code."""
    path = _LANGUAGES_DIR / f"{code}.yaml"
    if not path.exists():
        raise ValueError(f"No language profile for '{code}' at {path}")
    with open(path) as f:
        data = yaml.safe_load(f)
    return _parse_profile(data, path)


def extract_constraints(cs_data: dict[str, Any]) -> dict[str, Any]:
    """Pull constraint fields from a flat benchmark constraint-set dict."""
    return {
        k: v
        for k, v in cs_data.items()
        if k not in SCAFFOLD_KEYS and v is not None
    }
