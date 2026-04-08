from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    environment: str = "development"
    app_url: str = "http://localhost"

    # Database
    database_url: str = "postgresql+asyncpg://smi:localdev@db:5432/sketchmyinfra"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_days: int = 7

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # PlantUML (internal Docker service)
    plantuml_server_url: str = "http://plantuml:8080"

    # OAuth - Google
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth - GitHub
    github_client_id: str = ""
    github_client_secret: str = ""

    # CORS
    cors_origins: str = "http://localhost,http://localhost:3000"

    # Rate limits (generations per day)
    rate_limit_anonymous: int = 3
    rate_limit_free: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
