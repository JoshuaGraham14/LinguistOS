"""Tests for Fix-B plain OpenAI generator (prompt parity with HF plain_b)."""

from __future__ import annotations

from research.generation.baseline_gpt_plain import PlainGPTBGenerator, generate_plain_b
from research.generation.prompt_builder import build_prompt_plain

_ES_PRESENT_1SG = {"tense": "present", "person": "1st", "number": "singular"}


def test_plain_b_prompt_matches_hf_fix_b():
    """Same ``build_prompt_plain`` flags as ``PlainHFBGenerator``."""
    expected = build_prompt_plain(
        keyword="acercar",
        translation="acercar",
        target_language="es",
        constraints=_ES_PRESENT_1SG,
        num_candidates=1,
        sentence_length="short",
        require_full_sentence=True,
        morphology_hints=False,
    )
    assert "Output requirements: write a complete Spanish sentence" in expected
    assert "Reply with ONLY the Spanish sentence" in expected
    assert "No JSON" in expected
    assert '{"candidates"' not in expected


def test_registry_name():
    assert PlainGPTBGenerator().name == "baseline_gpt_plain_b"


def test_generate_plain_b_no_api_key_returns_empty(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = generate_plain_b(
        "acercar",
        "acercar",
        _ES_PRESENT_1SG,
        num_candidates=1,
        api_key="",
    )
    assert out == []
