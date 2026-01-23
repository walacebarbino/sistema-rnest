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
            # Garante colunas contra KeyError (Resolvendo image_03e83c e image_02f895)
            colunas_obrigatorias = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA']
            for col in colunas_obrigatorias:
                if col not in df.columns: df[col] = ""
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'NaT', '-'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE SEMANA E STATUS ---
def get_dates_from_week(week_number):
    if not week_number or week_number == "": return None, None
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
    # Recalcula status para Dashboards (Resolvendo image_03e056 e image_038375)
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]

        # Caixa de Semana que aceita VAZIO
        val_sem_orig = dados_tag['SEMANA OBRA']
        sem_input = st.text_input("SEMANA DA OBRA (Deixe vazio para desprogramar):", value=val_sem_orig)
        
        sug_ini, sug_fim = get_dates_from_week(sem_input) if sem_input.isdigit() else (None, None)

        with st.form("form_edit_v3"):
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
                
                updates = {'SEMANA OBRA': sem_input, 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_atual, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], val)
                st.success("Salvo!")
                st.rerun()

    elif aba == "📊 CURVA S":
        st.subheader("📊 Progresso Físico")
        df_atual['DT_M'] = pd.to_datetime(df_atual['DATA MONT'], dayfirst=True, errors='coerce')
        df_real = df_atual.dropna(subset=['DT_M']).sort_values('DT_M')
        if not df_real.empty:
            df_real['Acumulado'] = range(1, len(df_real) + 1)
            fig = px.line(df_real, x='DT_M', y='Acumulado', title="Avanço Realizado")
            st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📊 Painel de Controle e Relatórios")
        # Métricas (Resolvendo image_02ed0e)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total TAGs", len(df_atual))
        c2.metric("Montados ✅", len(df_atual[df_atual['STATUS'] == 'MONTADO']))
        c3.metric("Programados 📅", len(df_atual[df_atual['STATUS'] == 'PROGRAMADO']))
        c4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS'] == 'AGUARDANDO PROG']))

        st.divider()
        # 1. PROGRAMADO PRODUÇÃO (Resolvendo sua queixa de falta de relatórios)
        st.markdown("### 📋 PROGRAMADO PRODUÇÃO")
        semanas = sorted([s for s in df_atual['SEMANA OBRA'].unique() if s != ""], key=int, reverse=True)
        sem_f = st.selectbox("Filtrar Semana (Deixe vazio para ver todos programados):", [""] + semanas)
        
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        if sem_f != "": df_p = df_p[df_p['SEMANA OBRA'] == sem_f]
        
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'OBS']], use_container_width=True, hide_index=True)
        
        # 2. RELATÓRIO DE PENDÊNCIAS (Restaurado)
        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS TOTAIS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        st.dataframe(df_pend[['TAG', 'STATUS', 'ÁREA', 'OBS']], use_container_width=True, hide_index=True)

        # 3. AVANÇO SEMANAL / REALIZADO (Restaurado)
        st.divider()
        st.markdown("### 📈 REALIZADO (ÚLTIMOS 7 DIAS)")
        df_atual['DT_TEMP'] = pd.to_datetime(df_atual['DATA MONT'], dayfirst=True, errors='coerce')
        df_setec = df_atual[df_atual['DT_TEMP'] >= (datetime.now() - timedelta(days=7))]
        st.dataframe(df_setec[['TAG', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)

        # Botões de Download
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_p.to_excel(writer, sheet_name='Programado', index=False)
            df_pend.to_excel(writer, sheet_name='Pendencias', index=False)
        st.download_button("📥 BAIXAR RELATÓRIOS COMPLETOS (EXCEL)", buf.getvalue(), "Relatorios_GMONT.xlsx", use_container_width=True)

    elif aba == "📤 CARGA EM MASSA":
        st.subheader("📤 Gestão de Dados e Importação")
        # Restaurando botões de exportação (Resolvendo image_02f7fc)
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.info("Modelo para Carga")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False); st.download_button("📥 Baixar Modelo", b_m.getvalue(), "modelo.xlsx")
        with col_ex2:
            st.success("Base Completa")
            b_f = BytesIO(); df_atual.to_excel(b_f, index=False); st.download_button("📥 Exportar Tudo", b_f.getvalue(), "base_completa.xlsx")

        st.divider()
        up = st.file_uploader("Selecione o arquivo Excel atualizado:", type="xlsx")
        if up and st.button("🚀 EXECUTAR IMPORTAÇÃO"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    ln = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    for c in df_up.columns:
                        if c in cols_map: ws_atual.update_cell(ln, cols_map[c], r[c])
            st.success("Importação Concluída!"); st.rerun()
