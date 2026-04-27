from fastapi import APIRouter
from app.db.schemas import GenerateRequest, GenerateResponse

router = APIRouter()


@router.post("/generate")
def generate(req: GenerateRequest) -> GenerateResponse:
    """
    Generate Spanish sentences with target word and morpho-syntactic constraints.

    TODO: Implement pipeline (Generate → Analyze → Validate → Score → Rank)
    """
    # TODO: Implement sentence generation logic
    return GenerateResponse(candidates=[], mock=True)
