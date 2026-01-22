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

# --- CONTROLE DE ACESSO (SESSION STATE) ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

# --- FUNÇÃO DE LOGIN ---
def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("LOGO2.jpeg", width=250)
        except:
            st.header("ICE CONTROL")
        
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN de acesso (4 dígitos):", type="password", max_chars=4)
        
        # O sistema loga ao apertar o botão ou dar Enter
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "2026": # <--- SUA SENHA AQUI
                st.session_state['logado'] = True
                st.rerun()
            else:
                st.error("PIN Incorreto. Tente novamente.")
    st.stop()

# --- VERIFICAÇÃO DE LOGIN ---
if not st.session_state['logado']:
    tela_login()

# --- SE CHEGOU AQUI, O USUÁRIO ESTÁ LOGADO ---
# --- CONEXÃO E FUNÇÕES (MANTIDAS) ---
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
    except Exception as e:
        return pd.DataFrame(), None

def calcular_status(previsto, d_i, d_f, d_m):
    def tem(v): return str(v).strip().lower() not in ["nan", "none", "-", "0", ""]
    if tem(d_m): return "MONTADO"
    if tem(d_f): return "PROG. FINALIZADA"
    if tem(d_i): return "EM ANDAMENTO"
    if tem(previsto): return "PREVISTO"
    return "AGUARDANDO PROG"

# --- INTERFACE DO PAINEL (APÓS LOGIN) ---
st.sidebar.image("LOGO2.jpeg", width=120)
if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()

st.sidebar.divider()

st.markdown("### 🛠️ GESTÃO MONTAGEM ELE-INST")
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# Barra de Progresso
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

disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO POR TAG", "📊 QUADRO GERAL / CURVA S", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO POR TAG":
        st.subheader(f"🛠️ Editar TAG de {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG:", lista_tags)
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_operacional"):
            c1, c2, c3, c4, c5 = st.columns(5)
            v_prev = c1.text_input("Previsto", value=dados_tag.get('PREVISTO', ''))
            v_ini = c2.text_input("Data Iníc Prog", value=dados_tag.get('DATA INIC PROG', ''))
            v_fim = c3.text_input("Data Fim Prog", value=dados_tag.get('DATA FIM PROG', ''))
            v_mont = c4.text_input("Data Montagem", value=dados_tag.get('DATA MONT', ''))
            st_sug = calcular_status(v_prev, v_ini, v_fim, v_mont)
            v_status = c5.text_input("Status", value=st_sug, disabled=True)
            obs = st.text_input("Observação", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 GRAVAR ALTERAÇÕES"):
                linha_sheets = idx_base + 2
                try:
                    for col, val in zip(['PREVISTO','DATA INIC PROG','DATA FIM PROG','DATA MONT','STATUS','OBS'], 
                                       [v_prev, v_ini, v_fim, v_mont, st_sug, obs]):
                        if col in cols_map: ws_atual.update_cell(linha_sheets, cols_map[col], val)
                    st.success("Gravado!")
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")

    elif aba == "📊 QUADRO GERAL / CURVA S":
        st.subheader(f"📊 Curva S e Quadro Geral - {disc}")
        df_c = df_atual.copy()
        for c in ['PREVISTO', 'DATA FIM PROG', 'DATA MONT']:
            df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
        
        datas_alvo = pd.concat([df_c['PREVISTO'], df_c['DATA FIM PROG'], df_c['DATA MONT']]).dropna()
        if not datas_alvo.empty:
            eixo_x = pd.date_range(start=datas_alvo.min(), end=datas_alvo.max(), freq='D')
            df_curva = pd.DataFrame(index=eixo_x)
            df_curva['PREVISTO'] = [len(df_c[df_c['PREVISTO'] <= d]) for d in eixo_x]
            df_curva['PROGRAMADO'] = [len(df_c[df_c['DATA FIM PROG'] <= d]) for d in eixo_x]
            df_curva['REALIZADO'] = [len(df_c[df_c['DATA MONT'] <= d]) for d in eixo_x]
            st.plotly_chart(px.line(df_curva, title=f"Curva S - {disc}"), use_container_width=True)
        
        st.divider()
        st.dataframe(df_atual, use_container_width=True)

    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Gerenciamento de Dados via Excel")
        with st.expander("📥 EXPORTAR MODELO", expanded=True):
            colunas_modelo = ['TAG', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']
            df_export = df_atual[colunas_modelo] if not df_atual.empty else pd.DataFrame(columns=colunas_modelo)
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_export.to_excel(writer, index=False)
            st.download_button("📥 Baixar Planilha Modelo", buffer.getvalue(), f"Modelo_{disc}.xlsx")

        st.divider()

        with st.expander("🚀 IMPORTAR ATUALIZAÇÕES", expanded=True):
            up = st.file_uploader("Suba o arquivo Excel", type="xlsx")
            if up and st.button("🚀 Processar e Gravar"):
                try:
                    df_up = pd.read_excel(up).astype(str).replace('nan', '')
                    for _, r in df_up.iterrows():
                        if r['TAG'].strip() in df_atual['TAG'].values:
                            idx = df_atual.index[df_atual['TAG'] == r['TAG'].strip()][0] + 2
                            st_n = calcular_status(r.get('PREVISTO',''), r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT',''))
                            for col in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']:
                                if col in cols_map: ws_atual.update_cell(idx, cols_map[col], r.get(col, ''))
                            if 'STATUS' in cols_map: ws_atual.update_cell(idx, cols_map['STATUS'], st_n)
                    st.success("✅ Atualizado com sucesso!")
                    st.rerun()
                except Exception as e: st.error(f"Erro: {e}")
