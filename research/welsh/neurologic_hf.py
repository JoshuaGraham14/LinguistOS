"""Welsh Neurologic generators using Eurfa thin morph bans.

Subclasses Spanish Neurologic Fix-B arms but routes ban construction and the
positive literal through ``research.welsh.morph_bans`` so Spanish
``morph_bans.py`` stays untouched.

Morph-ban helpers are imported lazily inside methods to avoid a circular import
via ``research.generation`` package init.
"""

from __future__ import annotations

from typing import Any

from research.generation.morph_bans import MorphBanSet
from research.generation.neurologic_hf import (
    NeurologicHFThinInjectPlainBGenerator,
    NeurologicHFThinPlainBGenerator,
)


class WelshNeurologicHFThinPlainBGenerator(NeurologicHFThinPlainBGenerator):
    """Welsh thin CNF Neurologic + Fix-B plain (no form inject)."""

    @property
    def name(self) -> str:
        return "welsh_neurologic_hf_thin_plain_b"

    def _job_expected_form(self, constraints: dict[str, Any]) -> str:
        from research.welsh.morph_bans import welsh_neurologic_positive_form

        return welsh_neurologic_positive_form(constraints)

    def _job_morph_ban_set(
        self,
        keyword: str,
        constraints: dict[str, Any],
    ) -> MorphBanSet | None:
        if not self._USE_MORPH_BANS:
            return None
        from research.welsh.morph_bans import build_welsh_morph_ban_set

        return build_welsh_morph_ban_set(
            keyword,
            constraints,
            mode="thin",
        )


class WelshNeurologicHFThinInjectPlainBGenerator(
    NeurologicHFThinInjectPlainBGenerator
):
    """Welsh thin CNF Neurologic + Fix-B form inject."""

    @property
    def name(self) -> str:
        return "welsh_neurologic_hf_thin_inject_plain_b"

    def _job_expected_form(self, constraints: dict[str, Any]) -> str:
        from research.welsh.morph_bans import welsh_neurologic_positive_form

        return welsh_neurologic_positive_form(constraints)

    def _job_morph_ban_set(
        self,
        keyword: str,
        constraints: dict[str, Any],
    ) -> MorphBanSet | None:
        if not self._USE_MORPH_BANS:
            return None
        from research.welsh.morph_bans import build_welsh_morph_ban_set

        return build_welsh_morph_ban_set(
            keyword,
            constraints,
            mode="thin",
        )
