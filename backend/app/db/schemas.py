"""Pydantic schemas for request/response payloads."""
from pydantic import BaseModel


class SentenceCandidate(BaseModel):
    """A generated sentence with score and morpho-syntactic features."""
    sentence: str
    translation: str | None = None
    score: float
    features: dict | None = None


class GenerateRequest(BaseModel):
    """Request to generate Spanish sentences with constraints."""
    word: str
    translation: str
    tense: str
    person: str
    number: str
    num_candidates: int = 5


class GenerateResponse(BaseModel):
    """Response with ranked sentence candidates."""
    candidates: list[SentenceCandidate]
    mock: bool = False
