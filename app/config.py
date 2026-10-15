from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# (canonical S3_* variable, legacy MINIO_* alias). The legacy names are accepted for
# one transition release; when both are set the S3_* value wins and a warning is logged.
S3_LEGACY_ENV_ALIASES: tuple[tuple[str, str], ...] = (
    ("S3_ENDPOINT", "MINIO_ENDPOINT"),
    ("S3_PUBLIC_ENDPOINT", "MINIO_PUBLIC_ENDPOINT"),
    ("S3_ACCESS_KEY", "MINIO_ACCESS_KEY"),
    ("S3_SECRET_KEY", "MINIO_SECRET_KEY"),
    ("S3_BUCKET", "MINIO_BUCKET"),
    ("S3_REGION", "MINIO_REGION"),
)


def _env_has(name: str) -> bool:
    """True when ``name`` is set in the process environment (case-insensitive)."""
    upper = name.upper()
    return any(k.upper() == upper for k in os.environ)


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

    # --- Object storage (any S3-compatible service: RustFS, MinIO, AWS S3, Ceph) ---
    s3_endpoint: str = Field(
        default="http://localhost:9000",
        validation_alias=AliasChoices("S3_ENDPOINT", "MINIO_ENDPOINT"),
        description="Internal API-to-storage S3 endpoint.",
    )
    s3_public_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("S3_PUBLIC_ENDPOINT", "MINIO_PUBLIC_ENDPOINT"),
        description=(
            "Browser-reachable S3 URL used when signing download URLs "
            "(e.g. http://localhost:9002 or https://objects.example.org)."
        ),
    )
    s3_access_key: str = Field(
        default="minioadmin",
        validation_alias=AliasChoices("S3_ACCESS_KEY", "MINIO_ACCESS_KEY"),
        description="Restricted application credential (never the storage root key).",
    )
    s3_secret_key: str = Field(
        default="minioadmin",
        validation_alias=AliasChoices("S3_SECRET_KEY", "MINIO_SECRET_KEY"),
    )
    s3_bucket: str = Field(
        default="fairdatahive-catalog",
        validation_alias=AliasChoices("S3_BUCKET", "MINIO_BUCKET"),
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("S3_REGION", "MINIO_REGION"),
        description="Explicit SigV4 signing region.",
    )
    s3_addressing_style: Literal["path", "virtual", "auto"] = Field(
        default="path",
        description="botocore addressing style; self-hosted S3 services need 'path'.",
    )

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
    enable_openapi: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)

    dev_auth_enabled: bool = Field(default=False)
    dev_auth_sub: str = Field(default="dev-user")
    dev_auth_name: str = Field(default="Development User")

    @model_validator(mode="after")
    def _warn_on_legacy_storage_aliases(self) -> "Settings":
        """Warn (without printing values) when both S3_* and MINIO_* names are set."""
        for new_name, legacy_name in S3_LEGACY_ENV_ALIASES:
            if _env_has(new_name) and _env_has(legacy_name):
                logger.warning(
                    "Both %s and legacy %s are set; using %s. "
                    "Remove %s - the MINIO_* aliases are deprecated.",
                    new_name,
                    legacy_name,
                    new_name,
                    legacy_name,
                )
        return self

    @property
    def legacy_storage_env_in_use(self) -> list[str]:
        """Legacy MINIO_* variables present in the environment (for startup diagnostics)."""
        return [legacy for _, legacy in S3_LEGACY_ENV_ALIASES if _env_has(legacy)]

    @property
    def s3_public_url(self) -> str:
        """URL embedded in presigned download links (must resolve in the user's browser)."""
        return (self.s3_public_endpoint or self.s3_endpoint).rstrip("/")

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
