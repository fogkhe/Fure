from typing import Annotated

from fastapi import APIRouter, Depends

from fure.api.dependencies import get_database
from fure.database.connection import Database

router = APIRouter()


@router.get("/health", tags=["health"], summary="Check service availability")
async def health(
    database: Annotated[Database, Depends(get_database)],
) -> dict[str, str]:
    await database.check()
    return {"status": "ok"}
