"""Router para geocodificação reversa BDGD."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.services.geocoding_service import GeocodingService

router = APIRouter(prefix="/geocoding", tags=["Geocodificação Reversa"])


@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna estatísticas da geocodificação reversa."""
    return await GeocodingService.get_stats(db)


@router.get("/comparison")
async def get_comparison(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna amostra de clientes onde CEP geocodificado difere do BDGD."""
    return await GeocodingService.get_comparison_sample(db, limit)
