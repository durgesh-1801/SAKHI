from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.journey import JourneyCreate, JourneyUpdate, JourneyResponse
from app.services.journey_service import journey_service

router = APIRouter(prefix="/journeys", tags=["Safe Journey"])


@router.post(
    "",
    response_model=JourneyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new safe journey"
)
def create_journey(
    journey_in: JourneyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new Safe Journey (PLANNED or immediately ACTIVE if auto_start=True).
    Ensures that a user can only have one ACTIVE journey at any given time.
    """
    return journey_service.create_journey(db, current_user.id, journey_in)


@router.get(
    "",
    response_model=List[JourneyResponse],
    status_code=status.HTTP_200_OK,
    summary="List all journeys for user"
)
def list_journeys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns all safe journeys initiated by the authenticated user.
    """
    return journey_service.list_journeys(db, current_user.id)


@router.get(
    "/active",
    response_model=Optional[JourneyResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user's currently active journey"
)
def get_active_journey(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the user's currently ACTIVE journey, or null if none is in progress.
    """
    return journey_service.get_active_journey(db, current_user.id)


@router.get(
    "/{journey_id}",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get journey details by ID"
)
def get_journey(
    journey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves journey details. Enforces user ownership.
    """
    return journey_service.get_journey_for_user(db, journey_id, current_user.id)


@router.put(
    "/{journey_id}",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    summary="Update journey details"
)
def update_journey(
    journey_id: str,
    journey_in: JourneyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates journey origin, destination, or duration. Only allowed if not completed/cancelled.
    """
    return journey_service.update_journey(db, journey_id, current_user.id, journey_in)


@router.post(
    "/{journey_id}/start",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    summary="Start/Activate a planned journey"
)
def start_journey(
    journey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transitions journey from PLANNED to ACTIVE.
    Rejects if another journey is already active.
    """
    return journey_service.start_journey(db, journey_id, current_user.id)


@router.post(
    "/{journey_id}/end",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    summary="End/Complete an active journey"
)
def end_journey(
    journey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks journey as COMPLETED and timestamps conclusion.
    """
    return journey_service.end_journey(db, journey_id, current_user.id)


@router.post(
    "/{journey_id}/cancel",
    response_model=JourneyResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a planned or active journey"
)
def cancel_journey(
    journey_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Marks journey as CANCELLED.
    """
    return journey_service.cancel_journey(db, journey_id, current_user.id)
