from __future__ import annotations

import torch

from research.generation import GENERATOR_REGISTRY
from research.generation.constrained_hf import (
    ConstrainedHFHardPlainBGenerator,
    ConstrainedHFMorphBanPlainBGenerator,
    ConstrainedHFSoftMorphFormsPlainBGenerator,
    ConstrainedHFSoftMorphInjectPlainBGenerator,
    ConstrainedHFSoftMorphPronPlainBGenerator,
    _BatchedBadWordsLogitsProcessor,
)
from research.generation.morph_bans import MorphBanSet


NEW_GENERATORS = {
    "constrained_hf_morph_ban_plain_b",
    "constrained_hf_morph_ban_inject_plain_b",
    "constrained_hf_hard_morph_plain_b",
    "constrained_hf_hard_morph_inject_plain_b",
    "constrained_hf_soft_morph_plain_b",
    "constrained_hf_soft_morph_inject_plain_b",
    "constrained_hf_soft_morph_forms_plain_b",
    "constrained_hf_soft_morph_pron_plain_b",
}


def _constraints() -> dict[str, str]:
    return {
        "tense": "present",
        "person": "2nd",
        "number": "singular",
        "expected_form": "buscas",
    }


def test_registry_adds_all_morph_generators_without_enabling_existing_arms():
    assert NEW_GENERATORS <= GENERATOR_REGISTRY.keys()
    assert ConstrainedHFHardPlainBGenerator._USE_MORPH_BANS is False
    assert ConstrainedHFMorphBanPlainBGenerator._USE_MORPH_BANS is True
    assert ConstrainedHFMorphBanPlainBGenerator._USE_SOFT_BIAS is False


def test_component_ablation_modes_are_locked():
    assert ConstrainedHFSoftMorphFormsPlainBGenerator._MORPH_BAN_MODE == "forms_only"
    assert ConstrainedHFSoftMorphPronPlainBGenerator._MORPH_BAN_MODE == "pronouns_only"


def test_soft_morph_inject_uses_form_in_prompt_and_fix_b():
    gen = ConstrainedHFSoftMorphInjectPlainBGenerator(
        model="Qwen/Qwen3-1.7B",
        temperature=0.0,
    )
    constraints = _constraints()
    prompt = gen._build_user_prompt(
        keyword="buscar",
        translation="to search",
        target_language="es",
        constraints=constraints,
        num_candidates=1,
        sentence_length="short",
        cefr_level=None,
        explicit_subject_required=False,
        inject_expected_form=gen._resolve_inject_expected_form(constraints),
    )

    assert 'Required surface form' in prompt
    assert '"buscas"' in prompt
    assert "2–5 words" in prompt
    assert "Do NOT output the target form on its own" in prompt


def test_generate_many_passes_per_job_morph_ban_set(monkeypatch):
    import research.generation.constrained_hf as constrained

    captured = []
    fake_ban_set = MorphBanSet(
        mode="full",
        competing_forms=frozenset({"busco", "buscar"}),
        pronouns=frozenset({"yo"}),
    )
    monkeypatch.setattr(constrained, "build_morph_ban_set", lambda *a, **k: fake_ban_set)

    def fake_beam_batch(
        model_id,
        specs,
        *,
        num_beams,
        use_hard_constraint,
        bias_strength,
        batch_size=8,
        stop_bias_after_hit=False,
        no_repeat_ngram_size=0,
        min_new_tokens=0,
        length_penalty=1.0,
    ):
        captured.extend(specs)
        return ["Tú buscas libros."] * len(specs)

    monkeypatch.setattr(constrained, "beam_generate_batch", fake_beam_batch)
    gen = constrained.ConstrainedHFSoftMorphPlainBGenerator(
        model="Qwen/Qwen3-1.7B",
        temperature=0.0,
        num_beams=8,
    )
    jobs = [
        {
            "keyword": "buscar",
            "translation": "to search",
            "constraints": _constraints(),
            "num_candidates": 1,
            "target_language": "es",
            "sentence_length": "short",
        }
    ]

    result = gen.generate_many(jobs)
    assert result[0][0]["sentence"] == "Tú buscas libros."
    assert captured[0].morph_ban_set == fake_ban_set


def test_batched_bad_words_processor_is_sequence_aware_and_per_row():
    proc = _BatchedBadWordsLogitsProcessor(
        [
            [[10], [20, 21]],
            [[30]],
        ],
        num_beams=1,
        prompt_width=2,
    )
    scores = torch.zeros((2, 40))

    # Row 0 has generated prefix 20, so both single-token 10 and completion
    # token 21 are banned. Row 1 has its independent single-token ban 30.
    input_ids = torch.tensor([[0, 0, 20], [0, 0, 5]])
    out = proc(input_ids, scores)
    assert torch.isneginf(out[0, 10])
    assert torch.isneginf(out[0, 21])
    assert out[0, 30] == 0
    assert torch.isneginf(out[1, 30])
    assert out[1, 10] == 0
