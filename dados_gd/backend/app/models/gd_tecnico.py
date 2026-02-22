"""Modelos SQLAlchemy para dados técnicos das usinas GD."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GDTecnicoSolar(Base):
    __tablename__ = "gd_tecnico_solar"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cod_geracao_distribuida: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    mda_area_arranjo: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_potencia_instalada: Mapped[float | None] = mapped_column(Numeric(12, 4))
    nom_fabricante_modulo: Mapped[str | None] = mapped_column(String(200), index=True)
    nom_modelo_modulo: Mapped[str | None] = mapped_column(String(200))
    nom_fabricante_inversor: Mapped[str | None] = mapped_column(String(200), index=True)
    nom_modelo_inversor: Mapped[str | None] = mapped_column(String(200))
    qtd_modulos: Mapped[int | None] = mapped_column(Integer)
    mda_potencia_modulos: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_potencia_inversores: Mapped[float | None] = mapped_column(Numeric(12, 4))
    dat_conexao: Mapped[datetime | None] = mapped_column(DateTime)
    ckan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )


class GDTecnicoEolica(Base):
    __tablename__ = "gd_tecnico_eolica"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cod_geracao_distribuida: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    nom_fabricante_aerogerador: Mapped[str | None] = mapped_column(String(200))
    dsc_modelo_aerogerador: Mapped[str | None] = mapped_column(String(200))
    mda_potencia_instalada: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_altura_pa: Mapped[float | None] = mapped_column(Numeric(12, 4))
    idc_eixo_rotor: Mapped[str | None] = mapped_column(String(50))
    dat_conexao: Mapped[datetime | None] = mapped_column(DateTime)
    ckan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )


class GDTecnicoHidraulica(Base):
    __tablename__ = "gd_tecnico_hidraulica"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cod_geracao_distribuida: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    nom_rio: Mapped[str | None] = mapped_column(String(200))
    mda_potencia_instalada: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_potencia_aparente: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_fator_potencia: Mapped[float | None] = mapped_column(Numeric(8, 4))
    mda_tensao: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_nivel_operacional_montante: Mapped[float | None] = mapped_column(Numeric(12, 4))
    mda_nivel_operacional_jusante: Mapped[float | None] = mapped_column(Numeric(12, 4))
    dat_conexao: Mapped[datetime | None] = mapped_column(DateTime)
    ckan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )


class GDTecnicoTermica(Base):
    __tablename__ = "gd_tecnico_termica"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    cod_geracao_distribuida: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    mda_potencia_instalada: Mapped[float | None] = mapped_column(Numeric(12, 4))
    dat_conexao: Mapped[datetime | None] = mapped_column(DateTime)
    dsc_ciclo_termodinamico: Mapped[str | None] = mapped_column(String(100))
    dsc_maquina_motriz: Mapped[str | None] = mapped_column(String(100))
    ckan_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()", onupdate=datetime.utcnow
    )
