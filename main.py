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

# Função para aplicar a regra de status automaticamente
def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() != "":
        return "MONTADO"
    elif d_i and str(d_i).strip() != "":
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

try:
    nome_planilha = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_planilha)
    ws = sh.get_worksheet(0)
    
    # LER DADOS (Nova técnica para matar o erro <Response [200]>)
    valores = ws.get_all_values()
    
    if len(valores) > 0:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização Manual - {disc}")
            tag_alvo = st.selectbox("TAG:", df['TAG'].unique())
            dados_tag = df[df['TAG'] == tag_alvo].iloc[0]
            idx_plan = df.index[df['TAG'] == tag_alvo][0] + 2
            
            with st.form("f_ind"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados_tag.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados_tag.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados_tag.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados_tag.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    novo_status = calcular_status(d_i, d_m)
                    # Atualiza as 5 colunas principais
                    ws.update_cell(idx_plan, cols_map['DATA INIC PROG'], d_i)
                    ws.update_cell(idx_plan, cols_map['DATA FIM PROG'], d_f)
                    ws.update_cell(idx_plan, cols_map['PREVISTO'], d_p)
                    ws.update_cell(idx_plan, cols_map['DATA MONT'], d_m)
                    ws.update_cell(idx_plan, cols_map['STATUS'], novo_status)
                    st.success(f"TAG {tag_alvo} atualizado! Status: {novo_status}")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header(f"Importação Excel - {disc}")
            file = st.file_uploader("Arquivo .xlsx", type="xlsx")
            if file:
                df_up = pd.read_excel(file).astype(str).replace('nan', '')
                if st.button("🚀 PROCESSAR"):
                    for _, row in df_up.iterrows():
                        try:
                            m_idx = df.index[df['TAG'] == str(row['TAG'])][0] + 2
                            stat = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                            
                            # Atualização dinâmica baseada no que tem no Excel
                            for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                                if c in df_up.columns:
                                    ws.update_cell(m_idx, cols_map[c], str(row[c]))
                            ws.update_cell(m_idx, cols_map['STATUS'], stat)
                        except: continue
                    st.success("Carga finalizada!")
                    st.rerun()
    else:
        st.error("Planilha sem dados.")

except Exception as e:
    st.error(f"Erro: {e}")
