#!/usr/bin/env python3
"""LoRA SFT for Qwen3-1.7B Spanish sentence generation.

Supports both Experiment A (``LoRA-form``) and B (``LoRA-no-inject``): the
script only needs JSONL with ``prompt`` / ``completion`` from
``build_lora_sft_dataset.py``.

Usage::

    python -m research.scripts.train_lora_sft \\
        --data research/runs/lora/sft_lora_form_n150.jsonl \\
        --output-dir research/runs/lora/qwen3_1p7b_lora_form

    python -m research.scripts.train_lora_sft \\
        --data research/runs/lora/sft_lora_no_inject_n150.jsonl \\
        --output-dir research/runs/lora/qwen3_1p7b_lora_no_inject
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _expand_oversample(rows: list[dict], *, factor: int = 2) -> list[dict]:
    out = list(rows)
    for r in rows:
        tags = r.get("oversample_tags") or []
        if tags:
            for _ in range(factor - 1):
                out.append(r)
    return out


def _split_train_val(
    rows: list[dict],
    *,
    val_frac: float,
    seed: int,
    stratify_construction: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Deterministically split rows, optionally preserving construction balance."""
    rng = random.Random(seed)
    if not stratify_construction:
        shuffled = list(rows)
        rng.shuffle(shuffled)
        n_val = max(1, int(len(shuffled) * val_frac))
        return shuffled[n_val:], shuffled[:n_val]

    groups: dict[str, list[dict]] = {}
    for row in rows:
        construction = str((row.get("constraints") or {}).get("construction") or "UNK")
        groups.setdefault(construction, []).append(row)

    train_rows: list[dict] = []
    val_rows: list[dict] = []
    for construction in sorted(groups):
        group = list(groups[construction])
        rng.shuffle(group)
        n_val = max(1, int(len(group) * val_frac))
        val_rows.extend(group[:n_val])
        train_rows.extend(group[n_val:])
    rng.shuffle(train_rows)
    rng.shuffle(val_rows)
    return train_rows, val_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--val-frac", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--oversample-factor", type=int, default=2)
    parser.add_argument(
        "--stratify-construction",
        action="store_true",
        help="Preserve synthetic/periphrastic balance in the train/validation split.",
    )
    args = parser.parse_args()

    import torch
    from datasets import Dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import SFTConfig, SFTTrainer

    rows = _load_jsonl(args.data)
    rng = random.Random(args.seed)
    raw_train_rows, val_rows = _split_train_val(
        rows,
        val_frac=args.val_frac,
        seed=args.seed,
        stratify_construction=args.stratify_construction,
    )
    train_rows = _expand_oversample(
        raw_train_rows, factor=args.oversample_factor
    )
    rng.shuffle(train_rows)

    def to_text(r: dict) -> dict:
        # Chat-style single turn: user=prompt, assistant=completion
        messages = [
            {"role": "user", "content": r["prompt"]},
            {"role": "assistant", "content": r["completion"]},
        ]
        return {"messages": messages}

    train_ds = Dataset.from_list([to_text(r) for r in train_rows])
    val_ds = Dataset.from_list([to_text(r) for r in val_rows])

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=dtype,
        device_map="auto" if torch.cuda.is_available() else None,
        trust_remote_code=True,
        attn_implementation="eager",
    )

    peft_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = {
        "model": args.model,
        "data": str(args.data),
        "n_train_raw": len(raw_train_rows),
        "n_train_expanded": len(train_rows),
        "n_val": len(val_rows),
        "epochs": args.epochs,
        "lr": args.lr,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "oversample_factor": args.oversample_factor,
        "stratify_construction": args.stratify_construction,
        "seed": args.seed,
    }
    (args.output_dir / "train_config.json").write_text(
        json.dumps(config, indent=2), encoding="utf-8"
    )

    sft_args = SFTConfig(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        logging_steps=20,
        eval_strategy="steps",
        eval_steps=100,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        bf16=torch.cuda.is_available(),
        max_length=args.max_seq_length,
        packing=False,
        report_to=[],
        seed=args.seed,
    )

    trainer = SFTTrainer(
        model=model,
        args=sft_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        peft_config=peft_config,
    )
    trainer.train()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))
    print(f"Saved adapter → {args.output_dir}")


if __name__ == "__main__":
    main()
