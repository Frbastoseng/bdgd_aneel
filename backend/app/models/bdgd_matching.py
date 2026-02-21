"""Modelos para matching BDGD → CNPJ."""

from datetime import datetime

from sqlalchemy import (
    BigInteger, DateTime, Float, Index, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BdgdCliente(Base):
    """Dados BDGD normalizados para matching."""

    __tablename__ = "bdgd_clientes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cod_id: Mapped[str] = mapped_column(String(70), nullable=False, unique=True, index=True)

    # Endereco original
    lgrd_original: Mapped[str | None] = mapped_column(String(300))
    brr_original: Mapped[str | None] = mapped_column(String(200))
    cep_original: Mapped[str | None] = mapped_column(String(15))
    cnae_original: Mapped[str | None] = mapped_column(String(20))

    # Campos normalizados para matching
    logradouro_norm: Mapped[str | None] = mapped_column(String(300))
    numero_norm: Mapped[str | None] = mapped_column(String(20))
    bairro_norm: Mapped[str | None] = mapped_column(String(200))
    cep_norm: Mapped[str | None] = mapped_column(String(8), index=True)
    cnae_norm: Mapped[str | None] = mapped_column(String(7), index=True)
    cnae_5dig: Mapped[str | None] = mapped_column(String(5), index=True)

    # Localizacao
    mun_code: Mapped[str | None] = mapped_column(String(7))
    municipio_nome: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2), index=True)

    # Coordenadas
    point_x: Mapped[float | None] = mapped_column(Float)
    point_y: Mapped[float | None] = mapped_column(Float)

    # Dados do cliente BDGD
    clas_sub: Mapped[str | None] = mapped_column(String(10))
    gru_tar: Mapped[str | None] = mapped_column(String(10))
    dem_cont: Mapped[float | None] = mapped_column(Float)
    ene_max: Mapped[float | None] = mapped_column(Float)
    liv: Mapped[int | None] = mapped_column(Integer)
    possui_solar: Mapped[bool | None] = mapped_column(default=False)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    __table_args__ = (
        Index("idx_bdgd_cep_cnae", "cep_norm", "cnae_norm"),
        Index("idx_bdgd_municipio", "municipio_nome"),
    )


class BdgdCnpjMatch(Base):
    """Resultado do matching entre clientes BDGD e CNPJs."""

    __tablename__ = "bdgd_cnpj_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bdgd_cod_id: Mapped[str] = mapped_column(String(70), nullable=False, index=True)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, index=True)

    # Score total e por criterio
    score_total: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    score_cep: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    score_cnae: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    score_endereco: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    score_numero: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    score_bairro: Mapped[float] = mapped_column(Numeric(5, 2), default=0)

    # Ranking (1 = melhor match)
    rank: Mapped[int] = mapped_column(Integer, default=1)

    # Dados resumidos do CNPJ (para evitar joins)
    razao_social: Mapped[str | None] = mapped_column(String(200))
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    cnpj_logradouro: Mapped[str | None] = mapped_column(String(200))
    cnpj_numero: Mapped[str | None] = mapped_column(String(20))
    cnpj_bairro: Mapped[str | None] = mapped_column(String(100))
    cnpj_cep: Mapped[str | None] = mapped_column(String(10))
    cnpj_municipio: Mapped[str | None] = mapped_column(String(100))
    cnpj_uf: Mapped[str | None] = mapped_column(String(2))
    cnpj_cnae: Mapped[str | None] = mapped_column(String(10))
    cnpj_cnae_descricao: Mapped[str | None] = mapped_column(String(200))
    cnpj_situacao: Mapped[str | None] = mapped_column(String(50))
    cnpj_telefone: Mapped[str | None] = mapped_column(String(30))
    cnpj_email: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    __table_args__ = (
        Index("idx_match_cod_id_rank", "bdgd_cod_id", "rank"),
        Index("idx_match_score", "score_total"),
    )
