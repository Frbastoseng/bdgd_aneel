"""
Script para importar dados BDGD B3 de arquivo ZIP/CSV para Parquet.

Uso:
    python -m app.scripts.importar_b3 arquivo.zip [--limite N]

O CSV dentro do ZIP deve usar delimitador ';' e encoding 'utf-8'.
"""
import sys
import zipfile
import io
import csv
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    path1 = Path(__file__).parent.parent.parent / "data"
    path2 = Path("/app/data")
    path3 = Path.cwd() / "data"
    for path in [path2, path1, path3]:
        if path.exists():
            return path
    path1.mkdir(parents=True, exist_ok=True)
    return path1


# Mapeamento CSV → Parquet (mantendo nomes originais para compatibilidade com ANEEL)
CSV_COLUMNS = {
    "COD_ID_ENCR": "COD_ID_ENCR",
    "DIST": "DIST",
    "PAC": "PAC",
    "RAMAL": "RAMAL",
    "PN_CON": "PN_CON",
    "UNI_TR_MT": "UNI_TR_MT",
    "CTMT": "CTMT",
    "UNI_TR_AT": "UNI_TR_AT",
    "SUB": "SUB",
    "CONJ": "CONJ",
    "MUN": "MUN",
    "LGRD": "LGRD",
    "BRR": "BRR",
    "CEP": "CEP",
    "POINT_Y": "POINT_Y",
    "POINT_X": "POINT_X",
    "ARE_LOC": "ARE_LOC",
    "CLAS_SUB": "CLAS_SUB",
    "CNAE": "CNAE",
    "TIP_CC": "TIP_CC",
    "FAS_CON": "FAS_CON",
    "GRU_TEN": "GRU_TEN",
    "TEN_FORN": "TEN_FORN",
    "GRU_TAR": "GRU_TAR",
    "SIT_ATIV": "SIT_ATIV",
    "DAT_CON": "DAT_CON",
    "CAR_INST": "CAR_INST",
    "TIP_SIST": "TIP_SIST",
    "CEG_GD": "CEG_GD",
    "DATA_BASE": "DATA_BASE",
    "DESCR": "DESCR",
    "OBJECTID": "OBJECTID",
}

# Adicionar colunas mensais
for i in range(1, 13):
    m = str(i).zfill(2)
    CSV_COLUMNS[f"ENE_{m}"] = f"ENE_{m}"
    CSV_COLUMNS[f"DIC_{m}"] = f"DIC_{m}"
    CSV_COLUMNS[f"FIC_{m}"] = f"FIC_{m}"

FLOAT_COLUMNS = (
    ["CAR_INST", "TEN_FORN", "POINT_X", "POINT_Y"] +
    [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)] +
    [f"DIC_{str(i).zfill(2)}" for i in range(1, 13)] +
    [f"FIC_{str(i).zfill(2)}" for i in range(1, 13)]
)


def _parse_float(value: str) -> Optional[float]:
    """Converte string para float, tratando vírgula como decimal."""
    if not value or value.strip() == "":
        return None
    try:
        return float(value.replace(",", "."))
    except (ValueError, TypeError):
        return None


def importar_b3_zip(zip_path: str, limite: Optional[int] = None) -> dict:
    """
    Importa dados B3 de arquivo ZIP contendo CSV.

    Args:
        zip_path: Caminho para o arquivo ZIP
        limite: Limite de registros (None = todos)

    Returns:
        dict com resultado da importação
    """
    data_dir = _get_data_dir()
    output_file = data_dir / "dados_b3.parquet"

    logger.info(f"Importando B3 de {zip_path}")
    logger.info(f"Saída: {output_file}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Encontrar CSV dentro do ZIP
        csv_files = [f for f in zf.namelist() if f.endswith(".csv")]
        if not csv_files:
            raise ValueError("Nenhum arquivo CSV encontrado dentro do ZIP")

        csv_filename = csv_files[0]
        logger.info(f"Lendo CSV: {csv_filename}")

        with zf.open(csv_filename) as csv_file:
            text_stream = io.TextIOWrapper(csv_file, encoding="utf-8", errors="replace")
            reader = csv.DictReader(text_stream, delimiter=";")

            records = []
            count = 0

            for row in reader:
                record = {}

                for csv_col, parquet_col in CSV_COLUMNS.items():
                    value = row.get(csv_col, "")
                    if value is None:
                        value = ""
                    value = value.strip()

                    if parquet_col in FLOAT_COLUMNS:
                        record[parquet_col] = _parse_float(value)
                    else:
                        record[parquet_col] = value if value else None

                records.append(record)
                count += 1

                if count % 50000 == 0:
                    logger.info(f"  Processados {count:,} registros...")

                if limite and count >= limite:
                    break

    logger.info(f"Total de registros lidos: {count:,}")

    # Converter para DataFrame
    df = pd.DataFrame(records)

    # Calcular campos derivados
    ene_cols = [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)]
    dic_cols = [f"DIC_{str(i).zfill(2)}" for i in range(1, 13)]
    fic_cols = [f"FIC_{str(i).zfill(2)}" for i in range(1, 13)]

    ene_existentes = [c for c in ene_cols if c in df.columns]
    dic_existentes = [c for c in dic_cols if c in df.columns]
    fic_existentes = [c for c in fic_cols if c in df.columns]

    if ene_existentes:
        for c in ene_existentes:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

        df["CONSUMO_ANUAL"] = df[ene_existentes].sum(axis=1)
        meses_positivos = (df[ene_existentes] > 0).sum(axis=1)
        df["CONSUMO_MEDIO"] = np.where(
            meses_positivos > 0,
            df["CONSUMO_ANUAL"] / meses_positivos,
            0
        )
        df["ENE_MAX"] = df[ene_existentes].max(axis=1)

    if dic_existentes:
        for c in dic_existentes:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df["DIC_ANUAL"] = df[dic_existentes].sum(axis=1)

    if fic_existentes:
        for c in fic_existentes:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df["FIC_ANUAL"] = df[fic_existentes].sum(axis=1)

    # Solar
    if "CEG_GD" in df.columns:
        df["POSSUI_SOLAR"] = df["CEG_GD"].notna() & (df["CEG_GD"] != "")

    # Salvar parquet
    df.to_parquet(output_file, index=False)
    logger.info(f"Parquet salvo: {output_file} ({len(df):,} registros)")

    return {
        "message": f"Importação concluída: {len(df):,} registros",
        "total_registros": len(df),
        "arquivo": str(output_file)
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if len(sys.argv) < 2:
        print("Uso: python -m app.scripts.importar_b3 <arquivo.zip> [--limite N]")
        sys.exit(1)

    zip_path = sys.argv[1]
    limite = None

    if "--limite" in sys.argv:
        idx = sys.argv.index("--limite")
        if idx + 1 < len(sys.argv):
            limite = int(sys.argv[idx + 1])

    resultado = importar_b3_zip(zip_path, limite)
    print(resultado["message"])
