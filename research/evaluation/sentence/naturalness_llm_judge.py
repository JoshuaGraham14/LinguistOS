"""Naturalness judge for Spanish sentences via a hosted LLM (OpenAI Chat).

Single structured JSON call per sentence with a rigorous rubric that
separates:

- ``grammaticality``    — is the Spanish structurally correct?
- ``naturalness``       — would a native naturally say this?
- ``semantic_coherence``— does it express a coherent proposition?
- ``target_form_use``   — is the expected form used correctly as main verb?
- ``flags``             — interpretable error taxonomy.

The primary stored ``score`` is ``naturalness / 5`` so that
``mean::naturalness_llm_judge`` reads "higher = better" alongside EF and
LT. The other axes live in ``details`` and get roll-ups via
``aggregate_sentence_eval_rollups`` when we ask for them.

The judge is opt-in — not part of ``DEFAULT_EVALUATORS`` — because every
call spends OpenAI credits. Cluster generation scripts never enable it.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult

EVALUATOR_NAME = "naturalness_llm_judge"
DEFAULT_MODEL = "gpt-5.4-mini"
PROMPT_VERSION = "v3"

TARGET_FORM_USE_VALUES: frozenset[str] = frozenset(
    {
        "correct_main_verb",
        "correct_but_not_main_verb",
        "wrong_agreement_or_role",
        "mentioned_or_quoted_only",
        "absent",
    }
)

FLAG_VALUES: frozenset[str] = frozenset(
    {
        "odd_collocation",
        "subject_verb_disagreement",
        "tense_context_conflict",
        "repetition_or_degeneration",
        "mixed_language_or_meta_output",
    }
)

_MAX_RATIONALE_LEN = 240

# Cheap heuristic to catch non-English rationales (the model is instructed
# to write in English regardless of the sentence language). Not a language
# ID model; just a function-word-ratio red flag that triggers one retry.
_ENGLISH_FUNCTION_WORDS: frozenset[str] = frozenset(
    {
        "the",
        "and",
        "is",
        "are",
        "not",
        "with",
        "of",
        "to",
        "in",
        "a",
        "an",
        "that",
        "this",
        "would",
        "does",
        "for",
        "or",
        "but",
        "as",
        "it",
        "its",
        "on",
        "be",
        "was",
        "were",
        "has",
        "have",
        "verb",
        "subject",
        "sentence",
        "grammar",
        "agree",
    }
)

_SPANISH_FUNCTION_WORDS: frozenset[str] = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "y",
        "o",
        "es",
        "está",
        "están",
        "son",
        "no",
        "de",
        "del",
        "en",
        "que",
        "pero",
        "aunque",
        "porque",
        "con",
        "sin",
        "para",
        "por",
        "se",
        "su",
        "sus",
        "verbo",
        "palabra",
        "oración",
        "frase",
        "sujeto",
        "concuerda",
        "gramaticalmente",
    }
)

_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


SYSTEM_PROMPT = """\
You are a rigorous evaluator of Spanish sentences produced by a language
model that was asked to use a specific verb form. You are not the teacher
or the generator; you are grading the sentence as a native Spanish
speaker.

Rate ONLY the Spanish sentence. Do not consider any English translation.
Do not reward the sentence merely because the expected form appears in
it. Penalise sentences that quote or list the form instead of using it
as a main verb, and sentences that are repetitions or degenerate loops.
Short but well-formed clauses are acceptable; do not penalise a sentence
for being short if it is natural and coherent.

Return a single JSON object matching this schema. No prose, no code
fences, no extra keys, no null values.

{
  "grammaticality":     integer 1..5,
  "naturalness":        integer 1..5,
  "target_form_use":    "correct_main_verb"
                      | "correct_but_not_main_verb"
                      | "wrong_agreement_or_role"
                      | "mentioned_or_quoted_only"
                      | "absent",
  "semantic_coherence": integer 1..5,
  "flags": [
    "odd_collocation" |
    "subject_verb_disagreement" |
    "tense_context_conflict" |
    "repetition_or_degeneration" |
    "mixed_language_or_meta_output"
  ],
  "rationale": string (max 240 characters, written in English)
}

Scale anchors (one worked example per level; use these as calibration
points, not exhaustive rules):

grammaticality
  5 = fully grammatical Spanish.
      Ex: "Comemos temprano cada día." — every element is well-formed.
  4 = minor grammatical issue that does not impede understanding.
      Ex: "María tiene veinte año." — missing plural on "año" is a
      clear but minor slip.
  3 = noticeable grammatical errors but meaning is recoverable.
      Ex: "Ellos escribe cartas a los abuelos." — subject-verb number
      disagreement; the meaning is still obvious.
  2 = major grammatical errors.
      Ex: "Yo comer manzana ayer." — verb uninflected and article
      missing at the same time.
  1 = ungrammatical or not a valid sentence.
      Ex: "Manzana el que corre está." — words in an invalid order;
      not a Spanish sentence.

naturalness
  5 = a native would naturally produce this sentence.
      Ex: "Vosotros obtenéis información en la biblioteca." — an
      unremarkable everyday sentence.
  4 = acceptable, slightly unusual phrasing or word choice.
      Ex: "Nosotros comemos temprano cada día." — explicit "nosotros"
      is optional and slightly marked in a neutral context.
  3 = understandable but noticeably awkward.
      Ex: "Nos comemos temprano cada día." — reflexive is grammatical
      but mildly regional; a native would often rephrase.
  2 = substantially unnatural; a native would rewrite it.
      Ex: "Hacemos una decisión difícil." — English calque; a native
      says "tomamos una decisión".
  1 = broken or incoherent.
      Ex: "Coméis coméis coméis coméis juntos." — degenerate output.
  NEVER use this axis to penalise pure grammar mistakes; use
  `grammaticality` for those.

semantic_coherence
  5 = coherent, plausible meaning.
      Ex: "Comemos temprano cada día." — a plausible everyday event.
  4 = coherent, mildly odd content.
      Ex: "Bebemos café con ajo cada mañana." — imaginable but unusual.
  3 = interpretable but implausible.
      Ex: "Como una puerta." — grammatical, but the referent is
      implausible.
  2 = strained, partially interpretable.
      Ex: "Ayer comeré en casa." — "ayer" (past) clashes with the
      future verb "comeré"; the proposition contradicts itself.
  1 = nonsensical or degenerate.
      Ex: "Coméis coméis coméis juntos." — no meaningful proposition.

target_form_use categories:
  correct_main_verb            = the expected form is the main verb of
                                 the sentence and agrees with its subject
                                 in person and number.
  correct_but_not_main_verb    = the expected form appears with correct
                                 morphology but is subordinate, not the
                                 main verb.
  wrong_agreement_or_role      = the form is present but does not agree
                                 with its subject, or is used in a role
                                 it cannot syntactically fill.
  mentioned_or_quoted_only     = the form appears in quotes, as a
                                 vocabulary item, or as a metalinguistic
                                 mention; it is not used.
  absent                       = the exact expected form does not appear.

Flag definitions (assign each independently; a sentence may have zero
or several flags):
  odd_collocation             = lexically unusual or implausible word
                                combinations (e.g. "comer una puerta",
                                "información fácil"). Lexical only.
  subject_verb_disagreement   = subject and verb differ in person or
                                number. Purely grammatical.
  tense_context_conflict      = time adverbials or context contradict
                                the tense of the main verb.
  repetition_or_degeneration  = tokens or short phrases repeat in a
                                degenerate way.
  mixed_language_or_meta_output = contains non-Spanish spans, tags such
                                as </think>, or explains itself instead
                                of producing the sentence.

Write `rationale` in English regardless of the sentence language. This
field is read by an English-speaking annotator. If you cannot produce
an English rationale, return {"error": "no_english_rationale"} instead.

Spanish *haber*: he/has/ha/hemos/habéis/han (and past/future/conditional
forms) are Spanish auxiliaries. Sentence-initial "He" is 1sg *haber*,
NOT the English pronoun. Ex: "He comido pan." → correct_main_verb;
never flag mixed_language for "He" alone.

Participles: a past participle cannot stand alone as a predicate; it
needs a finite auxiliary (*haber*, or *ser*/*estar* for passive/
resultative). In a perfect/passive, the target participle under
haber/ser/estar counts as correct_main_verb. Bare forms like
"caminado en la calle" are NOT correct_main_verb.

Be strict but fair. If unsure between two integers, pick the lower one
for `grammaticality`, `naturalness`, and `semantic_coherence`.
"""


def _build_user_prompt(sentence: str, constraints: dict[str, Any]) -> str:
    """Compact, judge-facing user message. Never include arm/generator info."""
    parts: list[str] = [f"Target language: {constraints.get('target_language') or 'Spanish'}"]
    expected_form = constraints.get("expected_form")
    if expected_form:
        parts.append(f"Expected verb form: {expected_form}")
    for key, label in (
        ("keyword", "Lemma"),
        ("tense", "Tense"),
        ("person", "Person"),
        ("number", "Number"),
    ):
        val = constraints.get(key)
        if val:
            parts.append(f"{label}: {val}")
    parts.append("")
    parts.append("Sentence:")
    parts.append(f'"{sentence}"')
    return "\n".join(parts)


class LlmJudgeClient:
    """Minimal interface the evaluator uses. Real impl below; tests inject fakes."""

    def complete(self, system: str, user: str, *, model: str) -> str:  # pragma: no cover
        raise NotImplementedError


class OpenAIJudgeClient(LlmJudgeClient):
    """OpenAI Chat Completions wrapper. Loads key from env; no other side effects."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not set (research/.env)")
        from openai import OpenAI

        self._client = OpenAI(api_key=self._api_key)
        return self._client

    def complete(self, system: str, user: str, *, model: str) -> str:
        client = self._ensure_client()
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return completion.choices[0].message.content or "{}"


def _looks_non_english(rationale: str) -> bool:
    """Best-effort check that the rationale is English (per prompt rule).

    Compares Spanish-function-word count to English-function-word count.
    Flags Spanish as long as it dominates; ignores content words that happen
    to be shared (e.g. "natural"). Never a perfect language ID; the retry
    layer only needs a coarse signal.
    """
    if not rationale:
        return False
    tokens = [m.group(0).lower() for m in _WORD_RE.finditer(rationale)]
    if not tokens:
        return False
    en = sum(1 for t in tokens if t in _ENGLISH_FUNCTION_WORDS)
    es = sum(1 for t in tokens if t in _SPANISH_FUNCTION_WORDS)
    return es > en


def _parse_and_validate(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (parsed_dict, error_message). Non-empty error means the caller retries."""
    try:
        obj = json.loads(raw)
    except Exception as exc:
        return None, f"json_decode_failed: {exc}"
    if not isinstance(obj, dict):
        return None, "top_level_not_object"

    # Judge signalled it cannot comply — surface as an explicit error path.
    if "error" in obj and len(obj) == 1:
        return None, f"judge_error: {obj.get('error')}"

    required = {
        "grammaticality",
        "naturalness",
        "target_form_use",
        "semantic_coherence",
        "flags",
        "rationale",
    }
    missing = required - set(obj)
    if missing:
        return None, f"missing_keys: {sorted(missing)}"

    for k in ("grammaticality", "naturalness", "semantic_coherence"):
        v = obj[k]
        if not isinstance(v, int) or not (1 <= v <= 5):
            return None, f"{k}_out_of_range: {v!r}"

    tfu = obj["target_form_use"]
    if tfu not in TARGET_FORM_USE_VALUES:
        return None, f"bad_target_form_use: {tfu!r}"

    flags_raw = obj["flags"]
    if not isinstance(flags_raw, list):
        return None, f"flags_not_list: {type(flags_raw).__name__}"
    seen: set[str] = set()
    for f in flags_raw:
        if not isinstance(f, str) or f not in FLAG_VALUES:
            return None, f"bad_flag: {f!r}"
        if f in seen:
            return None, f"duplicate_flag: {f!r}"
        seen.add(f)

    rationale = obj["rationale"]
    if not isinstance(rationale, str) or not rationale.strip():
        return None, "rationale_empty"
    rationale = rationale.strip()
    if len(rationale) > _MAX_RATIONALE_LEN:
        rationale = rationale[:_MAX_RATIONALE_LEN]
    obj["rationale"] = rationale
    if _looks_non_english(rationale):
        return None, "rationale_not_english"
    return obj, None


class NaturalnessLlmJudgeEvaluator(BaseEvaluator):
    """Opt-in judge. Never included in DEFAULT_EVALUATORS.

    Parameters
    ----------
    client
        A ``LlmJudgeClient`` implementation. In production this is an
        :class:`OpenAIJudgeClient`; unit tests inject a stub.
    model
        Chat model slug. Falls back to ``OPENAI_JUDGE_MODEL`` then
        ``OPENAI_MODEL`` then :data:`DEFAULT_MODEL`.
    """

    def __init__(
        self,
        *,
        client: LlmJudgeClient | None = None,
        client_factory: Callable[[], LlmJudgeClient] | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client
        self._factory = client_factory
        self._model = (
            model
            or os.environ.get("OPENAI_JUDGE_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or DEFAULT_MODEL
        )

    @property
    def name(self) -> str:
        return EVALUATOR_NAME

    @property
    def model(self) -> str:
        return self._model

    def _get_client(self) -> LlmJudgeClient:
        if self._client is not None:
            return self._client
        if self._factory is not None:
            self._client = self._factory()
            return self._client
        self._client = OpenAIJudgeClient()
        return self._client

    def _call_with_retry(self, user: str) -> tuple[dict[str, Any] | None, str | None, str]:
        """One primary call, one strict retry on parse/schema/language failure."""
        client = self._get_client()
        last_raw = ""
        last_error: str | None = None
        for attempt in (1, 2):
            try:
                raw = client.complete(SYSTEM_PROMPT, user, model=self._model)
            except Exception as exc:  # pragma: no cover - env dependent
                return None, f"api_failure: {exc}", ""
            last_raw = raw or ""
            parsed, err = _parse_and_validate(last_raw)
            if parsed is not None:
                return parsed, None, last_raw
            last_error = err
            if attempt == 1:
                user = (
                    user
                    + "\n\n"
                    + "Your previous response failed validation ("
                    + (err or "unknown")
                    + "). Respond ONLY with a valid JSON object matching the schema, "
                    + "with the rationale written in English."
                )
        return None, last_error, last_raw

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        text = (sentence or "").strip()
        if not text:
            return EvaluationResult(
                score=0.0,
                details={
                    "error": "empty_sentence",
                    "model_id": self._model,
                    "prompt_version": PROMPT_VERSION,
                },
            )

        user_prompt = _build_user_prompt(text, constraints or {})
        parsed, err, raw = self._call_with_retry(user_prompt)
        if parsed is None:
            return EvaluationResult(
                score=0.0,
                details={
                    "error": err or "unknown_failure",
                    "raw_response": raw[:2000],
                    "model_id": self._model,
                    "prompt_version": PROMPT_VERSION,
                },
            )

        score = float(parsed["naturalness"]) / 5.0
        details: dict[str, Any] = {
            "grammaticality": int(parsed["grammaticality"]),
            "naturalness": int(parsed["naturalness"]),
            "target_form_use": parsed["target_form_use"],
            "semantic_coherence": int(parsed["semantic_coherence"]),
            "flags": list(parsed["flags"]),
            "rationale": parsed["rationale"],
            "model_id": self._model,
            "prompt_version": PROMPT_VERSION,
            "raw_response": raw[:2000],
        }
        return EvaluationResult(score=score, details=details)


__all__ = [
    "DEFAULT_MODEL",
    "EVALUATOR_NAME",
    "FLAG_VALUES",
    "LlmJudgeClient",
    "NaturalnessLlmJudgeEvaluator",
    "OpenAIJudgeClient",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "TARGET_FORM_USE_VALUES",
]
