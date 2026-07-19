"""Cheap local proxy for ``target_form_use == correct_main_verb``.

No spaCy / parser dependency: this is intentionally a lightweight gate for
decode-time rejection / resample on the cluster.  It is stricter than raw
expected-form presence, but weaker than a dependency ROOT check.
"""

from __future__ import annotations

import re

from research.generation.morph_bans import normalize_surface

_WORD_RE = re.compile(r"[^\W\d_]+", flags=re.UNICODE)
_QUOTED_SPAN_RE = re.compile(
    r"[\"“”«»'].*?[\"“”«»']",
    flags=re.DOTALL,
)
_META_MENTION_RE_TMPL = (
    r"(?i)\b(?:forma|palabra|verbo|conjugaci[oó]n)\b[^\n.!?]{0,40}\b{form}\b"
)
_SUBJECT_VERB_RE_TMPL = (
    r"(?i)\b(?:yo|t[uú]|[eé]l|ella|usted|nosotros|nosotras|"
    r"vosotros|vosotras|ellos|ellas|ustedes)\s+{form}\b"
)
_LIGHT_MENTION_RE_TMPL = (
    r"(?i)\b(?:es|incluye|menciona(?:mos)?|dij[oe]|llamad[oa])\s+{form}\b"
)


def _with_form(template: str, form_pat: str) -> str:
    return template.replace("{form}", form_pat)


def expected_form_is_main_verb(sentence: str, expected_form: str) -> bool:
    """Return True when *expected_form* looks used as a real sentence verb.

    Passes when the gold form appears as an unquoted whole word and is not
    framed as a metalanguage mention.  A matching subject + form pattern is
    treated as strong evidence.
    """
    text = (sentence or "").strip()
    target = normalize_surface(expected_form or "")
    if not text or not target:
        return False

    form_pat = re.escape(expected_form.strip())
    unquoted = _QUOTED_SPAN_RE.sub(" ", text)
    words = {normalize_surface(token) for token in _WORD_RE.findall(unquoted)}
    if target not in words:
        return False

    if re.search(_with_form(_META_MENTION_RE_TMPL, form_pat), text):
        return False

    if re.search(_with_form(_SUBJECT_VERB_RE_TMPL, form_pat), text):
        return True

    if re.search(_with_form(_LIGHT_MENTION_RE_TMPL, form_pat), text):
        return False

    return True
