#!/bin/bash
# Script de deploy para VPS - BDGD Pro
# Execute: bash deploy_vps.sh

set -e

echo "=========================================="
echo "  DEPLOY BDGD Pro na VPS"
echo "=========================================="

# Parar containers antigos se existirem
echo ""
echo ">>> Parando containers antigos..."
cd /root 2>/dev/null || cd ~
docker-compose down 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true

# Remover diretório antigo se existir
echo ""
echo ">>> Removendo instalação antiga..."
rm -rf /root/bdgd-pro 2>/dev/null || true
rm -rf /root/bdgd_aneel 2>/dev/null || true

# Clonar repositório
echo ""
echo ">>> Clonando repositório do GitHub..."
cd /root
git clone https://github.com/Frbastoseng/bdgd_aneel.git bdgd-pro

# Entrar no diretório
cd /root/bdgd-pro

# Criar arquivo .env para produção
echo ""
echo ">>> Criando arquivo .env..."
cat > .env << 'EOF'
# Produção
DATABASE_URL=postgresql+asyncpg://bdgd:bdgd123@db:5432/bdgd_pro
POSTGRES_USER=bdgd
POSTGRES_PASSWORD=bdgd123
POSTGRES_DB=bdgd_pro
SECRET_KEY=supersecretkey2026bdgdpro
ADMIN_EMAIL=admin@bdgdpro.com
ADMIN_PASSWORD=admin123
VITE_API_URL=/api/v1
EOF

# Criar diretório de dados
mkdir -p data

# Atualizar docker-compose para produção (porta 80)
echo ""
echo ">>> Configurando docker-compose para produção..."
cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  db:
    image: postgres:15-alpine
    container_name: bdgd_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-bdgd}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-bdgd123}
      POSTGRES_DB: ${POSTGRES_DB:-bdgd_pro}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-bdgd} -d ${POSTGRES_DB:-bdgd_pro}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always
    networks:
      - bdgd_network

  redis:
    image: redis:7-alpine
    container_name: bdgd_redis
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: always
    networks:
      - bdgd_network

  backend:
    build: ./backend
    container_name: bdgd_backend
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql+asyncpg://bdgd:bdgd123@db:5432/bdgd_pro}
      SECRET_KEY: ${SECRET_KEY:-supersecretkey2026}
      ADMIN_EMAIL: ${ADMIN_EMAIL:-admin@bdgdpro.com}
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:-admin123}
      REDIS_URL: redis://redis:6379
    volumes:
      - ./data:/app/data
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - bdgd_network

  frontend:
    build: ./frontend
    container_name: bdgd_frontend
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: always
    networks:
      - bdgd_network

volumes:
  postgres_data:

networks:
  bdgd_network:
    driver: bridge
EOF

# Atualizar nginx.conf para proxy reverso
echo ""
echo ">>> Configurando nginx para produção..."
cat > frontend/nginx.conf << 'EOF'
server {
    listen 80;
    server_name bdgd.btstech.com.br;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # Gzip
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied expired no-cache no-store private auth;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript;
    
    # Proxy para API
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
    
    # Health check
    location /health {
        proxy_pass http://backend:8000/health;
    }
    
    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # Cache para assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Build e iniciar containers
echo ""
echo ">>> Construindo e iniciando containers..."
docker-compose build --no-cache
docker-compose up -d

# Aguardar serviços ficarem prontos
echo ""
echo ">>> Aguardando serviços iniciarem..."
sleep 30

# Verificar status
echo ""
echo ">>> Status dos containers:"
docker-compose ps

echo ""
echo "=========================================="
echo "  DEPLOY CONCLUÍDO!"
echo "=========================================="
echo ""
echo "Acesse: https://bdgd.btstech.com.br"
echo ""
echo "Login padrão:"
echo "  Email: admin@bdgdpro.com"
echo "  Senha: admin123"
echo ""
