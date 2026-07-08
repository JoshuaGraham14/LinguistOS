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
    "spanish_challenging": {
        "pedir": [
            {"sentence": "Yo pido ayuda cuando la necesito.", "translation": "I ask for help when I need it."},
            {"sentence": "A veces pido demasiado.", "translation": "Sometimes I ask for too much."},
            {"sentence": "Yo pido la cuenta al camarero.", "translation": "I ask the waiter for the bill."},
        ],
        "dormir": [
            {"sentence": "Yo duermo ocho horas cada noche.", "translation": "I sleep eight hours every night."},
            {"sentence": "Duermo mejor en invierno.", "translation": "I sleep better in winter."},
            {"sentence": "Yo duermo en el sofá.", "translation": "I sleep on the sofa."},
        ],
        "decir": [
            {"sentence": "Ayer dije la verdad.", "translation": "Yesterday I told the truth."},
            {"sentence": "Dije que vendría.", "translation": "I said that he would come."},
            {"sentence": "Yo dije eso en clase.", "translation": "I said that in class."},
        ],
        "tener": [
            {"sentence": "Ellos tuvieron suerte.", "translation": "They were lucky."},
            {"sentence": "Los niños tuvieron miedo.", "translation": "The children were afraid."},
            {"sentence": "Mis padres tuvieron una idea.", "translation": "My parents had an idea."},
        ],
        "conducir": [
            {"sentence": "Ellos condujeron hasta Sevilla.", "translation": "They drove to Seville."},
            {"sentence": "Los turistas condujeron con cuidado.", "translation": "The tourists drove carefully."},
            {"sentence": "Mis amigos condujeron toda la noche.", "translation": "My friends drove all night."},
        ],
        "poner": [
            {"sentence": "Yo pondría la mesa aquí.", "translation": "I would put the table here."},
            {"sentence": "Pondría más sal.", "translation": "I would add more salt."},
            {"sentence": "Yo pondría eso en la nevera.", "translation": "I would put that in the fridge."},
        ],
        "venir": [
            {"sentence": "Yo vendría mañana si pudiera.", "translation": "I would come tomorrow if I could."},
            {"sentence": "Vendría contigo.", "translation": "I would come with you."},
            {"sentence": "Yo vendría más temprano.", "translation": "I would come earlier."},
        ],
        "llegar": [
            {"sentence": "Ayer llegué tarde a casa.", "translation": "Yesterday I arrived home late."},
            {"sentence": "Llegué antes que tú.", "translation": "I arrived before you."},
            {"sentence": "Yo llegué a las ocho.", "translation": "I arrived at eight."},
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
    bench = MOCK_OUTPUTS_BY_BENCHMARK.get(benchmark_name)
    if bench and keyword in bench:
        return list(bench[keyword])

    if benchmark_name in (
        "spanish_diagnostic_n150",
        "spanish_direction_hl50",
        "spanish_direction_hl50_smoke",
    ):
        basic = MOCK_OUTPUTS_BY_BENCHMARK["spanish_basic"].get(keyword)
        if basic:
            return list(basic)
        return [
            {
                "sentence": f"Yo uso {keyword} hoy.",
                "translation": f"I use {keyword} today.",
            }
        ]

    return []
