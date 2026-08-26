from pydantic_settings import BaseSettings
from pydantic import field_validator

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
    # El login web y el calendario usan clientes OAuth distintos: el script de
    # autorización necesita un cliente de escritorio (redirect a localhost), que
    # el cliente web no admite. Un refresh_token solo se canjea con el par que
    # lo emitió. Si quedan vacías, se usan las del login.
    GOOGLE_CALENDAR_CLIENT_ID: str = ""
    GOOGLE_CALENDAR_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""
    WHISPER_MODEL: str = "base"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    N8N_URL: str = ""
    N8N_WEBHOOK_URL: str = ""
    N8N_API_KEY: str = ""
    WEBHOOK_SECRET: str = ""
    OAUTH_ADMIN_EMAIL: str = "javierjrmontero@outlook.com"
    N8N_REGISTRATION_WEBHOOK: str = ""
    N8N_APPROVAL_WEBHOOK: str = ""
    APPROVAL_TOKEN_TTL: int = 172800  # 48 horas

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres")
        return v

    class Config:
        env_file = ".env"

settings = Settings()
