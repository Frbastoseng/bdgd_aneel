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

# Inicializa o dataframe vazio (será preenchido apenas se houver dados locais ou o usuário clicar no botão)
df_dados = pd.DataFrame()

# Função para baixar 100% dos dados da ANEEL
@st.cache_data
def baixar_dados_aneel():
    try:
        response = requests.get(API_URL, params={"resource_id": RESOURCE_ID, "limit": 1}, timeout=60)
        response.raise_for_status()
        total_registros = response.json()["result"]["total"]
        st.write(f"📱 Total de registros reportados pela API: {total_registros}")
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
                st.write(f"📅 Baixados {total_baixado}/{total_registros} registros...")
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
        st.warning("Dados locais não encontrados. Clique no botão para fazer o primeiro download.")
        return pd.DataFrame()

# Botão para atualizar os dados manualmente
if st.button("🔄 Atualizar Dados da ANEEL"):
    with st.spinner("Atualizando dados da ANEEL..."):
        df_dados = baixar_dados_aneel()
        if not df_dados.empty:
            st.success(f"Dados atualizados com sucesso! Total de registros: {len(df_dados)}")
else:
    df_dados = carregar_dados_locais()

# Mensagem se nada foi carregado
if df_dados.empty:
    st.error("⚠️ Nenhum dado disponível. Verifique a conexão ou clique em 'Atualizar Dados da ANEEL'.")
else:
    st.write(f"📊 Total de registros carregados: {len(df_dados)}")
