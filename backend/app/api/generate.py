from fastapi import APIRouter

router = APIRouter()


@router.post("/generate")
def generate() -> dict:
    return {"sentences": []}
