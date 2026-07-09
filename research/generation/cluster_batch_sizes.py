"""Recommended HF batch sizes for A30 (24 GB) cluster Qwen runs."""

from __future__ import annotations

import os
from typing import Literal

from research.generation.baseline_hf import DEFAULT_HF_BATCH_SIZE

WorkloadProfile = Literal["short", "medium", "json", "heavy"]

_PROFILE_BATCH: dict[WorkloadProfile, dict[str, int]] = {
    "short": {"qwen06b": 32, "qwen17b": 32, "qwen4b": 16, "default": 32},
    "medium": {"qwen06b": 16, "qwen17b": 16, "qwen4b": 8, "default": 16},
    "json": {"qwen06b": 16, "qwen17b": 16, "qwen4b": 8, "default": 16},
    "heavy": {"qwen06b": 8, "qwen17b": 8, "qwen4b": 4, "default": 8},
}


def model_key_from_id(model_id: str) -> str:
    lowered = model_id.lower()
    if "0.6b" in lowered:
        return "qwen06b"
    if "1.7b" in lowered:
        return "qwen17b"
    if "4b" in lowered:
        return "qwen4b"
    return "default"


def batch_size_for_profile(
    profile: WorkloadProfile,
    *,
    model_id: str | None = None,
    model_key: str | None = None,
) -> int:
    key = model_key or (model_key_from_id(model_id) if model_id else "default")
    return _PROFILE_BATCH[profile].get(key, _PROFILE_BATCH[profile]["default"])


def resolve_hf_batch_size(
    *,
    model_id: str,
    profile: WorkloadProfile = "json",
    yaml_override: int | None = None,
) -> int:
    """Resolve batch size: ``HF_BATCH_SIZE`` env > YAML > profile table."""
    env = os.environ.get("HF_BATCH_SIZE")
    if env is not None and env.strip():
        return int(env)
    if yaml_override is not None:
        return int(yaml_override)
    return batch_size_for_profile(profile, model_id=model_id)
