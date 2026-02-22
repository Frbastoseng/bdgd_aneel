"""
Configurações da aplicação usando Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache
import logging
import os

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Banco de dados - ler do ambiente (docker-compose passa via variáveis)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://bdgd_user:BdGd@Secure2026!@bdgd_db:5432/bdgd_aneel_prod?ssl=false"
    )
    DATABASE_URL_SYNC: str = os.getenv(
        "DATABASE_URL_SYNC",
        "postgresql://bdgd_user:BdGd@Secure2026!@bdgd_db:5432/bdgd_aneel_prod?sslmode=disable"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://bdgd_redis:6379/0")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "sua-chave-secreta-super-segura-aqui-mude-em-producao-2024")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # App
    APP_NAME: str = os.getenv("APP_NAME", "BDGD Pro")
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    
    # CORS
    ALLOWED_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        "https://bdgd.btstech.com.br,http://localhost:3000,http://localhost:5173,http://localhost:8080"
    )
    
    # Google Maps
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    
    # Admin padrão
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@bdgd.btstech.com.br")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "Admin@Bdgd2026!")
    
    # API ANEEL
    ANEEL_API_URL: str = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
    ANEEL_RESOURCE_ID: str = "f6671cba-f269-42ef-8eb3-62cb3bfa0b98"
    ANEEL_TARIFAS_RESOURCE_ID: str = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"

    # API GD (Geração Distribuída) - microserviço separado
    GD_API_URL: str = os.getenv("GD_API_URL", "http://gd_backend:8001")
    
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
    logger.info(f"[CONFIG] REDIS_URL: {settings.REDIS_URL}")
    logger.info(f"[CONFIG] DEBUG: {settings.DEBUG}")
    logger.info(f"[CONFIG] APP_NAME: {settings.APP_NAME}")
    return settings


settings = get_settings()
