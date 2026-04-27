"""Spanish morphological analysis using spaCy."""
import spacy
from dataclasses import dataclass


@dataclass
class TokenFeatures:
    text: str
    lemma: str
    pos: str
    morph: dict


class SpacyTools:
    def __init__(self):
        try:
            self.nlp = spacy.load("es_core_news_sm")
        except OSError:
            raise RuntimeError("Spanish spaCy model not found. Run: python -m spacy download es_core_news_sm")

    def analyze_sentence(self, sentence: str) -> dict:
        """Extract morphological features from a Spanish sentence."""
        doc = self.nlp(sentence)

        tokens = []
        for token in doc:
            morph = {}
            if token.morph:
                for key, value in token.morph.items():
                    morph[key] = value

            tokens.append(
                TokenFeatures(
                    text=token.text,
                    lemma=token.lemma_,
                    pos=token.pos_,
                    morph=morph,
                )
            )

        return {
            "sentence": sentence,
            "tokens": [
                {
                    "text": t.text,
                    "lemma": t.lemma,
                    "pos": t.pos,
                    "morph": t.morph,
                }
                for t in tokens
            ],
        }

    def find_verb_with_features(self, doc_analysis: dict, target_lemma: str) -> dict | None:
        """Find a verb token matching the target lemma."""
        for token in doc_analysis["tokens"]:
            if token["pos"] == "VERB" and token["lemma"].lower() == target_lemma.lower():
                return token
        return None
