"""
Configurações da aplicação GD ANEEL usando Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache
import logging
import os

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Banco de dados
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://gd_user:GdAneel2026Secure@gd_db:5432/gd_aneel"
    )
    DATABASE_URL_SYNC: str = os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql://gd_user:GdAneel2026Secure@gd_db:5432/gd_aneel"
    )

    # App
    APP_NAME: str = os.getenv("APP_NAME", "GD ANEEL")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")

    # CORS
    ALLOWED_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8080,http://localhost:8001"
    )

    # API ANEEL - Geração Distribuída
    ANEEL_API_URL: str = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
    ANEEL_GD_RESOURCE_ID: str = "b1bd71e7-d0ad-4214-9053-cbd58e9564a7"

    # Importação
    IMPORT_BATCH_SIZE: int = 50000

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    logger.info(f"[CONFIG] Configurações carregadas: {settings.ENVIRONMENT}")
    logger.info(f"[CONFIG] DATABASE_URL: {settings.DATABASE_URL[:60]}...")
    logger.info(f"[CONFIG] DEBUG: {settings.DEBUG}")
    logger.info(f"[CONFIG] APP_NAME: {settings.APP_NAME}")
    return settings


settings = get_settings()
