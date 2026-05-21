from pydantic_settings import BaseSettings
from pydantic import field_validator
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("LUNA_DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "Luna"
    host: str = "127.0.0.1"
    port: int = 8899
    debug: bool = False

    # ── LLM — provider selection ──────────────────────────────────────────────
    # Values: ollama | openai-compatible | nvidia-nim | anthropic | google | groq | cohere | mistral
    llm_provider: str = "ollama"

    # Ollama (local, default)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"

    # OpenAI / OpenAI-compatible (LM Studio, Jan.ai, llama.cpp, OpenRouter, etc.)
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"

    # NVIDIA NIM (OpenAI-compatible /v1/chat/completions)
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_api_key: str = ""
    nvidia_nim_model: str = "meta/llama-3.1-8b-instruct"

    # Anthropic Claude (native)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"

    # Google Gemini (native)
    google_api_key: str = ""
    google_model: str = "gemini-2.0-flash"

    # Groq (ultra-fast cloud inference, native)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Cohere (native)
    cohere_api_key: str = ""
    cohere_model: str = "command-r-plus"

    # Mistral AI (native)
    mistral_api_key: str = ""
    mistral_model: str = "mistral-large-latest"

    # Embedding provider: ollama | openai-compatible
    embedding_provider: str = "ollama"

    # ── Paths ─────────────────────────────────────────────────────────────────
    db_path: str = str(DATA_DIR / "luna.db")
    chroma_path: str = str(DATA_DIR / "chroma")
    frontend_dist: str = str(BASE_DIR / "frontend" / "dist")

    # ── Memory ────────────────────────────────────────────────────────────────
    max_conversation_history: int = 30
    memory_retrieval_count: int = 6
    fact_extraction_interval: int = 5

    # ── Auth & access ─────────────────────────────────────────────────────────
    # Production: set to a long random string; used to sign per-user JWT tokens.
    jwt_secret: str = ""
    jwt_expiry_hours: int = 720  # 30 days

    # ── Rate limiting (production) ────────────────────────────────────────────
    rate_limit_enabled: bool = False
    rate_limit_per_minute: int = 60        # requests per user per minute
    rate_limit_burst: int = 20             # additional burst allowance

    # ── External data APIs ────────────────────────────────────────────────────
    the_news_api: str = ""
    open_weather: str = ""
    alpha_vantage: str = ""
    weather_lat: float = 40.7128
    weather_lon: float = -74.0060
    weather_city: str = "New York"
    weather_timezone: str = "America/New_York"

    # ── Messaging channels (OpenClaw-style) ───────────────────────────────────
    # Telegram: set bot token + run  /setwebhook  to point at /api/channels/telegram
    telegram_bot_token: str = ""
    # Discord: set bot token + configure interactions endpoint /api/channels/discord
    discord_bot_token: str = ""
    discord_public_key: str = ""           # for signature verification
    # Slack: set bot token + signing secret; Events API → /api/channels/slack
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    # GitHub: PAT for API calls, webhook secret for event signature verification
    github_token: str = ""                  # Personal Access Token (repo scope)
    github_webhook_secret: str = ""         # Secret set in GitHub webhook settings
    github_default_repo: str = ""           # e.g. "owner/repo" — default for tool calls
    github_notify_slack_channel: str = ""   # Slack channel ID for event notifications
    github_notify_telegram_chat_id: str = "" # Telegram chat ID for event notifications

    # Google Workspace / Microsoft 365 (OAuth access tokens; opt-in)
    google_workspace_client_id: str = ""
    google_workspace_client_secret: str = ""
    google_workspace_refresh_token: str = ""
    google_workspace_access_token: str = ""
    microsoft_workspace_client_id: str = ""
    microsoft_workspace_client_secret: str = ""
    microsoft_workspace_tenant_id: str = "common"
    microsoft_workspace_refresh_token: str = ""
    microsoft_workspace_access_token: str = ""

    # ── Spotify (personal variant — opt-in) ──────────────────────────────────
    spotify_client_id: str = ""
    spotify_client_secret: str = ""

    # ── Health Platforms (opt-in) ────────────────────────────────────────────
    # Fitbit (OAuth2) — app.fitbit.com/oauth2/applications
    fitbit_client_id: str = ""
    fitbit_client_secret: str = ""
    fitbit_access_token: str = ""
    fitbit_refresh_token: str = ""

    # Google Fit (OAuth2) — separate from Workspace; Google Cloud Console
    google_fit_client_id: str = ""
    google_fit_client_secret: str = ""
    google_fit_access_token: str = ""
    google_fit_refresh_token: str = ""

    # Oura Ring (Personal Access Token) — cloud.ouraring.com/user/api-tokens
    oura_api_key: str = ""

    # Withings (OAuth2) — developer.withings.com
    withings_client_id: str = ""
    withings_client_secret: str = ""
    withings_access_token: str = ""
    withings_refresh_token: str = ""

    # Garmin Connect (credentials for garth library)
    garmin_email: str = ""
    garmin_password: str = ""

    # Apple Health / Samsung Health — these platforms have no public REST API.
    # Use the "Health Auto Export" iOS app or a compatible Android exporter
    # to push data to Luna's webhook endpoint: POST /api/health/webhook/apple
    # or POST /api/health/webhook/samsung
    # Set a shared secret to authenticate inbound webhooks.
    health_webhook_secret: str = ""

    # ── Variant ───────────────────────────────────────────────────────────────
    # personal  — casual companion, voice, desktop automation, single user
    # business  — professional team assistant, multi-user JWT, rate limiting on
    luna_variant: str = "personal"

    # ── Luna persona ──────────────────────────────────────────────────────────
    luna_name: str = "L.U.N.A."
    user_name: str = "friend"

    # Business variant config
    business_name: str = ""        # e.g. "Acme Corp"
    business_description: str = "" # e.g. "a SaaS company building developer tools"
    business_tone: str = "professional"  # professional | friendly | technical | concise

    # ── RL ────────────────────────────────────────────────────────────────────
    rl_learning_rate: float = 0.08
    rl_decay: float = 0.995

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "dev", "development", "true", "1", "yes", "on"}:
                return True
        return value

    class Config:
        env_file = os.getenv("LUNA_ENV_FILE", ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
