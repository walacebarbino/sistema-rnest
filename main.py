import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- 1. FUNÇÃO DE CONEXÃO (OBRIGATÓRIO ESTAR NO TOPO) ---
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

# --- 2. CONFIGURAÇÕES E DADOS ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
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
    except:
        return pd.DataFrame(), None

# --- 3. DASHBOARD DE AVANÇO (CAIXAS SEPARADAS) ---
st.title("🚀 GESTÃO DE AVANÇO RNEST")

df_ele, _ = extrair_dados("BD_ELE")
df_ins, _ = extrair_dados("BD_INST")

col_m1, col_m2 = st.columns(2)

def criar_card(df, titulo):
    if not df.empty and 'STATUS' in df.columns:
        total = len(df)
        montados = len(df[df['STATUS'].str.contains('MONTADO', na=False, case=False)])
        porcentagem = (montados / total) * 100 if total > 0 else 0
        st.metric(titulo, f"{porcentagem:.1f}%", f"{montados} de {total} concluídos")
        st.progress(porcentagem / 100)
    else:
        st.metric(titulo, "0%", "Sem dados")

with col_m1:
    st.info("⚡ DISCIPLINA: ELÉTRICA")
    criar_card(df_ele, "Progresso Elétrica")

with col_m2:
    st.success("🔬 DISCIPLINA: INSTRUMENTAÇÃO")
    criar_card(df_ins, "Progresso Instrumentação")

st.divider()

# --- 4. NAVEGAÇÃO ---
disc = st.sidebar.selectbox("Editar Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral e Curva S", "📝 Edição Individual", "📤 Carga em Massa"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
_, ws_atual = extrair_dados("BD_ELE" if disc == "ELÉTRICA" else "BD_INST")

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📊 Quadro Geral e Curva S":
        c_tab, c_graf = st.columns([1, 1])
        with c_tab:
            st.subheader(f"Lista de TAGs - {disc}")
            st.dataframe(df_atual, height=400)
        with c_graf:
            st.subheader("📈 Curva de Avanço")
            if 'DATA MONT' in df_atual.columns:
                df_c = df_atual.copy()
                df_c['DATA MONT'] = pd.to_datetime(df_c['DATA MONT'], errors='coerce')
                df_c = df_c.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                if not df_c.empty:
                    df_c['Acumulado'] = range(1, len(df_c) + 1)
                    fig = px.line(df_c, x='DATA MONT', y='Acumulado', markers=True, title="TAGs Montados x Tempo")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Preencha 'DATA MONT' para ver a curva.")

    elif aba == "📝 Edição Individual":
        tag_sel = st.selectbox("TAG:", sorted(df_atual['TAG'].unique()))
        idx = df_atual.index[df_atual['TAG'] == tag_sel][0]
        row = df_atual.iloc[idx]
        with st.form("edit_form"):
            d_i = st.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
            d_m = st.text_input("DATA MONT", row.get('DATA MONT', ''))
            if st.form_submit_button("SALVAR"):
                # Lógica simplificada de status
                st_n = "MONTADO" if d_m.strip() else ("AGUARDANDO MONT" if d_i.strip() else "AGUARDANDO PROG")
                ws_atual.update_cell(idx + 2, cols_map['STATUS'], st_n)
                ws_atual.update_cell(idx + 2, cols_map['DATA INIC PROG'], d_i)
                ws_atual.update_cell(idx + 2, cols_map['DATA MONT'], d_m)
                st.success("Atualizado!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.subheader("Modelo e Importação")
        # Gerar Modelo Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            pd.DataFrame(columns=['TAG', 'DATA INIC PROG', 'DATA MONT']).to_excel(writer, index=False)
        st.download_button("📥 BAIXAR MODELO EXCEL", buffer.getvalue(), "modelo_rnest.xlsx", "application/vnd.ms-excel")
        
        up = st.file_uploader("Subir Arquivo", type="xlsx")
        if up and st.button("PROCESSAR"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                if r['TAG'] in df_atual['TAG'].values:
                    i_g = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    ws_atual.update_cell(i_g, cols_map['DATA MONT'], r['DATA MONT'])
            st.success("Importação concluída!")
            st.rerun()
else:
    st.warning("Verifique se as planilhas 'BD_ELE' e 'BD_INST' existem e estão compartilhadas.")
