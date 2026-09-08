from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactUpdate, ContactResponse
from app.services.contact_service import contact_service

router = APIRouter(prefix="/contacts", tags=["Trusted Contacts"])


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a trusted contact"
)
def create_contact(
    contact_in: ContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new trusted contact belonging to the authenticated user.
    """
    return contact_service.create_contact(db, current_user.id, contact_in)


@router.get(
    "",
    response_model=List[ContactResponse],
    status_code=status.HTTP_200_OK,
    summary="List all trusted contacts"
)
def list_contacts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns only the authenticated user's trusted contacts, ordered by escalation priority.
    """
    return contact_service.list_contacts(db, current_user.id)


@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a specific trusted contact"
)
def get_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves a trusted contact by ID. Enforces strict ownership.
    """
    return contact_service.get_contact_for_user(db, contact_id, current_user.id)


@router.put(
    "/{contact_id}",
    response_model=ContactResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a trusted contact"
)
def update_contact(
    contact_id: str,
    contact_in: ContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Updates a trusted contact. Enforces strict ownership.
    """
    return contact_service.update_contact(db, contact_id, current_user.id, contact_in)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a trusted contact"
)
def delete_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a trusted contact and cleans up any references in emergency policy.
    """
    contact_service.delete_contact(db, contact_id, current_user.id)
    return {"message": "Trusted contact successfully removed"}
