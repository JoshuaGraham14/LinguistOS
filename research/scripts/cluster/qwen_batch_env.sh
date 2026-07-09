#!/bin/bash
# Recommended padded HF batch sizes for Qwen on A30 (24 GB).
# shellcheck disable=SC2034
# Usage: source research/scripts/cluster/qwen_batch_env.sh

# Short outputs (Diagnostic 1/1B/2B, ≤64 tokens)
BATCH_SHORT_06B=32
BATCH_SHORT_17B=32
BATCH_SHORT_4B=16

# Medium outputs (Diagnostic 2A, 3A — ~128–256 tokens)
BATCH_MEDIUM_06B=16
BATCH_MEDIUM_17B=16
BATCH_MEDIUM_4B=8

# JSON single-sample (Diagnostic 3B/C, 4A, Direction 1 inject JSON)
BATCH_JSON_06B=16
BATCH_JSON_17B=16
BATCH_JSON_4B=8

# Heavy pass@10 / n=10 (Diagnostic 3D, Diagnostic 5)
BATCH_HEAVY_17B=8
BATCH_HEAVY_4B=4

# Pipeline default when method YAML omits hf_batch_size
export HF_BATCH_SIZE="${HF_BATCH_SIZE:-8}"
