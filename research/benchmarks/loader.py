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


def _constraint_set_key(cs: dict[str, Any]) -> tuple[str, str, str, str]:
    return (cs["keyword"], cs["tense"], cs["person"], cs["number"])


def _mock_only_from_yaml(data: dict[str, Any]) -> bool:
    return bool(data.get("mock_only", False))


def _sync_mock_only(
    session: Session,
    benchmark: Benchmark,
    data: dict[str, Any],
) -> None:
    """Update mock_only when YAML flag changes."""
    mock_only = _mock_only_from_yaml(data)
    if benchmark.mock_only != mock_only:
        benchmark.mock_only = mock_only
        session.commit()


def _sync_expected_forms(
    session: Session,
    benchmark: Benchmark,
    cs_list: list[dict[str, Any]],
) -> None:
    """Update expected_form on existing rows when YAML provides gold labels."""
    by_key = {
        (cs.keyword, cs.tense, cs.person, cs.number): cs
        for cs in benchmark.constraint_sets
    }
    changed = False
    for cs_data in cs_list:
        expected = cs_data.get("expected_form")
        if not expected:
            continue
        row = by_key.get(_constraint_set_key(cs_data))
        if row is not None and row.expected_form != expected:
            row.expected_form = expected
            changed = True
    if changed:
        session.commit()


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
        _sync_mock_only(session, existing, data)
        _sync_expected_forms(session, existing, data["constraint_sets"])
        return existing

    language = data["language"]

    benchmark = Benchmark(
        name=data["name"],
        language=language,
        description=data.get("description"),
        mock_only=_mock_only_from_yaml(data),
    )
    session.add(benchmark)
    session.flush()

    for cs_data in data["constraint_sets"]:
        session.add(ConstraintSet.from_yaml_dict(
            benchmark_id=benchmark.id,
            cs_data=cs_data,
            default_language=language,
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
