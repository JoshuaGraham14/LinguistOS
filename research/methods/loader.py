"""Load a method config from a YAML file into the database.

Supports ``extends`` for shared base templates under ``methods/_base/``.
Preset files live under ``methods/baseline/`` and ``methods/individual/``;
lookup is by the YAML ``name`` field (CLI ``--method`` value), not file path.

Idempotent: if a config with the same name already exists, the existing
record is returned and no rows are inserted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from research.db.models import MethodConfig

_METHODS_ROOT = Path(__file__).resolve().parent
_REQUIRED_FIELDS = ("name", "method", "samples_per_case")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base; nested ``config`` dicts are merged shallowly."""
    merged = dict(base)
    for key, value in override.items():
        if key == "config" and isinstance(value, dict):
            parent_config = merged.get("config")
            if isinstance(parent_config, dict):
                merged["config"] = {**parent_config, **value}
            else:
                merged["config"] = dict(value)
        else:
            merged[key] = value
    return merged


def _resolve_extends_path(child_path: Path, extends: str) -> Path:
    """Resolve an ``extends`` reference relative to the child YAML file."""
    candidate = (child_path.parent / extends).resolve()
    if not str(candidate).startswith(str(_METHODS_ROOT)):
        raise ValueError(
            f"Method YAML {child_path}: extends path {extends!r} escapes methods/"
        )
    if not candidate.exists():
        raise FileNotFoundError(
            f"Method YAML {child_path}: extends file not found: {candidate}"
        )
    return candidate


def parse_method_yaml(path: str | Path) -> dict[str, Any]:
    """Load and merge a method YAML (following ``extends`` chain)."""
    path = Path(path)
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f) or {}

    extends = data.pop("extends", None)
    if extends:
        base_path = _resolve_extends_path(path, str(extends))
        base_data = parse_method_yaml(base_path)
        data = _deep_merge(base_data, data)

    return data


def _validate_raw(data: dict[str, Any], path: Path) -> None:
    """Raise on missing or invalid fields."""
    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise ValueError(f"Method YAML {path} missing required field: {field}")

    if not isinstance(data["samples_per_case"], int) or data["samples_per_case"] < 1:
        raise ValueError(f"Method YAML {path}: samples_per_case must be a positive integer")


def _iter_preset_yaml_paths(methods_dir: Path | None = None) -> list[Path]:
    """All loadable preset YAML files (excludes ``_base/`` templates)."""
    root = methods_dir or _METHODS_ROOT
    paths: list[Path] = []
    for path in sorted(root.rglob("*.yaml")):
        if "_base" in path.parts:
            continue
        paths.append(path)
    return paths


def find_method_yaml(name: str, methods_dir: Path | None = None) -> Path | None:
    """Return the preset file whose ``name`` field matches *name*."""
    for path in _iter_preset_yaml_paths(methods_dir):
        data = parse_method_yaml(path)
        if data.get("name") == name:
            return path
    return None


def load_method_config(session: Session, path: str | Path) -> MethodConfig:
    """Parse *path* and insert a MethodConfig.

    Returns the existing MethodConfig if one with the same name is present.
    """
    path = Path(path)
    data = parse_method_yaml(path)
    _validate_raw(data, path)

    existing = session.query(MethodConfig).filter_by(name=data["name"]).first()
    if existing is not None:
        return existing

    method_config = MethodConfig(
        name=data["name"],
        method=data["method"],
        samples_per_case=data["samples_per_case"],
        config=data.get("config"),
    )
    session.add(method_config)
    session.commit()
    return method_config


def load_method_config_by_name(session: Session, name: str) -> MethodConfig:
    """Resolve a preset by ``name`` and load it into the database."""
    path = find_method_yaml(name)
    if path is None:
        raise FileNotFoundError(
            f"No method preset named {name!r}. "
            f"Expected a YAML under methods/ with name: {name}"
        )
    return load_method_config(session, path)
