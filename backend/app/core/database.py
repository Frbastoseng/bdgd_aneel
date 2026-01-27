"""
Configuração do banco de dados com SQLAlchemy async
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from app.core.config import settings
import logging
import asyncio

logger = logging.getLogger(__name__)

# Base para modelos
Base = declarative_base()

# Variáveis globais que serão inicializadas depois
async_engine = None
sync_engine = None
AsyncSessionLocal = None


async def _init_engines_async():
    """Inicializar engines com retry - chamado apenas quando necessário"""
    global async_engine, sync_engine, AsyncSessionLocal
    
    if async_engine is not None:
        return  # Já inicializado
    
    logger.info(f"[DATABASE] Inicializando com DATABASE_URL: {settings.DATABASE_URL[:50]}...")
    
    # Aguardar um pouco para a rede Docker estar pronta
    await asyncio.sleep(2)
    
    # Engine assíncrono para operações normais
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args={
            "timeout": 10,
            "command_timeout": 10,
            "server_settings": {"jit": "off"}
        }
    )
    logger.info("[DATABASE] Engine assíncrono criado com sucesso")
    
    # Engine síncrono para migrações
    sync_engine = create_engine(
        settings.DATABASE_URL_SYNC,
        echo=settings.DEBUG,
        pool_size=5,
        max_overflow=10,
        connect_args={
            "connect_timeout": 10
        }
    )
    
    # Session factory
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False
    )


async def get_db() -> AsyncSession:
    """Dependency para injetar sessão do banco"""
    await _init_engines_async()
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Inicializar tabelas do banco"""
    await _init_engines_async()
    try:
        logger.info("[DATABASE] Iniciando conexão com o banco...")
        async with async_engine.begin() as conn:
            logger.info("[DATABASE] Conexão estabelecida, criando tabelas...")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("[DATABASE] ✓ Tabelas criadas com sucesso")
    except Exception as e:
        logger.error(f"[DATABASE] ✗ Erro ao inicializar banco: {e}", exc_info=True)
        raise


async def close_db():
    """Fechar conexões do banco"""
    global async_engine
    if async_engine is not None:
        await async_engine.dispose()
