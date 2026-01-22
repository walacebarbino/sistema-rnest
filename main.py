import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONEXÃO ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Tenta ler a chave dos Secrets
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
    else:
        st.error("Chave 'gcp_service_account' não encontrada nos Secrets!")
        st.stop()
except Exception as e:
    st.error(f"Erro na autenticação: {e}")
    st.stop()

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual"])

def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() not in ["", "nan"]: return "MONTADO"
    if d_i and str(d_i).strip() not in ["", "nan"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

try:
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    
    # Busca dados evitando erro 200
    valores = ws.get_all_values()
    if len(valores) > 1:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        if aba == "📊 Quadro Geral":
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            tags = [t for t in df['TAG'].unique() if t.strip() != ""]
            tag_alvo = st.selectbox("TAG:", tags)
            idx_plan = df.index[df['TAG'] == tag_alvo][0] + 2
            dados = df[df['TAG'] == tag_alvo].iloc[0]
            
            with st.form("f"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    stat = calcular_status(d_i, d_m)
                    # Atualiza colunas principais
                    for col, val in zip(['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT', 'STATUS'], [d_i, d_f, d_p, d_m, stat]):
                        if col in cols_map:
                            ws.update_cell(idx_plan, cols_map[col], val)
                    st.success(f"Salvo! Status: {stat}")
                    st.rerun()
except Exception as e:
    st.error(f"Erro ao acessar planilha: {e}")
