from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session.database import get_db
from app.schemas.auth import (
    SignupRequest, 
    LoginRequest, 
    TokenResponse, 
    TokenRefreshRequest, 
    UserResponse
)
from app.schemas.base import BaseResponse
from app.services.auth_service import AuthService
from app.api.dependencies.auth import get_current_active_user
from app.db.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/signup", response_model=BaseResponse[TokenResponse], status_code=status.HTTP_201_CREATED)
async def signup(data: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    """
    result = await AuthService.signup(db, data)
    return BaseResponse(data=result, message="User registered successfully")


@router.post("/login", response_model=BaseResponse[TokenResponse])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate and get access/refresh tokens.
    """
    result = await AuthService.login(db, data)
    return BaseResponse(data=result, message="Login successful")


@router.post("/refresh", response_model=BaseResponse[TokenResponse])
async def refresh(data: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh the access token using a refresh token.
    """
    result = await AuthService.refresh(db, data)
    return BaseResponse(data=result, message="Token refreshed successfully")


@router.get("/me", response_model=BaseResponse[UserResponse])
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user profile.
    """
    return BaseResponse(data=current_user, message="Profile retrieved successfully")


from app.api.dependencies.auth import oauth2_scheme

@router.post("/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout the current user. Works even if token is expired.
    """
    return BaseResponse(message="Successfully logged out")
