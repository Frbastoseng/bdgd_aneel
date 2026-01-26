"""
Configurações da aplicação usando Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    # Banco de dados
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/bdgd_pro"
    DATABASE_URL_SYNC: str = "postgresql://postgres:password@localhost:5432/bdgd_pro"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    SECRET_KEY: str = "sua-chave-secreta-super-segura-aqui-mude-em-producao"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # App
    APP_NAME: str = "BDGD Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # Google Maps
    GOOGLE_MAPS_API_KEY: str = ""
    
    # Admin padrão
    ADMIN_EMAIL: str = "admin@bdgdpro.com"
    ADMIN_PASSWORD: str = "admin123456"
    
    # API ANEEL
    ANEEL_API_URL: str = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
    ANEEL_RESOURCE_ID: str = "f6671cba-f269-42ef-8eb3-62cb3bfa0b98"
    ANEEL_TARIFAS_RESOURCE_ID: str = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
