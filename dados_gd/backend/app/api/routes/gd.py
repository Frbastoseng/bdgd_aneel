"""Rotas da API de Geração Distribuída."""

import logging
from typing import Optional, List

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.gd_service import GDService
from app.services.gd_tecnico_service import GDTecnicoService
from app.schemas.geracao_distribuida import (
    GDResponse, GDListResponse, GDStats, GDStatsUFDetail, MunicipioItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gd", tags=["Geração Distribuída"])


@router.get("/", response_model=GDListResponse)
async def listar_gd(
    page: int = Query(1, ge=1, description="Página"),
    per_page: int = Query(20, ge=1, le=100, description="Itens por página"),
    sig_uf: Optional[str] = Query(None, max_length=2, description="UF (ex: SP, MG)"),
    nom_municipio: Optional[str] = Query(None, description="Nome do município (parcial)"),
    sig_tipo_geracao: Optional[str] = Query(None, description="Tipo de geração (UFV, UTE, EOL, etc.)"),
    dsc_porte: Optional[str] = Query(None, description="Porte (Microgeração, Minigeração)"),
    cod_cep: Optional[str] = Query(None, max_length=8, description="CEP"),
    num_cpf_cnpj: Optional[str] = Query(None, max_length=18, description="CPF ou CNPJ"),
    sig_agente: Optional[str] = Query(None, description="Código do agente/distribuidora"),
    db: AsyncSession = Depends(get_db),
):
    """Listar empreendimentos de Geração Distribuída com filtros e paginação."""
    result = await GDService.listar(
        db=db,
        page=page,
        per_page=per_page,
        sig_uf=sig_uf,
        nom_municipio=nom_municipio,
        sig_tipo_geracao=sig_tipo_geracao,
        dsc_porte=dsc_porte,
        cod_cep=cod_cep,
        num_cpf_cnpj=num_cpf_cnpj,
        sig_agente=sig_agente,
    )
    return result


@router.get("/stats", response_model=GDStats)
async def estatisticas_gerais(
    db: AsyncSession = Depends(get_db),
):
    """Estatísticas gerais de Geração Distribuída."""
    return await GDService.estatisticas_gerais(db)


@router.get("/stats/uf/{uf}", response_model=GDStatsUFDetail)
async def estatisticas_uf(
    uf: str,
    db: AsyncSession = Depends(get_db),
):
    """Estatísticas detalhadas de Geração Distribuída por UF."""
    result = await GDService.estatisticas_uf(db, uf)
    if result["total_empreendimentos"] == 0:
        raise HTTPException(status_code=404, detail=f"UF '{uf.upper()}' não encontrada ou sem dados de GD")
    return result


@router.get("/municipios", response_model=list[MunicipioItem])
async def listar_municipios(
    sig_uf: Optional[str] = Query(None, max_length=2, description="Filtrar por UF"),
    busca: Optional[str] = Query(None, description="Busca parcial no nome do município"),
    limit: int = Query(50, ge=1, le=200, description="Limite de resultados"),
    db: AsyncSession = Depends(get_db),
):
    """Listar municípios com Geração Distribuída (para autocomplete)."""
    return await GDService.listar_municipios(db, sig_uf=sig_uf, busca=busca, limit=limit)


@router.post("/batch")
async def batch_lookup(
    codigos: List[str] = Body(..., embed=True, max_length=500),
    include_tecnico: bool = Query(False, description="Incluir dados técnicos da usina"),
    db: AsyncSession = Depends(get_db),
):
    """Busca em batch por lista de cod_empreendimento. Retorna dict {codigo: dados}.
    Usado pelo BDGD Pro para enriquecer consultas com dados de geração.
    Se include_tecnico=true, inclui dados técnicos (fabricante, modelo, etc.)."""
    if len(codigos) > 500:
        raise HTTPException(status_code=400, detail="Máximo de 500 códigos por requisição")

    items = await GDService.buscar_por_codigos(db, codigos)

    # Buscar dados técnicos se solicitado
    tecnico_map = {}
    if include_tecnico and items:
        cods = [item.cod_empreendimento for item in items if item.cod_empreendimento]
        tecnico_map = await GDTecnicoService.buscar_por_codigos(db, cods)

    result = {}
    for item in items:
        entry = {
            "cod_empreendimento": item.cod_empreendimento,
            "nom_titular": item.nom_titular,
            "num_cpf_cnpj": item.num_cpf_cnpj,
            "sig_tipo_geracao": item.sig_tipo_geracao,
            "dsc_fonte_geracao": item.dsc_fonte_geracao,
            "dsc_porte": item.dsc_porte,
            "potencia_instalada_kw": float(item.potencia_instalada_kw) if item.potencia_instalada_kw else None,
            "dth_conexao_inicial": item.dth_conexao_inicial.isoformat() if item.dth_conexao_inicial else None,
            "sig_modalidade": item.sig_modalidade,
            "qtd_modulos": item.qtd_modulos,
            "sig_agente": item.sig_agente,
            "nom_agente": item.nom_agente,
            "sig_uf": item.sig_uf,
            "nom_municipio": item.nom_municipio,
        }
        if include_tecnico:
            entry["dados_tecnicos"] = tecnico_map.get(item.cod_empreendimento)
        result[item.cod_empreendimento] = entry
    return result


@router.post("/batch-tecnico")
async def batch_tecnico_lookup(
    codigos: List[str] = Body(..., embed=True, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    """Busca dados técnicos em batch por lista de cod_empreendimento.
    Retorna dict {codigo: {tipo, ...dados_tecnicos}} apenas para encontrados."""
    if len(codigos) > 500:
        raise HTTPException(status_code=400, detail="Máximo de 500 códigos por requisição")

    return await GDTecnicoService.buscar_por_codigos(db, codigos)


@router.get("/cnpj/{cnpj}", response_model=List[GDResponse])
async def buscar_por_cnpj(
    cnpj: str,
    db: AsyncSession = Depends(get_db),
):
    """Buscar empreendimentos GD por CNPJ."""
    items = await GDService.buscar_por_cnpj(db, cnpj)
    if not items:
        raise HTTPException(status_code=404, detail=f"Nenhum empreendimento para CNPJ '{cnpj}'")
    return items


@router.get("/health")
async def health_check():
    """Health check do módulo GD."""
    return {"status": "healthy", "module": "geracao_distribuida"}


@router.get("/{cod_empreendimento}", response_model=GDResponse)
async def buscar_por_codigo(
    cod_empreendimento: str,
    db: AsyncSession = Depends(get_db),
):
    """Buscar empreendimento GD por código."""
    result = await GDService.buscar_por_codigo(db, cod_empreendimento)
    if not result:
        raise HTTPException(status_code=404, detail=f"Empreendimento '{cod_empreendimento}' não encontrado")
    return result
