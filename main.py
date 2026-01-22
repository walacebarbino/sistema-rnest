import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try: st.image("LOGO2.png", width=200) 
        except: st.header("G-MONT")
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN de acesso:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "1234":
                st.session_state['logado'] = True
                st.rerun()
            else: st.error("PIN Incorreto.")
    st.stop()

if not st.session_state['logado']:
    tela_login()

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
        st.error(f"Erro de Conexão: {e}")
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
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

def calcular_status(previsto, d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", "", "none"]
    if tem(d_m): return "MONTADO"
    if tem(d_f): return "PROG. FINALIZADA"
    if tem(d_i): return "EM ANDAMENTO"
    if tem(previsto): return "PREVISTO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO DE DADOS ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- INTERFACE LATERAL CENTRALIZADA ---
col_side1, col_side2, col_side3 = st.sidebar.columns([1, 3, 1])
with col_side2:
    st.image("LOGO2.png", width=120)

st.sidebar.divider()
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

st.markdown(f"### 🛠️ GESTÃO MONTAGEM ELE-INST - RNEST")
st.divider()

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO (AGORA COM CALENDÁRIO) ---
    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Edição por TAG - {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG:", lista_tags)
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        # Função para converter texto da planilha em objeto de data para o Streamlit
        def converter_para_data(texto):
            try: return datetime.strptime(texto, "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            
            # Campos de Data com Calendário
            v_prev = c1.date_input("Previsto", value=converter_para_data(dados_tag.get('PREVISTO')), format="DD/MM/YYYY")
            v_ini = c2.date_input("Início Prog", value=converter_para_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c3.date_input("Fim Prog", value=converter_para_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c4.date_input("Data Montagem", value=converter_para_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            obs = st.text_input("Observação", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                # Converte as datas de volta para texto no formato brasileiro para salvar na planilha
                f_prev = v_prev.strftime("%d/%m/%Y") if v_prev else ""
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                
                st_sug = calcular_status(f_prev, f_ini, f_fim, f_mont)
                linha = idx_base + 2
                
                campos = {
                    'PREVISTO': f_prev, 
                    'DATA INIC PROG': f_ini, 
                    'DATA FIM PROG': f_fim, 
                    'DATA MONT': f_mont, 
                    'STATUS': st_sug, 
                    'OBS': obs
                }
                
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                
                st.success("Dados salvos com sucesso!")
                st.rerun()
        
        st.divider()
        st.dataframe(df_atual, use_container_width=True)

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        def gerar_curva_data(df):
            if df.empty: return None
            df_c = df.copy()
            for c in ['PREVISTO', 'DATA FIM PROG', 'DATA MONT']:
                if c in df_c.columns:
                    df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
            datas = pd.concat([df_c[c] for c in ['PREVISTO', 'DATA FIM PROG', 'DATA MONT'] if c in df_c.columns]).dropna()
            if datas.empty: return None
            eixo_x = pd.date_range(start=datas.min(), end=datas.max(), freq='D')
            df_res = pd.DataFrame(index=eixo_x)
            for c, label in zip(['PREVISTO', 'DATA FIM PROG', 'DATA MONT'], ['PREVISTO', 'PROGRAMADO', 'REALIZADO']):
                if c in df_c.columns:
                    df_res[label] = [len(df_c[df_c[c] <= d]) for d in eixo_x]
            return df_res

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if not df_ele.empty:
                p_ele = (len(df_ele[df_ele['STATUS']=='MONTADO'])/len(df_ele))*100
                st.write(f"**⚡ ELÉTRICA: {p_ele:.1f}%**")
                st.progress(p_ele/100)
                df_res_ele = gerar_curva_data(df_ele)
                if df_res_ele is not None: 
                    st.plotly_chart(px.line(df_res_ele, title="Curva S - ELÉTRICA"), use_container_width=True)

        with col_g2:
            if not df_ins.empty:
                p_ins = (len(df_ins[df_ins['STATUS']=='MONTADO'])/len(df_ins))*100
                st.write(f"**🔬 INSTRUMENTAÇÃO: {p_ins:.1f}%**")
                st.progress(p_ins/100)
                df_res_ins = gerar_curva_data(df_ins)
                if df_res_ins is not None: 
                    st.plotly_chart(px.line(df_res_ins, title="Curva S - INSTRUMENTAÇÃO"), use_container_width=True)

    # --- ABA 3: RELATÓRIOS ---
    elif aba == "📋 RELATÓRIOS":
        st.subheader(f"📊 Relatórios Detalhados - {disc}")
        df_rep = df_atual.copy()
        # Tratamento de erro para colunas ausentes na visualização
        colunas_necessarias = ['TAG', 'STATUS', 'DATA MONT', 'OBS']
        for col in colunas_necessarias:
            if col not in df_rep.columns: df_rep[col] = ""

        if 'DATA MONT' in df_rep.columns:
            df_rep['DATA MONT'] = pd.to_datetime(df_rep['DATA MONT'], dayfirst=True, errors='coerce')
        
        hoje = datetime.now()
        inicio_semana = hoje - timedelta(days=7)
        
        total_tags = len(df_rep)
        montados = len(df_rep[df_rep['STATUS'] == 'MONTADO'])
        pendentes = total_tags - montados
        avanco_semanal = len(df_rep[df_rep['DATA MONT'] >= inicio_semana])
        
        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        c_r1.metric("Total de TAGs", total_tags)
        c_r2.metric("Total Montado", montados)
        c_r3.metric("Pendências", pendentes)
        c_r4.metric("Avanço 7 Dias", avanco_semanal)
        
        st.divider()
        col_r_left, col_r_right = st.columns(2)
        with col_r_left:
            st.markdown("#### 🚩 Lista de Pendências")
            df_pend = df_rep[df_rep['STATUS'] != 'MONTADO']
            st.dataframe(df_pend[['TAG', 'STATUS', 'OBS']], use_container_width=True, hide_index=True)
        with col_r_right:
            st.markdown("#### 📈 Avanço da Semana")
            df_sem = df_rep[df_rep['DATA MONT'] >= inicio_semana].copy()
            df_sem['DATA MONT'] = df_sem['DATA MONT'].dt.strftime('%d/%m/%Y')
            st.dataframe(df_sem[['TAG', 'DATA MONT', 'OBS']], use_container_width=True, hide_index=True)

    # --- ABA 4: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Importação e Exportação de Dados")
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            st.info("💡 **MODELO DE EDIÇÃO**")
            col_mod = ['TAG', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']
            df_mod = df_atual[[c for c in col_mod if c in df_atual.columns]]
            buffer_mod = BytesIO()
            with pd.ExcelWriter(buffer_mod, engine='xlsxwriter') as writer:
                df_mod.to_excel(writer, index=False)
            st.download_button("📥 Baixar Modelo", buffer_mod.getvalue(), f"modelo_{disc}.xlsx", use_container_width=True)

        with c_exp2:
            st.success("📂 **PLANILHA COMPLETA**")
            buffer_full = BytesIO()
            with pd.ExcelWriter(buffer_full, engine='xlsxwriter') as writer:
                df_atual.to_excel(writer, index=False)
            st.download_button("📥 EXPORTAR TODA A PLANILHA", buffer_full.getvalue(), f"DB_COMPLETO_{disc}.xlsx", use_container_width=True)

        st.divider()
        st.subheader("🚀 Importar Atualização")
        up = st.file_uploader("Selecione o arquivo Excel atualizado:", type="xlsx")
        if up and st.button("CONFIRMAR CARGA EM MASSA"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            progresso = st.progress(0)
            for i, (_, r) in enumerate(df_up.iterrows()):
                if r['TAG'] in df_atual['TAG'].values:
                    idx = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    st_n = calcular_status(r.get('PREVISTO',''), r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT',''))
                    for col in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']:
                        if col in cols_map: ws_atual.update_cell(idx, cols_map[col], r.get(col, ''))
                    if 'STATUS' in cols_map: ws_atual.update_cell(idx, cols_map['STATUS'], st_n)
                progresso.progress((i + 1) / len(df_up))
            st.success("Dados importados com sucesso!")
            st.rerun()

if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()
