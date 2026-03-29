from fastapi import APIRouter
from app.adapters.registry import list_adapters

router = APIRouter(prefix="/api/adapters", tags=["adapters"])


@router.get("")
def get_adapters():
    return list_adapters()
