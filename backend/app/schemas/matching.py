"""Schemas para matching BDGD -> CNPJ."""

from pydantic import BaseModel


class MatchItem(BaseModel):
    """Um resultado de matching CNPJ para um cliente BDGD."""
    cnpj: str
    rank: int
    score_total: float
    score_cep: float
    score_cnae: float
    score_endereco: float
    score_numero: float
    score_bairro: float
    razao_social: str | None = None
    nome_fantasia: str | None = None
    cnpj_logradouro: str | None = None
    cnpj_numero: str | None = None
    cnpj_bairro: str | None = None
    cnpj_cep: str | None = None
    cnpj_municipio: str | None = None
    cnpj_uf: str | None = None
    cnpj_cnae: str | None = None
    cnpj_cnae_descricao: str | None = None
    cnpj_situacao: str | None = None
    cnpj_telefone: str | None = None
    cnpj_email: str | None = None
    address_source: str | None = "bdgd"  # 'bdgd' ou 'geocoded'


class BdgdClienteComMatch(BaseModel):
    """Cliente BDGD com seus matches."""
    cod_id: str
    lgrd_original: str | None = None
    brr_original: str | None = None
    cep_original: str | None = None
    cnae_original: str | None = None
    municipio_nome: str | None = None
    uf: str | None = None
    clas_sub: str | None = None
    gru_tar: str | None = None
    dem_cont: float | None = None
    ene_max: float | None = None
    liv: int | None = None
    possui_solar: bool = False
    point_x: float | None = None
    point_y: float | None = None
    # Endereço geocodificado (via coordenadas)
    geo_logradouro: str | None = None
    geo_bairro: str | None = None
    geo_cep: str | None = None
    geo_municipio: str | None = None
    geo_uf: str | None = None
    matches: list[MatchItem] = []
    best_score: float | None = None


class MatchingPaginated(BaseModel):
    """Resposta paginada de matching."""
    data: list[BdgdClienteComMatch]
    total: int
    page: int
    per_page: int


class MatchingStats(BaseModel):
    """Estatisticas do matching."""
    total_clientes: int
    clientes_com_match: int
    clientes_sem_match: int
    avg_score_top1: float | None = None
    alta_confianca: int  # score >= 75
    media_confianca: int  # 50-74
    baixa_confianca: int  # 15-49
    total_matches: int
    via_geocode: int = 0  # matches melhorados pela geocodificação
