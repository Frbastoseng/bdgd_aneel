"""Schemas Pydantic para Geração Distribuída."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class GDBase(BaseModel):
    """Campos base de um empreendimento GD."""
    sig_agente: Optional[str] = None
    nom_agente: Optional[str] = None
    cod_cep: Optional[str] = None
    sig_uf: Optional[str] = None
    nom_municipio: Optional[str] = None
    cod_municipio_ibge: Optional[str] = None
    dsc_sub_grupo_tarifario: Optional[str] = None
    dsc_classe_consumo: Optional[str] = None
    sig_tipo_consumidor: Optional[str] = None
    num_cpf_cnpj: Optional[str] = None
    nom_titular: Optional[str] = None
    cod_empreendimento: Optional[str] = None
    dth_conexao_inicial: Optional[datetime] = None
    sig_tipo_geracao: Optional[str] = None
    dsc_fonte_geracao: Optional[str] = None
    dsc_porte: Optional[str] = None
    sig_modalidade: Optional[str] = None
    qtd_modulos: Optional[int] = None
    potencia_instalada_kw: Optional[float] = None
    potencia_fiscalizada_kw: Optional[float] = None
    coord_n: Optional[float] = None
    coord_e: Optional[float] = None
    nom_sub_estacao: Optional[str] = None


class GDResponse(GDBase):
    """Resposta da API com todos os campos."""
    id: int
    dth_atualiza_cadastral: Optional[datetime] = None
    cod_uf_ibge: Optional[str] = None
    dsc_sub_classe_consumo: Optional[str] = None
    garantia_fisica_mwm: Optional[float] = None
    idc_geracao_qualificada: Optional[str] = None
    num_cnpj_distribuidora: Optional[str] = None
    sig_tipo_consumidor_agg: Optional[str] = None
    coord_n_sub: Optional[float] = None
    coord_e_sub: Optional[float] = None
    potencia_carga: Optional[float] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GDListResponse(BaseModel):
    """Resposta paginada de listagem."""
    items: List[GDResponse]
    total: int
    page: int
    per_page: int
    pages: int


class GDStatsUF(BaseModel):
    """Estatísticas por UF."""
    uf: str
    total: int
    potencia_total_kw: float


class GDStatsTipo(BaseModel):
    """Estatísticas por tipo de geração."""
    tipo: str
    total: int
    potencia_total_kw: float


class GDStatsPorte(BaseModel):
    """Estatísticas por porte."""
    porte: str
    total: int


class GDStats(BaseModel):
    """Estatísticas gerais de GD."""
    total_empreendimentos: int
    potencia_total_instalada_kw: float
    por_uf: List[GDStatsUF]
    por_tipo_geracao: List[GDStatsTipo]
    por_porte: List[GDStatsPorte]


class GDStatsUFDetail(BaseModel):
    """Estatísticas detalhadas de uma UF."""
    uf: str
    total_empreendimentos: int
    potencia_total_instalada_kw: float
    por_tipo_geracao: List[GDStatsTipo]
    por_porte: List[GDStatsPorte]
    por_municipio: List[Dict[str, Any]]


class MunicipioItem(BaseModel):
    """Item de município para autocomplete."""
    nom_municipio: str
    sig_uf: str
    total: int
