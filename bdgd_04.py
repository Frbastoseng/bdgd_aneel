import streamlit as st
import pandas as pd
import requests
import os
from streamlit_folium import folium_static
import folium
import io
import numpy as np
import simplekml
from datetime import datetime

# ==========================
# Configuração da página
# ==========================
st.set_page_config(
    page_title="Consulta Nome_UF e Nome_Município - ANEEL",
    page_icon="🔌",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://dadosabertos.aneel.gov.br/",
        "About": "App para consulta cruzada entre base municipal/IBGE e base ANEEL. Carrega ANEEL sob demanda."
    }
)

# ==========================
# Constantes
# ==========================
API_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
RESOURCE_ID = "f6671cba-f269-42ef-8eb3-62cb3bfa0b98"
LOCAL_DATA_FILE = "dados_aneel.parquet"  # cache local
PLANILHA_PADRAO = "RELATORIO_DTB_BRASIL_DISTRITO.xls"
LOTE = 32000

# ==========================
# Estado da sessão
# ==========================
if "df_dados" not in st.session_state:
    st.session_state.df_dados = pd.DataFrame()
if "df_planilha" not in st.session_state:
    st.session_state.df_planilha = pd.DataFrame()
if "last_update" not in st.session_state:
    st.session_state.last_update = None

# ==========================
# Título / Header
# ==========================
left, mid, right = st.columns([0.7, 0.15, 0.15])
with left:
    st.markdown("""
    # 🔍 Consulta por Nome_UF e Nome_Município — **ANEEL**
    **Workflow:** por padrão usamos o **cache local**. Se quiser forçar atualização da ANEEL, clique no botão na barra lateral.
    """)
with mid:
    st.metric("Origem de dados", "Local (cache)" if os.path.exists(LOCAL_DATA_FILE) else "Sem cache")
with right:
    mtime = os.path.getmtime(LOCAL_DATA_FILE) if os.path.exists(LOCAL_DATA_FILE) else None
    st.metric(
        "Cache atualizado",
        datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M") if mtime else "—"
    )

# ==========================
# Utilitários
# ==========================
@st.cache_data(show_spinner=False)
def carregar_dados_locais(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_parquet(path)
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def baixar_dados_aneel(api_url: str, resource_id: str, lote: int = 32000) -> pd.DataFrame:
    try:
        r0 = requests.get(api_url, params={"resource_id": resource_id, "limit": 1}, timeout=60)
        r0.raise_for_status()
        total = r0.json()["result"]["total"]
    except Exception as e:
        st.error(f"Erro ao consultar total de registros: {e}")
        return pd.DataFrame()

    dados, offset, baixados = [], 0, 0
    progress = st.progress(0)
    with st.spinner(f"Baixando {total} registros em lotes de {lote}..."):
        while offset < total:
            try:
                params = {"resource_id": resource_id, "limit": lote, "offset": offset}
                rx = requests.get(api_url, params=params, timeout=120)
                rx.raise_for_status()
                recs = rx.json().get("result", {}).get("records", [])
                if not recs:
                    st.warning(f"Nenhum dado retornado no offset {offset}. Interrompendo download.")
                    break
                dados.extend(recs)
                baixados += len(recs)
                offset += lote
                progress.progress(min(baixados/total, 1.0))
            except Exception as e:
                st.error(f"Erro no lote offset {offset}: {e}")
                break
    df = pd.DataFrame(dados)
    if len(df) < total:
        st.warning(f"Atenção: esperados {total}, baixados {len(df)} registros.")
    try:
        df.to_parquet(LOCAL_DATA_FILE, index=False)
        st.success(f"✅ Dados ANEEL salvos localmente ({len(df)} registros).")
    except Exception as e:
        st.error(f"Erro ao salvar cache local: {e}")
    return df

# Ordenação geográfica simples (vizinho mais próximo)
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
        u = ordem[-1]
        up = coords[u]
        dmin, prox = float("inf"), None
        for i in range(n):
            if i not in usados:
                p = coords[i]
                d = np.sqrt((up[0] - p[0])**2 + (up[1] - p[1])**2)
                if d < dmin:
                    dmin, prox = d, i
        if prox is not None:
            ordem.append(prox)
            usados.add(prox)
    df_valid = df_valid.iloc[ordem].reset_index(drop=True)
    df_invalid = df[df[x_col].isna() | df[y_col].isna()]
    return pd.concat([df_valid, df_invalid], ignore_index=True)

# ==========================
# Sidebar — Controles principais
# ==========================
st.sidebar.header("⚙️ Controles")

# Status do cache local
if os.path.exists(LOCAL_DATA_FILE):
    st.sidebar.success("Usando **dados locais** como padrão.")
else:
    st.sidebar.warning("Cache local **não encontrado**. Carregue a planilha e/ou atualize a ANEEL.")

# Botão de atualização manual — ANEEL
if st.sidebar.button("🔄 Atualizar dados da ANEEL (sob demanda)"):
    st.session_state.df_dados = baixar_dados_aneel(API_URL, RESOURCE_ID, LOTE)
    st.session_state.last_update = datetime.now().strftime("%d/%m/%Y %H:%M")

# Carregar cache local **sem** baixar automaticamente
if st.session_state.df_dados.empty:
    st.session_state.df_dados = carregar_dados_locais(LOCAL_DATA_FILE)

# Upload/Carregamento da planilha IBGE
st.sidebar.header("📂 Planilha IBGE/Municipal")
up = st.sidebar.file_uploader("Enviar planilha (xls/xlsx)", type=["xls", "xlsx"], help="Se não enviar, tentaremos abrir o arquivo padrão local.")

@st.cache_data(show_spinner=False)
def carregar_planilha(arquivo):
    try:
        df = pd.read_excel(arquivo, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame()

if up is not None:
    st.session_state.df_planilha = carregar_planilha(up)
else:
    if os.path.exists(PLANILHA_PADRAO) and st.session_state.df_planilha.empty:
        st.session_state.df_planilha = carregar_planilha(PLANILHA_PADRAO)

# Validar planilha
colunas_necessarias = ["Nome_UF", "Nome_Município", "Código Município Completo", "Nome_Microrregião", "Nome_Mesorregião"]
missing = [c for c in colunas_necessarias if c not in st.session_state.df_planilha.columns]
if st.session_state.df_planilha.empty or missing:
    st.sidebar.error(
        "Planilha não carregada ou com colunas ausentes: " + (", ".join(missing) if missing else "Arquivo inválido.")
    )
else:
    st.sidebar.success(f"Planilha carregada: {len(st.session_state.df_planilha)} linhas")

# ==========================
# Filtros — Sidebar (Básico + Avançado)
# ==========================
st.sidebar.header("🧭 Filtros de Localização")
df_plan = st.session_state.df_planilha
ufs = sorted(df_plan.get("Nome_UF", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
uf = st.sidebar.selectbox("Nome_UF", [""] + ufs)

if uf:
    mun_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Município"].dropna().unique().tolist())
    micro_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Microrregião"].dropna().unique().tolist())
    meso_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Mesorregião"].dropna().unique().tolist())
else:
    mun_disp = sorted(df_plan.get("Nome_Município", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
    micro_disp = sorted(df_plan.get("Nome_Microrregião", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
    meso_disp = sorted(df_plan.get("Nome_Mesorregião", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []

muns = st.sidebar.multiselect("Nome_Município", mun_disp)
micros = st.sidebar.multiselect("Nome_Microrregião", micro_disp)
mesos = st.sidebar.multiselect("Nome_Mesorregião", meso_disp)

# Mapas de classificação
clas_sub_map = {
    "0": "Não informado", "RE1": "Residencial", "RE2": "Residencial baixa renda",
    "REBR": "Residencial baixa renda indígena", "REQU": "Residencial baixa renda quilombola",
    "REBP": "Baixa renda BPC", "REMU": "Baixa renda multifamiliar", "IN": "Industrial", "CO1": "Comercial",
    "CO2": "Transporte (exceto tração)", "CO3": "Telecom", "CO4": "Filantrópicas", "CO5": "Templos",
    "CO6": "Administração condominial", "CO7": "Iluminação rodovias", "CO8": "Semáforos e radares",
    "CO9": "Outros serviços", "RU1": "Agropecuária rural", "RU1A": "Rural (poços)", "RU1B": "Rural (bombeamento)",
    "RU2": "Agropecuária urbana", "RU3": "Residencial rural", "RU4": "Cooperativa eletrificação rural",
    "RU5": "Agroindustrial", "RU6": "Irrigação rural", "RU7": "Escola agrotécnica", "RU8": "Aquicultura",
    "PP1": "Poder público fed.", "PP2": "Poder público est./dist.", "PP3": "Poder público mun.", "IP": "Iluminação pública",
    "SP1": "Tração elétrica", "SP2": "Água, esgoto e saneamento", "CPR": "Consumo próprio distribuidora", "CSPS": "Conc./Permiss."
}

# Opções dinâmicas (só se houver ANEEL carregado)
df_dados = st.session_state.df_dados
@st.cache_data(show_spinner=False)
def opcoes_gru_tar(df):
    return sorted(df["GRU_TAR"].dropna().unique().tolist()) if not df.empty and "GRU_TAR" in df.columns else []

st.sidebar.header("🔎 Filtros Avançados")
with st.sidebar.expander("Abrir filtros avançados", expanded=False):
    ceg_opts = ["Possui Solar", "Não possui Solar"]
    ceg_sel = st.multiselect("CEG_GD (usina solar)", ceg_opts)
    clas_opts = sorted(clas_sub_map.values())
    clas_sel = st.multiselect("CLAS_SUB (classe)", clas_opts)
    gru_sel = st.multiselect("GRU_TAR (grupo tarifário)", opcoes_gru_tar(df_dados))
    liv_sel = st.multiselect("LIV (tipo de consumidor)", ["Livre", "Cativo"])
    c1, c2 = st.columns(2)
    with c1:
        dem_oper = st.selectbox("DEM_CONT", ["Todos", "Maior que", "Menor que"])
        dem_val = st.number_input("Valor DEM_CONT", min_value=0.0, value=0.0, step=1.0)
    with c2:
        ene_oper = st.selectbox("ENE_MAX", ["Todos", "Maior que", "Menor que"]) 
        ene_val = st.number_input("Valor ENE_MAX (kWh)", min_value=0.0, value=0.0, step=1.0)

# ==========================
# Ação: Buscar/Processar
# ==========================
cta = st.sidebar.button("🚀 Buscar dados (planilha × ANEEL)", type="primary")

if cta:
    if df_plan.empty:
        st.error("Carregue a planilha IBGE/Municipal antes de buscar.")
    elif df_dados.empty:
        st.warning("Base ANEEL não carregada. Use o botão na barra lateral para atualizar/baixar.")
    else:
        with st.spinner("Processando filtros e cruzando bases..."):
            df_fil = df_plan.copy()
            if uf:
                df_fil = df_fil[df_fil["Nome_UF"] == uf]
            if muns:
                df_fil = df_fil[df_fil["Nome_Município"].isin(muns)]
            if micros:
                df_fil = df_fil[df_fil["Nome_Microrregião"].isin(micros)]
            if mesos:
                df_fil = df_fil[df_fil["Nome_Mesorregião"].isin(mesos)]

            cods = df_fil["Código Município Completo"].dropna().astype(str).unique().tolist()
            if not cods:
                st.warning("Nenhum município encontrado após filtros.")
            else:
                dfa = df_dados.copy()
                if "MUN" in dfa.columns:
                    dfa["MUN"] = dfa["MUN"].astype(str)
                # conversões numéricas úteis
                num_cols = [
                    "LIV","DEM_CONT","DEM_01","DEM_02","DEM_03","ENE_01","ENE_02","POINT_X","POINT_Y",
                    "DIC_01","DIC_02","FIC_01","FIC_02"
                ]
                for c in [c for c in num_cols if c in dfa.columns]:
                    dfa[c] = pd.to_numeric(dfa[c], errors="coerce")

                df_final = dfa[dfa["MUN"].isin(cods)].merge(
                    df_fil[["Código Município Completo","Nome_UF","Nome_Município"]].astype({"Código Município Completo":"str"}),
                    left_on="MUN", right_on="Código Município Completo", how="inner"
                ).drop(columns=["Código Município Completo"], errors="ignore")

                if df_final.empty:
                    st.error("Nenhum dado após o merge. Verifique as bases.")
                else:
                    # Mapear CLAS_SUB
                    if "CLAS_SUB" in df_final.columns:
                        df_final["CLAS_SUB"] = df_final["CLAS_SUB"].map(clas_sub_map).fillna(df_final["CLAS_SUB"])

                    # ENE_MAX
                    ene_cols = [f"ENE_{str(i).zfill(2)}" for i in range(1,13) if f"ENE_{str(i).zfill(2)}" in df_final.columns]
                    for c in ene_cols:
                        df_final[c] = pd.to_numeric(df_final[c], errors="coerce")
                    if ene_cols:
                        df_final["ENE_MAX"] = df_final[ene_cols].max(axis=1)

                    # Filtros avançados
                    if ceg_sel:
                        mask = pd.Series(False, index=df_final.index)
                        if "Possui Solar" in ceg_sel:
                            mask |= df_final.get("CEG_GD").notna() & (df_final.get("CEG_GD") != "")
                        if "Não possui Solar" in ceg_sel:
                            mask |= df_final.get("CEG_GD").isna() | (df_final.get("CEG_GD") == "")
                        df_final = df_final[mask]

                    if clas_sel and "CLAS_SUB" in df_final.columns:
                        df_final = df_final[df_final["CLAS_SUB"].isin(clas_sel)]

                    if gru_sel and "GRU_TAR" in df_final.columns:
                        df_final = df_final[df_final["GRU_TAR"].isin(gru_sel)]

                    if liv_sel and "LIV" in df_final.columns:
                        df_final["LIV"] = pd.to_numeric(df_final["LIV"], errors="coerce")
                        liv_vals = [1 if x == "Livre" else 0 for x in liv_sel]
                        df_final = df_final[df_final["LIV"].isin(liv_vals)]

                    if dem_oper != "Todos" and "DEM_CONT" in df_final.columns:
                        df_final["DEM_CONT"] = pd.to_numeric(df_final["DEM_CONT"], errors="coerce")
                        if dem_oper == "Maior que":
                            df_final = df_final[df_final["DEM_CONT"] > dem_val]
                        elif dem_oper == "Menor que":
                            df_final = df_final[df_final["DEM_CONT"] < dem_val]

                    if ene_oper != "Todos" and "ENE_MAX" in df_final.columns:
                        if ene_oper == "Maior que":
                            df_final = df_final[df_final["ENE_MAX"] > ene_val]
                        elif ene_oper == "Menor que":
                            df_final = df_final[df_final["ENE_MAX"] < ene_val]

                    if df_final.empty:
                        st.warning("Nenhum dado após aplicar filtros.")
                    else:
                        # Coordenadas formatadas
                        if {"POINT_X","POINT_Y"}.issubset(df_final.columns):
                            df_final["Coordenadas"] = df_final.apply(
                                lambda r: f"{r['POINT_Y']}, {r['POINT_X']}" if pd.notna(r['POINT_X']) and pd.notna(r['POINT_Y']) else "",
                                axis=1
                            )

                        # KPIs
                        k1,k2,k3 = st.columns(3)
                        with k1:
                            st.metric("Registros filtrados", f"{len(df_final):,}".replace(",","."))
                        with k2:
                            st.metric("Municípios únicos", df_final["MUN"].nunique() if "MUN" in df_final.columns else "—")
                        with k3:
                            st.metric("Com coordenadas", df_final.dropna(subset=["POINT_X","POINT_Y"]).shape[0] if {"POINT_X","POINT_Y"}.issubset(df_final.columns) else 0)

                        # Abas: Tabela | Mapa | Exportar
                        tab1, tab2, tab3 = st.tabs(["📋 Tabela", "🗺️ Mapa", "⬇️ Exportar"])

                        with tab1:
                            st.dataframe(df_final, use_container_width=True)

                        with tab2:
                            if {"POINT_X","POINT_Y"}.issubset(df_final.columns):
                                df_map = df_final.dropna(subset=["POINT_X","POINT_Y"]).copy()
                                if not df_map.empty:
                                    m = folium.Map(location=[df_map["POINT_Y"].mean(), df_map["POINT_X"].mean()], zoom_start=8)
                                    for _, row in df_map.iterrows():
                                        popup = folium.Popup(html=f"<b>{row.get('Nome_Município','')}</b><br>DEM_CONT: {row.get('DEM_CONT','')}", max_width=300)
                                        folium.CircleMarker(location=[row["POINT_Y"], row["POINT_X"]], radius=5, popup=popup, tooltip=str(row.get("DEM_CONT",""))).add_to(m)
                                    folium_static(m, width=1200, height=600)
                                else:
                                    st.info("Sem coordenadas válidas para plotagem.")
                            else:
                                st.info("Colunas POINT_X/POINT_Y não disponíveis no resultado.")

                        with tab3:
                            df_exp = df_final.copy()
                            # Ordenação opcional por proximidade
                            if {"POINT_X","POINT_Y"}.issubset(df_exp.columns) and st.checkbox("Ordenar por proximidade geográfica", value=False):
                                df_exp = ordenar_por_proximidade(df_exp)
                                st.toast("Dados ordenados por proximidade.")

                            # CSV
                            st.download_button(
                                "Baixar CSV",
                                data=df_exp.to_csv(index=False).encode("utf-8"),
                                file_name="dados_combinados.csv",
                                mime="text/csv"
                            )

                            # XLSX
                            out = io.BytesIO()
                            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                                df_exp.to_excel(writer, index=False, sheet_name='Dados')
                            st.download_button(
                                "Baixar XLSX",
                                data=out.getvalue(),
                                file_name="dados_combinados.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

                            # KML
                            if {"POINT_X","POINT_Y"}.issubset(df_exp.columns):
                                def to_kml(dfk):
                                    kml = simplekml.Kml()
                                    for _, r in dfk.iterrows():
                                        if pd.notna(r["POINT_X"]) and pd.notna(r["POINT_Y"]):
                                            p = kml.newpoint(name=str(r.get("DEM_CONT","Ponto")), coords=[(r["POINT_X"], r["POINT_Y"])])
                                            p.description = (
                                                f"Nome_UF: {r.get('Nome_UF','N/A')}\n"
                                                f"Nome_Município: {r.get('Nome_Município','N/A')}\n"
                                                f"CLAS_SUB: {r.get('CLAS_SUB','N/A')}\n"
                                                f"GRU_TAR: {r.get('GRU_TAR','N/A')}"
                                            )
                                    return kml.kml()
                                st.download_button(
                                    "Baixar KML",
                                    data=to_kml(df_exp).encode("utf-8"),
                                    file_name="dados_combinados.kml",
                                    mime="application/vnd.google-earth.kml+xml"
                                )

# Rodapé
st.markdown("---")
st.caption("Fonte: ANEEL – Dados Abertos | Este app usa cache local e só atualiza a ANEEL quando solicitado.")


