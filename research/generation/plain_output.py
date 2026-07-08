"""Plain-text generation output parsing for the evaluation pipeline.

Plain arms return ``{sentence, translation}`` dicts compatible with
``run_experiment``. Translation is empty — evaluators (expected-form,
LanguageTool, length) score the Spanish sentence only.
"""

from __future__ import annotations

import re

from research.generation.baseline_hf import _THINKING_RE

# Stored in ``GeneratedSentence.translation`` for plain-output arms.
PLAIN_NO_TRANSLATION = ""

_JSONish_RE = re.compile(r"^\s*\{", re.DOTALL)


def strip_model_artifacts(raw: str) -> str:
    """Remove thinking blocks and common chat tail tokens from raw decode."""
    cleaned = _THINKING_RE.sub("", raw)
    for token in ('<|im_end|>', '<|endoftext|>', '<|im_start|>'):
        cleaned = cleaned.replace(token, "")
    return cleaned.strip()


def parse_plain_sentence(raw: str) -> tuple[str, str]:
    """Extract one Spanish sentence from plain model output.

    Returns ``(sentence, parse_mode)`` where *parse_mode* is ``plain``,
    ``empty``, or ``json_leak`` (model emitted JSON despite plain instruction).
    """
    text = strip_model_artifacts(raw)
    if not text:
        return "", "empty"

    if _JSONish_RE.match(text):
        return "", "json_leak"

    line = text.splitlines()[0].strip()
    line = re.sub(r"^(?:Spanish|Sentence)\s*:\s*", "", line, flags=re.IGNORECASE)
    line = line.strip('"').strip("'").strip()
    if not line:
        return "", "empty"
    return line, "plain"


def candidate_from_plain(raw: str) -> tuple[dict[str, str], str]:
    """Build a pipeline candidate dict plus parse mode."""
    sentence, mode = parse_plain_sentence(raw)
    return (
        {"sentence": sentence, "translation": PLAIN_NO_TRANSLATION},
        mode,
    )
