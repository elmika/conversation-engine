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
    openai_model: str = "gpt-4.1-mini"
    max_input_chars: int = 32_000
    max_output_tokens: int = 4_096
    request_timeout_s: int = 60
    max_retries: int = 2
    retry_backoff_s: float = 1.0
    default_prompt_slug: str = "default"
    # Sync SQLAlchemy engine; we offload DB work to worker threads.
    database_url: str = "sqlite:///./data/chat.db"
    
    # History capping to prevent context overflow and cost explosion
    # For gpt-4.1-mini (128K context), these are conservative limits
    max_history_turns: int = 20  # Max turns to include (10 back-and-forth exchanges)
    max_history_tokens: int = 100_000  # Max tokens in history (~75% of 128K context)
