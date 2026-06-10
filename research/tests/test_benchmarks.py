"""Tests for benchmark YAML loading and idempotency."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from research.benchmarks.loader import load_benchmark, _validate_raw
from research.db.models import Benchmark, ConstraintSet


@pytest.fixture
def yaml_path(tmp_path) -> Path:
    """Write a minimal valid benchmark YAML and return its path."""
    p = tmp_path / "test_bench.yaml"
    p.write_text(textwrap.dedent("""\
        name: test_bench
        language: es
        description: "A test benchmark"
        constraint_sets:
          - keyword: comer
            expected_form: comimos
            translation: to eat
            tense: preterite
            person: 1st
            number: plural
          - keyword: vivir
            expected_form: vivirá
            translation: to live
            tense: future
            person: 3rd
            number: singular
            cefr_level: B1
    """))
    return p


def test_load_benchmark_creates_rows(session, yaml_path):
    bm = load_benchmark(session, yaml_path)

    assert bm.name == "test_bench"
    assert bm.language == "es"
    assert bm.description == "A test benchmark"

    cs_rows = session.query(ConstraintSet).filter_by(benchmark_id=bm.id).all()
    assert len(cs_rows) == 2
    keywords = {cs.keyword for cs in cs_rows}
    assert keywords == {"comer", "vivir"}


def test_load_benchmark_sets_target_language_from_benchmark(session, yaml_path):
    bm = load_benchmark(session, yaml_path)
    cs_rows = session.query(ConstraintSet).filter_by(benchmark_id=bm.id).all()
    for cs in cs_rows:
        assert cs.target_language == "es"


def test_load_benchmark_passes_cefr_level(session, yaml_path):
    bm = load_benchmark(session, yaml_path)
    vivir = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="vivir"
    ).one()
    assert vivir.cefr_level == "B1"

    comer = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="comer"
    ).one()
    assert comer.cefr_level is None


def test_load_benchmark_passes_expected_form(session, yaml_path):
    bm = load_benchmark(session, yaml_path)

    comer = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="comer"
    ).one()
    assert comer.expected_form == "comimos"

    vivir = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="vivir"
    ).one()
    assert vivir.expected_form == "vivirá"


def test_load_benchmark_mock_only(session, tmp_path):
    p = tmp_path / "fixture.yaml"
    p.write_text(textwrap.dedent("""\
        name: fixture_bench
        language: es
        mock_only: true
        constraint_sets:
          - keyword: comer
            expected_form: comimos
            translation: to eat
            tense: preterite
            person: 1st
            number: plural
    """))
    bm = load_benchmark(session, p)
    assert bm.mock_only is True


def test_load_benchmark_syncs_mock_only_on_reload(session, tmp_path):
    p = tmp_path / "toggle.yaml"
    p.write_text(textwrap.dedent("""\
        name: toggle_bench
        language: es
        mock_only: true
        constraint_sets:
          - keyword: comer
            expected_form: comimos
            translation: to eat
            tense: preterite
            person: 1st
            number: plural
    """))
    bm = load_benchmark(session, p)
    assert bm.mock_only is True

    bm.mock_only = False
    session.commit()

    reloaded = load_benchmark(session, p)
    assert reloaded.id == bm.id
    assert reloaded.mock_only is True


def test_load_benchmark_syncs_expected_form_on_reload(session, yaml_path):
    bm = load_benchmark(session, yaml_path)
    comer = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="comer"
    ).one()
    comer.expected_form = None
    session.commit()

    reloaded = load_benchmark(session, yaml_path)
    assert reloaded.id == bm.id

    comer = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="comer"
    ).one()
    assert comer.expected_form == "comimos"


def test_load_benchmark_idempotent(session, yaml_path):
    first = load_benchmark(session, yaml_path)
    second = load_benchmark(session, yaml_path)

    assert first.id == second.id
    assert session.query(Benchmark).count() == 1
    assert session.query(ConstraintSet).count() == 2


def test_load_benchmark_per_set_language_override(session, tmp_path):
    p = tmp_path / "override.yaml"
    p.write_text(textwrap.dedent("""\
        name: override_lang
        language: es
        constraint_sets:
          - keyword: manger
            translation: to eat
            tense: present
            person: 1st
            number: singular
            target_language: fr
    """))
    bm = load_benchmark(session, p)
    cs = session.query(ConstraintSet).filter_by(benchmark_id=bm.id).one()
    assert cs.target_language == "fr"


# ── Validation ──────────────────────────────────────────────────────────────


def test_validate_missing_name(tmp_path):
    with pytest.raises(ValueError, match="missing required field: name"):
        _validate_raw({"language": "es", "constraint_sets": [{}]}, tmp_path / "x.yaml")


def test_validate_missing_language(tmp_path):
    with pytest.raises(ValueError, match="missing required field: language"):
        _validate_raw({"name": "x", "constraint_sets": [{}]}, tmp_path / "x.yaml")


def test_validate_empty_constraint_sets(tmp_path):
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_raw({"name": "x", "language": "es", "constraint_sets": []}, tmp_path / "x.yaml")


def test_validate_missing_constraint_field(tmp_path):
    data = {
        "name": "x",
        "language": "es",
        "constraint_sets": [{"keyword": "comer"}],
    }
    with pytest.raises(ValueError, match="constraint_sets\\[0\\] missing required field"):
        _validate_raw(data, tmp_path / "x.yaml")


def test_validate_rejects_invalid_tense_for_language(tmp_path):
    p = tmp_path / "bad_he.yaml"
    data = {
        "name": "bad_he",
        "language": "he",
        "constraint_sets": [{
            "keyword": "לשאול",
            "translation": "to ask",
            "tense": "qatal",
            "person": "1st",
            "number": "singular",
        }],
    }
    with pytest.raises(ValueError, match="invalid value 'qatal'"):
        _validate_raw(data, p)


def test_load_stores_constraints_json(session, yaml_path):
    bm = load_benchmark(session, yaml_path)
    comer = session.query(ConstraintSet).filter_by(
        benchmark_id=bm.id, keyword="comer"
    ).one()
    assert comer.constraints == {
        "tense": "preterite",
        "person": "1st",
        "number": "plural",
    }


def test_load_spanish_challenging_yaml(session):
    yaml_path = (
        Path(__file__).resolve().parent.parent / "benchmarks" / "spanish_challenging.yaml"
    )
    bm = load_benchmark(session, yaml_path)

    assert bm.name == "spanish_challenging"
    assert bm.mock_only is False
    assert len(bm.constraint_sets) == 8

    expected = {
        ("pedir", "present", "1st", "singular"): "pido",
        ("dormir", "present", "1st", "singular"): "duermo",
        ("decir", "preterite", "1st", "singular"): "dije",
        ("tener", "preterite", "3rd", "plural"): "tuvieron",
        ("conducir", "preterite", "3rd", "plural"): "condujeron",
        ("poner", "conditional", "1st", "singular"): "pondría",
        ("venir", "conditional", "1st", "singular"): "vendría",
        ("llegar", "preterite", "1st", "singular"): "llegué",
    }
    for cs in bm.constraint_sets:
        key = (cs.keyword, cs.tense, cs.person, cs.number)
        assert cs.expected_form == expected[key]


def test_load_spanish_grammar_probe_yaml(session):
    yaml_path = (
        Path(__file__).resolve().parent.parent / "benchmarks" / "spanish_grammar_probe.yaml"
    )
    bm = load_benchmark(session, yaml_path)

    assert bm.name == "spanish_grammar_probe"
    assert bm.mock_only is True
    assert len(bm.constraint_sets) == 4


def test_all_repo_benchmark_yamls_validate():
    """Every benchmark YAML in research/benchmarks/ passes schema validation."""
    bench_dir = Path(__file__).resolve().parent.parent / "benchmarks"
    for path in sorted(bench_dir.glob("*.yaml")):
        with open(path) as f:
            data = yaml.safe_load(f)
        _validate_raw(data, path)


def test_load_spanish_basic_yaml(session):
    """Smoke test: the real spanish_basic.yaml loads without errors."""
    yaml_path = Path(__file__).resolve().parent.parent / "benchmarks" / "spanish_basic.yaml"
    bm = load_benchmark(session, yaml_path)

    assert bm.name == "spanish_basic"
    assert bm.language == "es"
    assert len(bm.constraint_sets) == 5

    expected = {
        ("comer", "preterite", "1st", "plural"): "comimos",
        ("vivir", "future", "3rd", "singular"): "vivirá",
        ("hablar", "present", "2nd", "singular"): "hablas",
        ("escribir", "preterite", "3rd", "plural"): "escribieron",
        ("correr", "present", "1st", "singular"): "corro",
    }
    for cs in bm.constraint_sets:
        key = (cs.keyword, cs.tense, cs.person, cs.number)
        assert cs.expected_form == expected[key]
