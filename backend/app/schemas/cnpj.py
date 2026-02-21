"""Schemas para consulta e cache de CNPJ."""

from datetime import datetime

from pydantic import BaseModel


class SocioInfo(BaseModel):
    nome: str
    qualificacao: str


class SocioDetailInfo(BaseModel):
    nome: str
    qualificacao: str
    codigo_qualificacao: int | None = None
    cnpj_cpf: str | None = None
    data_entrada_sociedade: str | None = None
    faixa_etaria: str | None = None
    identificador_de_socio: int | None = None
    pais: str | None = None
    nome_representante_legal: str | None = None
    qualificacao_representante_legal: str | None = None


class CnaeSecundario(BaseModel):
    codigo: int | str | None = None
    descricao: str | None = None


class RegimeTributario(BaseModel):
    ano: int | None = None
    forma_de_tributacao: str | None = None
    quantidade_de_escrituracoes: int | None = None


class CnpjCacheItem(BaseModel):
    id: int
    cnpj: str
    razao_social: str | None = None
    nome_fantasia: str | None = None
    situacao_cadastral: str | None = None
    cnae_fiscal_descricao: str | None = None
    municipio: str | None = None
    uf: str | None = None
    telefone_1: str | None = None
    email: str | None = None
    capital_social: float | None = None
    porte: str | None = None
    natureza_juridica: str | None = None
    data_inicio_atividade: str | None = None
    opcao_pelo_simples: str | None = None
    opcao_pelo_mei: str | None = None
    socios: list[SocioInfo] | None = None
    data_consulta: datetime | None = None
    updated_at: datetime | None = None
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cep: str | None = None


class CnpjCacheDetail(CnpjCacheItem):
    telefone_2: str | None = None
    cnaes_secundarios: list[CnaeSecundario] | None = None
    cnae_fiscal: str | None = None
    data_situacao_cadastral: str | None = None
    motivo_situacao_cadastral: str | None = None
    descricao_tipo_logradouro: str | None = None
    identificador_matriz_filial: str | None = None
    data_opcao_pelo_simples: str | None = None
    data_exclusao_do_simples: str | None = None
    situacao_especial: str | None = None
    data_situacao_especial: str | None = None
    nome_cidade_exterior: str | None = None
    pais: str | None = None
    regime_tributario: list[RegimeTributario] | None = None
    socios_detalhados: list[SocioDetailInfo] | None = None
    data_consulta_formatada: str | None = None


class CnpjCachePaginated(BaseModel):
    data: list[CnpjCacheItem]
    total: int
    page: int
    per_page: int


class CnpjCacheStats(BaseModel):
    total: int
    ativas: int


class CnpjSearchItem(BaseModel):
    cnpj: str
    razao_social: str | None = None
    nome_fantasia: str | None = None
    municipio: str | None = None
    uf: str | None = None
    situacao_cadastral: str | None = None


class CnpjSearchResponse(BaseModel):
    results: list[CnpjSearchItem]
