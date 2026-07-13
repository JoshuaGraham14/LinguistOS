"""Reference-free fluency via length-normalized causal-LM perplexity.

The evaluator scores a sentence with a fixed Spanish (or multilingual)
**causal** language model (default: ``BSC-LT/salamandra-2b``) by running one
forward pass, summing per-token negative log-likelihood over the sentence
tokens, and length-normalizing.

- ``score``: ``exp(-mean_nll)`` in ``[0, 1]``. Higher is better, keeping the
  same "higher = better" convention as ``expected_form_match`` and
  ``grammar_languagetool`` so ``mean::fluency_perplexity`` roll-ups read
  naturally alongside the existing metrics.
- ``details.perplexity``: ``exp(mean_nll)``. Lower is better; kept in details
  for plots and paired comparisons.

The Salamandra pretraining objective is next-token prediction, so this is a
proper reference-free fluency score, **not** masked-LM pseudo-perplexity.

Important caveats (documented so the write-up is honest):

- PPL punishes rare-but-correct verb forms. Interpret it **within** a
  morphological cell across arms, never as an absolute quality score.
- We do not send prompt/context; the sentence is scored on its own so the
  scorer is comparable across arms with different prompt scaffolds.
"""

from __future__ import annotations

import math
import os
from typing import Any, Callable

from research.evaluation.sentence.base import BaseEvaluator, EvaluationResult

EVALUATOR_NAME = "fluency_perplexity"
DEFAULT_MODEL_ID = "BSC-LT/salamandra-2b"
DEFAULT_DTYPE = "bfloat16"
SCORER_VERSION = "v1"


class PerplexityScorer:
    """Protocol-ish object: ``.score(sentence)`` -> (mean_nll, token_count)."""

    def score(self, sentence: str) -> tuple[float, int]:  # pragma: no cover - override
        raise NotImplementedError


class HuggingFacePerplexityScorer(PerplexityScorer):
    """Real scorer backed by a Hugging Face causal LM.

    Loads once; forward pass per sentence. Designed for A30 (BF16 CUDA);
    falls back to CPU with a warning if CUDA is not available.
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        *,
        dtype: str = DEFAULT_DTYPE,
        revision: str | None = None,
        device: str | None = None,
        max_length: int = 512,
    ) -> None:
        self.model_id = model_id
        self.dtype_name = dtype
        self.revision = revision
        self.max_length = max_length
        self._tokenizer = None
        self._model = None
        self._device = device
        self._resolved_dtype = None

    def _lazy_init(self) -> None:
        if self._model is not None:
            return
        import torch  # local import: heavy, only when needed
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = self._device or ("cuda" if torch.cuda.is_available() else "cpu")
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(self.dtype_name.lower(), torch.bfloat16)
        # CPU + bf16 is technically supported but very slow and lossy for PPL.
        if device == "cpu" and torch_dtype is torch.bfloat16:
            torch_dtype = torch.float32
            self.dtype_name = "float32"

        kwargs: dict[str, Any] = {"torch_dtype": torch_dtype}
        if self.revision:
            kwargs["revision"] = self.revision

        tokenizer = AutoTokenizer.from_pretrained(self.model_id, revision=self.revision)
        model = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        model.to(device)
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        self._device = device
        self._resolved_dtype = torch_dtype

    def score(self, sentence: str) -> tuple[float, int]:
        import torch

        self._lazy_init()
        assert self._tokenizer is not None and self._model is not None
        enc = self._tokenizer(
            sentence,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            add_special_tokens=True,
        )
        input_ids = enc["input_ids"].to(self._device)
        if input_ids.shape[1] < 2:
            # Need at least one prediction target after the first token.
            return float("nan"), int(input_ids.shape[1])
        with torch.no_grad():
            outputs = self._model(input_ids=input_ids, labels=input_ids)
        # HF's causal LM loss is already the mean NLL over predicted tokens.
        mean_nll = float(outputs.loss.detach().to(torch.float32).item())
        # Number of tokens the loss was averaged over: input_ids shifted by 1.
        token_count = int(input_ids.shape[1] - 1)
        return mean_nll, token_count


class FluencyPerplexityEvaluator(BaseEvaluator):
    """Length-normalized causal-LM fluency score.

    Parameters
    ----------
    scorer
        Optional scorer instance (typically a ``HuggingFacePerplexityScorer``).
        When omitted, one is lazily built from environment configuration so
        tests can inject a fake without importing torch/transformers.
    scorer_factory
        Optional zero-arg factory returning a ``PerplexityScorer``. Overrides
        the default HF-based factory. Handy for isolating tests.
    """

    def __init__(
        self,
        *,
        scorer: PerplexityScorer | None = None,
        scorer_factory: Callable[[], PerplexityScorer] | None = None,
    ) -> None:
        self._scorer = scorer
        self._factory = scorer_factory

    @property
    def name(self) -> str:
        return EVALUATOR_NAME

    def _get_scorer(self) -> PerplexityScorer:
        if self._scorer is not None:
            return self._scorer
        if self._factory is not None:
            self._scorer = self._factory()
            return self._scorer
        # `or` (not .get(key, default)) so empty strings from a verbatim
        # .env.example copy still fall through to the defaults.
        model_id = os.environ.get("NATURALNESS_PPL_MODEL") or DEFAULT_MODEL_ID
        dtype = os.environ.get("NATURALNESS_PPL_DTYPE") or DEFAULT_DTYPE
        revision = os.environ.get("NATURALNESS_PPL_REVISION") or None
        self._scorer = HuggingFacePerplexityScorer(
            model_id=model_id, dtype=dtype, revision=revision
        )
        return self._scorer

    def evaluate(
        self,
        sentence: str,
        translation: str,
        constraints: dict[str, Any],
    ) -> EvaluationResult:
        text = (sentence or "").strip()
        if not text:
            return EvaluationResult(
                score=0.0,
                details={
                    "error": "empty_sentence",
                    "scorer_version": SCORER_VERSION,
                },
            )

        try:
            scorer = self._get_scorer()
            mean_nll, token_count = scorer.score(text)
        except Exception as exc:  # pragma: no cover - env dependent
            return EvaluationResult(
                score=0.0,
                details={
                    "error": f"scorer_failure: {exc}",
                    "scorer_version": SCORER_VERSION,
                },
            )

        if not (isinstance(mean_nll, float) and math.isfinite(mean_nll)) or token_count <= 0:
            return EvaluationResult(
                score=0.0,
                details={
                    "error": "no_scoreable_tokens",
                    "token_count": max(int(token_count), 0),
                    "scorer_version": SCORER_VERSION,
                },
            )

        perplexity = float(math.exp(mean_nll))
        score = float(math.exp(-mean_nll))
        # Guard against numerical drift outside [0, 1].
        if score < 0.0:
            score = 0.0
        elif score > 1.0:
            score = 1.0

        model_id = getattr(self._scorer, "model_id", None) or DEFAULT_MODEL_ID
        dtype = getattr(self._scorer, "dtype_name", None) or DEFAULT_DTYPE
        revision = getattr(self._scorer, "revision", None)
        device = getattr(self._scorer, "_device", None)

        return EvaluationResult(
            score=score,
            details={
                "mean_nll": mean_nll,
                "perplexity": perplexity,
                "token_count": int(token_count),
                "model_id": model_id,
                "revision": revision,
                "dtype": dtype,
                "device": device,
                "scorer_version": SCORER_VERSION,
            },
        )


__all__ = [
    "DEFAULT_DTYPE",
    "DEFAULT_MODEL_ID",
    "EVALUATOR_NAME",
    "FluencyPerplexityEvaluator",
    "HuggingFacePerplexityScorer",
    "PerplexityScorer",
    "SCORER_VERSION",
]
