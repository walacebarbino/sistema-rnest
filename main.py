import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- 1. CONEXÃO ---
@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(b64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação: {e}")
        st.stop()

client = conectar_google()

# --- 2. FUNÇÕES DE APOIO ---
def calcular_status(d_i, d_m):
    if str(d_m).strip() not in ["", "nan", "None", "-"]: return "MONTADO"
    if str(d_i).strip() not in ["", "nan", "None", "-"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            return pd.DataFrame(data[1:], columns=data[0]), ws
        return pd.DataFrame(), ws
    except:
        return pd.DataFrame(), None

# --- 3. CONFIGURAÇÃO DA TELA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.title("🚀 SISTEMA DE GESTÃO RNEST")

# --- 4. CÁLCULO DE AVANÇO (DASHBOARD NO TOPO) ---
df_ele, _ = extrair_dados("BD_ELE")
df_ins, _ = extrair_dados("BD_INST")

c1, c2 = st.columns(2)

def mostrar_metrica(df, titulo, cor):
    if not df.empty and 'STATUS' in df.columns:
        total = len(df)
        montados = len(df[df['STATUS'] == 'MONTADO'])
        progresso = (montados / total) * 100 if total > 0 else 0
        st.metric(titulo, f"{progresso:.1f}%", f"{montados} de {total} TAGs")
        st.progress(progresso/100)
    else:
        st.metric(titulo, "0%", "Sem dados")

with c1:
    st.subheader("⚡ ELÉTRICA")
    mostrar_metrica(df_ele, "Avanço Físico Elétrica", "#00FF00")

with c2:
    st.subheader("🔬 INSTRUMENTAÇÃO")
    mostrar_metrica(df_ins, "Avanço Físico Inst.", "#0000FF")

st.divider()

# --- 5. NAVEGAÇÃO ---
disc = st.sidebar.selectbox("Disciplina para Edição:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral e Curva", "📝 Edição Individual", "📤 Carga em Massa"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
_, ws_atual = extrair_dados("BD_ELE" if disc == "ELÉTRICA" else "BD_INST")

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📊 Quadro Geral e Curva":
        col_t, col_g = st.columns([1, 1])
        
        with col_t:
            st.subheader(f"Dados Atuais - {disc}")
            st.dataframe(df_atual, height=400)
        
        with col_g:
            st.subheader("📈 Curva de Avanço (Acumulado)")
            if 'DATA MONT' in df_atual.columns:
                df_curva = df_atual.copy()
                df_curva['DATA MONT'] = pd.to_datetime(df_curva['DATA MONT'], errors='coerce')
                df_curva = df_curva.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                df_curva['Contagem'] = 1
                df_curva['Acumulado'] = df_curva['Contagem'].cumsum()
                fig = px.line(df_curva, x='DATA MONT', y='Acumulado', title="Evolução da Montagem")
                st.plotly_chart(fig, use_container_width=True)

    elif aba == "📝 Edição Individual":
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx = df_atual.index[df_atual['TAG'] == tag_sel][0]
        row = df_atual.iloc[idx]
        
        with st.form("form_edit"):
            d_i = st.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
            d_m = st.text_input("DATA MONT", row.get('DATA MONT', ''))
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                st_at = calcular_status(d_i, d_m)
                ws_atual.update_cell(idx + 2, cols_map['STATUS'], st_at)
                ws_atual.update_cell(idx + 2, cols_map['DATA INIC PROG'], d_i)
                ws_atual.update_cell(idx + 2, cols_map['DATA MONT'], d_m)
                st.success("TAG Atualizado!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.subheader("Importação e Modelo")
        
        # BOTÃO PARA BAIXAR MODELO
        modelo = pd.DataFrame(columns=['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT'])
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            modelo.to_excel(writer, index=False)
        st.download_button(label="📥 BAIXAR MODELO EXCEL", data=output.getvalue(), file_name="modelo_importacao.xlsx")
        
        up = st.file_uploader("Subir planilha preenchida", type="xlsx")
        if up and st.button("🚀 INICIAR IMPORTAÇÃO"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    i_g = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    st_n = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                    ws_atual.update_cell(i_g, cols_map['STATUS'], st_n)
                    ws_atual.update_cell(i_g, cols_map['DATA MONT'], r.get('DATA MONT', ''))
            st.success("Carga finalizada!")
            st.rerun()
else:
    st.error("Planilha não encontrada ou sem dados. Verifique o compartilhamento com o e-mail da conta de serviço.")
