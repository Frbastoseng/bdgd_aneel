"""
Configuration for the standalone CNPJ module.

Reads database connection from environment variables or CRM's .env file.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Try to load CRM's .env if it exists
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME", "crm_ludfor")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Schema where cnpj_cache table lives
SCHEMA = "crm"

# Receita Federal open data URL (via Casa dos Dados mirror - RF direct is unreliable)
RF_BASE_URL = "https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/2026-01-11/"

# Download directory for Receita Federal files
DOWNLOAD_DIR = Path(__file__).resolve().parent / "data"

# Processing settings
BATCH_SIZE = 10000      # Rows per DB commit (execute_values handles large batches well)
ENCODING = "iso-8859-1" # Receita Federal file encoding
SEPARATOR = ";"         # CSV separator
