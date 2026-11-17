from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import AccountEnvelope

router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("", response_model=AccountEnvelope)
async def get_account(user: CurrentUser) -> AccountEnvelope:
    return AccountEnvelope(
        username=user.username,
        email=user.email,
        email_verified=user.email_verified_at is not None,
        pending_email=user.pending_email,
    )
