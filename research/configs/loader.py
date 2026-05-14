"""Load a generation config from a YAML file into the database.

Idempotent: if a config with the same name already exists, the existing
record is returned and no rows are inserted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from research.db.models import GenerationConfig


_REQUIRED_FIELDS = ("name", "method", "samples_per_case")


def _validate_raw(data: dict[str, Any], path: Path) -> None:
    """Raise on missing or invalid fields."""
    for field in _REQUIRED_FIELDS:
        if field not in data:
            raise ValueError(f"Config YAML {path} missing required field: {field}")

    if not isinstance(data["samples_per_case"], int) or data["samples_per_case"] < 1:
        raise ValueError(f"Config YAML {path}: samples_per_case must be a positive integer")


def load_generation_config(session: Session, path: str | Path) -> GenerationConfig:
    """Parse *path* and insert a GenerationConfig.

    Returns the existing GenerationConfig if one with the same name is present.
    """
    path = Path(path)
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    _validate_raw(data, path)

    existing = session.query(GenerationConfig).filter_by(name=data["name"]).first()
    if existing is not None:
        return existing

    gen_config = GenerationConfig(
        name=data["name"],
        method=data["method"],
        samples_per_case=data["samples_per_case"],
        config=data.get("config"),
    )
    session.add(gen_config)
    session.commit()
    return gen_config
