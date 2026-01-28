"""
Rotas para dados da ANEEL (BDGD e Tarifas)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import io

from app.core.database import get_db
from app.models.user import User
from app.schemas.aneel import (
    FiltroConsulta,
    FiltroTarifas,
    ConsultaResponse,
    TarifasResponse,
    MapaResponse,
    LocalidadesResponse,
    ClienteANEEL,
    PontoMapa,
    CLAS_SUB_MAP
)
from app.services.aneel_service import ANEELService, TarifasService
from app.api.deps import get_current_active_user, get_current_admin

router = APIRouter(prefix="/aneel", tags=["Dados ANEEL"])


# ============ Endpoints de Dados BDGD ============

@router.post("/consulta", response_model=ConsultaResponse)
async def consultar_dados(
    filtros: FiltroConsulta,
    current_user: User = Depends(get_current_active_user)
):
    """
    Consulta dados da BDGD ANEEL com filtros.
    
    Permite filtrar por UF, municípios, classes de cliente, grupos tarifários, etc.
    """
    try:
        dados, total = await ANEELService.consultar_dados(filtros)
        
        total_pages = (total + filtros.per_page - 1) // filtros.per_page
        
        # Converter para schema
        clientes = []
        for d in dados:
            cliente = ClienteANEEL(
                cod_id=d.get("COD_ID"),
                mun=d.get("MUN"),
                nome_uf=d.get("Nome_UF"),
                nome_municipio=d.get("Nome_Município"),
                clas_sub=d.get("CLAS_SUB"),
                clas_sub_descricao=d.get("CLAS_SUB_DESC"),
                gru_tar=d.get("GRU_TAR"),
                liv=d.get("LIV"),
                dem_cont=d.get("DEM_CONT"),
                car_inst=d.get("CAR_INST"),
                ene_max=d.get("ENE_MAX"),
                ceg_gd=d.get("CEG_GD"),
                possui_solar=d.get("POSSUI_SOLAR", False),
                point_x=d.get("POINT_X"),
                point_y=d.get("POINT_Y"),
                latitude=d.get("POINT_Y"),
                longitude=d.get("POINT_X")
            )
            clientes.append(cliente)
        
        return ConsultaResponse(
            dados=clientes,
            total=total,
            page=filtros.page,
            per_page=filtros.per_page,
            total_pages=total_pages
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar dados: {str(e)}"
        )


@router.get("/mapa")
async def obter_dados_mapa(
    municipios: Optional[str] = Query(None, description="Códigos de municípios separados por vírgula"),
    possui_solar: Optional[bool] = None,
    demanda_min: Optional[float] = None,
    demanda_max: Optional[float] = None,
    limit: int = Query(1000, le=5000),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retorna dados formatados para exibição no mapa.
    
    Inclui coordenadas e informações para Street View.
    """
    filtros = FiltroConsulta(
        municipios=municipios.split(",") if municipios else None,
        possui_solar=possui_solar,
        demanda_min=demanda_min,
        demanda_max=demanda_max,
        per_page=limit
    )
    
    dados, total = await ANEELService.consultar_dados(filtros)
    
    if not dados:
        return MapaResponse(
            pontos=[],
            centro={"lat": -15.7801, "lng": -47.9292},  # Brasília como padrão
            zoom=4
        )
    
    # Converter para pontos de mapa
    import pandas as pd
    df = pd.DataFrame(dados)
    
    pontos = ANEELService.obter_pontos_mapa(df)
    
    # Calcular centro
    lats = [p.latitude for p in pontos if p.latitude]
    lngs = [p.longitude for p in pontos if p.longitude]
    
    centro = {
        "lat": sum(lats) / len(lats) if lats else -15.7801,
        "lng": sum(lngs) / len(lngs) if lngs else -47.9292
    }
    
    return MapaResponse(
        pontos=pontos,
        centro=centro,
        zoom=10 if len(pontos) < 100 else 8
    )


@router.get("/opcoes-filtros")
async def obter_opcoes_filtros(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna as opções disponíveis para os filtros"""
    df = ANEELService.carregar_dados()
    
    if df.empty:
        return {
            "ufs": [],
            "municipios": [],
            "microrregioes": [],
            "mesorregioes": [],
            "municipios_por_uf": {},
            "microrregioes_por_uf": {},
            "mesorregioes_por_uf": {},
            "grupos_tarifarios": [],
            "classes_cliente": list(CLAS_SUB_MAP.values()),
            "tipos_consumidor": ["Livre", "Cativo"]
        }
    
    return ANEELService.obter_opcoes_filtros(df)


@router.post("/exportar/csv")
async def exportar_csv(
    filtros: FiltroConsulta,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados filtrados em formato CSV"""
    filtros.per_page = 100000  # Sem limite para exportação
    dados, _ = await ANEELService.consultar_dados(filtros)
    
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum dado encontrado para exportação"
        )
    
    import pandas as pd
    df = pd.DataFrame(dados)
    csv_bytes = ANEELService.exportar_csv(df)
    
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dados_aneel.csv"}
    )


@router.post("/exportar/xlsx")
async def exportar_xlsx(
    filtros: FiltroConsulta,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados filtrados em formato XLSX"""
    filtros.per_page = 100000
    dados, _ = await ANEELService.consultar_dados(filtros)
    
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum dado encontrado para exportação"
        )
    
    import pandas as pd
    df = pd.DataFrame(dados)
    xlsx_bytes = ANEELService.exportar_xlsx(df)
    
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dados_aneel.xlsx"}
    )


@router.post("/exportar/kml")
async def exportar_kml(
    filtros: FiltroConsulta,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados filtrados em formato KML para Google Earth"""
    filtros.per_page = 50000
    dados, _ = await ANEELService.consultar_dados(filtros)
    
    if not dados:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum dado encontrado para exportação"
        )
    
    import pandas as pd
    df = pd.DataFrame(dados)
    kml_str = ANEELService.exportar_kml(df)
    
    return StreamingResponse(
        io.BytesIO(kml_str.encode("utf-8")),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": "attachment; filename=dados_aneel.kml"}
    )


@router.post("/atualizar-dados")
async def atualizar_dados(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin)
):
    """
    Inicia atualização dos dados da ANEEL em background.
    
    Requer autenticação de admin.
    """
    # Verificar se já está em andamento
    progress = ANEELService.get_download_progress()
    if progress["status"] == "downloading":
        return {"message": "Download já está em andamento", "progress": progress}
    
    background_tasks.add_task(ANEELService.download_dados_aneel)
    
    return {"message": "Atualização iniciada em background"}


@router.get("/progresso-download")
async def progresso_download(
    current_user: User = Depends(get_current_admin)
):
    """
    Retorna o progresso atual do download de dados.
    
    Requer autenticação de admin.
    """
    return ANEELService.get_download_progress()


@router.get("/status-dados")
async def status_dados(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna status dos dados locais"""
    from pathlib import Path
    from datetime import datetime
    
    data_file = Path("data/dados_aneel.parquet")
    
    if data_file.exists():
        import os
        mod_time = datetime.fromtimestamp(os.path.getmtime(data_file))
        df = ANEELService.carregar_dados()
        
        return {
            "disponivel": True,
            "ultima_atualizacao": mod_time.isoformat(),
            "total_registros": len(df),
            "arquivo": str(data_file)
        }
    
    return {
        "disponivel": False,
        "ultima_atualizacao": None,
        "total_registros": 0
    }


@router.get("/status-localidades")
async def status_localidades(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna status da base de localidades (IBGE)"""
    from pathlib import Path
    from datetime import datetime
    import os
    
    # Tentar vários caminhos
    paths_to_check = [
        Path("/app/data"),
        Path(__file__).parent.parent.parent.parent / "data",
        Path.cwd() / "data"
    ]
    
    result = {
        "data_dir_found": None,
        "municipios_parquet": False,
        "municipios_excel": False,
        "arquivos_encontrados": [],
        "ufs_disponiveis": [],
        "total_municipios": 0
    }
    
    for data_path in paths_to_check:
        if data_path.exists():
            result["data_dir_found"] = str(data_path)
            result["arquivos_encontrados"] = [f.name for f in data_path.iterdir() if f.is_file()]
            
            municipios_parquet = data_path / "municipios.parquet"
            municipios_excel = data_path / "RELATORIO_DTB_BRASIL_DISTRITO.xlsx"
            
            result["municipios_parquet"] = municipios_parquet.exists()
            result["municipios_excel"] = municipios_excel.exists()
            break
    
    # Tentar carregar localidades
    try:
        df_loc = ANEELService.carregar_localidades()
        if not df_loc.empty:
            result["total_municipios"] = len(df_loc)
            if "Nome_UF" in df_loc.columns:
                result["ufs_disponiveis"] = sorted(df_loc["Nome_UF"].dropna().unique().tolist())
    except Exception as e:
        result["error"] = str(e)
    
    return result


# ============ Endpoints de Tarifas ============

@router.post("/tarifas/consulta", response_model=TarifasResponse)
async def consultar_tarifas(
    filtros: FiltroTarifas,
    current_user: User = Depends(get_current_active_user)
):
    """Consulta tarifas da ANEEL"""
    tarifas, total = await TarifasService.consultar_tarifas(filtros)
    
    return TarifasResponse(
        tarifas=tarifas,
        total=total
    )


@router.get("/tarifas/opcoes-filtros")
async def obter_opcoes_filtros_tarifas(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna opções de filtros para tarifas"""
    return TarifasService.obter_opcoes_filtros()


@router.post("/tarifas/atualizar")
async def atualizar_tarifas(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_admin)
):
    """Atualiza dados de tarifas em background"""
    background_tasks.add_task(TarifasService.download_tarifas)
    
    return {"message": "Atualização de tarifas iniciada em background"}
