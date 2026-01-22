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

# --- CSS PARA ALINHAMENTO PERFEITO DAS CAIXAS ---
st.markdown("""
    <style>
    [data-testid="column"] {
        padding-left: 5px !important;
        padding-right: 5px !important;
    }
    /* Força altura igual para caixas de data e o campo de Status */
    .stDateInput div, .stTextInput div {
        height: 45px !important;
    }
    /* Alinha os títulos no topo */
    label p {
        font-weight: bold !important;
        font-size: 14px !important;
        white-space: nowrap !important;
        min-height: 25px;
    }
    /* Estilo para o campo de Status desabilitado parecer uma caixa firme */
    input:disabled {
        background-color: #1e293b !important;
        color: #60a5fa !important;
        opacity: 1 !important;
        -webkit-text-fill-color: #60a5fa !important;
    }
    </style>
    """, unsafe_allow_html=True)

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
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
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
            # Limpeza de strings para evitar erros de busca
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- LÓGICA DE STATUS AUTOMÁTICA ---
def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", "", "nat", "null"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO INICIAL ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- BARRA LATERAL ---
st.sidebar.image("LOGO2.png", width=120)
st.sidebar.divider()
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

st.markdown(f"### 🛠️ GESTÃO MONTAGEM {disc} - RNEST")
st.divider()

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO ---
    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader("🛠️ Edição por TAG")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        def conv_data(texto):
            try: return datetime.strptime(texto, "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            st.markdown(f"**TAG: {tag_sel}**")
            c1, c2, c3, c4 = st.columns(4)
            
            v_ini = c1.date_input("Início Prog", value=conv_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=conv_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=conv_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            # Campo de Status idêntico em tamanho aos calendários
            status_auto = calcular_status_tag(v_ini, v_fim, v_mont)
            v_status = c4.text_input("Status da TAG", value=status_auto, disabled=True)
            
            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                novo_st = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                campos = {'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': novo_st, 'OBS': v_obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Salvo!")
                st.rerun()
        
        st.divider()
        st.dataframe(df_atual, use_container_width=True, hide_index=True)

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        def gerar_curva_data(df):
            df_c = df.copy()
            for c in ['DATA FIM PROG', 'DATA MONT']:
                if c in df_c.columns:
                    df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
            datas = pd.concat([df_c[c] for c in ['DATA FIM PROG', 'DATA MONT'] if c in df_c.columns]).dropna()
            if datas.empty: return None
            eixo_x = pd.date_range(start=datas.min(), end=datas.max(), freq='D')
            df_res = pd.DataFrame(index=eixo_x)
            for c, label in zip(['DATA FIM PROG', 'DATA MONT'], ['PROGRAMADO', 'REALIZADO']):
                if c in df_c.columns:
                    df_res[label] = [len(df_c[df_c[c] <= d]) for d in eixo_x]
            return df_res

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if not df_ele.empty:
                mont_ele = len(df_ele[df_ele['STATUS']=='MONTADO'])
                p_ele = (mont_ele/len(df_ele))*100 if len(df_ele)>0 else 0
                st.write(f"**⚡ ELÉTRICA: {p_ele:.1f}%**")
                st.progress(p_ele/100)
                res_ele = gerar_curva_data(df_ele)
                if res_ele is not None: st.plotly_chart(px.line(res_ele, title="Curva S - ELÉTRICA"), use_container_width=True)

        with col_g2:
            if not df_ins.empty:
                mont_ins = len(df_ins[df_ins['STATUS']=='MONTADO'])
                p_ins = (mont_ins/len(df_ins))*100 if len(df_ins)>0 else 0
                st.write(f"**🔬 INSTRUMENTAÇÃO: {p_ins:.1f}%**")
                st.progress(p_ins/100)
                res_ins = gerar_curva_data(df_ins)
                if res_ins is not None: st.plotly_chart(px.line(res_ins, title="Curva S - INSTRUMENTAÇÃO"), use_container_width=True)

    # --- ABA 3: RELATÓRIOS (CORRIGIDA) ---
    elif aba == "📋 RELATÓRIOS":
        st.subheader("📊 Resumo Gerencial")
        df_rep = df_atual.copy()
        
        # Garante que as colunas existem antes de filtrar
        if 'DATA MONT' in df_rep.columns:
            df_rep['DATA MONT_DT'] = pd.to_datetime(df_rep['DATA MONT'], dayfirst=True, errors='coerce')
        
        hoje = datetime.now()
        inicio_semana = hoje - timedelta(days=7)
        
        total = len(df_rep)
        # Filtra pelo novo status
        montados = len(df_rep[df_rep['STATUS'] == 'MONTADO'])
        prog = len(df_rep[df_rep['STATUS'] == 'PROGRAMADO'])
        aguard = len(df_rep[df_rep['STATUS'] == 'AGUARDANDO PROG'])
        
        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        c_r1.metric("Total", total)
        c_r2.metric("Montados", montados)
        c_r3.metric("Programados", prog)
        c_r4.metric("Aguardando", aguard)
        
        st.divider()
        col_r_left, col_r_right = st.columns(2)
        with col_r_left:
            st.markdown("#### 🚩 Pendências de Montagem")
            # Mostra apenas o que não está montado
            df_pend = df_rep[df_rep['STATUS'] != 'MONTADO']
            exibir = ['TAG', 'STATUS', 'OBS']
            st.dataframe(df_pend[[c for c in exibir if c in df_pend.columns]], use_container_width=True, hide_index=True)
        
        with col_r_right:
            st.markdown("#### 📈 Montagem nos últimos 7 dias")
            if 'DATA MONT_DT' in df_rep.columns:
                df_sem = df_rep[df_rep['DATA MONT_DT'] >= inicio_semana].copy()
                exibir_sem = ['TAG', 'DATA MONT', 'OBS']
                st.dataframe(df_sem[[c for c in exibir_sem if c in df_sem.columns]], use_container_width=True, hide_index=True)

    # --- ABA 4: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Sincronização com Excel")
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            st.info("📥 **MODELO**")
            col_mod = ['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']
            df_mod = df_atual[[c for c in col_mod if c in df_atual.columns]]
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_mod.to_excel(writer, index=False)
            st.download_button("Baixar Modelo", buf.getvalue(), f"modelo_{disc}.xlsx", use_container_width=True)
        with c_exp2:
            st.success("📂 **FULL EXPORT**")
            buf_f = BytesIO()
            with pd.ExcelWriter(buf_f, engine='xlsxwriter') as writer:
                df_atual.to_excel(writer, index=False)
            st.download_button("Exportar Tudo", buf_f.getvalue(), f"DB_COMPLETO_{disc}.xlsx", use_container_width=True)
            
        st.divider()
        up = st.file_uploader("Importar Excel:", type="xlsx")
        if up and st.button("CONFIRMAR CARGA"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            prog = st.progress(0)
            for i, (_, r) in enumerate(df_up.iterrows()):
                if r['TAG'] in df_atual['TAG'].values:
                    idx = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    s_auto = calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT',''))
                    for col in ['DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']:
                        if col in cols_map: ws_atual.update_cell(idx, cols_map[col], r.get(col, ''))
                    if 'STATUS' in cols_map: ws_atual.update_cell(idx, cols_map['STATUS'], s_auto)
                prog.progress((i + 1) / len(df_up))
            st.success("Importado!")
            st.rerun()

if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()
