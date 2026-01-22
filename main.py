import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- CONEXÃO (MANTIDA DO SEU COD FUNCIONAL) ---
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

# --- NOVA REGRA DE STATUS (SOLICITADA) ---
def calcular_status(previsto, d_i, d_f, d_m):
    d_m = str(d_m).strip().lower()
    d_f = str(d_f).strip().lower()
    d_i = str(d_i).strip().lower()
    prev = str(previsto).strip().lower()
    
    # Lista de valores considerados vazios
    vazios = ["nan", "none", "-", "0", ""]
    
    if d_m not in vazios: return "MONTADO"
    if d_f not in vazios: return "PROG. FINALIZADA"
    if d_i not in vazios: return "EM ANDAMENTO"
    if prev not in vazios: return "PREVISTO"
    return "AGUARDANDO PROG"

# --- INTERFACE OPERACIONAL ---
st.set_page_config(page_title="SISTEMA OPERACIONAL RNEST", layout="wide")

st.markdown("### 🛠️ GESTÃO OPERACIONAL RNEST")
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# Barra de Progresso Superior
col_m1, col_m2 = st.columns(2)
with col_m1:
    if not df_ele.empty:
        p = (len(df_ele[df_ele['STATUS']=='MONTADO'])/len(df_ele))*100
        st.write(f"**⚡ ELÉTRICA:** {p:.1f}%")
        st.progress(p/100)
with col_m2:
    if not df_ins.empty:
        p = (len(df_ins[df_ins['STATUS']=='MONTADO'])/len(df_ins))*100
        st.write(f"**🔬 INSTRUMENTAÇÃO:** {p:.1f}%")
        st.progress(p/100)

st.divider()

disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO POR TAG", "📊 QUADRO GERAL / CURVA S", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if df_atual.empty:
    st.warning(f"⚠️ Atenção: Não foi possível carregar os dados de {disc}.")
else:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO POR TAG":
        st.subheader(f"🛠️ Editar TAG de {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para editar:", lista_tags)
        
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_operacional"):
            st.markdown(f"**Editando: {tag_sel}**")
            c1, c2, c3, c4 = st.columns(4)
            
            # As caixas que você pediu:
            v_prev = c1.text_input("Previsto", value=dados_tag.get('PREVISTO', ''))
            v_ini = c2.text_input("Data Iníc Prog", value=dados_tag.get('DATA INIC PROG', ''))
            v_fim = c3.text_input("Data Fim Prog", value=dados_tag.get('DATA FIM PROG', ''))
            v_mont = c4.text_input("Data Montagem", value=dados_tag.get('DATA MONT', ''))
            
            obs = st.text_input("Observação", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 GRAVAR ALTERAÇÕES NA PLANILHA"):
                # O status muda automaticamente de acordo com as datas
                novo_status = calcular_status(v_prev, v_ini, v_fim, v_mont)
                linha_sheets = idx_base + 2
                
                try:
                    # Atualiza cada célula conforme o mapa de colunas
                    if 'PREVISTO' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['PREVISTO'], v_prev)
                    if 'DATA INIC PROG' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA INIC PROG'], v_ini)
                    if 'DATA FIM PROG' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA FIM PROG'], v_fim)
                    if 'DATA MONT' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA MONT'], v_mont)
                    if 'STATUS' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['STATUS'], novo_status)
                    if 'OBS' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['OBS'], obs)
                    
                    st.success(f"✅ {tag_sel} Gravado! Status: {novo_status}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    elif aba == "📊 QUADRO GERAL / CURVA S":
        st.subheader(f"Visualização de {disc}")
        st.dataframe(df_atual, use_container_width=True)

    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Carga via Excel")
        up = st.file_uploader("Subir planilha", type="xlsx")
        if up and st.button("🚀 Processar"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    i = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    st_n = calcular_status(r.get('PREVISTO'), r.get('DATA INIC PROG'), r.get('DATA FIM PROG'), r.get('DATA MONT'))
                    ws_atual.update_cell(i, cols_map['STATUS'], st_n)
            st.success("Concluído!")
            st.rerun()
