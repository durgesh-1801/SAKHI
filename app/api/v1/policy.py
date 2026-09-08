from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.policy import PolicyResponse, PolicyUpdate
from app.services.policy_service import policy_service

router = APIRouter(prefix="/emergency-policy", tags=["Emergency Policy"])


@router.get(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user emergency response policy"
)
def get_emergency_policy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the user's configured emergency response preferences,
    including verification timeout and primary/secondary contact assignments.
    """
    return policy_service.get_or_create_policy(db, current_user.id)


@router.put(
    "",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update emergency response policy"
)
def update_emergency_policy(
    policy_in: PolicyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates the emergency policy preferences.
    Validates that:
    - verification_timeout is within allowable boundaries (10 - 300 seconds).
    - Assigned primary and secondary contacts belong strictly to the authenticated user.
    - Primary and secondary contacts are distinct.
    """
    return policy_service.update_policy(db, current_user.id, policy_in)
