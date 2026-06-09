"""Tests for BaseGenerator ABC, generator registry, and method config loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from research.methods.loader import load_method_config, _validate_raw
from research.db.models import MethodConfig
from research.generation.base import BaseGenerator
from research.generation.baseline_gpt import BaselineGPTGenerator
from research.generation.individual_gpt import IndividualGPTGenerator
from research.generation import GENERATOR_REGISTRY
from research.methods.run_config import MethodRunConfig
from research.pipeline import _build_generator


# ── BaseGenerator ABC ──────────────────────────────────────────────────────


def test_cannot_instantiate_base_generator():
    with pytest.raises(TypeError):
        BaseGenerator()


def test_concrete_subclass_works():
    class Dummy(BaseGenerator):
        @property
        def name(self):
            return "dummy"

        def generate(self, keyword, translation, tense, person, number,
                     num_candidates, *, target_language="es", cefr_level=None,
                     sentence_length="short"):
            return [{"sentence": "Hola.", "translation": "Hello."}]

    gen = Dummy()
    assert gen.name == "dummy"
    result = gen.generate("x", "y", "present", "1st", "singular", 1)
    assert len(result) == 1


# ── Generator classes ──────────────────────────────────────────────────────


def test_baseline_generator_name():
    gen = BaselineGPTGenerator()
    assert gen.name == "baseline_gpt"


def test_individual_generator_name():
    gen = IndividualGPTGenerator()
    assert gen.name == "individual_gpt"


def test_baseline_generator_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gen = BaselineGPTGenerator()
    result = gen.generate("comer", "to eat", "past", "1st", "plural", 3)
    assert result == []


def test_individual_generator_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gen = IndividualGPTGenerator()
    result = gen.generate("comer", "to eat", "past", "1st", "plural", 3)
    assert result == []


# ── Registry ───────────────────────────────────────────────────────────────


def test_registry_contains_both_methods():
    assert "baseline_gpt" in GENERATOR_REGISTRY
    assert "individual_gpt" in GENERATOR_REGISTRY


def test_build_generator_from_method_config(session):
    mc = MethodConfig(
        name="test_build", method="baseline_gpt", samples_per_case=3,
        config={"model": "gpt-4o-mini", "temperature": 0.5},
    )
    session.add(mc)
    session.commit()

    gen = _build_generator(MethodRunConfig.from_method_config(mc), mc)
    assert isinstance(gen, BaselineGPTGenerator)
    assert gen._model == "gpt-4o-mini"
    assert gen._temperature == 0.5


def test_build_generator_unknown_method(session):
    mc = MethodConfig(
        name="bad", method="nonexistent", samples_per_case=1,
    )
    session.add(mc)
    session.commit()

    with pytest.raises(ValueError, match="Unknown generation method"):
        _build_generator(MethodRunConfig.from_method_config(mc), mc)


# ── Method config loader ───────────────────────────────────────────────────


@pytest.fixture
def method_yaml_path(tmp_path) -> Path:
    p = tmp_path / "test_cfg.yaml"
    p.write_text(textwrap.dedent("""\
        name: test_cfg
        method: baseline_gpt
        samples_per_case: 5
        config:
          model: gpt-4o
          temperature: 0.7
    """))
    return p


def test_load_method_config_creates_row(session, method_yaml_path):
    mc = load_method_config(session, method_yaml_path)
    assert mc.name == "test_cfg"
    assert mc.method == "baseline_gpt"
    assert mc.samples_per_case == 5
    assert mc.config["model"] == "gpt-4o"


def test_load_method_config_idempotent(session, method_yaml_path):
    first = load_method_config(session, method_yaml_path)
    second = load_method_config(session, method_yaml_path)
    assert first.id == second.id
    assert session.query(MethodConfig).count() == 1


def test_validate_missing_name(tmp_path):
    with pytest.raises(ValueError, match="missing required field: name"):
        _validate_raw({"method": "x", "samples_per_case": 1}, tmp_path / "x.yaml")


def test_validate_missing_method(tmp_path):
    with pytest.raises(ValueError, match="missing required field: method"):
        _validate_raw({"name": "x", "samples_per_case": 1}, tmp_path / "x.yaml")


def test_validate_bad_samples(tmp_path):
    with pytest.raises(ValueError, match="positive integer"):
        _validate_raw({"name": "x", "method": "y", "samples_per_case": 0}, tmp_path / "x.yaml")


def test_load_baseline_default_yaml(session):
    """Smoke test: the real baseline_default preset loads without errors."""
    yaml_path = Path(__file__).resolve().parent.parent / "methods" / "baseline" / "default.yaml"
    mc = load_method_config(session, yaml_path)
    assert mc.name == "baseline_default"
    assert mc.method == "baseline_gpt"
    assert mc.config["sentence_length"] == "short"


def test_load_individual_default_yaml(session):
    """Smoke test: the real individual_default preset loads without errors."""
    yaml_path = Path(__file__).resolve().parent.parent / "methods" / "individual" / "default.yaml"
    mc = load_method_config(session, yaml_path)
    assert mc.name == "individual_default"
    assert mc.method == "individual_gpt"


def test_parse_method_yaml_extends_merges_config():
    from research.methods.loader import parse_method_yaml

    path = Path(__file__).resolve().parent.parent / "methods" / "baseline" / "long_explicit.yaml"
    data = parse_method_yaml(path)
    assert data["name"] == "baseline_long_explicit"
    assert data["method"] == "baseline_gpt"
    assert data["config"]["model"] == "gpt-5.4-nano"
    assert data["config"]["sentence_length"] == "long"
    assert data["config"]["explicit_subject_required"] is True


def test_find_method_yaml_by_name():
    from research.methods.loader import find_method_yaml

    path = find_method_yaml("individual_random")
    assert path is not None
    assert path.name == "random.yaml"
