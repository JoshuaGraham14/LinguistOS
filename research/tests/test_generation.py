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

        def generate(self, keyword, translation, constraints,
                     num_candidates, *, target_language="es", cefr_level=None,
                     sentence_length="short", explicit_subject_required=False):
            return [{"sentence": "Hola.", "translation": "Hello."}]

    gen = Dummy()
    assert gen.name == "dummy"
    result = gen.generate(
        "x", "y", {"tense": "present", "person": "1st", "number": "singular"}, 1
    )
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
    result = gen.generate(
        "comer",
        "to eat",
        {"tense": "preterite", "person": "1st", "number": "plural"},
        3,
    )
    assert result == []


def test_individual_generator_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    gen = IndividualGPTGenerator()
    result = gen.generate(
        "comer",
        "to eat",
        {"tense": "preterite", "person": "1st", "number": "plural"},
        3,
    )
    assert result == []


# ── Registry ───────────────────────────────────────────────────────────────


def test_registry_contains_both_methods():
    assert "baseline_gpt" in GENERATOR_REGISTRY
    assert "individual_gpt" in GENERATOR_REGISTRY
    assert "baseline_hf" in GENERATOR_REGISTRY
    assert "baseline_hf_form_injected" in GENERATOR_REGISTRY
    assert "baseline_hf_form_injected_explicit" in GENERATOR_REGISTRY
    assert "baseline_hf_form_injected_plain" in GENERATOR_REGISTRY
    assert "constrained_hf_hard_plain" in GENERATOR_REGISTRY
    assert "constrained_hf_soft_json" in GENERATOR_REGISTRY


def test_baseline_hf_greedy_at_zero_temperature():
    from research.generation.baseline_hf import _sample_kwargs

    assert _sample_kwargs(0.0) == {"do_sample": False}
    assert _sample_kwargs(0.7)["do_sample"] is True
    assert _sample_kwargs(0.7)["temperature"] == 0.7


def test_build_generator_passes_beam_config(session):
    mc = MethodConfig(
        name="test_constrained",
        method="constrained_hf_hard_plain",
        samples_per_case=1,
        config={
            "model": "Qwen/Qwen3-1.7B",
            "temperature": 0,
            "num_beams": 4,
            "bias_strength": 5.0,
        },
    )
    session.add(mc)
    session.commit()

    gen = _build_generator(MethodRunConfig.from_method_config(mc), mc)
    from research.generation.constrained_hf import ConstrainedHFHardPlainGenerator

    assert isinstance(gen, ConstrainedHFHardPlainGenerator)
    assert gen._num_beams == 4
    assert gen._bias_strength == 5.0


def test_form_injected_explicit_hf_prompt_uses_overlay_and_injection():
    from research.generation.baseline_hf import FormInjectedExplicitHFGenerator

    gen = FormInjectedExplicitHFGenerator()
    prompt = gen._build_user_prompt(
        keyword="comer",
        translation="to eat",
        target_language="es",
        constraints={
            "tense": "preterite",
            "person": "1st",
            "number": "plural",
            "expected_form": "comimos",
        },
        num_candidates=10,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form="comimos",
    )
    assert "Required surface form" in prompt
    assert '"comimos"' in prompt
    assert "Additional requirements:" in prompt
    assert "nosotros" in prompt


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


def test_parse_method_yaml_loads_full_preset():
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


def test_generate_chat_batch_chunks_requests(monkeypatch):
    from research.generation.baseline_hf import ChatGenerationSpec, generate_chat_batch

    calls: list[int] = []
    counter = {"n": 0}

    def fake_once(model_id, specs, *, temperature):
        calls.append(len(specs))
        out = []
        for _ in specs:
            out.append(f"out-{counter['n']}")
            counter["n"] += 1
        return out

    monkeypatch.setattr(
        "research.generation.baseline_hf._generate_chat_batch_once",
        fake_once,
    )

    specs = [
        ChatGenerationSpec(system="sys", user=f"u{i}", max_new_tokens=32)
        for i in range(5)
    ]
    out = generate_chat_batch("fake-model", specs, batch_size=2)

    assert out == ["out-0", "out-1", "out-2", "out-3", "out-4"]
    assert calls == [2, 2, 1]


def test_generate_chat_batch_rejects_non_positive_batch_size():
    from research.generation.baseline_hf import ChatGenerationSpec, generate_chat_batch

    with pytest.raises(ValueError, match="batch_size must be positive"):
        generate_chat_batch(
            "fake-model",
            [ChatGenerationSpec(system="s", user="u", max_new_tokens=8)],
            batch_size=0,
        )


def test_resolve_hf_batch_size_prefers_env(monkeypatch):
    from research.generation.cluster_batch_sizes import resolve_hf_batch_size

    monkeypatch.setenv("HF_BATCH_SIZE", "12")
    assert resolve_hf_batch_size(model_id="Qwen/Qwen3-1.7B", profile="json") == 12


def test_batch_size_for_profile():
    from research.generation.cluster_batch_sizes import batch_size_for_profile

    assert batch_size_for_profile("short", model_key="qwen17b") == 32
    assert batch_size_for_profile("heavy", model_key="qwen4b") == 4


def test_baseline_hf_generate_many_batches_jobs(monkeypatch):
    from research.generation.baseline_hf import BaselineHFGenerator

    jobs = [
        {
            "keyword": "comer",
            "translation": "to eat",
            "constraints": {"tense": "present", "person": "1st", "number": "singular"},
            "num_candidates": 2,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
        {
            "keyword": "beber",
            "translation": "to drink",
            "constraints": {"tense": "present", "person": "2nd", "number": "singular"},
            "num_candidates": 1,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
    ]
    fake_json = [
        '{"candidates":[{"sentence":"Como pan.","translation":"I eat bread."},'
        '{"sentence":"Como arroz.","translation":"I eat rice."}]}',
        '{"candidates":[{"sentence":"Bebes agua.","translation":"You drink water."}]}',
    ]
    batch_sizes: list[int] = []

    def fake_batch(model_id, specs, *, temperature=0.0, batch_size=8):
        batch_sizes.append(len(specs))
        return fake_json[: len(specs)]

    monkeypatch.setattr(
        "research.generation.baseline_hf.generate_chat_batch",
        fake_batch,
    )

    gen = BaselineHFGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    out = gen.generate_many(jobs, batch_size=2)

    assert batch_sizes == [2]
    assert len(out[0]) == 2
    assert len(out[1]) == 1
    assert out[0][0]["sentence"] == "Como pan."


def test_plain_hf_generate_many_uses_plain_parse(monkeypatch):
    from research.generation.baseline_hf import FormInjectedPlainHFGenerator

    jobs = [
        {
            "keyword": "comer",
            "translation": "to eat",
            "constraints": {
                "tense": "present",
                "person": "1st",
                "number": "singular",
                "expected_form": "como",
            },
            "num_candidates": 1,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
        {
            "keyword": "beber",
            "translation": "to drink",
            "constraints": {
                "tense": "present",
                "person": "2nd",
                "number": "singular",
                "expected_form": "bebes",
            },
            "num_candidates": 1,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
    ]

    def fake_batch(model_id, specs, *, temperature=0.0, batch_size=8):
        return ["Como pan.", "Bebes agua."][: len(specs)]

    monkeypatch.setattr(
        "research.generation.baseline_hf.generate_chat_batch",
        fake_batch,
    )

    gen = FormInjectedPlainHFGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    out = gen.generate_many(jobs, batch_size=2)

    assert out[0][0]["sentence"] == "Como pan."
    assert out[1][0]["sentence"] == "Bebes agua."


def test_constrained_hf_generate_many_batches_jobs(monkeypatch):
    from research.generation.constrained_hf import ConstrainedHFHardPlainGenerator

    jobs = [
        {
            "keyword": "comer",
            "translation": "to eat",
            "constraints": {
                "tense": "present",
                "person": "1st",
                "number": "singular",
                "expected_form": "como",
            },
            "num_candidates": 1,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
        {
            "keyword": "beber",
            "translation": "to drink",
            "constraints": {
                "tense": "present",
                "person": "2nd",
                "number": "singular",
                "expected_form": "bebes",
            },
            "num_candidates": 1,
            "target_language": "es",
            "cefr_level": None,
            "sentence_length": "short",
            "explicit_subject_required": False,
        },
    ]
    batch_sizes: list[int] = []

    def fake_beam_batch(
        model_id,
        specs,
        *,
        num_beams,
        use_hard_constraint,
        bias_strength,
        batch_size=8,
    ):
        batch_sizes.append(len(specs))
        return ["Como pan.", "Bebes agua."][: len(specs)]

    monkeypatch.setattr(
        "research.generation.constrained_hf.beam_generate_batch",
        fake_beam_batch,
    )

    gen = ConstrainedHFHardPlainGenerator(model="Qwen/Qwen3-1.7B", temperature=0.0)
    out = gen.generate_many(jobs, batch_size=2)

    assert batch_sizes == [2]
    assert out[0][0]["sentence"] == "Como pan."
    assert out[1][0]["sentence"] == "Bebes agua."


def test_batch_size_for_beam_profile():
    from research.generation.cluster_batch_sizes import batch_size_for_profile

    assert batch_size_for_profile("beam", model_key="qwen17b") == 4
    assert batch_size_for_profile("beam", model_key="qwen4b") == 2
