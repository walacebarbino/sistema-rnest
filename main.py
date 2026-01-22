import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- 1. CONFIGURAÇÃO DE ACESSO (IDs DAS PLANILHAS) ---
# Cole aqui o ID que fica na URL da sua planilha entre /d/ e /edit
ID_PLANILHA_ELE = "COLE_AQUI_O_ID_DA_PLANILHA_ELETRICA"
ID_PLANILHA_INST = "COLE_AQUI_O_ID_DA_PLANILHA_INSTRUMENTACAO"

@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro de Autenticação: {e}")
        st.stop()

client = conectar_google()

# --- 2. FUNÇÕES OPERACIONAIS ---
def extrair_dados(disciplina):
    try:
        id_f = ID_PLANILHA_ELE if disciplina == "ELÉTRICA" else ID_PLANILHA_INST
        sh = client.open_by_key(id_f) # Busca direta pelo ID
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip() # Remove espaços invisíveis nos nomes das colunas
            return df, ws
        return pd.DataFrame(), None
    except Exception as e:
        st.sidebar.error(f"Erro ao acessar {disciplina}: {e}")
        return pd.DataFrame(), None

def calcular_status(d_i, d_m):
    d_m = str(d_m).strip().lower()
    d_i = str(d_i).strip().lower()
    if d_m not in ["", "nan", "none", "-", "0"]: return "MONTADO"
    if d_i not in ["", "nan", "none", "-", "0"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- 3. INTERFACE DO SISTEMA ---
st.set_page_config(page_title="SISTEMA OPERACIONAL RNEST", layout="wide")

st.markdown("### 🛠️ GESTÃO OPERACIONAL RNEST")

# Busca de dados inicial para o dashboard
df_ele, ws_ele = extrair_dados("ELÉTRICA")
df_ins, ws_ins = extrair_dados("INSTRUMENTAÇÃO")

# Dashboard de progresso no topo
c1, c2 = st.columns(2)
with c1:
    if not df_ele.empty:
        total = len(df_ele)
        realizado = len(df_ele[df_ele['STATUS'].str.upper() == 'MONTADO'])
        perc = (realizado/total)*100 if total > 0 else 0
        st.metric("⚡ AVANÇO ELÉTRICA", f"{perc:.1f}%", f"{realizado} de {total} TAGs")
        st.progress(perc/100)
with c2:
    if not df_ins.empty:
        total = len(df_ins)
        realizado = len(df_ins[df_ins['STATUS'].str.upper() == 'MONTADO'])
        perc = (realizado/total)*100 if total > 0 else 0
        st.metric("🔬 AVANÇO INSTRUMENTAÇÃO", f"{perc:.1f}%", f"{realizado} de {total} TAGs")
        st.progress(perc/100)

st.divider()

# Navegação
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO POR TAG", "📊 QUADRO GERAL / CURVA S", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if df_atual.empty:
    st.warning(f"⚠️ Não foi possível carregar os dados de {disc}. Verifique os IDs no código e o compartilhamento da planilha.")
else:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA: EDIÇÃO INDIVIDUAL ---
    if aba == "📝 EDIÇÃO POR TAG":
        st.subheader(f"Edição Individual - {disc}")
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para atualizar:", lista_tags)
        
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_update"):
            c1, c2 = st.columns(2)
            nova_data_prog = c1.text_input("DATA INIC PROG", value=dados_tag.get('DATA INIC PROG', ''))
            nova_data_mont = c2.text_input("DATA MONT", value=dados_tag.get('DATA MONT', ''))
            
            if st.form_submit_button("💾 GRAVAR NA PLANILHA"):
                novo_st = calcular_status(nova_data_prog, nova_data_mont)
                linha_google = idx_base + 2 # +1 do cabeçalho, +1 do índice 0 do Pandas
                
                try:
                    # Gravação operacional nas colunas específicas
                    if 'DATA INIC PROG' in cols_map: ws_atual.update_cell(linha_google, cols_map['DATA INIC PROG'], nova_data_prog)
                    if 'DATA MONT' in cols_map: ws_atual.update_cell(linha_google, cols_map['DATA MONT'], nova_data_mont)
                    if 'STATUS' in cols_map: ws_atual.update_cell(linha_google, cols_map['STATUS'], novo_st)
                    
                    st.success(f"✅ TAG {tag_sel} gravado! Status: {novo_st}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    # --- ABA: QUADRO GERAL / CURVA S ---
    elif aba == "📊 QUADRO GERAL / CURVA S":
        st.subheader(f"Base de Dados - {disc}")
        t1, t2 = st.tabs(["📋 Tabela Completa", "📈 Curva de Avanço"])
        
        with t1:
            st.dataframe(df_atual, use_container_width=True)
            
        with t2:
            if 'DATA MONT' in df_atual.columns:
                df_c = df_atual.copy()
                df_c['DATA MONT'] = pd.to_datetime(df_c['DATA MONT'], dayfirst=True, errors='coerce')
                df_c = df_c.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                if not df_c.empty:
                    df_c['Acumulado'] = range(1, len(df_c) + 1)
                    fig = px.line(df_c, x='DATA MONT', y='Acumulado', markers=True, title="Avanço Acumulado por Data")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Insira datas de montagem para visualizar a curva.")

    # --- ABA: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Importação via Excel")
        buffer = BytesIO()
        pd.DataFrame(columns=['TAG', 'DATA INIC PROG', 'DATA MONT']).to_excel(buffer, index=False)
        st.download_button("📥 Baixar Modelo para Preencher", buffer.getvalue(), "modelo_rnest.xlsx")
        
        f = st.file_uploader("Subir planilha preenchida", type="xlsx")
        if f and st.button("🚀 Processar"):
            df_up = pd.read_excel(f).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                tag_up = r['TAG'].strip()
                if tag_up in df_atual['TAG'].values:
                    i = df_atual.index[df_atual['TAG'] == tag_up][0] + 2
                    novo_st = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                    ws_atual.update_cell(i, cols_map['DATA MONT'], r['DATA MONT'])
                    ws_atual.update_cell(i, cols_map['STATUS'], novo_st)
            st.success("Importação concluída!")
            st.rerun()
