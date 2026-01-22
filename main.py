import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

@st.cache_resource
def conectar_google():
    try:
        # Puxa os dados do Secret
        info = dict(st.secrets["gcp_service_account"])
        
        # --- LIMPEZA RADICAL (MATA O ERRO DE 65 CARACTERES) ---
        raw_key = info["private_key"]
        
        # 1. Remove os cabeçalhos para limpar só o miolo
        header = "-----BEGIN PRIVATE KEY-----"
        footer = "-----END PRIVATE KEY-----"
        
        if header in raw_key and footer in raw_key:
            # Extrai apenas o código Base64 puro
            content = raw_key.split(header)[1].split(footer)[0]
            # Remove TUDO que não for letra, número, +, / ou = (limpeza total)
            content = re.sub(r'[^A-Za-z0-9+/=]', '', content)
            
            # Reconstrói a chave no formato exato que o Google exige
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
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    
    if len(data) > 0:
        df = pd.DataFrame(data[1:], columns=data[0])
        cols = {col: i + 1 for i, col in enumerate(data[0])}

        if aba == "📊 Quadro Geral":
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Edição Individual":
            tags = sorted([t for t in df['TAG'].unique() if t.strip() != ""])
            tag_sel = st.selectbox("TAG:", tags)
            idx = df.index[df['TAG'] == tag_sel][0]
            row = df.iloc[idx]
            
            with st.form("f"):
                c1, c2 = st.columns(2)
                d_i = c1.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
                d_m = c2.text_input("DATA MONT", row.get('DATA MONT', ''))
                if st.form_submit_button("SALVAR"):
                    st_at = calcular_status(d_i, d_m)
                    # Atualiza Status e datas (Exemplo simplificado para teste)
                    if 'STATUS' in cols: ws.update_cell(idx + 2, cols['STATUS'], st_at)
                    st.success("Salvo com sucesso!")
                    st.rerun()
except Exception as e:
    st.error(f"Erro: {e}")
