"""Unit tests for the Cysill Welsh grammar evaluator (mocked HTTP)."""

from __future__ import annotations

from research.evaluation.sentence import default_evaluators_for_language
from research.evaluation.sentence.cysill import (
    EVALUATOR_NAME,
    CysillGrammarEvaluator,
    build_cysill_details,
    match_to_dict,
)


class _FakeCysill:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def check(self, text: str) -> dict:
        self.calls.append(text)
        return self.payload


def test_match_to_dict_categories():
    spell = match_to_dict(
        {"isSpelling": True, "start": 0, "length": 3, "suggestions": ["abc"], "message": "x"}
    )
    assert spell["category"] == "MISSPELLING"
    gram = match_to_dict(
        {"isSpelling": False, "start": 1, "length": 2, "suggestions": [], "message": "y"}
    )
    assert gram["category"] == "GRAMMAR"


def test_cysill_pass_on_clean_payload():
    client = _FakeCysill({"success": True, "result": [], "version": 1})
    ev = CysillGrammarEvaluator(client_factory=lambda: client)
    result = ev.evaluate("Mae'r tywydd yn braf.", "", {"target_language": "cy"})
    assert result.score == 1.0
    assert result.details["passed"] is True
    assert result.details["match_count"] == 0
    assert client.calls == ["Mae'r tywydd yn braf."]


def test_cysill_fail_on_grammar_match():
    client = _FakeCysill(
        {
            "success": True,
            "result": [
                {
                    "isSpelling": False,
                    "start": 4,
                    "length": 9,
                    "suggestions": ["hen wlad"],
                    "message": "Mae 'hen' yn achosi treiglad meddal",
                }
            ],
            "version": 1,
        }
    )
    ev = CysillGrammarEvaluator(client_factory=lambda: client)
    result = ev.evaluate("mae hen gwlad fy tadau", "", {"target_language": "cy"})
    assert result.score == 0.0
    assert result.details["match_count"] == 1
    assert result.details["matches"][0]["category"] == "GRAMMAR"


def test_cysill_api_error_payload():
    client = _FakeCysill({"success": False, "errors": ["403 Forbidden"]})
    ev = CysillGrammarEvaluator(client_factory=lambda: client)
    result = ev.evaluate("test", "", {"target_language": "cy"})
    assert result.score == 0.0
    assert "403" in result.details["error"]


def test_cysill_skips_non_welsh():
    client = _FakeCysill({"success": True, "result": []})
    ev = CysillGrammarEvaluator(client_factory=lambda: client)
    result = ev.evaluate("Hola", "", {"target_language": "es"})
    assert result.details["skipped"] is True
    assert client.calls == []


def test_default_evaluators_include_cysill_when_key_set(monkeypatch):
    monkeypatch.setenv("CYSILL_API_KEY", "test-key")
    names = [e.name for e in default_evaluators_for_language("cy")]
    assert EVALUATOR_NAME in names
    assert "grammar_languagetool" not in names


def test_default_evaluators_omit_cysill_without_key(monkeypatch):
    monkeypatch.delenv("CYSILL_API_KEY", raising=False)
    names = [e.name for e in default_evaluators_for_language("cy")]
    assert EVALUATOR_NAME not in names
    assert "expected_form_match" in names


def test_build_cysill_details_empty_error():
    d = build_cysill_details(sentence="a b", matches=[], error="boom")
    assert d["passed"] is False
    assert d["error"] == "boom"
    assert d["token_count"] == 2
