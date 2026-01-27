#!/bin/bash
set -e

# Variáveis padrão
DB_HOST=${DB_HOST:-bdgd_db}
DB_PORT=${DB_PORT:-5432}
DB_USER=${DB_USER:-bdgd_user}
DB_NAME=${DB_NAME:-bdgd_aneel_prod}

echo "Aguardando banco de dados em $DB_HOST:$DB_PORT estar pronto..."
for i in {1..30}; do
  if nc -z $DB_HOST $DB_PORT 2>/dev/null; then
    echo "✓ Banco de dados está pronto!"
    sleep 2
    break
  fi
  echo "Tentativa $i/30: Banco de dados ainda não está disponível. Aguardando..."
  sleep 2
done

echo "Iniciando aplicação FastAPI..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
