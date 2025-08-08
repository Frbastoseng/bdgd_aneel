import streamlit as st
import pandas as pd
import requests
import os
from streamlit_folium import folium_static
import folium
import io
import numpy as np
import simplekml

# Configuração da página
st.set_page_config(page_title="Consulta Nome_UF e Nome_Município - ANEEL", layout="wide")

# Título
st.title("🔍 Consulta por Nome_UF e Nome_Município - ANEEL")

# URL da API da ANEEL e nome do arquivo local
API_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
RESOURCE_ID = "f6671cba-f269-42ef-8eb3-62cb3bfa0b98"
LOCAL_DATA_FILE = "dados_aneel.parquet"

# Função para baixar 100% dos dados da ANEEL
@st.cache_data
def baixar_dados_aneel():
    try:
        response = requests.get(API_URL, params={"resource_id": RESOURCE_ID, "limit": 1}, timeout=60)
        response.raise_for_status()
        total_registros = response.json()["result"]["total"]
        st.write(f"📡 Total de registros reportados pela API: {total_registros}")
    except Exception as e:
        st.error(f"Erro ao consultar total de registros: {e}")
        return pd.DataFrame()

    limite_por_requisicao = 32000
    dados_completos = []
    total_baixado = 0
    offset = 0

    with st.spinner(f"Baixando {total_registros} registros em lotes de {limite_por_requisicao}..."):
        while offset < total_registros:
            try:
                params = {"resource_id": RESOURCE_ID, "limit": limite_por_requisicao, "offset": offset}
                response = requests.get(API_URL, params=params, timeout=120)
                response.raise_for_status()

                registros = response.json().get("result", {}).get("records", [])
                if not registros:
                    st.warning(f"⚠️ Nenhum dado retornado no offset {offset}. Interrompendo download.")
                    break

                dados_completos.extend(registros)
                total_baixado += len(registros)
                st.write(f"📥 Baixados {total_baixado}/{total_registros} registros...")
                offset += limite_por_requisicao
            except Exception as e:
                st.error(f"Erro no lote offset {offset}: {e}")
                break

    df = pd.DataFrame(dados_completos)
    st.write(f"📊 Total consolidado: {len(df)} registros.")
    if len(df) < total_registros:
        st.warning(f"⚠️ Atenção: esperados {total_registros}, baixados {len(df)} registros.")

    try:
        df.to_parquet(LOCAL_DATA_FILE, index=False)
        st.success(f"✅ Dados salvos localmente com sucesso ({len(df)} registros).")
    except Exception as e:
        st.error(f"Erro ao salvar em arquivo local: {e}")

    return df

# Função para carregar dados locais
@st.cache_data
def carregar_dados_locais():
    if os.path.exists(LOCAL_DATA_FILE):
        try:
            df = pd.read_parquet(LOCAL_DATA_FILE)
            st.write(f"📊 Dados locais carregados: {len(df)} registros")
            return df
        except Exception as e:
            st.error(f"Erro ao carregar os dados locais: {e}")
            return pd.DataFrame()
    else:
        st.warning("Dados locais não encontrados. Realizando download inicial...")
        return baixar_dados_aneel()

# Botão para atualizar os dados manualmente
if st.button("🔄 Atualizar Dados da ANEEL"):
    with st.spinner("Atualizando dados da ANEEL..."):
        df_dados = baixar_dados_aneel()
        if not df_dados.empty:
            st.success(f"Dados atualizados com sucesso! Total de registros: {len(df_dados)}")
else:
    df_dados = carregar_dados_locais()

if df_dados.empty:
    st.error("⚠️ Nenhum dado disponível. Verifique a conexão ou tente atualizar manualmente.")
else:
    st.write(f"📊 Total de registros carregados: {len(df_dados)}")

# Carregar dados da planilha
st.sidebar.header("📂 Carregar Planilha")
file_path = "RELATORIO_DTB_BRASIL_DISTRITO.xls"

if not os.path.exists(file_path):
    st.sidebar.error(f"⚠️ Arquivo {file_path} não encontrado! Coloque o arquivo na mesma pasta do script.")
else:
    try:
        df_planilha = pd.read_excel(file_path, dtype=str)
        df_planilha.columns = df_planilha.columns.str.strip()
        colunas_necessarias = ["Nome_UF", "Nome_Município", "Código Município Completo", "Nome_Microrregião", "Nome_Mesorregião"]
        missing_cols = [col for col in colunas_necessarias if col not in df_planilha.columns]
        if missing_cols:
            st.sidebar.error(f"⚠️ Colunas ausentes na planilha: {', '.join(missing_cols)}. Verifique os nomes.")
        else:
            st.sidebar.success(f"📊 Planilha carregada com {len(df_planilha)} linhas!")
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar a planilha: {e}")
        df_planilha = pd.DataFrame()

# Dicionário de mapeamento para CLAS_SUB
clas_sub_map = {
    "0": "Não informado", "RE1": "Residencial", "RE2": "Residencial baixa renda",
    "REBR": "Residencial baixa renda indígena", "REQU": "Residencial baixa renda quilombola",
    "REBP": "Residencial baixa renda benefício de prestação continuada da assistência social – BPC",
    "REMU": "Residencial baixa renda multifamiliar", "IN": "Industrial", "CO1": "Comercial",
    "CO2": "Serviços de transporte, exceto tração elétrica", "CO3": "Serviços de comunicações e telecomunicações",
    "CO4": "Associação e entidades filantrópicas", "CO5": "Templos religiosos",
    "CO6": "Administração condominial: iluminação e instalações de uso comum de prédio ou conjunto de edificações",
    "CO7": "Iluminação em rodovias", "CO8": "Semáforos, radares e câmeras de monitoramento de trânsito",
    "CO9": "Outros serviços e outras atividades", "RU1": "Agropecuária rural",
    "RU1A": "Agropecuária rural (poços de captação de água)", "RU1B": "Agropecuária rural (bombeamento de água)",
    "RU2": "Agropecuária urbana", "RU3": "Residencial rural", "RU4": "Cooperativa de eletrificação rural",
    "RU5": "Agroindustrial", "RU6": "Serviço público de irrigação rural", "RU7": "Escola agrotécnica",
    "RU8": "Aqüicultura", "PP1": "Poder público federal", "PP2": "Poder público estadual ou distrital",
    "PP3": "Poder público municipal", "IP": "Iluminação pública", "SP1": "Tração elétrica",
    "SP2": "Água, esgoto e saneamento", "CPR": "Consumo próprio pela distribuidora", "CSPS": "Concessionária ou Permissionária"
}

# Função para obter opções de GRU_TAR
@st.cache_data
def obter_opcoes_filtros(df):
    return sorted(df["GRU_TAR"].dropna().unique().tolist())

# Função para ordenar por proximidade geográfica
def ordenar_por_proximidade(df, x_col="POINT_X", y_col="POINT_Y"):
    df_valid = df.dropna(subset=[x_col, y_col]).copy()
    if df_valid.empty:
        return df

    coords = df_valid[[x_col, y_col]].values
    n = len(coords)
    if n <= 1:
        return df

    ordem = [0]
    usados = {0}

    for _ in range(n - 1):
        ultimo_idx = ordem[-1]
        ultimo_ponto = coords[ultimo_idx]
        menor_dist = float('inf')
        proximo_idx = None

        for i in range(n):
            if i not in usados:
                ponto = coords[i]
                dist = np.sqrt((ultimo_ponto[0] - ponto[0])**2 + (ultimo_ponto[1] - ponto[1])**2)
                if dist < menor_dist:
                    menor_dist = dist
                    proximo_idx = i

        if proximo_idx is not None:
            ordem.append(proximo_idx)
            usados.add(proximo_idx)

    df_valid = df_valid.iloc[ordem].reset_index(drop=True)
    df_invalid = df[df[x_col].isna() | df[y_col].isna()]
    return pd.concat([df_valid, df_invalid], ignore_index=True)

# Filtros interativos
st.sidebar.header("Filtros")
ufs_disponiveis = df_planilha.get("Nome_UF", pd.Series([])).dropna().unique().tolist()
uf_selecionada = st.sidebar.selectbox("🌎 Selecione a Nome_UF:", [""] + sorted(ufs_disponiveis))

if uf_selecionada:
    municipios_disponiveis = df_planilha[df_planilha["Nome_UF"] == uf_selecionada]["Nome_Município"].dropna().unique().tolist()
    microrregioes_disponiveis = df_planilha[df_planilha["Nome_UF"] == uf_selecionada]["Nome_Microrregião"].dropna().unique().tolist()
    mesorregioes_disponiveis = df_planilha[df_planilha["Nome_UF"] == uf_selecionada]["Nome_Mesorregião"].dropna().unique().tolist()
else:
    municipios_disponiveis = df_planilha.get("Nome_Município", pd.Series([])).dropna().unique().tolist()
    microrregioes_disponiveis = df_planilha.get("Nome_Microrregião", pd.Series([])).dropna().unique().tolist()
    mesorregioes_disponiveis = df_planilha.get("Nome_Mesorregião", pd.Series([])).dropna().unique().tolist()

municipios_selecionados = st.sidebar.multiselect("🏙️ Selecione o(s) Nome_Município:", sorted(municipios_disponiveis))
microrregioes_selecionadas = st.sidebar.multiselect("📍 Selecione a(s) Nome_Microrregião:", sorted(microrregioes_disponiveis))
mesorregioes_selecionadas = st.sidebar.multiselect("🗺️ Selecione a(s) Nome_Mesorregião:", sorted(mesorregioes_disponiveis))

# Filtros avançados
st.sidebar.subheader("Filtros Avançados")
ceg_gd_opcoes = ["Possui Solar", "Não possui Solar"]
ceg_gd_filtro = st.sidebar.multiselect("☀️ Possui Usina Solar (CEG_GD):", ceg_gd_opcoes)
clas_sub_opcoes = sorted(clas_sub_map.values())
clas_sub_filtro = st.sidebar.multiselect("👥 Classe de Cliente (CLAS_SUB):", clas_sub_opcoes)
gru_tar_opcoes = obter_opcoes_filtros(df_dados)
gru_tar_filtro = st.sidebar.multiselect("💰 Grupo Tarifário (GRU_TAR):", gru_tar_opcoes)
liv_opcoes = ["Livre", "Cativo"]
liv_filtro = st.sidebar.multiselect("🔗 Tipo de Consumidor (LIV):", liv_opcoes)
dem_cont_operador = st.sidebar.selectbox("📏 Demanda Contratada (DEM_CONT):", ["Todos", "Maior que", "Menor que"])
dem_cont_valor = st.sidebar.number_input("Valor de DEM_CONT:", min_value=0.0, value=0.0, step=1.0)
st.sidebar.subheader("🔌 Filtro por Energia Máxima Mensal (ENE_MAX)")
ene_max_operador = st.sidebar.selectbox("Selecionar por:", ["Todos", "Maior que", "Menor que"], key="filtro_ene_max")
ene_max_valor = st.sidebar.number_input("Valor de ENE_MAX (kWh):", min_value=0.0, value=0.0, step=1.0, key="valor_ene_max")

# Botão para buscar dados
if st.sidebar.button("🔄 Buscar Dados") and not df_dados.empty and not df_planilha.empty:
    with st.spinner("Processando dados..."):
        df_filtrado = df_planilha.copy()

        if uf_selecionada:
            df_filtrado = df_filtrado[df_filtrado["Nome_UF"] == uf_selecionada]
        if municipios_selecionados:
            df_filtrado = df_filtrado[df_filtrado["Nome_Município"].isin(municipios_selecionados)]
        if microrregioes_selecionadas:
            df_filtrado = df_filtrado[df_filtrado["Nome_Microrregião"].isin(microrregioes_selecionadas)]
        if mesorregioes_selecionadas:
            df_filtrado = df_filtrado[df_filtrado["Nome_Mesorregião"].isin(mesorregioes_selecionadas)]

        codigos_municipios = df_filtrado["Código Município Completo"].dropna().unique().tolist()
        if not codigos_municipios:
            st.warning("⚠️ Nenhum município correspondente encontrado na planilha após filtros.")
        else:
            df_api = df_dados[df_dados["MUN"].isin(codigos_municipios)].copy()
            if not df_api.empty:
                # Converter colunas numéricas
                colunas_numericas = ["LIV", "DEM_CONT", "DEM_01", "DEM_02", "DEM_03", "ENE_01", "ENE_02", "DIC_01", "DIC_02", "FIC_01", "FIC_02", "POINT_X", "POINT_Y"]
                colunas_existentes = [col for col in colunas_numericas if col in df_api.columns]
                for coluna in colunas_existentes:
                    df_api[coluna] = pd.to_numeric(df_api[coluna], errors="coerce")

                df_api["MUN"] = df_api["MUN"].astype(str)
                df_filtrado["Código Município Completo"] = df_filtrado["Código Município Completo"].astype(str)

                # Merge
                df_final = df_api.merge(
                    df_filtrado[["Código Município Completo", "Nome_UF", "Nome_Município"]],
                    left_on="MUN",
                    right_on="Código Município Completo",
                    how="inner"
                ).drop(columns=["Código Município Completo"])

                if df_final.empty:
                    st.error("⚠️ Nenhum dado após o merge. Verifique os dados.")
                else:
                    # Substituir códigos de CLAS_SUB por descrições
                    if "CLAS_SUB" in df_final.columns:
                        df_final["CLAS_SUB"] = df_final["CLAS_SUB"].map(clas_sub_map).fillna(df_final["CLAS_SUB"])

                    # Criar coluna ENE_MAX antes dos filtros
                    colunas_energia = [f"ENE_{str(i).zfill(2)}" for i in range(1, 13)]
                    colunas_existentes_energia = [col for col in colunas_energia if col in df_final.columns]
                    for col in colunas_existentes_energia:
                        df_final[col] = pd.to_numeric(df_final[col], errors="coerce")
                    df_final["ENE_MAX"] = df_final[colunas_existentes_energia].max(axis=1)

                    # Aplicar filtros avançados
                    if ceg_gd_filtro:
                        mask = pd.Series(False, index=df_final.index)
                        if "Possui Solar" in ceg_gd_filtro:
                            mask |= df_final["CEG_GD"].notna() & (df_final["CEG_GD"] != "")
                        if "Não possui Solar" in ceg_gd_filtro:
                            mask |= df_final["CEG_GD"].isna() | (df_final["CEG_GD"] == "")
                        df_final = df_final[mask]

                    if clas_sub_filtro:
                        df_final = df_final[df_final["CLAS_SUB"].isin(clas_sub_filtro)]

                    if gru_tar_filtro:
                        df_final = df_final[df_final["GRU_TAR"].isin(gru_tar_filtro)]

                    if liv_filtro and "LIV" in df_final.columns:
                        df_final["LIV"] = pd.to_numeric(df_final["LIV"], errors="coerce")
                        liv_valores = [1 if x == "Livre" else 0 for x in liv_filtro]
                        df_final = df_final[df_final["LIV"].isin(liv_valores)]

                    if dem_cont_operador != "Todos" and "DEM_CONT" in df_final.columns:
                        df_final["DEM_CONT"] = pd.to_numeric(df_final["DEM_CONT"], errors="coerce")
                        if dem_cont_operador == "Maior que":
                            df_final = df_final[df_final["DEM_CONT"] > dem_cont_valor]
                        elif dem_cont_operador == "Menor que":
                            df_final = df_final[df_final["DEM_CONT"] < dem_cont_valor]

                    if ene_max_operador != "Todos" and "ENE_MAX" in df_final.columns:
                        if ene_max_operador == "Maior que":
                            df_final = df_final[df_final["ENE_MAX"] > ene_max_valor]
                        elif ene_max_operador == "Menor que":
                            df_final = df_final[df_final["ENE_MAX"] < ene_max_valor]

                    if df_final.empty:
                        st.warning("⚠️ Nenhum dado após aplicar filtros. Tente ajustar os critérios.")
                    else:
                        # Remover duplicatas
                        df_final = df_final.drop_duplicates()

                        # Criar coluna de coordenadas agrupadas
                        if "POINT_X" in df_final.columns and "POINT_Y" in df_final.columns:
                            df_final["Coordenadas"] = df_final.apply(
                                lambda row: f"{row['POINT_Y']}, {row['POINT_X']}" if pd.notna(row['POINT_X']) and pd.notna(row['POINT_Y']) else "",
                                axis=1
                            )

                        # Exibir tabela
                        st.write(f"### 📋 Dados encontrados: {len(df_final)} registros")
                        pd.set_option("styler.render.max_elements", 3000000)
                        st.dataframe(df_final.style.format(precision=2))

                        # Mapa com Folium
                        st.write("### 🗺️ Mapa com Coordenadas dos Clientes")
                        if "POINT_X" in df_final.columns and "POINT_Y" in df_final.columns:
                            df_mapa = df_final.dropna(subset=["POINT_X", "POINT_Y", "DEM_CONT"])
                            if not df_mapa.empty:
                                mapa = folium.Map(location=[df_mapa["POINT_Y"].mean(), df_mapa["POINT_X"].mean()], zoom_start=10)
                                for _, row in df_mapa.iterrows():
                                    folium.Marker(
                                        location=[row["POINT_Y"], row["POINT_X"]],
                                        popup=str(row["DEM_CONT"]),
                                        tooltip=str(row["DEM_CONT"])
                                    ).add_to(mapa)
                                folium_static(mapa)
                            else:
                                st.warning("⚠️ Nenhum dado com coordenadas válidas para plotar no mapa.")
                        else:
                            st.error("⚠️ As colunas POINT_X e/ou POINT_Y não estão presentes nos dados retornados.")

                        # Preparar dados para exportação
                        colunas_numericas_completas = [
                            "LIV", "DEM_CONT", "CAR_INST", "DEM_01", "DEM_02", "DEM_03", "DEM_04", "DEM_05", "DEM_06",
                            "DEM_07", "DEM_08", "DEM_09", "DEM_10", "DEM_11", "DEM_12", "ENE_01", "ENE_02", "ENE_03",
                            "ENE_04", "ENE_05", "ENE_06", "ENE_07", "ENE_08", "ENE_09", "ENE_10", "ENE_11", "ENE_12",
                            "DIC_01", "DIC_02", "FIC_01", "FIC_02"
                        ]
                        df_export = df_final.copy()
                        colunas_existentes = [col for col in colunas_numericas_completas if col in df_export.columns]
                        for coluna in colunas_existentes:
                            df_export[coluna] = pd.to_numeric(df_export[coluna], errors="coerce")

                        if "POINT_X" in df_export.columns and "POINT_Y" in df_export.columns:
                            df_export = ordenar_por_proximidade(df_export, x_col="POINT_X", y_col="POINT_Y")
                            st.write("📌 Dados ordenados por proximidade geográfica.")

                        # Botão para baixar CSV
                        csv = df_export.to_csv(index=False).encode("utf-8")
                        st.download_button("📥 Baixar Dados em CSV", data=csv, file_name="dados_combinados.csv", mime="text/csv")

                        # Botão para baixar XLSX
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                            df_export.to_excel(writer, index=False, sheet_name='Dados')
                        excel_data = output.getvalue()
                        st.download_button(
                            label="📥 Baixar Dados em XLSX",
                            data=excel_data,
                            file_name="dados_combinados.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                        # Botão para baixar KML
                        if "POINT_X" in df_export.columns and "POINT_Y" in df_export.columns:
                            def create_kml(df):
                                kml = simplekml.Kml()
                                for _, row in df.iterrows():
                                    if pd.notna(row["POINT_X"]) and pd.notna(row["POINT_Y"]):
                                        pnt = kml.newpoint(
                                            name=str(row.get("DEM_CONT", "Ponto")),
                                            coords=[(row["POINT_X"], row["POINT_Y"])]
                                        )
                                        pnt.description = f"Nome_UF: {row.get('Nome_UF', 'N/A')}\n" \
                                                        f"Nome_Município: {row.get('Nome_Município', 'N/A')}\n" \
                                                        f"CLAS_SUB: {row.get('CLAS_SUB', 'N/A')}\n" \
                                                        f"GRU_TAR: {row.get('GRU_TAR', 'N/A')}"
                                return kml

                            kml_obj = create_kml(df_export)
                            kml_str = kml_obj.kml()
                            st.download_button(
                                label="📥 Baixar Dados em KML",
                                data=kml_str.encode("utf-8"),
                                file_name="dados_combinados.kml",
                                mime="application/vnd.google-earth.kml+xml"
                            )
                        else:
                            st.warning("⚠️ Não é possível gerar KML: colunas POINT_X e/ou POINT_Y ausentes.")
            else:
                st.warning("⚠️ Nenhum dado retornado para os municípios selecionados.")

st.markdown("---")
st.markdown("🔗 **Fonte dos dados:** [ANEEL - Dados Abertos](https://dadosabertos.aneel.gov.br)")

