from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://mocker:mocker@localhost:5432/mocker"
    jwt_secret: str = "change-me-in-production"
    jwt_expire_days: int = 30
    cookie_secure: bool = False
    data_dir: str = "data/questions"
    anthropic_api_key: str | None = None
    # LLM used by the current-affairs generator. Providers: groq | gemini | openrouter | ollama | anthropic
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_model: str = ""          # empty = provider default (see content/llm.py)
    llm_base_url: str = ""       # override for self-hosted / proxies
    # Daily current-affairs job
    current_affairs_enabled: bool = True
    current_affairs_hour_ist: int = 6      # local (IST) hour to run each day
    current_affairs_target: int = 15       # questions to aim for per day
    current_affairs_days_back: int = 2     # how many days of news to consider
    admin_token: str = ""                  # if set, enables POST /api/admin/* with X-Admin-Token
    # Nightly answer-key audit of bulk-imported questions
    verify_enabled: bool = True
    verify_hour_ist: int = 3
    verify_batch_size: int = 10
    verify_per_night: int = 400            # questions audited per run (fits the free-tier token budget)
    verify_model: str = "qwen/qwen3.8-27b" # 2M tokens/day on Groq's free tier vs 200k for gpt-oss-120b
    verify_autodisable_confidence: float = 0.85
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
