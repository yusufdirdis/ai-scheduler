from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "ai-scheduler API"
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ai_scheduler"

    # Supabase Auth (JWT verification for multi-tenant API calls)
    SUPABASE_JWT_SECRET: str = ""
    AUTH_DISABLED: bool = False

    # Frontend URL
    PUBLIC_APP_URL: str = "http://localhost:3000"
    # Publicly reachable base URL for this API (used for Twilio webhook signature validation)
    PUBLIC_API_URL: str = "http://localhost:8000"

    # CORS — comma-separated origins
    CORS_ORIGINS: str = "http://localhost:3000"

    def cors_list(self) -> list[str]:
        parts = [p.strip() for p in self.CORS_ORIGINS.split(",") if p.strip()]
        return parts or ["http://localhost:3000"]

    # AI Provider: "gemini" | "openai" | "ollama"
    AI_PROVIDER: str = "gemini"
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    # Preferred over TWILIO_FROM_NUMBER when set — required for A2P 10DLC traffic.
    TWILIO_MESSAGING_SERVICE_SID: str = ""

    # Signed employee schedule-view links
    EMPLOYEE_LINK_SIGNING_SECRET: str = "dev-insecure-change-me"


settings = Settings()
