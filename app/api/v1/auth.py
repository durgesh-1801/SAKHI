from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.user_service import user_service
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Registers a new user account.
    Automatically initializes:
    - Default consent settings (explicit opt-in defaults).
    - Default emergency response policy (30s verification timeout, primary contact unassigned).
    """
    return user_service.create(db, user_in)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login user and obtain JWT token"
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticates user credentials and returns a signed JWT access token.
    """
    return auth_service.login(db, credentials)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile"
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Returns the authenticated user's profile details.
    """
    return current_user


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout user"
)
def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Stateless JWT logout endpoint. Clients should discard their access token.
    """
    return {"message": "Successfully logged out"}
