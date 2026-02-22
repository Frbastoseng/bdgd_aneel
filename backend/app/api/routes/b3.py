"""
Rotas para dados BDGD B3 (Baixa Tensão)
"""
from fastapi import APIRouter, Body, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import io
import pandas as pd

from app.core.database import get_db
from app.models.user import User
from app.schemas.b3 import (
    FiltroB3,
    ConsultaB3Response,
    ClienteB3,
    MapaB3Response,
    PontoMapaB3,
    ExportarSelecaoB3Request,
    CLAS_SUB_B3_MAP,
)
from app.schemas.aneel import CLAS_SUB_MAP, SavedQueryCreate, SavedQueryUpdate
from app.services.b3_service import B3Service
from app.services.b3_matching_service import B3MatchingService
from app.services.b3_refine_service import B3RefineService
from app.services.b3_lista_service import B3ListaService
from app.api.deps import get_current_active_user, get_current_admin

router = APIRouter(prefix="/b3", tags=["Dados B3"])


# ============ Endpoints de Dados B3 ============

@router.post("/consulta", response_model=ConsultaB3Response)
async def consultar_dados_b3(
    filtros: FiltroB3,
    current_user: User = Depends(get_current_active_user)
):
    """Consulta dados da BDGD B3 com filtros."""
    try:
        from app.services.gd_client import buscar_multiplos_cegs

        dados, total = await B3Service.consultar_dados(filtros)
        total_pages = (total + filtros.per_page - 1) // filtros.per_page

        all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}

        clientes = []
        for d in dados:
            cliente = ClienteB3(
                cod_id=d.get("COD_ID_ENCR"),
                dist=d.get("DIST"),
                pac=d.get("PAC"),
                mun=d.get("MUN"),
                nome_uf=d.get("Nome_UF"),
                nome_municipio=d.get("Nome_Município"),
                lgrd=d.get("LGRD"),
                brr=d.get("BRR"),
                cep=d.get("CEP"),
                clas_sub=d.get("CLAS_SUB"),
                clas_sub_descricao=all_clas_map.get(str(d.get("CLAS_SUB", "")), d.get("CLAS_SUB")),
                cnae=d.get("CNAE"),
                fas_con=d.get("FAS_CON"),
                gru_ten=d.get("GRU_TEN"),
                gru_tar=d.get("GRU_TAR"),
                sit_ativ=d.get("SIT_ATIV"),
                area_loc=d.get("ARE_LOC"),
                tip_cc=d.get("TIP_CC"),
                car_inst=d.get("CAR_INST"),
                consumo_anual=d.get("CONSUMO_ANUAL"),
                consumo_medio=d.get("CONSUMO_MEDIO"),
                ene_max=d.get("ENE_MAX"),
                ene_01=d.get("ENE_01"), ene_02=d.get("ENE_02"), ene_03=d.get("ENE_03"),
                ene_04=d.get("ENE_04"), ene_05=d.get("ENE_05"), ene_06=d.get("ENE_06"),
                ene_07=d.get("ENE_07"), ene_08=d.get("ENE_08"), ene_09=d.get("ENE_09"),
                ene_10=d.get("ENE_10"), ene_11=d.get("ENE_11"), ene_12=d.get("ENE_12"),
                dic_01=d.get("DIC_01"), dic_02=d.get("DIC_02"), dic_03=d.get("DIC_03"),
                dic_04=d.get("DIC_04"), dic_05=d.get("DIC_05"), dic_06=d.get("DIC_06"),
                dic_07=d.get("DIC_07"), dic_08=d.get("DIC_08"), dic_09=d.get("DIC_09"),
                dic_10=d.get("DIC_10"), dic_11=d.get("DIC_11"), dic_12=d.get("DIC_12"),
                dic_anual=d.get("DIC_ANUAL"),
                fic_01=d.get("FIC_01"), fic_02=d.get("FIC_02"), fic_03=d.get("FIC_03"),
                fic_04=d.get("FIC_04"), fic_05=d.get("FIC_05"), fic_06=d.get("FIC_06"),
                fic_07=d.get("FIC_07"), fic_08=d.get("FIC_08"), fic_09=d.get("FIC_09"),
                fic_10=d.get("FIC_10"), fic_11=d.get("FIC_11"), fic_12=d.get("FIC_12"),
                fic_anual=d.get("FIC_ANUAL"),
                ceg_gd=d.get("CEG_GD"),
                possui_solar=d.get("POSSUI_SOLAR", False),
                latitude=d.get("POINT_Y"),
                longitude=d.get("POINT_X"),
                dat_con=str(d.get("DAT_CON", "")) if d.get("DAT_CON") else None,
            )
            clientes.append(cliente)

        # Enriquecer com dados de Geração Distribuída
        cegs = [c.ceg_gd for c in clientes if c.ceg_gd]
        if cegs:
            gd_data = await buscar_multiplos_cegs(cegs)
            for cliente in clientes:
                if cliente.ceg_gd and cliente.ceg_gd in gd_data:
                    gd = gd_data[cliente.ceg_gd]
                    if gd:  # dict não vazio
                        gd_info = {
                            "cod_empreendimento": gd.get("cod_empreendimento"),
                            "tipo_geracao": gd.get("sig_tipo_geracao"),
                            "fonte_geracao": gd.get("dsc_fonte_geracao"),
                            "porte": gd.get("dsc_porte"),
                            "potencia_instalada_kw": gd.get("potencia_instalada_kw"),
                            "data_conexao": gd.get("dth_conexao_inicial"),
                            "modalidade": gd.get("sig_modalidade"),
                            "qtd_modulos": gd.get("qtd_modulos"),
                            "agente": gd.get("sig_agente"),
                            "nom_agente": gd.get("nom_agente"),
                        }
                        if gd.get("dados_tecnicos"):
                            gd_info["dados_tecnicos"] = gd["dados_tecnicos"]
                        cliente.geracao_distribuida = gd_info
                        cliente.nome_real = gd.get("nom_titular")
                        cliente.cnpj_real = gd.get("num_cpf_cnpj")

        return ConsultaB3Response(
            dados=clientes,
            total=total,
            page=filtros.page,
            per_page=filtros.per_page,
            total_pages=total_pages
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao consultar dados B3: {str(e)}"
        )


@router.get("/opcoes-filtros")
async def obter_opcoes_filtros_b3(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna opções disponíveis para os filtros B3"""
    return await B3Service.obter_opcoes_filtros()


@router.post("/exportar/csv")
async def exportar_csv_b3(
    filtros: FiltroB3,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados B3 filtrados em formato CSV"""
    filtros.per_page = 100000
    dados, _ = await B3Service.consultar_dados(filtros)
    if not dados:
        raise HTTPException(status_code=404, detail="Nenhum dado encontrado para exportação")
    df = pd.DataFrame(dados)
    csv_bytes = B3Service.exportar_csv(df)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dados_b3.csv"}
    )


@router.post("/exportar/xlsx")
async def exportar_xlsx_b3(
    filtros: FiltroB3,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados B3 filtrados em formato XLSX"""
    filtros.per_page = 100000
    dados, _ = await B3Service.consultar_dados(filtros)
    if not dados:
        raise HTTPException(status_code=404, detail="Nenhum dado encontrado para exportação")
    df = pd.DataFrame(dados)
    xlsx_bytes = B3Service.exportar_xlsx(df)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=dados_b3.xlsx"}
    )


@router.post("/exportar/kml")
async def exportar_kml_b3(
    filtros: FiltroB3,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados B3 filtrados em formato KML"""
    filtros.per_page = 50000
    dados, _ = await B3Service.consultar_dados(filtros)
    if not dados:
        raise HTTPException(status_code=404, detail="Nenhum dado encontrado para exportação")
    df = pd.DataFrame(dados)
    kml_str = B3Service.exportar_kml(df)
    return StreamingResponse(
        io.BytesIO(kml_str.encode("utf-8")),
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": "attachment; filename=dados_b3.kml"}
    )


@router.get("/status-dados")
async def status_dados_b3(
    current_user: User = Depends(get_current_active_user)
):
    """Retorna status dos dados B3"""
    return B3Service.get_status_dados()


@router.post("/importar")
async def importar_dados_b3(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin)
):
    """Importa dados B3 de arquivo ZIP contendo CSV"""
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="O arquivo deve ser um ZIP contendo CSV")

    try:
        import zipfile
        import tempfile
        import os

        # Salvar arquivo temporário
        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            from app.scripts.importar_b3 import importar_b3_zip
            resultado = importar_b3_zip(tmp_path)
            B3Service._limpar_cache()
            return resultado
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao importar dados B3: {str(e)}"
        )


# ============ Endpoints de Mapa B3 ============

@router.get("/mapa/pontos")
async def obter_pontos_mapa_b3(
    uf: Optional[str] = Query(None),
    municipio: Optional[str] = Query(None),
    possui_solar: Optional[bool] = None,
    classe: Optional[str] = Query(None),
    fas_con: Optional[str] = Query(None),
    consumo_min: Optional[float] = None,
    consumo_max: Optional[float] = None,
    limit: int = Query(5000, le=20000),
    current_user: User = Depends(get_current_active_user)
):
    """Retorna pontos para o mapa B3"""
    result = await B3Service.mapa_avancado(
        uf=uf, municipio=municipio, possui_solar=possui_solar,
        classe=classe, fas_con=fas_con,
        consumo_min=consumo_min, consumo_max=consumo_max,
        limit=limit
    )
    return MapaB3Response(**result)


@router.post("/mapa/exportar-selecao")
async def exportar_selecao_mapa_b3(
    request: ExportarSelecaoB3Request,
    current_user: User = Depends(get_current_active_user)
):
    """Exporta dados de pontos B3 dentro de uma área selecionada no mapa"""
    df = await B3Service.carregar_dados_processados()
    if df.empty:
        raise HTTPException(status_code=404, detail="Nenhum dado disponível")

    bounds = request.bounds
    df_area = df[
        (df["POINT_Y"] >= bounds.get("south", -90)) &
        (df["POINT_Y"] <= bounds.get("north", 90)) &
        (df["POINT_X"] >= bounds.get("west", -180)) &
        (df["POINT_X"] <= bounds.get("east", 180))
    ]

    if df_area.empty:
        raise HTTPException(status_code=404, detail="Nenhum ponto encontrado na área selecionada")

    all_clas_map = {**CLAS_SUB_MAP, **CLAS_SUB_B3_MAP}
    colunas_export = [
        "COD_ID_ENCR", "Nome_UF", "Nome_Município", "LGRD", "BRR", "CEP",
        "CLAS_SUB", "CNAE", "FAS_CON", "GRU_TAR", "SIT_ATIV",
        "CAR_INST", "CONSUMO_ANUAL", "CONSUMO_MEDIO", "DIC_ANUAL", "FIC_ANUAL",
        "CEG_GD", "POINT_X", "POINT_Y"
    ]
    colunas_disponiveis = [c for c in colunas_export if c in df_area.columns]
    df_export = df_area[colunas_disponiveis].copy()

    renome = {
        "COD_ID_ENCR": "Código", "Nome_UF": "Estado", "Nome_Município": "Município",
        "LGRD": "Logradouro", "BRR": "Bairro", "CEP": "CEP",
        "CLAS_SUB": "Classe", "CNAE": "CNAE", "FAS_CON": "Fase Conexão",
        "GRU_TAR": "Grupo Tarifário", "SIT_ATIV": "Situação",
        "CAR_INST": "Carga Instalada", "CONSUMO_ANUAL": "Consumo Anual",
        "CONSUMO_MEDIO": "Consumo Médio", "DIC_ANUAL": "DIC Anual",
        "FIC_ANUAL": "FIC Anual", "CEG_GD": "Geração Distribuída",
        "POINT_X": "Longitude", "POINT_Y": "Latitude"
    }
    df_export = df_export.rename(columns=renome)

    if request.formato == "csv":
        csv_bytes = df_export.to_csv(index=False, sep=";").encode("utf-8-sig")
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=selecao_b3_{len(df_export)}_pontos.csv"}
        )
    else:
        xlsx_buffer = io.BytesIO()
        df_export.to_excel(xlsx_buffer, index=False, engine="openpyxl")
        xlsx_buffer.seek(0)
        return StreamingResponse(
            xlsx_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=selecao_b3_{len(df_export)}_pontos.xlsx"}
        )


# ============ Consultas Salvas B3 ============

@router.get("/consultas-salvas")
async def listar_consultas_salvas_b3(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lista consultas salvas do tipo B3"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    import json

    query = select(SavedQuery).where(
        SavedQuery.user_id == current_user.id,
        SavedQuery.query_type == "b3"
    ).order_by(SavedQuery.last_used_at.desc().nullsfirst(), SavedQuery.created_at.desc())

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
async def criar_consulta_salva_b3(
    data: SavedQueryCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Salva uma nova consulta B3"""
    from app.models.user import SavedQuery
    import json

    nova_consulta = SavedQuery(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        filters=json.dumps(data.filters),
        query_type="b3"
    )

    db.add(nova_consulta)
    await db.commit()
    await db.refresh(nova_consulta)

    return {"id": nova_consulta.id, "name": nova_consulta.name, "message": "Consulta B3 salva com sucesso!"}


@router.put("/consultas-salvas/{query_id}")
async def atualizar_consulta_salva_b3(
    query_id: int,
    data: SavedQueryUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Atualiza uma consulta salva B3"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    import json

    result = await db.execute(
        select(SavedQuery).where(SavedQuery.id == query_id, SavedQuery.user_id == current_user.id)
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
    return {"message": "Consulta B3 atualizada com sucesso!"}


@router.delete("/consultas-salvas/{query_id}")
async def excluir_consulta_salva_b3(
    query_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Exclui uma consulta salva B3"""
    from sqlalchemy import select
    from app.models.user import SavedQuery

    result = await db.execute(
        select(SavedQuery).where(SavedQuery.id == query_id, SavedQuery.user_id == current_user.id)
    )
    consulta = result.scalar_one_or_none()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    await db.delete(consulta)
    await db.commit()
    return {"message": "Consulta B3 excluída com sucesso!"}


@router.post("/consultas-salvas/{query_id}/usar")
async def usar_consulta_salva_b3(
    query_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Registra uso de uma consulta salva B3 e retorna os filtros"""
    from sqlalchemy import select
    from app.models.user import SavedQuery
    from datetime import datetime
    import json

    result = await db.execute(
        select(SavedQuery).where(SavedQuery.id == query_id, SavedQuery.user_id == current_user.id)
    )
    consulta = result.scalar_one_or_none()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    consulta.use_count = (consulta.use_count or 0) + 1
    consulta.last_used_at = datetime.utcnow()
    await db.commit()

    return {
        "id": consulta.id,
        "name": consulta.name,
        "filters": json.loads(consulta.filters) if consulta.filters else {},
        "query_type": consulta.query_type
    }


# ============ Matching B3 -> CNPJ ============

@router.get("/matching/stats")
async def get_b3_matching_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna estatísticas do matching B3 -> CNPJ."""
    return await B3MatchingService.get_stats(db)


@router.post("/matching/batch-lookup")
async def b3_batch_lookup(
    cod_ids: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna o melhor match CNPJ para uma lista de cod_ids B3 (max 1000).

    Usado para enriquecer dados B3 na ConsultaB3Page e MapaB3Page.
    """
    if len(cod_ids) > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo de 1000 cod_ids por requisição.",
        )
    return await B3MatchingService.batch_lookup(db, cod_ids)


@router.post("/matching/refine")
async def b3_refine_matches(
    cod_ids: list[str] = Body(..., embed=True, max_length=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Geocodifica coordenadas e re-faz matching para clientes B3 (max 100).

    Fluxo:
      1. Geocodifica coordenadas via Nominatim (com cache compartilhado)
      2. Re-calcula matching com dupla fonte de endereço (BDGD + geocodificado)
      3. Retorna contagem de resultados melhorados
    """
    if len(cod_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo de 100 clientes por requisição.",
        )
    return await B3RefineService.refine_clientes(db, cod_ids)


@router.get("/matching/results/{cod_id}")
async def get_b3_cliente_matches(
    cod_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna detalhes de matching para um cliente B3."""
    result = await B3MatchingService.get_cliente_matches(db, cod_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente B3 {cod_id} não encontrado.",
        )
    return result


@router.post("/matching/populate")
async def populate_b3_clientes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    """Popular tabela b3_clientes a partir do parquet B3 (admin only).

    Necessário executar antes de rodar o matching.
    """
    return await B3MatchingService.populate_b3_clientes(db)


# ============ Listas de Prospecção B3 ============

@router.get("/listas")
async def listar_listas_b3(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista todas as listas de prospecção do usuário."""
    return await B3ListaService.listar(db, current_user.id)


@router.post("/listas")
async def criar_lista_b3(
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Cria uma nova lista de prospecção B3."""
    nome = data.get("nome")
    if not nome:
        raise HTTPException(status_code=400, detail="Nome é obrigatório")
    return await B3ListaService.criar(
        db, current_user.id,
        nome=nome,
        descricao=data.get("descricao"),
        filtros_aplicados=data.get("filtros_aplicados"),
    )


@router.get("/listas/{lista_id}")
async def detalhe_lista_b3(
    lista_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna detalhes de uma lista com suas UCs."""
    result = await B3ListaService.detalhe(db, lista_id, current_user.id)
    if not result:
        raise HTTPException(status_code=404, detail="Lista não encontrada")
    return result


@router.post("/listas/{lista_id}/adicionar")
async def adicionar_unidades_lista_b3(
    lista_id: int,
    cod_ids: list[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Adiciona UCs a uma lista de prospecção."""
    if len(cod_ids) > 10000:
        raise HTTPException(status_code=400, detail="Máximo de 10.000 UCs por operação")
    result = await B3ListaService.adicionar_unidades(db, lista_id, current_user.id, cod_ids)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/listas/{lista_id}/remover")
async def remover_unidades_lista_b3(
    lista_id: int,
    cod_ids: list[str] = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove UCs de uma lista de prospecção."""
    result = await B3ListaService.remover_unidades(db, lista_id, current_user.id, cod_ids)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/listas/{lista_id}")
async def excluir_lista_b3(
    lista_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Exclui uma lista de prospecção."""
    deleted = await B3ListaService.excluir(db, lista_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Lista não encontrada")
    return {"message": "Lista excluída com sucesso"}


@router.post("/listas/salvar-filtro")
async def salvar_filtro_como_lista_b3(
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Salva o resultado de um filtro como uma lista de prospecção (até 10.000 UCs)."""
    nome = data.get("nome")
    cod_ids = data.get("cod_ids", [])
    if not nome:
        raise HTTPException(status_code=400, detail="Nome é obrigatório")
    if not cod_ids:
        raise HTTPException(status_code=400, detail="Lista de cod_ids é obrigatória")
    return await B3ListaService.salvar_filtro_como_lista(
        db, current_user.id,
        nome=nome,
        descricao=data.get("descricao"),
        filtros=data.get("filtros", {}),
        cod_ids=cod_ids,
    )


@router.get("/listas/{lista_id}/exportar/csv")
async def exportar_lista_csv_b3(
    lista_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Exporta uma lista de prospecção como CSV."""
    csv_bytes = await B3ListaService.exportar_csv(db, lista_id, current_user.id)
    if not csv_bytes:
        raise HTTPException(status_code=404, detail="Lista vazia ou não encontrada")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=lista_prospeccao_{lista_id}.csv"}
    )
