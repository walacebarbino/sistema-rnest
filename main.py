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

# --- CSS PARA PADRONIZAÇÃO E ALINHAMENTO ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div, .stNumberInput div, .stSelectbox div { height: 45px !important; }
    div[data-testid="stForm"] > div { align-items: center; }
    label p { font-weight: bold !important; font-size: 14px !important; min-height: 25px; margin-bottom: 5px !important; }
    input:disabled { background-color: #1e293b !important; color: #60a5fa !important; opacity: 1 !important; }
    .stFileUploader { margin-top: -15px; }
    [data-testid="stSidebar"] [data-testid="stImage"] { text-align: center; display: block; margin-left: auto; margin-right: auto; }
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
        st.error(f"Erro na conexão: {e}"); st.stop()

client = conectar_google()

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        try:
            data = ws.get('DADOS')
        except:
            data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip()
            col_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']
            for c in col_obj:
                if c not in df.columns: df[c] = ""
            for c in df.columns:
                df[c] = df[c].astype(str).str.strip().replace(['nan', 'None', 'NaT', '-', 'NaN'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE APOIO ---
def get_dates_from_week(week_number):
    if not str(week_number).isdigit(): return None, None
    monday = DATA_INICIO_OBRA + timedelta(weeks=(int(week_number) - 1))
    friday = monday + timedelta(days=4)
    return monday.date(), friday.date()

def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip() not in ["", "None", "nan", "-", "DD/MM/YYYY"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

st.sidebar.subheader("MENU G-MONT")
disc = st.sidebar.selectbox("DISCIPLINA:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    cfg_rel = {
        "TAG": st.column_config.TextColumn(width="medium"),
        "DESCRIÇÃO": st.column_config.TextColumn(width="large"),
        "OBS": st.column_config.TextColumn(width="large"),
        "DOCUMENTO": st.column_config.TextColumn(width="medium")
    }

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        c_tag, c_sem = st.columns([2, 1])
        with c_tag:
            tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        with c_sem:
            sem_input = st.text_input("Semana da Obra:", value=dados_tag['SEMANA OBRA'])
        
        sug_ini, sug_fim = get_dates_from_week(sem_input)
        
        with st.form("form_edit_final"):
            c1, c2, c3, c4 = st.columns(4)
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default
            v_ini = c1.date_input("Início Prog", value=conv_dt(dados_tag['DATA INIC PROG'], sug_ini), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=conv_dt(dados_tag['DATA FIM PROG'], sug_fim), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            st_calc = calcular_status_tag(v_ini, v_fim, v_mont)
            c4.text_input("Status Atual", value=st_calc, disabled=True)
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                updates = {'SEMANA OBRA': sem_input, 'DATA INIC PROG': v_ini.strftime("%d/%m/%Y") if v_ini else "", 'DATA FIM PROG': v_fim.strftime("%d/%m/%Y") if v_fim else "", 'DATA MONT': v_mont.strftime("%d/%m/%Y") if v_mont else "", 'STATUS': st_calc, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], val)
                st.success("Salvo!"); time.sleep(1); st.rerun()

        st.divider()
        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'STATUS', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']], 
                     use_container_width=True, hide_index=True, column_config=cfg_rel)

    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S e Avanço - {disc}")
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per = (montados / total_t * 100) if total_t > 0 else 0
        st.metric("Avanço Geral", f"{per:.2f}%")
        st.progress(per / 100)
        
        df_c = df_atual.copy()
        df_c['DT_R'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_P'] = pd.to_datetime(df_c['DATA FIM PROG'], dayfirst=True, errors='coerce')
        real = df_c.dropna(subset=['DT_R']).sort_values('DT_R')
        prog = df_c.dropna(subset=['DT_P']).sort_values('DT_P')
        
        fig = go.Figure()
        if not prog.empty:
            prog['Acumulado'] = range(1, len(prog) + 1)
            fig.add_trace(go.Scatter(x=prog['DT_P'], y=prog['Acumulado'], name='Programado', line=dict(color='yellow', width=3)))
        if not real.empty:
            real['Acumulado'] = range(1, len(real) + 1)
            fig.add_trace(go.Scatter(x=real['DT_R'], y=real['Acumulado'], name='Realizado', line=dict(color='cyan', width=3)))
        
        fig.update_layout(template="plotly_dark", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df_atual))
        m2.metric("Montados ✅", len(df_atual[df_atual['STATUS']=='MONTADO']))
        m3.metric("Programados 📅", len(df_atual[df_atual['STATUS']=='PROGRAMADO']))
        m4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS']=='AGUARDANDO PROG']))
        
        st.divider()
        st.markdown("### 📅 PROGRAMADO PRODUÇÃO")
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']], use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        st.dataframe(df_pend[['TAG', 'DESCRIÇÃO', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader("📤 Sincronização e Base")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 **MODELO**")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 BAIXAR MODELO", b_m.getvalue(), "modelo.xlsx", use_container_width=True)
        
        with c2:
            st.info("🚀 **IMPORTAR EXCEL**")
            up = st.file_uploader("Upload:", type="xlsx", label_visibility="collapsed")
            if up:
                if st.button("🚀 SINCRONIZAR AGORA", use_container_width=True):
                    try:
                        with st.spinner('Sincronizando...'):
                            df_up = pd.read_excel(up, engine='openpyxl').fillna('')
                            df_up.columns = df_up.columns.str.strip().upper()
                            try: data_mat = ws_atual.get('DADOS')
                            except: data_mat = ws_atual.get_all_values()
                            
                            sucesso = 0
                            for _, r in df_up.iterrows():
                                t_ex = str(r.get('TAG', '')).strip()
                                for i, row in enumerate(data_mat[1:]):
                                    if str(row[0]).strip() == t_ex:
                                        if 'SEMANA' in str(df_up.columns): data_mat[i+1][1] = str(r.get('SEMANA OBRA', row[1]))
                                        if 'INIC' in str(df_up.columns):   data_mat[i+1][2] = str(r.get('DATA INIC PROG', row[2]))
                                        if 'FIM' in str(df_up.columns):    data_mat[i+1][3] = str(r.get('DATA FIM PROG', row[3]))
                                        if 'MONT' in str(df_up.columns):   data_mat[i+1][4] = str(r.get('DATA MONT', row[4]))
                                        if 'OBS' in str(df_up.columns):    data_mat[i+1][6] = str(r.get('OBS', row[6]))
                                        sucesso += 1
                            
                            final_mat = [[str(c) if (str(c).lower() != 'nan') else '' for c in lista] for lista in data_mat]
                            try: ws_atual.update('DADOS', final_mat)
                            except: ws_atual.update('A1', final_mat)
                            st.balloons(); st.success(f"✅ {sucesso} TAGs sincronizadas!"); time.sleep(2); st.rerun()
                    except Exception as e: st.error(f"Erro: {e}")

        with c3:
            st.info("💾 **BASE COMPLETA**")
            b_f = BytesIO(); df_atual.to_excel(b_f, index=False)
            st.download_button("📥 EXPORTAR TUDO", b_f.getvalue(), f"Base_{disc}.xlsx", use_container_width=True)
