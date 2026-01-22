import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import re

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

@st.cache_resource
def conectar_google():
    try:
        # Busca os segredos
        s_info = dict(st.secrets["gcp_service_account"])
        
        # --- LIMPEZA DA CHAVE (CORREÇÃO PARA O ERRO DE 65 CARACTERES) ---
        key = s_info["private_key"]
        
        # 1. Remove espaços em branco no início e fim
        key = key.strip()
        
        # 2. Se a chave foi colada com \n literais, converte para quebras reais
        key = key.replace("\\n", "\n")
        
        # 3. Remove espaços duplos ou caracteres invisíveis que quebram o Base64
        # Garante que as linhas da chave não tenham espaços vazios nelas
        lines = [line.strip() for line in key.split('\n')]
        key = '\n'.join(lines)
        
        s_info["private_key"] = key
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(s_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação (Verifique os Secrets): {e}")
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
        cols_map = {col: i + 1 for i, col in enumerate(data[0])}

        if aba == "📊 Quadro Geral":
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Edição Individual":
            st.header(f"Lançamento Individual - {disc}")
            tag_list = sorted([t for t in df['TAG'].unique() if t.strip() != ""])
            tag_sel = st.selectbox("Selecione o TAG:", tag_list)
            
            idx = df.index[df['TAG'] == tag_sel][0]
            row_data = df.iloc[idx]

            with st.form("form_edit"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(row_data.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(row_data.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(row_data.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(row_data.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    st_novo = calcular_status(d_i, d_m)
                    for k, v in {'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': st_novo}.items():
                        if k in cols_map:
                            ws.update_cell(idx + 2, cols_map[k], str(v))
                    st.success("Dados salvos!")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header("Importação Excel")
            file = st.file_uploader("Arquivo .xlsx", type="xlsx")
            if file and st.button("PROCESSAR"):
                df_up = pd.read_excel(file).astype(str).replace('nan', '')
                for _, r in df_up.iterrows():
                    t_up = str(r['TAG']).strip()
                    if t_up in df['TAG'].values:
                        idx_g = df.index[df['TAG'] == t_up][0] + 2
                        s = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                        for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                            if c in cols_map: ws.update_cell(idx_g, cols_map[c], str(r.get(c, '')))
                        if 'STATUS' in cols_map: ws.update_cell(idx_g, cols_map['STATUS'], s)
                st.success("Carga realizada!")
                st.rerun()
except Exception as e:
    st.error(f"Erro: {e}")
