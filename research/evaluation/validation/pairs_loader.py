"""Loader for the naturalness validation stimuli YAML.

Provides typed access to minimal-pair fixtures used by the smoke harness
that gates promotion of ``fluency_perplexity`` and ``naturalness_llm_judge``
to Direction 1.2 arm databases.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CATEGORIES: frozenset[str] = frozenset(
    {
        "odd_collocation",
        "agreement",
        "role_vs_mention",
        "repetition",
        "tense_conflict",
        "rare_but_correct",
    }
)

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

DEFAULT_PAIRS_YAML: Path = (
    Path(__file__).resolve().parent / "naturalness_pairs.yaml"
)


@dataclass(frozen=True)
class HumanLabel:
    grammaticality: int
    naturalness: int
    semantic_coherence: int
    target_form_use: str
    flags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "grammaticality": self.grammaticality,
            "naturalness": self.naturalness,
            "semantic_coherence": self.semantic_coherence,
            "target_form_use": self.target_form_use,
            "flags": list(self.flags),
        }


@dataclass(frozen=True)
class PairSentence:
    text: str
    human_label: HumanLabel


@dataclass(frozen=True)
class ValidationPair:
    pair_id: str
    category: str
    expected_form: str
    lemma: str
    tense: str
    person: str
    number: str
    target_language: str
    preferred: str  # "natural" | "awkward"
    natural: PairSentence
    awkward: PairSentence
    notes: str | None

    @property
    def preferred_sentence(self) -> PairSentence:
        return self.natural if self.preferred == "natural" else self.awkward

    @property
    def dispreferred_sentence(self) -> PairSentence:
        return self.awkward if self.preferred == "natural" else self.natural

    def constraints_for(self, side: str) -> dict[str, Any]:
        """Build a ``constraints`` dict shaped like the pipeline's evaluator input."""
        return {
            "keyword": self.lemma,
            "expected_form": self.expected_form,
            "lemma": self.lemma,
            "tense": self.tense,
            "person": self.person,
            "number": self.number,
            "target_language": self.target_language,
            "sentence_length": "short",
            "pair_id": self.pair_id,
            "pair_side": side,
        }


@dataclass(frozen=True)
class ValidationSet:
    version: int
    prompt_version: str
    pairs: tuple[ValidationPair, ...]

    def __iter__(self):
        return iter(self.pairs)

    def __len__(self) -> int:
        return len(self.pairs)

    def by_category(self) -> dict[str, list[ValidationPair]]:
        buckets: dict[str, list[ValidationPair]] = {c: [] for c in CATEGORIES}
        for pair in self.pairs:
            buckets[pair.category].append(pair)
        return buckets


def _parse_label(raw: dict[str, Any], *, ctx: str) -> HumanLabel:
    required = {
        "grammaticality",
        "naturalness",
        "semantic_coherence",
        "target_form_use",
        "flags",
    }
    missing = required - set(raw)
    if missing:
        raise ValueError(
            f"{ctx}: human_label missing keys {sorted(missing)}"
        )
    for k in ("grammaticality", "naturalness", "semantic_coherence"):
        v = raw[k]
        if not isinstance(v, int) or not (1 <= v <= 5):
            raise ValueError(f"{ctx}: {k}={v!r} must be int in 1..5")
    tfu = str(raw["target_form_use"])
    if tfu not in TARGET_FORM_USE_VALUES:
        raise ValueError(
            f"{ctx}: target_form_use={tfu!r} not in {sorted(TARGET_FORM_USE_VALUES)}"
        )
    flags_raw = raw["flags"] or []
    if not isinstance(flags_raw, list):
        raise ValueError(f"{ctx}: flags must be a list, got {type(flags_raw).__name__}")
    flags: list[str] = []
    for f in flags_raw:
        s = str(f)
        if s not in FLAG_VALUES:
            raise ValueError(
                f"{ctx}: flag {s!r} not in {sorted(FLAG_VALUES)}"
            )
        flags.append(s)
    return HumanLabel(
        grammaticality=int(raw["grammaticality"]),
        naturalness=int(raw["naturalness"]),
        semantic_coherence=int(raw["semantic_coherence"]),
        target_form_use=tfu,
        flags=tuple(flags),
    )


def _parse_sentence(raw: dict[str, Any], *, ctx: str) -> PairSentence:
    text = str(raw.get("text", "")).strip()
    if not text:
        raise ValueError(f"{ctx}: empty sentence text")
    label = _parse_label(raw.get("human_label") or {}, ctx=ctx)
    return PairSentence(text=text, human_label=label)


def _parse_pair(raw: dict[str, Any]) -> ValidationPair:
    pair_id = str(raw.get("pair_id") or "").strip()
    if not pair_id:
        raise ValueError("pair missing pair_id")
    category = str(raw.get("category") or "").strip()
    if category not in CATEGORIES:
        raise ValueError(
            f"{pair_id}: category={category!r} not in {sorted(CATEGORIES)}"
        )
    preferred = str(raw.get("preferred") or "natural").strip()
    if preferred not in {"natural", "awkward"}:
        raise ValueError(
            f"{pair_id}: preferred={preferred!r} must be 'natural' or 'awkward'"
        )
    sentences = raw.get("sentences") or {}
    if "natural" not in sentences or "awkward" not in sentences:
        raise ValueError(
            f"{pair_id}: sentences must contain 'natural' and 'awkward' entries"
        )
    return ValidationPair(
        pair_id=pair_id,
        category=category,
        expected_form=str(raw.get("expected_form") or "").strip(),
        lemma=str(raw.get("lemma") or "").strip(),
        tense=str(raw.get("tense") or "").strip(),
        person=str(raw.get("person") or "").strip(),
        number=str(raw.get("number") or "").strip(),
        target_language=str(raw.get("target_language") or "es").strip() or "es",
        preferred=preferred,
        natural=_parse_sentence(sentences["natural"], ctx=f"{pair_id}.natural"),
        awkward=_parse_sentence(sentences["awkward"], ctx=f"{pair_id}.awkward"),
        notes=(str(raw["notes"]).strip() if raw.get("notes") else None),
    )


def load_validation_pairs(path: Path | None = None) -> ValidationSet:
    """Parse the pairs YAML into a validated :class:`ValidationSet`."""
    src = Path(path) if path is not None else DEFAULT_PAIRS_YAML
    with src.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"{src}: top-level YAML must be a mapping")

    version = int(raw.get("version") or 1)
    prompt_version = str(raw.get("prompt_version") or "").strip() or "v1"
    pairs_raw = raw.get("pairs") or []
    if not isinstance(pairs_raw, list) or not pairs_raw:
        raise ValueError(f"{src}: 'pairs' must be a non-empty list")

    seen: set[str] = set()
    pairs: list[ValidationPair] = []
    for entry in pairs_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"{src}: pair entries must be mappings, got {type(entry).__name__}")
        pair = _parse_pair(entry)
        if pair.pair_id in seen:
            raise ValueError(f"{src}: duplicate pair_id {pair.pair_id!r}")
        seen.add(pair.pair_id)
        pairs.append(pair)

    return ValidationSet(
        version=version,
        prompt_version=prompt_version,
        pairs=tuple(pairs),
    )


__all__ = [
    "CATEGORIES",
    "FLAG_VALUES",
    "TARGET_FORM_USE_VALUES",
    "DEFAULT_PAIRS_YAML",
    "HumanLabel",
    "PairSentence",
    "ValidationPair",
    "ValidationSet",
    "load_validation_pairs",
]
