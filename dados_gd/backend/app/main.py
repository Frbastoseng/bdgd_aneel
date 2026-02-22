"""
GD ANEEL - Aplicação Principal FastAPI
Microserviço para dados de Geração Distribuída da ANEEL
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging

from app.core.config import settings
from app.core.database import init_db, close_db
from app.api.routes import gd_router

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

logger.info("=" * 80)
logger.info(f"GD ANEEL - Inicializando aplicação")
logger.info(f"Ambiente: {settings.ENVIRONMENT}")
logger.info(f"Debug: {settings.DEBUG}")
logger.info("=" * 80)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerenciamento do ciclo de vida da aplicação"""
    # Startup
    logger.info("=" * 80)
    logger.info("[STARTUP] Iniciando aplicação GD ANEEL...")
    logger.info(f"[STARTUP] Versão: {settings.APP_VERSION}")

    try:
        logger.info("[STARTUP] Conectando ao banco de dados...")
        await init_db()
        logger.info("[STARTUP] Banco de dados inicializado com sucesso")
    except Exception as e:
        logger.error(f"[STARTUP] Erro ao inicializar banco de dados: {e}", exc_info=True)
        raise

    logger.info("[STARTUP] Aplicação iniciada com sucesso")
    logger.info("=" * 80)
    yield

    # Shutdown
    logger.info("[SHUTDOWN] Encerrando aplicação...")
    await close_db()
    logger.info("[SHUTDOWN] Aplicação encerrada")


# Criar aplicação
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
    ## GD ANEEL API

    Microserviço para consulta de dados de Geração Distribuída da ANEEL.

    ### Funcionalidades:
    - Consulta de empreendimentos GD com filtros
    - Estatísticas por UF, tipo de geração e porte
    - Busca por código de empreendimento
    - Listagem de municípios com GD

    ### Dados:
    - 4M+ empreendimentos de micro e minigeração distribuída
    - Fonte: ANEEL Dados Abertos (CKAN API)
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# GZip (comprimir respostas > 500 bytes)
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS
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
app.include_router(gd_router, prefix="/api/v1")


# Health check
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
