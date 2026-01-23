import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta
import time

# --- CONFIGURAÇÃO E DATA BASE DA OBRA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
DATA_INICIO_OBRA = datetime(2025, 9, 29) 

# --- CSS PARA PADRONIZAÇÃO ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div, .stNumberInput div, .stSelectbox div { height: 45px !important; }
    div[data-testid="stForm"] > div { align-items: center; }
    input:disabled { background-color: #1e293b !important; color: #60a5fa !important; opacity: 1 !important; }
    [data-testid="stSidebar"] [data-testid="stImage"] { text-align: center; display: block; margin-left: auto; margin-right: auto; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.subheader("🔐 ACESSO RESTRITO G-MONT")
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()
if not st.session_state['logado']: tela_login()

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
        st.error(f"Erro na conexão: {e}"); st.stop()

client = conectar_google()

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip()
            cols_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']
            for c in cols_obj:
                if c not in df.columns: df[c] = ""
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- APOIO ---
def get_dates_from_week(week_number):
    if not str(week_number).isdigit(): return None, None
    monday = DATA_INICIO_OBRA + timedelta(weeks=(int(week_number) - 1))
    return monday.date(), (monday + timedelta(days=4)).date()

def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip() not in ["", "None", "nan", "-", "DD/MM/YYYY"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARGA ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- SIDEBAR E LOGO ---
try:
    st.sidebar.image("LOGO2.png", width=120)
except:
    try: st.sidebar.image("logo2.png", width=120)
    except: st.sidebar.markdown("### G-MONT")

disc = st.sidebar.selectbox("DISCIPLINA:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

cfg_rel = {
    "TAG": st.column_config.TextColumn(width="medium"),
    "DESCRIÇÃO": st.column_config.TextColumn(width="large"),
    "OBS": st.column_config.TextColumn(width="large"),
    "STATUS": st.column_config.TextColumn(width="medium"),
}

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição - {disc}")
        tag_sel = st.selectbox("TAG:", sorted(df_atual['TAG'].unique()))
        idx = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados = df_atual.iloc[idx]
        
        with st.form("form_edit"):
            c1, c2, c3 = st.columns(3)
            sem = c1.text_input("Semana:", value=dados['SEMANA OBRA'])
            obs = c2.text_input("OBS:", value=dados['OBS'])
            v_mont = c3.date_input("Montagem:", value=None, format="DD/MM/YYYY")
            if st.form_submit_button("💾 SALVAR"):
                ws_atual.update_cell(idx + 2, 2, sem) # Coluna B
                ws_atual.update_cell(idx + 2, 7, obs) # Coluna G
                if v_mont: ws_atual.update_cell(idx + 2, 5, v_mont.strftime("%d/%m/%Y"))
                st.success("Salvo!"); time.sleep(1); st.rerun()

        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'STATUS', 'OBS']], use_container_width=True, hide_index=True, column_config=cfg_rel)

    elif aba == "📊 CURVA S":
        st.subheader("📊 Avanço Físico")
        total = len(df_atual)
        real = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        st.metric("Progresso", f"{(real/total*100):.2f}%")
        st.progress(real/total)
        # Gráfico simplificado para evitar erro de data
        fig = go.Figure(go.Indicator(mode = "gauge+number", value = real, title = {'text': "TAGs Montadas"}, gauge = {'axis': {'range': [0, total]}}))
        st.plotly_chart(fig)

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📋 Relatórios de Campo")
        tab1, tab2 = st.tabs(["📅 PROGRAMADO", "🚩 PENDÊNCIAS"])
        with tab1:
            df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
            st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA']], use_container_width=True, hide_index=True, column_config=cfg_rel)
        with tab2:
            df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
            st.dataframe(df_pend[['TAG', 'DESCRIÇÃO', 'STATUS', 'OBS']], use_container_width=True, hide_index=True, column_config=cfg_rel)

   elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader("📤 Atualização em Massa")
        st.write("Suba o arquivo Excel para atualizar a base do Google Sheets de uma só vez.")
        
        up = st.file_uploader("Subir Excel", type="xlsx")
        
        if up:
            if st.button("🚀 IMPORTAR E SINCRONIZAR AGORA"):
                try:
                    with st.spinner('Comunicando com o Google Sheets... Aguarde.'):
                        df_up = pd.read_excel(up).astype(str).replace('nan', '')
                        
                        # Carrega a matriz completa da planilha para a memória (Mais rápido)
                        data_matrix = ws_atual.get_all_values()
                        headers = data_matrix[0]
                        
                        contagem = 0
                        # Percorre o Excel subido
                        for _, row_up in df_up.iterrows():
                            t_up = str(row_up.get('TAG', '')).strip()
                            
                            # Procura o TAG na matriz do Google
                            for i, row_ws in enumerate(data_matrix[1:]):
                                if str(row_ws[0]).strip() == t_up:
                                    # Se achou, atualiza os campos na memória
                                    # (Ajuste os índices conforme a ordem das suas colunas A=0, B=1...)
                                    if 'SEMANA OBRA' in df_up.columns: 
                                        data_matrix[i+1][1] = row_up['SEMANA OBRA'] # Coluna B
                                    if 'OBS' in df_up.columns: 
                                        data_matrix[i+1][6] = row_up['OBS'] # Coluna G
                                    contagem += 1
                        
                        # Devolve a matriz completa e atualizada para o Google de uma vez só
                        ws_atual.update('A1', data_matrix)
                        
                        # FEEDBACK DE SUCESSO
                        st.balloons() # Efeito visual de comemoração
                        st.success(f"✅ SUCESSO TOTAL! {contagem} TAGs foram sincronizadas com a planilha.")
                        time.sleep(2)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Erro crítico na importação: {e}")
                    st.info("Dica: Verifique se o TAG no Excel é exatamente igual ao da Planilha.")
