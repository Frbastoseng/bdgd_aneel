"""
Script de importação de dados técnicos das usinas GD da ANEEL.

Baixa dados da API CKAN em batches e carrega no PostgreSQL via COPY FROM.
Apenas registros PJ (vinculados a geracao_distribuida via cod_empreendimento).

Uso:
    python -m app.scripts.importar_dados_tecnicos --tipo solar
    python -m app.scripts.importar_dados_tecnicos --tipo termica
    python -m app.scripts.importar_dados_tecnicos --all
"""

import argparse
import csv
import io
import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional

import httpx
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuração
ANEEL_API_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
BATCH_SIZE = 50000

DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://gd_user:GdAneel2026Secure@gd_db:5432/gd_aneel"
)

# ════════════════════════════════════════════════════════════════
# Configuração por tipo de usina
# ════════════════════════════════════════════════════════════════

TIPO_CONFIG = {
    "solar": {
        "resource_id": "49fa9ca0-f609-4ae3-a6f7-b97bd0945a3a",
        "table": "gd_tecnico_solar",
        "staging_table": "solar_staging",
        "field_map": {
            "_id": "ckan_id",
            "CodGeracaoDistribuida": "cod_geracao_distribuida",
            "MdaAreaArranjo": "mda_area_arranjo",
            "MdaPotenciaInstaladaKW": "mda_potencia_instalada",
            "NomFabricanteModulo": "nom_fabricante_modulo",
            "NomModeloModulo": "nom_modelo_modulo",
            "NomFabricanteInversor": "nom_fabricante_inversor",
            "NomModeloInversor": "nom_modelo_inversor",
            "QtdModulos": "qtd_modulos",
            "MdaPotenciaModulosKW": "mda_potencia_modulos",
            "MdaPotenciaInversoresKW": "mda_potencia_inversores",
            "DatConexao": "dat_conexao",
        },
        "columns": [
            "ckan_id", "cod_geracao_distribuida", "mda_area_arranjo",
            "mda_potencia_instalada", "nom_fabricante_modulo", "nom_modelo_modulo",
            "nom_fabricante_inversor", "nom_modelo_inversor", "qtd_modulos",
            "mda_potencia_modulos", "mda_potencia_inversores", "dat_conexao",
        ],
        "numeric_fields": {
            "ckan_id", "mda_area_arranjo", "mda_potencia_instalada",
            "qtd_modulos", "mda_potencia_modulos", "mda_potencia_inversores",
        },
        "date_fields": {"dat_conexao"},
        "cast_map": {
            "ckan_id": "INTEGER",
            "mda_area_arranjo": "NUMERIC",
            "mda_potencia_instalada": "NUMERIC",
            "qtd_modulos": "INTEGER",
            "mda_potencia_modulos": "NUMERIC",
            "mda_potencia_inversores": "NUMERIC",
            "dat_conexao": "TIMESTAMP",
        },
    },
    "eolica": {
        "resource_id": "5f903d78-25ae-4a3f-a2bd-9a93351c59fb",
        "table": "gd_tecnico_eolica",
        "staging_table": "eolica_staging",
        "field_map": {
            "_id": "ckan_id",
            "CodGeracaoDistribuida": "cod_geracao_distribuida",
            "NomFabricanteAerogerador": "nom_fabricante_aerogerador",
            "DscModeloAerogerador": "dsc_modelo_aerogerador",
            "MdaPotenciaInstaladaKW": "mda_potencia_instalada",
            "MdaAlturaPa": "mda_altura_pa",
            "IdcEixoRotor": "idc_eixo_rotor",
            "DatConexao": "dat_conexao",
        },
        "columns": [
            "ckan_id", "cod_geracao_distribuida", "nom_fabricante_aerogerador",
            "dsc_modelo_aerogerador", "mda_potencia_instalada", "mda_altura_pa",
            "idc_eixo_rotor", "dat_conexao",
        ],
        "numeric_fields": {
            "ckan_id", "mda_potencia_instalada", "mda_altura_pa",
        },
        "date_fields": {"dat_conexao"},
        "cast_map": {
            "ckan_id": "INTEGER",
            "mda_potencia_instalada": "NUMERIC",
            "mda_altura_pa": "NUMERIC",
            "dat_conexao": "TIMESTAMP",
        },
    },
    "hidraulica": {
        "resource_id": "c189442a-18f0-44eb-9c89-3b48147a4d65",
        "table": "gd_tecnico_hidraulica",
        "staging_table": "hidraulica_staging",
        "field_map": {
            "_id": "ckan_id",
            "CodGeracaoDistribuida": "cod_geracao_distribuida",
            "NomRio": "nom_rio",
            "MdaPotenciaInstaladaKW": "mda_potencia_instalada",
            "MdaPotenciaAparenteKVA": "mda_potencia_aparente",
            "MdaFatorPotencia": "mda_fator_potencia",
            "MdaTensaoKV": "mda_tensao",
            "MdaNivelOperacionalMontante": "mda_nivel_operacional_montante",
            "MdaNivelOperacionalJusante": "mda_nivel_operacional_jusante",
            "DatConexao": "dat_conexao",
        },
        "columns": [
            "ckan_id", "cod_geracao_distribuida", "nom_rio",
            "mda_potencia_instalada", "mda_potencia_aparente", "mda_fator_potencia",
            "mda_tensao", "mda_nivel_operacional_montante",
            "mda_nivel_operacional_jusante", "dat_conexao",
        ],
        "numeric_fields": {
            "ckan_id", "mda_potencia_instalada", "mda_potencia_aparente",
            "mda_fator_potencia", "mda_tensao",
            "mda_nivel_operacional_montante", "mda_nivel_operacional_jusante",
        },
        "date_fields": {"dat_conexao"},
        "cast_map": {
            "ckan_id": "INTEGER",
            "mda_potencia_instalada": "NUMERIC",
            "mda_potencia_aparente": "NUMERIC",
            "mda_fator_potencia": "NUMERIC",
            "mda_tensao": "NUMERIC",
            "mda_nivel_operacional_montante": "NUMERIC",
            "mda_nivel_operacional_jusante": "NUMERIC",
            "dat_conexao": "TIMESTAMP",
        },
    },
    "termica": {
        "resource_id": "bd1d3783-b389-49d8-a828-a56e193d0671",
        "table": "gd_tecnico_termica",
        "staging_table": "termica_staging",
        "field_map": {
            "_id": "ckan_id",
            "CodGeracaoDistribuida": "cod_geracao_distribuida",
            "MdaPotenciaInstaladaKW": "mda_potencia_instalada",
            "DatConexao": "dat_conexao",
            "DscCicloTermodinamico": "dsc_ciclo_termodinamico",
            "DscMaquinaMotriz": "dsc_maquina_motriz",
        },
        "columns": [
            "ckan_id", "cod_geracao_distribuida", "mda_potencia_instalada",
            "dat_conexao", "dsc_ciclo_termodinamico", "dsc_maquina_motriz",
        ],
        "numeric_fields": {"ckan_id", "mda_potencia_instalada"},
        "date_fields": {"dat_conexao"},
        "cast_map": {
            "ckan_id": "INTEGER",
            "mda_potencia_instalada": "NUMERIC",
            "dat_conexao": "TIMESTAMP",
        },
    },
}


# ════════════════════════════════════════════════════════════════
# Funções auxiliares
# ════════════════════════════════════════════════════════════════

def parse_value(col: str, value: str, numeric_fields: set, date_fields: set) -> Optional[str]:
    """Converte valor da API para formato adequado ao PostgreSQL."""
    if value is None or value == "" or value == "None":
        return None

    value = str(value).strip()

    if col in numeric_fields:
        try:
            cleaned = value.replace(",", ".")
            float(cleaned)
            return cleaned
        except (ValueError, TypeError):
            return None

    if col in date_fields:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None

    return value


def record_to_row(record: dict, config: dict) -> list:
    """Converte um registro da API CKAN para uma linha CSV."""
    row = []
    # Inverter field_map para lookup rápido
    reverse_map = {v: k for k, v in config["field_map"].items()}

    for col in config["columns"]:
        api_field = reverse_map.get(col)
        raw_value = record.get(api_field) if api_field else None
        parsed = parse_value(col, raw_value, config["numeric_fields"], config["date_fields"])
        row.append(parsed if parsed is not None else "")
    return row


def download_batch(client: httpx.Client, resource_id: str, offset: int) -> dict:
    """Baixar um batch da API CKAN com retry."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.get(
                ANEEL_API_URL,
                params={
                    "resource_id": resource_id,
                    "limit": BATCH_SIZE,
                    "offset": offset,
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                raise Exception(f"API retornou success=false: {data}")

            return data["result"]

        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 10
                logger.warning(f"Erro no batch offset={offset}, tentativa {attempt + 1}/{max_retries}: {e}")
                logger.warning(f"Aguardando {wait}s antes de tentar novamente...")
                time.sleep(wait)
            else:
                raise


def create_staging_table(conn, staging_table: str, columns: list):
    """Cria tabela staging sem constraints para COPY FROM rápido."""
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        cols_sql = ", ".join(f"{col} TEXT" for col in columns)
        cur.execute(f"CREATE UNLOGGED TABLE {staging_table} ({cols_sql})")
    conn.commit()
    logger.info(f"Tabela staging '{staging_table}' criada")


def copy_batch_to_staging(conn, records: list, config: dict) -> int:
    """Copia batch de registros para staging table via COPY FROM."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    count = 0

    for record in records:
        row = record_to_row(record, config)
        # Substituir valores vazios por \N (NULL do PostgreSQL)
        row = [v if v != "" else "\\N" for v in row]
        writer.writerow(row)
        count += 1

    if count == 0:
        return 0

    buf.seek(0)
    cols_str = ", ".join(config["columns"])
    staging = config["staging_table"]

    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY {staging} ({cols_str}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
            buf
        )
    conn.commit()
    return count


def merge_staging_to_final(conn, config: dict):
    """Merge dos dados do staging para a tabela final.
    Filtra apenas registros PJ via INNER JOIN com geracao_distribuida."""
    table = config["table"]
    staging = config["staging_table"]
    columns = config["columns"]
    cast_map = config["cast_map"]

    cols_str = ", ".join(columns)
    update_cols = [c for c in columns if c != "cod_geracao_distribuida"]
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

    # Cast expressions para conversão de tipos
    cast_expressions = []
    for col in columns:
        if col in cast_map:
            cast_expressions.append(f"s.{col}::{cast_map[col]}")
        else:
            cast_expressions.append(f"s.{col}")
    select_cast = ", ".join(cast_expressions)

    # Deduplicar staging (manter último registro por cod_geracao_distribuida)
    with conn.cursor() as cur:
        logger.info("Deduplicando staging table...")
        cur.execute(f"""
            DELETE FROM {staging} a USING {staging} b
            WHERE a.ctid < b.ctid
            AND a.cod_geracao_distribuida = b.cod_geracao_distribuida
            AND a.cod_geracao_distribuida IS NOT NULL
            AND a.cod_geracao_distribuida != ''
        """)
        dupes = cur.rowcount
        logger.info(f"Removidos {dupes:,} duplicados do staging")
    conn.commit()

    # Contar registros no staging antes do filtro PJ
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {staging} WHERE cod_geracao_distribuida IS NOT NULL AND cod_geracao_distribuida != ''")
        total_staging = cur.fetchone()[0]
        logger.info(f"Total no staging (pós-dedup): {total_staging:,}")

    # Merge com INNER JOIN na geracao_distribuida (filtro PJ)
    sql = f"""
        INSERT INTO {table} ({cols_str}, created_at, updated_at)
        SELECT {select_cast}, NOW(), NOW()
        FROM {staging} s
        INNER JOIN geracao_distribuida gd ON s.cod_geracao_distribuida = gd.cod_empreendimento
        WHERE s.cod_geracao_distribuida IS NOT NULL AND s.cod_geracao_distribuida != ''
        ON CONFLICT (cod_geracao_distribuida)
        DO UPDATE SET {update_str}, updated_at = NOW()
    """

    with conn.cursor() as cur:
        logger.info(f"Fazendo merge staging → {table} (filtro PJ via geracao_distribuida)...")
        cur.execute(sql)
        rows = cur.rowcount
        logger.info(f"Merge concluído: {rows:,} registros PJ inseridos/atualizados (de {total_staging:,} no staging)")
    conn.commit()

    # Limpar staging
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


# ════════════════════════════════════════════════════════════════
# Importação principal
# ════════════════════════════════════════════════════════════════

def run_import(tipo: str):
    """Executa a importação de um tipo de dado técnico."""
    if tipo not in TIPO_CONFIG:
        logger.error(f"Tipo '{tipo}' não reconhecido. Opções: {list(TIPO_CONFIG.keys())}")
        sys.exit(1)

    config = TIPO_CONFIG[tipo]
    start_time = time.time()

    logger.info("=" * 80)
    logger.info(f"IMPORTAÇÃO DADOS TÉCNICOS - {tipo.upper()}")
    logger.info(f"Resource ID: {config['resource_id']}")
    logger.info(f"Tabela destino: {config['table']}")
    logger.info(f"Filtro: Apenas PJ (INNER JOIN geracao_distribuida)")
    logger.info("=" * 80)

    # Conectar ao banco
    logger.info(f"Conectando ao banco: {DATABASE_URL_SYNC[:50]}...")
    conn = psycopg2.connect(DATABASE_URL_SYNC)
    logger.info("Conectado ao banco de dados")

    # Criar staging table
    create_staging_table(conn, config["staging_table"], config["columns"])

    # Download e carga em batches
    total_downloaded = 0
    total_records = None

    with httpx.Client() as client:
        # Primeiro batch para descobrir o total
        logger.info("Baixando primeiro batch para descobrir total...")
        result = download_batch(client, config["resource_id"], 0)
        total_records = result.get("total", 0)
        records = result.get("records", [])
        actual_batch_size = len(records)

        logger.info(f"Total de registros na API: {total_records:,}")
        logger.info(f"Registros por request: {actual_batch_size:,}")

        if total_records == 0:
            logger.info(f"API vazia para {tipo}. Nada a importar.")
            conn.close()
            return

        batches_needed = (total_records + actual_batch_size - 1) // actual_batch_size if actual_batch_size > 0 else 0
        logger.info(f"Batches necessários: {batches_needed}")

        # Carregar primeiro batch
        if records:
            count = copy_batch_to_staging(conn, records, config)
            total_downloaded += len(records)
            elapsed = time.time() - start_time
            rate = total_downloaded / elapsed if elapsed > 0 else 0
            logger.info(
                f"Batch 1: {total_downloaded:,}/{total_records:,} "
                f"({100 * total_downloaded / total_records:.1f}%) - {rate:.0f} rec/s"
            )

        # Continuar com os batches restantes
        offset = actual_batch_size
        batch_num = 2

        while offset < total_records:
            result = download_batch(client, config["resource_id"], offset)
            records = result.get("records", [])

            if not records:
                logger.info("Sem mais registros, finalizando download")
                break

            copy_batch_to_staging(conn, records, config)
            total_downloaded += len(records)
            elapsed = time.time() - start_time
            rate = total_downloaded / elapsed if elapsed > 0 else 0
            eta = (total_records - total_downloaded) / rate if rate > 0 else 0

            if batch_num % 20 == 0 or batch_num <= 5:
                logger.info(
                    f"Batch {batch_num}: {total_downloaded:,}/{total_records:,} "
                    f"({100 * total_downloaded / total_records:.1f}%) "
                    f"- {rate:.0f} rec/s - ETA: {eta / 60:.1f} min"
                )

            offset += len(records)
            batch_num += 1

    logger.info(f"Download concluído: {total_downloaded:,} registros baixados")

    # Merge para tabela final (com filtro PJ)
    merge_staging_to_final(conn, config)

    # ANALYZE
    with conn.cursor() as cur:
        logger.info(f"Executando ANALYZE na tabela {config['table']}...")
        cur.execute(f"ANALYZE {config['table']}")
    conn.commit()

    # Contagem final
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {config['table']}")
        final_count = cur.fetchone()[0]

    conn.close()

    elapsed_total = time.time() - start_time
    logger.info("=" * 80)
    logger.info(f"IMPORTAÇÃO CONCLUÍDA - {tipo.upper()}")
    logger.info(f"Total baixado da API: {total_downloaded:,}")
    logger.info(f"Total PJ no banco: {final_count:,} registros")
    logger.info(f"Tempo total: {elapsed_total / 60:.1f} minutos")
    if elapsed_total > 0:
        logger.info(f"Velocidade média: {total_downloaded / elapsed_total:.0f} rec/s")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Importar dados técnicos das usinas GD da ANEEL")
    parser.add_argument(
        "--tipo",
        choices=["solar", "eolica", "hidraulica", "termica"],
        help="Tipo de usina a importar",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Importar todos os tipos",
    )
    args = parser.parse_args()

    if not args.tipo and not args.all:
        parser.error("Especifique --tipo ou --all")

    tipos = ["solar", "eolica", "hidraulica", "termica"] if args.all else [args.tipo]

    for tipo in tipos:
        try:
            run_import(tipo)
        except KeyboardInterrupt:
            logger.info("\nImportação cancelada pelo usuário")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Erro na importação de {tipo}: {e}", exc_info=True)
            if not args.all:
                sys.exit(1)


if __name__ == "__main__":
    main()
