"""
Standalone CNPJ query service.

Queries crm.cnpj_cache table directly using raw SQL.
No dependencies on app.* - completely standalone.
"""

import json
import logging

from sqlalchemy import text

from cnpj.config import SCHEMA
from cnpj.database import get_session

logger = logging.getLogger(__name__)


def consultar_cnpj(cnpj: str) -> dict | None:
    """
    Query a single CNPJ from the local database.

    Args:
        cnpj: CNPJ (only digits, 14 chars)

    Returns:
        dict with CNPJ data, or None if not found
    """
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())

    session = get_session()
    try:
        result = session.execute(
            text(f"SELECT * FROM {SCHEMA}.cnpj_cache WHERE cnpj = :cnpj"),
            {"cnpj": cnpj_limpo},
        ).mappings().first()

        if not result:
            return None

        return _row_to_dict(dict(result))
    finally:
        session.close()


def buscar_cnpjs(
    search: str | None = None,
    uf: str | None = None,
    municipio: str | None = None,
    situacao: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    """
    Search CNPJs with filters and pagination.

    Args:
        search: Search term (razao_social, nome_fantasia, CNPJ)
        uf: Filter by UF
        municipio: Filter by municipio
        situacao: Filter by situacao cadastral
        limit: Results limit
        offset: Pagination offset

    Returns:
        {"results": [...], "total": int}
    """
    conditions = []
    params: dict = {"limit": limit, "offset": offset}

    if search:
        conditions.append(
            "(razao_social ILIKE :search OR nome_fantasia ILIKE :search OR cnpj ILIKE :search)"
        )
        params["search"] = f"%{search}%"

    if uf:
        conditions.append("uf = :uf")
        params["uf"] = uf.upper()

    if municipio:
        conditions.append("municipio ILIKE :municipio")
        params["municipio"] = f"%{municipio}%"

    if situacao:
        conditions.append("situacao_cadastral ILIKE :situacao")
        params["situacao"] = f"%{situacao}%"

    where = " AND ".join(conditions) if conditions else "1=1"

    session = get_session()
    try:
        # Count
        total = session.execute(
            text(f"SELECT COUNT(*) FROM {SCHEMA}.cnpj_cache WHERE {where}"),
            params,
        ).scalar() or 0

        # Results
        rows = session.execute(
            text(
                f"SELECT * FROM {SCHEMA}.cnpj_cache WHERE {where} "
                f"ORDER BY razao_social LIMIT :limit OFFSET :offset"
            ),
            params,
        ).mappings().all()

        return {
            "results": [_row_to_dict(dict(r)) for r in rows],
            "total": total,
        }
    finally:
        session.close()


def buscar_lote(cnpjs: list[str]) -> dict:
    """
    Batch query for multiple CNPJs.

    Args:
        cnpjs: List of CNPJs (max 100)

    Returns:
        {"found": [...], "not_found": [...], "total_found": int, "total_not_found": int}
    """
    limpos = ["".join(c for c in cnpj if c.isdigit()) for cnpj in cnpjs]

    session = get_session()
    try:
        rows = session.execute(
            text(f"SELECT * FROM {SCHEMA}.cnpj_cache WHERE cnpj = ANY(:cnpjs)"),
            {"cnpjs": limpos},
        ).mappings().all()

        found_cnpjs = {dict(r)["cnpj"] for r in rows}
        not_found = [c for c in limpos if c not in found_cnpjs]

        return {
            "found": [_row_to_dict(dict(r)) for r in rows],
            "not_found": not_found,
            "total_found": len(rows),
            "total_not_found": len(not_found),
        }
    finally:
        session.close()


def get_stats() -> dict:
    """Get aggregate statistics from cnpj_cache."""
    session = get_session()
    try:
        result = session.execute(text(f"""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN situacao_cadastral ILIKE '%ativa%' THEN 1 END) as ativas,
                COUNT(CASE WHEN situacao_cadastral ILIKE '%suspensa%' THEN 1 END) as suspensas,
                COUNT(CASE WHEN situacao_cadastral ILIKE '%inapta%' THEN 1 END) as inaptas,
                COUNT(CASE WHEN situacao_cadastral ILIKE '%baixada%' THEN 1 END) as baixadas,
                COUNT(CASE WHEN opcao_pelo_simples = 'S' THEN 1 END) as simples,
                COUNT(CASE WHEN opcao_pelo_mei = 'S' THEN 1 END) as mei,
                COUNT(DISTINCT uf) as ufs
            FROM {SCHEMA}.cnpj_cache
        """)).mappings().first()

        return dict(result) if result else {}
    finally:
        session.close()


def _row_to_dict(row: dict) -> dict:
    """Convert a database row to a clean dict."""
    # Parse socios from JSONB
    socios = row.get("socios")
    if socios and isinstance(socios, str):
        try:
            socios = json.loads(socios)
        except json.JSONDecodeError:
            socios = None

    return {
        "cnpj": row.get("cnpj"),
        "razao_social": row.get("razao_social") or "",
        "nome_fantasia": row.get("nome_fantasia") or "",
        "situacao_cadastral": row.get("situacao_cadastral") or "",
        "data_situacao_cadastral": row.get("data_situacao_cadastral") or "",
        "data_inicio_atividade": row.get("data_inicio_atividade") or "",
        "natureza_juridica": row.get("natureza_juridica") or "",
        "porte": row.get("porte") or "",
        "capital_social": float(row["capital_social"]) if row.get("capital_social") else 0.0,
        "cnae_fiscal": row.get("cnae_fiscal") or "",
        "cnae_fiscal_descricao": row.get("cnae_fiscal_descricao") or "",
        "logradouro": row.get("logradouro") or "",
        "numero": row.get("numero") or "",
        "complemento": row.get("complemento") or "",
        "bairro": row.get("bairro") or "",
        "municipio": row.get("municipio") or "",
        "uf": row.get("uf") or "",
        "cep": row.get("cep") or "",
        "telefone_1": row.get("telefone_1") or "",
        "telefone_2": row.get("telefone_2") or "",
        "email": row.get("email") or "",
        "socios": socios or [],
        "opcao_pelo_simples": row.get("opcao_pelo_simples") or "",
        "opcao_pelo_mei": row.get("opcao_pelo_mei") or "",
        "data_consulta": row.get("data_consulta").isoformat() if row.get("data_consulta") else None,
        "_source": "local_database",
    }
