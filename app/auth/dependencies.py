"""
ARIA / SAKHI — Authentication Dependencies
==========================================
⚠️  BE1 ZONE — Backend Engineer 3 must NOT modify this file.
    BE3 only imports `get_current_user` from this module.

BE1 INSTRUCTIONS:
    Replace the body of `get_current_user` with real JWT validation.
    The function signature MUST remain identical:
        async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserRead

    All emergency endpoints are already wired to this dependency.
    Changing the signature will break BE3's routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

# BE1: Replace with real User schema/model return type
from app.schemas.user import UserRead

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> UserRead:
    """
    Validate the Bearer token and return the authenticated user.

    BE1 STUB — This raises NotImplementedError until BE1 implements JWT validation.
    All emergency endpoints use this dependency; they will return 501 until BE1
    replaces this stub body.
    """
    # ─── TODO BE1: Implement real JWT validation ───────────────────────────
    # Example implementation pattern:
    #
    #   try:
    #       payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    #       user_id: str = payload.get("sub")
    #       if user_id is None:
    #           raise credentials_exception
    #   except JWTError:
    #       raise credentials_exception
    #
    #   user = await UserService.get_by_id(UUID(user_id), db)
    #   if user is None:
    #       raise credentials_exception
    #   return user
    # ───────────────────────────────────────────────────────────────────────

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication not yet implemented. BE1: replace the body of get_current_user().",
    )
