# BDGD Pro

Sistema profissional de consulta de dados ANEEL da Base de Dados Geográfica da Distribuidora (BDGD).

## 🚀 Tecnologias

### Backend
- **FastAPI** - Framework web assíncrono de alta performance
- **SQLAlchemy** (async) - ORM com suporte a PostgreSQL
- **PostgreSQL** - Banco de dados relacional
- **Redis** - Cache e sessões
- **JWT** - Autenticação segura

### Frontend
- **React 18** - Biblioteca UI
- **TypeScript** - Tipagem estática
- **Vite** - Build tool moderno
- **Tailwind CSS** - Framework CSS utilitário
- **React Query** - Gerenciamento de estado servidor
- **Google Maps API** - Mapas e Street View

## 📋 Pré-requisitos

- Docker e Docker Compose
- Chave da API do Google Maps (para funcionalidade de mapas)
- Node.js 18+ (para desenvolvimento local)
- Python 3.11+ (para desenvolvimento local)

## 🔧 Instalação

### 1. Clone o repositório
```bash
git clone <seu-repositorio>
cd bdgd-pro
```

### 2. Configure as variáveis de ambiente
```bash
cp .env.example .env
```

Edite o arquivo `.env` e configure:
- `SECRET_KEY` - Chave secreta para JWT (mínimo 32 caracteres)
- `DB_PASSWORD` - Senha do banco de dados
- `GOOGLE_MAPS_API_KEY` - Chave da API do Google Maps

### 3. Inicie com Docker Compose
```bash
docker-compose up -d --build
```

O sistema estará disponível em:
- **Frontend**: http://localhost
- **API**: http://localhost:8000
- **Documentação API**: http://localhost:8000/docs

## 💻 Desenvolvimento Local

### Backend
```bash
cd backend

# Criar ambiente virtual
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
set DATABASE_URL=postgresql+asyncpg://bdgd:bdgd_secret_2024@localhost:5432/bdgd_pro
set SECRET_KEY=your-super-secret-key-change-in-production

# Executar migrações
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend

# Instalar dependências
npm install

# Configurar variáveis de ambiente
echo "VITE_API_URL=http://localhost:8000" > .env.local
echo "VITE_GOOGLE_MAPS_API_KEY=sua-chave-aqui" >> .env.local

# Iniciar servidor de desenvolvimento
npm run dev
```

## 📁 Estrutura do Projeto

```
bdgd-pro/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # Dependências de autenticação
│   │   │   └── routes/
│   │   │       ├── auth.py      # Endpoints de autenticação
│   │   │       ├── admin.py     # Endpoints administrativos
│   │   │       └── aneel.py     # Endpoints de dados ANEEL
│   │   ├── core/
│   │   │   ├── config.py        # Configurações
│   │   │   ├── database.py      # Conexão com banco
│   │   │   └── security.py      # JWT e hashing
│   │   ├── models/
│   │   │   └── user.py          # Modelos SQLAlchemy
│   │   ├── schemas/
│   │   │   ├── user.py          # Schemas Pydantic
│   │   │   └── aneel.py         # Schemas de dados
│   │   ├── services/
│   │   │   ├── auth_service.py  # Lógica de autenticação
│   │   │   └── aneel_service.py # Lógica de consulta ANEEL
│   │   └── main.py              # Aplicação FastAPI
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # Componentes reutilizáveis
│   │   ├── layouts/             # Layouts de página
│   │   ├── pages/               # Páginas da aplicação
│   │   ├── services/            # Cliente API
│   │   ├── stores/              # Estado global
│   │   └── types/               # Tipos TypeScript
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🔐 Sistema de Autenticação

### Fluxo de Registro
1. Usuário preenche formulário de cadastro
2. Solicitação fica pendente aguardando aprovação
3. Administrador revisa e aprova/rejeita
4. Usuário aprovado recebe acesso ao sistema

### Níveis de Acesso
- **Usuário**: Consulta de dados, mapas e exportação
- **Admin**: Gerenciamento de usuários e aprovações

## 📊 Funcionalidades

### Consulta BDGD
- Filtros por UF, município, microrregião, mesorregião
- Filtros por classificação e grupo tarifário
- Filtros por faixa de demanda e energia
- Exportação em CSV, XLSX e KML

### Mapa Interativo
- Visualização de pontos no Google Maps
- Street View integrado
- Filtros por demanda e geração solar
- Clusterização de marcadores

### Tarifas ANEEL
- Consulta de tarifas por distribuidora
- Filtros por subgrupo e modalidade
- Dados atualizados diretamente da ANEEL

### Painel Administrativo
- Dashboard com estatísticas
- Gerenciamento de usuários
- Aprovação de solicitações de acesso
- Suspensão/ativação de contas

## 🔧 Configuração do Google Maps

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um novo projeto ou selecione um existente
3. Ative as APIs:
   - Maps JavaScript API
   - Street View Static API
4. Crie uma chave de API
5. Adicione ao arquivo `.env`: `GOOGLE_MAPS_API_KEY=sua-chave`

## 📈 Performance e Escalabilidade

O sistema foi projetado para suportar 100+ usuários simultâneos:

- **FastAPI async**: Processamento assíncrono de requisições
- **Connection pooling**: pool_size=20, max_overflow=30
- **Redis cache**: Cache de consultas frequentes
- **Nginx**: Servidor web otimizado para produção
- **PostgreSQL**: Banco de dados robusto e escalável

## 🛡️ Segurança

- Senhas hashadas com bcrypt
- JWT com tokens de acesso (30 min) e refresh (7 dias)
- CORS configurável
- Headers de segurança no Nginx
- Rate limiting (implementável via Redis)

## 📝 Licença

Projeto proprietário - Todos os direitos reservados.
