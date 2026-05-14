"""Generation package — generator registry and base class."""

from __future__ import annotations

from typing import TYPE_CHECKING

from research.generation.baseline_gpt import BaselineGPTGenerator
from research.generation.individual_gpt import IndividualGPTGenerator

if TYPE_CHECKING:
    from research.generation.base import BaseGenerator

GENERATOR_REGISTRY: dict[str, type[BaseGenerator]] = {
    "baseline_gpt": BaselineGPTGenerator,
    "individual_gpt": IndividualGPTGenerator,
}
