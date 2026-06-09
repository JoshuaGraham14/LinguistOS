"""Tests for MethodRunConfig and random length resolution."""

from __future__ import annotations

import random

import pytest

from research.db.models import MethodConfig
from research.evaluation.length_bands import RANDOM_LENGTH, resolve_length_band
from research.methods.run_config import MethodRunConfig


def test_from_method_config_fixed_length():
    mc = MethodConfig(
        name="baseline_long",
        method="baseline_gpt",
        samples_per_case=3,
        config={"sentence_length": "long", "model": "gpt-test"},
    )
    run = MethodRunConfig.from_method_config(mc)
    assert run.sentence_length == "long"
    assert run.model == "gpt-test"
    assert run.is_random_length is False
    assert run.resolve_length(random.Random(0)) == "long"


def test_from_method_config_random():
    mc = MethodConfig(
        name="baseline_random",
        method="baseline_gpt",
        samples_per_case=3,
        config={"sentence_length": RANDOM_LENGTH},
    )
    run = MethodRunConfig.from_method_config(mc)
    assert run.is_random_length is True
    assert run.resolve_length(random.Random(42)) in {"short", "medium", "long"}


def test_from_method_config_rejects_unknown_length():
    mc = MethodConfig(
        name="bad",
        method="baseline_gpt",
        samples_per_case=1,
        config={"sentence_length": "tiny"},
    )
    with pytest.raises(ValueError, match="Unknown sentence_length"):
        MethodRunConfig.from_method_config(mc)


def test_resolve_length_band_random_is_deterministic_with_rng():
    rng = random.Random(99)
    first = resolve_length_band(RANDOM_LENGTH, rng=rng)
    second = resolve_length_band(RANDOM_LENGTH, rng=rng)
    assert first in {"short", "medium", "long"}
    assert second in {"short", "medium", "long"}
