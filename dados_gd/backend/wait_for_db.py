#!/usr/bin/env python3
"""Script para aguardar o banco de dados estar pronto"""
import socket
import time
import os
import sys

DB_HOST = os.getenv('DB_HOST', 'gd_db')
DB_PORT = int(os.getenv('DB_PORT', 5432))
MAX_ATTEMPTS = 120
WAIT_TIME = 1

def check_db_connection():
    """Verifica se o banco de dados está acessível"""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((DB_HOST, DB_PORT))
            sock.close()

            if result == 0:
                print(f"✓ Banco de dados está pronto em {DB_HOST}:{DB_PORT}")
                time.sleep(5)
                return True
            else:
                print(f"Tentativa {attempt}/{MAX_ATTEMPTS}: Banco de dados ainda não está disponível...")
                time.sleep(WAIT_TIME)
        except Exception as e:
            print(f"Tentativa {attempt}/{MAX_ATTEMPTS}: Erro ao conectar - {e}")
            time.sleep(WAIT_TIME)

    print("Timeout: Banco de dados não respondeu após múltiplas tentativas")
    return False

if __name__ == "__main__":
    if check_db_connection():
        sys.exit(0)
    else:
        sys.exit(1)
