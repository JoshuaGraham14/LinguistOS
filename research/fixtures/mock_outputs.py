"""Canned generation outputs for mock experiment runs (no OpenAI API)."""

MOCK_OUTPUTS: dict[str, list[dict[str, str]]] = {
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
}
