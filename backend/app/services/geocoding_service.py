"""Serviço para geocodificação reversa e consulta de status."""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class GeocodingService:
    """Consulta status e resultados da geocodificação reversa."""

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """Retorna estatísticas da geocodificação."""
        result = await db.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'success' THEN 1 END) as success,
                COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'error' THEN 1 END) as errors
            FROM geocode_cache
        """))
        cache_row = result.fetchone()

        result2 = await db.execute(text("""
            SELECT
                COUNT(*) as total_clientes,
                COUNT(CASE WHEN geo_status = 'success' THEN 1 END) as com_geocode,
                COUNT(CASE WHEN geo_cep IS NOT NULL THEN 1 END) as com_geo_cep,
                COUNT(CASE WHEN cep_norm IS NOT NULL AND geo_cep IS NOT NULL
                           AND cep_norm != geo_cep THEN 1 END) as cep_diferente,
                COUNT(CASE WHEN cep_norm IS NULL AND geo_cep IS NOT NULL THEN 1 END) as cep_novo
            FROM bdgd_clientes
        """))
        clientes_row = result2.fetchone()

        # Estatísticas de impacto no matching
        result3 = await db.execute(text("""
            SELECT
                COUNT(CASE WHEN rank = 1 AND address_source = 'geocoded' THEN 1 END) as matches_via_geocode,
                COUNT(CASE WHEN rank = 1 THEN 1 END) as total_top1
            FROM bdgd_cnpj_matches
        """))
        match_row = result3.fetchone()

        return {
            "cache": {
                "total": cache_row[0] or 0,
                "success": cache_row[1] or 0,
                "pending": cache_row[2] or 0,
                "errors": cache_row[3] or 0,
            },
            "clientes": {
                "total": clientes_row[0] or 0,
                "com_geocode": clientes_row[1] or 0,
                "com_geo_cep": clientes_row[2] or 0,
                "cep_diferente": clientes_row[3] or 0,
                "cep_novo": clientes_row[4] or 0,
            },
            "matching_impact": {
                "matches_via_geocode": match_row[0] or 0,
                "total_top1": match_row[1] or 0,
            },
        }

    @staticmethod
    async def get_comparison_sample(
        db: AsyncSession,
        limit: int = 20,
    ) -> list[dict]:
        """
        Retorna amostra de clientes onde o CEP geocodificado difere do BDGD.
        Útil para visualizar onde a geocodificação agrega valor.
        """
        result = await db.execute(text("""
            SELECT
                c.cod_id, c.lgrd_original, c.brr_original, c.cep_original,
                c.municipio_nome, c.uf,
                c.geo_logradouro, c.geo_bairro, c.geo_cep,
                c.geo_municipio, c.geo_uf,
                c.point_x, c.point_y
            FROM bdgd_clientes c
            WHERE c.geo_cep IS NOT NULL
              AND c.cep_norm IS NOT NULL
              AND c.cep_norm != c.geo_cep
            ORDER BY c.id
            LIMIT :limit
        """), {"limit": limit})

        rows = result.fetchall()
        return [
            {
                "cod_id": r[0],
                "bdgd_endereco": r[1],
                "bdgd_bairro": r[2],
                "bdgd_cep": r[3],
                "bdgd_municipio": r[4],
                "bdgd_uf": r[5],
                "geo_logradouro": r[6],
                "geo_bairro": r[7],
                "geo_cep": r[8],
                "geo_municipio": r[9],
                "geo_uf": r[10],
                "point_x": r[11],
                "point_y": r[12],
            }
            for r in rows
        ]
