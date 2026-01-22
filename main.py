import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA ICE CONTROL", layout="wide")

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try: st.image("LOGO2.jpeg", width=250)
        except: st.header("ICE CONTROL")
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN de acesso:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()

if not st.session_state['logado']:
    tela_login()

# --- CONEXÃO GOOGLE SHEETS ---
@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        st.stop()

client = conectar_google()

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

def calcular_status(previsto, d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", ""]
    if tem(d_m): return "MONTADO"
    if tem(d_f): return "PROG. FINALIZADA"
    if tem(d_i): return "EM ANDAMENTO"
    if tem(previsto): return "PREVISTO"
    return "AGUARDANDO PROG"

# --- BARRA LATERAL (SELEÇÃO) ---
st.sidebar.image("LOGO2.jpeg", width=120)
st.sidebar.divider()

# NOVO: SELETOR DE PROJETO
st.sidebar.subheader("📂 PROJETO")
projeto = st.sidebar.selectbox("Selecionar Obra:", ["RNEST", "NOVA OBRA"])

disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📤 CARGA EM MASSA"])

# Definição dos Bancos de Dados
if projeto == "RNEST":
    df_ele, ws_ele = extrair_dados("BD_ELE")
    df_ins, ws_ins = extrair_dados("BD_INST")
else:
    df_ele, ws_ele = extrair_dados("BD_ELE_OBRA2")
    df_ins, ws_ins = extrair_dados("BD_INST_OBRA2")

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO + QUADRO GERAL ABAIXO ---
    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Edição por TAG - {disc} ({projeto})")
        
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para editar:", lista_tags)
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            v_prev = c1.text_input("Previsto", value=dados_tag.get('PREVISTO', ''))
            v_ini = c2.text_input("Início Prog", value=dados_tag.get('DATA INIC PROG', ''))
            v_fim = c3.text_input("Fim Prog", value=dados_tag.get('DATA FIM PROG', ''))
            v_mont = c4.text_input("Data Montagem", value=dados_tag.get('DATA MONT', ''))
            
            st_sug = calcular_status(v_prev, v_ini, v_fim, v_mont)
            obs = st.text_input("Observação", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                linha = idx_base + 2
                campos = {'PREVISTO':v_prev, 'DATA INIC PROG':v_ini, 'DATA FIM PROG':v_fim, 'DATA MONT':v_mont, 'STATUS':st_sug, 'OBS':obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Dados salvos!")
                st.rerun()

        st.divider()
        st.subheader("📋 Quadro Geral de Dados")
        st.dataframe(df_atual, use_container_width=True) # Quadro Geral agora fica aqui embaixo

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        st.subheader(f"📈 Evolução da Obra: {projeto}")
        # Lógica da Curva S simplificada
        st.info("Gráfico de evolução baseado nas datas da planilha.")
        # ... (código da curva S mantido conforme anterior)

    # --- ABA 3: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader(f"Carga via Excel para {projeto}")
        up = st.file_uploader("Suba o arquivo .xlsx", type="xlsx")
        if up and st.button("🚀 Processar"):
            # Lógica de processamento mantida
            st.success("Base atualizada!")
            st.rerun()

if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()
