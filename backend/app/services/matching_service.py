"""Serviço para consultar resultados de matching BDGD -> CNPJ."""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MatchingService:
    """Consulta resultados de matching entre BDGD e CNPJ."""

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """Retorna estatisticas do matching."""
        result = await db.execute(text("""
            WITH approx AS (
                SELECT reltuples::bigint as cnt
                FROM pg_class WHERE relname = 'bdgd_clientes'
            ),
            match_stats AS (
                SELECT
                    COUNT(DISTINCT bdgd_cod_id) as clientes_com_match,
                    COUNT(*) as total_matches,
                    AVG(CASE WHEN rank = 1 THEN score_total END) as avg_score_top1,
                    COUNT(CASE WHEN rank = 1 AND score_total >= 75 THEN 1 END) as alta_confianca,
                    COUNT(CASE WHEN rank = 1 AND score_total >= 50 AND score_total < 75 THEN 1 END) as media_confianca,
                    COUNT(CASE WHEN rank = 1 AND score_total >= 15 AND score_total < 50 THEN 1 END) as baixa_confianca,
                    COUNT(CASE WHEN rank = 1 AND address_source = 'geocoded' THEN 1 END) as via_geocode
                FROM bdgd_cnpj_matches
            )
            SELECT
                GREATEST(a.cnt, 0) as total_clientes,
                ms.clientes_com_match,
                ms.total_matches,
                ms.avg_score_top1,
                ms.alta_confianca,
                ms.media_confianca,
                ms.baixa_confianca,
                ms.via_geocode
            FROM approx a, match_stats ms
        """))
        row = result.fetchone()

        total_clientes = row[0] or 0
        clientes_com_match = row[1] or 0

        return {
            "total_clientes": total_clientes,
            "clientes_com_match": clientes_com_match,
            "clientes_sem_match": total_clientes - clientes_com_match,
            "total_matches": row[2] or 0,
            "avg_score_top1": round(float(row[3]), 1) if row[3] else None,
            "alta_confianca": row[4] or 0,
            "media_confianca": row[5] or 0,
            "baixa_confianca": row[6] or 0,
            "via_geocode": row[7] or 0,
        }

    @staticmethod
    async def list_matches(
        db: AsyncSession,
        search: Optional[str] = None,
        uf: Optional[str] = None,
        min_score: Optional[float] = None,
        confianca: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Lista clientes BDGD com seus matches."""
        # Base query para clientes que tem match
        where_clauses = []
        params: dict = {}

        if search:
            where_clauses.append("""(
                c.cod_id ILIKE :search
                OR c.lgrd_original ILIKE :search
                OR c.cnae_original ILIKE :search
                OR c.municipio_nome ILIKE :search
                OR m.razao_social ILIKE :search
                OR m.nome_fantasia ILIKE :search
                OR m.cnpj ILIKE :search
            )""")
            params["search"] = f"%{search}%"

        if uf:
            where_clauses.append("c.uf = :uf")
            params["uf"] = uf.upper()

        if min_score is not None:
            where_clauses.append("m.score_total >= :min_score")
            params["min_score"] = min_score

        if confianca:
            if confianca == "alta":
                where_clauses.append("m.score_total >= 75")
            elif confianca == "media":
                where_clauses.append("m.score_total >= 50 AND m.score_total < 75")
            elif confianca == "baixa":
                where_clauses.append("m.score_total >= 15 AND m.score_total < 50")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Contar total de clientes distintos com match
        count_sql = f"""
            SELECT COUNT(DISTINCT c.cod_id)
            FROM bdgd_clientes c
            JOIN bdgd_cnpj_matches m ON m.bdgd_cod_id = c.cod_id AND m.rank = 1
            WHERE {where_sql}
        """
        total = (await db.execute(text(count_sql), params)).scalar() or 0

        # Buscar clientes paginados
        offset = (page - 1) * per_page
        clientes_sql = f"""
            SELECT DISTINCT ON (c.cod_id)
                c.cod_id, c.lgrd_original, c.brr_original, c.cep_original, c.cnae_original,
                c.municipio_nome, c.uf, c.clas_sub, c.gru_tar,
                c.dem_cont, c.ene_max, c.liv, c.possui_solar,
                c.point_x, c.point_y,
                m.score_total as best_score,
                c.geo_logradouro, c.geo_bairro, c.geo_cep, c.geo_municipio, c.geo_uf
            FROM bdgd_clientes c
            JOIN bdgd_cnpj_matches m ON m.bdgd_cod_id = c.cod_id AND m.rank = 1
            WHERE {where_sql}
            ORDER BY c.cod_id, m.score_total DESC
            OFFSET :offset LIMIT :per_page
        """
        params["offset"] = offset
        params["per_page"] = per_page

        clientes_rows = (await db.execute(text(clientes_sql), params)).fetchall()

        # Para cada cliente, buscar seus matches
        data = []
        for crow in clientes_rows:
            cod_id = crow[0]

            matches_sql = """
                SELECT cnpj, rank, score_total, score_cep, score_cnae,
                       score_endereco, score_numero, score_bairro,
                       razao_social, nome_fantasia, cnpj_logradouro, cnpj_numero,
                       cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf,
                       cnpj_cnae, cnpj_cnae_descricao, cnpj_situacao,
                       cnpj_telefone, cnpj_email, address_source
                FROM bdgd_cnpj_matches
                WHERE bdgd_cod_id = :cod_id
                ORDER BY rank
            """
            matches_rows = (await db.execute(text(matches_sql), {"cod_id": cod_id})).fetchall()

            matches = []
            for mrow in matches_rows:
                matches.append({
                    "cnpj": mrow[0],
                    "rank": mrow[1],
                    "score_total": float(mrow[2] or 0),
                    "score_cep": float(mrow[3] or 0),
                    "score_cnae": float(mrow[4] or 0),
                    "score_endereco": float(mrow[5] or 0),
                    "score_numero": float(mrow[6] or 0),
                    "score_bairro": float(mrow[7] or 0),
                    "razao_social": mrow[8],
                    "nome_fantasia": mrow[9],
                    "cnpj_logradouro": mrow[10],
                    "cnpj_numero": mrow[11],
                    "cnpj_bairro": mrow[12],
                    "cnpj_cep": mrow[13],
                    "cnpj_municipio": mrow[14],
                    "cnpj_uf": mrow[15],
                    "cnpj_cnae": mrow[16],
                    "cnpj_cnae_descricao": mrow[17],
                    "cnpj_situacao": mrow[18],
                    "cnpj_telefone": mrow[19],
                    "cnpj_email": mrow[20],
                    "address_source": mrow[21] or "bdgd",
                })

            data.append({
                "cod_id": crow[0],
                "lgrd_original": crow[1],
                "brr_original": crow[2],
                "cep_original": crow[3],
                "cnae_original": crow[4],
                "municipio_nome": crow[5],
                "uf": crow[6],
                "clas_sub": crow[7],
                "gru_tar": crow[8],
                "dem_cont": float(crow[9]) if crow[9] else None,
                "ene_max": float(crow[10]) if crow[10] else None,
                "liv": crow[11],
                "possui_solar": crow[12],
                "point_x": crow[13],
                "point_y": crow[14],
                "best_score": float(crow[15]) if crow[15] else None,
                "geo_logradouro": crow[16],
                "geo_bairro": crow[17],
                "geo_cep": crow[18],
                "geo_municipio": crow[19],
                "geo_uf": crow[20],
                "matches": matches,
            })

        return {
            "data": data,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    @staticmethod
    async def batch_lookup(db: AsyncSession, cod_ids: list[str]) -> dict:
        """Retorna o melhor match (rank=1) para uma lista de cod_ids.

        Usado para enriquecer dados ANEEL com info de CNPJ na ConsultaPage/MapaPage.
        """
        if not cod_ids:
            return {}

        result = await db.execute(text("""
            SELECT bdgd_cod_id, cnpj, score_total, razao_social, nome_fantasia,
                   cnpj_telefone, cnpj_email, cnpj_logradouro, cnpj_numero,
                   cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf,
                   cnpj_cnae, cnpj_cnae_descricao, cnpj_situacao, address_source
            FROM bdgd_cnpj_matches
            WHERE bdgd_cod_id = ANY(:ids) AND rank = 1
        """), {"ids": cod_ids})

        matches = {}
        for row in result.fetchall():
            matches[row[0]] = {
                "cnpj": row[1],
                "score_total": float(row[2] or 0),
                "razao_social": row[3],
                "nome_fantasia": row[4],
                "telefone": row[5],
                "email": row[6],
                "logradouro": row[7],
                "numero": row[8],
                "bairro": row[9],
                "cep": row[10],
                "municipio": row[11],
                "uf": row[12],
                "cnae": row[13],
                "cnae_descricao": row[14],
                "situacao": row[15],
                "address_source": row[16] or "bdgd",
            }
        return matches

    @staticmethod
    async def get_cliente_matches(db: AsyncSession, cod_id: str) -> dict | None:
        """Retorna detalhes de um cliente BDGD com todos os seus matches."""
        cliente_sql = """
            SELECT cod_id, lgrd_original, brr_original, cep_original, cnae_original,
                   municipio_nome, uf, clas_sub, gru_tar,
                   dem_cont, ene_max, liv, possui_solar, point_x, point_y,
                   geo_logradouro, geo_bairro, geo_cep, geo_municipio, geo_uf
            FROM bdgd_clientes
            WHERE cod_id = :cod_id
        """
        crow = (await db.execute(text(cliente_sql), {"cod_id": cod_id})).fetchone()
        if not crow:
            return None

        matches_sql = """
            SELECT cnpj, rank, score_total, score_cep, score_cnae,
                   score_endereco, score_numero, score_bairro,
                   razao_social, nome_fantasia, cnpj_logradouro, cnpj_numero,
                   cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf,
                   cnpj_cnae, cnpj_cnae_descricao, cnpj_situacao,
                   cnpj_telefone, cnpj_email
            FROM bdgd_cnpj_matches
            WHERE bdgd_cod_id = :cod_id
            ORDER BY rank
        """
        matches_rows = (await db.execute(text(matches_sql), {"cod_id": cod_id})).fetchall()

        matches = []
        for mrow in matches_rows:
            matches.append({
                "cnpj": mrow[0],
                "rank": mrow[1],
                "score_total": float(mrow[2] or 0),
                "score_cep": float(mrow[3] or 0),
                "score_cnae": float(mrow[4] or 0),
                "score_endereco": float(mrow[5] or 0),
                "score_numero": float(mrow[6] or 0),
                "score_bairro": float(mrow[7] or 0),
                "razao_social": mrow[8],
                "nome_fantasia": mrow[9],
                "cnpj_logradouro": mrow[10],
                "cnpj_numero": mrow[11],
                "cnpj_bairro": mrow[12],
                "cnpj_cep": mrow[13],
                "cnpj_municipio": mrow[14],
                "cnpj_uf": mrow[15],
                "cnpj_cnae": mrow[16],
                "cnpj_cnae_descricao": mrow[17],
                "cnpj_situacao": mrow[18],
                "cnpj_telefone": mrow[19],
                "cnpj_email": mrow[20],
            })

        return {
            "cod_id": crow[0],
            "lgrd_original": crow[1],
            "brr_original": crow[2],
            "cep_original": crow[3],
            "cnae_original": crow[4],
            "municipio_nome": crow[5],
            "uf": crow[6],
            "clas_sub": crow[7],
            "gru_tar": crow[8],
            "dem_cont": float(crow[9]) if crow[9] else None,
            "ene_max": float(crow[10]) if crow[10] else None,
            "liv": crow[11],
            "possui_solar": crow[12],
            "point_x": crow[13],
            "point_y": crow[14],
            "best_score": float(matches[0]["score_total"]) if matches else None,
            "geo_logradouro": crow[15],
            "geo_bairro": crow[16],
            "geo_cep": crow[17],
            "geo_municipio": crow[18],
            "geo_uf": crow[19],
            "matches": matches,
        }
