from fastapi import APIRouter
from app.db.schemas import GenerateRequest, GenerateResponse, SentenceCandidate
from app.config import settings
from app.core.generator import SentenceGenerator
from app.core.analyzer import LinguisticAnalyzer
from app.core.validator import ConstraintValidator
from app.core.scorer import SentenceScorer

router = APIRouter()


@router.post("/generate")
def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Generate Spanish sentences with target word and morpho-syntactic constraints.

    Pipeline: Generate → Analyze → Validate → Score → Rank
    """
    # Initialize pipeline components
    generator = SentenceGenerator(api_key=settings.openai_api_key)
    analyzer = LinguisticAnalyzer()
    validator = ConstraintValidator()
    scorer = SentenceScorer()

    # Build constraints dict from request
    constraints = {
        "tense": req.tense,
        "person": req.person,
        "number": req.number,
    }

    # Step 1: Generate candidate sentences
    try:
        candidates = generator.generate_candidates(
            word=req.word,
            translation=req.translation,
            tense=req.tense,
            person=req.person,
            number=req.number,
            num_candidates=req.num_candidates,
        )
    except Exception as e:
        # Return empty list if generation fails (frontend will fall back to mock)
        return GenerateResponse(candidates=[], mock=False)

    # Step 2-4: Analyze, validate, and score each candidate
    scored_candidates = []
    for sentence in candidates:
        try:
            # Extract verb features from sentence
            verb_features = analyzer.extract_verb_features(sentence, req.word)

            # Validate against constraints
            validation = validator.validate_features(verb_features, constraints)

            # Score based on constraint satisfaction
            score = scorer.score(validation, verb_features)

            # Build response candidate
            candidate = SentenceCandidate(
                sentence=sentence,
                translation=None,  # Frontend will provide translation
                score=score,
                features=verb_features,
            )
            scored_candidates.append(candidate)
        except Exception:
            # Skip sentences that fail analysis
            continue

    # Step 5: Sort by score (descending)
    scored_candidates.sort(key=lambda x: x.score, reverse=True)

    # Return top N candidates
    return GenerateResponse(
        candidates=scored_candidates[: req.num_candidates],
        mock=False,
    )
