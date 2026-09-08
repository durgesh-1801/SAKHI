from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.journey import SafeJourney, JourneyStatus
from app.schemas.journey import JourneyCreate, JourneyUpdate
from app.core.exceptions import (
    EntityNotFoundException,
    ForbiddenException,
    ConflictException,
    BadRequestException
)


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class JourneyService:
    @staticmethod
    def get_journey_for_user(db: Session, journey_id: str, user_id: str) -> SafeJourney:
        journey = db.query(SafeJourney).filter(SafeJourney.id == journey_id).first()
        if not journey:
            raise EntityNotFoundException("SafeJourney", journey_id)
        if journey.user_id != user_id:
            raise ForbiddenException("You do not have permission to access this journey")
        return journey

    @staticmethod
    def get_active_journey(db: Session, user_id: str) -> Optional[SafeJourney]:
        return (
            db.query(SafeJourney)
            .filter(
                SafeJourney.user_id == user_id,
                SafeJourney.status == JourneyStatus.ACTIVE.value
            )
            .first()
        )

    @staticmethod
    def list_journeys(db: Session, user_id: str) -> List[SafeJourney]:
        return (
            db.query(SafeJourney)
            .filter(SafeJourney.user_id == user_id)
            .order_by(SafeJourney.created_at.desc())
            .all()
        )

    @staticmethod
    def create_journey(db: Session, user_id: str, journey_in: JourneyCreate) -> SafeJourney:
        status = JourneyStatus.PLANNED.value
        started_at = None

        if journey_in.auto_start:
            existing_active = JourneyService.get_active_journey(db, user_id)
            if existing_active:
                raise ConflictException(
                    f"An active journey '{existing_active.id}' already exists. "
                    "Complete or cancel it before starting another."
                )
            status = JourneyStatus.ACTIVE.value
            started_at = get_utc_now()

        journey = SafeJourney(
            user_id=user_id,
            origin=journey_in.origin.strip(),
            destination=journey_in.destination.strip(),
            expected_duration=journey_in.expected_duration,
            status=status,
            started_at=started_at
        )
        db.add(journey)
        db.commit()
        db.refresh(journey)
        return journey

    @staticmethod
    def start_journey(db: Session, journey_id: str, user_id: str) -> SafeJourney:
        journey = JourneyService.get_journey_for_user(db, journey_id, user_id)

        if journey.status in (JourneyStatus.COMPLETED.value, JourneyStatus.CANCELLED.value):
            raise BadRequestException(f"Cannot start a journey in '{journey.status}' status")

        if journey.status == JourneyStatus.ACTIVE.value:
            return journey

        existing_active = JourneyService.get_active_journey(db, user_id)
        if existing_active and existing_active.id != journey.id:
            raise ConflictException(
                f"An active journey '{existing_active.id}' is already in progress. "
                "Complete or cancel it before activating this journey."
            )

        journey.status = JourneyStatus.ACTIVE.value
        journey.started_at = get_utc_now()
        db.commit()
        db.refresh(journey)
        return journey

    @staticmethod
    def end_journey(db: Session, journey_id: str, user_id: str) -> SafeJourney:
        journey = JourneyService.get_journey_for_user(db, journey_id, user_id)

        if journey.status == JourneyStatus.COMPLETED.value:
            return journey

        journey.status = JourneyStatus.COMPLETED.value
        journey.ended_at = get_utc_now()
        db.commit()
        db.refresh(journey)
        return journey

    @staticmethod
    def cancel_journey(db: Session, journey_id: str, user_id: str) -> SafeJourney:
        journey = JourneyService.get_journey_for_user(db, journey_id, user_id)

        if journey.status in (JourneyStatus.COMPLETED.value, JourneyStatus.CANCELLED.value):
            raise BadRequestException(f"Cannot cancel a journey that is already {journey.status.lower()}")

        journey.status = JourneyStatus.CANCELLED.value
        journey.ended_at = get_utc_now()
        db.commit()
        db.refresh(journey)
        return journey

    @staticmethod
    def update_journey(
        db: Session,
        journey_id: str,
        user_id: str,
        journey_in: JourneyUpdate
    ) -> SafeJourney:
        journey = JourneyService.get_journey_for_user(db, journey_id, user_id)

        if journey.status in (JourneyStatus.COMPLETED.value, JourneyStatus.CANCELLED.value):
            raise BadRequestException(f"Cannot modify a journey in '{journey.status}' status")

        if journey_in.origin is not None:
            journey.origin = journey_in.origin.strip()
        if journey_in.destination is not None:
            journey.destination = journey_in.destination.strip()
        if journey_in.expected_duration is not None:
            journey.expected_duration = journey_in.expected_duration

        db.commit()
        db.refresh(journey)
        return journey


journey_service = JourneyService()
