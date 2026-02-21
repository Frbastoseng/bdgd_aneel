"""Router para consulta de matching BDGD -> CNPJ."""

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.matching import (
    BdgdClienteComMatch,
    MatchingPaginated,
    MatchingStats,
)
from app.services.matching_service import MatchingService
from app.services.refine_service import RefineService

router = APIRouter(prefix="/matching", tags=["Matching BDGD-CNPJ"])


@router.get("/stats", response_model=MatchingStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna estatisticas do matching BDGD -> CNPJ."""
    return await MatchingService.get_stats(db)


@router.get("/results", response_model=MatchingPaginated)
async def list_matches(
    search: str | None = Query(None, description="Buscar por empresa, CNPJ, endereco"),
    uf: str | None = Query(None, description="Filtrar por UF"),
    min_score: float | None = Query(None, ge=0, le=100, description="Score minimo"),
    confianca: str | None = Query(
        None, description="Nivel de confianca: alta, media, baixa"
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lista resultados de matching com filtros e paginacao."""
    return await MatchingService.list_matches(
        db, search, uf, min_score, confianca, page, per_page
    )


@router.post("/batch-lookup")
async def batch_lookup(
    cod_ids: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna o melhor match CNPJ para uma lista de cod_ids (max 1000).

    Usado para enriquecer dados ANEEL na ConsultaPage e MapaPage.
    """
    if len(cod_ids) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximo de 1000 cod_ids por requisicao.",
        )
    return await MatchingService.batch_lookup(db, cod_ids)


@router.post("/refine")
async def refine_matches(
    cod_ids: list[str] = Body(..., embed=True, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Geocodifica coordenadas e re-faz matching para uma lista de clientes (max 100).

    Fluxo:
      1. Geocodifica coordenadas via Nominatim (com cache)
      2. Re-calcula matching com dupla fonte de endereco (BDGD + geocodificado)
      3. Retorna contagem de resultados melhorados
    """
    if len(cod_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximo de 100 clientes por requisicao.",
        )
    return await RefineService.refine_clientes(db, cod_ids)


@router.get("/results/{cod_id}", response_model=BdgdClienteComMatch)
async def get_cliente_matches(
    cod_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna detalhes de matching para um cliente BDGD."""
    result = await MatchingService.get_cliente_matches(db, cod_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente BDGD {cod_id} nao encontrado.",
        )
    return result
