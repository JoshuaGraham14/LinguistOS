"""Candidate sentence generation using OpenAI API."""
from openai import OpenAI


class SentenceGenerator:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def generate_candidates(
        self,
        word: str,
        translation: str,
        tense: str,
        person: str,
        number: str,
        num_candidates: int = 5,
    ) -> list[str]:
        """Generate Spanish sentences containing the word with specified morpho-syntactic constraints."""

        person_map = {
            "1st": "first person (yo/nosotros)",
            "2nd": "second person (tú/vosotros)",
            "3rd": "third person (él/ella/ellos/ellas)",
        }

        prompt = f"""Generate {num_candidates} natural Spanish sentences containing the word "{word}" ({translation}).

Requirements:
- Tense: {tense}
- Person: {person_map.get(person, person)}
- Number: {number}
- Each sentence must be grammatically correct and natural
- The target word must be in the specified tense and person/number
- Vary sentence structures and vocabulary while maintaining naturalness

Return ONLY the sentences, one per line, with no numbering or explanations."""

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )

        text = response.choices[0].message.content or ""
        sentences = [s.strip() for s in text.strip().split("\n") if s.strip()]
        return sentences[:num_candidates]
