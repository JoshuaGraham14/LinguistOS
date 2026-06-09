"""Abstract base class for sentence generators."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseGenerator(ABC):
    """A generator produces candidate sentences for a given constraint set."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this generation method (e.g. 'baseline_gpt')."""

    @abstractmethod
    def generate(
        self,
        keyword: str,
        translation: str,
        tense: str,
        person: str,
        number: str,
        num_candidates: int,
        *,
        target_language: str = "es",
        cefr_level: str | None = None,
        sentence_length: str = "short",
        explicit_subject_required: bool = False,
    ) -> list[dict[str, str]]:
        """Return up to *num_candidates* ``{sentence, translation}`` dicts."""
