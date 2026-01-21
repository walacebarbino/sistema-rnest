import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# 1. Configuração de Acesso Seguro
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

try:
    sh = client.open("BD_ELE") if disc == "ELÉTRICA" else client.open("BD_INST")
    ws = sh.get_worksheet(0)
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])

    # Identifica a posição das colunas dinamicamente
    cols = {col: i + 1 for i, col in enumerate(data[0])}

    if aba == "📊 Quadro Geral":
        st.header(f"Base de Dados: {disc}")
        st.dataframe(df, use_container_width=True)

    elif aba == "📝 Lançar Individual":
        st.header(f"Atualização por TAG - {disc}")
        tag = st.selectbox("Selecione o TAG:", df['TAG'].unique())
        idx = df.index[df['TAG'] == tag][0] + 2
        
        with st.form("f_ind"):
            c1, c2, c3 = st.columns(3)
            d_i = c1.text_input("DATA INIC PROG", value=df.loc[df['TAG'] == tag, 'DATA INIC PROG'].values[0])
            d_f = c2.text_input("DATA FIM PROG", value=df.loc[df['TAG'] == tag, 'DATA FIM PROG'].values[0])
            d_m = c3.text_input("DATA MONT", value=df.loc[df['TAG'] == tag, 'DATA MONT'].values[0])
            stat = st.selectbox("STATUS:", ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"])
            
            if st.form_submit_button("SALVAR"):
                # Atualiza cada coluna na posição correta, independente de onde ela esteja
                ws.update_cell(idx, cols['DATA INIC PROG'], d_i)
                ws.update_cell(idx, cols['DATA FIM PROG'], d_f)
                ws.update_cell(idx, cols['DATA MONT'], d_m)
                ws.update_cell(idx, cols['STATUS'], stat)
                st.success(f"TAG {tag} atualizado!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.header(f"Importação em Massa - {disc}")
        file = st.file_uploader("Suba o Excel (.xlsx)", type="xlsx")
        if file:
            df_up = pd.read_excel(file)
            if st.button("🚀 PROCESSAR CARGA"):
                for i, row in df_up.iterrows():
                    try:
                        m_idx = df.index[df['TAG'] == row['TAG']][0] + 2
                        ws.update_cell(m_idx, cols['DATA INIC PROG'], str(row['DATA INIC PROG']))
                        ws.update_cell(m_idx, cols['DATA FIM PROG'], str(row['DATA FIM PROG']))
                        ws.update_cell(m_idx, cols['DATA MONT'], str(row['DATA MONT']))
                        ws.update_cell(m_idx, cols['STATUS'], str(row['STATUS']))
                    except: continue
                st.success("Carga finalizada!")
                st.rerun()

except Exception as e:
    st.error(f"Erro: {e}")
