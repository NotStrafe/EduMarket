from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env early so pydantic can pick variables up in any runtime
load_dotenv()


class Settings(BaseSettings):
    app_name: str = "EduMarket API"
    app_version: str = "0.1.0"
    environment: str = "development"
    app_port: int = 8000

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "edumarket"
    postgres_user: str = "edumarket"
    postgres_password: str = "edumarket"
    database_url: str | None = None

    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            "postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
