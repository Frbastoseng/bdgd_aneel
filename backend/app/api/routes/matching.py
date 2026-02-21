"""Router para consulta de matching BDGD -> CNPJ."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
