import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.graph_objects as go
from io import BytesIO
from datetime import datetime, timedelta
import time # Importado para controlar o tempo de exibição da mensagem

# --- CONFIGURAÇÃO E DATA BASE DA OBRA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
DATA_INICIO_OBRA = datetime(2025, 9, 29) 

# --- FUNÇÃO PARA GERAR EXCEL (COM CACHE PARA PERFORMANCE) ---
@st.cache_data
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
        except: pass
        worksheet.merge_range('C3:F5', titulo_relatorio.upper(), fmt_titulo)
        worksheet.write('A7', f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_sub)
        for i, col in enumerate(df.columns):
            column_len = max(df[col].astype(str).map(len).max(), len(col)) + 3
            worksheet.set_column(i, i, column_len)
    return output.getvalue()

# --- CONTROLE DE ACESSO E DISCIPLINAS ---
if 'logado' not in st.session_state: st.session_state['logado'] = False
if 'disciplina_ativa' not in st.session_state: st.session_state['disciplina_ativa'] = None

# --- CSS PARA LOGO NA SIDEBAR ---
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
        # O Streamlit Cloud já validou o e-mail; aqui pedimos o PIN de segurança
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA", use_container_width=True):
            if pin == "2026": # Ajuste o PIN se desejar
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()

# --- VERIFICAÇÃO DE LOGIN ---
if not st.session_state['logado']:
    tela_login()

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

@st.cache_data(ttl=600)
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
            df = df.apply(lambda x: x.astype(str).str.strip().replace(['nan', 'None', 'NaT', '-'], ''))
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

# --- CARREGAMENTO DAS DISCIPLINAS ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")
df_est, ws_est = extrair_dados("BD_ESTR")

try: st.sidebar.image("LOGO2.png", width=120)
except: st.sidebar.markdown("### G-MONT")

disc = st.session_state['disciplina_ativa']
st.sidebar.subheader("MENU G-MONT")
st.sidebar.write(f"**Disciplina:** {disc}")
if st.sidebar.button("🔄 TROCAR DISCIPLINA"):
    st.session_state['disciplina_ativa'] = None
    st.rerun()

aba = st.sidebar.radio("NAVEGAÇÃO:", ["📝 EDIÇÃO/PROGRAMAÇÃO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 EXPORTAÇÃO E IMPORTAÇÕES"])
if st.sidebar.button("🚪 SAIR", use_container_width=True):
    st.session_state['logado'] = False  # Volta para a tela de PIN
    st.session_state['disciplina_ativa'] = None # Reseta a escolha da disciplina
    st.rerun()

map_planilhas = {"ELÉTRICA": "BD_ELE", "INSTRUMENTAÇÃO": "BD_INST", "ESTRUTURA": "BD_ESTR"}

if disc == "ELÉTRICA": df_atual, ws_atual = df_ele, ws_ele
elif disc == "INSTRUMENTAÇÃO": df_atual, ws_atual = df_ins, ws_ins
elif disc == "ESTRUTURA": df_atual, ws_atual = df_est, ws_est
else: df_atual, ws_atual = pd.DataFrame(), None

if not df_atual.empty:
    cond_montado = (df_atual['DATA MONT'] != "") & (df_atual['DATA MONT'] != "DD/MM/YYYY")
    cond_prog = ((df_atual['DATA INIC PROG'] != "") | (df_atual['DATA FIM PROG'] != "")) & ~cond_montado
    df_atual['STATUS'] = "AGUARDANDO PROG"
    df_atual.loc[cond_prog, 'STATUS'] = "PROGRAMADO"
    df_atual.loc[cond_montado, 'STATUS'] = "MONTADO"

    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}
    cfg_rel = {"TAG": st.column_config.TextColumn(width="medium"), "DESCRIÇÃO": st.column_config.TextColumn(width="large"), "OBS": st.column_config.TextColumn(width="large"), "DOCUMENTO": st.column_config.TextColumn(width="medium")}

    if aba == "📝 EDIÇÃO/PROGRAMAÇÃO":
        st.subheader(f"📝 Edição por TAG - {disc}")
        c_tag, c_sem = st.columns([2, 1])
        with c_tag: 
            tag_sel = st.selectbox("Selecione para EDITAR:", sorted(df_atual['TAG'].unique()))
        
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with c_sem: 
            sem_input = st.text_input("Semana da Obra:", value=dados_tag.get('SEMANA OBRA', ''))
        
        sug_ini, sug_fim = get_dates_from_week(sem_input)
        
        with st.form("form_edit_final"):
            def conv_dt(val, default):
                try: return datetime.strptime(str(val), "%d/%m/%Y").date()
                except: return default

            # CAMPOS COMUNS (Programação)
            c1, c2, c3 = st.columns(3)
            v_prev = c1.date_input("Data Previsto", value=conv_dt(dados_tag.get('PREVISTO', ''), None), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", value=conv_dt(dados_tag.get('DATA INIC PROG', ''), sug_ini), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", value=conv_dt(dados_tag.get('DATA FIM PROG', ''), sug_fim), format="DD/MM/YYYY")
            
            # LÓGICA EXCLUSIVA PARA ESTRUTURA METÁLICA
            if disc == "ESTRUTURA":
                c4, c5, c6, c7 = st.columns(4)
                v_fab = c4.date_input("Data Fabricação", value=conv_dt(dados_tag.get('DATA FABRICAÇÃO', ''), None), format="DD/MM/YYYY")
                v_pin = c5.date_input("Data Pintura", value=conv_dt(dados_tag.get('DATA PINTURA', ''), None), format="DD/MM/YYYY")
                v_mont = c6.date_input("Data Montagem", value=conv_dt(dados_tag.get('DATA MONT', ''), None), format="DD/MM/YYYY")
                v_torq = c7.date_input("Data Torque", value=conv_dt(dados_tag.get('DATA TARQUE', ''), None), format="DD/MM/YYYY")
                
                # Regra de Status ESTRUTURA
                if v_torq: st_atual = "Concluído"
                elif v_mont: st_atual = "Aguardando Torque"
                elif v_fab: st_atual = "Aguardando Pintura/Montagem"
                elif v_ini: st_atual = "Aguardando Fab"
                else: st_atual = "Aguardando Prog"
            
            else:
                # LÓGICA PARA ELÉTRICA / INSTRUMENTAÇÃO (Original)
                v_mont = st.date_input("Data Montagem", value=conv_dt(dados_tag.get('DATA MONT', ''), None), format="DD/MM/YYYY")
                st_atual = calcular_status_tag(v_ini, v_fim, v_mont)
                v_fab = v_pin = v_torq = None # Evita erro de variável inexistente

            st.info(f"Status Atualizado: **{st_atual}**")
            v_obs = st.text_input("Observações:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES", use_container_width=True):
                ws_escrita = client.open(map_planilhas[disc]).get_worksheet(0)
                
                # Formata datas base
                f_dates = {
                    'PREVISTO': v_prev.strftime("%d/%m/%Y") if v_prev else "",
                    'DATA INIC PROG': v_ini.strftime("%d/%m/%Y") if v_ini else "",
                    'DATA FIM PROG': v_fim.strftime("%d/%m/%Y") if v_fim else "",
                    'DATA MONT': v_mont.strftime("%d/%m/%Y") if v_mont else ""
                }
                
                # Adiciona colunas extras apenas se for ESTRUTURA
                if disc == "ESTRUTURA":
                    f_dates['DATA FABRICAÇÃO'] = v_fab.strftime("%d/%m/%Y") if v_fab else ""
                    f_dates['DATA PINTURA'] = v_pin.strftime("%d/%m/%Y") if v_pin else ""
                    f_dates['DATA TARQUE'] = v_torq.strftime("%d/%m/%Y") if v_torq else ""

                updates = {'SEMANA OBRA': sem_input, 'STATUS': st_atual, 'OBS': v_obs, **f_dates}
                valores_linha = df_atual.iloc[idx_base].tolist()
                
                for col, val in updates.items():
                    if col in cols_map: 
                        valores_linha[cols_map[col]-1] = str(val)
                
                ws_escrita.update(f"A{idx_base + 2}", [valores_linha])
                st.cache_data.clear()
                st.success("Salvo com sucesso!")
                time.sleep(1)
                st.rerun()

        st.divider()
        # QUADRO DE VISUALIZAÇÃO CONDICIONAL
        if disc == "ESTRUTURA":
            cols_view = ['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA FABRICAÇÃO', 'DATA PINTURA', 'DATA MONT', 'DATA TARQUE', 'STATUS', 'OBS']
        else:
            cols_view = ['TAG', 'SEMANA OBRA', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']
        
        df_vis = df_atual[[c for c in cols_view if c in df_atual.columns]].copy()
        for col in df_vis.columns:
            if 'DATA' in col or 'PREVISTO' in col:
                df_vis[col] = pd.to_datetime(df_vis[col], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').fillna("")

        busca_input = st.text_input("🔍 Pesquisar no Quadro:", key="busca_final_dinamica")
        if busca_input:
            mask = df_vis.apply(lambda row: row.astype(str).str.contains(busca_input, case=False).any(), axis=1)
            df_vis = df_vis[mask]

        st.dataframe(df_vis, use_container_width=True, hide_index=True, 
                     column_config={col: st.column_config.TextColumn(col) for col in df_vis.columns})
        

    elif aba == "📊 CURVA S":
        st.subheader(f"📊 Curva S Semanal e Avanço - {disc}")
        
        # 1. Indicadores de Topo
        total_t = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        per_real = (montados / total_t * 100) if total_t > 0 else 0
        
        c1, c2 = st.columns(2)
        c1.metric("Avanço Total Realizado", f"{per_real:.2f}%")
        c2.write("Progresso Visual:")
        c2.progress(per_real / 100)

        # 2. Preparação dos Dados (Semanas)
        df_c = df_atual.copy()
        
        # Converter Semana Obra (Programado) para numérico
        df_c['SEM_PROG'] = pd.to_numeric(df_c['SEMANA OBRA'], errors='coerce').fillna(0).astype(int)
        
        # Datas para Previsto e Realizado
        df_c['DT_REAL'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
        df_c['DT_PREV'] = pd.to_datetime(df_c['PREVISTO'], dayfirst=True, errors='coerce')

        # Função para converter data em número de semana da obra
        def converter_para_semana(data):
            if pd.isnull(data): return None
            # DATA_INICIO_OBRA deve estar definida no topo do seu código (29/09/2025)
            dias = (data - DATA_INICIO_OBRA).days
            return (dias // 7) + 1

        df_c['SEM_PREV'] = df_c['DT_PREV'].apply(converter_para_semana)
        df_c['SEM_REAL'] = df_c['DT_REAL'].apply(converter_para_semana)

        # Criar o eixo X com todas as semanas necessárias
        todas_semanas = sorted(list(set(
            df_c['SEM_PREV'].dropna().astype(int).tolist() + 
            df_c['SEM_PROG'][df_c['SEM_PROG'] > 0].tolist() + 
            df_c['SEM_REAL'].dropna().astype(int).tolist()
        )))
        
        if not todas_semanas:
            st.warning("Aguardando dados de cronograma para gerar o gráfico.")
        else:
            eixo_x = list(range(1, int(max(todas_semanas)) + 1))
            
            # Contagens por semana
            prev_sem = df_c['SEM_PREV'].value_counts().reindex(eixo_x, fill_value=0)
            prog_sem = df_c['SEM_PROG'].value_counts().reindex(eixo_x, fill_value=0)
            real_sem = df_c['SEM_REAL'].value_counts().reindex(eixo_x, fill_value=0)

            # Acumulados
            prev_acum = prev_sem.cumsum()
            prog_acum = prog_sem.cumsum()
            real_acum = real_sem.cumsum()

             # 3. Gráfico Plotly com Curvas Arredondadas (Spline)
            fig = go.Figure()

            # Barras Semanais (Volume)
            fig.add_trace(go.Bar(x=eixo_x, y=prev_sem, name='Previsto Semanal', marker_color='#2ecc71', opacity=0.2))
            fig.add_trace(go.Bar(x=eixo_x, y=real_sem, name='Realizado Semanal', marker_color='#3498db', opacity=0.2))

            # Linha PREVISTO (Verde Pontilhada)
            fig.add_trace(go.Scatter(x=eixo_x, y=prev_acum, name='LB - Previsto Acumulado', 
                                     line=dict(color='#27ae60', width=2, dash='dot', shape='spline')))

            # Linha PROGRAMADO (Amarela)
            fig.add_trace(go.Scatter(x=eixo_x, y=prog_acum, name='Programado Acumulado', 
                                     line=dict(color='#f1c40f', width=3, shape='spline')))

            # Linha REALIZADO (Azul e mais grossa para destaque)
            fig.add_trace(go.Scatter(x=eixo_x, y=real_acum, name='Realizado Acumulado', 
                                     line=dict(color='#3498db', width=4, shape='spline')))

            fig.update_layout(
                template="plotly_dark", 
                hovermode="x unified",
                height=550, 
                xaxis_title="Semanas de Obra",
                yaxis_title="Quantidade de Tags",
                legend=dict(orientation="h", y=1.05, xanchor="center", x=0.5),
                margin=dict(l=20, r=20, t=50, b=20) # Ajuste de margens para o gráfico respirar
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela de Apoio para conferência rápida
            with st.expander("Ver Quadro de Evolução Semanal"):
                df_resumo = pd.DataFrame({
                    "Semana": eixo_x,
                    "Previsto": prev_acum.values,
                    "Programado": prog_acum.values,
                    "Realizado": real_acum.values
                }).set_index("Semana")
                st.dataframe(df_resumo.T, use_container_width=True)

    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📋 Painel de Relatórios - {disc}")
        
        # 1. PAINEL DE MÉTRICAS
        if disc == "ESTRUTURA":
            c1, c2, c3, c4, c5, c6 = st.columns(6)
            c1.metric("Total Tags", len(df_atual))
            c2.metric("Aguard. Prog", len(df_atual[df_atual['STATUS'] == 'Aguardando Prog']))
            c3.metric("Aguard. Fab", len(df_atual[df_atual['STATUS'] == 'Aguardando Fab']))
            c4.metric("Aguard. Pintura", len(df_atual[df_atual['STATUS'] == 'Aguardando Pintura/Montagem']))
            c5.metric("Aguard. Montagem", len(df_atual[df_atual['STATUS'] == 'Aguardando Montagem']))
            c6.metric("Aguard. Torque", len(df_atual[df_atual['STATUS'] == 'Aguardando Torque']))
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total", len(df_atual))
            m2.metric("Montados ✅", len(df_atual[df_atual['STATUS'].isin(['MONTADO', 'Concluído'])]))
            m3.metric("Programados 📅", len(df_atual[df_atual['DATA INIC PROG'].fillna("") != ""]))
            m4.metric("Aguardando ⏳", len(df_atual[df_atual['DATA INIC PROG'].fillna("") == ""]))

        st.divider()

        # 2. PROGRAMAÇÃO
        st.markdown("### 📅 PROGRAMAÇÃO")
        # Filtro robusto para evitar erros com tipos diferentes
        df_p = df_atual[df_atual['DATA INIC PROG'].fillna("").astype(str) != ""].copy()
        
        semanas_prog = sorted([s for s in df_p['SEMANA OBRA'].unique() if s]) if not df_p.empty else []
        sem_sel_p = st.selectbox("Filtrar Programação por Semana:", ["TODAS"] + semanas_prog, key="rel_prog_sem")
        
        if sem_sel_p != "TODAS": 
            df_p = df_p[df_p['SEMANA OBRA'] == sem_sel_p]
        
        cols_p_alvo = ['TAG', 'ÁREA', 'SEMANA OBRA', 'DATA INIC PROG', 'DESCRIÇÃO']
        cols_p_safe = [c for c in cols_p_alvo if c in df_p.columns]
        
        if not df_p.empty:
            if 'DATA INIC PROG' in df_p.columns:
                df_p['DATA INIC PROG'] = pd.to_datetime(df_p['DATA INIC PROG'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').fillna("")
            
            st.dataframe(df_p[cols_p_safe], use_container_width=True, hide_index=True)
            
            # PROTEÇÃO: Só tenta exportar se houver linhas, evitando o erro do xlsxwriter
            excel_p = exportar_excel_com_cabecalho(df_p[cols_p_safe], f"RELATÓRIO DE PROGRAMAÇÃO - {disc}")
            st.download_button("📥 EXPORTAR PROGRAMAÇÃO", excel_p, f"Programacao_{disc}.xlsx", use_container_width=True)
        else:
            st.info("Nenhum item programado para exibição.")

        st.divider()

        # 3. AGUARDANDO PROGRAMAÇÃO
        st.markdown("### 🚩 AGUARDANDO PROGRAMAÇÃO")
        df_pend = df_atual[df_atual['DATA INIC PROG'].fillna("").astype(str) == ""].copy()
        
        cols_pend_alvo = ['TAG', 'DESCRIÇÃO', 'ÁREA', 'DOCUMENTO DE REFERENCIA', 'STATUS', 'PREVISTO', 'OBS']
        cols_pend_safe = [c for c in cols_pend_alvo if c in df_pend.columns]
        
        if not df_pend.empty:
            if 'PREVISTO' in df_pend.columns:
                df_pend['PREVISTO'] = pd.to_datetime(df_pend['PREVISTO'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').fillna("")
            
            st.dataframe(df_pend[cols_pend_safe], use_container_width=True, hide_index=True)
            excel_pend = exportar_excel_com_cabecalho(df_pend[cols_pend_safe], f"AGUARDANDO PROGRAMAÇÃO - {disc}")
            st.download_button("📥 EXPORTAR AGUARDANDO", excel_pend, f"Aguardando_{disc}.xlsx", use_container_width=True)
        else:
            st.success("Tudo programado! Nenhuma pendência encontrada.")

        st.divider()

        # 4. RELATÓRIO DE AVANÇO
        st.markdown("### 📈 RELATÓRIO DE AVANÇO")
        semanas_av = sorted([s for s in df_atual['SEMANA OBRA'].unique() if s], reverse=True)
        sem_sel_av = st.selectbox("Selecione a Semana:", semanas_av if semanas_av else ["-"], key="rel_av_sem")
        
        df_av = df_atual[(df_atual['SEMANA OBRA'] == sem_sel_av) & (df_atual['DATA MONT'].fillna("").astype(str) != "")].copy()
        
        cols_av_alvo = ['TAG', 'DESCRIÇÃO', 'DATA MONT', 'DATA TARQUE', 'ÁREA', 'STATUS', 'OBS']
        cols_av_safe = [c for c in cols_av_alvo if c in df_av.columns]
        
        if not df_av.empty:
            for d_col in ['DATA MONT', 'DATA TARQUE']:
                if d_col in df_av.columns:
                    df_av[d_col] = pd.to_datetime(df_av[d_col], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y').fillna("")
            
            st.dataframe(df_av[cols_av_safe], use_container_width=True, hide_index=True)
            excel_av = exportar_excel_com_cabecalho(df_av[cols_av_safe], f"RELATÓRIO DE AVANÇO - {disc}")
            st.download_button("📥 EXPORTAR AVANÇO", excel_av, f"Avanco_{disc}.xlsx", use_container_width=True)
        else:
            st.warning(f"Sem dados de avanço para a semana {sem_sel_av}.")

    elif aba == "📤 EXPORTAÇÃO E IMPORTAÇÕES":
        st.subheader(f"📤 Exportação e Importação - {disc}")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.info("📄 MODELO")
            mod = df_atual[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']].head(5)
            b_m = BytesIO(); mod.to_excel(b_m, index=False)
            st.download_button("📥 EXPORTAR MOD PLANILHA", b_m.getvalue(), "modelo_gmont.xlsx", use_container_width=True)
        with c2:
            st.info("🚀 IMPORTAÇÃO")
            up = st.file_uploader("Upload Excel:", type="xlsx")
            if up:
                if st.button("🚀 IMPORTAR E ATUALIZAR", use_container_width=True):
                    try:
                        df_up = pd.read_excel(up).astype(str)
                        df_up.columns = [str(c).strip().upper() for c in df_up.columns]
                        ws_escrita = client.open(map_planilhas[disc]).get_worksheet(0)
                        lista_mestra = ws_escrita.get_all_values()
                        headers = [str(h).strip().upper() for h in lista_mestra[0]]
                        idx_map = {name: i for i, name in enumerate(headers)}
                        sucesso = 0; nao_encontrado = 0
                        for _, r in df_up.iterrows():
                            tag_import = str(r.get('TAG', '')).strip()
                            if not tag_import or tag_import == 'nan': continue
                            achou = False
                            for i, row in enumerate(lista_mestra[1:]):
                                if str(row[0]).strip() == tag_import:
                                    for col in ['SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS', 'PREVISTO']:
                                        if col.upper() in df_up.columns:
                                            val = str(r[col.upper()]).strip()
                                            if val.lower() in ['nan', 'none', 'nat', 'dd/mm/yyyy']: val = ''
                                            lista_mestra[i+1][idx_map[col.upper()]] = val
                                    sucesso += 1; achou = True; break
                            if not achou: nao_encontrado += 1
                        if sucesso > 0:
                            ws_escrita.update('A1', lista_mestra)
                            st.cache_data.clear()
                            st.success(f"✅ IMPORTAÇÃO CONCLUÍDA!"); st.write(f"📊 **Resultado:** {sucesso} TAGs atualizadas.")
                            time.sleep(2)
                        else: st.error("❌ Nenhuma TAG correspondente encontrada.")
                    except Exception as e: st.error(f"❌ Erro no processamento: {e}")
        with c3:
            st.info("💾 BASE COMPLETA")
            df_export = df_atual.copy()
            colunas_data = ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT']
            for col in colunas_data:
                if col in df_export.columns:
                    temp_dt = pd.to_datetime(df_export[col], dayfirst=True, errors='coerce')
                    df_export[col] = temp_dt.dt.strftime('%d/%m/%Y').replace('NaT', '')
            excel_base = exportar_excel_com_cabecalho(df_export, f"BASE DE DADOS COMPLETA - {disc}")
            st.download_button("📥 EXPORTAR BASE", excel_base, f"Base_{disc}.xlsx", use_container_width=True)
