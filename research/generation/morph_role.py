"""Cheap local proxy for ``target_form_use == correct_main_verb``.

Uses spaCy's Spanish dependency parse: the expected surface form must appear
as a whole-word token whose dependency label is ``ROOT``.  This is intentionally
stricter than expected-form presence and far cheaper than the LLM judge, so it
can gate decode-time rejection / resample.
"""

from __future__ import annotations

from research.evaluation.sentence.verb_morphology import _get_spacy_nlp
from research.generation.morph_bans import normalize_surface

DEFAULT_SPACY_MODEL = "es_core_news_sm"


def expected_form_is_main_verb(
    sentence: str,
    expected_form: str,
    *,
    model_name: str = DEFAULT_SPACY_MODEL,
) -> bool:
    """Return True when *expected_form* is the sentence's dependency ROOT."""
    text = (sentence or "").strip()
    target = normalize_surface(expected_form or "")
    if not text or not target:
        return False
    nlp = _get_spacy_nlp(model_name)
    doc = nlp(text)
    for token in doc:
        if token.dep_ != "ROOT":
            continue
        if normalize_surface(token.text) == target:
            return True
    return False
