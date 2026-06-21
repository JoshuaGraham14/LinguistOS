"""Generation package — generator registry and base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from research.generation.baseline_gpt import BaselineGPTGenerator, FormInjectedGPTGenerator
from research.generation.baseline_hf import BaselineHFGenerator, FormInjectedHFGenerator
from research.generation.individual_gpt import IndividualGPTGenerator

if TYPE_CHECKING:
    from research.generation.base import BaseGenerator

GENERATOR_REGISTRY: dict[str, type[BaseGenerator]] = {
    "baseline_gpt": BaselineGPTGenerator,
    "baseline_gpt_form_injected": FormInjectedGPTGenerator,
    "baseline_hf": BaselineHFGenerator,
    "baseline_hf_form_injected": FormInjectedHFGenerator,
    "individual_gpt": IndividualGPTGenerator,
}
