from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    llm_provider: str = "ollama"
    environment: str = "development"
    database_url: str
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    antropic_api_key: str | None =None
    antropic_model: str = "claude-sonnet-5"
    antropic_max_tokens: int = 4096
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-nano"
    openai_max_output_tokens: int = 4096
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:32b"
    ollama_timeout_seconds: float = 300.0
settings = Settings()