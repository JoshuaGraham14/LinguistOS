"""Scoring: +1 per matched feature (lemma, tense, person, number)."""


class SentenceScorer:
    def score(self, validation: dict, verb_features: dict | None) -> float:
        """
        Score a sentence based on constraint satisfaction.
        - Base: 0 points
        - +1 for lemma match (if verb found)
        - +1 for tense match
        - +1 for person match
        - +1 for number match
        """
        score = 0.0

        if verb_features:
            score += 1.0  # Found the target lemma

        if validation.get("valid"):
            matches = validation.get("matches", {})
            score += sum(1 for v in matches.values() if v)  # +1 per matched feature

        return score
