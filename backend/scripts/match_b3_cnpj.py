"""
Script para matching entre clientes B3 (UCBT PJ) e base de CNPJ.

Otimizado para 10M+ registros usando abordagem híbrida:
  1. SQL JOIN para gerar candidatos (CEP match) em bulk
  2. Python para scoring detalhado (endereco, numero, bairro)
  3. Insert em batch com execute_values

Scoring:
  - CEP exato:       40 pts
  - CNAE 7 digitos:  25 pts  (5 digitos: 15 pts)
  - Endereco similar: ate 20 pts (Jaccard similarity)
  - Numero exato:    10 pts
  - Bairro similar:   ate 5 pts

Uso:
    docker exec bdgd_backend python scripts/match_b3_cnpj.py [--top N]
"""

import argparse
import os
import re
import sys
import time

import psycopg2
from psycopg2.extras import execute_values


DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "bdgd_pro"),
    "user": os.getenv("DB_USER", "bdgd"),
    "password": os.getenv("DB_PASSWORD", "bdgd_secret_2024"),
}


def normalizar_texto(texto):
    if not texto:
        return None
    t = str(texto).strip().upper()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or None


def fmt_num(n):
    return f"{n:,}".replace(",", ".")


def jaccard_words(text1, text2, min_len=3):
    """Jaccard similarity between word sets (words > min_len chars)."""
    if not text1 or not text2:
        return 0.0
    words1 = {p for p in text1.split() if len(p) > min_len}
    words2 = {p for p in text2.split() if len(p) > min_len}
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def score_candidate(cliente, cnpj_row):
    """Score one CNPJ candidate against a B3 client. Returns total + components."""
    (c_logr_norm, c_num_norm, c_bairro_norm, c_cep_norm,
     c_cnae_norm, c_cnae_5dig) = cliente

    (cnpj, razao, fantasia, logr, num, bairro, cep,
     mun, uf, cnae_fiscal, cnae_desc, situacao, tel, email) = cnpj_row

    # CEP score (40 pts)
    s_cep = 40.0 if (c_cep_norm and cep and c_cep_norm == cep) else 0.0

    # CNAE score (25/15 pts)
    s_cnae = 0.0
    cnpj_cnae = re.sub(r"\D", "", cnae_fiscal or "")[:7] if cnae_fiscal else ""
    if c_cnae_norm and cnpj_cnae:
        if c_cnae_norm == cnpj_cnae:
            s_cnae = 25.0
        elif c_cnae_5dig and cnpj_cnae[:5] == c_cnae_5dig:
            s_cnae = 15.0

    # Endereco score (20 pts)
    s_end = 0.0
    if c_logr_norm and logr:
        cnpj_logr = normalizar_texto(logr)
        if cnpj_logr:
            s_end = round(jaccard_words(c_logr_norm, cnpj_logr) * 20.0, 2)

    # Numero score (10 pts)
    s_num = 0.0
    if c_num_norm and num:
        if c_num_norm == re.sub(r"\D", "", num):
            s_num = 10.0

    # Bairro score (5 pts)
    s_brr = 0.0
    if c_bairro_norm and bairro:
        cnpj_brr = normalizar_texto(bairro)
        if cnpj_brr:
            if c_bairro_norm == cnpj_brr:
                s_brr = 5.0
            else:
                s_brr = round(jaccard_words(c_bairro_norm, cnpj_brr, 2) * 5.0, 2)

    total = s_cep + s_cnae + s_end + s_num + s_brr
    return total, s_cep, s_cnae, s_end, s_num, s_brr


def executar_matching(conn, top_n=3, resume=True):
    """Executa matching B3 -> CNPJ processando CEP a CEP."""
    print("\n[B3 MATCHING] Iniciando...", flush=True)

    if not resume:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE b3_cnpj_matches RESTART IDENTITY")
        conn.commit()
        print("  Tabela limpa (modo fresh)", flush=True)

    # Get CEPs already processed (for resume)
    ceps_processados = set()
    if resume:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT c.cep_norm
                FROM b3_cnpj_matches m
                JOIN b3_clientes c ON c.cod_id = m.bdgd_cod_id
                WHERE c.cep_norm IS NOT NULL
            """)
            ceps_processados = {r[0] for r in cur.fetchall()}
        print(f"  Resumindo: {fmt_num(len(ceps_processados))} CEPs ja processados", flush=True)

    # Get all CEPs ordered by frequency (ascending = lighter first)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT cep_norm, COUNT(*) as cnt
            FROM b3_clientes
            WHERE cep_norm IS NOT NULL AND cep_norm != ''
            GROUP BY cep_norm
            ORDER BY cnt ASC
        """)
        all_ceps = [(c, n) for c, n in cur.fetchall() if c not in ceps_processados]

    total_ceps = len(all_ceps)
    total_clientes = sum(c[1] for c in all_ceps)
    print(f"  {fmt_num(total_clientes)} clientes em {fmt_num(total_ceps)} CEPs", flush=True)

    start = time.time()
    matched_total = 0
    no_match_total = 0
    processed_clientes = 0
    processed_ceps = 0
    insert_batch = []

    insert_sql = """INSERT INTO b3_cnpj_matches (
        bdgd_cod_id, cnpj, score_total,
        score_cep, score_cnae, score_endereco, score_numero, score_bairro, rank,
        razao_social, nome_fantasia, cnpj_logradouro, cnpj_numero,
        cnpj_bairro, cnpj_cep, cnpj_municipio, cnpj_uf, cnpj_cnae,
        cnpj_cnae_descricao, cnpj_situacao, cnpj_telefone, cnpj_email,
        address_source
    ) VALUES %s"""

    for cep_norm, cep_count in all_ceps:
        # 1. Get CNPJ candidates for this CEP
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cnpj, razao_social, nome_fantasia,
                       logradouro, numero, bairro, cep,
                       municipio, uf, cnae_fiscal, cnae_fiscal_descricao,
                       situacao_cadastral, telefone_1, email
                FROM cnpj_cache
                WHERE cep = %s AND situacao_cadastral = 'ATIVA'
                LIMIT 200
            """, (cep_norm,))
            candidatos = cur.fetchall()

        if not candidatos:
            # No CNPJs for this CEP - all clients get no match
            no_match_total += cep_count
            processed_clientes += cep_count
            processed_ceps += 1
            continue

        # 2. Get all B3 clients with this CEP
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cod_id, logradouro_norm, numero_norm, bairro_norm,
                       cep_norm, cnae_norm, cnae_5dig
                FROM b3_clientes
                WHERE cep_norm = %s
            """, (cep_norm,))
            clientes = cur.fetchall()

        # 3. Score each client against candidates
        for cliente_row in clientes:
            cod_id = cliente_row[0]
            cliente_info = cliente_row[1:7]  # logr, num, bairro, cep, cnae, cnae5

            scored = []
            for cand in candidatos:
                total_score, s_cep, s_cnae, s_end, s_num, s_brr = score_candidate(
                    cliente_info, cand
                )
                if total_score >= 15:
                    scored.append((
                        total_score, s_cep, s_cnae, s_end, s_num, s_brr,
                        cand,  # full cnpj row
                    ))

            if not scored:
                no_match_total += 1
                processed_clientes += 1
                continue

            scored.sort(key=lambda x: x[0], reverse=True)
            for rank, item in enumerate(scored[:top_n], 1):
                total_score, s_cep, s_cnae, s_end, s_num, s_brr, cand = item
                (c_cnpj, c_razao, c_fantasia, c_logr, c_num, c_bairro,
                 c_cep, c_mun, c_uf, c_cnae, c_cnae_desc,
                 c_situacao, c_tel, c_email) = cand

                insert_batch.append((
                    cod_id, c_cnpj, total_score,
                    s_cep, s_cnae, s_end, s_num, s_brr, rank,
                    c_razao, c_fantasia, c_logr, c_num,
                    c_bairro, c_cep, c_mun, c_uf, c_cnae,
                    c_cnae_desc, c_situacao, c_tel, c_email,
                    "bdgd",
                ))
                matched_total += 1

            processed_clientes += 1

        processed_ceps += 1

        # Flush batch every 10K inserts
        if len(insert_batch) >= 10000:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, insert_batch, page_size=5000)
            conn.commit()
            insert_batch = []

        # Progress every 1000 CEPs
        if processed_ceps % 1000 == 0:
            elapsed = time.time() - start
            rate = processed_clientes / elapsed if elapsed > 0 else 0
            pct = processed_clientes / total_clientes * 100
            print(
                f"  CEPs: {fmt_num(processed_ceps)}/{fmt_num(total_ceps)} "
                f"| Clientes: {fmt_num(processed_clientes)}/{fmt_num(total_clientes)} ({pct:.1f}%) "
                f"| {fmt_num(matched_total)} matches | {rate:.0f}/s",
                flush=True,
            )

    # Final flush
    if insert_batch:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, insert_batch, page_size=5000)
        conn.commit()

    elapsed = time.time() - start
    print(f"\n[B3 MATCHING] Concluido em {elapsed:.0f}s ({elapsed/60:.1f} min)", flush=True)
    print(f"  {fmt_num(processed_clientes)} clientes processados", flush=True)
    print(f"  {fmt_num(matched_total)} matches ({fmt_num(matched_total // top_n)} clientes com match)", flush=True)
    print(f"  {fmt_num(no_match_total)} sem match", flush=True)
    if processed_clientes > 0:
        pct = (processed_clientes - no_match_total) / processed_clientes * 100
        print(f"  {pct:.1f}% com pelo menos 1 match", flush=True)


def main():
    parser = argparse.ArgumentParser(description="B3 -> CNPJ matching")
    parser.add_argument("--top", type=int, default=3)
    parser.add_argument("--fresh", action="store_true", help="Limpar tabela e recomeçar")
    args = parser.parse_args()

    print("=" * 60, flush=True)
    print("  MATCHING B3 (UCBT PJ) -> CNPJ", flush=True)
    print("=" * 60, flush=True)

    conn = psycopg2.connect(**DB)
    conn.autocommit = False

    try:
        executar_matching(conn, top_n=args.top, resume=not args.fresh)
    finally:
        conn.close()

    print("\n" + "=" * 60, flush=True)
    print("  CONCLUIDO", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
