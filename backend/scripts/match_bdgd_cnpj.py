"""
Script para matching entre clientes BDGD e base de CNPJ.

Metodologia:
  1. Carrega dados do parquet BDGD em tabela normalizada (bdgd_clientes)
  2. Para cada cliente BDGD, busca CNPJs candidatos por CEP (e municipio como fallback)
  3. Pontua cada candidato:
     - CEP exato:       40 pts
     - CNAE 7 digitos:  25 pts  (5 digitos: 15 pts)
     - Endereco similar: ate 20 pts (trigram similarity)
     - Numero exato:    10 pts
     - Bairro similar:   ate 5 pts (trigram similarity)
  4. Armazena os top N matches por cliente na tabela bdgd_cnpj_matches

Uso:
    python scripts/match_bdgd_cnpj.py [--top N] [--batch-size N] [--skip-load]

Executa dentro do container backend:
    docker exec bdgd_backend python scripts/match_bdgd_cnpj.py
"""

import argparse
import os
import re
import sys
import time
from typing import Optional

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values


# ──────────────────────────────────────────
# Configuracao
# ──────────────────────────────────────────

def _parse_db_url(url: str) -> dict:
    """Parse postgresql://user:pass@host:port/db into dict for psycopg2."""
    import re as _re
    m = _re.match(r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+?)(?:\?.*)?$", url)
    if m:
        return {"user": m[1], "password": m[2], "host": m[3], "port": int(m[4]), "dbname": m[5]}
    return {"host": "db", "port": 5432, "dbname": "bdgd_pro", "user": "bdgd", "password": "bdgd_secret_2024"}

_db_url = os.getenv("DATABASE_URL_SYNC", "")
DB = _parse_db_url(_db_url) if _db_url else {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "bdgd_pro"),
    "user": os.getenv("DB_USER", "bdgd"),
    "password": os.getenv("DB_PASSWORD", "bdgd_secret_2024"),
}

PARQUET_PATH = os.getenv("PARQUET_PATH", "/app/data/dados_aneel.parquet")
MUNICIPIOS_PATH = os.getenv("MUNICIPIOS_PATH", "/app/data/municipios.parquet")

# ──────────────────────────────────────────
# Normalizacao
# ──────────────────────────────────────────

def normalizar_cep(cep: Optional[str]) -> Optional[str]:
    """Remove formatacao do CEP: '13670-000' -> '13670000'."""
    if not cep:
        return None
    return re.sub(r"\D", "", str(cep).strip())[:8] or None


def normalizar_cnae(cnae: Optional[str]) -> Optional[str]:
    """Remove formatacao do CNAE: '2229-3/03' -> '2229303'."""
    if not cnae:
        return None
    return re.sub(r"\D", "", str(cnae).strip())[:7] or None


def parse_logradouro(lgrd: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Separa logradouro e numero do campo LGRD do BDGD.
    Ex: 'R IRINEU BIANCHINI, 257' -> ('R IRINEU BIANCHINI', '257')
    Ex: 'RDV WASHINGTON LUIZ, 667 B.RECALQUE' -> ('RDV WASHINGTON LUIZ', '667')
    """
    if not lgrd:
        return None, None

    lgrd = lgrd.strip()

    # Tentar separar por virgula
    if "," in lgrd:
        parts = lgrd.split(",", 1)
        rua = parts[0].strip()
        resto = parts[1].strip()
        # Extrair o numero do inicio do resto
        m = re.match(r"(\d+)", resto)
        numero = m.group(1) if m else None
        return rua, numero

    # Tentar extrair numero no final
    m = re.match(r"(.+?)\s+(\d+)\s*$", lgrd)
    if m:
        return m.group(1).strip(), m.group(2)

    return lgrd, None


def normalizar_texto(texto: Optional[str]) -> Optional[str]:
    """Normaliza texto para comparacao: upper, sem acentos, sem pontuacao extra."""
    if not texto:
        return None
    t = str(texto).strip().upper()
    # Remover pontuacao exceto espacos
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# ──────────────────────────────────────────
# Etapa 1: Carregar BDGD para PostgreSQL
# ──────────────────────────────────────────

def criar_tabelas(conn):
    """Cria tabelas se nao existirem."""
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bdgd_clientes (
                id BIGSERIAL PRIMARY KEY,
                cod_id VARCHAR(70) NOT NULL UNIQUE,
                lgrd_original VARCHAR(300),
                brr_original VARCHAR(200),
                cep_original VARCHAR(15),
                cnae_original VARCHAR(20),
                logradouro_norm VARCHAR(300),
                numero_norm VARCHAR(20),
                bairro_norm VARCHAR(200),
                cep_norm VARCHAR(8),
                cnae_norm VARCHAR(7),
                cnae_5dig VARCHAR(5),
                mun_code VARCHAR(7),
                municipio_nome VARCHAR(100),
                uf VARCHAR(2),
                point_x DOUBLE PRECISION,
                point_y DOUBLE PRECISION,
                clas_sub VARCHAR(10),
                gru_tar VARCHAR(10),
                dem_cont DOUBLE PRECISION,
                ene_max DOUBLE PRECISION,
                liv INTEGER,
                possui_solar BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS bdgd_cnpj_matches (
                id BIGSERIAL PRIMARY KEY,
                bdgd_cod_id VARCHAR(70) NOT NULL,
                cnpj VARCHAR(14) NOT NULL,
                score_total NUMERIC(6,2) DEFAULT 0,
                score_cep NUMERIC(5,2) DEFAULT 0,
                score_cnae NUMERIC(5,2) DEFAULT 0,
                score_endereco NUMERIC(5,2) DEFAULT 0,
                score_numero NUMERIC(5,2) DEFAULT 0,
                score_bairro NUMERIC(5,2) DEFAULT 0,
                rank INTEGER DEFAULT 1,
                razao_social VARCHAR(200),
                nome_fantasia VARCHAR(200),
                cnpj_logradouro VARCHAR(200),
                cnpj_numero VARCHAR(20),
                cnpj_bairro VARCHAR(100),
                cnpj_cep VARCHAR(10),
                cnpj_municipio VARCHAR(100),
                cnpj_uf VARCHAR(2),
                cnpj_cnae VARCHAR(10),
                cnpj_cnae_descricao VARCHAR(200),
                cnpj_situacao VARCHAR(50),
                cnpj_telefone VARCHAR(30),
                cnpj_email VARCHAR(200),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Indices
        for sql in [
            "CREATE INDEX IF NOT EXISTS idx_bdgd_cep_cnae ON bdgd_clientes (cep_norm, cnae_norm);",
            "CREATE INDEX IF NOT EXISTS idx_bdgd_municipio ON bdgd_clientes (municipio_nome);",
            "CREATE INDEX IF NOT EXISTS idx_bdgd_uf ON bdgd_clientes (uf);",
            "CREATE INDEX IF NOT EXISTS idx_match_cod_id_rank ON bdgd_cnpj_matches (bdgd_cod_id, rank);",
            "CREATE INDEX IF NOT EXISTS idx_match_score ON bdgd_cnpj_matches (score_total);",
            "CREATE INDEX IF NOT EXISTS idx_match_cnpj ON bdgd_cnpj_matches (cnpj);",
            # Indice em cnpj_cache para matching por CEP (se nao existir)
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_cep ON cnpj_cache (cep);",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_cnae ON cnpj_cache (cnae_fiscal);",
            "CREATE INDEX IF NOT EXISTS idx_cnpj_cache_municipio_upper ON cnpj_cache (UPPER(municipio));",
        ]:
            cur.execute(sql)

    conn.commit()


def carregar_bdgd(conn, parquet_path: str, municipios_path: str, batch_size: int = 5000):
    """Carrega e normaliza dados BDGD do parquet para PostgreSQL."""
    print("\n[CARGA] Carregando parquet BDGD...")
    df = pd.read_parquet(parquet_path)
    print(f"         {fmt_num(len(df))} registros carregados do parquet")

    # Carregar municipios para mapear codigo -> nome
    print("[CARGA] Carregando municipios...")
    mun_df = pd.read_parquet(municipios_path)
    # Pegar municipio unico (sem distritos duplicados)
    mun_map = (
        mun_df[["Código Município Completo", "Nome_Município", "Nome_UF"]]
        .drop_duplicates(subset=["Código Município Completo"])
        .set_index("Código Município Completo")
    )
    print(f"         {len(mun_map)} municipios mapeados")

    # UF sigla de Nome_UF
    uf_map = {
        "Acre": "AC", "Alagoas": "AL", "Amapá": "AP", "Amazonas": "AM",
        "Bahia": "BA", "Ceará": "CE", "Distrito Federal": "DF",
        "Espírito Santo": "ES", "Goiás": "GO", "Maranhão": "MA",
        "Mato Grosso": "MT", "Mato Grosso do Sul": "MS", "Minas Gerais": "MG",
        "Pará": "PA", "Paraíba": "PB", "Paraná": "PR", "Pernambuco": "PE",
        "Piauí": "PI", "Rio de Janeiro": "RJ", "Rio Grande do Norte": "RN",
        "Rio Grande do Sul": "RS", "Rondônia": "RO", "Roraima": "RR",
        "Santa Catarina": "SC", "São Paulo": "SP", "Sergipe": "SE",
        "Tocantins": "TO",
    }

    # Limpar tabela existente
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM bdgd_clientes")
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"[CARGA] Limpando {fmt_num(existing)} registros existentes...")
            cur.execute("TRUNCATE bdgd_clientes RESTART IDENTITY")
            conn.commit()

    # Normalizar e inserir
    print("[CARGA] Normalizando e inserindo dados...")
    start = time.time()
    inserted = 0

    insert_sql = """
        INSERT INTO bdgd_clientes (
            cod_id, lgrd_original, brr_original, cep_original, cnae_original,
            logradouro_norm, numero_norm, bairro_norm, cep_norm, cnae_norm, cnae_5dig,
            mun_code, municipio_nome, uf, point_x, point_y,
            clas_sub, gru_tar, dem_cont, ene_max, liv, possui_solar
        ) VALUES %s ON CONFLICT (cod_id) DO NOTHING
    """

    batch = []
    for idx, row in df.iterrows():
        cod_id = str(row.get("COD_ID_ENCR", row.get("COD_ID", f"row_{idx}")))
        lgrd = str(row.get("LGRD", "")) if pd.notna(row.get("LGRD")) else None
        brr = str(row.get("BRR", "")) if pd.notna(row.get("BRR")) else None
        cep = str(row.get("CEP", "")) if pd.notna(row.get("CEP")) else None
        cnae = str(row.get("CNAE", "")) if pd.notna(row.get("CNAE")) else None
        mun_code = str(row.get("MUN", "")) if pd.notna(row.get("MUN")) else None

        # Normalizar
        logradouro_norm, numero_norm = parse_logradouro(lgrd)
        logradouro_norm = normalizar_texto(logradouro_norm)
        bairro_norm = normalizar_texto(brr)
        cep_norm = normalizar_cep(cep)
        cnae_norm = normalizar_cnae(cnae)
        cnae_5dig = cnae_norm[:5] if cnae_norm and len(cnae_norm) >= 5 else None

        # Municipio
        municipio_nome = None
        uf = None
        if mun_code and mun_code in mun_map.index:
            mun_row = mun_map.loc[mun_code]
            municipio_nome = normalizar_texto(str(mun_row["Nome_Município"]))
            uf_nome = str(mun_row["Nome_UF"])
            uf = uf_map.get(uf_nome)

        # Coordenadas
        try:
            point_x = float(row.get("POINT_X", 0))
            point_y = float(row.get("POINT_Y", 0))
        except (ValueError, TypeError):
            point_x, point_y = None, None

        # Dados do cliente
        clas_sub = str(row.get("CLAS_SUB", "")) if pd.notna(row.get("CLAS_SUB")) else None
        gru_tar = str(row.get("GRU_TAR", "")) if pd.notna(row.get("GRU_TAR")) else None

        try:
            dem_cont = float(row.get("DEM_CONT", 0))
        except (ValueError, TypeError):
            dem_cont = 0

        # Calcular energia maxima
        ene_vals = []
        for m in range(1, 13):
            try:
                v = float(row.get(f"ENE_{m:02d}", 0))
                ene_vals.append(v)
            except (ValueError, TypeError):
                pass
        ene_max = max(ene_vals) if ene_vals else 0

        try:
            liv = int(float(row.get("LIV", 0)))
        except (ValueError, TypeError):
            liv = 0

        ceg_gd = str(row.get("CEG_GD", "")) if pd.notna(row.get("CEG_GD")) else ""
        possui_solar = bool(ceg_gd and ceg_gd.strip() != "")

        batch.append((
            cod_id, lgrd, brr, cep, cnae,
            logradouro_norm, numero_norm, bairro_norm, cep_norm, cnae_norm, cnae_5dig,
            mun_code, municipio_nome, uf, point_x, point_y,
            clas_sub, gru_tar, dem_cont, ene_max, liv, possui_solar,
        ))

        if len(batch) >= batch_size:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, batch, page_size=len(batch))
                inserted += cur.rowcount
            conn.commit()
            batch = []

            elapsed = time.time() - start
            rate = inserted / elapsed if elapsed > 0 else 0
            pct = inserted / len(df) * 100
            print(
                f"         {fmt_num(inserted)}/{fmt_num(len(df))} ({pct:.1f}%) - {rate:.0f} reg/s",
                end="\r",
            )

    # Ultimo lote
    if batch:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, batch, page_size=len(batch))
            inserted += cur.rowcount
        conn.commit()

    elapsed = time.time() - start
    print(f"\n         {fmt_num(inserted)} registros inseridos em {elapsed:.1f}s")
    return inserted


# ──────────────────────────────────────────
# Etapa 2: Matching
# ──────────────────────────────────────────

def _score_endereco(logr_ref, num_ref, bairro_ref, cep_ref, c_logr, c_num, c_bairro, c_cep):
    """
    Pontua um candidato CNPJ contra um endereço de referência.
    Retorna (s_cep, s_end, s_num, s_brr).
    """
    s_cep = 0.0
    s_end = 0.0
    s_num = 0.0
    s_brr = 0.0

    # Score CEP (40 pts)
    if cep_ref and c_cep and cep_ref == c_cep:
        s_cep = 40.0

    # Score endereco (ate 20 pts - similaridade Jaccard por palavras)
    if logr_ref and c_logr:
        c_logr_norm = normalizar_texto(c_logr)
        if c_logr_norm:
            palavras_ref = {p for p in logr_ref.split() if len(p) > 2}
            palavras_cnpj = {p for p in c_logr_norm.split() if len(p) > 2}
            if palavras_ref and palavras_cnpj:
                intersecao = palavras_ref & palavras_cnpj
                uniao = palavras_ref | palavras_cnpj
                jaccard = len(intersecao) / len(uniao)
                s_end = round(jaccard * 20.0, 2)

    # Score numero (10 pts)
    if num_ref and c_num:
        c_num_clean = re.sub(r"\D", "", c_num)
        if num_ref == c_num_clean:
            s_num = 10.0

    # Score bairro (ate 5 pts)
    if bairro_ref and c_bairro:
        c_bairro_norm = normalizar_texto(c_bairro)
        if c_bairro_norm:
            if bairro_ref == c_bairro_norm:
                s_brr = 5.0
            else:
                palavras_b = {p for p in bairro_ref.split() if len(p) > 2}
                palavras_c = {p for p in c_bairro_norm.split() if len(p) > 2}
                if palavras_b and palavras_c:
                    inter = palavras_b & palavras_c
                    if inter:
                        s_brr = round(len(inter) / max(len(palavras_b), len(palavras_c)) * 5.0, 2)

    return s_cep, s_end, s_num, s_brr


def executar_matching(conn, top_n: int = 3, batch_size: int = 1000):
    """
    Executa o matching BDGD -> CNPJ usando scoring multi-criterio com DUPLA FONTE
    de endereço: endereço original BDGD + endereço geocodificado (via coordenadas).

    Para cada cliente BDGD:
      1. Busca CNPJs candidatos por CEP (BDGD e/ou geocodificado)
      2. Se poucos, complementa com municipio + CNAE
      3. Pontua cada candidato usando AMBOS os endereços, ficando com o melhor
      4. Armazena os top N matches com indicação da fonte do endereço
    """
    print("\n[MATCHING] Iniciando matching (dupla fonte de endereco)...")

    # Limpar matches anteriores
    with conn.cursor() as cur:
        cur.execute("TRUNCATE bdgd_cnpj_matches RESTART IDENTITY")
    conn.commit()

    # Verificar se geocodificação existe
    has_geo = False
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM bdgd_clientes
            WHERE geo_status = 'success' AND geo_cep IS NOT NULL
        """)
        geo_count = cur.fetchone()[0]
        has_geo = geo_count > 0

    # Contar clientes (agora inclui quem tem CEP OU geo_cep)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM bdgd_clientes
            WHERE cep_norm IS NOT NULL OR geo_cep IS NOT NULL
        """)
        total = cur.fetchone()[0]

    print(f"           {fmt_num(total)} clientes com CEP para processar")
    if has_geo:
        print(f"           {fmt_num(geo_count)} clientes com endereco geocodificado (dupla fonte)")
    else:
        print("           [INFO] Sem geocodificacao. Execute geocode_bdgd.py para melhorar resultados.")

    start = time.time()
    matched = 0
    no_match = 0
    geo_improved = 0  # Contador de matches melhorados pela geocodificacao
    offset = 0

    while offset < total:
        # Buscar lote de clientes BDGD (inclui campos geocodificados)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_id, logradouro_norm, numero_norm, bairro_norm,
                       cep_norm, cnae_norm, cnae_5dig, municipio_nome, uf,
                       geo_logradouro, geo_numero, geo_bairro, geo_cep
                FROM bdgd_clientes
                WHERE cep_norm IS NOT NULL OR geo_cep IS NOT NULL
                ORDER BY id
                OFFSET %s LIMIT %s
            """, (offset, batch_size))
            clientes = cur.fetchall()

        if not clientes:
            break

        insert_batch = []

        for cliente in clientes:
            (cod_id, logr_norm, num_norm, bairro_norm,
             cep_norm, cnae_norm, cnae_5dig, mun_nome, uf,
             geo_logr, geo_num, geo_bairro, geo_cep) = cliente

            # ── Buscar candidatos com pool expandido ──
            # Unir candidatos por CEP BDGD + CEP geocodificado
            ceps_busca = set()
            if cep_norm:
                ceps_busca.add(cep_norm)
            if geo_cep and geo_cep != cep_norm:
                ceps_busca.add(geo_cep)

            candidatos = []
            cnpjs_vistos = set()

            with conn.cursor() as cur:
                # Busca por todos os CEPs disponíveis
                for cep_busca in ceps_busca:
                    cur.execute("""
                        SELECT
                            cnpj, razao_social, nome_fantasia,
                            logradouro, numero, bairro, cep,
                            municipio, uf, cnae_fiscal, cnae_fiscal_descricao,
                            situacao_cadastral, telefone_1, email
                        FROM cnpj_cache
                        WHERE cep = %s
                          AND situacao_cadastral = 'ATIVA'
                        LIMIT 200
                    """, (cep_busca,))
                    for row in cur.fetchall():
                        if row[0] not in cnpjs_vistos:
                            cnpjs_vistos.add(row[0])
                            candidatos.append(row)

                # Se poucos por CEP, complementar com municipio + CNAE
                if len(candidatos) < 5 and mun_nome and cnae_norm:
                    ceps_excluir = tuple(ceps_busca) if ceps_busca else ("",)
                    placeholders = ",".join(["%s"] * len(ceps_excluir))
                    cur.execute(f"""
                        SELECT
                            cnpj, razao_social, nome_fantasia,
                            logradouro, numero, bairro, cep,
                            municipio, uf, cnae_fiscal, cnae_fiscal_descricao,
                            situacao_cadastral, telefone_1, email
                        FROM cnpj_cache
                        WHERE UPPER(municipio) = %s
                          AND cnae_fiscal = %s
                          AND situacao_cadastral = 'ATIVA'
                          AND (cep IS NULL OR cep NOT IN ({placeholders}))
                        LIMIT 50
                    """, (mun_nome, cnae_norm, *ceps_excluir))
                    for row in cur.fetchall():
                        if row[0] not in cnpjs_vistos:
                            cnpjs_vistos.add(row[0])
                            candidatos.append(row)

            if not candidatos:
                no_match += 1
                continue

            # ── Pontuar cada candidato com DUPLA FONTE ──
            scored = []
            for cand in candidatos:
                (c_cnpj, c_razao, c_fantasia, c_logr, c_num, c_bairro,
                 c_cep, c_mun, c_uf, c_cnae, c_cnae_desc,
                 c_situacao, c_tel, c_email) = cand

                # Score CNAE (independe do endereco - 25/15 pts)
                s_cnae = 0.0
                c_cnae_clean = re.sub(r"\D", "", c_cnae or "")[:7] if c_cnae else ""
                if cnae_norm and c_cnae_clean:
                    if cnae_norm == c_cnae_clean:
                        s_cnae = 25.0
                    elif cnae_5dig and c_cnae_clean[:5] == cnae_5dig:
                        s_cnae = 15.0

                # ── Score com endereço BDGD original ──
                bdgd_cep, bdgd_end, bdgd_num, bdgd_brr = _score_endereco(
                    logr_norm, num_norm, bairro_norm, cep_norm,
                    c_logr, c_num, c_bairro, c_cep,
                )
                score_bdgd = bdgd_cep + s_cnae + bdgd_end + bdgd_num + bdgd_brr

                # ── Score com endereço GEOCODIFICADO ──
                score_geo = 0.0
                geo_scores = (0.0, 0.0, 0.0, 0.0)
                addr_source = "bdgd"

                if geo_cep or geo_logr:
                    geo_scores = _score_endereco(
                        geo_logr, geo_num, geo_bairro, geo_cep,
                        c_logr, c_num, c_bairro, c_cep,
                    )
                    score_geo = geo_scores[0] + s_cnae + geo_scores[1] + geo_scores[2] + geo_scores[3]

                # ── Usar o MELHOR entre BDGD e geocodificado ──
                if score_geo > score_bdgd:
                    s_cep, s_end, s_num, s_brr = geo_scores
                    total_score = score_geo
                    addr_source = "geocoded"
                else:
                    s_cep, s_end, s_num, s_brr = bdgd_cep, bdgd_end, bdgd_num, bdgd_brr
                    total_score = score_bdgd

                if total_score >= 15:  # Score minimo para ser relevante
                    scored.append((
                        total_score, s_cep, s_cnae, s_end, s_num, s_brr,
                        c_cnpj, c_razao, c_fantasia, c_logr, c_num,
                        c_bairro, c_cep, c_mun, c_uf, c_cnae,
                        c_cnae_desc, c_situacao, c_tel, c_email,
                        addr_source,
                    ))

            if not scored:
                no_match += 1
                continue

            # Ordenar por score e pegar top N
            scored.sort(key=lambda x: x[0], reverse=True)
            for rank, s in enumerate(scored[:top_n], 1):
                (total_score, s_cep, s_cnae, s_end, s_num, s_brr,
                 c_cnpj, c_razao, c_fantasia, c_logr, c_num,
                 c_bairro, c_cep, c_mun, c_uf, c_cnae,
                 c_cnae_desc, c_situacao, c_tel, c_email,
                 addr_source) = s

                insert_batch.append((
                    cod_id, c_cnpj, total_score,
                    s_cep, s_cnae, s_end, s_num, s_brr, rank,
                    c_razao, c_fantasia, c_logr, c_num,
                    c_bairro, c_cep, c_mun, c_uf, c_cnae,
                    c_cnae_desc, c_situacao, c_tel, c_email,
                    addr_source,
                ))
                matched += 1
                if addr_source == "geocoded" and rank == 1:
                    geo_improved += 1

        # Inserir lote de matches
        if insert_batch:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """INSERT INTO bdgd_cnpj_matches (
                        bdgd_cod_id, cnpj, score_total,
                        score_cep, score_cnae, score_endereco, score_numero, score_bairro, rank,
                        razao_social, nome_fantasia, cnpj_logradouro, cnpj_numero,
                        cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf, cnpj_cnae,
                        cnpj_cnae_descricao, cnpj_situacao, cnpj_telefone, cnpj_email,
                        address_source
                    ) VALUES %s""",
                    insert_batch,
                    page_size=len(insert_batch),
                )
            conn.commit()

        offset += batch_size
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        pct = min(offset, total) / total * 100
        print(
            f"           {fmt_num(min(offset, total))}/{fmt_num(total)} ({pct:.1f}%) "
            f"- {fmt_num(matched)} matches, {fmt_num(no_match)} sem match "
            f"- {rate:.0f} clientes/s",
            end="\r",
        )

    elapsed = time.time() - start
    print(f"\n\n           Concluido em {elapsed:.1f}s")
    print(f"           {fmt_num(matched)} matches encontrados")
    print(f"           {fmt_num(no_match)} clientes sem match")
    if has_geo:
        print(f"           {fmt_num(geo_improved)} matches top-1 melhorados pela geocodificacao")

    # Estatisticas de qualidade
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(DISTINCT bdgd_cod_id) as clientes_com_match,
                COUNT(CASE WHEN rank = 1 THEN 1 END) as total_top1,
                AVG(CASE WHEN rank = 1 THEN score_total END) as avg_score_top1,
                COUNT(CASE WHEN rank = 1 AND score_total >= 75 THEN 1 END) as alta_confianca,
                COUNT(CASE WHEN rank = 1 AND score_total >= 50 AND score_total < 75 THEN 1 END) as media_confianca,
                COUNT(CASE WHEN rank = 1 AND score_total >= 15 AND score_total < 50 THEN 1 END) as baixa_confianca,
                COUNT(CASE WHEN rank = 1 AND address_source = 'geocoded' THEN 1 END) as via_geocode
            FROM bdgd_cnpj_matches
        """)
        stats = cur.fetchone()

    print(f"\n  === Qualidade do Matching ===")
    print(f"  Clientes com match:   {fmt_num(stats[0])}")
    print(f"  Score medio (top 1):  {stats[2]:.1f}")
    print(f"  Alta confianca (>=75): {fmt_num(stats[3])} ({stats[3]/max(stats[1],1)*100:.1f}%)")
    print(f"  Media confianca (50-74): {fmt_num(stats[4])} ({stats[4]/max(stats[1],1)*100:.1f}%)")
    print(f"  Baixa confianca (15-49): {fmt_num(stats[5])} ({stats[5]/max(stats[1],1)*100:.1f}%)")
    if has_geo:
        print(f"  Matches via geocodificacao: {fmt_num(stats[6])} ({stats[6]/max(stats[1],1)*100:.1f}%)")


# ──────────────────────────────────────────
# Main
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Matching BDGD -> CNPJ")
    parser.add_argument("--top", type=int, default=3, help="Top N matches por cliente")
    parser.add_argument("--batch-size", type=int, default=1000, help="Tamanho do lote")
    parser.add_argument("--skip-load", action="store_true", help="Pular carga do parquet")
    args = parser.parse_args()

    print("=" * 70)
    print("  Matching BDGD -> CNPJ")
    print("=" * 70)
    print(f"  DB: {DB['host']}:{DB['port']}/{DB['dbname']}")
    print(f"  Top matches: {args.top}")
    print(f"  Batch size: {fmt_num(args.batch_size)}")

    conn = psycopg2.connect(**DB)

    try:
        # Criar tabelas
        print("\n[SETUP] Criando tabelas e indices...")
        criar_tabelas(conn)
        print("         OK")

        # Carregar dados BDGD
        if not args.skip_load:
            carregar_bdgd(conn, PARQUET_PATH, MUNICIPIOS_PATH)
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM bdgd_clientes")
                count = cur.fetchone()[0]
            print(f"\n[CARGA] Pulando carga (--skip-load). {fmt_num(count)} clientes na tabela.")

        # Executar matching
        executar_matching(conn, top_n=args.top, batch_size=args.batch_size)

    finally:
        conn.close()

    print("\n  Pronto!")


if __name__ == "__main__":
    main()
