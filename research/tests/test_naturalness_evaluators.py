"""Unit tests for the fluency_perplexity and naturalness_llm_judge evaluators.

Neither test touches torch or the OpenAI API — both evaluators accept an
injected scorer/client so the shape of the pipeline can be exercised
without network or GPU dependencies.
"""

from __future__ import annotations

import json
import math

import pytest

from research.evaluation.sentence import DEFAULT_EVALUATORS
from research.evaluation.sentence.fluency_perplexity import (
    DEFAULT_MODEL_ID,
    EVALUATOR_NAME as PPL_EVALUATOR_NAME,
    FluencyPerplexityEvaluator,
    PerplexityScorer,
)
from research.evaluation.sentence.naturalness_llm_judge import (
    DEFAULT_MODEL as JUDGE_DEFAULT_MODEL,
    EVALUATOR_NAME as JUDGE_EVALUATOR_NAME,
    LlmJudgeClient,
    NaturalnessLlmJudgeEvaluator,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
)


# ── Perplexity evaluator ─────────────────────────────────────────────────────


class _FakeScorer(PerplexityScorer):
    """Deterministic PPL fake so we can assert scoring shape without a GPU."""

    def __init__(self, mean_nll: float, token_count: int) -> None:
        self.mean_nll = mean_nll
        self.token_count = token_count
        self.model_id = "fake/model"
        self.dtype_name = "float32"
        self.revision = "cafef00d"
        self._device = "cpu"
        self.calls: list[str] = []

    def score(self, sentence: str) -> tuple[float, int]:
        self.calls.append(sentence)
        return self.mean_nll, self.token_count


def test_perplexity_scores_healthy_sentence():
    scorer = _FakeScorer(mean_nll=1.5, token_count=6)
    ev = FluencyPerplexityEvaluator(scorer=scorer)
    result = ev.evaluate(
        "Vosotros escribís cartas.",
        "You write letters.",
        {"target_language": "es", "expected_form": "escribís"},
    )
    assert result.score == pytest.approx(math.exp(-1.5))
    assert 0.0 <= result.score <= 1.0
    assert result.details["perplexity"] == pytest.approx(math.exp(1.5))
    assert result.details["token_count"] == 6
    assert result.details["model_id"] == "fake/model"
    assert result.details["revision"] == "cafef00d"
    assert result.details["dtype"] == "float32"
    assert result.details["device"] == "cpu"
    assert result.details["scorer_version"]
    assert scorer.calls == ["Vosotros escribís cartas."]


def test_perplexity_higher_mean_nll_gives_worse_score():
    good = FluencyPerplexityEvaluator(
        scorer=_FakeScorer(mean_nll=1.0, token_count=6)
    ).evaluate("A.", "A.", {"target_language": "es"})
    bad = FluencyPerplexityEvaluator(
        scorer=_FakeScorer(mean_nll=6.0, token_count=6)
    ).evaluate("B.", "B.", {"target_language": "es"})
    assert good.score > bad.score
    assert good.details["perplexity"] < bad.details["perplexity"]


def test_perplexity_empty_sentence_returns_error():
    ev = FluencyPerplexityEvaluator(scorer=_FakeScorer(0.0, 0))
    result = ev.evaluate("   ", "hello", {"target_language": "es"})
    assert result.score == 0.0
    assert result.details["error"] == "empty_sentence"


def test_perplexity_zero_tokens_returns_error():
    ev = FluencyPerplexityEvaluator(scorer=_FakeScorer(1.0, 0))
    result = ev.evaluate("Hola.", "Hi.", {"target_language": "es"})
    assert result.score == 0.0
    assert result.details["error"] == "no_scoreable_tokens"


def test_perplexity_score_clamped_to_unit_interval():
    # mean_nll = -0.1 -> exp(-mean_nll) > 1 -> should clamp to 1.0
    ev = FluencyPerplexityEvaluator(scorer=_FakeScorer(mean_nll=-0.1, token_count=4))
    result = ev.evaluate("Cualquier cosa.", "Anything.", {"target_language": "es"})
    assert result.score == 1.0


def test_perplexity_default_model_id_env(monkeypatch):
    # The evaluator advertises Salamandra as the default and reads env vars
    # for the model id / dtype / revision. We don't build a real HF scorer
    # here; we just verify the plumbing.
    from research.evaluation.sentence.fluency_perplexity import (
        HuggingFacePerplexityScorer,
    )

    assert DEFAULT_MODEL_ID == "BSC-LT/salamandra-2b"
    monkeypatch.setenv("NATURALNESS_PPL_MODEL", "some/other")
    monkeypatch.setenv("NATURALNESS_PPL_DTYPE", "float16")
    monkeypatch.setenv("NATURALNESS_PPL_REVISION", "deadbeef")

    ev = FluencyPerplexityEvaluator()
    scorer = ev._get_scorer()  # type: ignore[attr-defined]
    assert isinstance(scorer, HuggingFacePerplexityScorer)
    assert scorer.model_id == "some/other"
    assert scorer.dtype_name == "float16"
    assert scorer.revision == "deadbeef"


def test_perplexity_empty_env_vars_fall_back_to_defaults(monkeypatch):
    # A verbatim copy of .env.example sets these to empty strings; the
    # defaults must still win (regression test for .get(key, default)).
    from research.evaluation.sentence.fluency_perplexity import (
        DEFAULT_DTYPE,
        HuggingFacePerplexityScorer,
    )

    monkeypatch.setenv("NATURALNESS_PPL_MODEL", "")
    monkeypatch.setenv("NATURALNESS_PPL_DTYPE", "")
    monkeypatch.setenv("NATURALNESS_PPL_REVISION", "")
    ev = FluencyPerplexityEvaluator()
    scorer = ev._get_scorer()  # type: ignore[attr-defined]
    assert isinstance(scorer, HuggingFacePerplexityScorer)
    assert scorer.model_id == DEFAULT_MODEL_ID
    assert scorer.dtype_name == DEFAULT_DTYPE
    assert scorer.revision is None


def test_perplexity_not_in_default_evaluators():
    names = {ev.name for ev in DEFAULT_EVALUATORS}
    assert PPL_EVALUATOR_NAME not in names


# ── LLM judge evaluator ──────────────────────────────────────────────────────


class _RecordingClient(LlmJudgeClient):
    """Fake OpenAI client. Returns queued responses; records prompts."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete(self, system: str, user: str, *, model: str) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if not self._responses:
            raise AssertionError("no more queued responses")
        return self._responses.pop(0)


_VALID_JUDGE_RESPONSE = json.dumps(
    {
        "grammaticality": 5,
        "naturalness": 2,
        "target_form_use": "correct_main_verb",
        "semantic_coherence": 4,
        "flags": ["odd_collocation"],
        "rationale": "Verb is correctly conjugated but the noun-adjective pair is unnatural.",
    }
)


def test_judge_parses_valid_response():
    client = _RecordingClient([_VALID_JUDGE_RESPONSE])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Obtenéis información fácil.",
        "You get information easy.",
        {
            "expected_form": "obtenéis",
            "keyword": "obtener",
            "tense": "present",
            "person": "2nd",
            "number": "plural",
            "target_language": "es",
        },
    )
    assert result.score == pytest.approx(2 / 5)
    d = result.details
    assert d["grammaticality"] == 5
    assert d["naturalness"] == 2
    assert d["semantic_coherence"] == 4
    assert d["target_form_use"] == "correct_main_verb"
    assert d["flags"] == ["odd_collocation"]
    assert d["model_id"] == "gpt-5.4-mini"
    assert d["prompt_version"] == PROMPT_VERSION
    assert "rationale" in d and d["rationale"]

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["system"] == SYSTEM_PROMPT
    assert "Expected verb form: obtenéis" in call["user"]
    assert "Obtenéis información fácil." in call["user"]
    # Sanity: arm/generator name never leaks into the judge prompt.
    assert "soft" not in call["user"].lower()
    assert "beam" not in call["user"].lower()


def test_judge_retries_once_on_parse_failure_then_succeeds():
    client = _RecordingClient(["not json at all", _VALID_JUDGE_RESPONSE])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Coméis juntos en casa.",
        "You eat together at home.",
        {"expected_form": "coméis", "target_language": "es"},
    )
    assert result.score == pytest.approx(2 / 5)
    assert len(client.calls) == 2
    # Retry user prompt is augmented with the failure reason.
    assert "failed validation" in client.calls[1]["user"]


def test_judge_gives_up_after_second_failure():
    client = _RecordingClient(["bad", "still bad"])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Vosotros escribís cartas.",
        "You write letters.",
        {"expected_form": "escribís", "target_language": "es"},
    )
    assert result.score == 0.0
    assert result.details["error"].startswith("json_decode_failed")
    assert result.details["raw_response"] == "still bad"
    assert len(client.calls) == 2


def test_judge_rejects_bad_enum_value():
    payload = json.dumps(
        {
            "grammaticality": 5,
            "naturalness": 5,
            "target_form_use": "invented_role",
            "semantic_coherence": 5,
            "flags": [],
            "rationale": "All axes are fine but the enum is wrong on purpose.",
        }
    )
    client = _RecordingClient([payload, _VALID_JUDGE_RESPONSE])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Ella come una manzana.",
        "She eats an apple.",
        {"expected_form": "come", "target_language": "es"},
    )
    # Retry succeeds → score comes from the second response.
    assert result.score == pytest.approx(2 / 5)
    assert len(client.calls) == 2
    assert "bad_target_form_use" in client.calls[1]["user"]


def test_judge_rejects_out_of_range_axis():
    payload = json.dumps(
        {
            "grammaticality": 9,
            "naturalness": 5,
            "target_form_use": "correct_main_verb",
            "semantic_coherence": 5,
            "flags": [],
            "rationale": "Grammaticality has been set out of the allowed range.",
        }
    )
    client = _RecordingClient([payload, payload])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Ella come una manzana.",
        "She eats an apple.",
        {"expected_form": "come", "target_language": "es"},
    )
    assert result.score == 0.0
    assert result.details["error"].startswith("grammaticality_out_of_range")


def test_judge_rejects_non_english_rationale_then_retries():
    spanish_rationale = json.dumps(
        {
            "grammaticality": 5,
            "naturalness": 2,
            "target_form_use": "correct_main_verb",
            "semantic_coherence": 4,
            "flags": ["odd_collocation"],
            "rationale": "El verbo está bien conjugado pero la información es fácil no es natural.",
        }
    )
    client = _RecordingClient([spanish_rationale, _VALID_JUDGE_RESPONSE])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Obtenéis información fácil.",
        "You get information easy.",
        {"expected_form": "obtenéis", "target_language": "es"},
    )
    assert result.score == pytest.approx(2 / 5)
    assert len(client.calls) == 2
    assert "rationale_not_english" in client.calls[1]["user"]


def test_judge_signalled_error_object_is_a_failure():
    client = _RecordingClient(
        [
            json.dumps({"error": "no_english_rationale"}),
            json.dumps({"error": "no_english_rationale"}),
        ]
    )
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate(
        "Ella come una manzana.",
        "She eats an apple.",
        {"expected_form": "come", "target_language": "es"},
    )
    assert result.score == 0.0
    assert "judge_error" in result.details["error"]


def test_judge_empty_sentence_returns_error_without_api_call():
    client = _RecordingClient([])
    ev = NaturalnessLlmJudgeEvaluator(client=client, model="gpt-5.4-mini")
    result = ev.evaluate("   ", "", {"expected_form": "come"})
    assert result.score == 0.0
    assert result.details["error"] == "empty_sentence"
    assert client.calls == []


def test_judge_model_falls_back_through_env(monkeypatch):
    monkeypatch.delenv("OPENAI_JUDGE_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    ev = NaturalnessLlmJudgeEvaluator(client=_RecordingClient([]))
    assert ev.model == JUDGE_DEFAULT_MODEL

    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o")
    ev2 = NaturalnessLlmJudgeEvaluator(client=_RecordingClient([]))
    assert ev2.model == "gpt-4o"

    monkeypatch.setenv("OPENAI_JUDGE_MODEL", "gpt-5.4-mini")
    ev3 = NaturalnessLlmJudgeEvaluator(client=_RecordingClient([]))
    assert ev3.model == "gpt-5.4-mini"


def test_judge_not_in_default_evaluators():
    names = {ev.name for ev in DEFAULT_EVALUATORS}
    assert JUDGE_EVALUATOR_NAME not in names
