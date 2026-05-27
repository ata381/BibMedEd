import logging

from fastapi import APIRouter
from app.adapters.registry import list_adapters

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/adapters", tags=["adapters"])


@router.get("")
def get_adapters():
    return list_adapters()
