import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        s_info = dict(st.secrets["gcp_service_account"])
        
        # CORREÇÃO DEFINITIVA PARA PADDING E BASE64
        key = s_info["private_key"].replace("\\n", "\n")
        s_info["private_key"] = key
        
        creds = Credentials.from_service_account_info(s_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação (Verifique os Secrets): {e}")
        st.stop()

client = conectar_google()

# --- REGRAS DE STATUS AUTOMÁTICA ---
def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

# --- INTERFACE ---
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

try:
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    valores = ws.get_all_values()
    
    if len(valores) > 0:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização Individual - {disc}")
            tags = [t for t in df['TAG'].unique() if t.strip() != ""]
            tag_sel = st.selectbox("Selecione o TAG:", tags)
            idx_df = df.index[df['TAG'] == tag_sel][0]
            dados_atuais = df.iloc[idx_df]

            with st.form("form_edit"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados_atuais.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados_atuais.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados_atuais.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados_atuais.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    n_status = calcular_status(d_i, d_m)
                    campos = {'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': n_status}
                    for col_nome, valor in campos.items():
                        if col_nome in cols_map:
                            ws.update_cell(idx_df + 2, cols_map[col_nome], str(valor))
                    st.success(f"TAG {tag_sel} atualizado com sucesso!")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header("Importar Excel")
            arq = st.file_uploader("Suba o arquivo .xlsx", type="xlsx")
            if arq and st.button("🚀 PROCESSAR"):
                df_up = pd.read_excel(arq).astype(str).replace('nan', '')
                for _, row in df_up.iterrows():
                    tag_up = str(row['TAG']).strip()
                    if tag_up in df['TAG'].values:
                        idx_g = df.index[df['TAG'] == tag_up][0] + 2
                        n_stat = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                        for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                            if c in cols_map: ws.update_cell(idx_g, cols_map[c], str(row.get(c, '')))
                        if 'STATUS' in cols_map: ws.update_cell(idx_g, cols_map['STATUS'], n_stat)
                st.success("Carga processada!")
                st.rerun()
except Exception as e:
    st.error(f"Erro: {e}")
