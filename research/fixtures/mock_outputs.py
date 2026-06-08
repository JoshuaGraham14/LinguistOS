"""Canned generation outputs for mock experiment runs (no OpenAI API).

Keyed by benchmark name then constraint-set keyword so the same lemma can carry
different sentences in evaluation vs fixture benchmarks.
"""

from __future__ import annotations

MOCK_OUTPUTS_BY_BENCHMARK: dict[str, dict[str, list[dict[str, str]]]] = {
    "spanish_basic": {
        "comer": [
            {"sentence": "Nosotros comimos pizza anoche.", "translation": "We ate pizza last night."},
            {"sentence": "Comimos en el restaurante nuevo.", "translation": "We ate at the new restaurant."},
            {"sentence": "Ayer comimos paella juntos.", "translation": "Yesterday we ate paella together."},
        ],
        "vivir": [
            {"sentence": "Ella vivirá en Madrid.", "translation": "She will live in Madrid."},
            {"sentence": "Él vivirá cerca del parque.", "translation": "He will live near the park."},
            {"sentence": "Vivirá con su familia.", "translation": "He/She will live with his/her family."},
        ],
        "hablar": [
            {"sentence": "Tú hablas muy rápido.", "translation": "You speak very fast."},
            {"sentence": "Hablas español muy bien.", "translation": "You speak Spanish very well."},
            {"sentence": "Tú hablas con tu madre.", "translation": "You speak with your mother."},
        ],
        "escribir": [
            {"sentence": "Ellos escribieron una carta.", "translation": "They wrote a letter."},
            {"sentence": "Escribieron el informe ayer.", "translation": "They wrote the report yesterday."},
            {"sentence": "Ellos escribieron poemas.", "translation": "They wrote poems."},
        ],
        "correr": [
            {"sentence": "Yo corro en el parque.", "translation": "I run in the park."},
            {"sentence": "Corro todas las mañanas.", "translation": "I run every morning."},
            {"sentence": "Yo corro con mi perro.", "translation": "I run with my dog."},
        ],
    },
    "spanish_grammar_probe": {
        "probe_subj_verb": [
            {"sentence": "Yo comimos pizza ayer.", "translation": "We ate pizza yesterday."},
            {"sentence": "Nosotros comimos pizza anoche.", "translation": "We ate pizza last night."},
            {"sentence": "Él comimos en casa.", "translation": "He ate at home."},
        ],
        "probe_det_noun": [
            {"sentence": "Las chico come mucho.", "translation": "The boy eats a lot."},
            {"sentence": "El chico come mucho.", "translation": "The boy eats a lot."},
            {"sentence": "La casas son grandes.", "translation": "The houses are big."},
        ],
        "probe_prep": [
            {"sentence": "Ayer yo fui al tienda.", "translation": "Yesterday I went to the store."},
            {"sentence": "Ayer fui a la tienda.", "translation": "Yesterday I went to the store."},
            {"sentence": "Fui a el cine ayer.", "translation": "I went to the cinema yesterday."},
        ],
        "probe_correct": [
            {"sentence": "Tú hablas español muy bien.", "translation": "You speak Spanish very well."},
            {"sentence": "Hablas con tu madre cada día.", "translation": "You speak with your mother every day."},
            {"sentence": "Tú hablas muy rápido.", "translation": "You speak very fast."},
        ],
    },
}

# Back-compat alias used by older tests (spanish_basic only).
MOCK_OUTPUTS = MOCK_OUTPUTS_BY_BENCHMARK["spanish_basic"]


def get_mock_candidates(benchmark_name: str, keyword: str) -> list[dict[str, str]]:
    """Return canned sentences for a benchmark constraint set, or []."""
    return list(
        MOCK_OUTPUTS_BY_BENCHMARK.get(benchmark_name, {}).get(keyword, [])
    )
