import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E DATA BASE DA OBRA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
DATA_INICIO_OBRA = datetime(2025, 9, 29) 

# --- CSS PARA PADRONIZAÇÃO ---
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
            col_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA']
            for c in col_obj:
                if c not in df.columns: df[c] = ""
            for c in df.columns:
                df[c] = df[c].astype(str).str.strip().replace(['nan', 'None', 'NaT', '-'], '')
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
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO E QUADRO ---
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
            st_atual = calcular_status_tag(v_ini, v_fim, v_mont)
            c4.text_input("Status Atual", value=st_atual, disabled=True)
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                updates = {'SEMANA OBRA': sem_input, 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_atual, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], val)
                st.success("Salvo!"); st.rerun()
        st.divider()
        st.markdown(f"### 📋 QUADRO GERAL - {disc}")
        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'STATUS', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S e Avanço - {disc}")
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per_prog = (montados / total_t * 100) if total_t > 0 else 0
        st.metric("Avanço da Disciplina", f"{per_prog:.2f}%")
        st.progress(per_prog / 100)
        df_c = df_atual.copy()
        df_c['DT_REAL'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_PROG'] = pd.to_datetime(df_c['DATA FIM PROG'], dayfirst=True, errors='coerce')
        real = df_c.dropna(subset=['DT_REAL']).sort_values('DT_REAL')
        prog = df_c.dropna(subset=['DT_PROG']).sort_values('DT_PROG')
        fig = go.Figure()
        if not prog.empty:
            prog['Acumulado'] = range(1, len(prog) + 1)
            fig.add_trace(go.Scatter(x=prog['DT_PROG'], y=prog['Acumulado'], name='Programado', line=dict(color='yellow', width=3)))
        if not real.empty:
            real['Acumulado'] = range(1, len(real) + 1)
            fig.add_trace(go.Scatter(x=real['DT_REAL'], y=real['Acumulado'], name='Realizado', line=dict(color='cyan', width=3)))
        if not prog.empty:
            d_ini, d_fim = prog['DT_PROG'].min(), prog['DT_PROG'].max()
            fig.add_trace(go.Scatter(x=[d_ini, d_fim], y=[0, total_t], name='Previsto (Base)', line=dict(color='gray', dash='dot')))
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    # --- ABA 3: RELATÓRIOS (RESTAURADO COMPLETO) ---
    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df_atual)); m2.metric("Montados ✅", len(df_atual[df_atual['STATUS']=='MONTADO']))
        m3.metric("Programados 📅", len(df_atual[df_atual['STATUS']=='PROGRAMADO'])); m4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS']=='AGUARDANDO PROG']))
        
        st.divider()
        st.markdown("### 📅 PROGRAMADO PRODUÇÃO")
        semanas = sorted([s for s in df_atual['SEMANA OBRA'].unique() if str(s).isdigit()], key=int, reverse=True)
        sem_f = st.selectbox("Filtrar por Semana:", ["TODAS"] + semanas)
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        if sem_f != "TODAS": df_p = df_p[df_p['SEMANA OBRA'] == sem_f]
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'OBS']], use_container_width=True, hide_index=True)
        buf_p = BytesIO(); df_p.to_excel(buf_p, index=False)
        st.download_button("📥 EXPORTAR PROGRAMADO PRODUÇÃO", buf_p.getvalue(), f"Programado_{disc}.xlsx")

        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS TOTAIS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        st.dataframe(df_pend[['TAG', 'STATUS', 'ÁREA', 'OBS']], use_container_width=True, hide_index=True)
        buf_pe = BytesIO(); df_pend.to_excel(buf_pe, index=False)
        st.download_button("📥 EXPORTAR PENDÊNCIAS", buf_pe.getvalue(), f"Pendencias_{disc}.xlsx")

        st.divider()
        st.markdown("### 📈 AVANÇO SEMANAL (REALIZADO 7 DIAS)")
        df_atual['DT_TEMP'] = pd.to_datetime(df_atual['DATA MONT'], dayfirst=True, errors='coerce')
        df_setec = df_atual[df_atual['DT_TEMP'] >= (datetime.now() - timedelta(days=7))]
        st.dataframe(df_setec[['TAG', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)
        buf_r = BytesIO(); df_setec.to_excel(buf_r, index=False)
        st.download_button("📥 EXPORTAR AVANÇO SEMANAL", buf_r.getvalue(), f"Realizado_7_dias_{disc}.xlsx")

    # --- ABA 4: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader(f"📤 Carga em Massa - {disc}")
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False); st.download_button("📥 Baixar Modelo", b_m.getvalue(), "modelo.xlsx")
        with c_m2:
            b_f = BytesIO(); df_atual.to_excel(b_f, index=False); st.download_button("📥 Exportar Base", b_f.getvalue(), "base.xlsx")
        st.divider()
        up = st.file_uploader("Upload Excel:", type="xlsx")
        if up and st.button("🚀 EXECUTAR CARGA"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    ln = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    for c in df_up.columns:
                        if c in cols_map: ws_atual.update_cell(ln, cols_map[c], r[c])
            st.success("Importado!"); st.rerun()
