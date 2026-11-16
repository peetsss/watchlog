from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["system"])


class ServiceInfo(BaseModel):
    name: str
    version: str
    docs: str | None


@router.get("/", response_model=ServiceInfo)
async def root(request: Request) -> ServiceInfo:
    settings = request.app.state.settings
    return ServiceInfo(
        name="watchlog API",
        version=__version__,
        docs="/api/docs" if settings.docs_enabled else None,
    )
