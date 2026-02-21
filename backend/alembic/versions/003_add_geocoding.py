"""Add geocoding support for BDGD matching improvement

Revision ID: 003
Revises: 002
Create Date: 2026-02-21 00:00:00.000000

Adds:
  - geocode_cache table: cache of reverse geocoded coordinates
  - New columns in bdgd_clientes: geocoded address fields
  - New column in bdgd_cnpj_matches: address_source to track which address matched
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tabela de cache de geocodificação reversa ──
    op.create_table(
        'geocode_cache',
        sa.Column('id', sa.BigInteger(), nullable=False, autoincrement=True),
        # Coordenadas arredondadas para agrupar pontos proximos (~11m)
        sa.Column('lat_round', sa.String(12), nullable=False),
        sa.Column('lon_round', sa.String(12), nullable=False),
        sa.Column('lat_original', sa.Float(), nullable=True),
        sa.Column('lon_original', sa.Float(), nullable=True),

        # Endereço retornado pela geocodificação
        sa.Column('logradouro', sa.String(300), nullable=True),
        sa.Column('numero', sa.String(20), nullable=True),
        sa.Column('bairro', sa.String(200), nullable=True),
        sa.Column('cep', sa.String(8), nullable=True),
        sa.Column('municipio', sa.String(100), nullable=True),
        sa.Column('uf', sa.String(2), nullable=True),
        sa.Column('endereco_completo', sa.String(500), nullable=True),

        # Controle
        sa.Column('source', sa.String(20), nullable=False, server_default='nominatim'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error_msg', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),

        sa.PrimaryKeyConstraint('id'),
    )

    # Indice unico por coordenada arredondada
    op.create_index(
        'ix_geocode_cache_coords',
        'geocode_cache',
        ['lat_round', 'lon_round'],
        unique=True,
    )
    op.create_index('ix_geocode_cache_status', 'geocode_cache', ['status'])
    op.create_index('ix_geocode_cache_cep', 'geocode_cache', ['cep'])

    # ── Novos campos em bdgd_clientes ──
    for col_name, col_type in [
        ('geo_logradouro', sa.String(300)),
        ('geo_numero', sa.String(20)),
        ('geo_bairro', sa.String(200)),
        ('geo_cep', sa.String(8)),
        ('geo_municipio', sa.String(100)),
        ('geo_uf', sa.String(2)),
        ('geo_source', sa.String(20)),
        ('geo_status', sa.String(20)),
    ]:
        op.add_column('bdgd_clientes', sa.Column(col_name, col_type, nullable=True))

    op.create_index('idx_bdgd_geo_cep', 'bdgd_clientes', ['geo_cep'])
    op.create_index('idx_bdgd_geo_status', 'bdgd_clientes', ['geo_status'])

    # ── Novo campo em bdgd_cnpj_matches ──
    op.add_column(
        'bdgd_cnpj_matches',
        sa.Column('address_source', sa.String(20), nullable=True, server_default='bdgd'),
    )


def downgrade() -> None:
    op.drop_column('bdgd_cnpj_matches', 'address_source')

    op.drop_index('idx_bdgd_geo_status', table_name='bdgd_clientes')
    op.drop_index('idx_bdgd_geo_cep', table_name='bdgd_clientes')

    for col_name in [
        'geo_logradouro', 'geo_numero', 'geo_bairro', 'geo_cep',
        'geo_municipio', 'geo_uf', 'geo_source', 'geo_status',
    ]:
        op.drop_column('bdgd_clientes', col_name)

    op.drop_table('geocode_cache')
