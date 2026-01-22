import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONEXÃO ---
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Ajuste manual da key para evitar erro de base64
    s_info = dict(st.secrets["gcp_service_account"])
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

def calcular_status(d_i, d_m):
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    else:
        return "AGUARDANDO PROG"

try:
    sh = client.open("BD_ELE" if disc == "ELÉTRICA" else "BD_INST")
    ws = sh.get_worksheet(0)
    # get_all_values resolve o erro <Response [200]> com células vazias
    data = ws.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    cols_map = {col: i + 1 for i, col in enumerate(data[0])}

    if aba == "📊 Quadro Geral":
        st.header(f"Base de Dados: {disc}")
        st.dataframe(df, use_container_width=True)

    elif aba == "📝 Lançar Individual":
        st.header(f"Atualização Manual - {disc}")
        tags = [t for t in df['TAG'].unique() if t.strip() != ""]
        tag_sel = st.selectbox("TAG:", tags)
        idx = df.index[df['TAG'] == tag_sel][0]
        row_data = df.iloc[idx]
        
        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            d_i = c1.text_input("DATA INIC PROG", value=str(row_data.get('DATA INIC PROG', '')))
            d_f = c2.text_input("DATA FIM PROG", value=str(row_data.get('DATA FIM PROG', '')))
            d_p = c3.text_input("PREVISTO", value=str(row_data.get('PREVISTO', '')))
            d_m = c4.text_input("DATA MONT", value=str(row_data.get('DATA MONT', '')))
            
            if st.form_submit_button("SALVAR"):
                n_status = calcular_status(d_i, d_m)
                updates = {
                    'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 
                    'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': n_status
                }
                for col, val in updates.items():
                    if col in cols_map:
                        ws.update_cell(idx + 2, cols_map[col], str(val))
                st.success(f"TAG {tag_sel} atualizado! Status: {n_status}")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.header("Carga via Excel")
        file = st.file_uploader("Suba o arquivo .xlsx", type="xlsx")
        if file and st.button("PROCESSAR"):
            df_up = pd.read_excel(file).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                tag_up = str(r['TAG']).strip()
                if tag_up in df['TAG'].values:
                    idx_g = df.index[df['TAG'] == tag_up][0] + 2
                    n_st = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                    for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                        if c in cols_map:
                            ws.update_cell(idx_g, cols_map[c], str(r.get(c, '')))
                    if 'STATUS' in cols_map:
                        ws.update_cell(idx_g, cols_map['STATUS'], n_st)
            st.success("Carga finalizada!")
            st.rerun()

except Exception as e:
    st.error(f"Erro no sistema: {e}")
