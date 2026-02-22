"""
Schemas para dados BDGD B3 (Baixa Tensão)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


# ============ Schemas de Filtros ============

class FiltroB3(BaseModel):
    """Filtros para consulta de dados B3"""
    # Localização
    uf: Optional[str] = Field(None, description="Sigla do estado")
    municipios: Optional[List[str]] = Field(None, description="Lista de nomes de municípios")

    # Classificação
    classes_cliente: Optional[List[str]] = Field(None, description="Classes de cliente (CLAS_SUB)")
    grupos_tarifarios: Optional[List[str]] = Field(None, description="Grupos tarifários")
    fas_con: Optional[str] = Field(None, description="Fase de conexão (A, AB, ABC)")
    sit_ativ: Optional[str] = Field(None, description="Situação (AT=Ativo, DS=Desativado)")
    area_loc: Optional[str] = Field(None, description="Área (UR=Urbana, NU=Não Urbana)")
    possui_solar: Optional[bool] = Field(None, description="Possui geração solar")

    # Filtros de texto
    cnae: Optional[str] = Field(None, description="CNAE (busca parcial)")
    cep: Optional[str] = Field(None, description="CEP (busca por prefixo)")
    bairro: Optional[str] = Field(None, description="Bairro (busca parcial)")
    logradouro: Optional[str] = Field(None, description="Logradouro (busca parcial)")

    # Ranges numéricos
    consumo_medio_min: Optional[float] = Field(None, description="Consumo médio mensal mínimo (kWh)")
    consumo_medio_max: Optional[float] = Field(None, description="Consumo médio mensal máximo (kWh)")
    consumo_anual_min: Optional[float] = Field(None, description="Consumo anual mínimo (kWh)")
    consumo_anual_max: Optional[float] = Field(None, description="Consumo anual máximo (kWh)")
    car_inst_min: Optional[float] = Field(None, description="Carga instalada mínima (kW)")
    car_inst_max: Optional[float] = Field(None, description="Carga instalada máxima (kW)")
    dic_anual_min: Optional[float] = Field(None, description="DIC anual mínimo")
    dic_anual_max: Optional[float] = Field(None, description="DIC anual máximo")
    fic_anual_min: Optional[float] = Field(None, description="FIC anual mínimo")
    fic_anual_max: Optional[float] = Field(None, description="FIC anual máximo")

    # Paginação
    page: int = Field(1, ge=1)
    per_page: int = Field(100, ge=1, le=1000)


# ============ Schemas de Resposta ============

class ClienteB3(BaseModel):
    """Dados de um cliente/unidade consumidora B3"""
    cod_id: Optional[str] = None
    dist: Optional[str] = None
    pac: Optional[str] = None
    mun: Optional[str] = None
    nome_uf: Optional[str] = None
    nome_municipio: Optional[str] = None
    lgrd: Optional[str] = None
    brr: Optional[str] = None
    cep: Optional[str] = None

    # Classificação
    clas_sub: Optional[str] = None
    clas_sub_descricao: Optional[str] = None
    cnae: Optional[str] = None
    fas_con: Optional[str] = None
    gru_ten: Optional[str] = None
    gru_tar: Optional[str] = None
    sit_ativ: Optional[str] = None
    area_loc: Optional[str] = None
    tip_cc: Optional[str] = None

    # Carga e consumo
    car_inst: Optional[float] = None
    consumo_anual: Optional[float] = None
    consumo_medio: Optional[float] = None
    ene_max: Optional[float] = None

    # Energias mensais
    ene_01: Optional[float] = None
    ene_02: Optional[float] = None
    ene_03: Optional[float] = None
    ene_04: Optional[float] = None
    ene_05: Optional[float] = None
    ene_06: Optional[float] = None
    ene_07: Optional[float] = None
    ene_08: Optional[float] = None
    ene_09: Optional[float] = None
    ene_10: Optional[float] = None
    ene_11: Optional[float] = None
    ene_12: Optional[float] = None

    # DIC mensais
    dic_01: Optional[float] = None
    dic_02: Optional[float] = None
    dic_03: Optional[float] = None
    dic_04: Optional[float] = None
    dic_05: Optional[float] = None
    dic_06: Optional[float] = None
    dic_07: Optional[float] = None
    dic_08: Optional[float] = None
    dic_09: Optional[float] = None
    dic_10: Optional[float] = None
    dic_11: Optional[float] = None
    dic_12: Optional[float] = None
    dic_anual: Optional[float] = None

    # FIC mensais
    fic_01: Optional[float] = None
    fic_02: Optional[float] = None
    fic_03: Optional[float] = None
    fic_04: Optional[float] = None
    fic_05: Optional[float] = None
    fic_06: Optional[float] = None
    fic_07: Optional[float] = None
    fic_08: Optional[float] = None
    fic_09: Optional[float] = None
    fic_10: Optional[float] = None
    fic_11: Optional[float] = None
    fic_12: Optional[float] = None
    fic_anual: Optional[float] = None

    # Geração distribuída
    ceg_gd: Optional[str] = None
    possui_solar: bool = False
    geracao_distribuida: Optional[Dict[str, Any]] = None
    nome_real: Optional[str] = None
    cnpj_real: Optional[str] = None

    # Coordenadas
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Data
    dat_con: Optional[str] = None

    class Config:
        from_attributes = True


class ConsultaB3Response(BaseModel):
    """Resposta de consulta de dados B3"""
    dados: List[ClienteB3]
    total: int
    page: int
    per_page: int
    total_pages: int
    estatisticas: Optional[Dict[str, Any]] = None


# ============ Schemas de Mapa ============

class PontoMapaB3(BaseModel):
    """Ponto no mapa B3 com informações completas para tooltip"""
    id: str
    latitude: float
    longitude: float
    cod_id: Optional[str] = None
    titulo: Optional[str] = None

    # Informações básicas
    classe: Optional[str] = None
    grupo_tarifario: Optional[str] = None
    fas_con: Optional[str] = None

    # Localização
    municipio: Optional[str] = None
    uf: Optional[str] = None

    # Dados de consumo
    consumo_medio: Optional[float] = None
    consumo_anual: Optional[float] = None
    carga_instalada: Optional[float] = None
    dic_anual: Optional[float] = None
    fic_anual: Optional[float] = None

    # Solar
    possui_solar: bool = False

    # Para clustering
    cluster_id: Optional[int] = None


class MapaB3Response(BaseModel):
    """Resposta do mapa B3"""
    pontos: List[PontoMapaB3]
    total: int
    centro: Dict[str, float]
    zoom: int
    estatisticas: Optional[Dict[str, Any]] = None


class ExportarSelecaoB3Request(BaseModel):
    """Request para exportar dados de uma seleção no mapa B3"""
    bounds: Dict[str, float] = Field(..., description="north, south, east, west")
    filtros: Optional[Dict[str, Any]] = None
    formato: str = Field("xlsx", description="xlsx ou csv")


# ============ Mapeamentos ============

CLAS_SUB_B3_MAP = {
    "CO1": "Comercial",
    "CO2": "Serviços de transporte",
    "CO3": "Serviços de comunicações",
    "CO4": "Associação/filantrópicas",
    "CO5": "Templos religiosos",
    "CO6": "Adm. condominial",
    "CO7": "Iluminação rodovias",
    "CO8": "Semáforos/câmeras",
    "CO9": "Outros serviços",
    "IN1": "Industrial pequeno",
    "IN2": "Industrial médio",
    "IN3": "Industrial grande",
    "RU1": "Agropecuária rural",
    "RU2": "Agropecuária urbana",
    "RU3": "Residencial rural",
    "PP1": "Poder público federal",
    "PP2": "Poder público estadual",
    "PP3": "Poder público municipal",
    "IP1": "Iluminação pública",
    "SE1": "Serviço público",
    "RE1": "Residencial",
    "RE2": "Residencial baixa renda",
    "SP1": "Tração elétrica",
    "SP2": "Água/esgoto/saneamento",
}

FAS_CON_MAP = {
    "A": "Monofásico",
    "AB": "Bifásico",
    "ABC": "Trifásico",
}

SIT_ATIV_MAP = {
    "AT": "Ativo",
    "DS": "Desativado",
}

AREA_LOC_MAP = {
    "UR": "Urbana",
    "NU": "Não Urbana",
}
