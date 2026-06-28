from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AI Recruitment Intelligence Platform"
    DEBUG: bool = True
    API_VERSION: str = "v1"

    # Changed: OPENAI_API_KEY → GEMINI_API_KEY
    GEMINI_API_KEY: str = "your-key-here"
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_TEMPERATURE: float = 0.3

    DATABASE_URL: str = "sqlite:///./recruitment.db"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()