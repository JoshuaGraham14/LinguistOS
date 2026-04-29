"""Sentence generation endpoint.

Baseline implementation: a single ChatGPT call with a basic prompt that asks
the model to produce N candidate Spanish sentences for a given target word
and morpho-syntactic constraints.

LOS-502 extends this with optional lexicon constraints so generated
sentences only use words the learner already knows (plus optional stretch
words). Validation is deliberately conservative — a candidate that uses any
unknown content word is dropped, with graceful fallback to unconstrained.
"""

from __future__ import annotations

import json
import re
from random import sample
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db
from app.db.models import Vocab

router = APIRouter()

LexiconConstraint = Literal["off", "known_only", "known_plus_stretch"]


class GenerateRequest(BaseModel):
    word: str
    translation: str
    tense: str = "present"
    person: str = "3rd"
    number: str = "singular"
    num_candidates: int = Field(default=3, ge=1, le=10)
    sentence_length: str | None = None
    direction: str | None = None

    # LOS-502 constrained generation.
    lexicon_constraint: LexiconConstraint = "off"
    workspace_id: int | None = None
    stretch_count: int = Field(default=0, ge=0, le=20)
    extra_allowed_vocab_ids: list[int] = Field(default_factory=list)


class Candidate(BaseModel):
    sentence: str
    translation: str
    score: float = 1.0


class GenerateResponse(BaseModel):
    candidates: list[Candidate]
    mock: bool = False
    constrained: bool = False
    used_vocab_ids: list[int] = Field(default_factory=list)


def _allowed_vocab(req: GenerateRequest, db: Session) -> list[Vocab]:
    """Resolve the lexicon allowed for this generation, if any."""
    if req.lexicon_constraint == "off" or req.workspace_id is None:
        return []

    rows = db.scalars(
        select(Vocab).where(Vocab.workspace_id == req.workspace_id)
    ).all()
    if req.lexicon_constraint == "known_only":
        return [r for r in rows if r.learned]
    # known_plus_stretch
    known = [r for r in rows if r.learned]
    pool = [r for r in rows if not r.learned and r.id not in {k.id for k in known}]
    if req.stretch_count and pool:
        stretch = sample(pool, k=min(req.stretch_count, len(pool)))
    else:
        stretch = []
    extras = [r for r in rows if r.id in set(req.extra_allowed_vocab_ids)]
    return list({r.id: r for r in [*known, *stretch, *extras]}.values())


def _build_prompt(req: GenerateRequest, allowed: list[Vocab]) -> str:
    length = req.sentence_length or "short"
    constraint_block = ""
    if allowed:
        words = ", ".join(sorted({(r.lemma or r.word) for r in allowed}))
        constraint_block = (
            "\nVocabulary constraint: every content word must come from this list "
            "(plus closed-class function words like articles, prepositions, "
            f"pronouns, and conjugations of listed verbs):\n{words}\n"
        )
    return (
        "You generate Spanish example sentences for vocabulary practice.\n"
        f'Target word: "{req.word}" (English: "{req.translation}")\n'
        f"Constraints: tense={req.tense}, person={req.person}, "
        f"number={req.number}, length={length}.{constraint_block}\n"
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


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[\w\u00C0-\u017F]+", text)]


# Spanish closed-class words and very common short tokens that are safe to
# treat as "free" inside a constrained generation. Listing them avoids
# false-positive rejections when the LLM uses ordinary connective tissue.
_SPANISH_FREE_TOKENS: frozenset[str] = frozenset(
    {
        # articles
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        # personal pronouns
        "yo", "tú", "tu", "él", "ella", "usted", "nosotros", "nosotras",
        "vosotros", "vosotras", "ellos", "ellas", "ustedes",
        "me", "te", "se", "nos", "os", "lo", "le", "les",
        # possessives
        "mi", "mis", "tus", "su", "sus", "nuestro", "nuestra",
        "nuestros", "nuestras",
        # common prepositions / conjunctions / negations
        "a", "al", "de", "del", "en", "con", "sin", "para", "por",
        "y", "e", "o", "u", "ni", "que", "como", "pero", "si", "no",
        "ya", "muy", "más", "menos", "también", "tampoco", "aún", "aun",
        # demonstratives
        "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
        "aquel", "aquella", "aquellos", "aquellas", "esto", "eso", "aquello",
        # interrogatives / relatives
        "qué", "quién", "quiénes", "cuál", "cuáles", "cuándo", "cómo",
        "dónde", "donde", "cuanto", "cuánto",
    }
)


def _filter_by_lexicon(
    candidates: list[Candidate],
    allowed: list[Vocab],
) -> tuple[list[Candidate], list[int]]:
    """Drop candidates that use any content word outside the allowed list.

    Returns ``(passing_candidates, used_vocab_ids)``. Tokens that are
    ≤ 2 characters or that appear in :data:`_SPANISH_FREE_TOKENS` are
    treated as closed-class function words and never rejected.
    """
    if not allowed:
        return candidates, []

    allowed_terms: dict[str, int] = {}
    for r in allowed:
        for term in {r.word, r.lemma, r.surface_form, *(r.surface_forms or [])}:
            if term:
                allowed_terms[term.lower()] = r.id

    passing: list[Candidate] = []
    used_ids: set[int] = set()
    for cand in candidates:
        tokens = _tokenize(cand.sentence)
        unmatched = [
            t
            for t in tokens
            if t not in allowed_terms
            and len(t) > 2
            and t not in _SPANISH_FREE_TOKENS
        ]
        if unmatched:
            continue
        for t in tokens:
            vid = allowed_terms.get(t)
            if vid is not None:
                used_ids.add(vid)
        passing.append(cand)
    return passing, sorted(used_ids)


def _mock_response() -> GenerateResponse:
    return GenerateResponse(candidates=[], mock=True, constrained=False)


@router.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    """Generate sentence candidates, optionally constrained to a lexicon.

    When ``lexicon_constraint`` is ``"off"`` the prompt is unconstrained.
    When it's on but the resolved allowed-list is empty (e.g. a learner
    asked for ``"known_only"`` but has no learned words yet), the LLM is
    still called unconstrained and the response carries ``constrained=False``
    so the UI can surface a "Constraint relaxed" hint.
    """
    constraint_requested = req.lexicon_constraint != "off"
    allowed = _allowed_vocab(req, db)

    if not settings.openai_api_key:
        return _mock_response()

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
                {"role": "user", "content": _build_prompt(req, allowed)},
            ],
        )
        raw = completion.choices[0].message.content or "{}"
        candidates = _parse_candidates(raw)
        if not candidates:
            return _mock_response()

        if constraint_requested and allowed:
            filtered, used_ids = _filter_by_lexicon(candidates, allowed)
            if filtered:
                return GenerateResponse(
                    candidates=filtered,
                    mock=False,
                    constrained=True,
                    used_vocab_ids=used_ids,
                )
            # Constraint dropped everything; surface unconstrained results.
            return GenerateResponse(
                candidates=candidates,
                mock=False,
                constrained=False,
                used_vocab_ids=[],
            )

        # Either no constraint requested, or constraint requested but the
        # learner has no eligible vocab yet. Both cases yield
        # ``constrained=False`` — the UI knows when it asked for one.
        return GenerateResponse(candidates=candidates, mock=False, constrained=False)
    except Exception:
        return _mock_response()
