from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://fairdatahive:fairdatahive@localhost:5432/fairdatahive"
    )

    minio_endpoint: str = Field(default="http://localhost:9000")
    minio_public_endpoint: str | None = Field(
        default=None,
        description="Browser-reachable MinIO URL for presigned downloads (e.g. http://localhost:9000).",
    )
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="fairdatahive-catalog")
    minio_region: str = Field(default="us-east-1")

    keycloak_url: str = Field(default="http://localhost:8080")
    keycloak_realm: str = Field(default="fairdatahive")
    keycloak_client_id: str | None = Field(
        default=None,
        description="OAuth client ID; when set, JWT access tokens must include this aud.",
    )

    redis_url: str = Field(default="redis://localhost:6379/0")

    base_url: str = Field(default="http://localhost:8000")

    embedding_model: str = Field(default="multi-qa-mpnet-base-dot-v1")
    embedding_dim: int = Field(default=768)
    fair_score_publish_threshold: float = Field(default=0.4)
    presigned_url_expiry_seconds: int = Field(default=3600)
    access_request_expiry_days: int = Field(default=30)
    max_upload_size_mb: int = Field(default=500)
    semantic_search_threshold: float = Field(default=0.30)

    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    email_from: str = Field(default="noreply@fairdatahive.local")

    datacite_repo_id: str | None = Field(default=None)
    datacite_password: str | None = Field(default=None)
    datacite_doi_prefix: str | None = Field(default=None)
    datacite_api_url: str = Field(default="https://api.test.datacite.org")

    testing: bool = Field(default=False)

    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000,http://localhost:8001"
    )
    dev_auth_enabled: bool = Field(default=False)
    dev_auth_sub: str = Field(default="dev-user")
    dev_auth_name: str = Field(default="Development User")

    @property
    def minio_public_url(self) -> str:
        """URL embedded in presigned download links (must resolve in the user's browser)."""
        return (self.minio_public_endpoint or self.minio_endpoint).rstrip("/")

    @property
    def jwks_url(self) -> str:
        return (
            f"{self.keycloak_url.rstrip('/')}"
            f"/realms/{self.keycloak_realm}/protocol/openid-connect/certs"
        )

    @property
    def issuer_url(self) -> str:
        return f"{self.keycloak_url.rstrip('/')}/realms/{self.keycloak_realm}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
