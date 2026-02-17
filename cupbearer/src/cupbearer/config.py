from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised when required application configuration is missing."""


@dataclass(frozen=True)
class Settings:
    env: str
    service_name: str
    log_level: str
    db_path: str
    worker_poll_interval_seconds: float
    worker_retry_base_seconds: float
    worker_retry_max_seconds: float
    twilio_account_sid: str | None
    twilio_auth_token: str | None
    twilio_whatsapp_from: str | None
    twilio_webhook_validate_signature: bool
    twilio_send_mode: str
    agent_provider: str
    claude_api_key: str | None
    claude_model: str
    claude_base_url: str
    claude_timeout_seconds: float
    claude_mock_response: str | None
    claude_mock_tool_followup_response: str | None
    steersman_base_url: str
    steersman_auth_token: str
    steersman_timeout_seconds: float
    mem0_enabled: bool
    mem0_storage_path: str
    openai_api_key: str | None


def load_settings() -> Settings:
    env = os.getenv("CUPBEARER_ENV")
    if not env:
        raise ConfigError("Missing required environment variable: CUPBEARER_ENV")

    service_name = os.getenv("CUPBEARER_SERVICE_NAME", "cupbearer")
    log_level = os.getenv("CUPBEARER_LOG_LEVEL", "INFO").upper()
    db_path = os.getenv("CUPBEARER_DB_PATH", "data/cupbearer.db")
    worker_poll_interval_seconds = float(
        os.getenv("CUPBEARER_WORKER_POLL_INTERVAL_SECONDS", "1.0")
    )
    worker_retry_base_seconds = float(
        os.getenv("CUPBEARER_WORKER_RETRY_BASE_SECONDS", "5.0")
    )
    worker_retry_max_seconds = float(
        os.getenv("CUPBEARER_WORKER_RETRY_MAX_SECONDS", "300.0")
    )
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
    twilio_webhook_validate_signature = (
        os.getenv("CUPBEARER_TWILIO_VALIDATE_SIGNATURE", "1").strip() != "0"
    )
    twilio_send_mode = os.getenv("CUPBEARER_TWILIO_SEND_MODE", "live").strip().lower()
    agent_provider = os.getenv("CUPBEARER_AGENT_PROVIDER", "claude").strip().lower()
    claude_api_key = os.getenv("ANTHROPIC_API_KEY")
    claude_model = os.getenv("CUPBEARER_CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    claude_base_url = os.getenv("CUPBEARER_CLAUDE_BASE_URL", "https://api.anthropic.com")
    claude_timeout_seconds = float(os.getenv("CUPBEARER_CLAUDE_TIMEOUT_SECONDS", "20.0"))
    claude_mock_response = os.getenv("CUPBEARER_CLAUDE_MOCK_RESPONSE")
    claude_mock_tool_followup_response = os.getenv("CUPBEARER_CLAUDE_MOCK_TOOL_FOLLOWUP_RESPONSE")
    steersman_base_url = os.getenv("CUPBEARER_STEERSMAN_BASE_URL", "http://127.0.0.1:8765")
    steersman_auth_token = os.getenv("CUPBEARER_STEERSMAN_AUTH_TOKEN", "dev-token")
    steersman_timeout_seconds = float(os.getenv("CUPBEARER_STEERSMAN_TIMEOUT_SECONDS", "10.0"))
    mem0_enabled = os.getenv("CUPBEARER_MEM0_ENABLED", "0").strip() != "0"
    mem0_storage_path = os.getenv("CUPBEARER_MEM0_STORAGE_PATH", "data/mem0_qdrant")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    return Settings(
        env=env,
        service_name=service_name,
        log_level=log_level,
        db_path=db_path,
        worker_poll_interval_seconds=worker_poll_interval_seconds,
        worker_retry_base_seconds=worker_retry_base_seconds,
        worker_retry_max_seconds=worker_retry_max_seconds,
        twilio_account_sid=twilio_account_sid,
        twilio_auth_token=twilio_auth_token,
        twilio_whatsapp_from=twilio_whatsapp_from,
        twilio_webhook_validate_signature=twilio_webhook_validate_signature,
        twilio_send_mode=twilio_send_mode,
        agent_provider=agent_provider,
        claude_api_key=claude_api_key,
        claude_model=claude_model,
        claude_base_url=claude_base_url,
        claude_timeout_seconds=claude_timeout_seconds,
        claude_mock_response=claude_mock_response,
        claude_mock_tool_followup_response=claude_mock_tool_followup_response,
        steersman_base_url=steersman_base_url,
        steersman_auth_token=steersman_auth_token,
        steersman_timeout_seconds=steersman_timeout_seconds,
        mem0_enabled=mem0_enabled,
        mem0_storage_path=mem0_storage_path,
        openai_api_key=openai_api_key,
    )
