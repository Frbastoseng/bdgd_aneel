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
                    COUNT(CASE WHEN rank = 1 AND score_total >= 15 AND score_total < 50 THEN 1 END) as baixa_confianca
                FROM bdgd_cnpj_matches
            )
            SELECT
                GREATEST(a.cnt, 0) as total_clientes,
                ms.clientes_com_match,
                ms.total_matches,
                ms.avg_score_top1,
                ms.alta_confianca,
                ms.media_confianca,
                ms.baixa_confianca
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
                m.score_total as best_score
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
                "matches": matches,
            })

        return {
            "data": data,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    @staticmethod
    async def get_cliente_matches(db: AsyncSession, cod_id: str) -> dict | None:
        """Retorna detalhes de um cliente BDGD com todos os seus matches."""
        cliente_sql = """
            SELECT cod_id, lgrd_original, brr_original, cep_original, cnae_original,
                   municipio_nome, uf, clas_sub, gru_tar,
                   dem_cont, ene_max, liv, possui_solar, point_x, point_y
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
            "matches": matches,
        }
