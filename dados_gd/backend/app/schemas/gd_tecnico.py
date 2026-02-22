"""Schemas Pydantic para dados técnicos das usinas GD."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class TecnicoSolarResponse(BaseModel):
    cod_geracao_distribuida: str
    mda_area_arranjo: Optional[float] = None
    mda_potencia_instalada: Optional[float] = None
    nom_fabricante_modulo: Optional[str] = None
    nom_modelo_modulo: Optional[str] = None
    nom_fabricante_inversor: Optional[str] = None
    nom_modelo_inversor: Optional[str] = None
    qtd_modulos: Optional[int] = None
    mda_potencia_modulos: Optional[float] = None
    mda_potencia_inversores: Optional[float] = None
    dat_conexao: Optional[datetime] = None

    class Config:
        from_attributes = True


class TecnicoEolicaResponse(BaseModel):
    cod_geracao_distribuida: str
    nom_fabricante_aerogerador: Optional[str] = None
    dsc_modelo_aerogerador: Optional[str] = None
    mda_potencia_instalada: Optional[float] = None
    mda_altura_pa: Optional[float] = None
    idc_eixo_rotor: Optional[str] = None
    dat_conexao: Optional[datetime] = None

    class Config:
        from_attributes = True


class TecnicoHidraulicaResponse(BaseModel):
    cod_geracao_distribuida: str
    nom_rio: Optional[str] = None
    mda_potencia_instalada: Optional[float] = None
    mda_potencia_aparente: Optional[float] = None
    mda_fator_potencia: Optional[float] = None
    mda_tensao: Optional[float] = None
    mda_nivel_operacional_montante: Optional[float] = None
    mda_nivel_operacional_jusante: Optional[float] = None
    dat_conexao: Optional[datetime] = None

    class Config:
        from_attributes = True


class TecnicoTermicaResponse(BaseModel):
    cod_geracao_distribuida: str
    mda_potencia_instalada: Optional[float] = None
    dat_conexao: Optional[datetime] = None
    dsc_ciclo_termodinamico: Optional[str] = None
    dsc_maquina_motriz: Optional[str] = None

    class Config:
        from_attributes = True


class DadosTecnicosResponse(BaseModel):
    """Wrapper unificado: identifica o tipo e retorna os dados específicos."""
    tipo: str
    dados: Dict[str, Any]
