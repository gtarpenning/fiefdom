from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STEERSMAN_", extra="ignore")

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765, ge=1, le=65535)
    log_level: str = Field(default="info")
    auth_token: str = Field(default="dev-token")
    audit_log_path: str = Field(default=".steersman/audit.jsonl")
    idempotency_ttl_seconds: int = Field(default=3600, ge=1)
