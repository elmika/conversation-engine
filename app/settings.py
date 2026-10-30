"""Application configuration from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from env and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    anthropic_api_key: str = ""
    default_model: str = "gpt-4.1"
    wrap_up_model: str = "gpt-5.6-luna"
    max_input_chars: int = 32_000
    max_output_tokens: int = 4_096
    request_timeout_s: int = 60
    max_retries: int = 2
    retry_backoff_s: float = 1.0
    default_prompt_slug: str = "default"
    # Sync SQLAlchemy engine; we offload DB work to worker threads.
    database_url: str = "sqlite:///./data/chat.db"

    # History capping to prevent context overflow and cost explosion
    # For gpt-4.1 (1M context), these are conservative limits
    max_history_turns: int = 20  # Max turns to include (10 back-and-forth exchanges)
    max_history_tokens: int = 100_000  # Max tokens in history (~75% of 128K context)

    prompts_dir: str = "./prompts"
    sections_dir: str = "./sections"

    # Usage ceilings — starting point for a handful of supervised pilot learners,
    # tuned after test traffic. Overridable via a Fly secret without a code change.
    session_spend_cap_usd: float = 0.50
    daily_user_spend_cap_usd: float = 1.00
    daily_platform_spend_cap_usd: float = 5.00

    # Static bearer token for admin-only routes. An unset token must never mean
    # "open" — require_admin() fails closed (401) when this is empty.
    admin_token: str = ""
