"""Modelo SQLAlchemy para dados de Geração Distribuída da ANEEL."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GeracaoDistribuida(Base):
    __tablename__ = "geracao_distribuida"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Dados cadastrais
    dth_atualiza_cadastral: Mapped[datetime | None] = mapped_column(DateTime)
    sig_agente: Mapped[str | None] = mapped_column(String(20), index=True)
    nom_agente: Mapped[str | None] = mapped_column(String(200))

    # Localização
    cod_cep: Mapped[str | None] = mapped_column(String(8), index=True)
    sig_uf: Mapped[str | None] = mapped_column(String(2), index=True)
    nom_municipio: Mapped[str | None] = mapped_column(String(200), index=True)
    cod_uf_ibge: Mapped[str | None] = mapped_column(String(2))
    cod_municipio_ibge: Mapped[str | None] = mapped_column(String(7), index=True)

    # Tarifação e consumo
    dsc_sub_grupo_tarifario: Mapped[str | None] = mapped_column(String(10))
    dsc_classe_consumo: Mapped[str | None] = mapped_column(String(100))
    dsc_sub_classe_consumo: Mapped[str | None] = mapped_column(String(100))
    sig_tipo_consumidor: Mapped[str | None] = mapped_column(String(10))

    # Titular
    num_cpf_cnpj: Mapped[str | None] = mapped_column(String(18), index=True)
    nom_titular: Mapped[str | None] = mapped_column(String(300))

    # Empreendimento
    cod_empreendimento: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    dth_conexao_inicial: Mapped[datetime | None] = mapped_column(DateTime)

    # Geração
    sig_tipo_geracao: Mapped[str | None] = mapped_column(String(10), index=True)
    dsc_fonte_geracao: Mapped[str | None] = mapped_column(String(100))
    dsc_porte: Mapped[str | None] = mapped_column(String(50), index=True)
    sig_modalidade: Mapped[str | None] = mapped_column(String(50))
    qtd_modulos: Mapped[int | None] = mapped_column(Integer)

    # Potência
    potencia_instalada_kw: Mapped[float | None] = mapped_column(Numeric(12, 4))
    potencia_fiscalizada_kw: Mapped[float | None] = mapped_column(Numeric(12, 4))
    garantia_fisica_mwm: Mapped[float | None] = mapped_column(Numeric(12, 4))

    # Coordenadas do empreendimento
    coord_n: Mapped[float | None] = mapped_column(Numeric(12, 8))
    coord_e: Mapped[float | None] = mapped_column(Numeric(12, 8))

    # Qualificação
    idc_geracao_qualificada: Mapped[str | None] = mapped_column(String(10))

    # Distribuidora
    num_cnpj_distribuidora: Mapped[str | None] = mapped_column(String(18))
    sig_tipo_consumidor_agg: Mapped[str | None] = mapped_column(String(50))

    # Subestação
    nom_sub_estacao: Mapped[str | None] = mapped_column(String(200))
    coord_n_sub: Mapped[float | None] = mapped_column(Numeric(12, 8))
    coord_e_sub: Mapped[float | None] = mapped_column(Numeric(12, 8))
    potencia_carga: Mapped[float | None] = mapped_column(Numeric(12, 4))

    # ID original do CKAN
    ckan_id: Mapped[int | None] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_gd_uf_municipio", "sig_uf", "nom_municipio"),
        Index("idx_gd_tipo_porte", "sig_tipo_geracao", "dsc_porte"),
        Index("idx_gd_uf_tipo", "sig_uf", "sig_tipo_geracao"),
    )
