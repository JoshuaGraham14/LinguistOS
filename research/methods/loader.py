"""Load a method config from a YAML file into the database.

Preset files live under ``methods/baseline/`` and ``methods/individual/``.
Lookup is by the YAML ``name`` field (CLI ``--method`` value), not file path.

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


def parse_method_yaml(path: str | Path) -> dict[str, Any]:
    """Load a method preset YAML."""
    path = Path(path)
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _validate_raw(data: dict[str, Any], path: Path) -> None:
    """Raise on missing or invalid fields."""
    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise ValueError(f"Method YAML {path} missing required field: {field}")

    if not isinstance(data["samples_per_case"], int) or data["samples_per_case"] < 1:
        raise ValueError(f"Method YAML {path}: samples_per_case must be a positive integer")


def _iter_preset_yaml_paths(methods_dir: Path | None = None) -> list[Path]:
    """All preset YAML files under ``methods/baseline/`` and ``methods/individual/``."""
    root = methods_dir or _METHODS_ROOT
    paths: list[Path] = []
    for subdir in ("baseline", "individual"):
        folder = root / subdir
        if folder.is_dir():
            paths.extend(sorted(folder.glob("*.yaml")))
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
            f"Expected a YAML under methods/baseline/ or methods/individual/ "
            f"with name: {name}"
        )
    return load_method_config(session, path)
