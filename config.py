from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://procureiq:procureiq@localhost:5432/procureiq"
    api_key: str = "procureiq-dev-key"
    api_base_url: str = "http://localhost:8000"
    openai_api_key: str = ""
    log_level: str = "INFO"


settings = Settings()
