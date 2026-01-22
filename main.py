import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

@st.cache_resource
def conectar():
    try:
        info = dict(st.secrets["gcp_service_account"])
        # Limpeza agressiva: remove quebras reais e substitui os \n de texto por quebras reais
        clean_key = info["private_key"].replace("\\n", "\n").replace("\r", "").strip()
        info["private_key"] = clean_key
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return gspread.authorize(Credentials.from_service_account_info(info, scopes=scope))
    except Exception as e:
        st.error(f"Erro de Autenticação: {e}")
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
            tag_sel = st.selectbox("TAG:", sorted(df['TAG'].unique()))
            idx = df.index[df['TAG'] == tag_sel][0]
            row = df.iloc[idx]
            with st.form("edit"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
                d_f = c2.text_input("DATA FIM PROG", row.get('DATA FIM PROG', ''))
                d_p = c3.text_input("PREVISTO", row.get('PREVISTO', ''))
                d_m = c4.text_input("DATA MONT", row.get('DATA MONT', ''))
                if st.form_submit_button("SALVAR"):
                    st_at = calcular_status(d_i, d_m)
                    for k, v in {'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': st_at}.items():
                        if k in cols: ws.update_cell(idx + 2, cols[k], str(v))
                    st.success("Salvo!")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            f = st.file_uploader("Excel", type="xlsx")
            if f and st.button("PROCESSAR"):
                df_up = pd.read_excel(f).astype(str).replace('nan', '')
                for _, r in df_up.iterrows():
                    if r['TAG'] in df['TAG'].values:
                        idx_g = df.index[df['TAG'] == r['TAG']][0] + 2
                        s = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                        for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                            if c in cols: ws.update_cell(idx_g, cols[c], str(r.get(c, '')))
                        if 'STATUS' in cols: ws.update_cell(idx_g, cols['STATUS'], s)
                st.success("Carga OK!")
                st.rerun()
except Exception as e:
    st.error(f"Erro: {e}")
