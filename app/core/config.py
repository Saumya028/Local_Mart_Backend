from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    # Only set for projects still on the legacy shared HS256 secret (Project
    # Settings -> API -> JWT Keys -> "Legacy JWT Secret" tab). Projects on the
    # newer asymmetric JWT Signing Keys don't have one — auth still works via
    # JWKS verification (see app/core/security.py) without this being set.
    supabase_jwt_secret: str = ""

    cors_origins: str = "http://localhost:3000"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
