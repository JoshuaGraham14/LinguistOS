"""Individual GPT generation -- one API call per sample.

Same prompt and model as baseline_gpt, but requests exactly one candidate
per call and repeats N times. This tests whether batching multiple
candidates in a single prompt degrades quality or diversity.
"""

from __future__ import annotations

from research.generation.base import BaseGenerator
from research.generation.baseline_gpt import generate


class IndividualGPTGenerator(BaseGenerator):
    """Makes N separate API calls, each requesting one candidate."""

    def __init__(self, model: str = "gpt-5.4-nano", temperature: float = 0.7):
        self._model = model
        self._temperature = temperature

    @property
    def name(self) -> str:
        return "individual_gpt"

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
    ) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        for _ in range(num_candidates):
            batch = generate(
                keyword=keyword,
                translation=translation,
                tense=tense,
                person=person,
                number=number,
                num_candidates=1,
                target_language=target_language,
                cefr_level=cefr_level,
                model=self._model,
                temperature=self._temperature,
            )
            results.extend(batch)
        return results
