"""Cache local de dados CNPJ da Receita Federal."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CnpjCache(Base):
    __tablename__ = "cnpj_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False, unique=True, index=True)

    # Dados principais
    razao_social: Mapped[str | None] = mapped_column(String(200))
    nome_fantasia: Mapped[str | None] = mapped_column(String(200))
    situacao_cadastral: Mapped[str | None] = mapped_column(String(50))
    data_situacao_cadastral: Mapped[str | None] = mapped_column(String(10))
    data_inicio_atividade: Mapped[str | None] = mapped_column(String(10))
    natureza_juridica: Mapped[str | None] = mapped_column(String(200))
    porte: Mapped[str | None] = mapped_column(String(50))
    capital_social: Mapped[float | None] = mapped_column(Numeric(15, 2))

    # CNAE
    cnae_fiscal: Mapped[str | None] = mapped_column(String(10))
    cnae_fiscal_descricao: Mapped[str | None] = mapped_column(String(200))
    cnaes_secundarios: Mapped[dict | None] = mapped_column(JSONB)

    # Endereco
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(200))
    bairro: Mapped[str | None] = mapped_column(String(100))
    municipio: Mapped[str | None] = mapped_column(String(100))
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    cep: Mapped[str | None] = mapped_column(String(10))

    # Contato
    telefone_1: Mapped[str | None] = mapped_column(String(30))
    telefone_2: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))

    # Socios (QSA)
    socios: Mapped[dict | None] = mapped_column(JSONB)

    # Simples / MEI
    opcao_pelo_simples: Mapped[str | None] = mapped_column(String(5))
    opcao_pelo_mei: Mapped[str | None] = mapped_column(String(5))

    # Resposta completa da API (para referencia)
    raw_json: Mapped[dict | None] = mapped_column(JSONB)

    # Controle de atualizacao
    data_consulta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro_ultima_consulta: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_cnpj_cache_situacao", "situacao_cadastral"),
    )
