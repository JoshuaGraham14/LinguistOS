"""Typed view of a method YAML ``config`` block for pipeline and generators."""

from __future__ import annotations

from dataclasses import dataclass

from research.db.models import MethodConfig
from research.evaluation.length_bands import RANDOM_LENGTH, resolve_length_band


@dataclass(frozen=True)
class MethodRunConfig:
    """Generator and prompt settings resolved from a MethodConfig row."""

    model: str = "gpt-5.4-nano"
    temperature: float = 0.7
    sentence_length: str = "short"
    explicit_subject_required: bool = False
    hf_batch_size: int | None = None
    reasoning_effort: str | None = None

    @classmethod
    def from_method_config(cls, method_config: MethodConfig) -> MethodRunConfig:
        raw = method_config.config or {}
        sentence_length = str(raw.get("sentence_length", "short"))
        # Validate early so bad YAML fails at experiment start.
        if sentence_length != RANDOM_LENGTH:
            resolve_length_band(sentence_length)
        hf_batch_size = raw.get("hf_batch_size")
        reasoning_effort = raw.get("reasoning_effort")
        return cls(
            model=str(raw.get("model", "gpt-5.4-nano")),
            temperature=float(raw.get("temperature", 0.7)),
            sentence_length=sentence_length,
            explicit_subject_required=bool(raw.get("explicit_subject_required", False)),
            hf_batch_size=int(hf_batch_size) if hf_batch_size is not None else None,
            reasoning_effort=str(reasoning_effort) if reasoning_effort is not None else None,
        )

    @property
    def is_random_length(self) -> bool:
        return self.sentence_length == RANDOM_LENGTH

    def resolve_length(self, rng) -> str:
        """Return a fixed band label, drawing one when ``sentence_length`` is random."""
        return resolve_length_band(self.sentence_length, rng=rng)
