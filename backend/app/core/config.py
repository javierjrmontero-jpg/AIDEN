from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    ASSISTANT_NAME: str = "AIDEN"
    ASSISTANT_LANGUAGE: str = "es"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    DATABASE_URL: str = "sqlite:///./data/db/aiden.db"
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    BRAVE_SEARCH_API_KEY: str = ""
    SEARCH_ENABLED: bool = True
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_CALENDAR_ENABLED: bool = True
    MICROSOFT_CLIENT_ID: str = ""
    class Config:
        env_file = ".env"

settings = Settings()
