"""Serviço de consulta CNPJ para o BDGD Pro."""

import logging
from typing import Optional

from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cnpj_cache import CnpjCache

logger = logging.getLogger(__name__)


class CnpjService:
    """Serviço para consulta de CNPJs no banco de dados local."""

    @staticmethod
    async def list_cache(
        db: AsyncSession,
        search: Optional[str] = None,
        uf: Optional[str] = None,
        situacao: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """Lista CNPJs com filtros e paginacao."""
        # Colunas leves (sem raw_json)
        columns = [
            CnpjCache.id,
            CnpjCache.cnpj,
            CnpjCache.razao_social,
            CnpjCache.nome_fantasia,
            CnpjCache.situacao_cadastral,
            CnpjCache.cnae_fiscal_descricao,
            CnpjCache.municipio,
            CnpjCache.uf,
            CnpjCache.telefone_1,
            CnpjCache.email,
            CnpjCache.capital_social,
            CnpjCache.porte,
            CnpjCache.natureza_juridica,
            CnpjCache.data_inicio_atividade,
            CnpjCache.opcao_pelo_simples,
            CnpjCache.opcao_pelo_mei,
            CnpjCache.socios,
            CnpjCache.data_consulta,
            CnpjCache.updated_at,
            CnpjCache.logradouro,
            CnpjCache.numero,
            CnpjCache.complemento,
            CnpjCache.bairro,
            CnpjCache.cep,
        ]

        base = select(*columns)
        has_filter = False

        if search:
            search_term = f"%{search}%"
            base = base.where(
                or_(
                    CnpjCache.razao_social.ilike(search_term),
                    CnpjCache.nome_fantasia.ilike(search_term),
                    CnpjCache.cnpj.ilike(search_term),
                    CnpjCache.municipio.ilike(search_term),
                    CnpjCache.cnae_fiscal_descricao.ilike(search_term),
                )
            )
            has_filter = True

        if uf:
            base = base.where(CnpjCache.uf == uf.upper())
            has_filter = True

        if situacao:
            base = base.where(CnpjCache.situacao_cadastral.ilike(f"%{situacao}%"))
            has_filter = True

        # Contagem
        if has_filter:
            # Contagem limitada para filtros (evitar scan completo)
            count_q = select(func.count()).select_from(
                base.limit(10001).subquery()
            )
            total = (await db.execute(count_q)).scalar() or 0
        else:
            # Contagem aproximada via pg_class (instantanea)
            approx_q = text(
                "SELECT reltuples::bigint FROM pg_class WHERE relname = 'cnpj_cache'"
            )
            result = await db.execute(approx_q)
            total = result.scalar() or 0
            if total < 0:
                total = 0

        # Resultados paginados
        offset = (page - 1) * per_page
        query = base.offset(offset).limit(per_page)
        if has_filter:
            query = query.order_by(CnpjCache.razao_social)
        else:
            query = query.order_by(CnpjCache.id)
        rows = (await db.execute(query)).all()

        data = []
        for row in rows:
            socios_list = None
            if row.socios and isinstance(row.socios, list):
                socios_list = [
                    {"nome": s.get("nome", ""), "qualificacao": s.get("qualificacao", "")}
                    for s in row.socios
                ]

            data.append({
                "id": row.id,
                "cnpj": row.cnpj,
                "razao_social": row.razao_social,
                "nome_fantasia": row.nome_fantasia,
                "situacao_cadastral": row.situacao_cadastral,
                "cnae_fiscal_descricao": row.cnae_fiscal_descricao,
                "municipio": row.municipio,
                "uf": row.uf,
                "telefone_1": row.telefone_1,
                "email": row.email,
                "capital_social": float(row.capital_social) if row.capital_social else None,
                "porte": row.porte,
                "natureza_juridica": row.natureza_juridica,
                "data_inicio_atividade": row.data_inicio_atividade,
                "opcao_pelo_simples": row.opcao_pelo_simples,
                "opcao_pelo_mei": row.opcao_pelo_mei,
                "socios": socios_list,
                "data_consulta": row.data_consulta,
                "updated_at": row.updated_at,
                "logradouro": row.logradouro,
                "numero": row.numero,
                "complemento": row.complemento,
                "bairro": row.bairro,
                "cep": row.cep,
            })

        return {
            "data": data,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    @staticmethod
    async def get_detail(db: AsyncSession, cnpj: str) -> dict | None:
        """Retorna detalhes completos de um CNPJ."""
        cnpj_limpo = "".join(c for c in cnpj if c.isdigit())

        result = await db.execute(
            select(CnpjCache).where(CnpjCache.cnpj == cnpj_limpo)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            return None

        # Socios basico
        socios_list = None
        if entry.socios and isinstance(entry.socios, list):
            socios_list = [
                {"nome": s.get("nome", ""), "qualificacao": s.get("qualificacao", "")}
                for s in entry.socios
            ]

        # Socios detalhados do raw_json
        socios_detalhados = None
        cnaes_secundarios = None
        motivo_situacao = None
        desc_tipo_logradouro = None
        ident_matriz_filial = None
        data_opcao_simples = None
        data_exclusao_simples = None
        situacao_especial = None
        data_situacao_especial = None
        nome_cidade_exterior = None
        pais = None
        regime_tributario = None

        raw = entry.raw_json or {}

        if raw:
            # QSA detalhado
            qsa = raw.get("qsa", [])
            if qsa and isinstance(qsa, list):
                socios_detalhados = []
                for s in qsa:
                    socios_detalhados.append({
                        "nome": s.get("nome_socio", s.get("nome", "")),
                        "qualificacao": s.get("qualificacao_socio", s.get("qualificacao", "")),
                        "codigo_qualificacao": s.get("codigo_qualificacao_socio"),
                        "cnpj_cpf": s.get("cnpj_cpf_do_socio", ""),
                        "data_entrada_sociedade": s.get("data_entrada_sociedade", ""),
                        "faixa_etaria": s.get("faixa_etaria", ""),
                        "identificador_de_socio": s.get("identificador_de_socio"),
                        "pais": s.get("pais", ""),
                        "nome_representante_legal": s.get("nome_representante_legal", ""),
                        "qualificacao_representante_legal": s.get(
                            "qualificacao_representante_legal", ""
                        ),
                    })

            # CNAEs secundarios
            cnaes_raw = raw.get("cnaes_secundarios", entry.cnaes_secundarios)
            if cnaes_raw and isinstance(cnaes_raw, list):
                cnaes_secundarios = [
                    {
                        "codigo": c.get("codigo", c.get("code", "")),
                        "descricao": c.get("descricao", c.get("text", "")),
                    }
                    for c in cnaes_raw
                ]

            motivo_situacao = raw.get("motivo_situacao_cadastral", "")
            desc_tipo_logradouro = raw.get("descricao_tipo_de_logradouro", "")

            ident_raw = raw.get("identificador_matriz_filial")
            if ident_raw == 1:
                ident_matriz_filial = "MATRIZ"
            elif ident_raw == 2:
                ident_matriz_filial = "FILIAL"
            else:
                ident_matriz_filial = str(ident_raw) if ident_raw else None

            data_opcao_simples = raw.get("data_opcao_pelo_simples", "")
            data_exclusao_simples = raw.get("data_exclusao_do_simples", "")
            situacao_especial = raw.get("situacao_especial", "")
            data_situacao_especial = raw.get("data_situacao_especial", "")
            nome_cidade_exterior = raw.get("nome_cidade_no_exterior", "")
            pais = raw.get("pais", "")

            regime_raw = raw.get("simples", {})
            if isinstance(regime_raw, dict) and regime_raw.get("simples"):
                regime_tributario = [
                    {
                        "ano": r.get("ano"),
                        "forma_de_tributacao": r.get("forma_de_tributacao"),
                        "quantidade_de_escrituracoes": r.get("quantidade_de_escrituracoes"),
                    }
                    for r in regime_raw.get("simples", [])
                    if isinstance(r, dict)
                ]

        # Formatar data_consulta
        data_consulta_fmt = None
        if entry.data_consulta:
            data_consulta_fmt = entry.data_consulta.strftime("%d/%m/%Y %H:%M")

        return {
            "id": entry.id,
            "cnpj": entry.cnpj,
            "razao_social": entry.razao_social,
            "nome_fantasia": entry.nome_fantasia,
            "situacao_cadastral": entry.situacao_cadastral,
            "cnae_fiscal_descricao": entry.cnae_fiscal_descricao,
            "municipio": entry.municipio,
            "uf": entry.uf,
            "telefone_1": entry.telefone_1,
            "email": entry.email,
            "capital_social": float(entry.capital_social) if entry.capital_social else None,
            "porte": entry.porte,
            "natureza_juridica": entry.natureza_juridica,
            "data_inicio_atividade": entry.data_inicio_atividade,
            "opcao_pelo_simples": entry.opcao_pelo_simples,
            "opcao_pelo_mei": entry.opcao_pelo_mei,
            "socios": socios_list,
            "data_consulta": entry.data_consulta,
            "updated_at": entry.updated_at,
            "logradouro": entry.logradouro,
            "numero": entry.numero,
            "complemento": entry.complemento,
            "bairro": entry.bairro,
            "cep": entry.cep,
            # Campos detalhados
            "telefone_2": entry.telefone_2,
            "cnaes_secundarios": cnaes_secundarios,
            "cnae_fiscal": entry.cnae_fiscal,
            "data_situacao_cadastral": entry.data_situacao_cadastral,
            "motivo_situacao_cadastral": motivo_situacao,
            "descricao_tipo_logradouro": desc_tipo_logradouro,
            "identificador_matriz_filial": ident_matriz_filial,
            "data_opcao_pelo_simples": data_opcao_simples,
            "data_exclusao_do_simples": data_exclusao_simples,
            "situacao_especial": situacao_especial,
            "data_situacao_especial": data_situacao_especial,
            "nome_cidade_exterior": nome_cidade_exterior,
            "pais": pais,
            "regime_tributario": regime_tributario,
            "socios_detalhados": socios_detalhados,
            "data_consulta_formatada": data_consulta_fmt,
        }

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """Retorna estatisticas do cache de CNPJs (estimativa rapida)."""
        # Usar pg_class para contagem aproximada instantanea
        approx_q = text(
            "SELECT reltuples::bigint FROM pg_class WHERE relname = 'cnpj_cache'"
        )
        result = await db.execute(approx_q)
        total = result.scalar() or 0
        if total < 0:
            total = 0

        # Ativas = estimativa (maioria eh ativa, ~98% nos dados importados)
        # Para contagem exata seria lento demais em 15M registros
        ativas = int(total * 0.98) if total > 0 else 0

        return {"total": total, "ativas": ativas}

    @staticmethod
    async def search(
        db: AsyncSession, q: str, limit: int = 10
    ) -> list[dict]:
        """Busca rapida de CNPJs (autocomplete)."""
        if len(q) < 2:
            return []

        # Se numerico, buscar por prefixo de CNPJ
        q_digits = "".join(c for c in q if c.isdigit())
        if q_digits and len(q_digits) >= 2:
            stmt = (
                select(
                    CnpjCache.cnpj,
                    CnpjCache.razao_social,
                    CnpjCache.nome_fantasia,
                    CnpjCache.municipio,
                    CnpjCache.uf,
                    CnpjCache.situacao_cadastral,
                )
                .where(CnpjCache.cnpj.like(f"{q_digits}%"))
                .limit(limit)
            )
        else:
            search_term = f"%{q}%"
            stmt = (
                select(
                    CnpjCache.cnpj,
                    CnpjCache.razao_social,
                    CnpjCache.nome_fantasia,
                    CnpjCache.municipio,
                    CnpjCache.uf,
                    CnpjCache.situacao_cadastral,
                )
                .where(
                    or_(
                        CnpjCache.razao_social.ilike(search_term),
                        CnpjCache.nome_fantasia.ilike(search_term),
                    )
                )
                .order_by(CnpjCache.razao_social)
                .limit(limit)
            )

        rows = (await db.execute(stmt)).all()

        return [
            {
                "cnpj": row.cnpj,
                "razao_social": row.razao_social,
                "nome_fantasia": row.nome_fantasia,
                "municipio": row.municipio,
                "uf": row.uf,
                "situacao_cadastral": row.situacao_cadastral,
            }
            for row in rows
        ]
