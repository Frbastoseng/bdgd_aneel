# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY .env* .
COPY wait_for_db.py .
COPY entrypoint_simple.sh /app/entrypoint.sh

# Criar diretório de dados
RUN mkdir -p /app/data && chmod +x /app/entrypoint.sh /app/wait_for_db.py

# Expor porta
EXPOSE 8000

# Comando de inicialização
ENTRYPOINT ["/app/entrypoint.sh"]
