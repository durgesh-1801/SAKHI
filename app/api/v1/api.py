from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.contacts import router as contacts_router
from app.api.v1.consent import router as consent_router
from app.api.v1.policy import router as policy_router
from app.api.v1.journeys import router as journeys_router
from app.api.v1.context import router as context_router
from app.api.v1.ai import router as ai_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(contacts_router)
api_router.include_router(consent_router)
api_router.include_router(policy_router)
api_router.include_router(journeys_router)
api_router.include_router(context_router)
api_router.include_router(ai_router)
