"""Constraint and grammar validation."""


class ConstraintValidator:
    def validate_features(
        self, extracted_features: dict | None, constraints: dict
    ) -> dict:
        """
        Check if extracted morphological features satisfy constraints.

        Returns:
            {
                "valid": bool,
                "matches": {"tense": bool, "person": bool, "number": bool},
                "missing": list of feature names not found
            }
        """
        if not extracted_features:
            return {
                "valid": False,
                "matches": {"tense": False, "person": False, "number": False},
                "missing": ["lemma_not_found"],
            }

        matches = {}
        missing = []

        tense_map = {
            "present": ["Pres"],
            "preterite": ["Past"],
            "imperfect": ["Imp"],
            "future": ["Fut"],
            "conditional": ["Cond"],
            "subjunctive": ["Subj"],
        }

        # Map constraint tense to spaCy tense
        constraint_tense = constraints.get("tense", "present").lower()
        spacy_tense_options = tense_map.get(constraint_tense, [])

        feature_tense = extracted_features.get("tense")
        matches["tense"] = any(feature_tense and feature_tense.startswith(t) for t in spacy_tense_options)

        # Person mapping (spaCy uses 1, 2, 3)
        constraint_person = constraints.get("person", "3rd").lower()
        person_map = {"1st": ["1"], "2nd": ["2"], "3rd": ["3"]}
        spacy_person_options = person_map.get(constraint_person, ["3"])

        feature_person = extracted_features.get("person")
        matches["person"] = any(feature_person and feature_person in p for p in spacy_person_options)

        # Number (Sing, Plur)
        constraint_number = constraints.get("number", "singular").lower()
        number_map = {"singular": ["Sing"], "plural": ["Plur"]}
        spacy_number_options = number_map.get(constraint_number, ["Sing"])

        feature_number = extracted_features.get("number")
        matches["number"] = any(feature_number and feature_number.startswith(n) for n in spacy_number_options)

        valid = all(matches.values())

        return {
            "valid": valid,
            "matches": matches,
            "missing": missing,
        }
