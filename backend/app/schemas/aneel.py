"""
Schemas para dados da ANEEL (BDGD e Tarifas)
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============ Schemas de Filtros ============

class FiltroConsulta(BaseModel):
    """Filtros para consulta de dados ANEEL"""
    uf: Optional[str] = Field(None, description="Sigla do estado")
    municipios: Optional[List[str]] = Field(None, description="Lista de códigos de municípios")
    microrregioes: Optional[List[str]] = Field(None, description="Lista de microrregiões")
    mesorregioes: Optional[List[str]] = Field(None, description="Lista de mesorregiões")
    
    # Filtros avançados
    possui_solar: Optional[bool] = Field(None, description="Possui geração solar (CEG_GD)")
    classes_cliente: Optional[List[str]] = Field(None, description="Classes de cliente (CLAS_SUB)")
    grupos_tarifarios: Optional[List[str]] = Field(None, description="Grupos tarifários")
    tipo_consumidor: Optional[str] = Field(None, description="Livre ou Cativo")
    
    # Filtros numéricos
    demanda_min: Optional[float] = Field(None, description="Demanda contratada mínima")
    demanda_max: Optional[float] = Field(None, description="Demanda contratada máxima")
    energia_max_min: Optional[float] = Field(None, description="Energia máxima mensal mínima")
    energia_max_max: Optional[float] = Field(None, description="Energia máxima mensal máxima")
    
    # Paginação
    page: int = Field(1, ge=1)
    per_page: int = Field(100, ge=1, le=1000)


class FiltroTarifas(BaseModel):
    """Filtros para consulta de tarifas"""
    distribuidora: Optional[str] = None
    subgrupo: Optional[str] = None
    modalidade: Optional[str] = None
    detalhe: Optional[str] = None
    apenas_ultima_tarifa: bool = False


# ============ Schemas de Resposta ============

class ClienteANEEL(BaseModel):
    """Dados de um cliente/unidade consumidora"""
    id: Optional[int] = None
    cod_id: Optional[str] = None
    mun: Optional[str] = None
    nome_uf: Optional[str] = None
    nome_municipio: Optional[str] = None
    
    # Classificação
    clas_sub: Optional[str] = None
    clas_sub_descricao: Optional[str] = None
    gru_tar: Optional[str] = None
    
    # Consumidor livre/cativo
    liv: Optional[int] = None
    
    # Demanda e carga
    dem_cont: Optional[float] = None
    car_inst: Optional[float] = None
    
    # Demandas mensais
    dem_01: Optional[float] = None
    dem_02: Optional[float] = None
    dem_03: Optional[float] = None
    dem_04: Optional[float] = None
    dem_05: Optional[float] = None
    dem_06: Optional[float] = None
    dem_07: Optional[float] = None
    dem_08: Optional[float] = None
    dem_09: Optional[float] = None
    dem_10: Optional[float] = None
    dem_11: Optional[float] = None
    dem_12: Optional[float] = None
    
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
    ene_max: Optional[float] = None
    
    # Indicadores de qualidade
    dic_01: Optional[float] = None
    dic_02: Optional[float] = None
    fic_01: Optional[float] = None
    fic_02: Optional[float] = None
    
    # Geração distribuída
    ceg_gd: Optional[str] = None
    possui_solar: bool = False
    
    # Coordenadas
    point_x: Optional[float] = None
    point_y: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    class Config:
        from_attributes = True


class ConsultaResponse(BaseModel):
    """Resposta de consulta de dados"""
    dados: List[ClienteANEEL]
    total: int
    page: int
    per_page: int
    total_pages: int
    
    # Estatísticas
    estatisticas: Optional[Dict[str, Any]] = None


class TarifaANEEL(BaseModel):
    """Dados de uma tarifa"""
    id: Optional[int] = None
    sig_agente: Optional[str] = None
    dsc_reh: Optional[str] = None
    nom_posto_tarifario: Optional[str] = None
    dsc_unidade_terciaria: Optional[str] = None
    vlr_tusd: Optional[float] = None
    vlr_te: Optional[float] = None
    dat_fim_vigencia: Optional[datetime] = None
    dsc_sub_grupo: Optional[str] = None
    dsc_modalidade_tarifaria: Optional[str] = None
    dsc_detalhe: Optional[str] = None


class TarifasResponse(BaseModel):
    """Resposta de consulta de tarifas"""
    tarifas: List[TarifaANEEL]
    total: int


# ============ Schemas de Localidades ============

class UF(BaseModel):
    """Estado"""
    sigla: str
    nome: str


class Municipio(BaseModel):
    """Município"""
    codigo: str
    nome: str
    uf: str
    microrregiao: Optional[str] = None
    mesorregiao: Optional[str] = None


class LocalidadesResponse(BaseModel):
    """Resposta de localidades disponíveis"""
    ufs: List[UF]
    municipios: Optional[List[Municipio]] = None
    microrregioes: Optional[List[str]] = None
    mesorregioes: Optional[List[str]] = None


# ============ Schemas de Mapa ============

class PontoMapa(BaseModel):
    """Ponto para exibição no mapa"""
    id: str
    latitude: float
    longitude: float
    titulo: str
    descricao: Optional[str] = None
    tipo: Optional[str] = None
    dados: Optional[Dict[str, Any]] = None


class MapaResponse(BaseModel):
    """Resposta de dados para mapa"""
    pontos: List[PontoMapa]
    centro: Dict[str, float]
    zoom: int = 10


# ============ Schemas de Exportação ============

class ExportRequest(BaseModel):
    """Request para exportação de dados"""
    formato: str = Field(..., description="csv, xlsx ou kml")
    filtros: FiltroConsulta


class ExportResponse(BaseModel):
    """Resposta de exportação"""
    download_url: str
    filename: str
    expires_at: datetime


# ============ Schemas de Estatísticas ============

class EstatisticasGerais(BaseModel):
    """Estatísticas gerais dos dados"""
    total_clientes: int
    total_municipios: int
    total_ufs: int
    clientes_com_solar: int
    demanda_total: float
    energia_total: float


class EstatisticasPorClasse(BaseModel):
    """Estatísticas por classe de cliente"""
    classe: str
    quantidade: int
    percentual: float
    demanda_media: float
    energia_media: float


# ============ Schemas para Mapa Avançado ============

class AreaSelecao(BaseModel):
    """Área de seleção para exportação de pontos"""
    bounds: Dict[str, float] = Field(..., description="Limites da área: north, south, east, west")
    
class PontoMapaCompleto(BaseModel):
    """Ponto no mapa com informações completas para tooltip"""
    id: str
    latitude: float
    longitude: float
    cod_id: Optional[str] = None
    titulo: Optional[str] = None
    
    # Informações básicas
    tipo_consumidor: str  # "livre" ou "cativo"
    classe: Optional[str] = None
    grupo_tarifario: Optional[str] = None
    
    # Localização
    municipio: Optional[str] = None
    uf: Optional[str] = None
    
    # Dados de consumo
    demanda: Optional[float] = None  # Alias para frontend
    demanda_contratada: Optional[float] = None
    consumo_medio: Optional[float] = None
    consumo_max: Optional[float] = None
    carga_instalada: Optional[float] = None
    
    # Solar
    possui_solar: bool = False
    
    # Para clustering
    cluster_id: Optional[int] = None


class MapaAvancadoResponse(BaseModel):
    """Resposta do mapa avançado com pontos completos"""
    pontos: List[PontoMapaCompleto]
    total: int
    centro: Dict[str, float]
    zoom: int
    estatisticas: Optional[Dict[str, Any]] = None


class ExportarSelecaoRequest(BaseModel):
    """Request para exportar dados de uma seleção"""
    bounds: Dict[str, float] = Field(..., description="north, south, east, west")
    filtros: Optional[Dict[str, Any]] = None
    formato: str = Field("xlsx", description="xlsx ou csv")


# ============ Schemas para Consultas Salvas ============

class SavedQueryCreate(BaseModel):
    """Criar consulta salva"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    filters: Dict[str, Any]
    query_type: str = Field("consulta", description="consulta, mapa, tarifas")


class SavedQueryUpdate(BaseModel):
    """Atualizar consulta salva"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class SavedQueryResponse(BaseModel):
    """Resposta de consulta salva"""
    id: int
    name: str
    description: Optional[str] = None
    filters: Dict[str, Any]
    query_type: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    use_count: int = 0


# ============ Mapeamentos ============

CLAS_SUB_MAP = {
    "0": "Não informado",
    "RE1": "Residencial",
    "RE2": "Residencial baixa renda",
    "REBR": "Residencial baixa renda indígena",
    "REQU": "Residencial baixa renda quilombola",
    "REBP": "Residencial baixa renda benefício de prestação continuada da assistência social – BPC",
    "REMU": "Residencial baixa renda multifamiliar",
    "IN": "Industrial",
    "CO1": "Comercial",
    "CO2": "Serviços de transporte, exceto tração elétrica",
    "CO3": "Serviços de comunicações e telecomunicações",
    "CO4": "Associação e entidades filantrópicas",
    "CO5": "Templos religiosos",
    "CO6": "Administração condominial: iluminação e instalações de uso comum de prédio ou conjunto de edificações",
    "CO7": "Iluminação em rodovias",
    "CO8": "Semáforos, radares e câmeras de monitoramento de trânsito",
    "CO9": "Outros serviços e outras atividades",
    "RU1": "Agropecuária rural",
    "RU1A": "Agropecuária rural (poços de captação de água)",
    "RU1B": "Agropecuária rural (bombeamento de água)",
    "RU2": "Agropecuária urbana",
    "RU3": "Residencial rural",
    "RU4": "Cooperativa de eletrificação rural",
    "RU5": "Agroindustrial",
    "RU6": "Serviço público de irrigação rural",
    "RU7": "Escola agrotécnica",
    "RU8": "Aquicultura",
    "PP1": "Poder público federal",
    "PP2": "Poder público estadual ou distrital",
    "PP3": "Poder público municipal",
    "IP": "Iluminação pública",
    "SP1": "Tração elétrica",
    "SP2": "Água, esgoto e saneamento",
    "CPR": "Consumo próprio pela distribuidora",
    "CSPS": "Concessionária ou Permissionária"
}
