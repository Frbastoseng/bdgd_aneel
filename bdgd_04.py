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
    initial_sidebar_state="collapsed",  # começa recolhida no mobile
    menu_items={
        "Get Help": "https://dadosabertos.aneel.gov.br/",
        "About": "App para consulta cruzada entre base municipal/IBGE e base ANEEL. Carrega ANEEL sob demanda."
    }
)

# ==========================
# CSS — Mobile-first (app-like)
# ==========================
st.markdown("""
<style>
/* Some defaults */
.block-container { padding-top: 4.5rem; padding-bottom: 5rem; }

/* App bar fixo no topo */
.appbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  height: 56px; display: flex; align-items: center; gap: 8px;
  padding: 0 16px; background: #0e1117; color: #fff; border-bottom: 1px solid #232730;
}
.appbar h1 { font-size: 1.05rem; margin: 0; font-weight: 600; }
.appbar .pill { background:#1f6feb; color:#fff; padding:6px 10px; border-radius:999px; font-size:.8rem; }
.appbar .meta { margin-left:auto; font-size:.8rem; opacity:.85 }

/* Barra de ações no rodapé para mobile */
@media (max-width: 768px) {
  .block-container { padding-bottom: 6.5rem; }
  .actionbar {
    position: fixed; bottom: 0; left: 0; right: 0; z-index: 9999;
    background: #0e1117; border-top: 1px solid #232730; padding: 8px 12px;
  }
  .actionbar .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
}
/* Componentes mais "clicáveis" no mobile */
.stButton>button, .stDownloadButton>button, .stTextInput>div>div>input,
.stSelectbox, .stMultiSelect, .stNumberInput>div>div>input {
  min-height: 44px;
}
.stButton>button { width: 100%; font-weight: 600; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stDataFrame { border-radius: 12px; overflow: hidden; }

/* Esconde menu/hamburger e footer do Streamlit para aspecto de app */
header[data-testid="stHeader"] { visibility: hidden; height: 0; }
footer { visibility: hidden; height: 0; }
</style>
""", unsafe_allow_html=True)

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
# App Bar (topo fixo)
# ==========================
mtime = os.path.getmtime(LOCAL_DATA_FILE) if os.path.exists(LOCAL_DATA_FILE) else None
st.markdown(f"""
<div class="appbar">
  <span>🔌</span>
  <h1>Consulta ANEEL — Municípios</h1>
  <span class="pill">{'Local (cache)' if os.path.exists(LOCAL_DATA_FILE) else 'Sem cache'}</span>
  <div class="meta">{datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M") if mtime else '—'}</div>
</div>
""", unsafe_allow_html=True)

# ==========================
# Utilitários
# ==========================
@st.cache_data(show_spinner=False)
def carregar_dados_locais(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
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
# Sidebar — Controles principais (em expanders p/ mobile)
# ==========================
with st.sidebar:
    st.header("⚙️ Controles")
    if os.path.exists(LOCAL_DATA_FILE):
        st.success("Usando **dados locais** como padrão.")
    else:
        st.warning("Cache local **não encontrado**. Carregue a planilha e/ou atualize a ANEEL.")

    if st.button("🔄 Atualizar dados da ANEEL (sob demanda)", use_container_width=True, type="primary"):
        st.session_state.df_dados = baixar_dados_aneel(API_URL, RESOURCE_ID, LOTE)
        st.session_state.last_update = datetime.now().strftime("%d/%m/%Y %H:%M")

    st.header("📂 Planilha IBGE/Municipal")
    with st.expander("Enviar planilha (xls/xlsx)"):
        up = st.file_uploader("Selecionar arquivo", type=["xls", "xlsx"], label_visibility="collapsed",
                              help="Se não enviar, tentaremos abrir o arquivo padrão local.")

@st.cache_data(show_spinner=False)
def carregar_planilha(arquivo):
    try:
        df = pd.read_excel(arquivo, dtype=str)
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame()

if "up" not in locals():
    up = None

if up is not None:
    st.session_state.df_planilha = carregar_planilha(up)
else:
    if os.path.exists(PLANILHA_PADRAO) and st.session_state.df_planilha.empty:
        st.session_state.df_planilha = carregar_planilha(PLANILHA_PADRAO)

colunas_necessarias = ["Nome_UF", "Nome_Município", "Código Município Completo", "Nome_Microrregião", "Nome_Mesorregião"]
missing = [c for c in colunas_necessarias if c not in st.session_state.df_planilha.columns]
if st.session_state.df_planilha.empty or missing:
    st.sidebar.error("Planilha não carregada ou com colunas ausentes: " + (", ".join(missing) if missing else "Arquivo inválido."))
else:
    st.sidebar.success(f"Planilha carregada: {len(st.session_state.df_planilha):,}".replace(",", "."))

# ==========================
# Filtros — Mobile-first
# ==========================
st.markdown("### 🔎 Filtros")
df_plan = st.session_state.df_planilha

with st.expander("Localização (UF, Município, Micro/Meso)", expanded=False):
    ufs = sorted(df_plan.get("Nome_UF", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
    uf = st.selectbox("UF", [""] + ufs, index=0)
    if uf:
        mun_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Município"].dropna().unique().tolist())
        micro_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Microrregião"].dropna().unique().tolist())
        meso_disp = sorted(df_plan[df_plan["Nome_UF"] == uf]["Nome_Mesorregião"].dropna().unique().tolist())
    else:
        mun_disp = sorted(df_plan.get("Nome_Município", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
        micro_disp = sorted(df_plan.get("Nome_Microrregião", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []
        meso_disp = sorted(df_plan.get("Nome_Mesorregião", pd.Series(dtype=str)).dropna().unique().tolist()) if not df_plan.empty else []

    muns = st.multiselect("Município", mun_disp)
    micros = st.multiselect("Microrregião", micro_disp)
    mesos = st.multiselect("Mesorregião", meso_disp)

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

df_dados = st.session_state.df_dados

@st.cache_data(show_spinner=False)
def opcoes_gru_tar(df):
    return sorted(df["GRU_TAR"].dropna().unique().tolist()) if not df.empty and "GRU_TAR" in df.columns else []

with st.expander("Filtros avançados (opcionais)", expanded=False):
    ceg_sel = st.multiselect("CEG_GD (usina solar)", ["Possui Solar", "Não possui Solar"])
    clas_sel = st.multiselect("CLAS_SUB (classe)", sorted(clas_sub_map.values()))
    gru_sel = st.multiselect("GRU_TAR (grupo tarifário)", opcoes_gru_tar(df_dados))
    liv_sel = st.multiselect("LIV (tipo de consumidor)", ["Livre", "Cativo"])
    c1, c2 = st.columns(2)
    with c1:
        dem_oper = st.selectbox("DEM_CONT", ["Todos", "Maior que", "Menor que"])
        dem_val = st.number_input("Valor DEM_CONT", min_value=0.0, value=0.0, step=1.0)
    with c2:
        ene_oper = st.selectbox("ENE_MAX", ["Todos", "Maior que", "Menor que"]) 
        ene_val = st.number_input("Valor ENE_MAX (kWh)", min_value=0.0, value=0.0, step=1.0)

# Botões principais (também aparecem no rodapé no mobile)
col_btn = st.columns([1,1,1])
with col_btn[0]:
    btn_atualizar = st.button("🔄 Atualizar ANEEL", use_container_width=True)
with col_btn[1]:
    btn_buscar = st.button("🚀 Buscar dados", type="primary", use_container_width=True)
with col_btn[2]:
    st.write("")  # espaço

if btn_atualizar:
    st.session_state.df_dados = baixar_dados_aneel(API_URL, RESOURCE_ID, LOTE)
    st.session_state.last_update = datetime.now().strftime("%d/%m/%Y %H:%M")

# Carregar cache local **sem** baixar automaticamente
if st.session_state.df_dados.empty:
    st.session_state.df_dados = carregar_dados_locais(LOCAL_DATA_FILE)

# ==========================
# Execução da busca
# ==========================
cta = btn_buscar  # unifica com o botão do rodapé

if cta:
    if df_plan.empty:
        st.error("Carregue a planilha IBGE/Municipal antes de buscar.")
    elif st.session_state.df_dados.empty:
        st.warning("Base ANEEL não carregada. Use o botão para atualizar/baixar.")
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
                dfa = st.session_state.df_dados.copy()
                if "MUN" in dfa.columns:
                    dfa["MUN"] = dfa["MUN"].astype(str)

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
                    if "CLAS_SUB" in df_final.columns:
                        df_final["CLAS_SUB"] = df_final["CLAS_SUB"].map(clas_sub_map).fillna(df_final["CLAS_SUB"])

                    ene_cols = [f"ENE_{str(i).zfill(2)}" for i in range(1,13) if f"ENE_{str(i).zfill(2)}" in df_final.columns]
                    for c in ene_cols:
                        df_final[c] = pd.to_numeric(df_final[c], errors="coerce")
                    if ene_cols:
                        df_final["ENE_MAX"] = df_final[ene_cols].max(axis=1)

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
                        if {"POINT_X","POINT_Y"}.issubset(df_final.columns):
                            df_final["Coordenadas"] = df_final.apply(
                                lambda r: f"{r['POINT_Y']}, {r['POINT_X']}" if pd.notna(r['POINT_X']) and pd.notna(r['POINT_Y']) else "",
                                axis=1
                            )

                        # KPIs — em cards simples (boa leitura no mobile)
                        k1,k2,k3 = st.columns(3)
                        with k1:
                            st.metric("Registros filtrados", f"{len(df_final):,}".replace(",",".")) 
                        with k2:
                            st.metric("Municípios únicos", df_final["MUN"].nunique() if "MUN" in df_final.columns else "—")
                        with k3:
                            st.metric("Com coordenadas", df_final.dropna(subset=["POINT_X","POINT_Y"]).shape[0] if {"POINT_X","POINT_Y"}.issubset(df_final.columns) else 0)

                        # Abas
                        tab1, tab2, tab3 = st.tabs(["📋 Tabela", "🗺️ Mapa", "⬇️ Exportar"])

                        with tab1:
                            st.dataframe(df_final, use_container_width=True, hide_index=True)

                        with tab2:
                            if {"POINT_X","POINT_Y"}.issubset(df_final.columns):
                                df_map = df_final.dropna(subset=["POINT_X","POINT_Y"]).copy()
                                if not df_map.empty:
                                    # Centro do mapa
                                    m = folium.Map(location=[df_map["POINT_Y"].mean(), df_map["POINT_X"].mean()], zoom_start=7, control_scale=True)
                                    for _, row in df_map.iterrows():
                                        lat, lon = float(row["POINT_Y"]), float(row["POINT_X"])
                                        nome = row.get("Nome_Município","")
                                        dem  = row.get("DEM_CONT","")
                                        gmaps_url = f"https://www.google.com/maps?q={lat},{lon}"
                                        popup_html = f"""
                                        <b>{nome}</b><br>
                                        DEM_CONT: {dem}<br>
                                        <a href="{gmaps_url}" target="_blank">Abrir no Google Maps</a>
                                        """
                                        folium.CircleMarker(
                                            location=[lat, lon], radius=5,
                                            popup=folium.Popup(popup_html, max_width=320),
                                            tooltip=str(dem)
                                        ).add_to(m)
                                    # Tenta ocupar a largura total no mobile
                                    folium_static(m, width=None, height=450)
                                else:
                                    st.info("Sem coordenadas válidas para plotagem.")
                            else:
                                st.info("Colunas POINT_X/POINT_Y não disponíveis no resultado.")

                        with tab3:
                            df_exp = df_final.copy()
                            if {"POINT_X","POINT_Y"}.issubset(df_exp.columns) and st.checkbox("Ordenar por proximidade geográfica", value=False):
                                df_exp = ordenar_por_proximidade(df_exp)
                                st.toast("Dados ordenados por proximidade.")

                            st.download_button(
                                "Baixar CSV",
                                data=df_exp.to_csv(index=False).encode("utf-8"),
                                file_name="dados_combinados.csv",
                                mime="text/csv",
                                use_container_width=True
                            )

                            out = io.BytesIO()
                            with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
                                df_exp.to_excel(writer, index=False, sheet_name='Dados')
                            st.download_button(
                                "Baixar XLSX",
                                data=out.getvalue(),
                                file_name="dados_combinados.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )

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
                                    mime="application/vnd.google-earth.kml+xml",
                                    use_container_width=True
                                )

# ==========================
# Barra de ações fixa (somente no mobile)
# ==========================
st.markdown("""
<div class="actionbar">
  <div class="grid">
    <form action="#" method="post">
      <input type="hidden" name="__streamlit__" value="true"/>
    </form>
  </div>
</div>
""", unsafe_allow_html=True)

# Rodapé
st.markdown("---")
st.caption("Fonte: ANEEL – Dados Abertos | Cache local; atualização apenas sob demanda. Otimizado para uso no celular.")




