"""Add cnpj_cache table

Revision ID: 002
Revises: 001
Create Date: 2026-02-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensao pg_trgm para busca fuzzy
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        'cnpj_cache',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column('cnpj', sa.String(14), nullable=False),

        # Dados principais
        sa.Column('razao_social', sa.String(200), nullable=True),
        sa.Column('nome_fantasia', sa.String(200), nullable=True),
        sa.Column('situacao_cadastral', sa.String(50), nullable=True),
        sa.Column('data_situacao_cadastral', sa.String(10), nullable=True),
        sa.Column('data_inicio_atividade', sa.String(10), nullable=True),
        sa.Column('natureza_juridica', sa.String(200), nullable=True),
        sa.Column('porte', sa.String(50), nullable=True),
        sa.Column('capital_social', sa.Numeric(15, 2), nullable=True),

        # CNAE
        sa.Column('cnae_fiscal', sa.String(10), nullable=True),
        sa.Column('cnae_fiscal_descricao', sa.String(200), nullable=True),
        sa.Column('cnaes_secundarios', JSONB, nullable=True),

        # Endereco
        sa.Column('logradouro', sa.String(200), nullable=True),
        sa.Column('numero', sa.String(20), nullable=True),
        sa.Column('complemento', sa.String(200), nullable=True),
        sa.Column('bairro', sa.String(100), nullable=True),
        sa.Column('municipio', sa.String(100), nullable=True),
        sa.Column('uf', sa.String(2), nullable=True),
        sa.Column('cep', sa.String(10), nullable=True),

        # Contato
        sa.Column('telefone_1', sa.String(30), nullable=True),
        sa.Column('telefone_2', sa.String(30), nullable=True),
        sa.Column('email', sa.String(200), nullable=True),

        # Socios (QSA)
        sa.Column('socios', JSONB, nullable=True),

        # Simples / MEI
        sa.Column('opcao_pelo_simples', sa.String(5), nullable=True),
        sa.Column('opcao_pelo_mei', sa.String(5), nullable=True),

        # Resposta completa da API
        sa.Column('raw_json', JSONB, nullable=True),

        # Controle
        sa.Column('data_consulta', sa.DateTime(timezone=True), nullable=True),
        sa.Column('erro_ultima_consulta', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id')
    )

    # Indices
    op.create_index('ix_cnpj_cache_cnpj', 'cnpj_cache', ['cnpj'], unique=True)
    op.create_index('ix_cnpj_cache_uf', 'cnpj_cache', ['uf'])
    op.create_index('idx_cnpj_cache_situacao', 'cnpj_cache', ['situacao_cadastral'])

    # Indices GIN trigram para busca fuzzy
    op.execute(
        "CREATE INDEX idx_cnpj_cache_razao_trgm ON cnpj_cache "
        "USING gin (razao_social gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_cnpj_cache_fantasia_trgm ON cnpj_cache "
        "USING gin (nome_fantasia gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX idx_cnpj_cache_municipio_trgm ON cnpj_cache "
        "USING gin (municipio gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_table('cnpj_cache')
