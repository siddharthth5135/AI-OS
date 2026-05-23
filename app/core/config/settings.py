from functools import lru_cache
from typing import List

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings parsed from environment variables (.env).
    Access secrets via settings.field.get_secret_value()
    """
    # Application Settings
    app_name: str = Field(default="AI OS")
    debug: bool = Field(default=False)
    version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")

    # Database Configuration
    database_url: SecretStr
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=5)

    # Redis Configuration
    redis_url: SecretStr
    redis_ttl_seconds: int = Field(default=3600)

    # PgVector Configuration
    pgvector_host: str = Field(default="localhost")
    pgvector_port: int = Field(default=6333)
    pgvector_collection_memory: str = Field(default="memory")
    pgvector_collection_documents: str = Field(default="documents")
    pgvector_collection_chats: str = Field(default="chats")

    # Google Gemini AI Configuration
    gemini_api_key: SecretStr
    gemini_model: str = Field(default="gemini-1.5-flash")
    gemini_max_tokens: int = Field(default=2048)

    # JWT Authentication Configuration
    jwt_secret_key: SecretStr
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_expire_minutes: int = Field(default=60)
    jwt_refresh_expire_days: int = Field(default=7)

    # Celery Worker Configuration
    celery_broker_url: SecretStr
    celery_result_backend: SecretStr

    # Storage and CORS
    storage_path: str = Field(default="storage")
    cors_origins: List[str] = Field(default=["*"])

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def async_database_url(self) -> str:
        """Get the database URL formatted for asyncpg."""
        url = self.database_url.get_secret_value()
        # Strip pgbouncer query parameter as it causes asyncpg TypeError
        if "?pgbouncer=" in url or "&pgbouncer=" in url:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            query_params.pop("pgbouncer", None)
            new_query = urlencode(query_params, doseq=True)
            url = urlunparse(parsed._replace(query=new_query))
            
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the Settings model.
    """
    return Settings()


settings = get_settings()
