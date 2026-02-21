"""Serviço para consultar resultados de matching B3 -> CNPJ.

Opera nas tabelas b3_clientes e b3_cnpj_matches (separadas do ANEEL).
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class B3MatchingService:
    """Consulta resultados de matching entre B3 e CNPJ."""

    @staticmethod
    async def get_stats(db: AsyncSession) -> dict:
        """Retorna estatísticas do matching B3."""
        result = await db.execute(text("""
            WITH approx AS (
                SELECT reltuples::bigint as cnt
                FROM pg_class WHERE relname = 'b3_clientes'
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
                FROM b3_cnpj_matches
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
    async def batch_lookup(db: AsyncSession, cod_ids: list[str]) -> dict:
        """Retorna o melhor match (rank=1) para uma lista de cod_ids B3.

        Usado para enriquecer dados B3 com info de CNPJ na ConsultaB3Page/MapaB3Page.
        """
        if not cod_ids:
            return {}

        result = await db.execute(text("""
            SELECT bdgd_cod_id, cnpj, score_total, razao_social, nome_fantasia,
                   cnpj_telefone, cnpj_email, cnpj_logradouro, cnpj_numero,
                   cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf,
                   cnpj_cnae, cnpj_cnae_descricao, cnpj_situacao, address_source
            FROM b3_cnpj_matches
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
        """Retorna detalhes de um cliente B3 com todos os seus matches."""
        cliente_sql = """
            SELECT cod_id, lgrd_original, brr_original, cep_original, cnae_original,
                   municipio_nome, uf, clas_sub, gru_tar,
                   consumo_anual, consumo_medio, dic_anual, fic_anual,
                   car_inst, fas_con, sit_ativ,
                   possui_solar, point_x, point_y,
                   geo_logradouro, geo_bairro, geo_cep, geo_municipio, geo_uf
            FROM b3_clientes
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
                   cnpj_telefone, cnpj_email, address_source
            FROM b3_cnpj_matches
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
            "consumo_anual": float(crow[9]) if crow[9] else None,
            "consumo_medio": float(crow[10]) if crow[10] else None,
            "dic_anual": float(crow[11]) if crow[11] else None,
            "fic_anual": float(crow[12]) if crow[12] else None,
            "car_inst": float(crow[13]) if crow[13] else None,
            "fas_con": crow[14],
            "sit_ativ": crow[15],
            "possui_solar": crow[16],
            "point_x": crow[17],
            "point_y": crow[18],
            "best_score": float(matches[0]["score_total"]) if matches else None,
            "geo_logradouro": crow[19],
            "geo_bairro": crow[20],
            "geo_cep": crow[21],
            "geo_municipio": crow[22],
            "geo_uf": crow[23],
            "matches": matches,
        }

    @staticmethod
    async def populate_b3_clientes(db: AsyncSession, parquet_path: str = None) -> dict:
        """Popula tabela b3_clientes a partir do parquet B3.

        Extrai dados do parquet e insere/atualiza na tabela b3_clientes
        para viabilizar o matching com CNPJ.
        """
        import re
        import pandas as pd
        from pathlib import Path

        if parquet_path is None:
            from app.core.config import settings
            parquet_path = str(Path(settings.DATA_DIR) / "dados_b3.parquet")

        df = pd.read_parquet(parquet_path)
        logger.info(f"[B3 Populate] Carregados {len(df)} registros do parquet")

        def normalizar_texto(texto):
            if not texto or pd.isna(texto):
                return None
            t = str(texto).strip().upper()
            t = re.sub(r"[^\w\s]", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            return t or None

        def normalizar_cep(cep):
            if not cep or pd.isna(cep):
                return None
            return re.sub(r"\D", "", str(cep).strip())[:8] or None

        def extrair_numero(logradouro):
            if not logradouro or pd.isna(logradouro):
                return None
            m = re.search(r"\b(\d+)\s*$", str(logradouro).strip())
            return m.group(1) if m else None

        inserted = 0
        batch_size = 500
        batch = []

        for _, row in df.iterrows():
            cod_id = row.get("COD_ID_ENCR")
            if not cod_id or pd.isna(cod_id):
                continue

            lgrd = str(row.get("LGRD", "")) if row.get("LGRD") and not pd.isna(row.get("LGRD")) else None
            brr = str(row.get("BRR", "")) if row.get("BRR") and not pd.isna(row.get("BRR")) else None
            cep = str(row.get("CEP", "")) if row.get("CEP") and not pd.isna(row.get("CEP")) else None
            cnae = str(row.get("CNAE", "")) if row.get("CNAE") and not pd.isna(row.get("CNAE")) else None

            logradouro_norm = normalizar_texto(lgrd)
            numero_norm = extrair_numero(lgrd)
            bairro_norm = normalizar_texto(brr)
            cep_norm = normalizar_cep(cep)
            cnae_norm = re.sub(r"\D", "", cnae)[:7] if cnae else None
            cnae_5dig = cnae_norm[:5] if cnae_norm and len(cnae_norm) >= 5 else None

            mun = str(row.get("MUN", "")) if row.get("MUN") and not pd.isna(row.get("MUN")) else None
            nome_mun = str(row.get("Nome_Município", "")) if row.get("Nome_Município") and not pd.isna(row.get("Nome_Município")) else None
            nome_uf = str(row.get("Nome_UF", "")) if row.get("Nome_UF") and not pd.isna(row.get("Nome_UF")) else None

            batch.append({
                "cod_id": str(cod_id),
                "lgrd_original": lgrd,
                "brr_original": brr,
                "cep_original": cep,
                "cnae_original": cnae,
                "logradouro_norm": logradouro_norm,
                "numero_norm": numero_norm,
                "bairro_norm": bairro_norm,
                "cep_norm": cep_norm,
                "cnae_norm": cnae_norm,
                "cnae_5dig": cnae_5dig,
                "mun_code": mun,
                "municipio_nome": normalizar_texto(nome_mun),
                "uf": str(nome_uf).upper()[:2] if nome_uf else None,
                "point_x": float(row.get("POINT_X")) if row.get("POINT_X") and not pd.isna(row.get("POINT_X")) else None,
                "point_y": float(row.get("POINT_Y")) if row.get("POINT_Y") and not pd.isna(row.get("POINT_Y")) else None,
                "clas_sub": str(row.get("CLAS_SUB", "")) if row.get("CLAS_SUB") and not pd.isna(row.get("CLAS_SUB")) else None,
                "gru_tar": str(row.get("GRU_TAR", "")) if row.get("GRU_TAR") and not pd.isna(row.get("GRU_TAR")) else None,
                "consumo_anual": float(row.get("CONSUMO_ANUAL")) if row.get("CONSUMO_ANUAL") and not pd.isna(row.get("CONSUMO_ANUAL")) else None,
                "consumo_medio": float(row.get("CONSUMO_MEDIO")) if row.get("CONSUMO_MEDIO") and not pd.isna(row.get("CONSUMO_MEDIO")) else None,
                "car_inst": float(row.get("CAR_INST")) if row.get("CAR_INST") and not pd.isna(row.get("CAR_INST")) else None,
                "fas_con": str(row.get("FAS_CON", "")) if row.get("FAS_CON") and not pd.isna(row.get("FAS_CON")) else None,
                "sit_ativ": str(row.get("SIT_ATIV", "")) if row.get("SIT_ATIV") and not pd.isna(row.get("SIT_ATIV")) else None,
                "dic_anual": float(row.get("DIC_ANUAL")) if row.get("DIC_ANUAL") and not pd.isna(row.get("DIC_ANUAL")) else None,
                "fic_anual": float(row.get("FIC_ANUAL")) if row.get("FIC_ANUAL") and not pd.isna(row.get("FIC_ANUAL")) else None,
                "possui_solar": bool(row.get("POSSUI_SOLAR")),
            })

            if len(batch) >= batch_size:
                await _insert_batch(db, batch)
                inserted += len(batch)
                batch = []

        if batch:
            await _insert_batch(db, batch)
            inserted += len(batch)

        await db.commit()
        logger.info(f"[B3 Populate] Inseridos {inserted} clientes em b3_clientes")
        return {"inserted": inserted}


async def _insert_batch(db: AsyncSession, batch: list[dict]):
    """Insere um batch de clientes na tabela b3_clientes."""
    for item in batch:
        await db.execute(text("""
            INSERT INTO b3_clientes (
                cod_id, lgrd_original, brr_original, cep_original, cnae_original,
                logradouro_norm, numero_norm, bairro_norm, cep_norm,
                cnae_norm, cnae_5dig,
                mun_code, municipio_nome, uf, point_x, point_y,
                clas_sub, gru_tar, consumo_anual, consumo_medio,
                car_inst, fas_con, sit_ativ, dic_anual, fic_anual, possui_solar
            ) VALUES (
                :cod_id, :lgrd_original, :brr_original, :cep_original, :cnae_original,
                :logradouro_norm, :numero_norm, :bairro_norm, :cep_norm,
                :cnae_norm, :cnae_5dig,
                :mun_code, :municipio_nome, :uf, :point_x, :point_y,
                :clas_sub, :gru_tar, :consumo_anual, :consumo_medio,
                :car_inst, :fas_con, :sit_ativ, :dic_anual, :fic_anual, :possui_solar
            )
            ON CONFLICT (cod_id) DO UPDATE SET
                lgrd_original = EXCLUDED.lgrd_original,
                brr_original = EXCLUDED.brr_original,
                cep_original = EXCLUDED.cep_original,
                cnae_original = EXCLUDED.cnae_original,
                logradouro_norm = EXCLUDED.logradouro_norm,
                numero_norm = EXCLUDED.numero_norm,
                bairro_norm = EXCLUDED.bairro_norm,
                cep_norm = EXCLUDED.cep_norm,
                cnae_norm = EXCLUDED.cnae_norm,
                cnae_5dig = EXCLUDED.cnae_5dig,
                mun_code = EXCLUDED.mun_code,
                municipio_nome = EXCLUDED.municipio_nome,
                uf = EXCLUDED.uf,
                point_x = EXCLUDED.point_x,
                point_y = EXCLUDED.point_y,
                clas_sub = EXCLUDED.clas_sub,
                gru_tar = EXCLUDED.gru_tar,
                consumo_anual = EXCLUDED.consumo_anual,
                consumo_medio = EXCLUDED.consumo_medio,
                car_inst = EXCLUDED.car_inst,
                fas_con = EXCLUDED.fas_con,
                sit_ativ = EXCLUDED.sit_ativ,
                dic_anual = EXCLUDED.dic_anual,
                fic_anual = EXCLUDED.fic_anual,
                possui_solar = EXCLUDED.possui_solar
        """), item)
