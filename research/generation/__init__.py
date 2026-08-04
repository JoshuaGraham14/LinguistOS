"""Generation package — generator registry and base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from research.generation.baseline_gpt import BaselineGPTGenerator, FormInjectedGPTGenerator
from research.generation.baseline_gpt_plain import (
    FormInjectedPlainGPTBGenerator,
    PlainGPTBGenerator,
)
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    FormInjectedExplicitHFGenerator,
    FormInjectedHFGenerator,
    FormInjectedPlainHFBGenerator,
    FormInjectedPlainHFGenerator,
    PlainHFBExplicitGenerator,
    PlainHFBGenerator,
    PlainHFGenerator,
)
from research.generation.constrained_hf import (
    ConstrainedHFHardInjectPlainBGenerator,
    ConstrainedHFHardInjectPlainGenerator,
    ConstrainedHFHardJsonGenerator,
    ConstrainedHFHardMorphInjectPlainBGenerator,
    ConstrainedHFHardMorphPlainBGenerator,
    ConstrainedHFHardPlainBGenerator,
    ConstrainedHFHardPlainGenerator,
    ConstrainedHFMorphBanInjectPlainBGenerator,
    ConstrainedHFMorphBanPlainBGenerator,
    ConstrainedHFSoftDiversePlainGenerator,
    ConstrainedHFSoftInjectPlainABGenerator,
    ConstrainedHFSoftInjectPlainAGenerator,
    ConstrainedHFSoftInjectPlainBGenerator,
    ConstrainedHFSoftInjectPlainGenerator,
    ConstrainedHFSoftJsonGenerator,
    ConstrainedHFSoftMorphFormsPlainBGenerator,
    ConstrainedHFSoftMorphInjectPlainBGenerator,
    ConstrainedHFSoftMorphPlainBGenerator,
    ConstrainedHFSoftMorphPronPlainBGenerator,
    ConstrainedHFSoftMorphSoftnegThinInjectPlainBGenerator,
    ConstrainedHFSoftMorphSoftnegThinInjectRolePlainBGenerator,
    ConstrainedHFSoftMorphSoftnegThinPlainBGenerator,
    ConstrainedHFSoftPlainABGenerator,
    ConstrainedHFSoftPlainAGenerator,
    ConstrainedHFSoftPlainBExplicitGenerator,
    ConstrainedHFSoftPlainBGenerator,
    ConstrainedHFSoftPlainGenerator,
)
from research.generation.fewshot_hf import (
    FewShotDynamicHFGenerator,
    FewShotDynamicSoftHFGenerator,
    FewShotStaticHFGenerator,
    FewShotWelshDynamicHFGenerator,
    FewShotWelshStaticHFGenerator,
)
from research.generation.individual_gpt import IndividualGPTGenerator
from research.generation.neurologic_hf import (
    NeurologicHFAgreePlainBGenerator,
    NeurologicHFAgreeScenePlainBGenerator,
    NeurologicHFThinInjectPlainBGenerator,
    NeurologicHFThinPlainBGenerator,
    NeurologicHFThinScenePlainBGenerator,
)

if TYPE_CHECKING:
    from research.generation.base import BaseGenerator

GENERATOR_REGISTRY: dict[str, type[BaseGenerator]] = {
    "baseline_gpt": BaselineGPTGenerator,
    "baseline_gpt_form_injected": FormInjectedGPTGenerator,
    "baseline_gpt_plain_b": PlainGPTBGenerator,
    "baseline_gpt_form_injected_plain_b": FormInjectedPlainGPTBGenerator,
    "baseline_hf": BaselineHFGenerator,
    "baseline_hf_plain": PlainHFGenerator,
    "baseline_hf_plain_b": PlainHFBGenerator,
    "baseline_hf_plain_b_explicit": PlainHFBExplicitGenerator,
    "baseline_hf_form_injected": FormInjectedHFGenerator,
    "baseline_hf_form_injected_plain": FormInjectedPlainHFGenerator,
    "baseline_hf_form_injected_plain_b": FormInjectedPlainHFBGenerator,
    "baseline_hf_form_injected_explicit": FormInjectedExplicitHFGenerator,
    "constrained_hf_hard_plain": ConstrainedHFHardPlainGenerator,
    "constrained_hf_hard_plain_b": ConstrainedHFHardPlainBGenerator,
    "constrained_hf_hard_json": ConstrainedHFHardJsonGenerator,
    "constrained_hf_hard_inject_plain": ConstrainedHFHardInjectPlainGenerator,
    "constrained_hf_hard_inject_plain_b": ConstrainedHFHardInjectPlainBGenerator,
    "constrained_hf_morph_ban_plain_b": ConstrainedHFMorphBanPlainBGenerator,
    "constrained_hf_morph_ban_inject_plain_b": ConstrainedHFMorphBanInjectPlainBGenerator,
    "constrained_hf_hard_morph_plain_b": ConstrainedHFHardMorphPlainBGenerator,
    "constrained_hf_hard_morph_inject_plain_b": ConstrainedHFHardMorphInjectPlainBGenerator,
    "constrained_hf_soft_plain": ConstrainedHFSoftPlainGenerator,
    "constrained_hf_soft_plain_a": ConstrainedHFSoftPlainAGenerator,
    "constrained_hf_soft_plain_b": ConstrainedHFSoftPlainBGenerator,
    "constrained_hf_soft_plain_b_explicit": ConstrainedHFSoftPlainBExplicitGenerator,
    "constrained_hf_soft_plain_ab": ConstrainedHFSoftPlainABGenerator,
    "constrained_hf_soft_inject_plain": ConstrainedHFSoftInjectPlainGenerator,
    "constrained_hf_soft_inject_plain_a": ConstrainedHFSoftInjectPlainAGenerator,
    "constrained_hf_soft_inject_plain_b": ConstrainedHFSoftInjectPlainBGenerator,
    "constrained_hf_soft_inject_plain_ab": ConstrainedHFSoftInjectPlainABGenerator,
    "constrained_hf_soft_json": ConstrainedHFSoftJsonGenerator,
    "constrained_hf_soft_diverse_plain": ConstrainedHFSoftDiversePlainGenerator,
    "constrained_hf_soft_morph_plain_b": ConstrainedHFSoftMorphPlainBGenerator,
    "constrained_hf_soft_morph_inject_plain_b": ConstrainedHFSoftMorphInjectPlainBGenerator,
    "constrained_hf_soft_morph_forms_plain_b": ConstrainedHFSoftMorphFormsPlainBGenerator,
    "constrained_hf_soft_morph_pron_plain_b": ConstrainedHFSoftMorphPronPlainBGenerator,
    "constrained_hf_soft_morph_softneg_thin_plain_b": ConstrainedHFSoftMorphSoftnegThinPlainBGenerator,
    "constrained_hf_soft_morph_softneg_thin_inject_plain_b": ConstrainedHFSoftMorphSoftnegThinInjectPlainBGenerator,
    "constrained_hf_soft_morph_softneg_thin_inject_role_plain_b": ConstrainedHFSoftMorphSoftnegThinInjectRolePlainBGenerator,
    "neurologic_hf_thin_plain_b": NeurologicHFThinPlainBGenerator,
    "neurologic_hf_thin_inject_plain_b": NeurologicHFThinInjectPlainBGenerator,
    "neurologic_hf_agree_plain_b": NeurologicHFAgreePlainBGenerator,
    "neurologic_hf_thin_scene_plain_b": NeurologicHFThinScenePlainBGenerator,
    "neurologic_hf_agree_scene_plain_b": NeurologicHFAgreeScenePlainBGenerator,
    "fewshot_hf_static_plain_b": FewShotStaticHFGenerator,
    "fewshot_hf_dynamic_plain_b": FewShotDynamicHFGenerator,
    "fewshot_hf_dynamic_soft_plain_b": FewShotDynamicSoftHFGenerator,
    "fewshot_hf_welsh_static_plain_b": FewShotWelshStaticHFGenerator,
    "fewshot_hf_welsh_dynamic_plain_b": FewShotWelshDynamicHFGenerator,
    "individual_gpt": IndividualGPTGenerator,
}
