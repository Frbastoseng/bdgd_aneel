"""
BDGD Pro - Aplicação Principal FastAPI
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from app.core.config import settings
from app.core.database import init_db, close_db, AsyncSessionLocal
from app.api.routes import auth_router, admin_router, aneel_router
from app.services.auth_service import AuthService

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciamento do ciclo de vida da aplicação"""
    # Startup
    logger.info("Iniciando aplicação BDGD Pro...")
    
    # Inicializar banco de dados
    await init_db()
    logger.info("Banco de dados inicializado")
    
    # Criar admin padrão
    async with AsyncSessionLocal() as session:
        admin = await AuthService.create_admin_user(session)
        if admin:
            logger.info(f"Usuário admin disponível: {admin.email}")
    
    yield
    
    # Shutdown
    logger.info("Encerrando aplicação...")
    await close_db()


# Criar aplicação
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## BDGD Pro API
    
    Sistema profissional para consulta de dados da ANEEL (BDGD e Tarifas).
    
    ### Funcionalidades:
    - 🔐 Autenticação com JWT
    - 👥 Controle de acesso com aprovação de admin
    - 📊 Consulta de dados BDGD
    - 💰 Consulta de tarifas
    - 🗺️ Dados para mapa com Street View
    - 📥 Exportação (CSV, XLSX, KML)
    
    ### Autenticação:
    1. Registre-se em `/api/v1/auth/register`
    2. Aguarde aprovação do administrador
    3. Faça login em `/api/v1/auth/login`
    4. Use o token Bearer em todas as requisições
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Handlers de erro
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handler para erros de validação"""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Erro de validação",
            "errors": errors
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handler geral de exceções"""
    logger.error(f"Erro não tratado: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Erro interno do servidor",
            "message": str(exc) if settings.DEBUG else "Ocorreu um erro inesperado"
        }
    )


# Registrar rotas
app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(aneel_router, prefix="/api/v1")


# Rotas de health check
@app.get("/", tags=["Health"])
async def root():
    """Rota raiz"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Verificação de saúde da aplicação"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/v1/config", tags=["Config"])
async def get_public_config():
    """Configurações públicas da aplicação"""
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "google_maps_enabled": bool(settings.GOOGLE_MAPS_API_KEY)
    }
