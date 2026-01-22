import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json

# --- 1. CONEXÃO (DEFINIDA NO TOPO) ---
@st.cache_resource
def conectar_google():
    try:
        # Puxa o blocão de texto do Base64 e decodifica
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

# --- 2. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
client = conectar_google()

def calcular_status(d_i, d_m):
    d_m_s = str(d_m).strip().lower()
    d_i_s = str(d_i).strip().lower()
    if d_m_s not in ["", "nan", "none", "-", "0"]: return "MONTADO"
    if d_i_s not in ["", "nan", "none", "-", "0"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- 3. SIDEBAR ---
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Edição Individual", "📤 Carga em Massa"])

try:
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    cols = {col: i + 1 for i, col in enumerate(data[0])}

    if aba == "📊 Quadro Geral":
        st.header(f"Base: {disc}")
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
                if 'STATUS' in cols: ws.update_cell(idx + 2, cols['STATUS'], st_at)
                if 'DATA INIC PROG' in cols: ws.update_cell(idx + 2, cols['DATA INIC PROG'], d_i)
                if 'DATA MONT' in cols: ws.update_cell(idx + 2, cols['DATA MONT'], d_m)
                st.success("Dados salvos com sucesso!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        f = st.file_uploader("Subir Excel (.xlsx)", type="xlsx")
        if f and st.button("PROCESSAR"):
            df_up = pd.read_excel(f).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df['TAG'].values:
                    i_g = df.index[df['TAG'] == r['TAG']][0] + 2
                    st_n = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                    for c in ['DATA INIC PROG', 'DATA MONT']:
                        if c in cols: ws.update_cell(i_g, cols[c], str(r.get(c, '')))
                    if 'STATUS' in cols: ws.update_cell(i_g, cols['STATUS'], st_n)
            st.success("Importação concluída!")
            st.rerun()

except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
