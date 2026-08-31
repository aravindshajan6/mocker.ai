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
    # A day is only considered done once it actually has questions; below this the job retries.
    current_affairs_min_questions: int = 3
    current_affairs_max_attempts: int = 6
    current_affairs_tick_minutes: int = 5
    # Phased classification of staged exam questions
    staging_enabled: bool = True
    staging_hour_ist: int = 2
    staging_per_run: int = 600            # ceiling per run; the token budget usually stops it first
    staging_rate_limit_retries: int = 4
    staging_max_minutes: int = 90         # bound a run; the queue resumes the next night
    staging_model: str = "qwen/qwen3.8-27b"   # 2M tokens/day on Groq's free tier
    verify_enabled: bool = True
    verify_hour_ist: int = 3
    verify_batch_size: int = 10
    verify_per_night: int = 400            # questions audited per run (fits the free-tier token budget)
    verify_model: str = "qwen/qwen3.8-27b" # 2M tokens/day on Groq's free tier vs 200k for gpt-oss-120b
    verify_autodisable_confidence: float = 0.85
    # "Explain more" — results are cached on the question forever, so this only guards runaways
    explain_daily_budget: int = 300
    explain_model: str = ""                # blank = the provider default
    # Reminders
    reminders_enabled: bool = True
    vapid_subject: str = "mailto:hello@mocker.local"
    telegram_bot_token: str = ""           # optional; from @BotFather
    telegram_bot_username: str = ""        # used to build the deep link
    public_base_url: str = "http://localhost:3001"
    # Rate limiting. `trusted_proxy_hops` MUST match the real topology in front of uvicorn:
    # behind Traefik -> Next.js rewrite it is 2. Too low and forged X-Forwarded-For buys a fresh
    # bucket; too high and every visitor collapses into one.
    rate_limit_enabled: bool = True
    trusted_proxy_hops: int = 0            # 0 = direct (dev); production sets 2
    rate_limit_default: str = "300/minute"
    rate_limit_login: str = "8/minute;40/hour"
    rate_limit_explain: str = "20/minute"
    # Exposes POST /api/testing/reset-rate-limits. Must stay false anywhere reachable publicly.
    testing_hooks: bool = False
    hsts_enabled: bool = False             # production (behind TLS) sets this true
    # Public sign-up is closed by default: accounts are provisioned by an admin.
    allow_signup: bool = False
    # Accounts created on startup (leave a password empty to skip that account)
    demo_email: str = "demo@mocker.app"
    demo_password: str = "demo1234"
    demo_name: str = "Demo Learner"
    admin_email: str = "admin@mocker.app"
    admin_password: str = "changeme-admin"
    admin_name: str = "Admin"
    seed_user_email: str = "aswathi@gmail.com"
    seed_user_password: str = "aswathi123"
    seed_user_name: str = "Aswathi"
    cors_origins: str = "http://localhost:3001,http://localhost:3000"
    # Scoring
    base_points: int = 10
    daily_quiz_size: int = 10
    topic_quiz_size: int = 10
    daily_bonus: int = 25


settings = Settings()
