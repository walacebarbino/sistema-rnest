import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E DATA BASE DA OBRA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
# Baseado na sua informação de que 22/01/2026 é Semana 17
DATA_INICIO_OBRA = datetime(2025, 9, 29) 

# --- CSS PARA ALINHAMENTO E PADRONIZAÇÃO ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div, .stNumberInput div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; min-height: 25px; }
    input:disabled { background-color: #1e293b !important; color: #60a5fa !important; opacity: 1 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONTROLE DE ACESSO ---
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
        st.error(f"Erro na conexão com Google: {e}")
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
            # Garante colunas mínimas para evitar erros das imagens 02f895 e 03e83c
            colunas_obrigatorias = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']
            for col in colunas_obrigatorias:
                if col not in df.columns: df[col] = ""
            
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'NaT', '-'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE SEMANA E STATUS ---
def get_dates_from_week(week_number):
    monday = DATA_INICIO_OBRA + timedelta(weeks=(int(week_number) - 1))
    friday = monday + timedelta(days=4)
    return monday.date(), friday.date()

def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip() not in ["", "None", "nan", "-"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

st.sidebar.subheader("MENU G-MONT")
disc = st.sidebar.selectbox("DISCIPLINA:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    # Recalcula status para garantir Dashboards atualizados (Resolve image_03e056)
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        tag_sel = st.selectbox("Selecione o TAG para editar:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]

        # REATIVIDADE: Sessão para controlar as datas ao mudar a semana
        if f"sem_{tag_sel}" not in st.session_state:
            st.session_state[f"sem_{tag_sel}"] = int(dados_tag['SEMANA OBRA']) if str(dados_tag['SEMANA OBRA']).isdigit() else 17

        def mudar_semana():
            st.session_state[f"sem_{tag_sel}"] = st.session_state[f"temp_sem_{tag_sel}"]

        c_sem, c_blank = st.columns([1, 3])
        sem_obra = c_sem.number_input("SEMANA DA OBRA", min_value=1, key=f"temp_sem_{tag_sel}", on_change=mudar_semana, value=st.session_state[f"sem_{tag_sel}"])
        
        sug_ini, sug_fim = get_dates_from_week(sem_obra)

        with st.form("form_edit_final"):
            col1, col2, col3, col4 = st.columns(4)
            
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default

            v_ini = col1.date_input("Início Prog", value=conv_dt(dados_tag['DATA INIC PROG'], sug_ini), format="DD/MM/YYYY")
            v_fim = col2.date_input("Fim Prog", value=conv_dt(dados_tag['DATA FIM PROG'], sug_fim), format="DD/MM/YYYY")
            v_mont = col3.date_input("Data Montagem", value=conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            
            st_atual = calcular_status_tag(v_ini, v_fim, v_mont)
            col4.text_input("Status Atual", value=st_atual, disabled=True)
            
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                
                linha = idx_base + 2
                updates = {'SEMANA OBRA': str(sem_obra), 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_atual, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Salvo!")
                st.rerun()
        
        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'STATUS', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📊 Painel de Controle")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(df_atual))
        c2.metric("Montados", len(df_atual[df_atual['STATUS'] == 'MONTADO']))
        c3.metric("Programados", len(df_atual[df_atual['STATUS'] == 'PROGRAMADO']))
        c4.metric("Aguardando", len(df_atual[df_atual['STATUS'] == 'AGUARDANDO PROG']))

        st.divider()
        st.markdown("### 📋 PROGRAMADO PRODUÇÃO")
        semanas_existentes = sorted([s for s in df_atual['SEMANA OBRA'].unique() if s != ""], key=int, reverse=True)
        sem_f = st.selectbox("Filtrar por Semana de Obra:", semanas_existentes if semanas_existentes else ["17"])
        
        df_p = df_atual[(df_atual['STATUS'] == 'PROGRAMADO') & (df_atual['SEMANA OBRA'] == sem_f)]
        st.dataframe(df_p[['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'OBS']], use_container_width=True, hide_index=True)
        
        if not df_p.empty:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_p.to_excel(writer, index=False)
            st.download_button("📥 BAIXAR PROGRAMADO PRODUÇÃO (EXCEL)", buf.getvalue(), f"PROD_SEM_{sem_f}.xlsx", use_container_width=True)

    elif aba == "📤 CARGA EM MASSA":
        st.subheader("📤 Gestão de Dados em Massa")
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            st.info("Baixe o modelo para preenchimento")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']].head(5)
            buf_m = BytesIO()
            with pd.ExcelWriter(buf_m, engine='xlsxwriter') as writer: mod.to_excel(writer, index=False)
            st.download_button("📥 Baixar Modelo Excel", buf_m.getvalue(), "modelo_carga.xlsx")
        
        with c_m2:
            st.success("Exportação completa da base")
            buf_f = BytesIO()
            with pd.ExcelWriter(buf_f, engine='xlsxwriter') as writer: df_atual.to_excel(writer, index=False)
            st.download_button("📥 Exportar Base Completa", buf_f.getvalue(), "base_completa.xlsx")

        st.divider()
        up = st.file_uploader("Upload de arquivo preenchido:", type="xlsx")
        if up and st.button("🚀 EXECUTAR CARGA EM MASSA"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            prog = st.progress(0)
            for i, (_, r) in enumerate(df_up.iterrows()):
                if r['TAG'] in df_atual['TAG'].values:
                    ln = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    for c in df_up.columns:
                        if c in cols_map: ws_atual.update_cell(ln, cols_map[c], r[c])
                prog.progress((i+1)/len(df_up))
            st.success("Carga Finalizada!")
            st.rerun()
