import structlog
from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import settings
from app.core.security.jwt import (create_access_token, create_refresh_token,
                                   decode_token)
from app.core.security.password import (get_dummy_hash, hash_password,
                                        verify_password)
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (LoginRequest, SignupRequest, TokenRefreshRequest,
                              TokenResponse)

logger = structlog.get_logger("ai_os.auth")


class AuthService:
    """
    Business logic for user authentication, including signup, login, and token refresh.
    """

    @staticmethod
    async def signup(db: AsyncSession, data: SignupRequest) -> TokenResponse:
        """
        Registers a new user and returns authentication tokens.
        """
        # Check email uniqueness
        if await UserRepository.get_by_email(db, data.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            )

        # Check username uniqueness
        if await UserRepository.get_by_username(db, data.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
            )

        # Hash password and create user
        hashed_password = hash_password(data.password)
        user = await UserRepository.create(
            db, username=data.username, email=data.email, password_hash=hashed_password
        )

        logger.info("auth.signup_success", user_id=str(user.id), username=user.username)

        # Generate tokens
        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_expire_minutes * 60,
        )

    @staticmethod
    async def login(db: AsyncSession, data: LoginRequest) -> TokenResponse:
        """
        Authenticates a user and returns new tokens.
        Implements timing-attack protection and avoids account enumeration.
        """
        user = await UserRepository.get_by_email(db, data.email)

        # Generic error message to prevent enumeration
        unauthorized_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if not user:
            # Timing safety: perform a dummy verification
            verify_password(data.password, get_dummy_hash())
            raise unauthorized_exception

        if not verify_password(data.password, user.password_hash):
            raise unauthorized_exception

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated",
            )

        # Update last login and generate tokens
        await UserRepository.update_last_login(db, user.id)

        logger.info("auth.login_success", user_id=str(user.id))

        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_expire_minutes * 60,
        )

    @staticmethod
    async def refresh(db: AsyncSession, data: TokenRefreshRequest) -> TokenResponse:
        """
        Rotates tokens using a valid refresh token.
        """
        try:
            payload = decode_token(data.refresh_token)
        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        user_id = payload.get("sub")
        user = await UserRepository.get_by_id(db, user_id)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new tokens (rotating the access token)
        logger.info("auth.token_refresh", user_id=str(user.id))

        access_token = create_access_token(user.id, user.role)

        return TokenResponse(
            access_token=access_token,
            refresh_token=data.refresh_token,  # Keep the same refresh token as requested
            expires_in=settings.jwt_access_expire_minutes * 60,
        )
