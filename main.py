import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# 1. Configuração de Acesso Seguro (Secrets)
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# 2. Abrir a Planilha (Certifique-se que o nome no Drive é BD_RNEST)
sh = client.open("BD_RNEST")

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

ws = sh.worksheet("ELE") if disc == "ELÉTRICA" else sh.worksheet("INST")
df = pd.DataFrame(ws.get_all_records())

if aba == "📊 Quadro Geral":
    st.header(f"Base de Dados: {disc}")
    st.dataframe(df, use_container_width=True)

elif aba == "📝 Lançar Individual":
    st.header("Atualização por TAG")
    tag = st.selectbox("Selecione o TAG:", df['TAG'].unique())
    idx = df.index[df['TAG'] == tag][0] + 2
    
    with st.form("f_ind"):
        c1, c2, c3 = st.columns(3)
        d_i = c1.text_input("DATA INIC PROG", value=str(df.at[idx-2, 'DATA INIC PROG']))
        d_f = c2.text_input("DATA FIM PROG", value=str(df.at[idx-2, 'DATA FIM PROG']))
        d_m = c3.text_input("DATA MONT", value=str(df.at[idx-2, 'DATA MONT']))
        stat = st.selectbox("STATUS:", ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"])
        
        if st.form_submit_button("SALVAR"):
            ws.update(f"C{idx}:F{idx}", [[d_i, d_f, d_m, stat]])
            st.success(f"TAG {tag} atualizado!")

elif aba == "📤 Carga em Massa":
    st.header("Importação em Massa")
    st.info("O Excel deve ter as colunas: TAG, DATA INIC PROG, DATA FIM PROG, DATA MONT, STATUS")
    file = st.file_uploader("Suba o arquivo Excel", type="xlsx")
    if file:
        df_up = pd.read_excel(file)
        if st.button("🚀 PROCESSAR CARGA"):
            for i, row in df_up.iterrows():
                try:
                    match_idx = df.index[df['TAG'] == row['TAG']][0] + 2
                    ws.update(f"C{match_idx}:F{match_idx}", [[str(row.get('DATA INIC PROG','')), str(row.get('DATA FIM PROG','')), str(row.get('DATA MONT','')), row.get('STATUS','')]])
                except: continue
            st.success("Carga em massa finalizada!")
