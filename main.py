import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA ICE CONTROL", layout="wide")

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try: st.image("LOGO2.jpeg", width=250)
        except: st.header("ICE CONTROL")
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN de acesso:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "1234": # Altere sua senha aqui se desejar
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
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

def calcular_status(previsto, d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", ""]
    if tem(d_m): return "MONTADO"
    if tem(d_f): return "PROG. FINALIZADA"
    if tem(d_i): return "EM ANDAMENTO"
    if tem(previsto): return "PREVISTO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO DE DADOS (RNEST) ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- INTERFACE ---
st.sidebar.image("LOGO2.jpeg", width=120)
st.sidebar.divider()

disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

# Barra de Progresso no Topo
st.markdown(f"### 🛠️ GESTÃO MONTAGEM ELE-INST - RNEST")
c_m1, c_m2 = st.columns(2)
with c_m1:
    if not df_ele.empty:
        p = (len(df_ele[df_ele['STATUS']=='MONTADO'])/len(df_ele))*100
        st.write(f"**⚡ ELÉTRICA:** {p:.1f}%")
        st.progress(p/100)
with c_m2:
    if not df_ins.empty:
        p = (len(df_ins[df_ins['STATUS']=='MONTADO'])/len(df_ins))*100
        st.write(f"**🔬 INSTRUMENTAÇÃO:** {p:.1f}%")
        st.progress(p/100)
st.divider()

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO E QUADRO GERAL JUNTOS ---
    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Editar TAG de {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para editar:", lista_tags)
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_edit"):
            c1, c2, c3, c4 = st.columns(4)
            v_prev = c1.text_input("Previsto", value=dados_tag.get('PREVISTO', ''))
            v_ini = c2.text_input("Início Prog", value=dados_tag.get('DATA INIC PROG', ''))
            v_fim = c3.text_input("Fim Prog", value=dados_tag.get('DATA FIM PROG', ''))
            v_mont = c4.text_input("Data Montagem", value=dados_tag.get('DATA MONT', ''))
            st_sug = calcular_status(v_prev, v_ini, v_fim, v_mont)
            obs = st.text_input("Observação", value=dados_tag.get('OBS', ''))
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                linha = idx_base + 2
                campos = {'PREVISTO':v_prev, 'DATA INIC PROG':v_ini, 'DATA FIM PROG':v_fim, 'DATA MONT':v_mont, 'STATUS':st_sug, 'OBS':obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Dados salvos!")
                st.rerun()

        st.divider()
        st.subheader("📋 Quadro Geral de Dados")
        st.dataframe(df_atual, use_container_width=True)

    # --- ABA 2: CURVA S (ELÉTRICA E INSTRUMENTAÇÃO LADO A LADO) ---
    elif aba == "📊 CURVA S":
        st.subheader("📈 Evolução Acumulada das Disciplinas")
        
        def gerar_curva_data(df):
            df_c = df.copy()
            for c in ['PREVISTO', 'DATA FIM PROG', 'DATA MONT']:
                df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
            datas = pd.concat([df_c['PREVISTO'], df_c['DATA FIM PROG'], df_c['DATA MONT']]).dropna()
            if datas.empty: return None
            eixo_x = pd.date_range(start=datas.min(), end=datas.max(), freq='D')
            df_res = pd.DataFrame(index=eixo_x)
            df_res['PREVISTO'] = [len(df_c[df_c['PREVISTO'] <= d]) for d in eixo_x]
            df_res['PROGRAMADO'] = [len(df_c[df_c['DATA FIM PROG'] <= d]) for d in eixo_x]
            df_res['REALIZADO'] = [len(df_c[df_c['DATA MONT'] <= d]) for d in eixo_x]
            return df_res

        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            df_res_ele = gerar_curva_data(df_ele)
            if df_res_ele is not None:
                st.plotly_chart(px.line(df_res_ele, title="⚡ Curva S - ELÉTRICA"), use_container_width=True)
            else: st.info("Sem datas para Elétrica")

        with col_g2:
            df_res_ins = gerar_curva_data(df_ins)
            if df_res_ins is not None:
                st.plotly_chart(px.line(df_res_ins, title="🔬 Curva S - INSTRUMENTAÇÃO"), use_container_width=True)
            else: st.info("Sem datas para Instrumentação")

    # --- ABA 3: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Gerenciamento Excel")
        with st.expander("📥 EXPORTAR MODELO", expanded=True):
            col_mod = ['TAG', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']
            df_exp = df_atual[[c for c in col_mod if c in df_atual.columns]]
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_exp.to_excel(writer, index=False)
            st.download_button("Baixar Excel", buffer.getvalue(), f"Modelo_{disc}.xlsx")

        with st.expander("🚀 IMPORTAR ATUALIZAÇÕES", expanded=True):
            up = st.file_uploader("Suba o arquivo", type="xlsx")
            if up and st.button("CONFIRMAR IMPORTAÇÃO"):
                df_up = pd.read_excel(up).astype(str).replace('nan', '')
                for _, r in df_up.iterrows():
                    if r['TAG'] in df_atual['TAG'].values:
                        idx = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                        st_n = calcular_status(r.get('PREVISTO',''), r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT',''))
                        for col in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']:
                            if col in cols_map: ws_atual.update_cell(idx, cols_map[col], r.get(col, ''))
                        if 'STATUS' in cols_map: ws_atual.update_cell(idx, cols_map['STATUS'], st_n)
                st.success("Base RNEST atualizada!")
                st.rerun()

if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()
