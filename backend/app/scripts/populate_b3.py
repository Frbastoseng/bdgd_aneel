"""Script para popular b3_clientes via COPY FROM CSV (bulk load rápido)."""

import pandas as pd
import re
import time
import io
import sys
import psycopg2


def main():
    print("=== POPULATE b3_clientes via COPY FROM CSV ===", flush=True)
    print("Carregando parquet B3 (colunas essenciais)...", flush=True)
    t0 = time.time()

    cols = [
        "COD_ID_ENCR", "LGRD", "BRR", "CEP", "CNAE", "MUN",
        "CLAS_SUB", "GRU_TAR", "CONSUMO_ANUAL", "CONSUMO_MEDIO",
        "CAR_INST", "FAS_CON", "SIT_ATIV", "DIC_ANUAL", "FIC_ANUAL",
        "POSSUI_SOLAR", "POINT_X", "POINT_Y",
    ]
    df = pd.read_parquet("/app/data/dados_b3.parquet", columns=cols)
    print(f"Parquet carregado: {len(df):,} registros em {time.time()-t0:.1f}s", flush=True)

    # Drop rows without COD_ID and dedup
    df = df.dropna(subset=["COD_ID_ENCR"])
    df = df.drop_duplicates(subset=["COD_ID_ENCR"])
    print(f"Registros unicos com COD_ID: {len(df):,}", flush=True)

    # Vectorized normalization helpers
    def v_norm(series):
        s = series.fillna("").astype(str).str.strip().str.upper()
        s = s.str.replace(r"[^\w\s]", " ", regex=True)
        s = s.str.replace(r"\s+", " ", regex=True).str.strip()
        # Also remove any tabs/newlines
        s = s.str.replace(r"[\t\n\r]", " ", regex=True)
        return s.replace("", None)

    def v_norm_cep(series):
        s = series.fillna("").astype(str).str.strip()
        s = s.str.replace(r"\D", "", regex=True).str[:8]
        return s.replace("", None)

    def v_extrair_num(series):
        return series.fillna("").astype(str).str.strip().str.extract(
            r"(\d+)\s*$", expand=False
        )

    def v_cnae_norm(series):
        s = series.fillna("").astype(str).str.replace(r"\D", "", regex=True).str[:7]
        return s.replace("", None)

    def safe_str(series):
        """Safely convert to string, clean tabs/newlines, replace nan/None."""
        s = series.astype(str).str.replace(r"[\t\n\r]", " ", regex=True)
        return s.replace({"nan": None, "None": None, "": None})

    print("Normalizando dados...", flush=True)
    t1 = time.time()

    out = pd.DataFrame()
    out["cod_id"] = df["COD_ID_ENCR"].astype(str)
    out["lgrd_original"] = safe_str(df["LGRD"])
    out["brr_original"] = safe_str(df["BRR"])
    out["cep_original"] = safe_str(df["CEP"])
    out["cnae_original"] = safe_str(df["CNAE"])
    out["logradouro_norm"] = v_norm(df["LGRD"])
    out["numero_norm"] = v_extrair_num(df["LGRD"])
    out["bairro_norm"] = v_norm(df["BRR"])
    out["cep_norm"] = v_norm_cep(df["CEP"])
    out["cnae_norm"] = v_cnae_norm(df["CNAE"])

    # cnae_5dig
    cnae_n = out["cnae_norm"].fillna("")
    mask = cnae_n.str.len() >= 5
    out["cnae_5dig"] = None
    out.loc[mask, "cnae_5dig"] = cnae_n[mask].str[:5]

    out["mun_code"] = safe_str(df["MUN"])
    out["point_x"] = df["POINT_X"]
    out["point_y"] = df["POINT_Y"]
    out["clas_sub"] = safe_str(df["CLAS_SUB"])
    out["gru_tar"] = safe_str(df["GRU_TAR"])
    out["consumo_anual"] = df["CONSUMO_ANUAL"]
    out["consumo_medio"] = df["CONSUMO_MEDIO"]
    out["car_inst"] = df["CAR_INST"]
    out["fas_con"] = safe_str(df["FAS_CON"])
    out["sit_ativ"] = safe_str(df["SIT_ATIV"])
    out["dic_anual"] = df["DIC_ANUAL"]
    out["fic_anual"] = df["FIC_ANUAL"]
    out["possui_solar"] = df["POSSUI_SOLAR"].fillna(False).astype(bool)

    print(f"Normalizacao concluida em {time.time()-t1:.1f}s", flush=True)

    # Connect
    print("Conectando ao PostgreSQL...", flush=True)
    conn = psycopg2.connect(
        host="db", port=5432, database="bdgd_pro",
        user="bdgd", password="bdgd_secret_2024",
    )
    cur = conn.cursor()

    columns = list(out.columns)
    cols_str = ", ".join(columns)

    # Process in chunks to avoid memory issues with 11M rows
    chunk_size = 500_000
    total_rows = len(out)
    total_inserted = 0

    print(f"Processando em chunks de {chunk_size:,}...", flush=True)

    for i in range(0, total_rows, chunk_size):
        chunk = out.iloc[i : i + chunk_size]

        # Write chunk as CSV to buffer using copy_expert (handles quoting)
        buf = io.StringIO()
        chunk.to_csv(buf, index=False, header=False, sep=",", quoting=1)  # QUOTE_ALL
        buf.seek(0)

        sql = f"COPY b3_clientes ({cols_str}) FROM STDIN WITH (FORMAT csv, NULL '')"
        cur.copy_expert(sql, buf)
        conn.commit()

        total_inserted += len(chunk)
        elapsed = time.time() - t0
        rate = total_inserted / elapsed if elapsed > 0 else 0
        pct = total_inserted * 100 // total_rows
        print(
            f"  Chunk {i//chunk_size + 1}: {total_inserted:,}/{total_rows:,} "
            f"({pct}%) - {rate:.0f} reg/s - {elapsed:.0f}s",
            flush=True,
        )

    cur.execute("SELECT COUNT(*) FROM b3_clientes")
    count = cur.fetchone()[0]
    print(f"Total b3_clientes no banco: {count:,}", flush=True)

    cur.close()
    conn.close()

    total_time = time.time() - t0
    print(f"=== CONCLUIDO em {total_time:.0f}s ({total_time/60:.1f} min) ===", flush=True)


if __name__ == "__main__":
    main()
