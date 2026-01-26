import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E DATA BASE ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
DATA_INICIO_OBRA = datetime(2025, 9, 29) 

# --- FUNÇÃO DE EXCEL (PROTEÇÃO CONTRA VAZIO E DATAS) ---
def exportar_excel_com_cabecalho(df, titulo_relatorio):
    if df.empty: return None
    output = BytesIO()
    # Garantir que datas virem string DD/MM/AAAA antes de exportar
    df_exp = df.copy()
    cols_data = ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT']
    for c in cols_data:
        if c in df_exp.columns:
            df_exp[c] = pd.to_datetime(df_exp[c], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').replace('NaT', '')
            
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_exp.to_excel(writer, index=False, sheet_name='Relatorio', startrow=8)
        workbook, worksheet = writer.book, writer.sheets['Relatorio']
        fmt_t = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        try: worksheet.insert_image('A1', 'LOGO2.png', {'x_scale': 0.4, 'y_scale': 0.4})
        except: pass
        worksheet.merge_range('C3:F5', titulo_relatorio.upper(), fmt_t)
        for i, col in enumerate(df_exp.columns):
            worksheet.set_column(i, i, max(df_exp[col].astype(str).map(len).max(), len(col)) + 3)
    return output.getvalue()

# --- CONEXÃO E CACHE ---
@st.cache_resource
def conectar_google():
    try:
        creds_dict = json.loads(base64.b64decode(st.secrets["GOOGLE_CREDENTIALS_BASE64"]))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scope))
    except Exception as e: st.error(f"Erro: {e}"); st.stop()

def extrair_dados(nome):
    try:
        sh = conectar_google().open(nome)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) <= 1: return pd.DataFrame(), ws
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = df.columns.str.strip()
        # Limpeza rápida vetorizada
        df = df.replace(['nan', 'None', 'NaT', '-', 'DD/MM/YYYY'], '').fillna('')
        return df, ws
    except: return pd.DataFrame(), None

# --- ESTADOS DE SESSÃO ---
if 'logado' not in st.session_state: st.session_state.logado = False
if 'disc' not in st.session_state: st.session_state.disc = None

# --- LOGIN E SELEÇÃO (ESTRUTURA ORIGINAL) ---
if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        try: st.image("LOGO2.png", width=120)
        except: pass
        pin = st.text_input("PIN:", type="password")
        if st.button("ENTRAR") and pin == "1234":
            st.session_state.logado = True; st.rerun()
    st.stop()

if not st.session_state.disc:
    st.markdown("<h1 style='text-align:center;'>G-MONT</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    if c1.button("⚡ ELÉTRICA", use_container_width=True): st.session_state.disc = "ELÉTRICA"; st.rerun()
    if c2.button("🔧 INSTRUMENTAÇÃO", use_container_width=True): st.session_state.disc = "INSTRUMENTAÇÃO"; st.rerun()
    if c3.button("🏗️ ESTRUTURA", use_container_width=True): st.session_state.disc = "ESTRUTURA"; st.rerun()
    st.stop()

# --- CARGA DE DADOS ---
bd_map = {"ELÉTRICA": "BD_ELE", "INSTRUMENTAÇÃO": "BD_INST", "ESTRUTURA": "BD_ESTR"}
df_atual, ws_atual = extrair_dados(bd_map[st.session_state.disc])

# --- SIDEBAR ---
st.sidebar.image("LOGO2.png", width=120) if True else None
st.sidebar.write(f"**Disciplina:** {st.session_state.disc}")
if st.sidebar.button("🔄 TROCAR DISCIPLINA"): st.session_state.disc = None; st.rerun()
aba = st.sidebar.radio("MENU:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

if not df_atual.empty:
    # Lógica de Status
    def calc_st(r):
        if r['DATA MONT']: return "MONTADO"
        if r['DATA INIC PROG'] or r['DATA FIM PROG']: return "PROGRAMADO"
        return "AGUARDANDO PROG"
    df_atual['STATUS'] = df_atual.apply(calc_st, axis=1)

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição - {st.session_state.disc}")
        tag_sel = st.selectbox("TAG:", sorted(df_atual['TAG'].unique()))
        dados = df_atual[df_atual['TAG'] == tag_sel].iloc[0]
        
        with st.form("f_ed"):
            c1, c2, c3, c4 = st.columns(4)
            def dt_p(v): 
                try: return datetime.strptime(v, "%d/%m/%Y").date()
                except: return None
            v_prev = c1.date_input("Previsto", dt_p(dados['PREVISTO']), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início", dt_p(dados['DATA INIC PROG']), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim", dt_p(dados['DATA FIM PROG']), format="DD/MM/YYYY")
            v_mont = c4.date_input("Montagem", dt_p(dados['DATA MONT']), format="DD/MM/YYYY")
            v_obs = st.text_input("OBS:", value=dados['OBS'])
            if st.form_submit_button("💾 SALVAR"):
                # Otimização: Batch Update da linha
                row_idx = df_atual.index[df_atual['TAG'] == tag_sel][0] + 2
                vals = [v_prev.strftime("%d/%m/%Y") if v_prev else "", v_ini.strftime("%d/%m/%Y") if v_ini else "", 
                        v_fim.strftime("%d/%m/%Y") if v_fim else "", v_mont.strftime("%d/%m/%Y") if v_mont else "", v_obs]
                # Mapeia colunas e atualiza
                for i, col in enumerate(['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']):
                    c_idx = df_atual.columns.get_loc(col) + 1
                    ws_atual.update_cell(row_idx, c_idx, vals[i])
                st.cache_resource.clear(); st.success("Salvo!"); st.rerun()

        st.divider()
        c_aux1, c_aux2 = st.columns(2)
        with c_aux2: # Deleção Segura
            t_del = st.selectbox("Deletar:", [""] + sorted(df_atual['TAG'].tolist()), key="del_z")
            if st.button("🔴 EXCLUIR") and t_del:
                cell = ws_atual.find(t_del, in_column=1)
                if cell: 
                    ws_atual.delete_rows(cell.row)
                    st.cache_resource.clear(); st.rerun()
        
        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'PREVISTO', 'STATUS', 'OBS']], use_container_width=True)

    elif aba == "📊 CURVA S":
        # Curva S Otimizada
        df_c = df_atual.copy()
        df_c['DT_M'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_P'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')
        res = df_c['DT_P'].dt.to_period('M').value_counts().sort_index().cumsum()
        fig = go.Figure(go.Scatter(x=[str(i) for i in res.index], y=res.values, name="Previsto", line=dict(color='green')))
        st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📋 Relatórios")
        # Mantendo estrutura de 3 blocos original
        st.write("### Programação")
        df_p = df_atual[df_atual['STATUS'] == "PROGRAMADO"]
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO']], hide_index=True)
        
        st.write("### Pendências")
        df_pend = df_atual[df_atual['STATUS'] != "MONTADO"]
        st.dataframe(df_pend[['TAG', 'STATUS', 'PREVISTO']], hide_index=True)
        
        st.write("### Avanço Semanal")
        sem = st.selectbox("Semana:", sorted(df_atual['SEMANA OBRA'].unique(), reverse=True))
        df_s = df_atual[(df_atual['SEMANA OBRA'] == sem) & (df_atual['STATUS'] == "MONTADO")]
        st.dataframe(df_s, hide_index=True)
        if not df_s.empty:
            st.download_button("📥 Exportar Semana", exportar_excel_com_cabecalho(df_s, f"Semana {sem}"), "rel.xlsx")

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        c1, c2, c3 = st.columns(3)
        with c2: # Importação com Identificador de Falhas
            up = st.file_uploader("Excel:")
            if up and st.button("🚀 IMPORTAR"):
                df_up = pd.read_excel(up).astype(str)
                lista_m = ws_atual.get_all_values()
                sucesso, falhas = 0, []
                for _, r in df_up.iterrows():
                    tag_i = r['TAG'].strip()
                    achou = False
                    for i, row in enumerate(lista_m):
                        if row[0] == tag_i:
                            # Atualiza colunas (exemplo simplificado p/ velocidade)
                            lista_m[i][1] = r.get('SEMANA OBRA', row[1]) 
                            sucesso += 1; achou = True; break
                    if not achou: falhas.append(tag_i)
                if sucesso: ws_atual.update('A1', lista_m); st.success(f"Atualizado: {sucesso}")
                if falhas: st.warning(f"Não encontradas: {len(falhas)}"); st.code(", ".join(falhas))
        with c3:
            st.download_button("📥 BASE COMPLETA", exportar_excel_com_cabecalho(df_atual, "BASE"), "base.xlsx")
