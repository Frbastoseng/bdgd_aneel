"""Serviço para listas de prospecção B3."""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_UNIDADES_POR_LISTA = 10000


class B3ListaService:
    """CRUD para listas de prospecção B3."""

    @staticmethod
    async def listar(db: AsyncSession, user_id: int) -> list[dict]:
        """Lista todas as listas do usuário com contagem de UCs."""
        result = await db.execute(text("""
            SELECT l.id, l.nome, l.descricao, l.filtros_aplicados,
                   l.created_at, l.updated_at,
                   COUNT(u.cod_id) as total_unidades
            FROM b3_listas_prospeccao l
            LEFT JOIN b3_lista_unidades u ON u.lista_id = l.id
            WHERE l.user_id = :user_id
            GROUP BY l.id
            ORDER BY l.updated_at DESC
        """), {"user_id": user_id})

        listas = []
        for row in result.fetchall():
            listas.append({
                "id": row[0],
                "nome": row[1],
                "descricao": row[2],
                "filtros_aplicados": json.loads(row[3]) if row[3] else {},
                "created_at": row[4].isoformat() if row[4] else None,
                "updated_at": row[5].isoformat() if row[5] else None,
                "total_unidades": row[6] or 0,
            })
        return listas

    @staticmethod
    async def criar(
        db: AsyncSession, user_id: int,
        nome: str, descricao: Optional[str] = None,
        filtros_aplicados: Optional[dict] = None
    ) -> dict:
        """Cria uma nova lista de prospecção."""
        result = await db.execute(text("""
            INSERT INTO b3_listas_prospeccao (nome, descricao, user_id, filtros_aplicados)
            VALUES (:nome, :descricao, :user_id, :filtros)
            RETURNING id, created_at
        """), {
            "nome": nome,
            "descricao": descricao,
            "user_id": user_id,
            "filtros": json.dumps(filtros_aplicados or {}),
        })
        row = result.fetchone()
        await db.commit()

        return {
            "id": row[0],
            "nome": nome,
            "descricao": descricao,
            "created_at": row[1].isoformat() if row[1] else None,
            "total_unidades": 0,
        }

    @staticmethod
    async def detalhe(db: AsyncSession, lista_id: int, user_id: int) -> Optional[dict]:
        """Retorna detalhes de uma lista com suas UCs."""
        result = await db.execute(text("""
            SELECT id, nome, descricao, filtros_aplicados, created_at, updated_at
            FROM b3_listas_prospeccao
            WHERE id = :id AND user_id = :user_id
        """), {"id": lista_id, "user_id": user_id})
        row = result.fetchone()
        if not row:
            return None

        # Buscar UCs da lista
        ucs_result = await db.execute(text("""
            SELECT cod_id, added_at
            FROM b3_lista_unidades
            WHERE lista_id = :lista_id
            ORDER BY added_at DESC
        """), {"lista_id": lista_id})

        unidades = [{"cod_id": r[0], "added_at": r[1].isoformat() if r[1] else None}
                     for r in ucs_result.fetchall()]

        return {
            "id": row[0],
            "nome": row[1],
            "descricao": row[2],
            "filtros_aplicados": json.loads(row[3]) if row[3] else {},
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
            "total_unidades": len(unidades),
            "unidades": unidades,
        }

    @staticmethod
    async def adicionar_unidades(
        db: AsyncSession, lista_id: int, user_id: int, cod_ids: list[str]
    ) -> dict:
        """Adiciona UCs a uma lista."""
        # Verificar propriedade
        check = await db.execute(text("""
            SELECT id FROM b3_listas_prospeccao WHERE id = :id AND user_id = :user_id
        """), {"id": lista_id, "user_id": user_id})
        if not check.fetchone():
            return {"error": "Lista não encontrada"}

        # Verificar limite
        count_result = await db.execute(text("""
            SELECT COUNT(*) FROM b3_lista_unidades WHERE lista_id = :lista_id
        """), {"lista_id": lista_id})
        current_count = count_result.scalar() or 0

        if current_count + len(cod_ids) > MAX_UNIDADES_POR_LISTA:
            return {"error": f"Limite de {MAX_UNIDADES_POR_LISTA} unidades por lista excedido"}

        added = 0
        for cod_id in cod_ids:
            try:
                await db.execute(text("""
                    INSERT INTO b3_lista_unidades (lista_id, cod_id)
                    VALUES (:lista_id, :cod_id)
                    ON CONFLICT DO NOTHING
                """), {"lista_id": lista_id, "cod_id": cod_id})
                added += 1
            except Exception:
                pass

        # Atualizar timestamp
        await db.execute(text("""
            UPDATE b3_listas_prospeccao SET updated_at = NOW() WHERE id = :id
        """), {"id": lista_id})

        await db.commit()
        return {"added": added, "total": current_count + added}

    @staticmethod
    async def remover_unidades(
        db: AsyncSession, lista_id: int, user_id: int, cod_ids: list[str]
    ) -> dict:
        """Remove UCs de uma lista."""
        check = await db.execute(text("""
            SELECT id FROM b3_listas_prospeccao WHERE id = :id AND user_id = :user_id
        """), {"id": lista_id, "user_id": user_id})
        if not check.fetchone():
            return {"error": "Lista não encontrada"}

        placeholders = ", ".join([f":id_{i}" for i in range(len(cod_ids))])
        params = {f"id_{i}": cid for i, cid in enumerate(cod_ids)}
        params["lista_id"] = lista_id

        result = await db.execute(text(f"""
            DELETE FROM b3_lista_unidades
            WHERE lista_id = :lista_id AND cod_id IN ({placeholders})
        """), params)

        await db.execute(text("""
            UPDATE b3_listas_prospeccao SET updated_at = NOW() WHERE id = :id
        """), {"id": lista_id})

        await db.commit()
        return {"removed": result.rowcount}

    @staticmethod
    async def excluir(db: AsyncSession, lista_id: int, user_id: int) -> bool:
        """Exclui uma lista (CASCADE remove unidades)."""
        result = await db.execute(text("""
            DELETE FROM b3_listas_prospeccao WHERE id = :id AND user_id = :user_id
        """), {"id": lista_id, "user_id": user_id})
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def salvar_filtro_como_lista(
        db: AsyncSession, user_id: int,
        nome: str, descricao: Optional[str],
        filtros: dict, cod_ids: list[str]
    ) -> dict:
        """Cria lista a partir de um filtro, adicionando até 10.000 UCs."""
        cod_ids = cod_ids[:MAX_UNIDADES_POR_LISTA]

        result = await db.execute(text("""
            INSERT INTO b3_listas_prospeccao (nome, descricao, user_id, filtros_aplicados)
            VALUES (:nome, :descricao, :user_id, :filtros)
            RETURNING id
        """), {
            "nome": nome,
            "descricao": descricao,
            "user_id": user_id,
            "filtros": json.dumps(filtros),
        })
        lista_id = result.fetchone()[0]

        added = 0
        for cod_id in cod_ids:
            try:
                await db.execute(text("""
                    INSERT INTO b3_lista_unidades (lista_id, cod_id)
                    VALUES (:lista_id, :cod_id)
                    ON CONFLICT DO NOTHING
                """), {"lista_id": lista_id, "cod_id": cod_id})
                added += 1
            except Exception:
                pass

        await db.commit()
        return {"id": lista_id, "nome": nome, "total_unidades": added}

    @staticmethod
    async def exportar_csv(db: AsyncSession, lista_id: int, user_id: int) -> Optional[bytes]:
        """Exporta uma lista como CSV com dados do parquet."""
        check = await db.execute(text("""
            SELECT id FROM b3_listas_prospeccao WHERE id = :id AND user_id = :user_id
        """), {"id": lista_id, "user_id": user_id})
        if not check.fetchone():
            return None

        ucs_result = await db.execute(text("""
            SELECT cod_id FROM b3_lista_unidades WHERE lista_id = :lista_id
        """), {"lista_id": lista_id})
        cod_ids = [r[0] for r in ucs_result.fetchall()]

        if not cod_ids:
            return None

        from app.services.b3_service import B3Service
        import pandas as pd

        df = B3Service.carregar_dados_processados()
        if df.empty:
            return None

        df_lista = df[df["COD_ID_ENCR"].isin(cod_ids)]
        if df_lista.empty:
            return None

        return B3Service.exportar_csv(df_lista)
