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

from app.core.config import settings
from app.schemas.aneel import (
    FiltroConsulta,
    FiltroTarifas,
    ClienteANEEL,
    TarifaANEEL,
    CLAS_SUB_MAP,
    PontoMapa
)

# Diretório de dados
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

ANEEL_DATA_FILE = DATA_DIR / "dados_aneel.parquet"
TARIFAS_DATA_FILE = DATA_DIR / "tarifas_aneel.parquet"
MUNICIPIOS_FILE = DATA_DIR / "municipios.parquet"
MUNICIPIOS_SOURCES = [
    DATA_DIR / "RELATORIO_DTB_BRASIL_DISTRITO.xlsx",
    DATA_DIR / "RELATORIO_DTB_BRASIL_DISTRITO.xls",
]


class ANEELService:
    """Serviço para dados da BDGD ANEEL"""

    @staticmethod
    def carregar_localidades() -> pd.DataFrame:
        """Carrega base de localidades (UF, município, micro e meso)."""
        if MUNICIPIOS_FILE.exists():
            try:
                return pd.read_parquet(MUNICIPIOS_FILE)
            except Exception:
                pass

        for src in MUNICIPIOS_SOURCES:
            if src.exists():
                try:
                    df_loc = pd.read_excel(src, dtype=str)
                    df_loc.columns = df_loc.columns.str.strip()
                    df_loc.to_parquet(MUNICIPIOS_FILE, index=False)
                    return df_loc
                except Exception:
                    continue

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
    async def download_dados_aneel(progress_callback=None) -> pd.DataFrame:
        """Baixa dados completos da API ANEEL"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Primeiro, obter total de registros
            response = await client.get(
                settings.ANEEL_API_URL,
                params={"resource_id": settings.ANEEL_RESOURCE_ID, "limit": 1}
            )
            response.raise_for_status()
            total_registros = response.json()["result"]["total"]
            
            # Baixar em lotes
            limite_por_requisicao = 32000
            dados_completos = []
            offset = 0
            
            while offset < total_registros:
                params = {
                    "resource_id": settings.ANEEL_RESOURCE_ID,
                    "limit": limite_por_requisicao,
                    "offset": offset
                }
                
                response = await client.get(settings.ANEEL_API_URL, params=params)
                response.raise_for_status()
                
                registros = response.json().get("result", {}).get("records", [])
                if not registros:
                    break
                
                dados_completos.extend(registros)
                offset += limite_por_requisicao
                
                if progress_callback:
                    progress_callback(len(dados_completos), total_registros)
            
            df = pd.DataFrame(dados_completos)
            
            # Salvar em parquet
            df.to_parquet(ANEEL_DATA_FILE, index=False)
            
            return df
    
    @staticmethod
    def carregar_dados() -> pd.DataFrame:
        """Carrega dados do arquivo local"""
        if ANEEL_DATA_FILE.exists():
            return pd.read_parquet(ANEEL_DATA_FILE)
        return pd.DataFrame()
    
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
        Consulta dados com filtros.
        Lógica igual ao projeto original bdgd_04.py:
        1. Filtra na planilha IBGE para obter códigos de municípios
        2. Usa esses códigos para filtrar os dados da ANEEL
        3. Faz merge para adicionar Nome_UF/Nome_Município ao resultado
        """
        df = ANEELService.carregar_dados()
        
        if df.empty:
            return [], 0
        
        df = ANEELService.processar_dados(df)
        
        # Carregar planilha IBGE para filtros de localidade
        df_ibge = ANEELService.carregar_localidades()
        
        # Identificar coluna de código do município no IBGE
        code_candidates = [
            "Código Município Completo",
            "Codigo Municipio Completo",
            "Código Município",
            "Codigo Municipio",
        ]
        code_col = None
        if not df_ibge.empty:
            code_col = next((c for c in code_candidates if c in df_ibge.columns), None)
        
        # Se temos filtros de localidade e planilha IBGE disponível
        if not df_ibge.empty and code_col:
            df_ibge_filtrado = df_ibge.copy()
            
            # Filtrar por UF na planilha IBGE
            if filtros.uf and "Nome_UF" in df_ibge_filtrado.columns:
                df_ibge_filtrado = df_ibge_filtrado[df_ibge_filtrado["Nome_UF"] == filtros.uf]
            
            # Filtrar por Municípios na planilha IBGE
            if filtros.municipios and "Nome_Município" in df_ibge_filtrado.columns:
                municipios = [str(m).strip() for m in filtros.municipios if str(m).strip()]
                if municipios:
                    df_ibge_filtrado = df_ibge_filtrado[df_ibge_filtrado["Nome_Município"].isin(municipios)]
            
            # Filtrar por Microrregiões na planilha IBGE
            if filtros.microrregioes and "Nome_Microrregião" in df_ibge_filtrado.columns:
                df_ibge_filtrado = df_ibge_filtrado[df_ibge_filtrado["Nome_Microrregião"].isin(filtros.microrregioes)]
            
            # Filtrar por Mesorregiões na planilha IBGE
            if filtros.mesorregioes and "Nome_Mesorregião" in df_ibge_filtrado.columns:
                df_ibge_filtrado = df_ibge_filtrado[df_ibge_filtrado["Nome_Mesorregião"].isin(filtros.mesorregioes)]
            
            # Obter códigos de municípios filtrados
            codigos_municipios = df_ibge_filtrado[code_col].dropna().unique().tolist()
            
            # Se houve filtro de localidade, filtrar dados ANEEL pelos códigos
            tem_filtro_localidade = filtros.uf or filtros.municipios or filtros.microrregioes or filtros.mesorregioes
            if tem_filtro_localidade and "MUN" in df.columns:
                df["MUN"] = df["MUN"].astype(str)
                codigos_str = [str(c) for c in codigos_municipios]
                df = df[df["MUN"].isin(codigos_str)]
                
                if df.empty:
                    return [], 0
            
            # Fazer merge para adicionar Nome_UF/Nome_Município (como no projeto original)
            if "MUN" in df.columns:
                cols_merge = [code_col]
                for col in ["Nome_UF", "Nome_Município", "Nome_Microrregião", "Nome_Mesorregião"]:
                    if col in df_ibge.columns:
                        cols_merge.append(col)
                
                df_ibge_merge = df_ibge[cols_merge].drop_duplicates()
                df_ibge_merge[code_col] = df_ibge_merge[code_col].astype(str)
                df["MUN"] = df["MUN"].astype(str)
                
                df = df.merge(
                    df_ibge_merge,
                    left_on="MUN",
                    right_on=code_col,
                    how="inner" if tem_filtro_localidade else "left"
                )
                
                if code_col in df.columns and code_col != "MUN":
                    df = df.drop(columns=[code_col])
        else:
            # Fallback: usar enriquecimento básico
            df = ANEELService.enriquecer_com_localidades(df)
            
            # Filtros diretos (se dados já estão enriquecidos)
            if filtros.uf and "Nome_UF" in df.columns:
                df = df[df["Nome_UF"] == filtros.uf]
            
            if filtros.municipios:
                municipios = [str(m).strip() for m in filtros.municipios if str(m).strip()]
                if municipios and "Nome_Município" in df.columns:
                    df = df[df["Nome_Município"].isin(municipios)]
        
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
    async def download_tarifas() -> pd.DataFrame:
        """Baixa tarifas da API ANEEL"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            dados_completos = []
            offset = 0
            limite = 32000
            
            while True:
                params = {
                    "resource_id": settings.ANEEL_TARIFAS_RESOURCE_ID,
                    "limit": limite,
                    "offset": offset
                }
                
                response = await client.get(settings.ANEEL_API_URL, params=params)
                response.raise_for_status()
                
                result = response.json().get("result", {})
                records = result.get("records", [])
                total = result.get("total", 0)
                
                if not records:
                    break
                
                dados_completos.extend(records)
                offset += len(records)
                
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
