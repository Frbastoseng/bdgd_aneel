"""
Script para importar dados de CNPJ do banco do CRM-5.0 para o BDGD Pro.

Uso:
    python scripts/import_cnpj.py

Configura as conexoes via variaveis de ambiente ou valores padrao:
    - CRM DB: localhost:5433/crm_ludfor (schema crm)
    - BDGD DB: localhost:5434/bdgd_aneel_prod (schema public)
"""

import os
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

# ──────────────────────────────────────────
# Configuracao
# ──────────────────────────────────────────

CRM_DB = {
    "host": os.getenv("CRM_DB_HOST", "localhost"),
    "port": int(os.getenv("CRM_DB_PORT", "5433")),
    "dbname": os.getenv("CRM_DB_NAME", "crm_ludfor"),
    "user": os.getenv("CRM_DB_USER", "postgres"),
    "password": os.getenv("CRM_DB_PASSWORD", "postgres"),
}

BDGD_DB = {
    "host": os.getenv("BDGD_DB_HOST", "localhost"),
    "port": int(os.getenv("BDGD_DB_PORT", "5434")),
    "dbname": os.getenv("BDGD_DB_NAME", "bdgd_aneel_prod"),
    "user": os.getenv("BDGD_DB_USER", os.getenv("DB_USER", "bdgd_user")),
    "password": os.getenv("BDGD_DB_PASSWORD", os.getenv("DB_PASSWORD", "BdGd@Secure2026!")),
}

BATCH_SIZE = 5000
CRM_SCHEMA = "crm"

# Colunas a copiar (mesma ordem na origem e destino)
COLUMNS = [
    "cnpj", "razao_social", "nome_fantasia", "situacao_cadastral",
    "data_situacao_cadastral", "data_inicio_atividade", "natureza_juridica",
    "porte", "capital_social", "cnae_fiscal", "cnae_fiscal_descricao",
    "cnaes_secundarios", "logradouro", "numero", "complemento", "bairro",
    "municipio", "uf", "cep", "telefone_1", "telefone_2", "email",
    "socios", "opcao_pelo_simples", "opcao_pelo_mei", "raw_json",
    "data_consulta", "erro_ultima_consulta", "created_at", "updated_at",
]

COLUMNS_SQL = ", ".join(COLUMNS)
PLACEHOLDERS = ", ".join(["%s"] * len(COLUMNS))


def fmt_num(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main():
    print("=" * 70)
    print("  Importacao de CNPJs: CRM-5.0 -> BDGD Pro")
    print("=" * 70)
    print(f"\n  Origem:  {CRM_DB['host']}:{CRM_DB['port']}/{CRM_DB['dbname']} (schema {CRM_SCHEMA})")
    print(f"  Destino: {BDGD_DB['host']}:{BDGD_DB['port']}/{BDGD_DB['dbname']} (schema public)")
    print(f"  Batch:   {fmt_num(BATCH_SIZE)} registros\n")

    # Conectar
    print("[1/4] Conectando ao banco CRM-5.0...")
    try:
        src = psycopg2.connect(**CRM_DB)
        src.set_session(readonly=True)
        print("       OK")
    except Exception as e:
        print(f"       ERRO: {e}")
        sys.exit(1)

    print("[2/4] Conectando ao banco BDGD Pro...")
    try:
        dst = psycopg2.connect(**BDGD_DB)
        print("       OK")
    except Exception as e:
        print(f"       ERRO: {e}")
        src.close()
        sys.exit(1)

    # Contar registros na origem
    print("[3/4] Contando registros na origem...")
    with src.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {CRM_SCHEMA}.cnpj_cache")
        total = cur.fetchone()[0]
    print(f"       {fmt_num(total)} registros encontrados")

    if total == 0:
        print("\n  Nenhum registro para importar.")
        src.close()
        dst.close()
        return

    # Verificar registros existentes no destino
    with dst.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cnpj_cache")
        existing = cur.fetchone()[0]

    if existing > 0:
        print(f"\n  ATENCAO: Ja existem {fmt_num(existing)} registros no destino.")
        resp = input("  Deseja LIMPAR a tabela destino antes de importar? (s/N): ").strip().lower()
        if resp == "s":
            with dst.cursor() as cur:
                cur.execute("TRUNCATE cnpj_cache RESTART IDENTITY")
                dst.commit()
            print("  Tabela limpa.")
        else:
            print("  Continuando com ON CONFLICT DO NOTHING (registros duplicados serao ignorados).")

    # Importar em lotes
    print(f"\n[4/4] Importando {fmt_num(total)} registros...")
    start = time.time()
    imported = 0
    skipped = 0

    with src.cursor("cnpj_reader") as src_cur:
        src_cur.itersize = BATCH_SIZE
        src_cur.execute(f"SELECT {COLUMNS_SQL} FROM {CRM_SCHEMA}.cnpj_cache ORDER BY id")

        batch = []
        for row in src_cur:
            batch.append(row)

            if len(batch) >= BATCH_SIZE:
                count = _insert_batch(dst, batch)
                imported += count
                skipped += len(batch) - count
                batch = []

                elapsed = time.time() - start
                rate = imported / elapsed if elapsed > 0 else 0
                pct = (imported + skipped) / total * 100
                print(
                    f"       {fmt_num(imported + skipped)}/{fmt_num(total)} "
                    f"({pct:.1f}%) - {fmt_num(imported)} inseridos, "
                    f"{fmt_num(skipped)} ignorados - {rate:.0f} reg/s",
                    end="\r",
                )

        # Ultimo lote
        if batch:
            count = _insert_batch(dst, batch)
            imported += count
            skipped += len(batch) - count

    elapsed = time.time() - start
    print(f"\n\n  Concluido em {elapsed:.1f}s")
    print(f"  {fmt_num(imported)} registros inseridos")
    if skipped:
        print(f"  {fmt_num(skipped)} registros ignorados (duplicados)")
    print(f"  Velocidade media: {imported / elapsed:.0f} reg/s" if elapsed > 0 else "")

    src.close()
    dst.close()
    print("\n  Pronto!")


def _insert_batch(conn, batch: list) -> int:
    """Insere um lote de registros com ON CONFLICT DO NOTHING."""
    insert_sql = (
        f"INSERT INTO cnpj_cache ({COLUMNS_SQL}) VALUES %s "
        f"ON CONFLICT (cnpj) DO NOTHING"
    )
    with conn.cursor() as cur:
        execute_values(cur, insert_sql, batch, page_size=len(batch))
        count = cur.rowcount
    conn.commit()
    return count


if __name__ == "__main__":
    main()
