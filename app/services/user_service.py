from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.consent import UserConsent
from app.models.policy import EmergencyPolicy
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import ConflictException, EntityNotFoundException


class UserService:
    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email.lower().strip()).first()

    @staticmethod
    def create(db: Session, user_in: UserCreate) -> User:
        email = user_in.email.lower().strip()
        existing_user = UserService.get_by_email(db, email)
        if existing_user:
            raise ConflictException(f"User with email '{email}' already exists")

        # 1. Create User
        db_user = User(
            name=user_in.name.strip(),
            email=email,
            phone=user_in.phone.strip(),
            password_hash=get_password_hash(user_in.password),
            is_active=True
        )
        db.add(db_user)
        db.flush()  # assign db_user.id

        # 2. Initialize Consent-First Default Preferences (All opt-in by default)
        db_consent = UserConsent(
            user_id=db_user.id,
            location_monitoring=False,
            ai_detection=False,
            audio_analysis=False,
            automatic_escalation=False,
            evidence_collection=False
        )
        db.add(db_consent)

        # 3. Initialize Default Emergency Response Policy
        db_policy = EmergencyPolicy(
            user_id=db_user.id,
            verification_timeout=30,
            auto_alert_enabled=True,
            location_sharing_enabled=True,
            primary_contact_id=None,
            secondary_contact_id=None,
            escalation_level=1
        )
        db.add(db_policy)

        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def update(db: Session, user: User, user_in: UserUpdate) -> User:
        if user_in.name is not None:
            user.name = user_in.name.strip()
        if user_in.phone is not None:
            user.phone = user_in.phone.strip()
        if user_in.password is not None:
            user.password_hash = get_password_hash(user_in.password)

        db.commit()
        db.refresh(user)
        return user


user_service = UserService()
