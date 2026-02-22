"""Criar tabelas de dados técnicos das usinas GD

Revision ID: 002
Revises: 001
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Solar (UFV) ──────────────────────────────────────────────
    op.create_table(
        'gd_tecnico_solar',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cod_geracao_distribuida', sa.String(50), nullable=True),
        sa.Column('mda_area_arranjo', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_potencia_instalada', sa.Numeric(12, 4), nullable=True),
        sa.Column('nom_fabricante_modulo', sa.String(200), nullable=True),
        sa.Column('nom_modelo_modulo', sa.String(200), nullable=True),
        sa.Column('nom_fabricante_inversor', sa.String(200), nullable=True),
        sa.Column('nom_modelo_inversor', sa.String(200), nullable=True),
        sa.Column('qtd_modulos', sa.Integer(), nullable=True),
        sa.Column('mda_potencia_modulos', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_potencia_inversores', sa.Numeric(12, 4), nullable=True),
        sa.Column('dat_conexao', sa.DateTime(), nullable=True),
        sa.Column('ckan_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cod_geracao_distribuida'),
    )
    op.create_index('idx_solar_cod_gd', 'gd_tecnico_solar', ['cod_geracao_distribuida'])
    op.create_index('idx_solar_fabricante_modulo', 'gd_tecnico_solar', ['nom_fabricante_modulo'])
    op.create_index('idx_solar_fabricante_inversor', 'gd_tecnico_solar', ['nom_fabricante_inversor'])

    # ── Eólica (EOL) ────────────────────────────────────────────
    op.create_table(
        'gd_tecnico_eolica',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cod_geracao_distribuida', sa.String(50), nullable=True),
        sa.Column('nom_fabricante_aerogerador', sa.String(200), nullable=True),
        sa.Column('dsc_modelo_aerogerador', sa.String(200), nullable=True),
        sa.Column('mda_potencia_instalada', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_altura_pa', sa.Numeric(12, 4), nullable=True),
        sa.Column('idc_eixo_rotor', sa.String(50), nullable=True),
        sa.Column('dat_conexao', sa.DateTime(), nullable=True),
        sa.Column('ckan_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cod_geracao_distribuida'),
    )
    op.create_index('idx_eolica_cod_gd', 'gd_tecnico_eolica', ['cod_geracao_distribuida'])

    # ── Hidráulica (CGH) ────────────────────────────────────────
    op.create_table(
        'gd_tecnico_hidraulica',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cod_geracao_distribuida', sa.String(50), nullable=True),
        sa.Column('nom_rio', sa.String(200), nullable=True),
        sa.Column('mda_potencia_instalada', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_potencia_aparente', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_fator_potencia', sa.Numeric(8, 4), nullable=True),
        sa.Column('mda_tensao', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_nivel_operacional_montante', sa.Numeric(12, 4), nullable=True),
        sa.Column('mda_nivel_operacional_jusante', sa.Numeric(12, 4), nullable=True),
        sa.Column('dat_conexao', sa.DateTime(), nullable=True),
        sa.Column('ckan_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cod_geracao_distribuida'),
    )
    op.create_index('idx_hidraulica_cod_gd', 'gd_tecnico_hidraulica', ['cod_geracao_distribuida'])

    # ── Térmica (UTE) ───────────────────────────────────────────
    op.create_table(
        'gd_tecnico_termica',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('cod_geracao_distribuida', sa.String(50), nullable=True),
        sa.Column('mda_potencia_instalada', sa.Numeric(12, 4), nullable=True),
        sa.Column('dat_conexao', sa.DateTime(), nullable=True),
        sa.Column('dsc_ciclo_termodinamico', sa.String(100), nullable=True),
        sa.Column('dsc_maquina_motriz', sa.String(100), nullable=True),
        sa.Column('ckan_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cod_geracao_distribuida'),
    )
    op.create_index('idx_termica_cod_gd', 'gd_tecnico_termica', ['cod_geracao_distribuida'])


def downgrade() -> None:
    op.drop_table('gd_tecnico_termica')
    op.drop_table('gd_tecnico_hidraulica')
    op.drop_table('gd_tecnico_eolica')
    op.drop_table('gd_tecnico_solar')
