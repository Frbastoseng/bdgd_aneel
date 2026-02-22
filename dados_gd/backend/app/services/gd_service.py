"""Serviço de consulta de dados de Geração Distribuída."""

import logging
import math
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geracao_distribuida import GeracaoDistribuida

logger = logging.getLogger(__name__)


class GDService:
    """Serviço para consultas de Geração Distribuída."""

    @staticmethod
    async def listar(
        db: AsyncSession,
        page: int = 1,
        per_page: int = 20,
        sig_uf: Optional[str] = None,
        nom_municipio: Optional[str] = None,
        sig_tipo_geracao: Optional[str] = None,
        dsc_porte: Optional[str] = None,
        cod_cep: Optional[str] = None,
        num_cpf_cnpj: Optional[str] = None,
        sig_agente: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Listar empreendimentos GD com filtros e paginação."""

        query = select(GeracaoDistribuida)
        count_query = select(func.count(GeracaoDistribuida.id))

        # Aplicar filtros
        if sig_uf:
            query = query.where(GeracaoDistribuida.sig_uf == sig_uf.upper())
            count_query = count_query.where(GeracaoDistribuida.sig_uf == sig_uf.upper())
        if nom_municipio:
            query = query.where(GeracaoDistribuida.nom_municipio.ilike(f"%{nom_municipio}%"))
            count_query = count_query.where(GeracaoDistribuida.nom_municipio.ilike(f"%{nom_municipio}%"))
        if sig_tipo_geracao:
            query = query.where(GeracaoDistribuida.sig_tipo_geracao == sig_tipo_geracao.upper())
            count_query = count_query.where(GeracaoDistribuida.sig_tipo_geracao == sig_tipo_geracao.upper())
        if dsc_porte:
            query = query.where(GeracaoDistribuida.dsc_porte.ilike(f"%{dsc_porte}%"))
            count_query = count_query.where(GeracaoDistribuida.dsc_porte.ilike(f"%{dsc_porte}%"))
        if cod_cep:
            query = query.where(GeracaoDistribuida.cod_cep == cod_cep)
            count_query = count_query.where(GeracaoDistribuida.cod_cep == cod_cep)
        if num_cpf_cnpj:
            query = query.where(GeracaoDistribuida.num_cpf_cnpj == num_cpf_cnpj)
            count_query = count_query.where(GeracaoDistribuida.num_cpf_cnpj == num_cpf_cnpj)
        if sig_agente:
            query = query.where(GeracaoDistribuida.sig_agente == sig_agente.upper())
            count_query = count_query.where(GeracaoDistribuida.sig_agente == sig_agente.upper())

        # Contagem total (usar estimativa para queries sem filtro)
        if not any([sig_uf, nom_municipio, sig_tipo_geracao, dsc_porte, cod_cep, num_cpf_cnpj, sig_agente]):
            result = await db.execute(text(
                "SELECT reltuples::BIGINT FROM pg_class WHERE relname = 'geracao_distribuida'"
            ))
            total = max(result.scalar() or 0, 0)
        else:
            result = await db.execute(count_query)
            total = result.scalar() or 0

        # Paginação
        offset = (page - 1) * per_page
        query = query.order_by(GeracaoDistribuida.id).offset(offset).limit(per_page)

        result = await db.execute(query)
        items = result.scalars().all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": math.ceil(total / per_page) if per_page > 0 else 0
        }

    @staticmethod
    async def buscar_por_codigo(db: AsyncSession, cod_empreendimento: str) -> Optional[GeracaoDistribuida]:
        """Buscar empreendimento por código."""
        result = await db.execute(
            select(GeracaoDistribuida).where(
                GeracaoDistribuida.cod_empreendimento == cod_empreendimento
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def estatisticas_gerais(db: AsyncSession) -> Dict[str, Any]:
        """Estatísticas gerais de Geração Distribuída."""

        # Total e potência total
        result = await db.execute(
            select(
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            )
        )
        row = result.one()
        total = row[0]
        potencia_total = float(row[1])

        # Por UF
        result = await db.execute(
            select(
                GeracaoDistribuida.sig_uf,
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            )
            .where(GeracaoDistribuida.sig_uf.isnot(None))
            .group_by(GeracaoDistribuida.sig_uf)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )
        por_uf = [
            {"uf": r[0], "total": r[1], "potencia_total_kw": float(r[2])}
            for r in result.all()
        ]

        # Por tipo de geração
        result = await db.execute(
            select(
                GeracaoDistribuida.sig_tipo_geracao,
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            )
            .where(GeracaoDistribuida.sig_tipo_geracao.isnot(None))
            .group_by(GeracaoDistribuida.sig_tipo_geracao)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )
        por_tipo = [
            {"tipo": r[0], "total": r[1], "potencia_total_kw": float(r[2])}
            for r in result.all()
        ]

        # Por porte
        result = await db.execute(
            select(
                GeracaoDistribuida.dsc_porte,
                func.count(GeracaoDistribuida.id)
            )
            .where(GeracaoDistribuida.dsc_porte.isnot(None))
            .group_by(GeracaoDistribuida.dsc_porte)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )
        por_porte = [
            {"porte": r[0], "total": r[1]}
            for r in result.all()
        ]

        return {
            "total_empreendimentos": total,
            "potencia_total_instalada_kw": potencia_total,
            "por_uf": por_uf,
            "por_tipo_geracao": por_tipo,
            "por_porte": por_porte,
        }

    @staticmethod
    async def estatisticas_uf(db: AsyncSession, uf: str) -> Dict[str, Any]:
        """Estatísticas detalhadas de uma UF."""
        uf = uf.upper()

        # Total e potência da UF
        result = await db.execute(
            select(
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            ).where(GeracaoDistribuida.sig_uf == uf)
        )
        row = result.one()
        total = row[0]
        potencia_total = float(row[1])

        # Por tipo de geração na UF
        result = await db.execute(
            select(
                GeracaoDistribuida.sig_tipo_geracao,
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            )
            .where(GeracaoDistribuida.sig_uf == uf)
            .where(GeracaoDistribuida.sig_tipo_geracao.isnot(None))
            .group_by(GeracaoDistribuida.sig_tipo_geracao)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )
        por_tipo = [
            {"tipo": r[0], "total": r[1], "potencia_total_kw": float(r[2])}
            for r in result.all()
        ]

        # Por porte na UF
        result = await db.execute(
            select(
                GeracaoDistribuida.dsc_porte,
                func.count(GeracaoDistribuida.id)
            )
            .where(GeracaoDistribuida.sig_uf == uf)
            .where(GeracaoDistribuida.dsc_porte.isnot(None))
            .group_by(GeracaoDistribuida.dsc_porte)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )
        por_porte = [
            {"porte": r[0], "total": r[1]}
            for r in result.all()
        ]

        # Top 20 municípios
        result = await db.execute(
            select(
                GeracaoDistribuida.nom_municipio,
                func.count(GeracaoDistribuida.id),
                func.coalesce(func.sum(GeracaoDistribuida.potencia_instalada_kw), 0)
            )
            .where(GeracaoDistribuida.sig_uf == uf)
            .where(GeracaoDistribuida.nom_municipio.isnot(None))
            .group_by(GeracaoDistribuida.nom_municipio)
            .order_by(func.count(GeracaoDistribuida.id).desc())
            .limit(20)
        )
        por_municipio = [
            {"municipio": r[0], "total": r[1], "potencia_total_kw": float(r[2])}
            for r in result.all()
        ]

        return {
            "uf": uf,
            "total_empreendimentos": total,
            "potencia_total_instalada_kw": potencia_total,
            "por_tipo_geracao": por_tipo,
            "por_porte": por_porte,
            "por_municipio": por_municipio,
        }

    @staticmethod
    async def buscar_por_codigos(db: AsyncSession, codigos: List[str]) -> List[GeracaoDistribuida]:
        """Buscar múltiplos empreendimentos por código (batch lookup)."""
        if not codigos:
            return []
        result = await db.execute(
            select(GeracaoDistribuida).where(
                GeracaoDistribuida.cod_empreendimento.in_(codigos)
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def buscar_por_cnpj(db: AsyncSession, cnpj: str) -> List[GeracaoDistribuida]:
        """Buscar empreendimentos por CNPJ."""
        result = await db.execute(
            select(GeracaoDistribuida).where(
                GeracaoDistribuida.num_cpf_cnpj == cnpj
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def listar_municipios(
        db: AsyncSession,
        sig_uf: Optional[str] = None,
        busca: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Listar municípios com GD para autocomplete."""
        query = (
            select(
                GeracaoDistribuida.nom_municipio,
                GeracaoDistribuida.sig_uf,
                func.count(GeracaoDistribuida.id).label("total")
            )
            .where(GeracaoDistribuida.nom_municipio.isnot(None))
            .group_by(GeracaoDistribuida.nom_municipio, GeracaoDistribuida.sig_uf)
            .order_by(func.count(GeracaoDistribuida.id).desc())
        )

        if sig_uf:
            query = query.where(GeracaoDistribuida.sig_uf == sig_uf.upper())
        if busca:
            query = query.where(GeracaoDistribuida.nom_municipio.ilike(f"%{busca}%"))

        query = query.limit(limit)
        result = await db.execute(query)

        return [
            {"nom_municipio": r[0], "sig_uf": r[1], "total": r[2]}
            for r in result.all()
        ]
