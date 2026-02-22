"""Criar tabela geracao_distribuida

Revision ID: 001
Revises:
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'geracao_distribuida',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        # Dados cadastrais
        sa.Column('dth_atualiza_cadastral', sa.DateTime(), nullable=True),
        sa.Column('sig_agente', sa.String(20), nullable=True),
        sa.Column('nom_agente', sa.String(200), nullable=True),
        # Localização
        sa.Column('cod_cep', sa.String(8), nullable=True),
        sa.Column('sig_uf', sa.String(2), nullable=True),
        sa.Column('nom_municipio', sa.String(200), nullable=True),
        sa.Column('cod_uf_ibge', sa.String(2), nullable=True),
        sa.Column('cod_municipio_ibge', sa.String(7), nullable=True),
        # Tarifação e consumo
        sa.Column('dsc_sub_grupo_tarifario', sa.String(10), nullable=True),
        sa.Column('dsc_classe_consumo', sa.String(100), nullable=True),
        sa.Column('dsc_sub_classe_consumo', sa.String(100), nullable=True),
        sa.Column('sig_tipo_consumidor', sa.String(10), nullable=True),
        # Titular
        sa.Column('num_cpf_cnpj', sa.String(18), nullable=True),
        sa.Column('nom_titular', sa.String(300), nullable=True),
        # Empreendimento
        sa.Column('cod_empreendimento', sa.String(50), nullable=True),
        sa.Column('dth_conexao_inicial', sa.DateTime(), nullable=True),
        # Geração
        sa.Column('sig_tipo_geracao', sa.String(10), nullable=True),
        sa.Column('dsc_fonte_geracao', sa.String(100), nullable=True),
        sa.Column('dsc_porte', sa.String(50), nullable=True),
        sa.Column('sig_modalidade', sa.String(50), nullable=True),
        sa.Column('qtd_modulos', sa.Integer(), nullable=True),
        # Potência
        sa.Column('potencia_instalada_kw', sa.Numeric(12, 4), nullable=True),
        sa.Column('potencia_fiscalizada_kw', sa.Numeric(12, 4), nullable=True),
        sa.Column('garantia_fisica_mwm', sa.Numeric(12, 4), nullable=True),
        # Coordenadas
        sa.Column('coord_n', sa.Numeric(12, 8), nullable=True),
        sa.Column('coord_e', sa.Numeric(12, 8), nullable=True),
        # Qualificação
        sa.Column('idc_geracao_qualificada', sa.String(10), nullable=True),
        # Distribuidora
        sa.Column('num_cnpj_distribuidora', sa.String(18), nullable=True),
        sa.Column('sig_tipo_consumidor_agg', sa.String(50), nullable=True),
        # Subestação
        sa.Column('nom_sub_estacao', sa.String(200), nullable=True),
        sa.Column('coord_n_sub', sa.Numeric(12, 8), nullable=True),
        sa.Column('coord_e_sub', sa.Numeric(12, 8), nullable=True),
        sa.Column('potencia_carga', sa.Numeric(12, 4), nullable=True),
        # CKAN
        sa.Column('ckan_id', sa.Integer(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cod_empreendimento'),
    )

    # Indexes individuais
    op.create_index('idx_gd_sig_agente', 'geracao_distribuida', ['sig_agente'])
    op.create_index('idx_gd_cod_cep', 'geracao_distribuida', ['cod_cep'])
    op.create_index('idx_gd_sig_uf', 'geracao_distribuida', ['sig_uf'])
    op.create_index('idx_gd_nom_municipio', 'geracao_distribuida', ['nom_municipio'])
    op.create_index('idx_gd_cod_municipio_ibge', 'geracao_distribuida', ['cod_municipio_ibge'])
    op.create_index('idx_gd_num_cpf_cnpj', 'geracao_distribuida', ['num_cpf_cnpj'])
    op.create_index('idx_gd_cod_empreendimento', 'geracao_distribuida', ['cod_empreendimento'])
    op.create_index('idx_gd_sig_tipo_geracao', 'geracao_distribuida', ['sig_tipo_geracao'])
    op.create_index('idx_gd_dsc_porte', 'geracao_distribuida', ['dsc_porte'])

    # Indexes compostos
    op.create_index('idx_gd_uf_municipio', 'geracao_distribuida', ['sig_uf', 'nom_municipio'])
    op.create_index('idx_gd_tipo_porte', 'geracao_distribuida', ['sig_tipo_geracao', 'dsc_porte'])
    op.create_index('idx_gd_uf_tipo', 'geracao_distribuida', ['sig_uf', 'sig_tipo_geracao'])


def downgrade() -> None:
    op.drop_table('geracao_distribuida')
