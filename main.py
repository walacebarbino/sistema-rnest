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
            df.columns = df.columns.str.strip()
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE STATUS ---
def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", "", "nat", "null"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- BARRA LATERAL ---
col_side1, col_side2, col_side3 = st.sidebar.columns([1, 3, 1])
with col_side2:
    st.image("LOGO2.png", width=120)
st.sidebar.divider()
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Edição por TAG - {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG:", lista_tags)
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        def converter_para_data(texto):
            try: return datetime.strptime(texto, "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            st.markdown(f"#### Editando: **{tag_sel}**")
            
            # AS 4 COLUNAS ENFILEIRADAS COM O MESMO TAMANHO
            c1, c2, c3, c4 = st.columns(4)
            
            v_ini = c1.date_input("Início Prog", value=converter_para_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=converter_para_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c3.date_input("Montagem", value=converter_para_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            # Status Curto e Alinhado
            status_visual = calcular_status_tag(v_ini, v_fim, v_mont)
            c4.markdown("**Status:**")
            if status_visual == "MONTADO":
                c4.success(status_visual)
            elif status_visual == "PROGRAMADO":
                c4.warning(status_visual)
            else:
                c4.info(status_visual)
            
            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                novo_status = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                campos = {'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': novo_status, 'OBS': v_obs}
                
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                
                st.success(f"TAG {tag_sel} atualizada!")
                st.rerun()
        
        st.divider()
        st.dataframe(df_atual, use_container_width=True, hide_index=True)
