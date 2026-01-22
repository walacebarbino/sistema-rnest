import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- CONEXÃO ---
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

# --- REGRAS DE STATUS ---
def calcular_status(d_i, d_m):
    d_m = str(d_m).strip()
    d_i = str(d_i).strip()
    if d_m and d_m.lower() not in ["nan", "none", "-", "0"]: return "MONTADO"
    if d_i and d_i.lower() not in ["nan", "none", "-", "0"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- INTERFACE OPERACIONAL ---
st.set_page_config(page_title="SISTEMA OPERACIONAL RNEST", layout="wide")

# Barra Superior com Avanço Geral
st.markdown("### 🛠️ GESTÃO OPERACIONAL RNEST")
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

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

# Menu Lateral
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO POR TAG", "📊 QUADRO GERAL / CURVA S", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if df_atual.empty:
    st.warning(f"⚠️ Atenção: Não foi possível carregar os dados de {disc}. Verifique se a planilha 'BD_ELE' ou 'BD_INST' foi compartilhada com o e-mail da conta de serviço.")
else:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO INDIVIDUAL (OPERACIONAL) ---
    if aba == "📝 EDIÇÃO POR TAG":
        st.subheader(f"🛠️ Editar TAG de {disc}")
        
        # Busca a lista de TAGs para o usuário escolher
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para editar:", lista_tags)
        
        # Localiza os dados atuais do TAG
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_operacional"):
            st.markdown(f"**Editando: {tag_sel}**")
            c1, c2, c3 = st.columns(3)
            
            nova_data_prog = c1.text_input("Data Início Prog (DD/MM/AAAA)", value=dados_tag.get('DATA INIC PROG', ''))
            nova_data_mont = c2.text_input("Data Montagem (DD/MM/AAAA)", value=dados_tag.get('DATA MONT', ''))
            obs = c3.text_input("Observação (Opcional)", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 GRAVAR ALTERAÇÕES NA PLANILHA"):
                novo_status = calcular_status(nova_data_prog, nova_data_mont)
                
                # Linha no Google Sheets é index + 2 (1 do cabeçalho + 1 porque começa em 1)
                linha_sheets = idx_base + 2
                
                try:
                    # Grava diretamente no Google Sheets
                    if 'DATA INIC PROG' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA INIC PROG'], nova_data_prog)
                    if 'DATA MONT' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA MONT'], nova_data_mont)
                    if 'STATUS' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['STATUS'], novo_status)
                    
                    st.success(f"✅ TAG {tag_sel} atualizado com sucesso! Status: {novo_status}")
                    st.rerun() # Recarrega para mostrar o dado novo
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    # --- ABA 2: QUADRO GERAL E CURVA S ---
    elif aba == "📊 QUADRO GERAL / CURVA S":
        st.subheader(f"Visualização de {disc}")
        tab1, tab2 = st.tabs(["📋 Tabela de Dados", "📈 Curva S"])
        
        with tab1:
            st.dataframe(df_atual, use_container_width=True)
            
        with tab2:
            if 'DATA MONT' in df_atual.columns:
                df_c = df_atual.copy()
                df_c['DATA MONT'] = pd.to_datetime(df_c['DATA MONT'], errors='coerce')
                df_c = df_c.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                if not df_c.empty:
                    df_c['Realizado'] = range(1, len(df_c) + 1)
                    fig = px.line(df_c, x='DATA MONT', y='Realizado', markers=True, title="Avanço Acumulado")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("A curva S aparecerá conforme as datas de montagem forem preenchidas.")

    # --- ABA 3: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Importar Atualizações via Excel")
        buffer = BytesIO()
        pd.DataFrame(columns=['TAG', 'DATA INIC PROG', 'DATA MONT']).to_excel(buffer, index=False)
        st.download_button("📥 Baixar Modelo", buffer.getvalue(), "modelo_rnest.xlsx")
        
        up = st.file_uploader("Subir planilha preenchida", type="xlsx")
        if up and st.button("🚀 Processar Arquivo"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    i = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    status = calcular_status(r['DATA INIC PROG'], r['DATA MONT'])
                    ws_atual.update_cell(i, cols_map['DATA MONT'], r['DATA MONT'])
                    ws_atual.update_cell(i, cols_map['STATUS'], status)
            st.success("Planilha processada e Sheets atualizado!")
            st.rerun()
