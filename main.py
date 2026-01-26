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

st.markdown("""
    <style>
    [data-testid="stSidebar"] [data-testid="stImage"] { padding: 0px !important; margin-top: -60px !important; margin-left: -20px !important; margin-right: -20px !important; width: calc(100% + 40px) !important; }
    [data-testid="stSidebar"] [data-testid="stImage"] img { width: 100% !important; height: auto !important; border-radius: 0px !important; }
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
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
    st.markdown("<h3 style='text-align: center;'>Escolha a Disciplina para iniciar:</h3>", unsafe_allow_html=True)
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
            col_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO', 'FAMÍLIA', 'UNIDADE', 'CONTRATO', 'PREVISTO']
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
if st.sidebar.button("🔄 TROCAR DISCIPLINA"):
    st.session_state['disciplina_ativa'] = None
    st.rerun()

aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        c_tag, c_sem = st.columns([2, 1])
        with c_tag:
            tag_sel = st.selectbox("Selecione para EDITAR:", sorted(df_atual['TAG'].unique()))
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
            v_prev = c1.date_input("Data Previsto", value=conv_dt(dados_tag.get('PREVISTO', ''), None), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", value=conv_dt(dados_tag['DATA INIC PROG'], sug_ini), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", value=conv_dt(dados_tag['DATA FIM PROG'], sug_fim), format="DD/MM/YYYY")
            v_mont = c4.date_input("Data Montagem", value=conv_dt(dados_tag['DATA MONT'], None), format="DD/MM/YYYY")
            st.info(f"Status Atual: **{dados_tag['STATUS']}**")
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
                f_prev = v_prev.strftime("%d/%m/%Y") if v_prev else ""
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                st_at = calcular_status_tag(f_ini, f_fim, f_mont)
                updates = {'SEMANA OBRA': sem_input, 'PREVISTO': f_prev, 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_at, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], str(val))
                st.cache_resource.clear()
                st.rerun()

        st.divider()
        col_cad, col_del = st.columns(2)
        with col_cad:
            with st.expander("➕ CADASTRAR NOVO TAG"):
                with st.form("form_novo_tag_completo"):
                    n_tag = st.text_input("TAG *")
                    n_desc = st.text_input("Descrição")
                    c_n1, c_n2 = st.columns(2)
                    n_area = c_n1.text_input("Área")
                    n_doc = c_n2.text_input("Documento")
                    n_fam = c_n1.text_input("Família")
                    n_uni = c_n2.text_input("Unidade")
                    if st.form_submit_button("🚀 CADASTRAR TAG", use_container_width=True):
                        if n_tag:
                            nova_linha = [n_tag, "", "", "", "", "", "AGUARDANDO PROG", disc, n_desc, n_area, n_doc, n_fam, "", n_uni, "", "", ""]
                            ws_atual.append_row(nova_linha)
                            st.success(f"✅ TAG {n_tag} cadastrada com sucesso!")
                            st.cache_resource.clear()
                            # Rerun removido para manter a mensagem de sucesso visível
                        else: st.error("O campo TAG é obrigatório.")
        with col_del:
            with st.expander("🗑️ DELETAR TAG DO BANCO"):
                tag_para_del = st.selectbox("Selecione a TAG para DELETAR:", [""] + sorted(df_atual['TAG'].unique().tolist()), key="del_box")
                conf_del = st.checkbox("Confirmar exclusão definitiva")
                if st.button("🔴 EXCLUIR TAG SELECIONADA") and tag_para_del and conf_del:
                    cell = ws_atual.find(tag_para_del, in_column=1)
                    if cell:
                        ws_atual.delete_rows(cell.row)
                        st.cache_resource.clear()
                        st.rerun()

        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)

    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S e Avanço - {disc}")
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per_real = (montados / total_t * 100) if total_t > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric("Avanço Total Realizado", f"{per_real:.2f}%")
        c2.progress(per_real / 100)
        df_c = df_atual.copy()
        df_c['DT_REAL'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_PREV'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')
        prev_mes = df_c['DT_PREV'].dt.to_period('M').value_counts().sort_index()
        real_mes = df_c['DT_REAL'].dt.to_period('M').value_counts().sort_index()
        todos_meses = sorted(list(set(prev_mes.index.tolist() + real_mes.index.tolist())))
        x_eixo = [str(m) for m in todos_meses]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x_eixo, y=prev_mes.reindex(todos_meses, fill_value=0).cumsum(), name='LB - Prev. Acumulado', line=dict(color='#27ae60', width=4)))
        fig.add_trace(go.Scatter(x=x_eixo, y=real_mes.reindex(todos_meses, fill_value=0).cumsum(), name='Real. Acumulado', line=dict(color='#e74c3c', width=4)))
        fig.update_layout(template="plotly_dark", height=500)
        st.plotly_chart(fig, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df_atual)); m2.metric("Montados ✅", len(df_atual[df_atual['STATUS']=='MONTADO']))
        m3.metric("Programados 📅", len(df_atual[df_atual['STATUS']=='PROGRAMADO'])); m4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS']=='AGUARDANDO PROG']))
        
        st.divider()
        st.markdown("### 📅 PROGRAMADO PRODUÇÃO")
        sem_prog = sorted(df_atual[df_atual['STATUS'] == 'PROGRAMADO']['SEMANA OBRA'].unique())
        s_sel_p = st.selectbox("Filtrar Programação por Semana:", ["TODAS"] + sem_prog)
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        if s_sel_p != "TODAS": df_p = df_p[df_p['SEMANA OBRA'] == s_sel_p]
        st.dataframe(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']], use_container_width=True, hide_index=True)
        if not df_p.empty:
            st.download_button("📥 EXPORTAR PROGRAMADO", exportar_excel_com_cabecalho(df_p[['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']], "PROGRAMAÇÃO"), f"Prog_{disc}.xlsx", use_container_width=True)

        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS TOTAIS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        st.dataframe(df_pend[['TAG', 'DESCRIÇÃO', 'ÁREA', 'STATUS', 'PREVISTO', 'OBS']], use_container_width=True, hide_index=True)
        if not df_pend.empty:
            st.download_button("📥 EXPORTAR PENDÊNCIAS", exportar_excel_com_cabecalho(df_pend[['TAG', 'DESCRIÇÃO', 'ÁREA', 'STATUS', 'PREVISTO', 'OBS']], "PENDENCIAS"), f"Pendencias_{disc}.xlsx", use_container_width=True)

        st.divider()
        st.markdown("### 📈 AVANÇO POR SEMANA (REALIZADO)")
        s_disp = sorted(df_atual['SEMANA OBRA'].unique(), reverse=True)
        s_sel = st.selectbox("Selecione a Semana de Montagem:", s_disp if s_disp else ["-"])
        df_sem = df_atual[(df_atual['SEMANA OBRA'] == s_sel) & (df_atual['STATUS'] == 'MONTADO')]
        st.dataframe(df_sem[['TAG', 'DESCRIÇÃO', 'DATA MONT', 'ÁREA', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)
        if not df_sem.empty:
            st.download_button(f"📥 EXPORTAR SEMANA {s_sel}", exportar_excel_com_cabecalho(df_sem[['TAG', 'DESCRIÇÃO', 'DATA MONT', 'ÁREA', 'STATUS', 'OBS']], f"AVANÇO SEMANA {s_sel}"), f"Avanco_Sem_{s_sel}.xlsx", use_container_width=True)

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader(f"📤 Exportação e Importação - {disc}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 MODELO")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 MODELO PLANILHA", b_m.getvalue(), "modelo.xlsx", use_container_width=True)
        with c2:
            st.info("🚀 IMPORTAÇÃO")
            up = st.file_uploader("Upload Excel:", type="xlsx")
            if up and st.button("🚀 IMPORTAR E ATUALIZAR", use_container_width=True):
                df_up = pd.read_excel(up).astype(str)
                df_up.columns = [str(c).strip().upper() for c in df_up.columns]
                lista_m = ws_atual.get_all_values()
                headers = [h.strip().upper() for h in lista_m[0]]
                idx_m = {n: i for i, n in enumerate(headers)}
                sucesso, falhas = 0, []
                for _, r in df_up.iterrows():
                    t_imp = str(r.get('TAG','')).strip()
                    if t_imp in ['nan', '']: continue
                    achou = False
                    for i, row in enumerate(lista_m[1:]):
                        if str(row[0]).strip() == t_imp:
                            for col in ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']:
                                if col.upper() in df_up.columns:
                                    val = str(r[col.upper()]).strip()
                                    if val.lower() in ['nan','nat','none']: val = ''
                                    lista_m[i+1][idx_m[col.upper()]] = val
                            sucesso += 1; achou = True; break
                    if not achou: falhas.append(t_imp)
                if sucesso: ws_atual.update('A1', lista_m); st.success(f"{sucesso} TAGs atualizadas!")
                if falhas: st.warning(f"⚠️ {len(falhas)} TAGs não encontradas:"); st.code(", ".join(falhas))
        with c3:
            st.info("💾 BASE COMPLETA")
            df_exp = df_atual.copy()
            for col in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT']:
                if col in df_exp.columns:
                    df_exp[col] = pd.to_datetime(df_exp[col], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').replace('NaT', '')
            st.download_button("📥 EXPORTAR BASE", exportar_excel_com_cabecalho(df_exp, f"BASE {disc}"), f"Base_{disc}.xlsx", use_container_width=True)
