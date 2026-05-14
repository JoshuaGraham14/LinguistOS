"""Tests for BaseGenerator ABC, generator registry, and config loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from research.configs.loader import load_generation_config, _validate_raw
from research.db.models import GenerationConfig
from research.generation.base import BaseGenerator
from research.generation.baseline_gpt import BaselineGPTGenerator
from research.generation.individual_gpt import IndividualGPTGenerator
from research.generation import GENERATOR_REGISTRY
from research.run_experiment import _build_generator


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
                     num_candidates, *, target_language="es", cefr_level=None):
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


def test_build_generator_from_config(session):
    gc = GenerationConfig(
        name="test_build", method="baseline_gpt", samples_per_case=3,
        config={"model": "gpt-4o-mini", "temperature": 0.5},
    )
    session.add(gc)
    session.commit()

    gen = _build_generator(gc)
    assert isinstance(gen, BaselineGPTGenerator)
    assert gen._model == "gpt-4o-mini"
    assert gen._temperature == 0.5


def test_build_generator_unknown_method(session):
    gc = GenerationConfig(
        name="bad", method="nonexistent", samples_per_case=1,
    )
    session.add(gc)
    session.commit()

    with pytest.raises(ValueError, match="Unknown generation method"):
        _build_generator(gc)


# ── Config loader ──────────────────────────────────────────────────────────


@pytest.fixture
def config_yaml_path(tmp_path) -> Path:
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


def test_load_generation_config_creates_row(session, config_yaml_path):
    gc = load_generation_config(session, config_yaml_path)
    assert gc.name == "test_cfg"
    assert gc.method == "baseline_gpt"
    assert gc.samples_per_case == 5
    assert gc.config["model"] == "gpt-4o"


def test_load_generation_config_idempotent(session, config_yaml_path):
    first = load_generation_config(session, config_yaml_path)
    second = load_generation_config(session, config_yaml_path)
    assert first.id == second.id
    assert session.query(GenerationConfig).count() == 1


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
    """Smoke test: the real baseline_default.yaml loads without errors."""
    yaml_path = Path(__file__).resolve().parent.parent / "configs" / "baseline_default.yaml"
    gc = load_generation_config(session, yaml_path)
    assert gc.name == "baseline_default"
    assert gc.method == "baseline_gpt"


def test_load_individual_default_yaml(session):
    """Smoke test: the real individual_default.yaml loads without errors."""
    yaml_path = Path(__file__).resolve().parent.parent / "configs" / "individual_default.yaml"
    gc = load_generation_config(session, yaml_path)
    assert gc.name == "individual_default"
    assert gc.method == "individual_gpt"
