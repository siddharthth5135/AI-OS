from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_active_user
from app.db.models.user import User
from app.db.session.database import get_db
from app.schemas.auth import (LoginRequest, SignupRequest, TokenRefreshRequest,
                              TokenResponse, UserResponse)
from app.schemas.base import BaseResponse, ErrorResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup",
    response_model=BaseResponse[TokenResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Validates signup payload (username, email, and password strength) and registers a new active user account. Returns access and refresh tokens.",
    responses={
        400: {
            "description": "Invalid input credentials or weak password structure",
            "model": ErrorResponse,
        },
        409: {
            "description": "Email or username already exists",
            "model": ErrorResponse,
        },
        422: {"description": "Validation error", "model": ErrorResponse},
    },
)
async def signup(data: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user account.
    """
    result = await AuthService.signup(db, data)
    return BaseResponse(data=result, message="User registered successfully")


@router.post(
    "/login",
    response_model=BaseResponse[TokenResponse],
    summary="User login authentication",
    description="Authenticates active user credentials and returns JWT access and refresh tokens.",
    responses={
        400: {"description": "Invalid input formatting", "model": ErrorResponse},
        401: {
            "description": "Incorrect email or password combination",
            "model": ErrorResponse,
        },
        422: {"description": "Validation error", "model": ErrorResponse},
    },
)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate and get access/refresh tokens.
    """
    result = await AuthService.login(db, data)
    return BaseResponse(data=result, message="Login successful")


@router.post(
    "/refresh",
    response_model=BaseResponse[TokenResponse],
    summary="Refresh access token",
    description="Accepts a valid refresh token and issues a new access token.",
    responses={
        400: {"description": "Invalid refresh token payload", "model": ErrorResponse},
        401: {
            "description": "Expired or signature-invalid refresh token",
            "model": ErrorResponse,
        },
        422: {"description": "Validation error", "model": ErrorResponse},
    },
)
async def refresh(data: TokenRefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    Refresh the access token using a refresh token.
    """
    result = await AuthService.refresh(db, data)
    return BaseResponse(data=result, message="Token refreshed successfully")


@router.get(
    "/me",
    response_model=BaseResponse[UserResponse],
    summary="Get current user profile",
    description="Returns detailed profile attributes for the currently authenticated user.",
    responses={
        401: {
            "description": "Not authenticated or token expired",
            "model": ErrorResponse,
        }
    },
)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Get current authenticated user profile.
    """
    return BaseResponse(data=current_user, message="Profile retrieved successfully")


from app.api.dependencies.auth import oauth2_scheme


@router.post(
    "/logout",
    response_model=BaseResponse[None],
    summary="Logout user session",
    description="Statelessly requests clear/invalidation of credentials on client side.",
    responses={401: {"description": "Not authenticated", "model": ErrorResponse}},
)
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Logout the current user. Works even if token is expired.
    """
    return BaseResponse(data=None, message="Successfully logged out")
