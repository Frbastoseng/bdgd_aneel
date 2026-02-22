"""
Script de importação de dados de Geração Distribuída da ANEEL.

Baixa dados da API CKAN em batches e carrega no PostgreSQL via COPY FROM.

Uso:
    python -m app.scripts.importar_gd
"""

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
RESOURCE_ID = "b1bd71e7-d0ad-4214-9053-cbd58e9564a7"
BATCH_SIZE = 50000

# Database URL (sync para psycopg2)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    "postgresql://gd_user:GdAneel2026Secure@gd_db:5432/gd_aneel"
)

# Mapeamento campos CKAN → colunas do banco
FIELD_MAP = {
    "_id": "ckan_id",
    "DthAtualizaCadastralEmpreworking": "dth_atualiza_cadastral",
    "SigAgente": "sig_agente",
    "NomAgente": "nom_agente",
    "CodCEP": "cod_cep",
    "DscSubGrupoTarifario": "dsc_sub_grupo_tarifario",
    "DscClasseConsumo": "dsc_classe_consumo",
    "DscSubClasseConsumo": "dsc_sub_classe_consumo",
    "SigUF": "sig_uf",
    "NomMunicipio": "nom_municipio",
    "CodUFIBGE": "cod_uf_ibge",
    "CodMunicipioIBGE": "cod_municipio_ibge",
    "SigTipoConsumidor": "sig_tipo_consumidor",
    "NumCPFCNPJ": "num_cpf_cnpj",
    "NomTitularEmpreendimento": "nom_titular",
    "CodEmpreendimento": "cod_empreendimento",
    "DthConexaoInicial": "dth_conexao_inicial",
    "SigTipoGeracao": "sig_tipo_geracao",
    "DscFonteGeracao": "dsc_fonte_geracao",
    "DscPorte": "dsc_porte",
    "SigModalidadeEmpreendimento": "sig_modalidade",
    "QtdModulos": "qtd_modulos",
    "MdaPotenciaInstaladaKW": "potencia_instalada_kw",
    "MdaPotenciaFiscalizadaKW": "potencia_fiscalizada_kw",
    "MdaGarantiaFisicaMWm": "garantia_fisica_mwm",
    "NumCoordNEmpreendimento": "coord_n",
    "NumCoordEEmpreendimento": "coord_e",
    "IdcGeracaoQualificada": "idc_geracao_qualificada",
    "NumCNPJDistribuidora": "num_cnpj_distribuidora",
    "SigTipoConsumidorAggregate": "sig_tipo_consumidor_agg",
    "NomSubEstacao": "nom_sub_estacao",
    "NumCoordNSub": "coord_n_sub",
    "NumCoordESub": "coord_e_sub",
    "MdaPotenciaCarga": "potencia_carga",
}

# Colunas na ordem do CSV para COPY FROM
COLUMNS = [
    "ckan_id", "dth_atualiza_cadastral", "sig_agente", "nom_agente",
    "cod_cep", "dsc_sub_grupo_tarifario", "dsc_classe_consumo",
    "dsc_sub_classe_consumo", "sig_uf", "nom_municipio", "cod_uf_ibge",
    "cod_municipio_ibge", "sig_tipo_consumidor", "num_cpf_cnpj",
    "nom_titular", "cod_empreendimento", "dth_conexao_inicial",
    "sig_tipo_geracao", "dsc_fonte_geracao", "dsc_porte", "sig_modalidade",
    "qtd_modulos", "potencia_instalada_kw", "potencia_fiscalizada_kw",
    "garantia_fisica_mwm", "coord_n", "coord_e", "idc_geracao_qualificada",
    "num_cnpj_distribuidora", "sig_tipo_consumidor_agg", "nom_sub_estacao",
    "coord_n_sub", "coord_e_sub", "potencia_carga",
]

# Campos numéricos que precisam de conversão
NUMERIC_FIELDS = {
    "ckan_id", "qtd_modulos",
    "potencia_instalada_kw", "potencia_fiscalizada_kw",
    "garantia_fisica_mwm", "coord_n", "coord_e",
    "coord_n_sub", "coord_e_sub", "potencia_carga",
}

# Campos de data
DATE_FIELDS = {"dth_atualiza_cadastral", "dth_conexao_inicial"}


def parse_value(col: str, value: str) -> Optional[str]:
    """Converte valor da API para formato adequado ao PostgreSQL."""
    if value is None or value == "" or value == "None":
        return None

    value = str(value).strip()

    if col in NUMERIC_FIELDS:
        try:
            # Tratar vírgula como separador decimal
            cleaned = value.replace(",", ".")
            float(cleaned)  # Validar
            return cleaned
        except (ValueError, TypeError):
            return None

    if col in DATE_FIELDS:
        # Tentar parsing de data
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return None

    return value


def record_to_row(record: dict) -> list:
    """Converte um registro da API CKAN para uma linha CSV."""
    row = []
    for col in COLUMNS:
        # Encontrar o campo original da API
        api_field = None
        for k, v in FIELD_MAP.items():
            if v == col:
                api_field = k
                break

        raw_value = record.get(api_field, None) if api_field else None
        parsed = parse_value(col, raw_value)
        row.append(parsed if parsed is not None else "")
    return row


def download_batch(client: httpx.Client, offset: int) -> dict:
    """Baixar um batch da API CKAN com retry."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.get(
                ANEEL_API_URL,
                params={
                    "resource_id": RESOURCE_ID,
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


def create_staging_table(conn):
    """Cria tabela staging sem constraints para COPY FROM rápido."""
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS gd_staging")
        cols_sql = ", ".join(f"{col} TEXT" for col in COLUMNS)
        cur.execute(f"CREATE UNLOGGED TABLE gd_staging ({cols_sql})")
    conn.commit()
    logger.info("Tabela staging criada")


def is_cnpj(cpf_cnpj: str) -> bool:
    """Verifica se o documento é CNPJ (14 dígitos) - filtra apenas PJ."""
    if not cpf_cnpj:
        return False
    digits = "".join(c for c in str(cpf_cnpj) if c.isdigit())
    return len(digits) == 14


def copy_batch_to_staging(conn, records: list) -> int:
    """Copia batch de registros PJ para staging table via COPY FROM.
    Retorna quantidade de registros PJ efetivamente inseridos."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
    pj_count = 0

    for record in records:
        # Filtrar apenas Pessoa Jurídica (CNPJ = 14 dígitos)
        cpf_cnpj = record.get("NumCPFCNPJ", "")
        if not is_cnpj(cpf_cnpj):
            continue

        row = record_to_row(record)
        # Substituir valores vazios por \N (NULL do PostgreSQL)
        row = [v if v != "" else "\\N" for v in row]
        writer.writerow(row)
        pj_count += 1

    if pj_count == 0:
        return 0

    buf.seek(0)
    cols_str = ", ".join(COLUMNS)

    with conn.cursor() as cur:
        cur.copy_expert(
            f"COPY gd_staging ({cols_str}) FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
            buf
        )
    conn.commit()
    return pj_count


def merge_staging_to_final(conn):
    """Merge dos dados do staging para a tabela final com ON CONFLICT."""
    cols_str = ", ".join(COLUMNS)
    update_cols = [c for c in COLUMNS if c != "cod_empreendimento"]
    update_str = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)

    # Converter tipos na inserção
    cast_expressions = []
    for col in COLUMNS:
        if col in {"ckan_id", "qtd_modulos"}:
            cast_expressions.append(f"{col}::INTEGER")
        elif col in {"potencia_instalada_kw", "potencia_fiscalizada_kw", "garantia_fisica_mwm",
                      "coord_n", "coord_e", "coord_n_sub", "coord_e_sub", "potencia_carga"}:
            cast_expressions.append(f"{col}::NUMERIC")
        elif col in {"dth_atualiza_cadastral", "dth_conexao_inicial"}:
            cast_expressions.append(f"{col}::TIMESTAMP")
        else:
            cast_expressions.append(col)

    select_cast = ", ".join(cast_expressions)

    # Deduplicar staging (manter último registro por cod_empreendimento)
    with conn.cursor() as cur:
        logger.info("Deduplicando staging table...")
        cur.execute("""
            DELETE FROM gd_staging a USING gd_staging b
            WHERE a.ctid < b.ctid
            AND a.cod_empreendimento = b.cod_empreendimento
            AND a.cod_empreendimento IS NOT NULL
            AND a.cod_empreendimento != ''
        """)
        dupes = cur.rowcount
        logger.info(f"Removidos {dupes:,} duplicados do staging")
    conn.commit()

    sql = f"""
        INSERT INTO geracao_distribuida ({cols_str}, created_at, updated_at)
        SELECT {select_cast}, NOW(), NOW()
        FROM gd_staging
        WHERE cod_empreendimento IS NOT NULL AND cod_empreendimento != ''
        ON CONFLICT (cod_empreendimento)
        DO UPDATE SET {update_str}, updated_at = NOW()
    """

    with conn.cursor() as cur:
        logger.info("Fazendo merge staging → geracao_distribuida...")
        cur.execute(sql)
        rows = cur.rowcount
        logger.info(f"Merge concluído: {rows} registros inseridos/atualizados")

    conn.commit()

    # Limpar staging
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS gd_staging")
    conn.commit()


def run_import():
    """Executa a importação completa."""
    start_time = time.time()

    logger.info("=" * 80)
    logger.info("IMPORTAÇÃO DE DADOS - GERAÇÃO DISTRIBUÍDA ANEEL (APENAS PJ)")
    logger.info(f"API: {ANEEL_API_URL}")
    logger.info(f"Resource ID: {RESOURCE_ID}")
    logger.info(f"Filtro: Apenas Pessoa Jurídica (CNPJ 14 dígitos)")
    logger.info("=" * 80)

    # Conectar ao banco
    logger.info(f"Conectando ao banco: {DATABASE_URL_SYNC[:50]}...")
    conn = psycopg2.connect(DATABASE_URL_SYNC)
    logger.info("Conectado ao banco de dados")

    # Criar staging table
    create_staging_table(conn)

    # Download e carga em batches
    total_downloaded = 0
    total_pj = 0
    total_records = None

    with httpx.Client() as client:
        # Primeiro batch para descobrir o total e o limit real da API
        logger.info("Baixando primeiro batch para descobrir total e limit da API...")
        result = download_batch(client, 0)
        total_records = result.get("total", 0)
        records = result.get("records", [])
        actual_batch_size = len(records)

        logger.info(f"Total de registros na API: {total_records:,}")
        logger.info(f"Limit real da API (registros por request): {actual_batch_size:,}")
        logger.info(f"Batches necessários: {(total_records + actual_batch_size - 1) // actual_batch_size}")

        # Carregar primeiro batch
        if records:
            pj_count = copy_batch_to_staging(conn, records)
            total_downloaded += len(records)
            total_pj += pj_count
            elapsed = time.time() - start_time
            rate = total_downloaded / elapsed if elapsed > 0 else 0
            logger.info(
                f"Batch 1: {total_downloaded:,}/{total_records:,} "
                f"({100 * total_downloaded / total_records:.1f}%) "
                f"- PJ: {total_pj:,} ({100 * total_pj / total_downloaded:.1f}%) "
                f"- {rate:.0f} rec/s"
            )

        # Continuar com os batches restantes - avançar pelo tamanho real retornado
        offset = actual_batch_size
        batch_num = 2

        while offset < total_records:
            result = download_batch(client, offset)
            records = result.get("records", [])

            if not records:
                logger.info("Sem mais registros, finalizando download")
                break

            pj_count = copy_batch_to_staging(conn, records)
            total_downloaded += len(records)
            total_pj += pj_count
            elapsed = time.time() - start_time
            rate = total_downloaded / elapsed if elapsed > 0 else 0
            eta = (total_records - total_downloaded) / rate if rate > 0 else 0

            if batch_num % 50 == 0 or batch_num <= 5:
                logger.info(
                    f"Batch {batch_num}: {total_downloaded:,}/{total_records:,} "
                    f"({100 * total_downloaded / total_records:.1f}%) "
                    f"- PJ: {total_pj:,} ({100 * total_pj / total_downloaded:.1f}%) "
                    f"- {rate:.0f} rec/s - ETA: {eta / 60:.1f} min"
                )

            offset += len(records)
            batch_num += 1

    logger.info(f"Download concluído: {total_downloaded:,} registros baixados, {total_pj:,} PJ filtrados")

    # Merge para tabela final
    merge_staging_to_final(conn)

    # ANALYZE para atualizar estatísticas do planner
    with conn.cursor() as cur:
        logger.info("Executando ANALYZE na tabela...")
        cur.execute("ANALYZE geracao_distribuida")
    conn.commit()

    # Verificar contagem final
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM geracao_distribuida")
        final_count = cur.fetchone()[0]

    conn.close()

    elapsed_total = time.time() - start_time
    logger.info("=" * 80)
    logger.info(f"IMPORTAÇÃO CONCLUÍDA (APENAS PJ)")
    logger.info(f"Total baixado da API: {total_downloaded:,}")
    logger.info(f"Total PJ filtrado: {total_pj:,}")
    logger.info(f"Total no banco: {final_count:,} registros")
    logger.info(f"Tempo total: {elapsed_total / 60:.1f} minutos")
    logger.info(f"Velocidade média: {total_downloaded / elapsed_total:.0f} rec/s")
    logger.info("=" * 80)


if __name__ == "__main__":
    try:
        run_import()
    except KeyboardInterrupt:
        logger.info("\nImportação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erro fatal na importação: {e}", exc_info=True)
        sys.exit(1)
