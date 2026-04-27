"""Sentence generation endpoint.

Baseline implementation: a single ChatGPT call with a basic prompt that asks
the model to produce N candidate Spanish sentences for a given target word
and morpho-syntactic constraints.

The richer Generate -> Analyze -> Validate -> Score -> Rank pipeline is the
research focus and lives elsewhere; this endpoint is intentionally thin.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()


class GenerateRequest(BaseModel):
    word: str
    translation: str
    tense: str = "present"
    person: str = "3rd"
    number: str = "singular"
    num_candidates: int = Field(default=3, ge=1, le=10)
    sentence_length: str | None = None
    direction: str | None = None


class Candidate(BaseModel):
    sentence: str
    translation: str
    score: float = 1.0


class GenerateResponse(BaseModel):
    candidates: list[Candidate]
    mock: bool = False


def _build_prompt(req: GenerateRequest) -> str:
    length = req.sentence_length or "short"
    return (
        "You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word: "{req.word}" (English: "{req.translation}")\n'
        f"Constraints: tense={req.tense}, person={req.person}, "
        f"number={req.number}, length={length}.\n"
        f"Produce {req.num_candidates} natural, {length}-length Spanish "
        "sentences that contain the target word, each with its English "
        "translation.\n"
        "Reply ONLY as JSON in this exact shape:\n"
        '{"candidates":[{"sentence":"...","translation":"..."}, ...]}'
    )


def _parse_candidates(raw: str) -> list[Candidate]:
    data: Any = json.loads(raw)
    items = data.get("candidates", []) if isinstance(data, dict) else []
    out: list[Candidate] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        sentence = str(item.get("sentence", "")).strip()
        translation = str(item.get("translation", "")).strip()
        if sentence and translation:
            out.append(Candidate(sentence=sentence, translation=translation, score=1.0))
    return out


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    if not settings.openai_api_key:
        return GenerateResponse(candidates=[], mock=True)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful Spanish language tutor. "
                    "Always respond with valid JSON.",
                },
                {"role": "user", "content": _build_prompt(req)},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        candidates = _parse_candidates(raw)
        if not candidates:
            return GenerateResponse(candidates=[], mock=True)
        return GenerateResponse(candidates=candidates, mock=False)
    except Exception:
        return GenerateResponse(candidates=[], mock=True)
