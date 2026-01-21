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
    # Seleciona a planilha correta no Drive
    nome_planilha = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_planilha)
    ws = sh.get_worksheet(0)
    
    # FORMA ROBUSTA DE LER OS DADOS (Evita Erro 200)
    lista_de_dados = ws.get_all_values()
    
    if len(lista_de_dados) > 1:
        # Transforma em tabela usando a primeira linha como cabeçalho
        df = pd.DataFrame(lista_de_dados[1:], columns=lista_de_dados[0])
        cols = {col: i + 1 for i, col in enumerate(lista_de_dados[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização por TAG - {disc}")
            tag_selecionada = st.selectbox("Selecione o TAG:", df['TAG'].unique())
            linha_df = df[df['TAG'] == tag_selecionada].iloc[0]
            idx_planilha = df.index[df['TAG'] == tag_selecionada][0] + 2
            
            with st.form("f_ind"):
                c1, c2, c3 = st.columns(3)
                d_i = c1.text_input("DATA INIC PROG", value=str(linha_df.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(linha_df.get('DATA FIM PROG', '')))
                d_m = c3.text_input("DATA MONT", value=str(linha_df.get('DATA MONT', '')))
                stat = st.selectbox("STATUS:", ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"])
                
                if st.form_submit_button("SALVAR"):
                    ws.update_cell(idx_planilha, cols['DATA INIC PROG'], d_i)
                    ws.update_cell(idx_planilha, cols['DATA FIM PROG'], d_f)
                    ws.update_cell(idx_planilha, cols['DATA MONT'], d_m)
                    ws.update_cell(idx_planilha, cols['STATUS'], stat)
                    st.success("Atualizado!")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header(f"Importação em Massa - {disc}")
            file = st.file_uploader("Suba o arquivo Excel", type="xlsx")
            if file:
                df_up = pd.read_excel(file).astype(str)
                if st.button("🚀 PROCESSAR"):
                    for _, row in df_up.iterrows():
                        try:
                            m_idx = df.index[df['TAG'] == row['TAG']][0] + 2
                            ws.update_cell(m_idx, cols['DATA INIC PROG'], row['DATA INIC PROG'])
                            ws.update_cell(m_idx, cols['DATA FIM PROG'], row['DATA FIM PROG'])
                            ws.update_cell(m_idx, cols['DATA MONT'], row['DATA MONT'])
                            ws.update_cell(m_idx, cols['STATUS'], row['STATUS'])
                        except: continue
                    st.success("Concluído!")
                    st.rerun()
    else:
        st.error("A planilha está vazia ou sem cabeçalhos!")

except Exception as e:
    st.error(f"Erro crítico: {e}")
