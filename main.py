import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONEXÃO COM GOOGLE SHEETS ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    s_info = dict(st.secrets["gcp_service_account"])
    # Corrige quebras de linha da chave
    s_info["private_key"] = s_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(s_info, scopes=scope)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"Erro na Autenticação (Verifique os Secrets): {e}")
    st.stop()

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

# --- REGRA DE STATUS AUTOMÁTICA ---
def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

try:
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    
    # get_all_values() evita o erro 200
    valores = ws.get_all_values()
    
    if len(valores) > 0:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Edição Individual - {disc}")
            tags_v = [t for t in df['TAG'].unique() if t.strip() != ""]
            tag_sel = st.selectbox("Selecione o TAG:", tags_v)
            
            idx_df = df.index[df['TAG'] == tag_sel][0]
            dados = df.iloc[idx_df]
            linha_g = idx_df + 2 

            with st.form("form_ind"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    n_status = calcular_status(d_i, d_m)
                    campos = {'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': n_status}
                    for col_n, val in campos.items():
                        if col_n in cols_map:
                            ws.update_cell(linha_g, cols_map[col_n], str(val))
                    st.success(f"Salvo! Novo Status: {n_status}")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header("Carga via Excel")
            arq = st.file_uploader("Suba o arquivo .xlsx", type="xlsx")
            if arq:
                df_up = pd.read_excel(arq).astype(str).replace('nan', '')
                if st.button("🚀 PROCESSAR"):
                    for _, row in df_up.iterrows():
                        t_up = str(row['TAG']).strip()
                        if t_up in df['TAG'].values:
                            idx_g = df.index[df['TAG'] == t_up][0] + 2
                            st_at = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                            for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                                if c in df_up.columns and c in cols_map:
                                    ws.update_cell(idx_g, cols_map[c], str(row[c]))
                            if 'STATUS' in cols_map:
                                ws.update_cell(idx_g, cols_map['STATUS'], st_at)
                    st.success("Carga finalizada!")
                    st.rerun()
    else:
        st.warning("Planilha vazia.")
except Exception as e:
    st.error(f"Erro no processamento: {e}")
