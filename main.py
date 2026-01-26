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

st.markdown("""
    <style>
    [data-testid="stSidebar"] [data-testid="stImage"] { padding: 0px !important; margin-top: -60px !important; margin-left: -20px !important; }
    [data-testid="stSidebar"] [data-testid="stImage"] img { width: 100% !important; height: auto !important; }
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

df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")
df_est, ws_est = extrair_dados("BD_ESTR")

disc = st.session_state['disciplina_ativa']
if disc == "ELÉTRICA": df_atual, ws_atual = df_ele, ws_ele
elif disc == "INSTRUMENTAÇÃO": df_atual, ws_atual = df_ins, ws_ins
else: df_atual, ws_atual = df_est, ws_est

st.sidebar.subheader("MENU G-MONT")
st.sidebar.write(f"**Disciplina:** {disc}")
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}
    cfg_rel = {"TAG": st.column_config.TextColumn(width="medium"), "DESCRIÇÃO": st.column_config.TextColumn(width="large")}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        tag_sel = st.selectbox("Selecione para EDITAR:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default
            v_prev = c1.date_input("Previsto", conv_dt(dados_tag['PREVISTO'], None), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", conv_dt(dados_tag['DATA INIC PROG'], None), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", conv_dt(dados_tag['DATA FIM PROG'], None), format="DD/MM/YYYY")
            v_mont = c4.date_input("Montagem", conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            if st.form_submit_button("💾 SALVAR"):
                updates = {'PREVISTO': v_prev.strftime("%d/%m/%Y") if v_prev else "", 'DATA INIC PROG': v_ini.strftime("%d/%m/%Y") if v_ini else "", 'DATA FIM PROG': v_fim.strftime("%d/%m/%Y") if v_fim else "", 'DATA MONT': v_mont.strftime("%d/%m/%Y") if v_mont else "", 'OBS': v_obs}
                for col, val in updates.items(): ws_atual.update_cell(idx_base+2, cols_map[col], str(val))
                st.cache_resource.clear(); st.success("Salvo!"); st.rerun()

        st.divider()
        col_cad, col_del = st.columns(2)
        with col_cad:
            with st.expander("➕ CADASTRAR NOVO"):
                with st.form("f_novo"):
                    n_tag = st.text_input("TAG *")
                    if st.form_submit_button("CADASTRAR"):
                        ws_atual.append_row([n_tag, "", "", "", "", "", "AGUARDANDO PROG", disc, "", "", "", "", "", "", "", "", ""])
                        st.cache_resource.clear(); st.rerun()
        
        with col_del:
            with st.expander("🗑️ DELETAR TAG"):
                tag_del = st.selectbox("TAG para Deletar:", [""] + sorted(df_atual['TAG'].unique().tolist()), key="sb_del")
                conf = st.checkbox("Confirmar exclusão", key="ck_del")
                if st.button("🔴 EXCLUIR DEFINITIVO") and conf and tag_del:
                    cell = ws_atual.find(tag_del, in_column=1)
                    if cell:
                        ws_atual.delete_rows(cell.row)
                        st.cache_resource.clear()
                        for k in ["sb_del", "ck_del"]: 
                            if k in st.session_state: del st.session_state[k]
                        st.rerun()

        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📊 CURVA S":
        st.subheader("📊 Curva S")
        st.info("Visualização de progresso baseada em datas de montagem.")

    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        st.markdown("### 📈 AVANÇO POR SEMANA")
        semanas = sorted(df_atual['SEMANA OBRA'].unique(), reverse=True)
        sem_sel = st.selectbox("Selecione a Semana:", semanas if semanas else ["-"])
        df_sem = df_atual[(df_atual['SEMANA OBRA'] == sem_sel) & (df_atual['STATUS'] == 'MONTADO')]
        st.dataframe(df_sem, use_container_width=True, hide_index=True)
        
        if not df_sem.empty:
            excel_sem = exportar_excel_com_cabecalho(df_sem, f"RELATORIO_SEM_{sem_sel}")
            st.download_button("📥 EXPORTAR EXCEL", excel_sem, f"Semana_{sem_sel}.xlsx")
        else:
            st.warning("Sem dados para exportar nesta semana.")

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader("📤 Exportação e Importação")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 MODELO")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 BAIXAR MODELO", b_m.getvalue(), "modelo.xlsx")
            
        with c2:
            st.info("🚀 IMPORTAÇÃO")
            up = st.file_uploader("Upload Excel:", type="xlsx")
            if up and st.button("IMPORTAR"):
                df_up = pd.read_excel(up).astype(str)
                df_up.columns = [str(c).strip().upper() for c in df_up.columns]
                lista_m = ws_atual.get_all_values()
                headers = [h.strip().upper() for h in lista_m[0]]
                idx_m = {n: i for i, n in enumerate(headers)}
                sucesso, falhas = 0, []
                for _, r in df_up.iterrows():
                    tag_i = str(r.get('TAG','')).strip()
                    achou = False
                    for i, row in enumerate(lista_m[1:]):
                        if str(row[0]).strip() == tag_i:
                            for c in ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']:
                                if c.upper() in df_up.columns:
                                    val = str(r[c.upper()]).strip()
                                    if val.lower() in ['nan','nat','none']: val = ''
                                    lista_m[i+1][idx_m[c.upper()]] = val
                            sucesso += 1; achou = True; break
                    if not achou: falhas.append(tag_i)
                if sucesso: ws_atual.update('A1', lista_m); st.success(f"{sucesso} atualizados!")
                if falhas: st.warning(f"{len(falhas)} não encontradas:"); st.code(", ".join(falhas))

        with c3:
            st.info("💾 BASE COMPLETA")
            df_exp = df_atual.copy()
            for c in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT']:
                if c in df_exp.columns:
                    df_exp[c] = pd.to_datetime(df_exp[c], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').replace('NaT', '')
            excel_full = exportar_excel_com_cabecalho(df_exp, f"BASE COMPLETA {disc}")
            st.download_button("📥 EXPORTAR BASE", excel_full, f"Base_{disc}.xlsx")
