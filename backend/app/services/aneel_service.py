"""
Serviço para consulta de dados da ANEEL
"""
import httpx
import pandas as pd
import numpy as np
from typing import Optional, List, Tuple, Dict, Any
from pathlib import Path
import asyncio
from datetime import datetime
import io
import logging

from app.core.config import settings
from app.schemas.aneel import (
    FiltroConsulta,
    FiltroTarifas,
    ClienteANEEL,
    TarifaANEEL,
    CLAS_SUB_MAP,
    PontoMapa
)

# Configurar logging
logger = logging.getLogger(__name__)

# Diretório de dados - tenta múltiplos caminhos para compatibilidade
def _get_data_dir() -> Path:
    """Encontra o diretório de dados, checando múltiplos caminhos possíveis."""
    # Caminho 1: Relativo ao arquivo (para desenvolvimento)
    path1 = Path(__file__).parent.parent.parent / "data"
    
    # Caminho 2: /app/data (para Docker)
    path2 = Path("/app/data")
    
    # Caminho 3: Diretório atual + data
    path3 = Path.cwd() / "data"
    
    for path in [path2, path1, path3]:
        if path.exists():
            logger.info(f"Usando diretório de dados: {path}")
            return path
    
    # Se nenhum existe, cria o primeiro
    path1.mkdir(parents=True, exist_ok=True)
    logger.info(f"Criado diretório de dados: {path1}")
    return path1

DATA_DIR = _get_data_dir()

ANEEL_DATA_FILE = DATA_DIR / "dados_aneel.parquet"
TARIFAS_DATA_FILE = DATA_DIR / "tarifas_aneel.parquet"
MUNICIPIOS_FILE = DATA_DIR / "municipios.parquet"
MUNICIPIOS_SOURCES = [
    DATA_DIR / "RELATORIO_DTB_BRASIL_DISTRITO.xlsx",
    DATA_DIR / "RELATORIO_DTB_BRASIL_DISTRITO.xls",
]

# Cache em memória para dados processados (evita reload a cada requisição)
_cache_dados_processados: Optional[pd.DataFrame] = None
_cache_localidades: Optional[pd.DataFrame] = None
_cache_opcoes_filtros: Optional[Dict[str, Any]] = None
_cache_dados_por_uf: Dict[str, pd.DataFrame] = {}

# Estado global do progresso de download
_download_progress: Dict[str, Any] = {
    "status": "idle",  # idle, downloading, completed, error
    "current": 0,
    "total": 0,
    "percent": 0,
    "message": "",
    "started_at": None,
    "completed_at": None,
    "error": None
}


class ANEELService:
    """Serviço para dados da BDGD ANEEL"""

    @staticmethod
    def _limpar_cache():
        """Limpa o cache em memória (usar após atualizar dados)"""
        global _cache_dados_processados, _cache_localidades, _cache_opcoes_filtros, _cache_dados_por_uf
        _cache_dados_processados = None
        _cache_localidades = None
        _cache_opcoes_filtros = None
        _cache_dados_por_uf = {}

    @staticmethod
    def get_download_progress() -> Dict[str, Any]:
        """Retorna o progresso atual do download"""
        global _download_progress
        return _download_progress.copy()
    
    @staticmethod
    def _update_progress(status: str, current: int = 0, total: int = 0, message: str = "", error: str = None):
        """Atualiza o progresso do download"""
        global _download_progress
        _download_progress["status"] = status
        _download_progress["current"] = current
        _download_progress["total"] = total
        _download_progress["percent"] = round((current / total * 100) if total > 0 else 0, 1)
        _download_progress["message"] = message
        _download_progress["error"] = error
        
        if status == "downloading" and _download_progress["started_at"] is None:
            _download_progress["started_at"] = datetime.now().isoformat()
            _download_progress["completed_at"] = None
        elif status in ["completed", "error"]:
            _download_progress["completed_at"] = datetime.now().isoformat()

    @staticmethod
    def carregar_localidades() -> pd.DataFrame:
        """Carrega base de localidades (UF, município, micro e meso) com cache."""
        global _cache_localidades
        if _cache_localidades is not None:
            return _cache_localidades
        
        logger.info(f"Tentando carregar localidades de {MUNICIPIOS_FILE}")
        
        if MUNICIPIOS_FILE.exists():
            try:
                _cache_localidades = pd.read_parquet(MUNICIPIOS_FILE)
                logger.info(f"Localidades carregadas do parquet: {len(_cache_localidades)} registros")
                logger.info(f"Colunas disponíveis: {list(_cache_localidades.columns)}")
                return _cache_localidades
            except Exception as e:
                logger.warning(f"Erro ao carregar parquet de municípios: {e}")

        for src in MUNICIPIOS_SOURCES:
            logger.info(f"Tentando carregar localidades de {src}")
            if src.exists():
                try:
                    df_loc = pd.read_excel(src, dtype=str)
                    df_loc.columns = df_loc.columns.str.strip()
                    df_loc.to_parquet(MUNICIPIOS_FILE, index=False)
                    _cache_localidades = df_loc
                    logger.info(f"Localidades carregadas do Excel e salvas em parquet: {len(df_loc)} registros")
                    return _cache_localidades
                except Exception as e:
                    logger.warning(f"Erro ao carregar Excel {src}: {e}")
                    continue

        logger.warning("Nenhuma base de localidades encontrada!")
        logger.warning(f"Diretório de dados: {DATA_DIR}")
        logger.warning(f"Arquivos no diretório: {list(DATA_DIR.iterdir()) if DATA_DIR.exists() else 'Diretório não existe'}")
        return pd.DataFrame()

    @staticmethod
    def enriquecer_com_localidades(df: pd.DataFrame) -> pd.DataFrame:
        """Enriquece o dataset com colunas de UF, município, microrregião e mesorregião."""
        if df.empty:
            return df

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

        # Garantir colunas principais
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
            if code_col in df.columns:
                df = df.drop(columns=[code_col])

        return df
    
    @staticmethod
    async def _fazer_requisicao_com_retry(client: httpx.AsyncClient, url: str, params: dict, max_retries: int = 5) -> dict:
        """Faz requisição HTTP com retry automático e backoff exponencial"""
        last_exception = None
        
        for tentativa in range(max_retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.HTTPStatusError) as e:
                last_exception = e
                wait_time = min(2 ** tentativa * 2, 60)  # Backoff: 2, 4, 8, 16, 32 segundos (max 60)
                
                if tentativa < max_retries - 1:
                    ANEELService._update_progress(
                        "downloading", 
                        _download_progress["current"], 
                        _download_progress["total"], 
                        f"Erro na requisição (tentativa {tentativa + 1}/{max_retries}). Aguardando {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise last_exception
        
        raise last_exception
    
    @staticmethod
    async def download_dados_aneel(progress_callback=None) -> pd.DataFrame:
        """Baixa dados completos da API ANEEL com retry robusto"""
        try:
            ANEELService._update_progress("downloading", 0, 0, "Conectando à API da ANEEL...")
            
            # Timeout configurado por operação (conexão: 30s, leitura: 300s para dados grandes)
            timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
            
            async with httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_connections=5)) as client:
                # Primeiro, obter total de registros
                data = await ANEELService._fazer_requisicao_com_retry(
                    client,
                    settings.ANEEL_API_URL,
                    {"resource_id": settings.ANEEL_RESOURCE_ID, "limit": 1}
                )
                total_registros = data["result"]["total"]
                
                ANEELService._update_progress("downloading", 0, total_registros, f"Iniciando download de {total_registros:,} registros...")
                
                # Baixar em lotes menores para maior estabilidade
                limite_por_requisicao = 20000  # Reduzido de 32000 para maior estabilidade
                dados_completos = []
                offset = 0
                requisicoes_consecutivas_ok = 0
                
                while offset < total_registros:
                    params = {
                        "resource_id": settings.ANEEL_RESOURCE_ID,
                        "limit": limite_por_requisicao,
                        "offset": offset
                    }
                    
                    try:
                        data = await ANEELService._fazer_requisicao_com_retry(client, settings.ANEEL_API_URL, params)
                        registros = data.get("result", {}).get("records", [])
                        
                        if not registros:
                            break
                        
                        dados_completos.extend(registros)
                        offset += limite_por_requisicao
                        requisicoes_consecutivas_ok += 1
                        
                        # Atualizar progresso
                        ANEELService._update_progress(
                            "downloading", 
                            len(dados_completos), 
                            total_registros, 
                            f"Baixando... {len(dados_completos):,} de {total_registros:,} registros"
                        )
                        
                        if progress_callback:
                            progress_callback(len(dados_completos), total_registros)
                        
                        # Pequena pausa para não sobrecarregar a API (a cada 5 requisições bem sucedidas)
                        if requisicoes_consecutivas_ok % 5 == 0:
                            await asyncio.sleep(0.5)
                            
                    except Exception as e:
                        # Se falhar após todos os retries, mas temos dados parciais, salvar progresso
                        if len(dados_completos) > 0:
                            ANEELService._update_progress(
                                "downloading", 
                                len(dados_completos), 
                                total_registros, 
                                f"Erro persistente. Salvando {len(dados_completos):,} registros já baixados..."
                            )
                            # Salvar dados parciais
                            df_parcial = pd.DataFrame(dados_completos)
                            df_parcial.to_parquet(ANEEL_DATA_FILE, index=False)
                            ANEELService._limpar_cache()
                        raise
                
                ANEELService._update_progress("downloading", len(dados_completos), total_registros, "Salvando dados...")
                
                df = pd.DataFrame(dados_completos)
                
                # Salvar em parquet
                df.to_parquet(ANEEL_DATA_FILE, index=False)
                
                # Limpar cache para recarregar dados atualizados
                ANEELService._limpar_cache()
                
                ANEELService._update_progress("completed", len(dados_completos), total_registros, f"Download concluído! {len(dados_completos):,} registros salvos.")
                
                return df
                
        except Exception as e:
            error_msg = str(e)
            # Informar quantos registros foram salvos antes do erro
            registros_salvos = 0
            if ANEEL_DATA_FILE.exists():
                try:
                    df_check = pd.read_parquet(ANEEL_DATA_FILE)
                    registros_salvos = len(df_check)
                except:
                    pass
            
            if registros_salvos > 0:
                error_msg = f"{error_msg} (Parcial: {registros_salvos:,} registros salvos)"
            
            ANEELService._update_progress("error", registros_salvos, _download_progress.get("total", 0), "Erro no download", error_msg)
            raise
    
    @staticmethod
    def carregar_dados() -> pd.DataFrame:
        """Carrega dados do arquivo local com cache em memória"""
        global _cache_dados_processados
        
        # Se já temos dados processados em cache, retornar
        if _cache_dados_processados is not None:
            return _cache_dados_processados
        
        if ANEEL_DATA_FILE.exists():
            return pd.read_parquet(ANEEL_DATA_FILE)
        return pd.DataFrame()
    
    @staticmethod
    def carregar_dados_processados() -> pd.DataFrame:
        """Carrega e processa dados com cache - use esta função para consultas"""
        global _cache_dados_processados
        
        if _cache_dados_processados is not None:
            return _cache_dados_processados
        
        df = ANEELService.carregar_dados()
        if df.empty:
            return df
        
        df = ANEELService.processar_dados(df)
        df = ANEELService.enriquecer_com_localidades(df)
        
        _cache_dados_processados = df
        return _cache_dados_processados
    
    @staticmethod
    def carregar_dados_por_uf(uf: str) -> pd.DataFrame:
        """Carrega dados filtrados por UF com cache - muito mais rápido para consultas"""
        global _cache_dados_por_uf
        
        if uf in _cache_dados_por_uf:
            return _cache_dados_por_uf[uf]
        
        df = ANEELService.carregar_dados_processados()
        if df.empty or "Nome_UF" not in df.columns:
            return df
        
        df_uf = df[df["Nome_UF"] == uf].copy()
        _cache_dados_por_uf[uf] = df_uf
        return df_uf
    
    @staticmethod
    def processar_dados(df: pd.DataFrame) -> pd.DataFrame:
        """Processa e limpa os dados"""
        if df.empty:
            return df
        
        # Converter colunas numéricas
        colunas_numericas = [
            "LIV", "DEM_CONT", "CAR_INST",
            "DEM_01", "DEM_02", "DEM_03", "DEM_04", "DEM_05", "DEM_06",
            "DEM_07", "DEM_08", "DEM_09", "DEM_10", "DEM_11", "DEM_12",
            "ENE_01", "ENE_02", "ENE_03", "ENE_04", "ENE_05", "ENE_06",
            "ENE_07", "ENE_08", "ENE_09", "ENE_10", "ENE_11", "ENE_12",
            "DIC_01", "DIC_02", "FIC_01", "FIC_02",
            "POINT_X", "POINT_Y"
        ]
        
        for col in colunas_numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Calcular ENE_MAX
        colunas_energia = [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)]
        colunas_existentes = [c for c in colunas_energia if c in df.columns]
        if colunas_existentes:
            df["ENE_MAX"] = df[colunas_existentes].max(axis=1)
        
        # Mapear CLAS_SUB
        if "CLAS_SUB" in df.columns:
            df["CLAS_SUB_DESC"] = df["CLAS_SUB"].map(CLAS_SUB_MAP).fillna(df["CLAS_SUB"])
        
        # Identificar solar
        if "CEG_GD" in df.columns:
            df["POSSUI_SOLAR"] = df["CEG_GD"].notna() & (df["CEG_GD"] != "")
        
        return df
    
    @staticmethod
    async def consultar_dados(filtros: FiltroConsulta) -> Tuple[List[Dict], int]:
        """
        Consulta dados com filtros - OTIMIZADO COM CACHE.
        Se há filtro de UF, usa cache por UF para resposta instantânea.
        """
        # Usar cache otimizado por UF se disponível
        if filtros.uf:
            df = ANEELService.carregar_dados_por_uf(filtros.uf)
        else:
            df = ANEELService.carregar_dados_processados()
        
        if df.empty:
            return [], 0
        
        # Aplicar filtros de localidade (já temos Nome_UF, Nome_Município no cache)
        if filtros.municipios and "Nome_Município" in df.columns:
            municipios = [str(m).strip() for m in filtros.municipios if str(m).strip()]
            if municipios:
                df = df[df["Nome_Município"].isin(municipios)]
        
        if filtros.microrregioes and "Nome_Microrregião" in df.columns:
            df = df[df["Nome_Microrregião"].isin(filtros.microrregioes)]
        
        if filtros.mesorregioes and "Nome_Mesorregião" in df.columns:
            df = df[df["Nome_Mesorregião"].isin(filtros.mesorregioes)]

        # Aplicar filtros avançados (independentes de localidade)
        if filtros.possui_solar is not None:
            if filtros.possui_solar:
                df = df[df["CEG_GD"].notna() & (df["CEG_GD"] != "")]
            else:
                df = df[df["CEG_GD"].isna() | (df["CEG_GD"] == "")]
        
        if filtros.classes_cliente:
            # Mapear de volta para códigos se necessário
            codigos = []
            for classe in filtros.classes_cliente:
                for cod, desc in CLAS_SUB_MAP.items():
                    if desc == classe or cod == classe:
                        codigos.append(cod)
            if codigos:
                df = df[df["CLAS_SUB"].isin(codigos)]
        
        if filtros.grupos_tarifarios:
            df = df[df["GRU_TAR"].isin(filtros.grupos_tarifarios)]
        
        if filtros.tipo_consumidor:
            if filtros.tipo_consumidor == "Livre":
                df = df[df["LIV"] == 1]
            elif filtros.tipo_consumidor == "Cativo":
                df = df[df["LIV"] == 0]
        
        if filtros.demanda_min is not None:
            df = df[df["DEM_CONT"] >= filtros.demanda_min]
        
        if filtros.demanda_max is not None:
            df = df[df["DEM_CONT"] <= filtros.demanda_max]
        
        if filtros.energia_max_min is not None:
            df = df[df["ENE_MAX"] >= filtros.energia_max_min]
        
        if filtros.energia_max_max is not None:
            df = df[df["ENE_MAX"] <= filtros.energia_max_max]
        
        # Remover duplicatas
        df = df.drop_duplicates()
        
        total = len(df)
        
        # Paginação
        start = (filtros.page - 1) * filtros.per_page
        end = start + filtros.per_page
        df_page = df.iloc[start:end]
        
        # Converter para lista de dicts
        records = df_page.to_dict("records")
        
        return records, total
    
    @staticmethod
    def obter_pontos_mapa(df: pd.DataFrame) -> List[PontoMapa]:
        """Converte dados para pontos de mapa"""
        pontos = []
        
        df_valid = df.dropna(subset=["POINT_X", "POINT_Y"])
        
        for _, row in df_valid.iterrows():
            ponto = PontoMapa(
                id=str(row.get("COD_ID", row.name)),
                latitude=float(row["POINT_Y"]),
                longitude=float(row["POINT_X"]),
                titulo=f"Demanda: {row.get('DEM_CONT', 'N/A')} kW",
                descricao=f"Classe: {row.get('CLAS_SUB_DESC', row.get('CLAS_SUB', 'N/A'))}",
                tipo=row.get("GRU_TAR", ""),
                dados={
                    "dem_cont": row.get("DEM_CONT"),
                    "ene_max": row.get("ENE_MAX"),
                    "gru_tar": row.get("GRU_TAR"),
                    "clas_sub": row.get("CLAS_SUB_DESC", row.get("CLAS_SUB")),
                    "possui_solar": bool(row.get("POSSUI_SOLAR", False))
                }
            )
            pontos.append(ponto)
        
        return pontos
    
    @staticmethod
    def exportar_csv(df: pd.DataFrame) -> bytes:
        """Exporta dados para CSV"""
        return df.to_csv(index=False).encode("utf-8")
    
    @staticmethod
    def exportar_xlsx(df: pd.DataFrame) -> bytes:
        """Exporta dados para XLSX"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Dados')
        return output.getvalue()
    
    @staticmethod
    def exportar_kml(df: pd.DataFrame) -> str:
        """Exporta dados para KML"""
        import simplekml
        
        kml = simplekml.Kml()
        
        df_valid = df.dropna(subset=["POINT_X", "POINT_Y"])
        
        for _, row in df_valid.iterrows():
            pnt = kml.newpoint(
                name=str(row.get("DEM_CONT", "Ponto")),
                coords=[(row["POINT_X"], row["POINT_Y"])]
            )
            pnt.description = (
                f"UF: {row.get('Nome_UF', 'N/A')}\n"
                f"Município: {row.get('Nome_Município', 'N/A')}\n"
                f"Classe: {row.get('CLAS_SUB_DESC', row.get('CLAS_SUB', 'N/A'))}\n"
                f"Grupo Tarifário: {row.get('GRU_TAR', 'N/A')}"
            )
        
        return kml.kml()
    
    @staticmethod
    def obter_opcoes_filtros(df: pd.DataFrame) -> Dict[str, List[str]]:
        """
        Retorna opções disponíveis para filtros.
        UF/Município/Micro/Meso vêm da planilha IBGE (como no projeto original).
        Grupos tarifários vêm dos dados ANEEL.
        """
        # Carregar planilha IBGE para opções de localidade
        df_ibge = ANEELService.carregar_localidades()
        
        if df_ibge.empty:
            # Fallback para dados enriquecidos se planilha não disponível
            ufs = sorted(df["Nome_UF"].dropna().unique().tolist()) if "Nome_UF" in df.columns else []
            municipios = sorted(df["Nome_Município"].dropna().unique().tolist()) if "Nome_Município" in df.columns else []
            microrregioes = []
            mesorregioes = []
            municipios_por_uf = {}
            microrregioes_por_uf = {}
            mesorregioes_por_uf = {}
        else:
            # Usar planilha IBGE (como no projeto original bdgd_04.py)
            ufs = sorted(df_ibge["Nome_UF"].dropna().unique().tolist()) if "Nome_UF" in df_ibge.columns else []
            municipios = sorted(df_ibge["Nome_Município"].dropna().unique().tolist()) if "Nome_Município" in df_ibge.columns else []
            microrregioes = sorted(df_ibge["Nome_Microrregião"].dropna().unique().tolist()) if "Nome_Microrregião" in df_ibge.columns else []
            mesorregioes = sorted(df_ibge["Nome_Mesorregião"].dropna().unique().tolist()) if "Nome_Mesorregião" in df_ibge.columns else []
            
            # Mapear por UF (como no projeto original)
            municipios_por_uf = {}
            microrregioes_por_uf = {}
            mesorregioes_por_uf = {}
            
            if "Nome_UF" in df_ibge.columns:
                for uf in ufs:
                    df_uf = df_ibge[df_ibge["Nome_UF"] == uf]
                    if "Nome_Município" in df_ibge.columns:
                        municipios_por_uf[uf] = sorted(df_uf["Nome_Município"].dropna().unique().tolist())
                    if "Nome_Microrregião" in df_ibge.columns:
                        microrregioes_por_uf[uf] = sorted(df_uf["Nome_Microrregião"].dropna().unique().tolist())
                    if "Nome_Mesorregião" in df_ibge.columns:
                        mesorregioes_por_uf[uf] = sorted(df_uf["Nome_Mesorregião"].dropna().unique().tolist())

        opcoes = {
            "ufs": ufs,
            "municipios": municipios,
            "microrregioes": microrregioes,
            "mesorregioes": mesorregioes,
            "municipios_por_uf": municipios_por_uf,
            "microrregioes_por_uf": microrregioes_por_uf,
            "mesorregioes_por_uf": mesorregioes_por_uf,
            "grupos_tarifarios": sorted(df["GRU_TAR"].dropna().unique().tolist()) if "GRU_TAR" in df.columns else [],
            "classes_cliente": list(CLAS_SUB_MAP.values()),
            "tipos_consumidor": ["Livre", "Cativo"]
        }
        return opcoes


class TarifasService:
    """Serviço para tarifas da ANEEL"""
    
    @staticmethod
    async def _fazer_requisicao_com_retry(client: httpx.AsyncClient, url: str, params: dict, max_retries: int = 5) -> dict:
        """Faz requisição HTTP com retry automático e backoff exponencial"""
        last_exception = None
        
        for tentativa in range(max_retries):
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.HTTPStatusError) as e:
                last_exception = e
                wait_time = min(2 ** tentativa * 2, 60)
                
                if tentativa < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    raise last_exception
        
        raise last_exception
    
    @staticmethod
    async def download_tarifas() -> pd.DataFrame:
        """Baixa tarifas da API ANEEL com retry robusto"""
        timeout = httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)
        
        async with httpx.AsyncClient(timeout=timeout, limits=httpx.Limits(max_connections=5)) as client:
            dados_completos = []
            offset = 0
            limite = 20000  # Reduzido para maior estabilidade
            requisicoes_consecutivas_ok = 0
            
            while True:
                params = {
                    "resource_id": settings.ANEEL_TARIFAS_RESOURCE_ID,
                    "limit": limite,
                    "offset": offset
                }
                
                data = await TarifasService._fazer_requisicao_com_retry(client, settings.ANEEL_API_URL, params)
                
                result = data.get("result", {})
                records = result.get("records", [])
                total = result.get("total", 0)
                
                if not records:
                    break
                
                dados_completos.extend(records)
                offset += len(records)
                requisicoes_consecutivas_ok += 1
                
                # Pequena pausa a cada 5 requisições
                if requisicoes_consecutivas_ok % 5 == 0:
                    await asyncio.sleep(0.5)
                
                if offset >= total:
                    break
            
            df = pd.DataFrame(dados_completos)
            df.to_parquet(TARIFAS_DATA_FILE, index=False)
            
            return df
    
    @staticmethod
    def carregar_tarifas() -> pd.DataFrame:
        """Carrega tarifas do arquivo local"""
        if TARIFAS_DATA_FILE.exists():
            return pd.read_parquet(TARIFAS_DATA_FILE)
        return pd.DataFrame()
    
    @staticmethod
    def processar_tarifas(df: pd.DataFrame) -> pd.DataFrame:
        """Processa dados de tarifas"""
        if df.empty:
            return df
        
        # Converter datas
        for col in ['DatGeracaoConjuntoDados', 'DatInicioVigencia', 'DatFimVigencia']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        # Converter valores
        for col in ['VlrTUSD', 'VlrTE']:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '.'),
                    errors='coerce'
                )
        
        # Filtros padrão
        filtros = [
            ('DscBaseTarifaria', 'Tarifa de Aplicação'),
            ('DscClasse', 'Não se aplica'),
            ('DscSubClasse', 'Não se aplica'),
            ('SigAgenteAcessante', 'Não se aplica')
        ]
        
        for col, val in filtros:
            if col in df.columns:
                df = df[df[col] == val]
        
        return df
    
    @staticmethod
    async def consultar_tarifas(filtros: FiltroTarifas) -> Tuple[List[TarifaANEEL], int]:
        """Consulta tarifas com filtros"""
        df = TarifasService.carregar_tarifas()
        
        if df.empty:
            return [], 0
        
        df = TarifasService.processar_tarifas(df)
        
        if filtros.distribuidora and filtros.distribuidora != "Todas":
            df = df[df["SigAgente"] == filtros.distribuidora]
        
        if filtros.subgrupo and filtros.subgrupo != "Todos":
            df = df[df["DscSubGrupo"] == filtros.subgrupo]
        
        if filtros.modalidade and filtros.modalidade != "Todas":
            df = df[df["DscModalidadeTarifaria"] == filtros.modalidade]
        
        if filtros.detalhe and filtros.detalhe != "Todos":
            df = df[df["DscDetalhe"] == filtros.detalhe]
        
        if filtros.apenas_ultima_tarifa and "DatFimVigencia" in df.columns:
            ultimas = df.groupby("SigAgente")["DatFimVigencia"].transform("max")
            df = df[df["DatFimVigencia"] == ultimas]
        
        total = len(df)
        
        # Converter para lista
        tarifas = []
        for _, row in df.iterrows():
            tarifa = TarifaANEEL(
                sig_agente=row.get("SigAgente"),
                dsc_reh=row.get("DscREH"),
                nom_posto_tarifario=row.get("NomPostoTarifario"),
                dsc_unidade_terciaria=row.get("DscUnidadeTerciaria"),
                vlr_tusd=row.get("VlrTUSD"),
                vlr_te=row.get("VlrTE"),
                dat_fim_vigencia=row.get("DatFimVigencia"),
                dsc_sub_grupo=row.get("DscSubGrupo"),
                dsc_modalidade_tarifaria=row.get("DscModalidadeTarifaria"),
                dsc_detalhe=row.get("DscDetalhe")
            )
            tarifas.append(tarifa)
        
        return tarifas, total
    
    @staticmethod
    def obter_opcoes_filtros() -> Dict[str, List[str]]:
        """Retorna opções disponíveis para filtros de tarifas"""
        df = TarifasService.carregar_tarifas()
        
        if df.empty:
            return {
                "distribuidoras": [],
                "subgrupos": [],
                "modalidades": [],
                "detalhes": []
            }
        
        df = TarifasService.processar_tarifas(df)
        
        return {
            "distribuidoras": sorted(df["SigAgente"].dropna().unique().tolist()) if "SigAgente" in df.columns else [],
            "subgrupos": sorted(df["DscSubGrupo"].dropna().unique().tolist()) if "DscSubGrupo" in df.columns else [],
            "modalidades": sorted(df["DscModalidadeTarifaria"].dropna().unique().tolist()) if "DscModalidadeTarifaria" in df.columns else [],
            "detalhes": sorted(df["DscDetalhe"].dropna().unique().tolist()) if "DscDetalhe" in df.columns else []
        }
