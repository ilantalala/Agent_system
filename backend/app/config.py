from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    llm_provider: str = "ollama"
    environment: str = "development"
    database_url: str

settings = Settings()