import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# 1. ACESSO SEGURO
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

# Regra de Status
def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

try:
    # Abre a planilha
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    
    # FORÇA A LEITURA COMO LISTA PURA (Resolve o erro 200)
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Mapeia as colunas
    cols_map = {col: i + 1 for i, col in enumerate(df.columns)}

    if aba == "📊 Quadro Geral":
        st.header(f"Base de Dados: {disc}")
        # Mostra a tabela mesmo com linhas vazias
        st.dataframe(df, use_container_width=True)

    elif aba == "📝 Lançar Individual":
        st.header("Atualização por TAG")
        # Filtra apenas linhas onde a TAG não é vazia
        tags = df[df['TAG'] != ""]['TAG'].unique()
        tag_alvo = st.selectbox("TAG:", tags)
        
        row_idx = df.index[df['TAG'] == tag_alvo][0]
        dados = df.iloc[row_idx]
        real_row = row_idx + 2

        with st.form("edit_form"):
            c1, c2, c3, c4 = st.columns(4)
            d_i = c1.text_input("DATA INIC PROG", value=str(dados.get('DATA INIC PROG', '')))
            d_f = c2.text_input("DATA FIM PROG", value=str(dados.get('DATA FIM PROG', '')))
            d_p = c3.text_input("PREVISTO", value=str(dados.get('PREVISTO', '')))
            d_m = c4.text_input("DATA MONT", value=str(dados.get('DATA MONT', '')))
            
            if st.form_submit_button("SALVAR"):
                n_status = calcular_status(d_i, d_m)
                # Lista de colunas para atualizar
                para_atualizar = {
                    'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 
                    'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': n_status
                }
                for col, val in para_atualizar.items():
                    if col in cols_map:
                        ws.update_cell(real_row, cols_map[col], val)
                st.success(f"Atualizado! Status: {n_status}")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.header("Importação Excel")
        file = st.file_uploader("Arquivo .xlsx", type="xlsx")
        if file:
            df_up = pd.read_excel(file).astype(str).replace('nan', '')
            if st.button("PROCESSAR"):
                for _, row in df_up.iterrows():
                    try:
                        m_idx = df.index[df['TAG'] == str(row['TAG'])][0] + 2
                        n_stat = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                        for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                            if c in df_up.columns and c in cols_map:
                                ws.update_cell(m_idx, cols_map[c], str(row[c]))
                        ws.update_cell(m_idx, cols_map['STATUS'], n_stat)
                    except: continue
                st.success("Carga finalizada!")
                st.rerun()

except Exception as e:
    st.error(f"Erro de Conexão: {e}")
