#!/bin/bash
# Shared cache / runtime env for long cluster jobs (HF, LanguageTool, logging).
# Usage: source research/scripts/cluster/research_cache_env.sh
#
# Expects PROJECT to be set by the caller.

: "${PROJECT:?set PROJECT before sourcing research_cache_env.sh}"

export HF_HOME="${PROJECT}/.cache/huggingface"
export TRANSFORMERS_CACHE="${HF_HOME}"
export LTP_PATH="${PROJECT}/.cache/language_tool_python"
export PYTHONUNBUFFERED=1

mkdir -p "${HF_HOME}" "${LTP_PATH}"
