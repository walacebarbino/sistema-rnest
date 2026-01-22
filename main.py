import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- 1. CONEXÃO (TOPO DO ARQUIVO) ---
@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
client = conectar_google()

# --- 2. FUNÇÕES DE DADOS ---
def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0]), ws
        return pd.DataFrame(), None
    except Exception:
        return pd.DataFrame(), None

def calcular_status(d_i, d_m):
    if str(d_m).strip() not in ["", "nan", "None", "-"]: return "MONTADO"
    if str(d_i).strip() not in ["", "nan", "None", "-"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- 3. DASHBOARD (CAIXAS SEPARADAS) ---
st.title("🚀 GESTÃO DE AVANÇO RNEST")

df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

col1, col2 = st.columns(2)

def mostrar_card(df, titulo):
    if not df.empty and 'STATUS' in df.columns:
        total = len(df)
        montados = len(df[df['STATUS'].str.upper() == 'MONTADO'])
        prog = (montados / total) * 100 if total > 0 else 0
        st.metric(titulo, f"{prog:.1f}%", f"{montados} de {total} concluídos")
        st.progress(prog/100)
    else:
        st.metric(titulo, "0%", "Sem conexão")

with col1:
    st.info("⚡ ELÉTRICA")
    mostrar_card(df_ele, "Avanço Elétrica")

with col2:
    st.success("🔬 INSTRUMENTAÇÃO")
    mostrar_card(df_ins, "Avanço Instrumentação")

st.divider()

# --- 4. NAVEGAÇÃO ---
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral e Curva S", "📝 Edição Individual", "📤 Carga em Massa"])

df_f = df_ele if disc == "ELÉTRICA" else df_ins
ws_f = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_f.empty:
    if aba == "📊 Quadro Geral e Curva S":
        c_t, c_g = st.columns(2)
        with c_t: st.dataframe(df_f)
        with c_g:
            if 'DATA MONT' in df_f.columns:
                df_c = df_f.copy()
                df_c['DATA MONT'] = pd.to_datetime(df_c['DATA MONT'], errors='coerce')
                df_c = df_c.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                if not df_c.empty:
                    df_c['Progresso'] = range(1, len(df_c) + 1)
                    st.plotly_chart(px.line(df_c, x='DATA MONT', y='Progresso', title="Curva de Avanço"))

    elif aba == "📤 Carga em Massa":
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as w:
            pd.DataFrame(columns=['TAG', 'DATA INIC PROG', 'DATA MONT']).to_excel(w, index=False)
        st.download_button("📥 BAIXAR MODELO EXCEL", buffer.getvalue(), "modelo.xlsx")
