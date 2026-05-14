"""Load a benchmark definition from a YAML file into the database.

Usage (as a module):
    python -m research.benchmarks.loader research/benchmarks/spanish_basic.yaml

Idempotent: if a benchmark with the same name already exists, the existing
record is returned and no rows are inserted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from research.db.models import Benchmark, ConstraintSet


_REQUIRED_CS_FIELDS = ("keyword", "translation", "tense", "person", "number")


def _validate_raw(data: dict[str, Any], path: Path) -> None:
    """Raise on missing or invalid top-level fields."""
    for field in ("name", "language", "constraint_sets"):
        if field not in data:
            raise ValueError(f"Benchmark YAML {path} missing required field: {field}")

    cs_list = data["constraint_sets"]
    if not isinstance(cs_list, list) or len(cs_list) == 0:
        raise ValueError(f"Benchmark YAML {path}: constraint_sets must be a non-empty list")

    for i, cs in enumerate(cs_list):
        for req in _REQUIRED_CS_FIELDS:
            if req not in cs:
                raise ValueError(
                    f"Benchmark YAML {path}: constraint_sets[{i}] missing required field: {req}"
                )


def load_benchmark(session: Session, path: str | Path) -> Benchmark:
    """Parse *path* and insert a Benchmark with its ConstraintSets.

    Returns the existing Benchmark if one with the same name is already present.
    """
    path = Path(path)
    with open(path) as f:
        data: dict[str, Any] = yaml.safe_load(f)

    _validate_raw(data, path)

    existing = session.query(Benchmark).filter_by(name=data["name"]).first()
    if existing is not None:
        return existing

    language = data["language"]

    benchmark = Benchmark(
        name=data["name"],
        language=language,
        description=data.get("description"),
    )
    session.add(benchmark)
    session.flush()

    for cs_data in data["constraint_sets"]:
        session.add(ConstraintSet(
            benchmark_id=benchmark.id,
            keyword=cs_data["keyword"],
            translation=cs_data["translation"],
            tense=cs_data["tense"],
            person=cs_data["person"],
            number=cs_data["number"],
            target_language=cs_data.get("target_language", language),
            cefr_level=cs_data.get("cefr_level"),
            extra_constraints=cs_data.get("extra_constraints"),
        ))

    session.commit()
    return benchmark


def main() -> None:
    import argparse

    from research.db.database import SessionLocal, init_db

    parser = argparse.ArgumentParser(description="Load a benchmark YAML into the database")
    parser.add_argument("path", type=str, help="Path to benchmark YAML file")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        bm = load_benchmark(session, args.path)
        print(f"Benchmark '{bm.name}' (id={bm.id}): "
              f"{len(bm.constraint_sets)} constraint sets")
    finally:
        session.close()


if __name__ == "__main__":
    main()
