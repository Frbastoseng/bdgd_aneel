"""Router para consulta de CNPJs."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.cnpj import (
    CnpjCacheDetail,
    CnpjCachePaginated,
    CnpjCacheStats,
    CnpjSearchResponse,
)
from app.services.cnpj_service import CnpjService

router = APIRouter(prefix="/cnpj", tags=["CNPJ"])


@router.get("/cache", response_model=CnpjCachePaginated)
async def list_cache(
    search: str | None = Query(None, description="Buscar por empresa, CNPJ, cidade, CNAE"),
    uf: str | None = Query(None, description="Filtrar por UF"),
    situacao: str | None = Query(None, description="Filtrar por situacao cadastral"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lista CNPJs com filtros e paginacao."""
    return await CnpjService.list_cache(db, search, uf, situacao, page, per_page)


@router.get("/cache/stats", response_model=CnpjCacheStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna estatisticas do cache de CNPJs."""
    return await CnpjService.get_stats(db)


@router.get("/cache/{cnpj}", response_model=CnpjCacheDetail)
async def get_detail(
    cnpj: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna detalhes completos de um CNPJ."""
    result = await CnpjService.get_detail(db, cnpj)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CNPJ {cnpj} nao encontrado.",
        )
    return result


@router.get("/search", response_model=CnpjSearchResponse)
async def search(
    q: str = Query(..., min_length=2, description="Termo de busca"),
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Busca rapida de CNPJs (autocomplete)."""
    results = await CnpjService.search(db, q, limit)
    return {"results": results}
