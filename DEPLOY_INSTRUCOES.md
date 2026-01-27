# 🚀 Deploy BDGD Pro na VPS

## Dados da VPS
- **Host:** 129.121.33.228
- **Porta SSH:** 22022
- **Usuário:** root
- **Senha:** Tfe@Cpfl@2026
- **URL:** https://bdgd.btstech.com.br

---

## Passo 1: Conectar na VPS

Abra um terminal (PowerShell ou CMD) e execute:

```bash
ssh -o HostKeyAlgorithms=+ssh-rsa -p 22022 root@129.121.33.228
```

Quando pedir a senha, digite: `Tfe@Cpfl@2026`

---

## Passo 2: Executar o Deploy

Após conectar, copie e cole TODOS os comandos abaixo de uma vez:

```bash
# Parar containers antigos
cd /root
docker-compose down 2>/dev/null || true
docker stop $(docker ps -aq) 2>/dev/null || true
docker rm $(docker ps -aq) 2>/dev/null || true

# Limpar instalação antiga
rm -rf /root/bdgd-pro /root/bdgd_aneel 2>/dev/null || true

# Clonar repositório
git clone https://github.com/Frbastoseng/bdgd_aneel.git bdgd-pro
cd /root/bdgd-pro

# Criar .env
cat > .env << 'EOF'
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

# Atualizar nginx.conf para produção
cat > frontend/nginx.conf << 'EOF'
server {
    listen 80;
    server_name bdgd.btstech.com.br;
    
    root /usr/share/nginx/html;
    index index.html;
    
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/x-javascript application/xml application/javascript;
    
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
    }
    
    location /health {
        proxy_pass http://backend:8000/health;
    }
    
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
EOF

# Build e iniciar
docker-compose build --no-cache
docker-compose up -d

# Verificar status
sleep 30
docker-compose ps
echo ""
echo "Deploy concluído! Acesse: https://bdgd.btstech.com.br"
echo "Login: admin@bdgdpro.com / admin123"
```

---

## Verificar se está funcionando

Após o deploy, execute:
```bash
docker-compose ps
docker-compose logs --tail=20 backend
```

Se precisar reiniciar:
```bash
cd /root/bdgd-pro
docker-compose restart
```

---

## Credenciais de Acesso

- **URL:** https://bdgd.btstech.com.br
- **Email:** admin@bdgdpro.com
- **Senha:** admin123
