"""Linguistic feature extraction and analysis."""
from app.nlp.spacy_tools import SpacyTools


class LinguisticAnalyzer:
    def __init__(self):
        self.spacy_tools = SpacyTools()

    def analyze_sentence(self, sentence: str) -> dict:
        """Analyze a sentence and extract morphological features."""
        analysis = self.spacy_tools.analyze_sentence(sentence)
        return analysis

    def extract_verb_features(self, sentence: str, target_lemma: str) -> dict | None:
        """Extract features from the target verb in a sentence."""
        analysis = self.analyze_sentence(sentence)
        verb_token = self.spacy_tools.find_verb_with_features(analysis, target_lemma)

        if not verb_token:
            return None

        features = {
            "text": verb_token["text"],
            "lemma": verb_token["lemma"],
            "pos": verb_token["pos"],
        }

        morph = verb_token.get("morph", {})
        if isinstance(morph, dict):
            features["tense"] = morph.get("Tense", "").split("|")[0] if "Tense" in morph else None
            features["person"] = morph.get("Person", "").split("|")[0] if "Person" in morph else None
            features["number"] = morph.get("Number", "").split("|")[0] if "Number" in morph else None
            features["mood"] = morph.get("Mood", "").split("|")[0] if "Mood" in morph else None

        return features
