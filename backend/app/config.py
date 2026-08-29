from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mocker:mocker@localhost:5432/mocker"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_days: int = 30
    cookie_secure: bool = False
    data_dir: str = "data/questions"
    anthropic_api_key: str | None = None
    # Demo account created on startup (set demo_password empty to disable)
    demo_email: str = "demo@mocker.app"
    demo_password: str = "demo1234"
    demo_name: str = "Demo Learner"
    cors_origins: str = "http://localhost:3001,http://localhost:3000"
    # Scoring
    base_points: int = 10
    daily_quiz_size: int = 10
    topic_quiz_size: int = 10
    daily_bonus: int = 25


settings = Settings()
