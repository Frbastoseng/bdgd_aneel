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
            logger.info("[DATABASE] ✓ Tabelas ORM criadas com sucesso")

            # Criar tabelas B3 matching (raw SQL)
            from sqlalchemy import text
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS b3_clientes (
                    cod_id TEXT PRIMARY KEY,
                    lgrd_original TEXT, brr_original TEXT, cep_original TEXT, cnae_original TEXT,
                    logradouro_norm TEXT, numero_norm TEXT, bairro_norm TEXT, cep_norm TEXT,
                    cnae_norm TEXT, cnae_5dig TEXT,
                    mun_code TEXT, municipio_nome TEXT, uf TEXT, point_x FLOAT, point_y FLOAT,
                    clas_sub TEXT, gru_tar TEXT, consumo_anual FLOAT, consumo_medio FLOAT,
                    car_inst FLOAT, fas_con TEXT, sit_ativ TEXT,
                    dic_anual FLOAT, fic_anual FLOAT, possui_solar BOOLEAN DEFAULT FALSE,
                    geo_logradouro TEXT, geo_numero TEXT, geo_bairro TEXT, geo_cep TEXT,
                    geo_municipio TEXT, geo_uf TEXT, geo_source TEXT, geo_status TEXT
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS b3_cnpj_matches (
                    id SERIAL PRIMARY KEY,
                    bdgd_cod_id TEXT NOT NULL REFERENCES b3_clientes(cod_id) ON DELETE CASCADE,
                    cnpj TEXT NOT NULL, score_total FLOAT NOT NULL DEFAULT 0,
                    score_cep FLOAT DEFAULT 0, score_cnae FLOAT DEFAULT 0,
                    score_endereco FLOAT DEFAULT 0, score_numero FLOAT DEFAULT 0,
                    score_bairro FLOAT DEFAULT 0, rank INTEGER NOT NULL DEFAULT 1,
                    address_source TEXT DEFAULT 'bdgd',
                    razao_social TEXT, nome_fantasia TEXT,
                    cnpj_logradouro TEXT, cnpj_numero TEXT, cnpj_bairro TEXT,
                    cnpj_cep TEXT, cnpj_municipio TEXT, cnpj_uf TEXT,
                    cnpj_cnae TEXT, cnpj_cnae_descricao TEXT, cnpj_situacao TEXT,
                    cnpj_telefone TEXT, cnpj_email TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_b3_clientes_cep ON b3_clientes(cep_norm)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_b3_clientes_uf ON b3_clientes(uf)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_b3_matches_cod_id ON b3_cnpj_matches(bdgd_cod_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_b3_matches_rank ON b3_cnpj_matches(bdgd_cod_id, rank)"))

            # Tabelas de prospecção B3
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS b3_listas_prospeccao (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(200) NOT NULL, descricao TEXT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    filtros_aplicados JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS b3_lista_unidades (
                    lista_id INTEGER NOT NULL REFERENCES b3_listas_prospeccao(id) ON DELETE CASCADE,
                    cod_id TEXT NOT NULL, added_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (lista_id, cod_id)
                )
            """))
            logger.info("[DATABASE] ✓ Tabelas B3 matching/prospecção criadas")
    except Exception as e:
        logger.error(f"[DATABASE] ✗ Erro ao inicializar banco: {e}", exc_info=True)
        raise


async def close_db():
    """Fechar conexões do banco"""
    global async_engine
    if async_engine is not None:
        await async_engine.dispose()
