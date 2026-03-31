from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="job-bot-general")
    app_env: str = Field(default="development")
    app_debug: bool = Field(default=False)
    api_v1_prefix: str = Field(default="/api/v1")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/job_bot_general",
        alias="DATABASE_URL",
    )
    github_repository: str | None = Field(default=None)
    github_token: str | None = Field(default=None, alias="GH_TOKEN")

    openai_api_key: str | None = Field(default=None)
    scrapegraph_api_key: str | None = Field(default=None, alias="SGAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
