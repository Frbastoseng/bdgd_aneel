"""
Serviço de refinamento para B3: geocodifica coordenadas e re-faz matching
para clientes B3 (opera nas tabelas b3_clientes / b3_cnpj_matches).

Reutiliza as funções utilitárias do refine_service original.
"""

import logging
import re
import asyncio
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.refine_service import (
    _normalizar_texto,
    _normalizar_cep,
    _round_coord,
    _reverse_geocode,
    _score_endereco,
    COORD_PRECISION,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

MAX_CLIENTES = 100


class B3RefineService:
    """Geocodifica e re-faz matching sob demanda para clientes B3."""

    @staticmethod
    async def refine_clientes(db: AsyncSession, cod_ids: list[str]) -> dict:
        """
        Para cada cod_id B3:
          1. Verifica se já tem geocode no cache, senão geocodifica
          2. Atualiza geo_* em b3_clientes
          3. Re-calcula matching com dupla fonte
          4. Retorna resultados atualizados
        """
        cod_ids = cod_ids[:MAX_CLIENTES]
        if not cod_ids:
            return {"refined": 0, "geocoded": 0, "improved": 0}

        # 1. Buscar clientes com coordenadas
        placeholders = ", ".join([f":id_{i}" for i in range(len(cod_ids))])
        params = {f"id_{i}": cid for i, cid in enumerate(cod_ids)}

        result = await db.execute(text(f"""
            SELECT cod_id, point_x, point_y,
                   logradouro_norm, numero_norm, bairro_norm,
                   cep_norm, cnae_norm, cnae_5dig, municipio_nome, uf,
                   geo_logradouro, geo_numero, geo_bairro, geo_cep, geo_status
            FROM b3_clientes
            WHERE cod_id IN ({placeholders})
              AND point_x IS NOT NULL AND point_y IS NOT NULL
              AND point_x != 0 AND point_y != 0
        """), params)
        clientes = result.fetchall()

        if not clientes:
            return {"refined": 0, "geocoded": 0, "improved": 0}

        # 2. Agrupar coordenadas únicas que precisam geocodificar
        coords_to_geocode = {}
        for c in clientes:
            if c[15] == "success":  # geo_status
                continue
            lat_r = _round_coord(c[2])  # point_y
            lon_r = _round_coord(c[1])  # point_x
            if (lat_r, lon_r) not in coords_to_geocode:
                coords_to_geocode[(lat_r, lon_r)] = (c[2], c[1])

        # 3. Verificar cache existente (reutiliza geocode_cache)
        geocoded_results = {}
        if coords_to_geocode:
            for (lat_r, lon_r), (lat, lon) in list(coords_to_geocode.items()):
                cache_result = await db.execute(text("""
                    SELECT logradouro, numero, bairro, cep, municipio, uf, status
                    FROM geocode_cache
                    WHERE lat_round = :lat_r AND lon_round = :lon_r AND status = 'success'
                """), {"lat_r": lat_r, "lon_r": lon_r})
                row = cache_result.fetchone()
                if row:
                    geocoded_results[(lat_r, lon_r)] = {
                        "logradouro": _normalizar_texto(row[0]),
                        "numero": row[1],
                        "bairro": _normalizar_texto(row[2]),
                        "cep": row[3],
                        "municipio": _normalizar_texto(row[4]),
                        "uf": row[5],
                    }
                    del coords_to_geocode[(lat_r, lon_r)]

        # 4. Geocodificar pendentes via Nominatim
        geocoded_count = 0
        if coords_to_geocode:
            async with httpx.AsyncClient(
                timeout=15, headers={"User-Agent": USER_AGENT}
            ) as http_client:
                for (lat_r, lon_r), (lat, lon) in coords_to_geocode.items():
                    geo = await _reverse_geocode(http_client, lat, lon)
                    if geo["status"] == "success":
                        geocoded_results[(lat_r, lon_r)] = geo
                        geocoded_count += 1
                        await db.execute(text("""
                            INSERT INTO geocode_cache
                                (lat_round, lon_round, lat_original, lon_original,
                                 logradouro, numero, bairro, cep, municipio, uf,
                                 status, source, updated_at)
                            VALUES (:lat_r, :lon_r, :lat, :lon,
                                    :logr, :num, :brr, :cep, :mun, :uf,
                                    'success', 'nominatim', NOW())
                            ON CONFLICT (lat_round, lon_round) DO UPDATE SET
                                logradouro = EXCLUDED.logradouro,
                                numero = EXCLUDED.numero,
                                bairro = EXCLUDED.bairro,
                                cep = EXCLUDED.cep,
                                municipio = EXCLUDED.municipio,
                                uf = EXCLUDED.uf,
                                status = 'success',
                                updated_at = NOW()
                        """), {
                            "lat_r": lat_r, "lon_r": lon_r, "lat": lat, "lon": lon,
                            "logr": geo.get("logradouro"), "num": geo.get("numero"),
                            "brr": geo.get("bairro"), "cep": geo.get("cep"),
                            "mun": geo.get("municipio"), "uf": geo.get("uf"),
                        })
                    await asyncio.sleep(1.1)

        # 5. Atualizar geo_* em b3_clientes
        for c in clientes:
            lat_r = _round_coord(c[2])
            lon_r = _round_coord(c[1])
            geo = geocoded_results.get((lat_r, lon_r))
            if geo:
                await db.execute(text("""
                    UPDATE b3_clientes SET
                        geo_logradouro = :logr, geo_numero = :num, geo_bairro = :brr,
                        geo_cep = :cep, geo_municipio = :mun, geo_uf = :uf,
                        geo_source = 'nominatim', geo_status = 'success'
                    WHERE cod_id = :cod_id
                """), {
                    "logr": geo.get("logradouro"), "num": geo.get("numero"),
                    "brr": geo.get("bairro"), "cep": geo.get("cep"),
                    "mun": geo.get("municipio"), "uf": geo.get("uf"),
                    "cod_id": c[0],
                })

        # 6. Re-calcular matching para esses clientes
        improved = 0
        for c in clientes:
            cod_id = c[0]
            logr_norm, num_norm, bairro_norm = c[3], c[4], c[5]
            cep_norm, cnae_norm, cnae_5dig, mun_nome = c[6], c[7], c[8], c[9]

            lat_r = _round_coord(c[2])
            lon_r = _round_coord(c[1])
            geo = geocoded_results.get((lat_r, lon_r))

            geo_logr = geo.get("logradouro") if geo else c[11]
            geo_num = geo.get("numero") if geo else c[12]
            geo_brr = geo.get("bairro") if geo else c[13]
            geo_cep = geo.get("cep") if geo else c[14]

            # Buscar candidatos CNPJ
            ceps_busca = set()
            if cep_norm:
                ceps_busca.add(cep_norm)
            if geo_cep and geo_cep != cep_norm:
                ceps_busca.add(geo_cep)

            if not ceps_busca:
                continue

            candidatos = []
            cnpjs_vistos = set()
            for cep_busca in ceps_busca:
                rows = await db.execute(text("""
                    SELECT cnpj, razao_social, nome_fantasia,
                           logradouro, numero, bairro, cep,
                           municipio, uf, cnae_fiscal, cnae_fiscal_descricao,
                           situacao_cadastral, telefone_1, email
                    FROM cnpj_cache
                    WHERE cep = :cep AND situacao_cadastral = 'ATIVA'
                    LIMIT 200
                """), {"cep": cep_busca})
                for row in rows.fetchall():
                    if row[0] not in cnpjs_vistos:
                        cnpjs_vistos.add(row[0])
                        candidatos.append(row)

            if len(candidatos) < 5 and mun_nome and cnae_norm:
                rows = await db.execute(text("""
                    SELECT cnpj, razao_social, nome_fantasia,
                           logradouro, numero, bairro, cep,
                           municipio, uf, cnae_fiscal, cnae_fiscal_descricao,
                           situacao_cadastral, telefone_1, email
                    FROM cnpj_cache
                    WHERE UPPER(municipio) = :mun AND cnae_fiscal = :cnae
                      AND situacao_cadastral = 'ATIVA'
                    LIMIT 50
                """), {"mun": mun_nome, "cnae": cnae_norm})
                for row in rows.fetchall():
                    if row[0] not in cnpjs_vistos:
                        cnpjs_vistos.add(row[0])
                        candidatos.append(row)

            if not candidatos:
                continue

            # Pontuar com dupla fonte
            scored = []
            for cand in candidatos:
                c_cnpj, c_razao, c_fantasia = cand[0], cand[1], cand[2]
                c_logr, c_num, c_bairro, c_cep = cand[3], cand[4], cand[5], cand[6]
                c_mun, c_uf, c_cnae, c_cnae_desc = cand[7], cand[8], cand[9], cand[10]
                c_situacao, c_tel, c_email = cand[11], cand[12], cand[13]

                # CNAE score
                s_cnae = 0.0
                c_cnae_clean = re.sub(r"\D", "", c_cnae or "")[:7] if c_cnae else ""
                if cnae_norm and c_cnae_clean:
                    if cnae_norm == c_cnae_clean:
                        s_cnae = 25.0
                    elif cnae_5dig and c_cnae_clean[:5] == cnae_5dig:
                        s_cnae = 15.0

                # BDGD score
                b_cep, b_end, b_num, b_brr = _score_endereco(
                    logr_norm, num_norm, bairro_norm, cep_norm,
                    c_logr, c_num, c_bairro, c_cep)
                score_bdgd = b_cep + s_cnae + b_end + b_num + b_brr

                # Geocoded score
                addr_source = "bdgd"
                score_geo = 0.0
                g_scores = (0.0, 0.0, 0.0, 0.0)
                if geo_cep or geo_logr:
                    g_scores = _score_endereco(
                        geo_logr, geo_num, geo_brr, geo_cep,
                        c_logr, c_num, c_bairro, c_cep)
                    score_geo = g_scores[0] + s_cnae + g_scores[1] + g_scores[2] + g_scores[3]

                if score_geo > score_bdgd:
                    s_cep, s_end, s_num, s_brr = g_scores
                    total_score = score_geo
                    addr_source = "geocoded"
                else:
                    s_cep, s_end, s_num, s_brr = b_cep, b_end, b_num, b_brr
                    total_score = score_bdgd

                if total_score >= 15:
                    scored.append((
                        total_score, s_cep, s_cnae, s_end, s_num, s_brr,
                        c_cnpj, c_razao, c_fantasia, c_logr, c_num,
                        c_bairro, c_cep, c_mun, c_uf, c_cnae,
                        c_cnae_desc, c_situacao, c_tel, c_email, addr_source,
                    ))

            if not scored:
                continue

            # Guardar old best score
            old_best = await db.execute(text("""
                SELECT score_total FROM b3_cnpj_matches
                WHERE bdgd_cod_id = :cod_id AND rank = 1
            """), {"cod_id": cod_id})
            old_row = old_best.fetchone()
            old_score = float(old_row[0]) if old_row else 0

            # Deletar matches antigos e inserir novos
            await db.execute(text(
                "DELETE FROM b3_cnpj_matches WHERE bdgd_cod_id = :cod_id"
            ), {"cod_id": cod_id})

            scored.sort(key=lambda x: x[0], reverse=True)
            for rank, s in enumerate(scored[:3], 1):
                await db.execute(text("""
                    INSERT INTO b3_cnpj_matches (
                        bdgd_cod_id, cnpj, score_total,
                        score_cep, score_cnae, score_endereco, score_numero, score_bairro,
                        rank, razao_social, nome_fantasia, cnpj_logradouro, cnpj_numero,
                        cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf, cnpj_cnae,
                        cnpj_cnae_descricao, cnpj_situacao, cnpj_telefone, cnpj_email,
                        address_source
                    ) VALUES (
                        :cod_id, :cnpj, :score, :s_cep, :s_cnae, :s_end, :s_num, :s_brr,
                        :rank, :razao, :fantasia, :logr, :num, :brr, :cep, :mun, :uf,
                        :cnae, :cnae_desc, :sit, :tel, :email, :addr_src
                    )
                """), {
                    "cod_id": cod_id, "cnpj": s[6], "score": s[0],
                    "s_cep": s[1], "s_cnae": s[2], "s_end": s[3],
                    "s_num": s[4], "s_brr": s[5], "rank": rank,
                    "razao": s[7], "fantasia": s[8], "logr": s[9], "num": s[10],
                    "brr": s[11], "cep": s[12], "mun": s[13], "uf": s[14],
                    "cnae": s[15], "cnae_desc": s[16], "sit": s[17],
                    "tel": s[18], "email": s[19], "addr_src": s[20],
                })

            new_score = scored[0][0]
            if new_score > old_score:
                improved += 1

        await db.commit()

        return {
            "refined": len(clientes),
            "geocoded": geocoded_count,
            "improved": improved,
        }
