"""Few-shot in-context-learning generators (Direction 5).

A prompt-time conditioning arm to contrast with decode-time constrained
decoding (Direction 1) and train-time LoRA adaptation (Direction 2). The
model is shown K worked (constraint -> sentence) demonstrations prepended to
the standard Fix-B plain prompt; no weights change and no decode constraint
is applied (except in the soft-combo arm, which additionally keeps the
Direction 1.2 soft logit bias).

Demonstrations are inlined into the user turn rather than rendered as
separate chat turns: this keeps the existing padded-batch generation path
untouched and works identically under greedy (`generate_many`) and soft-beam
(constrained) decoding.
"""

from __future__ import annotations

from typing import Any

from research.generation.baseline_hf import PlainHFBGenerator
from research.generation.constrained_hf import ConstrainedHFSoftPlainBGenerator
from research.generation.fewshot import (
    format_demonstration_block,
    load_exemplar_pool,
    select_exemplars,
)

DEFAULT_FEWSHOT_K = 3


class FewShotPromptMixin:
    """Prepend selected few-shot demonstrations to the base plain prompt.

    Concrete generators set ``_FEWSHOT_MODE`` (``"static"`` | ``"dynamic"``)
    and ``_FEWSHOT_K``. The exemplar pool is loaded lazily and cached.
    """

    _FEWSHOT_MODE: str = "dynamic"
    _FEWSHOT_K: int = DEFAULT_FEWSHOT_K
    _FEWSHOT_POOL_PATH: str | None = None

    def _fewshot_block(self, constraints: dict[str, Any], keyword: str) -> str:
        pool = load_exemplar_pool(self._FEWSHOT_POOL_PATH)
        exemplars = select_exemplars(
            pool,
            self._FEWSHOT_MODE,
            self._FEWSHOT_K,
            constraints=constraints,
            exclude_verb=keyword,
        )
        return format_demonstration_block(exemplars)

    def _build_user_prompt(
        self,
        *,
        keyword: str,
        translation: str,
        target_language: str,
        constraints: dict[str, Any],
        num_candidates: int,
        sentence_length: str,
        cefr_level: str | None,
        explicit_subject_required: bool,
        inject_expected_form: str | None,
        scene_hint: str | None = None,
    ) -> str:
        base = super()._build_user_prompt(  # type: ignore[misc]
            keyword=keyword,
            translation=translation,
            target_language=target_language,
            constraints=constraints,
            num_candidates=num_candidates,
            sentence_length=sentence_length,
            cefr_level=cefr_level,
            explicit_subject_required=explicit_subject_required,
            inject_expected_form=inject_expected_form,
            scene_hint=scene_hint,
        )
        block = self._fewshot_block(constraints, keyword)
        if not block:
            return base
        return f"{block}\n\n{base}"


class FewShotStaticHFGenerator(FewShotPromptMixin, PlainHFBGenerator):
    """K fixed demonstrations (same for every cell) + Fix-B greedy decode."""

    _FEWSHOT_MODE = "static"
    _FEWSHOT_K = DEFAULT_FEWSHOT_K

    @property
    def name(self) -> str:
        return "fewshot_hf_static_plain_b"


class FewShotDynamicHFGenerator(FewShotPromptMixin, PlainHFBGenerator):
    """K tense-matched demonstrations (per cell) + Fix-B greedy decode."""

    _FEWSHOT_MODE = "dynamic"
    _FEWSHOT_K = DEFAULT_FEWSHOT_K

    @property
    def name(self) -> str:
        return "fewshot_hf_dynamic_plain_b"


class FewShotDynamicSoftHFGenerator(
    FewShotPromptMixin, ConstrainedHFSoftPlainBGenerator
):
    """Cross-mechanism combo: tense-matched few-shot prompt + soft logit bias.

    Tests whether prompt-time (ICL) and decode-time (soft bias, lambda=5)
    conditioning stack or interfere.
    """

    _FEWSHOT_MODE = "dynamic"
    _FEWSHOT_K = DEFAULT_FEWSHOT_K

    @property
    def name(self) -> str:
        return "fewshot_hf_dynamic_soft_plain_b"
