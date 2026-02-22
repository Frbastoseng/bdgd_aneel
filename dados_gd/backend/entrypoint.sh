#!/bin/bash
set -e

echo "Aguardando banco de dados estar pronto..."
python3 /app/wait_for_db.py

if [ $? -ne 0 ]; then
    echo "Falha ao conectar ao banco de dados"
    exit 1
fi

echo "Iniciando aplicação GD ANEEL..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
