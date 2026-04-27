from fastapi import APIRouter

router = APIRouter()


@router.get("/vocab")
def list_vocab() -> dict:
    return {"items": []}


@router.post("/vocab")
def add_vocab() -> dict:
    return {"item": None}
