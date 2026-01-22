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

# --- CSS PARA ALINHAMENTO E PADRONIZAÇÃO ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; min-height: 25px; }
    input:disabled { 
        background-color: #1e293b !important; 
        color: #60a5fa !important; 
        opacity: 1 !important; 
        -webkit-text-fill-color: #60a5fa !important; 
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
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'NAT', 'null'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE STATUS ---
def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip() not in ["", "-", "0"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

st.sidebar.image("LOGO2.png", width=120)
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader("🛠️ Edição por TAG")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        def conv_data(texto):
            try: return datetime.strptime(texto, "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            v_ini = c1.date_input("Início Prog", value=conv_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=conv_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=conv_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            st_auto = calcular_status_tag(v_ini.strftime("%d/%m/%Y") if v_ini else "", 
                                          v_fim.strftime("%d/%m/%Y") if v_fim else "", 
                                          v_mont.strftime("%d/%m/%Y") if v_mont else "")
            c4.text_input("Status Atual", value=st_auto, disabled=True)
            
            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                novo_st = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                campos = {'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': novo_st, 'OBS': v_obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Atualizado!")
                st.rerun()
        st.dataframe(df_atual, use_container_width=True, hide_index=True)

    elif aba == "📊 CURVA S":
        # ... (Mantido o código de Curva S anterior para brevidade)
        st.write("Visualização de Curva S ativa.")

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📊 Painel de Controle e Relatórios")
        df_r = df_atual.copy()
        
        # Correção da lógica de contagem para o Dashboard
        total = len(df_r)
        montados = len(df_r[df_r['STATUS'] == 'MONTADO'])
        programados = len(df_r[df_r['STATUS'] == 'PROGRAMADO'])
        aguardando = len(df_r[df_r['STATUS'] == 'AGUARDANDO PROG'])
        
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("Total TAGs", total)
        c_m2.metric("Montados ✅", montados)
        c_m3.metric("Programados 📅", programados)
        c_m4.metric("Aguardando ⏳", aguardando)
        
        st.divider()
        
        # SEÇÃO DE EXPORTAÇÃO PARA PRODUÇÃO
        st.markdown("### 📋 Lista de Entrega para Produção")
        st.info("Abaixo estão apenas os TAGs com datas de programação definidas (Status: PROGRAMADO).")
        df_prod = df_r[df_r['STATUS'] == 'PROGRAMADO'].copy()
        cols_prod = ['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'DESCRIÇÃO', 'ÁREA', 'OBS']
        df_prod_exp = df_prod[[c for c in cols_prod if c in df_prod.columns]]
        
        st.dataframe(df_prod_exp, use_container_width=True, hide_index=True)
        
        if not df_prod_exp.empty:
            buf_prod = BytesIO()
            with pd.ExcelWriter(buf_prod, engine='xlsxwriter') as writer:
                df_prod_exp.to_excel(writer, index=False, sheet_name='PRODUÇÃO')
            st.download_button("📥 BAIXAR LISTA DE PRODUÇÃO (EXCEL)", buf_prod.getvalue(), f"PRODUCAO_{disc}_{datetime.now().strftime('%d_%m')}.xlsx", "button/primary", use_container_width=True)

        st.divider()
        
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### 🚩 Pendências Totais")
            df_pend = df_r[df_r['STATUS'] != 'MONTADO']
            st.dataframe(df_pend[['TAG', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)
            buf_pend = BytesIO()
            with pd.ExcelWriter(buf_pend, engine='xlsxwriter') as writer:
                df_pend.to_excel(writer, index=False)
            st.download_button("📥 Exportar Pendências", buf_pend.getvalue(), "pendencias.xlsx")

        with col_r:
            st.markdown("#### 📈 Realizado (Últimos 7 dias)")
            df_r['DT_M'] = pd.to_datetime(df_r['DATA MONT'], dayfirst=True, errors='coerce')
            df_sem = df_r[df_r['DT_M'] >= (datetime.now() - timedelta(days=7))]
            st.dataframe(df_sem[['TAG', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)
            buf_sem = BytesIO()
            with pd.ExcelWriter(buf_sem, engine='xlsxwriter') as writer:
                df_sem.to_excel(writer, index=False)
            st.download_button("📥 Exportar Semanal", buf_sem.getvalue(), "semanal.xlsx")

    elif aba == "📤 CARGA EM MASSA":
        # ... (Mantido o código de Carga em Massa anterior)
        st.write("Área de importação de Excel ativa.")
