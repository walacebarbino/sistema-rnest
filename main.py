import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- 1. CONFIGURAÇÃO DE ACESSO ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

# Função de Regra de Status
def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() != "" and str(d_m).lower() != 'nan':
        return "MONTADO"
    elif d_i and str(d_i).strip() != "" and str(d_i).lower() != 'nan':
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

try:
    nome_planilha = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_planilha)
    ws = sh.get_worksheet(0)
    
    # PEGA OS DADOS (Evita o erro <Response [200]>)
    dados_brutos = ws.get_all_values()
    
    if len(dados_brutos) > 0:
        # Transforma em DataFrame usando a primeira linha como cabeçalho
        df = pd.DataFrame(dados_brutos[1:], columns=dados_brutos[0])
        cols_map = {col: i + 1 for i, col in enumerate(dados_brutos[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Quadro Geral: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização Manual - {disc}")
            tag_alvo = st.selectbox("Selecione o TAG:", df['TAG'].unique())
            dados_tag = df[df['TAG'] == tag_alvo].iloc[0]
            idx_plan = df.index[df['TAG'] == tag_alvo][0] + 2
            
            with st.form("f_ind"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados_tag.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados_tag.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados_tag.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados_tag.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    n_status = calcular_status(d_i, d_m)
                    # Atualiza as colunas de dados e o status automático
                    colunas_alvo = ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT', 'STATUS']
                    valores_alvo = [d_i, d_f, d_p, d_m, n_status]
                    
                    for col, val in zip(colunas_alvo, valores_alvo):
                        if col in cols_map:
                            ws.update_cell(idx_plan, cols_map[col], val)
                            
                    st.success(f"TAG {tag_alvo} salvo! Novo Status: {n_status}")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header(f"Carga via Excel - {disc}")
            file = st.file_uploader("Suba o arquivo .xlsx", type="xlsx")
            if file:
                df_up = pd.read_excel(file).astype(str).replace('nan', '')
                if st.button("🚀 PROCESSAR"):
                    for _, row in df_up.iterrows():
                        try:
                            m_idx = df.index[df['TAG'] == str(row['TAG'])][0] + 2
                            n_stat = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                            for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                                if c in df_up.columns and c in cols_map:
                                    ws.update_cell(m_idx, cols_map[c], str(row[c]))
                            if 'STATUS' in cols_map:
                                ws.update_cell(m_idx, cols_map['STATUS'], n_stat)
                        except: continue
                    st.success("Carga finalizada!")
                    st.rerun()
    else:
        st.warning("Planilha sem dados ou sem cabeçalho.")
except Exception as e:
    st.error(f"Erro: {e}")
