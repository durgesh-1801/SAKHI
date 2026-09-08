from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.consent import ConsentResponse, ConsentUpdate
from app.services.consent_service import consent_service

router = APIRouter(prefix="/consent", tags=["Consent Management"])


@router.get(
    "",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user consent preferences"
)
def get_user_consent(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the authenticated user's consent preferences.
    In SAKHI, all surveillance and analysis features are opt-in.
    """
    return consent_service.get_or_create_consent(db, current_user.id)


@router.put(
    "",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user consent preferences"
)
def update_user_consent(
    consent_in: ConsentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the authenticated user's opt-in consent settings.
    Updates the audit timestamp automatically.
    """
    return consent_service.update_consent(db, current_user.id, consent_in)
