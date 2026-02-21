"""
Processes downloaded Receita Federal ZIP files and loads into crm.cnpj_cache.

The Receita Federal distributes CNPJ data across multiple file types:
- Empresas:         CNPJ_BASICO -> razao_social, capital_social, porte, natureza_juridica
- Estabelecimentos: CNPJ completo -> endereco, contato, CNAE, situacao_cadastral
- Socios:           CNPJ_BASICO -> QSA (quadro societario)
- Simples:          CNPJ_BASICO -> opcao_pelo_simples, opcao_pelo_mei

Processing strategy (2-pass, memory-efficient):
1. Load lookup tables into memory (Cnaes, Municipios, etc.)
2. Pre-scan Estabelecimentos to collect ATIVA cnpj_basico values (~8M of 56M)
3. Load Simples filtered to needed basicos, identify MEIs
4. Load Empresas filtered to needed basicos (minus MEIs)
5. Stream Estabelecimentos again, join with all data, insert
6. Stream Socios, aggregate by CNPJ_BASICO, batch-update rows

Filters applied:
- situacao_cadastral = 02 (ATIVA) only
- opcao_pelo_mei != 'S' (exclude MEI)

Memory usage: ~2-3 GB instead of 20+ GB by only loading needed records.
"""

import csv
import gc
import json
import logging
import zipfile
from datetime import datetime, timezone
from io import TextIOWrapper
from pathlib import Path

from psycopg2.extras import execute_values
from sqlalchemy import text

from cnpj.config import BATCH_SIZE, DOWNLOAD_DIR, ENCODING, SCHEMA, SEPARATOR
from cnpj.database import get_session

logger = logging.getLogger(__name__)

# ---- Optional progress callback (set by cnpj_bulk_update service) ----
_progress_callback = None


def set_progress_callback(callback):
    """Set a callback function for progress reporting.

    Callback signature: (step_name: str, step_number: int, total_steps: int, detail: str)
    """
    global _progress_callback
    _progress_callback = callback


def _report_progress(step_name: str, step_number: int, total_steps: int, detail: str = ""):
    if _progress_callback:
        _progress_callback(step_name, step_number, total_steps, detail)


# Situacao cadastral codes
SITUACAO_ATIVA = "02"
SITUACAO_MAP = {
    "01": "NULA",
    "02": "ATIVA",
    "03": "SUSPENSA",
    "04": "INAPTA",
    "08": "BAIXADA",
}

# Porte codes
PORTE_MAP = {
    "00": "NAO INFORMADO",
    "01": "MICRO EMPRESA",
    "03": "EMPRESA DE PEQUENO PORTE",
    "05": "DEMAIS",
}

# Empresa tuple field indices
_E_RAZAO = 0
_E_NATUREZA = 1
_E_QUAL_RESP = 2
_E_CAPITAL = 3
_E_PORTE = 4


def _read_csv_from_zip(zip_path: Path):
    """
    Generator that yields rows from a CSV inside a ZIP file.

    Receita Federal CSVs:
    - Encoding: ISO-8859-1
    - Separator: semicolon
    - No header row
    - Fields quoted with double-quotes
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        csv_names = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
        if not csv_names:
            return

        for csv_name in csv_names:
            with zf.open(csv_name) as raw:
                reader = csv.reader(
                    TextIOWrapper(raw, encoding=ENCODING),
                    delimiter=SEPARATOR,
                    quotechar='"',
                )
                yield from reader


def _format_date(date_str: str) -> str | None:
    """Convert YYYYMMDD to YYYY-MM-DD, or return None."""
    if not date_str or date_str == "0" or len(date_str) != 8:
        return None
    try:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    except Exception:
        return None


def _format_phone(ddd: str, number: str) -> str | None:
    """Format phone as (DDD) NUMBER."""
    ddd = (ddd or "").strip()
    number = (number or "").strip()
    if not ddd or not number:
        return None
    return f"({ddd}) {number}"


def _clean(val: str | None) -> str | None:
    """Strip whitespace and return None for empty strings."""
    if val is None:
        return None
    val = val.strip()
    return val if val else None


# ---- Lookup loading ----


def load_lookups() -> dict:
    """Load all lookup tables into memory dicts."""
    lookups = {
        "cnaes": {},       # code -> description
        "municipios": {},  # code -> name
        "naturezas": {},   # code -> description
        "qualificacoes": {},  # code -> description
        "motivos": {},     # code -> description
        "paises": {},      # code -> name
    }

    files = {
        "cnaes": "Cnaes.zip",
        "municipios": "Municipios.zip",
        "naturezas": "Naturezas.zip",
        "qualificacoes": "Qualificacoes.zip",
        "motivos": "Motivos.zip",
        "paises": "Paises.zip",
    }

    for key, filename in files.items():
        path = DOWNLOAD_DIR / filename
        if not path.exists():
            logger.warning("Lookup file not found: %s", path)
            continue

        count = 0
        for row in _read_csv_from_zip(path):
            if len(row) >= 2:
                lookups[key][row[0].strip()] = row[1].strip()
                count += 1

        logger.info("Loaded %d %s entries.", count, key)

    return lookups


# ---- Pre-scan Estabelecimentos ----


def prescan_estabelecimentos() -> set:
    """
    Quick scan of Estabelecimentos to collect cnpj_basico values
    for records with situacao_cadastral = ATIVA.

    Returns a set of cnpj_basico strings (~8M entries, ~500MB).
    """
    needed = set()
    total_rows = 0

    for i in range(10):
        path = DOWNLOAD_DIR / f"Estabelecimentos{i}.zip"
        if not path.exists():
            continue

        logger.info("  Pre-scanning %s ...", path.name)
        file_count = 0

        for row in _read_csv_from_zip(path):
            total_rows += 1
            if len(row) < 6:
                continue

            if row[5].strip() == SITUACAO_ATIVA:
                needed.add(row[0].strip())
                file_count += 1

        logger.info("    %s: %d ATIVA basicos found.", path.name, file_count)

    logger.info("  Pre-scan complete: %d unique ATIVA basicos from %d total rows.",
                len(needed), total_rows)
    return needed


# ---- Simples loading (filtered) ----


def load_simples_filtered(needed_basicos: set) -> tuple:
    """
    Load Simples data only for cnpj_basico values in needed_basicos.
    Returns (simples_info, mei_subset) where:
    - simples_info: dict[str, tuple(str|None, str|None)] = {cnpj_basico: (opt_simples, opt_mei)}
    - mei_subset: set of cnpj_basico where opcao_pelo_mei == 'S'
    """
    simples_info = {}  # cnpj_basico -> (opt_simples, opt_mei)
    mei_subset = set()

    path = DOWNLOAD_DIR / "Simples.zip"
    if not path.exists():
        logger.warning("Simples.zip not found - MEI filter will not work!")
        return simples_info, mei_subset

    logger.info("Loading %s (filtered to %d needed basicos) ...", path.name, len(needed_basicos))
    count = 0
    for row in _read_csv_from_zip(path):
        if len(row) < 5:
            continue

        cnpj_basico = row[0].strip()
        if cnpj_basico not in needed_basicos:
            continue

        opt_simples = _clean(row[1])
        opt_mei = _clean(row[4]) if len(row) > 4 else None

        simples_info[cnpj_basico] = (opt_simples, opt_mei)
        if opt_mei == "S":
            mei_subset.add(cnpj_basico)
        count += 1

    logger.info("  Simples: %d entries loaded, %d are MEI.", count, len(mei_subset))
    return simples_info, mei_subset


# ---- Empresas loading (filtered) ----


def load_empresas_filtered(needed_basicos: set) -> dict:
    """
    Load Empresas data only for cnpj_basico values in needed_basicos.
    Uses tuples for memory efficiency.

    Returns dict[str, tuple]: cnpj_basico -> (razao_social, natureza_code, qual_resp, capital, porte_code)
    """
    empresas = {}

    for i in range(10):
        path = DOWNLOAD_DIR / f"Empresas{i}.zip"
        if not path.exists():
            logger.warning("File not found: %s", path)
            continue

        logger.info("Loading %s (filtered) ...", path.name)
        count = 0
        for row in _read_csv_from_zip(path):
            if len(row) < 6:
                continue

            cnpj_basico = row[0].strip()
            if cnpj_basico not in needed_basicos:
                continue

            try:
                capital = float(row[4].strip().replace(",", ".")) if row[4].strip() else None
            except ValueError:
                capital = None

            empresas[cnpj_basico] = (
                _clean(row[1]),   # razao_social
                _clean(row[2]),   # natureza_juridica_code
                _clean(row[3]),   # qualificacao_responsavel
                capital,          # capital_social
                _clean(row[5]),   # porte_code
            )
            count += 1

        logger.info("  %s: %d empresas loaded.", path.name, count)

    logger.info("Total empresas in memory: %d (of %d needed)", len(empresas), len(needed_basicos))
    return empresas


# ---- Main loader ----


def load_estabelecimentos(
    empresas: dict,
    simples_info: dict,
    mei_set: set,
    lookups: dict,
):
    """
    Stream Estabelecimentos files, join with Empresas + Simples + lookups,
    filter (ATIVA, non-MEI), and bulk-insert into crm.cnpj_cache.
    """
    session = get_session()

    # Truncate for fresh load
    logger.info("Truncating cnpj_cache for fresh load ...")
    session.execute(text(f"TRUNCATE TABLE {SCHEMA}.cnpj_cache"))
    session.commit()

    # Get raw psycopg2 connection for execute_values
    raw_conn = session.get_bind().raw_connection()
    cursor = raw_conn.cursor()

    total_inserted = 0
    total_skipped = 0
    total_mei_skipped = 0
    batch = []

    insert_sql = f"""
        INSERT INTO {SCHEMA}.cnpj_cache (
            cnpj, razao_social, nome_fantasia, situacao_cadastral,
            data_situacao_cadastral, data_inicio_atividade,
            natureza_juridica, porte, capital_social,
            cnae_fiscal, cnae_fiscal_descricao, cnaes_secundarios,
            logradouro, numero, complemento, bairro,
            municipio, uf, cep,
            telefone_1, telefone_2, email,
            socios,
            opcao_pelo_simples, opcao_pelo_mei,
            data_consulta, raw_json
        ) VALUES %s
    """

    row_template = """(
        %(cnpj)s, %(razao_social)s, %(nome_fantasia)s, %(situacao_cadastral)s,
        %(data_situacao_cadastral)s, %(data_inicio_atividade)s,
        %(natureza_juridica)s, %(porte)s, %(capital_social)s,
        %(cnae_fiscal)s, %(cnae_fiscal_descricao)s, %(cnaes_secundarios)s::jsonb,
        %(logradouro)s, %(numero)s, %(complemento)s, %(bairro)s,
        %(municipio)s, %(uf)s, %(cep)s,
        %(telefone_1)s, %(telefone_2)s, %(email)s,
        %(socios)s::jsonb,
        %(opcao_pelo_simples)s, %(opcao_pelo_mei)s,
        %(data_consulta)s, %(raw_json)s::jsonb
    )"""

    now = datetime.now(timezone.utc)

    for i in range(10):
        path = DOWNLOAD_DIR / f"Estabelecimentos{i}.zip"
        if not path.exists():
            logger.warning("File not found: %s", path)
            continue

        logger.info("Processing %s ...", path.name)
        file_count = 0

        for row in _read_csv_from_zip(path):
            if len(row) < 28:
                continue

            # Filter: only ATIVA
            situacao_code = row[5].strip()
            if situacao_code != SITUACAO_ATIVA:
                total_skipped += 1
                continue

            cnpj_basico = row[0].strip()
            cnpj_ordem = row[1].strip()
            cnpj_dv = row[2].strip()
            cnpj = f"{cnpj_basico}{cnpj_ordem}{cnpj_dv}"

            if len(cnpj) != 14:
                total_skipped += 1
                continue

            # Filter: exclude MEI
            if cnpj_basico in mei_set:
                total_mei_skipped += 1
                continue

            # Join with Empresas (tuple)
            empresa = empresas.get(cnpj_basico)

            # Resolve lookups
            cnae_principal = _clean(row[11])
            cnae_desc = lookups.get("cnaes", {}).get(cnae_principal, "") if cnae_principal else None
            municipio_code = _clean(row[20])
            municipio_name = lookups.get("municipios", {}).get(municipio_code, "") if municipio_code else None
            natureza_code = empresa[_E_NATUREZA] if empresa else None
            natureza_desc = lookups.get("naturezas", {}).get(natureza_code, "") if natureza_code else None
            porte_code = empresa[_E_PORTE] if empresa else None
            porte_desc = PORTE_MAP.get(porte_code, "") if porte_code else None

            # Build CNAE secundarios
            cnaes_sec_raw = _clean(row[12])
            cnaes_secundarios = None
            if cnaes_sec_raw:
                codes = [c.strip() for c in cnaes_sec_raw.split(",") if c.strip() and c.strip() != "0000000"]
                if codes:
                    cnaes_secundarios = json.dumps([
                        {
                            "codigo": c,
                            "descricao": lookups.get("cnaes", {}).get(c, ""),
                        }
                        for c in codes
                    ], ensure_ascii=False)

            # Resolve simples/mei values
            si = simples_info.get(cnpj_basico)
            opt_simples = si[0] if si else None
            opt_mei = si[1] if si else None
            qual_resp = empresa[_E_QUAL_RESP] if empresa else None

            # Build record
            record = {
                "cnpj": cnpj,
                "razao_social": empresa[_E_RAZAO] if empresa else None,
                "nome_fantasia": _clean(row[4]),
                "situacao_cadastral": SITUACAO_MAP.get(situacao_code, situacao_code),
                "data_situacao_cadastral": _format_date(row[6].strip()),
                "data_inicio_atividade": _format_date(row[10].strip()),
                "natureza_juridica": f"{natureza_code} - {natureza_desc}" if natureza_code and natureza_desc else natureza_desc,
                "porte": porte_desc,
                "capital_social": empresa[_E_CAPITAL] if empresa else None,
                "cnae_fiscal": cnae_principal,
                "cnae_fiscal_descricao": cnae_desc,
                "cnaes_secundarios": cnaes_secundarios,
                "logradouro": f"{_clean(row[13]) or ''} {_clean(row[14]) or ''}".strip() or None,
                "numero": _clean(row[15]),
                "complemento": _clean(row[16]),
                "bairro": _clean(row[17]),
                "municipio": municipio_name,
                "uf": _clean(row[19]),
                "cep": _clean(row[18]),
                "telefone_1": _format_phone(row[21], row[22]),
                "telefone_2": _format_phone(row[23], row[24]) if len(row) > 24 else None,
                "email": (_clean(row[27]) or "").lower() or None if len(row) > 27 else None,
                "socios": None,
                "opcao_pelo_simples": opt_simples,
                "opcao_pelo_mei": opt_mei,
                "data_consulta": now,
                "raw_json": json.dumps({
                    "cnpj_basico": cnpj_basico,
                    "identificador_matriz_filial": int(row[3].strip()) if row[3].strip() else None,
                    "motivo_situacao_cadastral": _clean(row[7]),
                    "nome_cidade_exterior": _clean(row[8]),
                    "pais": lookups.get("paises", {}).get(_clean(row[9]), "") if _clean(row[9]) else None,
                    "situacao_especial": _clean(row[28]) if len(row) > 28 else None,
                    "data_situacao_especial": _format_date(row[29].strip()) if len(row) > 29 else None,
                    "descricao_tipo_logradouro": _clean(row[13]),
                    "qualificacao_do_responsavel": int(qual_resp) if qual_resp else None,
                    "ddd_fax": _format_phone(row[25], row[26]) if len(row) > 26 else None,
                    "descricao_situacao_cadastral": SITUACAO_MAP.get(situacao_code, situacao_code),
                    "descricao_identificador_matriz_filial": "MATRIZ" if row[3].strip() == "1" else "FILIAL" if row[3].strip() == "2" else None,
                    "descricao_motivo_situacao_cadastral": lookups.get("motivos", {}).get(_clean(row[7]), "") if _clean(row[7]) else None,
                    "_source": "receita_federal_bulk",
                    "_loaded_at": now.isoformat(),
                }, ensure_ascii=False),
            }

            batch.append(record)
            file_count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(cursor, raw_conn, insert_sql, row_template, batch)
                total_inserted += len(batch)
                batch = []

                if total_inserted % 100000 == 0:
                    logger.info(
                        "  Progress: %d inserted, %d skipped (inactive), %d skipped (MEI)",
                        total_inserted, total_skipped, total_mei_skipped,
                    )

        logger.info("  %s: %d records processed.", path.name, file_count)

    # Flush remaining
    if batch:
        _flush_batch(cursor, raw_conn, insert_sql, row_template, batch)
        total_inserted += len(batch)

    cursor.close()
    raw_conn.close()
    session.close()

    logger.info("=" * 60)
    logger.info("Loading complete!")
    logger.info("  Inserted/updated: %d", total_inserted)
    logger.info("  Skipped (inactive): %d", total_skipped)
    logger.info("  Skipped (MEI): %d", total_mei_skipped)
    logger.info("=" * 60)

    return {
        "inserted": total_inserted,
        "skipped_inactive": total_skipped,
        "skipped_mei": total_mei_skipped,
    }


def _flush_batch(cursor, conn, sql, template, batch: list):
    """Insert a batch using psycopg2 execute_values (multi-row INSERT)."""
    try:
        execute_values(cursor, sql, batch, template=template, page_size=len(batch))
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error("Error inserting batch: %s", e)
        raise


def load_socios(lookups: dict):
    """
    Load Socios data and update existing cnpj_cache rows.

    Socios CSV columns:
    0: CNPJ_BASICO (8 digits)
    1: IDENTIFICADOR_SOCIO (1=PJ, 2=PF, 3=Estrangeiro)
    2: NOME_SOCIO_RAZAO_SOCIAL
    3: CNPJ_CPF_SOCIO
    4: QUALIFICACAO_SOCIO (code)
    5: DATA_ENTRADA_SOCIEDADE (YYYYMMDD)
    6: PAIS (code)
    7: REPRESENTANTE_LEGAL
    8: NOME_REPRESENTANTE
    9: QUALIFICACAO_REPRESENTANTE (code)
    10: FAIXA_ETARIA (code)
    """
    # First, aggregate socios by CNPJ_BASICO
    socios_map: dict[str, list] = {}

    for i in range(10):
        path = DOWNLOAD_DIR / f"Socios{i}.zip"
        if not path.exists():
            logger.warning("File not found: %s", path)
            continue

        logger.info("Loading socios from %s ...", path.name)
        count = 0

        for row in _read_csv_from_zip(path):
            if len(row) < 7:
                continue

            cnpj_basico = row[0].strip()
            nome = _clean(row[2])
            qual_code = _clean(row[4])
            qual_desc = lookups.get("qualificacoes", {}).get(qual_code, "") if qual_code else ""

            socio = {
                "nome": nome or "",
                "qualificacao": qual_desc or qual_code or "",
            }

            if cnpj_basico not in socios_map:
                socios_map[cnpj_basico] = []
            socios_map[cnpj_basico].append(socio)
            count += 1

        logger.info("  %s: %d socios loaded.", path.name, count)

    logger.info("Updating cnpj_cache with socios data for %d CNPJ bases ...", len(socios_map))

    # Use temp table + batch UPDATE for speed
    session = get_session()
    raw_conn = session.get_bind().raw_connection()
    cursor = raw_conn.cursor()

    # Create temp table
    cursor.execute("""
        CREATE TEMP TABLE _tmp_socios (
            cnpj_basico TEXT NOT NULL,
            socios JSONB NOT NULL
        ) ON COMMIT PRESERVE ROWS
    """)
    raw_conn.commit()

    # Bulk insert socios_map into temp table
    socios_data = [
        {"cnpj_basico": k, "socios": json.dumps(v, ensure_ascii=False)}
        for k, v in socios_map.items()
    ]
    del socios_map
    gc.collect()

    logger.info("  Inserting %d socios entries into temp table ...", len(socios_data))

    for i in range(0, len(socios_data), 50000):
        chunk = socios_data[i : i + 50000]
        execute_values(
            cursor,
            "INSERT INTO _tmp_socios (cnpj_basico, socios) VALUES %s",
            chunk,
            template="(%(cnpj_basico)s, %(socios)s::jsonb)",
            page_size=len(chunk),
        )
        raw_conn.commit()
        if (i + 50000) % 500000 < 50000:
            logger.info("  Temp table: %d/%d inserted.", min(i + 50000, len(socios_data)), len(socios_data))

    del socios_data
    gc.collect()

    # Create index on temp table for join performance
    logger.info("  Creating index on temp table ...")
    cursor.execute("CREATE INDEX ON _tmp_socios (cnpj_basico)")
    raw_conn.commit()

    # Single UPDATE using LEFT(cnpj, 8) join
    logger.info("  Running batch UPDATE join ...")
    cursor.execute(f"""
        UPDATE {SCHEMA}.cnpj_cache c
        SET socios = t.socios
        FROM _tmp_socios t
        WHERE LEFT(c.cnpj, 8) = t.cnpj_basico
    """)
    updated = cursor.rowcount
    raw_conn.commit()

    # Cleanup
    cursor.execute("DROP TABLE IF EXISTS _tmp_socios")
    raw_conn.commit()
    cursor.close()
    raw_conn.close()
    session.close()

    logger.info("Socios update complete: %d rows updated.", updated)


def cleanup_downloads():
    """Delete all downloaded ZIP files to free disk space."""
    if not DOWNLOAD_DIR.exists():
        return

    deleted = 0
    freed = 0
    for f in DOWNLOAD_DIR.glob("*.zip"):
        size = f.stat().st_size
        f.unlink()
        deleted += 1
        freed += size

    if deleted:
        logger.info(
            "Cleanup: deleted %d ZIP files, freed %.1f GB.",
            deleted, freed / (1024 * 1024 * 1024),
        )


def run_full_load(delete_after: bool = True):
    """
    Execute the complete load pipeline (2-pass, memory-efficient):
    1. Load lookups
    2. Pre-scan Estabelecimentos for ATIVA cnpj_basicos
    3. Load Simples (filtered), identify MEIs
    4. Load Empresas (filtered to non-MEI ATIVA basicos)
    5. Stream Estabelecimentos, join, filter, insert
    6. Load Socios and update rows
    7. Delete ZIP files (optional)
    """
    logger.info("=" * 60)
    logger.info("Starting full CNPJ data load pipeline (2-pass)")
    logger.info("=" * 60)

    start = datetime.now()

    # Step 1: Lookups
    logger.info("\n[1/7] Loading lookup tables ...")
    _report_progress("Carregando tabelas de lookup", 1, 7)
    lookups = load_lookups()

    # Step 2: Pre-scan Estabelecimentos
    logger.info("\n[2/7] Pre-scanning Estabelecimentos for ATIVA records ...")
    _report_progress("Pre-scan Estabelecimentos (empresas ativas)", 2, 7)
    needed_basicos = prescan_estabelecimentos()

    # Step 3: Simples (filtered)
    logger.info("\n[3/7] Loading Simples (filtered to %d basicos) ...", len(needed_basicos))
    _report_progress("Carregando Simples Nacional", 3, 7, f"{len(needed_basicos):,} basicos")
    simples_info, mei_subset = load_simples_filtered(needed_basicos)

    # Remove MEIs from needed set
    final_basicos = needed_basicos - mei_subset
    mei_count = len(needed_basicos) - len(final_basicos)
    logger.info("  Removed %d MEI basicos, %d remaining.", mei_count, len(final_basicos))
    del needed_basicos
    gc.collect()

    # Step 4: Empresas (filtered)
    logger.info("\n[4/7] Loading Empresas (filtered to %d basicos) ...", len(final_basicos))
    _report_progress("Carregando Empresas", 4, 7, f"{len(final_basicos):,} basicos")
    empresas = load_empresas_filtered(final_basicos)
    del final_basicos
    gc.collect()

    # Step 5: Estabelecimentos (main load - 2nd pass)
    logger.info("\n[5/7] Processing Estabelecimentos (main load) ...")
    _report_progress("Processando Estabelecimentos (carga principal)", 5, 7)
    result = load_estabelecimentos(empresas, simples_info, mei_subset, lookups)

    # Free memory before loading socios
    del empresas, simples_info, mei_subset
    gc.collect()

    # Step 6: Socios
    logger.info("\n[6/7] Loading Socios ...")
    _report_progress("Carregando Socios (QSA)", 6, 7, f"{result['inserted']:,} registros base")
    load_socios(lookups)

    # Step 7: Cleanup
    if delete_after:
        logger.info("\n[7/7] Cleaning up downloaded files ...")
        _report_progress("Limpando arquivos temporarios", 7, 7)
        cleanup_downloads()
    else:
        logger.info("\n[7/7] Skipping cleanup (delete_after=False).")
        _report_progress("Finalizando", 7, 7)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("\n" + "=" * 60)
    logger.info("Full load complete in %.1f minutes.", elapsed / 60)
    logger.info("  Records loaded: %d", result["inserted"])
    logger.info("  Skipped (inactive): %d", result["skipped_inactive"])
    logger.info("  Skipped (MEI): %d", result["skipped_mei"])
    logger.info("=" * 60)

    return result
