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

# --- FUNÇÃO PARA GERAR EXCEL COM CABEÇALHO ---
def exportar_excel_com_cabecalho(df, titulo_relatorio):
    if df.empty:
        return None
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Relatorio', startrow=8)
        workbook  = writer.book
        worksheet = writer.sheets['Relatorio']
        fmt_titulo = workbook.add_format({'bold': True, 'font_size': 14, 'align': 'center', 'valign': 'vcenter'})
        fmt_sub = workbook.add_format({'font_size': 10, 'italic': True})
        try:
            worksheet.insert_image('A1', 'LOGO2.png', {'x_scale': 0.4, 'y_scale': 0.4})
        except:
            pass
        worksheet.merge_range('C3:F5', titulo_relatorio.upper(), fmt_titulo)
        worksheet.write('A7', f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_sub)
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 3
            worksheet.set_column(i, i, column_len)
    return output.getvalue()

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'disciplina_ativa' not in st.session_state: st.session_state['disciplina_ativa'] = None

# --- ESTILO ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] [data-testid="stImage"] { padding: 0px !important; margin-top: -60px !important; margin-left: -20px !important; margin-right: -20px !important; width: calc(100% + 40px) !important; }
    [data-testid="stSidebar"] [data-testid="stImage"] img { width: 100% !important; height: auto !important; border-radius: 0px !important; }
    .stDateInput div, .stTextInput div, .stNumberInput div, .stSelectbox div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

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
    col1, col2, col3 = st.columns(3)
    if col1.button("⚡ ELÉTRICA", use_container_width=True):
        st.session_state['disciplina_ativa'] = "ELÉTRICA"; st.rerun()
    if col2.button("🔧 INSTRUMENTAÇÃO", use_container_width=True):
        st.session_state['disciplina_ativa'] = "INSTRUMENTAÇÃO"; st.rerun()
    if col3.button("🏗️ ESTRUTURA", use_container_width=True):
        st.session_state['disciplina_ativa'] = "ESTRUTURA"; st.rerun()
    st.stop()

if not st.session_state['logado']: tela_login()
if not st.session_state['disciplina_ativa']: tela_selecao_disciplina()

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
            # Garante que todas as colunas necessárias existam
            cols_nec = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO', 'FAMÍLIA', 'UNIDADE', 'PREVISTO']
            for c in cols_nec:
                if c not in df.columns: df[c] = ""
            df = df.replace(['nan', 'None', 'NaT', '-'], '')
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

# CARGA DE DADOS
disc = st.session_state['disciplina_ativa']
planilha_nome = {"ELÉTRICA": "BD_ELE", "INSTRUMENTAÇÃO": "BD_INST", "ESTRUTURA": "BD_ESTR"}[disc]
df_atual, ws_atual = extrair_dados(planilha_nome)

st.sidebar.subheader("MENU G-MONT")
st.sidebar.write(f"**Disciplina:** {disc}")
if st.sidebar.button("🔄 TROCAR DISCIPLINA"):
    st.session_state['disciplina_ativa'] = None; st.rerun()

aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição - {disc}")
        tag_sel = st.selectbox("Selecione para EDITAR:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        sem_input = st.text_input("Semana da Obra:", value=dados_tag['SEMANA OBRA'])
        sug_ini, sug_fim = get_dates_from_week(sem_input)
        
        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default
            v_prev = c1.date_input("Previsto", conv_dt(dados_tag.get('PREVISTO',''), None), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", conv_dt(dados_tag['DATA INIC PROG'], sug_ini), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", conv_dt(dados_tag['DATA FIM PROG'], sug_fim), format="DD/MM/YYYY")
            v_mont = c4.date_input("Montagem", conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
                f_ini, f_fim, f_mont = v_ini.strftime("%d/%m/%Y"), v_fim.strftime("%d/%m/%Y"), (v_mont.strftime("%d/%m/%Y") if v_mont else "")
                st_at = calcular_status_tag(f_ini, f_fim, f_mont)
                updates = {'SEMANA OBRA': sem_input, 'PREVISTO': v_prev.strftime("%d/%m/%Y") if v_prev else "", 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_at, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], str(val))
                st.toast("✅ Alterações salvas com sucesso!"); st.cache_resource.clear(); st.rerun()

        st.divider()
        col_cad, col_del = st.columns(2)
        with col_cad:
            with st.expander("➕ CADASTRAR NOVO TAG", expanded=False):
                with st.form("form_novo_tag"):
                    n_tag = st.text_input("TAG *")
                    n_desc = st.text_input("Descrição")
                    c_n1, c_n2 = st.columns(2)
                    n_area = c_n1.text_input("Área")
                    n_doc = c_n2.text_input("Documento")
                    n_fam = c_n1.text_input("Família")
                    n_uni = c_n2.text_input("Unidade")
                    
                    if st.form_submit_button("🚀 CADASTRAR TAG", use_container_width=True):
                        if n_tag:
                            # Monta a linha baseada nas colunas do seu Google Sheets (ajustado para a imagem)
                            nova_linha = [n_tag, "", "", "", "", "", "AGUARDANDO PROG", disc, n_desc, n_area, n_doc, n_fam, "", n_uni, "", "", ""]
                            ws_atual.append_row(nova_linha)
                            st.success(f"✅ TAG {n_tag} cadastrada com sucesso!")
                            st.cache_resource.clear()
                            # Removido rerun imediato para mostrar a mensagem verde
                        else: st.error("Erro: O campo TAG é obrigatório.")

        with col_del:
            with st.expander("🗑️ DELETAR TAG DO BANCO", expanded=False):
                tag_para_del = st.selectbox("TAG para DELETAR:", [""] + sorted(df_atual['TAG'].unique().tolist()))
                conf_del = st.checkbox("Confirmo a exclusão")
                if st.button("🔴 EXCLUIR DEFINITIVO") and tag_para_del and conf_del:
                    cell = ws_atual.find(tag_para_del, in_column=1)
                    if cell:
                        ws_atual.delete_rows(cell.row)
                        st.toast(f"🗑️ TAG {tag_para_del} removida."); st.cache_resource.clear(); st.rerun()

        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S - {disc}")
        df_c = df_atual.copy()
        df_c['DT_P'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')
        df_c['DT_R'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        prev_acum = df_c['DT_P'].dt.to_period('M').value_counts().sort_index().cumsum()
        real_acum = df_c['DT_R'].dt.to_period('M').value_counts().sort_index().cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[str(x) for x in prev_acum.index], y=prev_acum.values, name="Previsto", line=dict(color='green', width=3)))
        fig.add_trace(go.Scatter(x=[str(x) for x in real_acum.index], y=real_acum.values, name="Realizado", line=dict(color='red', width=3)))
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        # Programação
        st.markdown("### 📅 PROGRAMADO")
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA']], use_container_width=True, hide_index=True)
        
        # Pendências
        st.markdown("### 🚩 PENDÊNCIAS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        st.dataframe(df_pend[['TAG', 'DESCRIÇÃO', 'STATUS', 'PREVISTO']], use_container_width=True, hide_index=True)
        
        # Avanço Semanal
        st.markdown("### 📈 AVANÇO POR SEMANA")
        sem_sel = st.selectbox("Escolha a Semana:", sorted(df_atual['SEMANA OBRA'].unique(), reverse=True))
        df_sem = df_atual[(df_atual['SEMANA OBRA'] == sem_sel) & (df_atual['STATUS'] == 'MONTADO')]
        st.dataframe(df_sem[['TAG', 'DESCRIÇÃO', 'DATA MONT']], use_container_width=True, hide_index=True)
        if not df_sem.empty:
            st.download_button("📥 Exportar Excel", exportar_excel_com_cabecalho(df_sem, f"AVANCO SEMANA {sem_sel}"), f"Semana_{sem_sel}.xlsx")

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader("📤 Movimentação de Dados")
        c1, c2 = st.columns(2)
        with c1:
            st.info("🚀 IMPORTAÇÃO")
            up = st.file_uploader("Subir Excel:", type="xlsx")
            if up and st.button("EXECUTAR ATUALIZAÇÃO"):
                df_up = pd.read_excel(up).astype(str)
                lista_m = ws_atual.get_all_values()
                sucesso = 0
                for _, r in df_up.iterrows():
                    for i, row in enumerate(lista_m):
                        if row[0] == str(r['TAG']).strip():
                            # Atualiza as colunas de datas/obs
                            for col in ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']:
                                if col in df_up.columns:
                                    col_idx = df_atual.columns.get_loc(col)
                                    lista_m[i][col_idx] = str(r[col]).replace('nan','')
                            sucesso += 1; break
                if sucesso:
                    ws_atual.update('A1', lista_m); st.success(f"🚀 {sucesso} TAGs atualizadas!")
                    st.cache_resource.clear()
        with c2:
            st.info("💾 EXPORTAR BASE")
            st.download_button("📥 BAIXAR EXCEL COMPLETO", exportar_excel_com_cabecalho(df_atual, "BASE COMPLETA"), "Base_G-MONT.xlsx")
