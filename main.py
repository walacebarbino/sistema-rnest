import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")

# --- AJUSTE DE ALINHAMENTO VIA CSS (FORÇA O NIVELAMENTO) ---
st.markdown("""
    <style>
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }
    .stDateInput label, .stMarkdown p {
        min-height: 25px;
        margin-bottom: 5px !important;
    }
    div[data-testid="stNotification"] {
        padding: 10px !important;
        margin-top: 0px !important;
        height: 45px;
        display: flex;
        align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try: st.image("LOGO2.png", width=200) 
        except: st.header("G-MONT")
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR"):
            if pin == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()

if not st.session_state['logado']:
    tela_login()

# --- CONEXÃO E DADOS ---
@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except: return None

client = conectar_google()

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip()
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", "", "nat"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- INTERFACE LATERAL ---
st.sidebar.image("LOGO2.png", width=120)
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Edição por TAG - {disc}")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        def conv_data(texto):
            try: return datetime.strptime(texto, "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            st.markdown(f"**TAG: {tag_sel}**")
            
            # CRIANDO AS 4 COLUNAS EXATAMENTE IGUAIS
            c1, c2, c3, c4 = st.columns(4)
            
            v_ini = c1.date_input("Início Prog", value=conv_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=conv_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=conv_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            # Status Alinhado
            st_val = calcular_status_tag(v_ini, v_fim, v_mont)
            c4.markdown("**Status da TAG**") # Label para alinhar com os outros
            if st_val == "MONTADO": c4.success(st_val)
            elif st_val == "PROGRAMADO": c4.warning(st_val)
            else: c4.info(st_val)
            
            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                n_st = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                campos = {'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': n_st, 'OBS': v_obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Salvo!")
                st.rerun()
        
        st.divider()
        st.dataframe(df_atual, use_container_width=True, hide_index=True)
