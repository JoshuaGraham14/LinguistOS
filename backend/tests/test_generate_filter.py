"""Constrained generation filter (LOS-502).

We exercise the pure helpers — the OpenAI client itself stays mocked
out, since the filter is the part with interesting behaviour.
"""

from __future__ import annotations

from app.api.generate import (
    Candidate,
    _filter_by_lexicon,
)


class _Fake:
    """Stand-in for a Vocab row exposing only the fields the filter reads."""

    def __init__(self, *, vid: int, lemma: str, surface: str | None = None) -> None:
        self.id = vid
        self.word = surface or lemma
        self.lemma = lemma
        self.surface_form = surface or lemma
        self.surface_forms = [surface or lemma]


def _cand(sentence: str) -> Candidate:
    return Candidate(sentence=sentence, translation="…", score=1.0)


def test_filter_passes_sentences_built_from_allowed_vocab() -> None:
    allowed = [
        _Fake(vid=1, lemma="comer", surface="como"),
        _Fake(vid=2, lemma="pan"),
    ]
    candidates = [_cand("Yo como pan.")]

    passing, used = _filter_by_lexicon(candidates, allowed)
    assert len(passing) == 1
    assert used == [1, 2]


def test_filter_drops_sentences_with_unknown_content_words() -> None:
    allowed = [_Fake(vid=1, lemma="pan")]
    candidates = [_cand("Como manzanas y pan.")]

    passing, _ = _filter_by_lexicon(candidates, allowed)
    assert passing == []


def test_filter_treats_closed_class_words_as_free() -> None:
    allowed = [
        _Fake(vid=1, lemma="comer", surface="como"),
        _Fake(vid=2, lemma="pan"),
    ]
    # "el", "y", "para" are closed-class function words — they should
    # not cause rejection even though they aren't in the lexicon.
    candidates = [_cand("Como el pan y para mí.")]

    passing, used = _filter_by_lexicon(candidates, allowed)
    assert len(passing) == 1
    assert 1 in used and 2 in used


def test_filter_no_op_when_no_allowed_vocab() -> None:
    candidates = [_cand("Anything goes here.")]
    passing, used = _filter_by_lexicon(candidates, [])
    assert passing == candidates
    assert used == []
