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
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try:
            st.image("LOGO2.png", width=200)
        except:
            pass
        st.subheader("🔐 ACESSO RESTRITO G-MONT")
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA", use_container_width=True):
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
            col_obj = ['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO', 'PREVISTO']
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

# --- CARREGAMENTO DAS DISCIPLINAS ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")
df_est, ws_est = extrair_dados("BD_ESTR") # <--- Nova planilha: BD_ESTR

# --- SIDEBAR ---
try:
    st.sidebar.image("LOGO2.png", width=120)
except:
    st.sidebar.markdown("### G-MONT")

st.sidebar.subheader("MENU G-MONT")
disc = st.sidebar.selectbox("DISCIPLINA:", ["ELÉTRICA", "INSTRUMENTAÇÃO", "ESTRUTURA"])
aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 GESTÃO DE DADOS"])

st.sidebar.divider()
if st.sidebar.button("🚪 SAIR DO SISTEMA", use_container_width=True):
    st.session_state['logado'] = False
    st.rerun()

# --- DIRECIONAMENTO DE DADOS (FORMA EXPLÍCITA) ---
if disc == "ELÉTRICA":
    df_atual, ws_atual = df_ele, ws_ele
elif disc == "INSTRUMENTAÇÃO":
    df_atual, ws_atual = df_ins, ws_ins
elif disc == "ESTRUTURA":
    df_atual, ws_atual = df_est, ws_est
else:
    # Caso de segurança: se algo der errado, carrega um DF vazio
    df_atual, ws_atual = pd.DataFrame(), None

if not df_atual.empty:
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    cfg_rel = {
        "TAG": st.column_config.TextColumn(width="medium"),
        "DESCRIÇÃO": st.column_config.TextColumn(width="large"),
        "OBS": st.column_config.TextColumn(width="large"),
        "DOCUMENTO": st.column_config.TextColumn(width="medium")
    }

    # --- ABA 1: EDIÇÃO E QUADRO ---
    if aba == "📝 EDIÇÃO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        
        # --- PARTE SUPERIOR: SELEÇÃO E EDIÇÃO ---
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
            
            st_atual = calcular_status_tag(v_ini, v_fim, v_mont)
            st.info(f"Status Atualizado: **{st_atual}**")
            v_obs = st.text_input("Observações:", value=dados_tag['OBS'])
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
                f_prev = v_prev.strftime("%d/%m/%Y") if v_prev else ""
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                
                updates = {'SEMANA OBRA': sem_input, 'PREVISTO': f_prev, 'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': st_atual, 'OBS': v_obs}
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(idx_base + 2, cols_map[col], str(val))
                st.success("Salvo com sucesso!"); st.rerun()

        # --- MEIO: ÁREA DE CADASTRAMENTO E EXCLUSÃO ---
        st.divider()
        col_cad, col_del = st.columns(2)

        with col_cad:
            with st.expander("➕ CADASTRAR TAG", expanded=False):
                with st.form("form_novo_tag"):
                    c1, c2 = st.columns(2)
                    n_tag = c1.text_input("TAG *")
                    n_disc = c2.text_input("DISCIPLINA", value=disc)
                    n_desc = st.text_input("DESCRIÇÃO")
                    
                    c3, c4, c5 = st.columns(3)
                    n_fam = c3.text_input("FAMÍLIA")
                    n_uni = c4.text_input("UNIDADE")
                    n_area = c5.text_input("ÁREA")
                    
                    n_des = st.text_input("DESENHO (DOC)")
                    
                    if st.form_submit_button("🚀 CADASTRAR NO BANCO"):
                        if n_tag:
                            # Montando a linha conforme a estrutura da sua planilha
                            # Ajuste a ordem conforme necessário: TAG, SEMANA, INIC, FIM, PREV, MONT, STATUS, DISC, DESC, AREA, DOC...
                            nova_linha = [n_tag, "", "", "", "", "", "AGUARDANDO PROG", n_disc, n_desc, n_area, n_des, n_fam, "", n_uni, "", "", ""]
                            ws_atual.append_row(nova_linha)
                            st.success(f"TAG {n_tag} cadastrado!"); st.rerun()
                        else:
                            st.error("O campo TAG é obrigatório.")

        with col_del:
            with st.expander("🗑️ DELETAR TAG", expanded=False):
                tag_para_deletar = st.selectbox("Selecione a TAG para DELETAR:", [""] + sorted(df_atual['TAG'].unique().tolist()))
                
                if tag_para_deletar:
                    st.warning(f"🚨 ATENÇÃO: Isso excluirá permanentemente a TAG: {tag_para_deletar}")
                    confirm_del = st.checkbox("Eu confirmo que desejo apagar este registro")
                    
                    # Criando duas colunas para os botões de ação
                    c_btn_del, c_btn_can = st.columns(2)
                    
                    # Botão de Excluir
                    if c_btn_del.button("🔴 CONFIRMAR EXCLUSÃO", use_container_width=True):
                        if confirm_del:
                            try:
                                cell = ws_atual.find(tag_para_deletar, in_column=1)
                                if cell:
                                    ws_atual.delete_rows(cell.row)
                                    st.success(f"TAG {tag_para_deletar} removida com sucesso!")
                                    st.rerun()
                                else:
                                    st.error("TAG não encontrada na planilha.")
                            except Exception as e:
                                st.error(f"Erro ao excluir: {e}")
                        else:
                            st.info("Você precisa marcar a caixa de confirmação acima.")
                    
                    # Botão de Cancelar
                    if c_btn_can.button("⚪ CANCELAR", use_container_width=True):
                        st.info("Operação cancelada.")
                        st.rerun() # Recarrega a página para limpar a seleção e fechar o aviso

        # --- PARTE INFERIOR: QUADRO (DATAFRAME) ---
        st.divider()
        col_dates_cfg = {
            "TAG": st.column_config.TextColumn("TAG", help="Clique e arraste para copiar"),
            "PREVISTO": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA INIC PROG": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA FIM PROG": st.column_config.DateColumn(format="DD/MM/YYYY"),
            "DATA MONT": st.column_config.DateColumn(format="DD/MM/YYYY"),
        }
        st.dataframe(df_atual[['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']], 
                     use_container_width=True, hide_index=True, column_config={**cfg_rel, **col_dates_cfg})

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S e Avanço - {disc}")
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per_real = (montados / total_t * 100) if total_t > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.metric("Avanço Total Realizado", f"{per_real:.2f}%")
        c2.write("Progresso Visual:")
        c2.progress(per_real / 100)

        df_c = df_atual.copy()
        df_c['DT_REAL'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_PREV'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')
        
        prev_mes = df_c['DT_PREV'].dt.to_period('M').value_counts().sort_index()
        real_mes = df_c['DT_REAL'].dt.to_period('M').value_counts().sort_index()
        
        todos_meses = sorted(list(set(prev_mes.index.tolist() + real_mes.index.tolist())))
        x_eixo = [str(m) for m in todos_meses]
        prev_acum = prev_mes.reindex(todos_meses, fill_value=0).cumsum()
        real_acum = real_mes.reindex(todos_meses, fill_value=0).cumsum()

        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_eixo, y=prev_mes.reindex(todos_meses, fill_value=0), name='LB - Previsto Mensal', marker_color='#2ecc71', opacity=0.6))
        fig.add_trace(go.Bar(x=x_eixo, y=real_mes.reindex(todos_meses, fill_value=0), name='Realizado Mensal', marker_color='#3498db', opacity=0.6))
        fig.add_trace(go.Scatter(x=x_eixo, y=prev_acum, name='LB - Prev. Acumulado', line=dict(color='#27ae60', width=4)))
        fig.add_trace(go.Scatter(x=x_eixo, y=real_acum, name='Real. Acumulado', line=dict(color='#e74c3c', width=4)))

        fig.update_layout(template="plotly_dark", barmode='group', height=500, legend=dict(orientation="h", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

    # --- ABA 3: RELATÓRIOS ---
    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", len(df_atual)); m2.metric("Montados ✅", len(df_atual[df_atual['STATUS']=='MONTADO']))
        m3.metric("Programados 📅", len(df_atual[df_atual['STATUS']=='PROGRAMADO'])); m4.metric("Aguardando ⏳", len(df_atual[df_atual['STATUS']=='AGUARDANDO PROG']))
        
        st.divider()
        st.markdown("### 📅 PROGRAMADO PRODUÇÃO")
        df_p = df_atual[df_atual['STATUS'] == 'PROGRAMADO']
        cols_p = ['TAG', 'SEMANA OBRA', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO']
        st.dataframe(df_p[cols_p], use_container_width=True, hide_index=True, column_config=cfg_rel)
        buf_p = BytesIO(); df_p[cols_p].to_excel(buf_p, index=False)
        st.download_button("📥 EXPORTAR PROGRAMAÇÃO", buf_p.getvalue(), f"Programado_{disc}.xlsx")

        st.divider()
        st.markdown("### 🚩 LISTA DE PENDÊNCIAS")
        df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
        cols_pend = ['TAG', 'DESCRIÇÃO', 'ÁREA', 'STATUS', 'PREVISTO', 'OBS']
        cfg_pend_br = {**cfg_rel, "PREVISTO": st.column_config.DateColumn("PREVISTO", format="DD/MM/YYYY")}
        st.dataframe(df_pend[cols_pend], use_container_width=True, hide_index=True, column_config=cfg_pend_br)
        buf_pe = BytesIO(); df_pend[cols_pend].to_excel(buf_pe, index=False)
        st.download_button("📥 EXPORTAR PENDÊNCIAS", buf_pe.getvalue(), f"Pendencias_{disc}.xlsx")

        st.divider()
        st.markdown("### 📈 AVANÇO SEMANAL (REALIZADO)")
        semanas_disponiveis = sorted(df_atual['SEMANA OBRA'].unique(), reverse=True)
        semana_sel = st.selectbox("Selecione a Semana:", semanas_disponiveis if len(semanas_disponiveis) > 0 else ["-"])
        df_semana = df_atual[(df_atual['SEMANA OBRA'] == semana_sel) & (df_atual['STATUS'] == 'MONTADO')]
        cols_av = ['TAG', 'DESCRIÇÃO', 'DATA MONT', 'ÁREA', 'STATUS', 'OBS']
        st.dataframe(df_semana[cols_av], use_container_width=True, hide_index=True, column_config={**cfg_rel, "DATA MONT": st.column_config.DateColumn(format="DD/MM/YYYY")})
        buf_r = BytesIO(); df_semana[cols_av].to_excel(buf_r, index=False)
        st.download_button(f"📥 EXPORTAR SEMANA {semana_sel}", buf_r.getvalue(), f"Avanco_Semana_{semana_sel}_{disc}.xlsx")

   # --- ABA 4: EXPORTAÇÃO E IMPORTAÇÕES ---
    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader(f"📤 Exportações e Importações - {disc}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 **MODELO**")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 EXPORTAR MOD PLANILHA", b_m.getvalue(), "modelo_gmont.xlsx", use_container_width=True)
        
        with c2:
            st.info("🚀 **IMPORTAÇÃO**")
            up = st.file_uploader("Upload Excel:", type="xlsx", label_visibility="collapsed")
            if up:
                if st.button("🚀 IMPORTAR E LIMPAR DADOS", use_container_width=True):
                    try:
                        df_up = pd.read_excel(up).astype(str)
                        df_up.columns = [str(c).strip().upper() for c in df_up.columns]
                        lista_mestra = ws_atual.get_all_values()
                        headers = [str(h).strip().upper() for h in lista_mestra[0]]
                        idx_map = {name: i for i, name in enumerate(headers)}
                        
                        sucesso = 0
                        colunas_alvo = ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']

                        for _, r in df_up.iterrows():
                            tag_import = str(r.get('TAG', '')).strip()
                            if tag_import in ['', 'nan', 'None']: continue
                            for i, row in enumerate(lista_mestra[1:]):
                                if str(row[0]).strip() == tag_import:
                                    for col in colunas_alvo:
                                        if col.upper() in df_up.columns and col.upper() in idx_map:
                                            val = str(r[col.upper()]).strip()
                                            if val.lower() in ['nan', 'none', 'nat', '0', 'dd/mm/yyyy']: val = ''
                                            lista_mestra[i+1][idx_map[col.upper()]] = val
                                    sucesso += 1; break

                        if sucesso > 0:
                            ws_atual.update('A1', lista_mestra)
                            st.success(f"✅ {sucesso} TAGs atualizadas!"); st.rerun()
                    except Exception as e: st.error(f"❌ Erro: {e}")
        
        with c3:
            st.info("💾 **BASE COMPLETA**")
            b_f = BytesIO(); df_atual.to_excel(b_f, index=False)
            st.download_button("📥 EXPORTAR BASE", b_f.getvalue(), f"Base_{disc}.xlsx", use_container_width=True)
