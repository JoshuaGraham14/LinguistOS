"""Tests for per-language morph config loading and validation."""

from __future__ import annotations

import pytest

from research.evaluation.morph_configs import load_morph_config


def test_load_es_config():
    config = load_morph_config("es")
    assert config["parser"] == "spacy"
    assert config["model"] == "es_core_news_sm"
    assert "VERB" in config["pos_filter"]
    assert config["tense_map"]["preterite"] == "Past"
    assert config["tense_map"]["imperfect"] == "Imp"
    assert config["tense_map"]["present"] == "Pres"
    assert config["tense_map"]["future"] == "Fut"
    assert config["person_map"]["1st"] == "1"
    assert config["number_map"]["plural"] == "Plur"


def test_load_unknown_language_raises():
    with pytest.raises(ValueError, match="No morph config for language 'xx'"):
        load_morph_config("xx")


def test_load_es_config_cached():
    """lru_cache should return the same object on repeated calls."""
    assert load_morph_config("es") is load_morph_config("es")
