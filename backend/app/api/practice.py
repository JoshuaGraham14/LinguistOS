from fastapi import APIRouter

router = APIRouter()


@router.post("/practice")
def practice() -> dict:
    return {"result": None}
