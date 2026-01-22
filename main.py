import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

@st.cache_resource
def conectar_google():
    try:
        # Puxa os dados brutos
        info = dict(st.secrets["gcp_service_account"])
        
        # --- LIMPEZA RADICAL DA CHAVE ---
        raw_key = info["private_key"]
        
        # Extrai apenas o que está entre o BEGIN e o END
        if "-----BEGIN PRIVATE KEY-----" in raw_key:
            header = "-----BEGIN PRIVATE KEY-----"
            footer = "-----END PRIVATE KEY-----"
            # Pega o miolo da chave e remove espaços, quebras de linha e lixo
            content = raw_key.split(header)[1].split(footer)[0]
            content = re.sub(r'\s+', '', content) # Remove TUDO que não for caractere
            
            # Reconstrói a chave no formato padrão que o Google exige
            info["private_key"] = f"{header}\n{content}\n{footer}\n"
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

client = conectar_google()

# --- REGRAS DE STATUS ---
def calcular_status(d_i, d_m):
    d_m_s = str(d_m).strip().lower()
    d_i_s = str(d_i).strip().lower()
    if d_m_s not in ["", "nan", "none", "-", "0"]: return "MONTADO"
    if d_i_s not in ["", "nan", "none", "-", "0"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- INTERFACE ---
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Edição Individual", "📤 Carga em Massa"])

try:
    sh = client.open("BD_ELE" if disc == "ELÉTRICA" else "BD_INST")
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    if len(data) > 0:
        df = pd.DataFrame(data[1:], columns=data[0])
        cols = {col: i + 1 for i, col in enumerate(data[0])}

        if aba == "📊 Quadro Geral":
            st.dataframe(df, use_container_width=True)
        elif aba == "📝 Edição Individual":
            tag_sel = st.selectbox("TAG:", sorted(df['TAG'].unique()))
            idx = df.index[df['TAG'] == tag_sel][0]
            row = df.iloc[idx]
            with st.form("edit"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
                d_m = c4.text_input("DATA MONT", row.get('DATA MONT', ''))
                if st.form_submit_button("SALVAR"):
                    st_at = calcular_status(d_i, d_m)
                    ws.update_cell(idx + 2, cols['STATUS'], st_at)
                    st.success("Salvo!")
                    st.rerun()
except Exception as e:
    st.error(f"Erro no Google Sheets: {e}")
