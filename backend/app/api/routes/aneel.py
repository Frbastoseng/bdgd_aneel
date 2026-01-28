"""
Rotas para dados da ANEEL (BDGD e Tarifas)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import io
import pandas as pd

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
    CLAS_SUB_MAP,
    PontoMapaCompleto,
    MapaAvancadoResponse,
    ExportarSelecaoRequest,
    SavedQueryCreate,
    SavedQueryUpdate
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


# ============ Endpoints de Mapa Avançado ============

@router.get("/mapa/pontos")
async def obter_pontos_mapa_avancado(
    uf: Optional[str] = Query(None, description="Filtrar por UF"),
    municipio: Optional[str] = Query(None, description="Filtrar por nome do município"),
    possui_solar: Optional[bool] = None,
    tipo_consumidor: Optional[str] = Query(None, description="Livre ou Cativo"),
    demanda_min: Optional[float] = None,
    demanda_max: Optional[float] = None,
    classe: Optional[str] = Query(None, description="Classe do cliente"),
    limit: int = Query(5000, le=20000),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retorna pontos para o mapa avançado com informações completas para tooltip.
    Otimizado para grandes volumes de dados.
    """
    from app.schemas.aneel import PontoMapaCompleto, MapaAvancadoResponse, CLAS_SUB_MAP
    
    # Usar dados processados com enriquecimento de localidades
    df = ANEELService.carregar_dados_processados()
    
    if df.empty:
        return MapaAvancadoResponse(
            pontos=[],
            total=0,
            centro={"lat": -15.7801, "lng": -47.9292},
            zoom=4
        )
    
    # Aplicar filtros
    if uf:
        df = df[df["Nome_UF"] == uf] if "Nome_UF" in df.columns else df
    
    if municipio:
        # Filtrar por nome do município (Nome_Município) que vem do enriquecimento
        if "Nome_Município" in df.columns:
            df = df[df["Nome_Município"] == municipio]
        elif "MUN" in df.columns:
            df = df[df["MUN"] == municipio]
    
    if possui_solar is not None:
        df = df[df["POSSUI_SOLAR"] == possui_solar] if "POSSUI_SOLAR" in df.columns else df
    
    if tipo_consumidor:
        if tipo_consumidor.lower() == "livre":
            df = df[df["LIV"] == 1] if "LIV" in df.columns else df
        elif tipo_consumidor.lower() == "cativo":
            df = df[df["LIV"] == 0] if "LIV" in df.columns else df
    
    if demanda_min is not None and "DEM_CONT" in df.columns:
        df = df[df["DEM_CONT"] >= demanda_min]
    
    if demanda_max is not None and "DEM_CONT" in df.columns:
        df = df[df["DEM_CONT"] <= demanda_max]
    
    if classe and "CLAS_SUB" in df.columns:
        df = df[df["CLAS_SUB"] == classe]
    
    total = len(df)
    
    # Limitar resultados
    df = df.head(limit)
    
    # Converter para pontos
    pontos = []
    for idx, row in df.iterrows():
        try:
            lat = float(row.get("POINT_Y", 0))
            lng = float(row.get("POINT_X", 0))
            
            if lat == 0 or lng == 0:
                continue
            
            # Calcular consumo médio
            ene_cols = [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)]
            consumos = [float(row.get(c, 0) or 0) for c in ene_cols if c in row]
            consumo_medio = sum(consumos) / len(consumos) if consumos else 0
            
            ponto = PontoMapaCompleto(
                id=str(row.get("COD_ID", idx)),
                latitude=lat,
                longitude=lng,
                cod_id=str(row.get("COD_ID", "")),
                titulo=str(row.get("Nome_Município", "") or row.get("COD_ID", "")),
                tipo_consumidor="livre" if row.get("LIV") == 1 else "cativo",
                classe=CLAS_SUB_MAP.get(str(row.get("CLAS_SUB", "")), str(row.get("CLAS_SUB", ""))),
                grupo_tarifario=str(row.get("GRU_TAR", "")),
                municipio=str(row.get("Nome_Município", "")),
                uf=str(row.get("Nome_UF", "")),
                demanda=float(row.get("DEM_CONT", 0) or 0),
                demanda_contratada=float(row.get("DEM_CONT", 0) or 0),
                consumo_medio=round(consumo_medio, 2),
                consumo_max=float(row.get("ENE_MAX", 0) or 0),
                carga_instalada=float(row.get("CAR_INST", 0) or 0),
                possui_solar=bool(row.get("POSSUI_SOLAR", False))
            )
            pontos.append(ponto)
        except Exception:
            continue
    
    # Calcular centro
    if pontos:
        lats = [p.latitude for p in pontos]
        lngs = [p.longitude for p in pontos]
        centro = {
            "lat": sum(lats) / len(lats),
            "lng": sum(lngs) / len(lngs)
        }
    else:
        centro = {"lat": -15.7801, "lng": -47.9292}
    
    # Estatísticas rápidas
    demandas = [p.demanda or 0 for p in pontos if p.demanda]
    estatisticas = {
        "total_pontos": len(pontos),
        "total_base": total,
        "com_solar": sum(1 for p in pontos if p.possui_solar),
        "livres": sum(1 for p in pontos if p.tipo_consumidor == "livre"),
        "cativos": sum(1 for p in pontos if p.tipo_consumidor == "cativo"),
        "demanda_media": round(sum(demandas) / len(demandas), 2) if demandas else 0,
    }
    
    return MapaAvancadoResponse(
        pontos=pontos,
        total=total,
        centro=centro,
        zoom=10 if len(pontos) < 500 else 8,
        estatisticas=estatisticas
    )


@router.post("/mapa/exportar-selecao")
async def exportar_selecao_mapa(
    request: "ExportarSelecaoRequest",
    current_user: User = Depends(get_current_active_user)
):
    """
    Exporta dados de pontos dentro de uma área selecionada no mapa.
    Retorna arquivo XLSX ou CSV.
    """
    from app.schemas.aneel import ExportarSelecaoRequest, CLAS_SUB_MAP
    
    # Usar dados processados com enriquecimento
    df = ANEELService.carregar_dados_processados()
    
    if df.empty:
        raise HTTPException(status_code=404, detail="Nenhum dado disponível")
    
    # Filtrar por bounds (área selecionada)
    bounds = request.bounds
    north = bounds.get("north", 90)
    south = bounds.get("south", -90)
    east = bounds.get("east", 180)
    west = bounds.get("west", -180)
    
    # POINT_Y = latitude, POINT_X = longitude (já convertidos em dados processados)
    df_area = df[
        (df["POINT_Y"] >= south) & 
        (df["POINT_Y"] <= north) &
        (df["POINT_X"] >= west) & 
        (df["POINT_X"] <= east)
    ]
    
    # Aplicar filtros adicionais se fornecidos
    filtros = request.filtros or {}
    
    if filtros.get("possui_solar") is not None:
        df_area = df_area[df_area["POSSUI_SOLAR"] == filtros["possui_solar"]]
    
    if filtros.get("tipo_consumidor"):
        if filtros["tipo_consumidor"].lower() == "livre":
            df_area = df_area[df_area["LIV"] == 1]
        elif filtros["tipo_consumidor"].lower() == "cativo":
            df_area = df_area[df_area["LIV"] == 0]
    
    if df_area.empty:
        raise HTTPException(status_code=404, detail="Nenhum ponto encontrado na área selecionada")
    
    # Preparar dados para exportação
    colunas_export = [
        "COD_ID", "Nome_UF", "Nome_Município", "CLAS_SUB", "GRU_TAR", "LIV",
        "DEM_CONT", "CAR_INST", "ENE_MAX", "CEG_GD", "POINT_X", "POINT_Y"
    ]
    colunas_disponiveis = [c for c in colunas_export if c in df_area.columns]
    df_export = df_area[colunas_disponiveis].copy()
    
    # Renomear colunas para português
    renome = {
        "COD_ID": "Código",
        "Nome_UF": "Estado",
        "Nome_Município": "Município",
        "CLAS_SUB": "Classe",
        "GRU_TAR": "Grupo Tarifário",
        "LIV": "Livre",
        "DEM_CONT": "Demanda Contratada",
        "CAR_INST": "Carga Instalada",
        "ENE_MAX": "Energia Máxima",
        "CEG_GD": "Geração Distribuída",
        "POINT_X": "Longitude",
        "POINT_Y": "Latitude"
    }
    df_export = df_export.rename(columns=renome)
    
    # Converter coluna Livre
    if "Livre" in df_export.columns:
        df_export["Livre"] = df_export["Livre"].map({1: "Sim", 0: "Não"})
    
    # Exportar
    if request.formato == "csv":
        csv_bytes = df_export.to_csv(index=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=selecao_mapa_{len(df_export)}_pontos.csv"}
        )
    else:
        xlsx_buffer = io.BytesIO()
        df_export.to_excel(xlsx_buffer, index=False, engine="openpyxl")
        xlsx_buffer.seek(0)
        return StreamingResponse(
            xlsx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=selecao_mapa_{len(df_export)}_pontos.xlsx"}
        )


# ============ Endpoints de Consultas Salvas ============

@router.get("/consultas-salvas")
async def listar_consultas_salvas(
    query_type: Optional[str] = Query(None, description="Filtrar por tipo: consulta, mapa, tarifas"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista todas as consultas salvas do usuário"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    import json
    
    query = select(SavedQuery).where(SavedQuery.user_id == current_user.id)
    
    if query_type:
        query = query.where(SavedQuery.query_type == query_type)
    
    query = query.order_by(SavedQuery.last_used_at.desc().nullsfirst(), SavedQuery.created_at.desc())
    
    result = await db.execute(query)
    saved_queries = result.scalars().all()
    
    return [
        {
            "id": sq.id,
            "name": sq.name,
            "description": sq.description,
            "filters": json.loads(sq.filters) if sq.filters else {},
            "query_type": sq.query_type,
            "created_at": sq.created_at.isoformat() if sq.created_at else None,
            "updated_at": sq.updated_at.isoformat() if sq.updated_at else None,
            "last_used_at": sq.last_used_at.isoformat() if sq.last_used_at else None,
            "use_count": sq.use_count or 0
        }
        for sq in saved_queries
    ]


@router.post("/consultas-salvas")
async def criar_consulta_salva(
    data: "SavedQueryCreate",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Salva uma nova consulta"""
    from app.models.user import SavedQuery
    from app.schemas.aneel import SavedQueryCreate
    import json
    
    nova_consulta = SavedQuery(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        filters=json.dumps(data.filters),
        query_type=data.query_type
    )
    
    db.add(nova_consulta)
    await db.commit()
    await db.refresh(nova_consulta)
    
    return {
        "id": nova_consulta.id,
        "name": nova_consulta.name,
        "message": "Consulta salva com sucesso!"
    }


@router.put("/consultas-salvas/{query_id}")
async def atualizar_consulta_salva(
    query_id: int,
    data: "SavedQueryUpdate",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza uma consulta salva"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    from app.schemas.aneel import SavedQueryUpdate
    import json
    
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == query_id,
            SavedQuery.user_id == current_user.id
        )
    )
    consulta = result.scalar_one_or_none()
    
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    if data.name:
        consulta.name = data.name
    if data.description is not None:
        consulta.description = data.description
    if data.filters:
        consulta.filters = json.dumps(data.filters)
    
    await db.commit()
    
    return {"message": "Consulta atualizada com sucesso!"}


@router.delete("/consultas-salvas/{query_id}")
async def excluir_consulta_salva(
    query_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Exclui uma consulta salva"""
    from sqlalchemy import select, delete
    from app.models.user import SavedQuery
    
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == query_id,
            SavedQuery.user_id == current_user.id
        )
    )
    consulta = result.scalar_one_or_none()
    
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    await db.delete(consulta)
    await db.commit()
    
    return {"message": "Consulta excluída com sucesso!"}


@router.post("/consultas-salvas/{query_id}/usar")
async def usar_consulta_salva(
    query_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Registra uso de uma consulta salva e retorna os filtros"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    from datetime import datetime
    import json
    
    result = await db.execute(
        select(SavedQuery).where(
            SavedQuery.id == query_id,
            SavedQuery.user_id == current_user.id
        )
    )
    consulta = result.scalar_one_or_none()
    
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    # Atualizar uso
    consulta.use_count = (consulta.use_count or 0) + 1
    consulta.last_used_at = datetime.utcnow()
    await db.commit()
    
    return {
        "id": consulta.id,
        "name": consulta.name,
        "filters": json.loads(consulta.filters) if consulta.filters else {},
        "query_type": consulta.query_type
    }


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
