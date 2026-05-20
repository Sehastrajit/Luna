from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
(DATA_DIR / "backups").mkdir(exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "Luna"
    host: str = "127.0.0.1"
    port: int = 8899
    debug: bool = False

    # Ollama
    llm_provider: str = "ollama"  # ollama | openai-compatible
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qcwind/qwen3-8b-instruct-Q4-K-M:latest"
    ollama_embed_model: str = "nomic-embed-text"

    # OpenAI-compatible cloud/local APIs
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    embedding_provider: str = "ollama"  # ollama | openai-compatible

    # Paths
    db_path: str = str(DATA_DIR / "luna.db")
    chroma_path: str = str(DATA_DIR / "chroma")
    frontend_dist: str = str(BASE_DIR / "frontend" / "dist")

    # Memory
    max_conversation_history: int = 30
    memory_retrieval_count: int = 6
    fact_extraction_interval: int = 5  # extract facts every N messages

    # Remote access — set a strong random string to enable auth
    luna_api_key: str = ""

    # External data APIs
    the_news_api: str = ""
    open_weather: str = ""
    alpha_vantage: str = ""
    weather_lat: float = 40.7128
    weather_lon: float = -74.0060
    weather_city: str = "New York"
    weather_timezone: str = "America/New_York"

    # Luna persona
    luna_name: str = "L.U.N.A."
    user_name: str = "friend"  # updated once learned

    # RL
    rl_learning_rate: float = 0.08
    rl_decay: float = 0.995  # daily decay toward neutral

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
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
