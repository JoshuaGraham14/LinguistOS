#!/usr/bin/env python3
"""Single-cell constrained-decoding spike (Option A: HF force_words_ids).

Cell: escribir, future, 2nd person, plural  →  expected_form = "escribiréis"
(the vosotros form that produced 7 subject-verb agreement errors under
prompt-level form injection in Exp 9.)

Approach
--------
- Same baseline prompt as Exp 9 (no form injection in the prompt text).
- Pass ``force_words_ids=[[gold_token_ids]]`` to ``model.generate`` so the
  decoder is **required** to emit the gold form somewhere in the output.
- Beam search (num_beams=4); sampling is incompatible with this constraint.
- n=10 sentences via 10 separate generate calls with different seeds so beams
  diversify slightly via the prompt tokens.
- Score: EF, LanguageTool grammar, with full manual review printed.

Question
--------
When the decoder guarantees ``escribiréis`` appears, does the model still
produce ``nosotros escribiréis`` style frames (binding failure persists),
or does it correctly anchor a ``vosotros`` subject (binding integrates)?

Output: docs/spike-results/eval_spanish_cd_escribireis_qwen17b_results.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.evaluation.sentence.expected_form import normalize_token, tokenize
from research.evaluation.sentence.languagetool import LanguageToolGrammarEvaluator
from research.generation.baseline_hf import (
    _is_qwen3,
    _load_model,
    _strip_thinking,
    parse_candidates_lenient,
)
from research.generation.prompt_builder import build_prompt

MODEL_ID = "Qwen/Qwen3-1.7B"
N_SAMPLES = 10
NUM_BEAMS = 4
MAX_NEW_TOKENS = 40
GOLD_FORM = "escribiréis"

# Beam search is deterministic given the same prompt, so we use 10 different
# scene prompts (one per sample) so the surrounding context differs while the
# core constraints (verb, tense, person, number) stay constant. Each prompt
# asks for ONE plain-text Spanish sentence — JSON output collides with
# beam-search repetition limits.
SCENE_PROMPTS: list[str] = [
    "about writing a letter",
    "about writing a report at work",
    "about writing emails together",
    "about writing exam answers",
    "about writing a story for class",
    "about writing notes in a meeting",
    "about writing a postcard from a trip",
    "about writing the homework tonight",
    "about writing an article for the school magazine",
    "about writing a list of names",
]

CONSTRAINTS = {
    "tense": "future",
    "person": "2nd",
    "number": "plural",
    "target_language": "es",
}

_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "docs/spike-results/eval_spanish_cd_escribireis_qwen17b_results.json"
)


def encode_force_variants(tokenizer, form: str) -> list[list[int]]:
    """Return token-id sequences for the gold form, both with and without a
    leading space. ``force_words_ids`` accepts a *disjunctive* set as inner
    lists, so we pass both variants and the decoder may match either."""
    variants: list[list[int]] = []
    for prefix in ("", " "):
        ids = tokenizer.encode(prefix + form, add_special_tokens=False)
        if ids and ids not in variants:
            variants.append(ids)
    return variants


def build_plain_prompt(scene: str) -> str:
    return (
        "Write one short Spanish sentence (5–12 words) for a CEFR A1 learner "
        "using the verb 'escribir' in the **simple future** tense, **2nd "
        "person plural** (vosotros/vosotras). The subject of the sentence "
        f"should be 'vosotros' or 'vosotras'. Topic: {scene}.\n\n"
        "Reply with ONLY the Spanish sentence on a single line, no JSON, no "
        "translation, no quotes, no extra commentary."
    )


def cd_generate(
    tokenizer,
    model,
    *,
    prompt: str,
    system: str,
    force_words_ids: list[list[list[int]]],
) -> str:
    import torch

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": True,
        "tokenize": False,
    }
    if _is_qwen3(MODEL_ID):
        template_kwargs["enable_thinking"] = False
    text = tokenizer.apply_chat_template(messages, **template_kwargs)
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            num_beams=NUM_BEAMS,
            do_sample=False,
            force_words_ids=force_words_ids,
            pad_token_id=tokenizer.eos_token_id,
            num_return_sequences=1,
            custom_generate="transformers-community/constrained-beam-search",
            trust_remote_code=True,
            remove_invalid_values=True,
        )
    prompt_len = inputs["input_ids"].shape[1]
    raw = tokenizer.decode(output[0][prompt_len:], skip_special_tokens=True)
    return _strip_thinking(raw)


def main() -> None:
    tokenizer, model = _load_model(MODEL_ID)

    variants = encode_force_variants(tokenizer, GOLD_FORM)
    print(f"Token-id variants for {GOLD_FORM!r}:")
    for v in variants:
        decoded = [tokenizer.decode([t]) for t in v]
        print(f"  ids={v}  →  pieces={decoded}")
    # Disjunctive constraint: ``force_words_ids = [[[v1], [v2]]]`` would mean
    # "one of these phrases must appear somewhere".
    force_words_ids = [variants]

    system = "You are a Spanish language tutor. Reply with exactly one Spanish sentence."

    lt = LanguageToolGrammarEvaluator()
    rows: list[dict[str, Any]] = []
    t_start = time.perf_counter()

    for i in range(N_SAMPLES):
        scene = SCENE_PROMPTS[i]
        prompt = build_plain_prompt(scene)
        print(f"[{i + 1}/{N_SAMPLES}] scene={scene!r}...", flush=True)
        t0 = time.perf_counter()
        raw = cd_generate(
            tokenizer,
            model,
            prompt=prompt,
            system=system,
            force_words_ids=force_words_ids,
        )
        latency = round(time.perf_counter() - t0, 2)
        sentence = raw.strip().split("\n")[0].strip()
        # Strip surrounding quotes if model added them
        sentence = sentence.strip('"').strip("'").strip()
        gold_norm = normalize_token(GOLD_FORM)
        ef_pass = any(normalize_token(t) == gold_norm for t in tokenize(sentence))
        gram = lt.evaluate(
            sentence=sentence,
            translation="",
            constraints={"target_language": "es"},
        )
        grammar_matches = (gram.details or {}).get("matches", [])
        rows.append(
            {
                "sample": i + 1,
                "scene": scene,
                "prompt": prompt,
                "raw": raw,
                "latency_s": latency,
                "sentence": sentence,
                "ef_pass": ef_pass,
                "grammar_pass": gram.score >= 1.0,
                "grammar_matches": grammar_matches,
            }
        )
        flag = "OK" if (ef_pass and gram.score >= 1.0) else "✗"
        gm = (
            f"  [{grammar_matches[0].get('rule')}: {grammar_matches[0].get('message','')[:50]}]"
            if grammar_matches
            else ""
        )
        print(f"   {flag} {sentence!r}{gm}")

    elapsed = round(time.perf_counter() - t_start, 1)
    n = sum(1 for r in rows if r["sentence"])
    ef_pass = sum(1 for r in rows if r["ef_pass"])
    gr_pass = sum(1 for r in rows if r["grammar_pass"])
    print()
    print(f"=== HEADLINE ({n}/{N_SAMPLES} parsed in {elapsed}s) ===")
    print(f"  EF      : {ef_pass}/{N_SAMPLES}")
    print(f"  Grammar : {gr_pass}/{N_SAMPLES}")

    data: dict[str, Any] = {
        "model_id": MODEL_ID,
        "cell": {
            "keyword": "escribir",
            "tense": "future",
            "person": "2nd",
            "number": "plural",
            "expected_form": GOLD_FORM,
        },
        "method": "constrained_beam_search_force_words_ids",
        "num_beams": NUM_BEAMS,
        "max_new_tokens": MAX_NEW_TOKENS,
        "n_samples": N_SAMPLES,
        "system": system,
        "token_id_variants": variants,
        "elapsed_s": elapsed,
        "ef_pass": ef_pass,
        "grammar_pass": gr_pass,
        "results": rows,
    }
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nWrote {_OUTPUT}")


if __name__ == "__main__":
    main()
