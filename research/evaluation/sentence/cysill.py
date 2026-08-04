"""Welsh grammar/spelling check via Cysill Ar-lein (Techiaith API).

LanguageTool has no Welsh pack. Cysill is the Bangor/Techiaith checker that
covers spelling, grammar, and mutation errors. Requires ``CYSILL_API_KEY``
from https://api.techiaith.org.

API docs: https://github.com/PorthTechnolegauIaith/cysill

Rate limits are per API key (often a few hundred calls/hour). Full Welsh
grids should prefer offline rescoring with caching, not live per-sentence
calls on every generation arm.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Protocol

import requests

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult
from research.evaluation.sentence.expected_form import tokenize

EVALUATOR_NAME = "grammar_cysill"
DEFAULT_ENDPOINT = "https://api.techiaith.org/cysill/v1/"
ENV_API_KEY = "CYSILL_API_KEY"
ENV_ENDPOINT = "CYSILL_API_ENDPOINT"
ENV_CACHE_DIR = "CYSILL_CACHE_DIR"


class CysillClient(Protocol):
    def check(self, text: str) -> dict[str, Any]: ...


def cysill_api_key() -> str | None:
    key = (os.environ.get(ENV_API_KEY) or "").strip()
    return key or None


def cysill_available() -> bool:
    return cysill_api_key() is not None


def _default_cache_dir() -> Path:
    override = (os.environ.get(ENV_CACHE_DIR) or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / ".cache" / "cysill"


class HttpCysillClient:
    """Thin HTTPS GET client for the Cysill Ar-lein API."""

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = DEFAULT_ENDPOINT,
        lang: str = "en",
        timeout_s: float = 30.0,
        cache_dir: Path | None = None,
        session: requests.Session | None = None,
        sleep_s: float = 0.0,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._lang = lang
        self._timeout_s = timeout_s
        self._cache_dir = cache_dir
        self._session = session or requests.Session()
        self._sleep_s = sleep_s
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, text: str) -> Path | None:
        if self._cache_dir is None:
            return None
        digest = hashlib.sha256(f"{self._lang}\0{text}".encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.json"

    def check(self, text: str) -> dict[str, Any]:
        cached = self._cache_path(text)
        if cached is not None and cached.is_file():
            return json.loads(cached.read_text(encoding="utf-8"))

        if self._sleep_s > 0:
            time.sleep(self._sleep_s)
        resp = self._session.get(
            self._endpoint,
            params={
                "api_key": self._api_key,
                "text": text,
                "max_errors": 0,  # return all matches
                "lang": self._lang,
            },
            timeout=self._timeout_s,
        )
        resp.raise_for_status()
        payload = resp.json()
        if cached is not None:
            cached.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload


def _get_cysill_client() -> CysillClient:
    key = cysill_api_key()
    if not key:
        raise RuntimeError(
            f"{ENV_API_KEY} is not set. Register at https://api.techiaith.org "
            "and add the key to research/.env"
        )
    endpoint = (os.environ.get(ENV_ENDPOINT) or DEFAULT_ENDPOINT).strip()
    return HttpCysillClient(
        api_key=key,
        endpoint=endpoint,
        cache_dir=_default_cache_dir(),
    )


def match_to_dict(match: dict[str, Any]) -> dict[str, Any]:
    suggestions = match.get("suggestions") or []
    is_spelling = bool(match.get("isSpelling"))
    return {
        "rule": "spelling" if is_spelling else "grammar",
        "category": "MISSPELLING" if is_spelling else "GRAMMAR",
        "message": match.get("message"),
        "offset": match.get("start"),
        "error_length": match.get("length"),
        "replacements": list(suggestions)[:3],
        "is_spelling": is_spelling,
    }


def build_cysill_details(
    *,
    sentence: str,
    matches: list[dict[str, Any]],
    error: str | None = None,
    skipped: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    if error is not None or skipped:
        out = {
            "passed": False,
            "match_count": 0,
            "total_match_count": 0,
            "token_count": len(tokenize(sentence)),
            "matches": [],
        }
        if error is not None:
            out["error"] = error
        if skipped:
            out["skipped"] = True
        if reason is not None:
            out["reason"] = reason
        return out
    return {
        "passed": len(matches) == 0,
        "match_count": len(matches),
        "total_match_count": len(matches),
        "token_count": len(tokenize(sentence)),
        "matches": [match_to_dict(m) for m in matches],
    }


class CysillGrammarEvaluator(BaseEvaluator):
    """Pass (1.0) when Cysill reports no spelling/grammar/mutation matches."""

    def __init__(
        self,
        client_factory: Callable[[], CysillClient] | None = None,
    ) -> None:
        self._client_factory = client_factory or _get_cysill_client

    @property
    def name(self) -> str:
        return EVALUATOR_NAME

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        language = (constraints.get("target_language") or "cy").strip() or "cy"
        if language != "cy":
            return EvaluationResult(
                score=0.0,
                details=build_cysill_details(
                    sentence=sentence,
                    matches=[],
                    skipped=True,
                    reason="cysill_welsh_only",
                ),
            )
        if not sentence.strip():
            return EvaluationResult(
                score=0.0,
                details=build_cysill_details(
                    sentence=sentence,
                    matches=[],
                    reason="empty_sentence",
                ),
            )

        try:
            client = self._client_factory()
            payload = client.check(sentence)
        except Exception as exc:  # pragma: no cover - network / env dependent
            return EvaluationResult(
                score=0.0,
                details=build_cysill_details(
                    sentence=sentence,
                    matches=[],
                    error=str(exc),
                ),
            )

        if not payload.get("success", False):
            errors = payload.get("errors") or ["cysill_request_failed"]
            return EvaluationResult(
                score=0.0,
                details=build_cysill_details(
                    sentence=sentence,
                    matches=[],
                    error="; ".join(str(e) for e in errors),
                ),
            )

        matches = list(payload.get("result") or [])
        details = build_cysill_details(sentence=sentence, matches=matches)
        return EvaluationResult(
            score=1.0 if details["passed"] else 0.0,
            details=details,
        )
