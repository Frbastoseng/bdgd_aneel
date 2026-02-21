"""
Serviço para consulta de dados BDGD B3 (Baixa Tensão)

Otimizado para 11.5M+ registros:
  - Carregamento async via run_in_executor (não bloqueia event loop)
  - opcoes-filtros usa IBGE direto (sem carregar parquet)
  - Carregamento lazy com status de "loading"
"""
import asyncio
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
import io
import logging
import os
from datetime import datetime

from app.schemas.b3 import (
    FiltroB3,
    ClienteB3,
    PontoMapaB3,
    CLAS_SUB_B3_MAP,
)
from app.schemas.aneel import CLAS_SUB_MAP

logger = logging.getLogger(__name__)


def _get_data_dir() -> Path:
    """Encontra o diretório de dados."""
    path1 = Path(__file__).parent.parent.parent / "data"
    path2 = Path("/app/data")
    path3 = Path.cwd() / "data"
    for path in [path2, path1, path3]:
        if path.exists():
            return path
    path1.mkdir(parents=True, exist_ok=True)
    return path1


DATA_DIR = _get_data_dir()
B3_DATA_FILE = DATA_DIR / "dados_b3.parquet"

# Cache em memória
_cache_b3_processado: Optional[pd.DataFrame] = None
_cache_b3_opcoes: Optional[Dict[str, Any]] = None
_cache_b3_por_uf: Dict[str, pd.DataFrame] = {}
_cache_loading: bool = False



# Colunas essenciais para consulta e mapa (sem mensais ENE/DIC/FIC que usam muita RAM)
_COLUNAS_ESSENCIAIS = [
    "COD_ID_ENCR", "DIST", "PAC", "MUN", "LGRD", "BRR", "CEP",
    "CLAS_SUB", "CNAE", "TIP_CC", "FAS_CON", "GRU_TEN", "TEN_FORN",
    "GRU_TAR", "SIT_ATIV", "DAT_CON", "CAR_INST", "TIP_SIST",
    "CEG_GD", "ARE_LOC", "POINT_X", "POINT_Y",
    # Campos pré-calculados no parquet (importação já calculou)
    "CONSUMO_ANUAL", "CONSUMO_MEDIO", "DIC_ANUAL", "FIC_ANUAL",
    "POSSUI_SOLAR",
]

# Colunas mensais (carregadas on-demand para detalhes de 1 registro)
_COLUNAS_MENSAIS = [
    f"{prefix}_{str(i).zfill(2)}" for prefix in ["ENE", "DIC", "FIC"]
    for i in range(1, 13)
]


def _carregar_e_processar_sync() -> pd.DataFrame:
    """Carrega e processa parquet B3 (chamado em thread).

    Carrega apenas colunas essenciais (~25 cols) em vez de todas (~60 cols)
    para reduzir uso de memória de ~6GB para ~2GB com 11.5M registros.
    """
    global _cache_b3_processado, _cache_loading

    if _cache_b3_processado is not None:
        return _cache_b3_processado

    if not B3_DATA_FILE.exists():
        logger.warning(f"B3: Arquivo não encontrado: {B3_DATA_FILE}")
        return pd.DataFrame()

    _cache_loading = True
    try:
        logger.info(f"B3: Iniciando carregamento de {B3_DATA_FILE} (colunas essenciais)...")

        # Descobrir quais colunas existem no parquet
        try:
            import pyarrow.parquet as pq
            schema = pq.read_schema(str(B3_DATA_FILE))
            colunas_parquet = set(schema.names)
            colunas_carregar = [c for c in _COLUNAS_ESSENCIAIS if c in colunas_parquet]
            logger.info(f"B3: Carregando {len(colunas_carregar)} de {len(colunas_parquet)} colunas")
            df = pd.read_parquet(B3_DATA_FILE, columns=colunas_carregar)
        except Exception:
            # Fallback: carregar tudo (pode OOM mas pelo menos tenta)
            logger.warning("B3: Fallback - carregando todas as colunas")
            df = pd.read_parquet(B3_DATA_FILE)

        logger.info(f"B3: Carregados {len(df)} registros, processando...")

        # Processar dados
        df = _processar_dados(df)
        df = _enriquecer_com_localidades(df)

        _cache_b3_processado = df
        logger.info(f"B3: Cache pronto com {len(df)} registros processados")
        return df
    finally:
        _cache_loading = False


def _processar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Processa e limpa os dados B3"""
    if df.empty:
        return df

    # Converter colunas numéricas
    colunas_numericas = ["CAR_INST", "TEN_FORN", "POINT_X", "POINT_Y"]
    for i in range(1, 13):
        m = str(i).zfill(2)
        colunas_numericas.extend([f"ENE_{m}", f"DIC_{m}", f"FIC_{m}"])

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcular campos derivados se não existem
    ene_cols = [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)]
    ene_existentes = [c for c in ene_cols if c in df.columns]

    if ene_existentes:
        if "CONSUMO_ANUAL" not in df.columns:
            df["CONSUMO_ANUAL"] = df[ene_existentes].sum(axis=1)
        if "CONSUMO_MEDIO" not in df.columns:
            ene_values = df[ene_existentes]
            meses_com_consumo = (ene_values > 0).sum(axis=1)
            df["CONSUMO_MEDIO"] = np.where(
                meses_com_consumo > 0,
                df[ene_existentes].sum(axis=1) / meses_com_consumo,
                0
            )
        if "ENE_MAX" not in df.columns:
            df["ENE_MAX"] = df[ene_existentes].max(axis=1)

    dic_cols = [f"DIC_{str(i).zfill(2)}" for i in range(1, 13)]
    dic_existentes = [c for c in dic_cols if c in df.columns]
    if dic_existentes and "DIC_ANUAL" not in df.columns:
        df["DIC_ANUAL"] = df[dic_existentes].sum(axis=1)

    fic_cols = [f"FIC_{str(i).zfill(2)}" for i in range(1, 13)]
    fic_existentes = [c for c in fic_cols if c in df.columns]
    if fic_existentes and "FIC_ANUAL" not in df.columns:
        df["FIC_ANUAL"] = df[fic_existentes].sum(axis=1)

    # Mapear CLAS_SUB
    all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}
    if "CLAS_SUB" in df.columns:
        df["CLAS_SUB_DESC"] = df["CLAS_SUB"].map(all_clas_map).fillna(df["CLAS_SUB"])

    # Identificar solar
    if "CEG_GD" in df.columns:
        df["POSSUI_SOLAR"] = df["CEG_GD"].notna() & (df["CEG_GD"] != "")

    return df


def _enriquecer_com_localidades(df: pd.DataFrame) -> pd.DataFrame:
    """Enriquece com nomes de UF e município usando base IBGE"""
    if df.empty:
        return df

    from app.services.aneel_service import ANEELService
    df_loc = ANEELService.carregar_localidades()
    if df_loc.empty:
        return df

    df_loc.columns = df_loc.columns.str.strip()
    code_candidates = [
        "Código Município Completo",
        "Codigo Municipio Completo",
        "Código Município",
        "Codigo Municipio",
    ]
    code_col = next((c for c in code_candidates if c in df_loc.columns), None)
    if not code_col:
        return df

    cols = [code_col]
    for col in ["Nome_UF", "Nome_Município", "Nome_Microrregião", "Nome_Mesorregião"]:
        if col in df_loc.columns:
            cols.append(col)

    df_loc = df_loc[cols].drop_duplicates()
    df_loc[code_col] = df_loc[code_col].astype(str)

    df = df.copy()
    if "MUN" in df.columns:
        df["MUN"] = df["MUN"].astype(str)
        df = df.merge(df_loc, left_on="MUN", right_on=code_col, how="left")
        if code_col in df.columns and code_col != "MUN":
            df = df.drop(columns=[code_col])

    return df


class B3Service:
    """Serviço para dados BDGD B3 (Baixa Tensão)"""

    @staticmethod
    def _limpar_cache():
        global _cache_b3_processado, _cache_b3_opcoes, _cache_b3_por_uf
        _cache_b3_processado = None
        _cache_b3_opcoes = None
        _cache_b3_por_uf = {}

    @staticmethod
    async def carregar_dados_processados() -> pd.DataFrame:
        """Carrega e processa dados B3 com cache (async, não bloqueia event loop)"""
        global _cache_b3_processado
        if _cache_b3_processado is not None:
            return _cache_b3_processado

        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, _carregar_e_processar_sync)
        return df

    @staticmethod
    async def carregar_dados_por_uf(uf: str) -> pd.DataFrame:
        """Carrega dados B3 filtrados por UF com cache"""
        global _cache_b3_por_uf
        if uf in _cache_b3_por_uf:
            return _cache_b3_por_uf[uf]
        df = await B3Service.carregar_dados_processados()
        if df.empty or "Nome_UF" not in df.columns:
            return df
        df_uf = df[df["Nome_UF"] == uf].copy()
        _cache_b3_por_uf[uf] = df_uf
        return df_uf

    @staticmethod
    async def consultar_dados(filtros: FiltroB3) -> Tuple[List[Dict], int]:
        """Consulta dados B3 com filtros e paginação"""
        if filtros.uf:
            df = await B3Service.carregar_dados_por_uf(filtros.uf)
        else:
            df = await B3Service.carregar_dados_processados()

        if df.empty:
            return [], 0

        # Filtros de localidade
        if filtros.municipios and "Nome_Município" in df.columns:
            municipios = [str(m).strip() for m in filtros.municipios if str(m).strip()]
            if municipios:
                df = df[df["Nome_Município"].isin(municipios)]

        # Filtros de classificação
        if filtros.classes_cliente:
            all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}
            codigos = []
            for classe in filtros.classes_cliente:
                for cod, desc in all_clas_map.items():
                    if desc == classe or cod == classe:
                        codigos.append(cod)
            if codigos:
                df = df[df["CLAS_SUB"].isin(codigos)]

        if filtros.grupos_tarifarios and "GRU_TAR" in df.columns:
            df = df[df["GRU_TAR"].isin(filtros.grupos_tarifarios)]

        if filtros.fas_con and "FAS_CON" in df.columns:
            df = df[df["FAS_CON"] == filtros.fas_con]

        if filtros.sit_ativ and "SIT_ATIV" in df.columns:
            df = df[df["SIT_ATIV"] == filtros.sit_ativ]

        if filtros.area_loc and "ARE_LOC" in df.columns:
            df = df[df["ARE_LOC"] == filtros.area_loc]

        if filtros.possui_solar is not None and "CEG_GD" in df.columns:
            if filtros.possui_solar:
                df = df[df["CEG_GD"].notna() & (df["CEG_GD"] != "")]
            else:
                df = df[df["CEG_GD"].isna() | (df["CEG_GD"] == "")]

        # Filtros de texto
        if filtros.cnae and "CNAE" in df.columns:
            df = df[df["CNAE"].astype(str).str.contains(filtros.cnae, case=False, na=False)]

        if filtros.cep and "CEP" in df.columns:
            df = df[df["CEP"].astype(str).str.startswith(filtros.cep)]

        if filtros.bairro and "BRR" in df.columns:
            df = df[df["BRR"].astype(str).str.contains(filtros.bairro, case=False, na=False)]

        if filtros.logradouro and "LGRD" in df.columns:
            df = df[df["LGRD"].astype(str).str.contains(filtros.logradouro, case=False, na=False)]

        # Filtros de range
        range_filters = [
            ("consumo_medio_min", "CONSUMO_MEDIO", ">="),
            ("consumo_medio_max", "CONSUMO_MEDIO", "<="),
            ("consumo_anual_min", "CONSUMO_ANUAL", ">="),
            ("consumo_anual_max", "CONSUMO_ANUAL", "<="),
            ("car_inst_min", "CAR_INST", ">="),
            ("car_inst_max", "CAR_INST", "<="),
            ("dic_anual_min", "DIC_ANUAL", ">="),
            ("dic_anual_max", "DIC_ANUAL", "<="),
            ("fic_anual_min", "FIC_ANUAL", ">="),
            ("fic_anual_max", "FIC_ANUAL", "<="),
        ]

        for filtro_attr, col, op in range_filters:
            val = getattr(filtros, filtro_attr, None)
            if val is not None and col in df.columns:
                if op == ">=":
                    df = df[df[col] >= val]
                else:
                    df = df[df[col] <= val]

        df = df.drop_duplicates()
        total = len(df)

        # Paginação
        start = (filtros.page - 1) * filtros.per_page
        end = start + filtros.per_page
        df_page = df.iloc[start:end]

        records = df_page.to_dict("records")
        return records, total

    @staticmethod
    async def mapa_avancado(
        uf: Optional[str] = None,
        municipio: Optional[str] = None,
        possui_solar: Optional[bool] = None,
        classe: Optional[str] = None,
        fas_con: Optional[str] = None,
        consumo_min: Optional[float] = None,
        consumo_max: Optional[float] = None,
        limit: int = 5000
    ) -> Dict[str, Any]:
        """Retorna pontos para o mapa B3"""
        df = await B3Service.carregar_dados_processados()
        if df.empty:
            return {"pontos": [], "total": 0, "centro": {"lat": -15.7801, "lng": -47.9292}, "zoom": 4}

        # Filtros
        if uf and "Nome_UF" in df.columns:
            df = df[df["Nome_UF"] == uf]
        if municipio and "Nome_Município" in df.columns:
            df = df[df["Nome_Município"] == municipio]
        if possui_solar is not None and "POSSUI_SOLAR" in df.columns:
            df = df[df["POSSUI_SOLAR"] == possui_solar]
        if classe and "CLAS_SUB" in df.columns:
            df = df[df["CLAS_SUB"] == classe]
        if fas_con and "FAS_CON" in df.columns:
            df = df[df["FAS_CON"] == fas_con]
        if consumo_min is not None and "CONSUMO_MEDIO" in df.columns:
            df = df[df["CONSUMO_MEDIO"] >= consumo_min]
        if consumo_max is not None and "CONSUMO_MEDIO" in df.columns:
            df = df[df["CONSUMO_MEDIO"] <= consumo_max]

        total = len(df)
        df = df.head(limit)

        all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}
        pontos = []
        for idx, row in df.iterrows():
            try:
                lat = float(row.get("POINT_Y", 0))
                lng = float(row.get("POINT_X", 0))
                if lat == 0 or lng == 0:
                    continue

                ponto = PontoMapaB3(
                    id=str(row.get("COD_ID_ENCR", idx)),
                    latitude=lat,
                    longitude=lng,
                    cod_id=str(row.get("COD_ID_ENCR", "")),
                    titulo=str(row.get("Nome_Município", "") or row.get("COD_ID_ENCR", "")),
                    classe=all_clas_map.get(str(row.get("CLAS_SUB", "")), str(row.get("CLAS_SUB", ""))),
                    grupo_tarifario=str(row.get("GRU_TAR", "")),
                    fas_con=str(row.get("FAS_CON", "")),
                    municipio=str(row.get("Nome_Município", "")),
                    uf=str(row.get("Nome_UF", "")),
                    consumo_medio=round(float(row.get("CONSUMO_MEDIO", 0) or 0), 2),
                    consumo_anual=round(float(row.get("CONSUMO_ANUAL", 0) or 0), 2),
                    carga_instalada=float(row.get("CAR_INST", 0) or 0),
                    dic_anual=round(float(row.get("DIC_ANUAL", 0) or 0), 2),
                    fic_anual=round(float(row.get("FIC_ANUAL", 0) or 0), 2),
                    possui_solar=bool(row.get("POSSUI_SOLAR", False))
                )
                pontos.append(ponto)
            except Exception:
                continue

        # Centro
        if pontos:
            lats = [p.latitude for p in pontos]
            lngs = [p.longitude for p in pontos]
            centro = {"lat": sum(lats) / len(lats), "lng": sum(lngs) / len(lngs)}
        else:
            centro = {"lat": -15.7801, "lng": -47.9292}

        estatisticas = {
            "total_pontos": len(pontos),
            "total_base": total,
            "com_solar": sum(1 for p in pontos if p.possui_solar),
            "consumo_medio_total": round(sum(p.consumo_medio or 0 for p in pontos), 2),
        }

        return {
            "pontos": pontos,
            "total": total,
            "centro": centro,
            "zoom": 10 if len(pontos) < 500 else 8,
            "estatisticas": estatisticas
        }

    @staticmethod
    async def obter_opcoes_filtros() -> Dict[str, Any]:
        """Retorna opções para filtros B3 (usa IBGE direto, não carrega parquet)"""
        global _cache_b3_opcoes
        if _cache_b3_opcoes is not None:
            return _cache_b3_opcoes

        # UFs e municípios via IBGE (rápido, não precisa carregar 1.9GB parquet)
        from app.services.aneel_service import ANEELService
        df_ibge = ANEELService.carregar_localidades()

        ufs = []
        municipios_por_uf = {}
        if not df_ibge.empty and "Nome_UF" in df_ibge.columns:
            ufs = sorted(df_ibge["Nome_UF"].dropna().unique().tolist())
            for uf in ufs:
                df_uf = df_ibge[df_ibge["Nome_UF"] == uf]
                if "Nome_Município" in df_ibge.columns:
                    municipios_por_uf[uf] = sorted(df_uf["Nome_Município"].dropna().unique().tolist())

        all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}

        _cache_b3_opcoes = {
            "ufs": ufs,
            "municipios_por_uf": municipios_por_uf,
            "grupos_tarifarios": ["A1", "A2", "A3", "A3a", "A4", "AS", "B1", "B2", "B3", "B4"],
            "classes_cliente": sorted(set(all_clas_map.values())),
            "fases_conexao": [
                {"codigo": "A", "descricao": "Monofásico"},
                {"codigo": "AB", "descricao": "Bifásico"},
                {"codigo": "ABC", "descricao": "Trifásico"},
            ],
            "situacoes": [
                {"codigo": "AT", "descricao": "Ativo"},
                {"codigo": "DS", "descricao": "Desativado"},
            ],
            "areas": [
                {"codigo": "UR", "descricao": "Urbana"},
                {"codigo": "NU", "descricao": "Não Urbana"},
            ],
        }
        return _cache_b3_opcoes

    @staticmethod
    async def get_dados_mensais(cod_id: str) -> Optional[Dict[str, Any]]:
        """Busca dados mensais (ENE/DIC/FIC 01-12) de um registro específico."""
        if not B3_DATA_FILE.exists():
            return None
        try:
            import pyarrow.parquet as pq
            schema = pq.read_schema(str(B3_DATA_FILE))
            cols_disponiveis = set(schema.names)
            cols_buscar = ["COD_ID_ENCR"] + [c for c in _COLUNAS_MENSAIS if c in cols_disponiveis]
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                lambda: pd.read_parquet(
                    B3_DATA_FILE,
                    columns=cols_buscar,
                    filters=[("COD_ID_ENCR", "==", cod_id)]
                )
            )
            if df.empty:
                return None
            return df.iloc[0].to_dict()
        except Exception as e:
            logger.error(f"B3: Erro ao buscar dados mensais de {cod_id}: {e}")
            return None

    @staticmethod
    def exportar_csv(df: pd.DataFrame) -> bytes:
        """Exporta dados para CSV"""
        return df.to_csv(index=False, sep=";").encode("utf-8-sig")

    @staticmethod
    def exportar_xlsx(df: pd.DataFrame) -> bytes:
        """Exporta dados para XLSX"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados B3')
        return output.getvalue()

    @staticmethod
    def exportar_kml(df: pd.DataFrame) -> str:
        """Exporta dados para KML"""
        import simplekml
        kml = simplekml.Kml()
        df_valid = df.dropna(subset=["POINT_X", "POINT_Y"])
        all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}

        for _, row in df_valid.iterrows():
            pnt = kml.newpoint(
                name=str(row.get("COD_ID_ENCR", "Ponto")),
                coords=[(row["POINT_X"], row["POINT_Y"])]
            )
            pnt.description = (
                f"UF: {row.get('Nome_UF', 'N/A')}\n"
                f"Município: {row.get('Nome_Município', 'N/A')}\n"
                f"Classe: {all_clas_map.get(str(row.get('CLAS_SUB', '')), row.get('CLAS_SUB', 'N/A'))}\n"
                f"Consumo Médio: {row.get('CONSUMO_MEDIO', 'N/A')} kWh\n"
                f"Consumo Anual: {row.get('CONSUMO_ANUAL', 'N/A')} kWh\n"
                f"DIC Anual: {row.get('DIC_ANUAL', 'N/A')}\n"
                f"FIC Anual: {row.get('FIC_ANUAL', 'N/A')}"
            )
        return kml.kml()

    @staticmethod
    def get_status_dados() -> Dict[str, Any]:
        """Retorna status dos dados B3 (sem carregar parquet inteiro)"""
        if B3_DATA_FILE.exists():
            mod_time = datetime.fromtimestamp(os.path.getmtime(B3_DATA_FILE))
            size_gb = os.path.getsize(B3_DATA_FILE) / (1024**3)
            # Se cache está pronto, usar contagem do cache
            if _cache_b3_processado is not None:
                total = len(_cache_b3_processado)
            else:
                # Ler apenas metadados do parquet (sem carregar dados)
                try:
                    import pyarrow.parquet as pq
                    pf = pq.ParquetFile(str(B3_DATA_FILE))
                    total = pf.metadata.num_rows
                except Exception:
                    total = 0  # Fallback
            return {
                "disponivel": True,
                "ultima_atualizacao": mod_time.isoformat(),
                "total_registros": total,
                "arquivo": str(B3_DATA_FILE),
                "tamanho_gb": round(size_gb, 2),
                "cache_pronto": _cache_b3_processado is not None,
                "carregando": _cache_loading,
            }
        return {
            "disponivel": False,
            "ultima_atualizacao": None,
            "total_registros": 0,
            "cache_pronto": False,
            "carregando": False,
        }
