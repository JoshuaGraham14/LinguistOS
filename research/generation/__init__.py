"""Generation package — generator registry and base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from research.generation.baseline_gpt import BaselineGPTGenerator, FormInjectedGPTGenerator
from research.generation.baseline_hf import (
    BaselineHFGenerator,
    FormInjectedExplicitHFGenerator,
    FormInjectedHFGenerator,
    FormInjectedPlainHFGenerator,
    PlainHFGenerator,
)
from research.generation.constrained_hf import (
    ConstrainedHFHardInjectPlainBGenerator,
    ConstrainedHFHardInjectPlainGenerator,
    ConstrainedHFHardJsonGenerator,
    ConstrainedHFHardPlainBGenerator,
    ConstrainedHFHardPlainGenerator,
    ConstrainedHFSoftDiversePlainGenerator,
    ConstrainedHFSoftInjectPlainABGenerator,
    ConstrainedHFSoftInjectPlainAGenerator,
    ConstrainedHFSoftInjectPlainBGenerator,
    ConstrainedHFSoftInjectPlainGenerator,
    ConstrainedHFSoftJsonGenerator,
    ConstrainedHFSoftPlainABGenerator,
    ConstrainedHFSoftPlainAGenerator,
    ConstrainedHFSoftPlainBGenerator,
    ConstrainedHFSoftPlainGenerator,
)
from research.generation.individual_gpt import IndividualGPTGenerator

if TYPE_CHECKING:
    from research.generation.base import BaseGenerator

GENERATOR_REGISTRY: dict[str, type[BaseGenerator]] = {
    "baseline_gpt": BaselineGPTGenerator,
    "baseline_gpt_form_injected": FormInjectedGPTGenerator,
    "baseline_hf": BaselineHFGenerator,
    "baseline_hf_plain": PlainHFGenerator,
    "baseline_hf_form_injected": FormInjectedHFGenerator,
    "baseline_hf_form_injected_plain": FormInjectedPlainHFGenerator,
    "baseline_hf_form_injected_explicit": FormInjectedExplicitHFGenerator,
    "constrained_hf_hard_plain": ConstrainedHFHardPlainGenerator,
    "constrained_hf_hard_plain_b": ConstrainedHFHardPlainBGenerator,
    "constrained_hf_hard_json": ConstrainedHFHardJsonGenerator,
    "constrained_hf_hard_inject_plain": ConstrainedHFHardInjectPlainGenerator,
    "constrained_hf_hard_inject_plain_b": ConstrainedHFHardInjectPlainBGenerator,
    "constrained_hf_soft_plain": ConstrainedHFSoftPlainGenerator,
    "constrained_hf_soft_plain_a": ConstrainedHFSoftPlainAGenerator,
    "constrained_hf_soft_plain_b": ConstrainedHFSoftPlainBGenerator,
    "constrained_hf_soft_plain_ab": ConstrainedHFSoftPlainABGenerator,
    "constrained_hf_soft_inject_plain": ConstrainedHFSoftInjectPlainGenerator,
    "constrained_hf_soft_inject_plain_a": ConstrainedHFSoftInjectPlainAGenerator,
    "constrained_hf_soft_inject_plain_b": ConstrainedHFSoftInjectPlainBGenerator,
    "constrained_hf_soft_inject_plain_ab": ConstrainedHFSoftInjectPlainABGenerator,
    "constrained_hf_soft_json": ConstrainedHFSoftJsonGenerator,
    "constrained_hf_soft_diverse_plain": ConstrainedHFSoftDiversePlainGenerator,
    "individual_gpt": IndividualGPTGenerator,
}
