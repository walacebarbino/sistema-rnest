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

# --- CONTROLE DE ACESSO E DISCIPLINAS ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'disciplina_ativa' not in st.session_state: st.session_state['disciplina_ativa'] = None

# --- CSS PARA LOGO NA SIDEBAR ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] [data-testid="stImage"] {
        padding: 0px !important;
        margin-top: -60px !important;
        margin-left: -20px !important;
        margin-right: -20px !important;
        width: calc(100% + 40px) !important;
    }
    [data-testid="stSidebar"] [data-testid="stImage"] img {
        width: 100% !important;
        height: auto !important;
        border-radius: 0px !important;
    }
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div, .stNumberInput div, .stSelectbox div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- TELAS DE ENTRADA (ALTERAÇÃO SOLICITADA) ---
def tela_login():
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try: st.image("LOGO2.png", width=120)
        except: pass
        st.subheader("🔐 LOGIN G-MONT")
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA", use_container_width=True):
            if pin == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()

def tela_selecao_disciplina():
    st.markdown("<h1 style='text-align: center;'>BEM-VINDO AO G-MONT</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center;'>Escolha a Disciplina para iniciar:</h3>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    if col1.button("⚡ ELÉTRICA", use_container_width=True):
        st.session_state['disciplina_ativa'] = "ELÉTRICA"
        st.rerun()
    if col2.button("🔧 INSTRUMENTAÇÃO", use_container_width=True):
        st.session_state['disciplina_ativa'] = "INSTRUMENTAÇÃO"
        st.rerun()
    if col3.button("🏗️ ESTRUTURA", use_container_width=True):
        st.session_state['disciplina_ativa'] = "ESTRUTURA"
        st.rerun()
    st.stop()

if not st.session_state['logado']: tela_login()
if not st.session_state['disciplina_ativa']: tela_selecao_disciplina()

# --- CONEXÃO GOOGLE SHEETS (SEU ORIGINAL) ---
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
            col_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO', 'PREVISTO']
            for c in col_obj:
                if c not in df.columns: df[c] = ""
            for c in df.columns:
                df[c] = df[c].astype(str).str.strip().replace(['nan', 'None', 'NaT', '-'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

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

# --- CARREGAMENTO E SIDEBAR ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")
df_est, ws_est = extrair_dados("BD_ESTR")

disc = st.session_state['disciplina_ativa']
if disc == "ELÉTRICA": df_atual, ws_atual = df_ele, ws_ele
elif disc == "INSTRUMENTAÇÃO": df_atual, ws_atual = df_ins, ws_ins
elif disc == "ESTRUTURA": df_atual, ws_atual = df_est, ws_est
else: df_atual, ws_atual = pd.DataFrame(), None

with st.sidebar:
    try: st.image("LOGO2.png", use_container_width=True)
    except: pass
    st.subheader(f"📍 {disc}")
    if st.button("🔄 TROCAR DISCIPLINA", use_container_width=True):
        st.session_state['disciplina_ativa'] = None
        st.rerun()
    aba = st.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])
    st.divider()
    if st.button("🚪 SAIR", use_container_width=True):
        st.session_state['logado'] = False
        st.session_state['disciplina_ativa'] = None
        st.rerun()

# --- LÓGICA DAS ABAS (SEU ORIGINAL) ---
if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}
    cfg_rel = {"TAG": st.column_config.TextColumn(width="medium"), "DESCRIÇÃO": st.column_config.TextColumn(width="large"), "OBS": st.column_config.TextColumn(width="large"), "DOCUMENTO": st.column_config.TextColumn(width="medium")}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        c_tag, c_sem = st.columns([2, 1])
        with c_tag: tag_sel = st.selectbox("Selecione para EDITAR:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        with c_sem: sem_input = st.text_input("Semana da Obra:", value=dados_tag['SEMANA OBRA'])
        sug_ini, sug_fim = get_dates_from_week(sem_input)
        with st.form("form_edit_final"):
            c1, c2, c3, c4 = st.columns(4)
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default
            v_prev = c1.date_input("Data Previsto", value=conv_dt(dados_tag.get('PREVISTO', ''), None), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", value=conv_dt(dados_tag['DATA INIC PROG'], sug_ini), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", value=conv_dt(dados_tag['DATA FIM PROG'], sug_fim), format="DD/MM/YYYY")
            v_mont = c4.date_input("Data Montagem", value=conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            st_atual = calcular_status_tag(v_ini, v_fim, v_mont); st.info(f"Status Atualizado: **{st_atual}**")
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
                f_prev, f_ini, f_fim, f_mont = [v.strftime("%d/%m/%Y") if v else "" for v in [v_prev, v_ini, v_fim, v_mont]]
                updates = {'SEMANA OBRA': sem_input, 'PREVISTO': f_prev, 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_atual, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], str(val))
                st.success("Salvo!"); st.rerun()
        st.divider()
        col_cad, col_del = st.columns(2)
        with col_cad:
            with st.expander("➕ CADASTRAR NOVO TAG"):
                with st.form("form_novo"):
                    n_tag = st.text_input("TAG *")
                    if st.form_submit_button("🚀 CADASTRAR"):
                        if n_tag: ws_atual.append_row([n_tag, "", "", "", "", "", "AGUARDANDO PROG", disc, "", "", "", "", "", "", "", "", ""]); st.rerun()
        with col_del:
            with st.expander("🗑️ DELETAR TAG"):
                tag_para_deletar = st.selectbox("TAG para DELETAR:", [""] + sorted(df_atual['TAG'].unique().tolist()))
                if tag_para_deletar and st.button("🔴 CONFIRMAR EXCLUSÃO"):
                    cell = ws_atual.find(tag_para_deletar, in_column=1)
                    if cell: ws_atual.delete_rows(cell.row); st.rerun()
        st.divider()
        # --- QUADRO COM DESCRIÇÃO ANTES DO STATUS (ALTERAÇÃO SOLICITADA) ---
        colunas_quadro = ['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'DESCRIÇÃO', 'STATUS', 'OBS']
        col_dates_cfg = {
            "TAG": st.column_config.TextColumn("TAG"),
            "PREVISTO": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA INIC PROG": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA FIM PROG": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA MONT": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DESCRIÇÃO": st.column_config.TextColumn("DESCRIÇÃO", width="large")
        }
        st.dataframe(df_atual[colunas_quadro], use_container_width=True, hide_index=True, column_config={**cfg_rel, **col_dates_cfg})

    elif aba == "📊 CURVA S":
        # (SEU CÓDIGO ORIGINAL DE CURVA S)
        st.subheader(f"📊 Curva S - {disc}")
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per_real = (montados / total_t * 100) if total_t > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Avanço Total", f"{per_real:.2f}%")
        c2.progress(per_real / 100)
        df_c = df_atual.copy()
        df_c['DT_REAL'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_PREV'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')
        prev_mes = df_c['DT_PREV'].dt.to_period('M').value_counts().sort_index()
        real_mes = df_c['DT_REAL'].dt.to_period('M').value_counts().sort_index()
        todos_meses = sorted(list(set(prev_mes.index.tolist() + real_mes.index.tolist())))
        x_eixo = [str(m) for m in todos_meses]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_eixo, y=prev_mes.reindex(todos_meses, fill_value=0), name='Previsto', marker_color='#2ecc71', opacity=0.6))
        fig.add_trace(go.Bar(x=x_eixo, y=real_mes.reindex(todos_meses, fill_value=0), name='Realizado', marker_color='#3498db', opacity=0.6))
        fig.add_trace(go.Scatter(x=x_eixo, y=prev_mes.reindex(todos_meses, fill_value=0).cumsum(), name='Prev. Acum.', line=dict(color='#27ae60', width=4)))
        fig.add_trace(go.Scatter(x=x_eixo, y=real_mes.reindex(todos_meses, fill_value=0).cumsum(), name='Real. Acum.', line=dict(color='#e74c3c', width=4)))
        fig.update_layout(template="plotly_dark", barmode='group', height=500); st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        # (SEU CÓDIGO ORIGINAL DE RELATÓRIOS)
        st.subheader(f"📋 Relatórios - {disc}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df_atual)); m2.metric("Montados ✅", len(df_atual[df_atual['STATUS']=='MONTADO']))
        m3.metric("Programados 📅", len(df_atual[df_atual['STATUS']=='PROGRAMADO'])); m4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS']=='AGUARDANDO PROG']))
        st.divider()
        st.markdown("### 📅 PROGRAMADO PRODUÇÃO")
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        cols_p = ['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']
        st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True, column_config=cfg_rel)
        buf_p = BytesIO(); df_p[cols_p].to_excel(buf_p, index=False)
        st.download_button("📥 EXPORTAR PROGRAMADO", buf_p.getvalue(), f"Programado_{disc}.xlsx")
        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS TOTAIS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        cols_pend = ['TAG', 'DESCRIÇÃO', 'ÁREA', 'STATUS', 'PREVISTO', 'OBS']
        st.dataframe(df_pend[cols_pend], use_container_width=True, hide_index=True, column_config=cfg_rel)
        buf_pe = BytesIO(); df_pend[cols_pend].to_excel(buf_pe, index=False)
        st.download_button("📥 EXPORTAR PENDÊNCIAS", buf_pe.getvalue(), f"Pendencias_{disc}.xlsx")
        st.divider()
        st.markdown("### 📈 AVANÇO POR SEMANA")
        semanas = sorted(df_atual['SEMANA OBRA'].unique(), reverse=True)
        semana_sel = st.selectbox("Selecione a Semana:", semanas if len(semanas)>0 else ["-"])
        df_semana = df_atual[(df_atual['SEMANA OBRA'] == semana_sel) & (df_atual['STATUS'] == 'MONTADO')]
        st.dataframe(df_semana[['TAG', 'DESCRIÇÃO', 'DATA MONT', 'ÁREA', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        # (SEU CÓDIGO ORIGINAL DE IMPORTAÇÃO/EXPORTAÇÃO)
        st.subheader(f"📤 Exportações e Importações - {disc}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 MODELO")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 EXPORTAR MOD", b_m.getvalue(), "modelo.xlsx")
        with c2:
            st.info("🚀 IMPORTAÇÃO")
            up = st.file_uploader("Upload Excel:", type="xlsx")
            if up and st.button("🚀 IMPORTAR"):
                try:
                    df_up = pd.read_excel(up).astype(str)
                    lista_mestra = ws_atual.get_all_values()
                    headers = [str(h).strip().upper() for h in lista_mestra[0]]
                    idx_map = {name: i for i, name in enumerate(headers)}
                    for _, r in df_up.iterrows():
                        tag_import = str(r.get('TAG', '')).strip()
                        for i, row in enumerate(lista_mestra[1:]):
                            if str(row[0]).strip() == tag_import:
                                for col in ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']:
                                    if col.upper() in [c.upper() for c in df_up.columns]:
                                        lista_mestra[i+1][idx_map[col.upper()]] = str(r[col]).strip()
                                break
                    ws_atual.update('A1', lista_mestra); st.success("Sucesso!"); st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
        with c3:
            st.info("💾 BASE COMPLETA")
            b_f = BytesIO(); df_atual.to_excel(b_f, index=False)
            st.download_button("📥 EXPORTAR BASE", b_f.getvalue(), f"Base_{disc}.xlsx")
