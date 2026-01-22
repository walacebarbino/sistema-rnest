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
        # Lê a variável Base64 configurada nos Secrets
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        # Decodifica para o formato JSON original
        creds_dict = json.loads(base64.b64decode(b64_creds))
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro Crítico de Autenticação: {e}")
        st.stop()

# --- 2. CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
client = conectar_google()

# Função de extração com o ajuste opcional para detalhar erros de permissão
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
        # Exibe o erro técnico se a planilha não abrir (ex: falta de compartilhamento)
        st.sidebar.error(f"Erro ao acessar {nome_planilha}: {e}")
        return pd.DataFrame(), None

def calcular_status(d_i, d_m):
    d_m_s = str(d_m).strip().lower()
    d_i_s = str(d_i).strip().lower()
    if d_m_s not in ["", "nan", "none", "-", "0"]: return "MONTADO"
    if d_i_s not in ["", "nan", "none", "-", "0"]: return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- 3. DASHBOARD DE AVANÇO (CAIXAS SEPARADAS NO TOPO) ---
st.title("🚀 GESTÃO DE AVANÇO RNEST")

df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

col_m1, col_m2 = st.columns(2)

def criar_card(df, titulo, cor_tema):
    if not df.empty and 'STATUS' in df.columns:
        total = len(df)
        # Conta 'MONTADO' independente de maiúsculas/minúsculas
        montados = len(df[df['STATUS'].str.strip().str.upper() == 'MONTADO'])
        porcentagem = (montados / total) * 100 if total > 0 else 0
        
        with st.container():
            st.metric(titulo, f"{porcentagem:.1f}%", f"{montados} de {total} TAGs")
            st.progress(porcentagem / 100)
    else:
        st.metric(titulo, "0%", "Sem conexão com os dados")

with col_m1:
    st.info("⚡ DISCIPLINA: ELÉTRICA")
    criar_card(df_ele, "Progresso Elétrica", "blue")

with col_m2:
    st.success("🔬 DISCIPLINA: INSTRUMENTAÇÃO")
    criar_card(df_ins, "Progresso Instrumentação", "green")

st.divider()

# --- 4. NAVEGAÇÃO LATERAL ---
disc = st.sidebar.selectbox("Editar Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral e Curva S", "📝 Edição Individual", "📤 Carga em Massa"])

# Define qual banco de dados usar baseado na seleção
df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📊 Quadro Geral e Curva S":
        c_tab, c_graf = st.columns([1, 1])
        with c_tab:
            st.subheader(f"Lista de TAGs - {disc}")
            st.dataframe(df_atual, height=450, use_container_width=True)
        
        with c_graf:
            st.subheader("📈 Curva S de Avanço")
            if 'DATA MONT' in df_atual.columns:
                df_c = df_atual.copy()
                df_c['DATA MONT'] = pd.to_datetime(df_c['DATA MONT'], errors='coerce')
                df_c = df_c.dropna(subset=['DATA MONT']).sort_values('DATA MONT')
                if not df_c.empty:
                    df_c['Acumulado'] = range(1, len(df_c) + 1)
                    fig = px.line(df_c, x='DATA MONT', y='Acumulado', markers=True, 
                                 title="Evolução de Montagem (TAGs Acumulados)")
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Insira datas na coluna 'DATA MONT' para gerar a curva.")

    elif aba == "📝 Edição Individual":
        st.subheader(f"Editor de TAG - {disc}")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx = df_atual.index[df_atual['TAG'] == tag_sel][0]
        row = df_atual.iloc[idx]
        
        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            d_i = c1.text_input("DATA INIC PROG", row.get('DATA INIC PROG', ''))
            d_m = c2.text_input("DATA MONT", row.get('DATA MONT', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÕES"):
                st_n = calcular_status(d_i, d_m)
                # Atualiza no Sheets (Lembrando que o Sheets começa em 1 e tem cabeçalho, logo +2)
                ws_atual.update_cell(idx + 2, cols_map['STATUS'], st_n)
                ws_atual.update_cell(idx + 2, cols_map['DATA INIC PROG'], d_i)
                ws_atual.update_cell(idx + 2, cols_map['DATA MONT'], d_m)
                st.success(f"TAG {tag_sel} atualizado para {st_n}!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.subheader("Importação via Excel")
        
        # Botão para baixar modelo exato
        buffer = BytesIO()
        modelo_cols = ['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            pd.DataFrame(columns=modelo_cols).to_excel(writer, index=False)
        
        st.download_button(
            label="📥 BAIXAR MODELO EXCEL",
            data=buffer.getvalue(),
            file_name=f"modelo_carga_{disc}.xlsx",
            mime="application/vnd.ms-excel"
        )
        
        up = st.file_uploader("Subir planilha preenchida", type="xlsx")
        if up and st.button("🚀 INICIAR PROCESSAMENTO"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                tag_up = str(r['TAG']).strip()
                if tag_up in df_atual['TAG'].values:
                    i_g = df_atual.index[df_atual['TAG'] == tag_up][0] + 2
                    novo_st = calcular_status(r.get('DATA INIC PROG'), r.get('DATA MONT'))
                    # Atualiza colunas principais
                    if 'DATA MONT' in cols_map: ws_atual.update_cell(i_g, cols_map['DATA MONT'], r['DATA MONT'])
                    if 'STATUS' in cols_map: ws_atual.update_cell(i_g, cols_map['STATUS'], novo_st)
            st.success("Carga em massa finalizada!")
            st.rerun()
else:
    st.warning("⚠️ Planilhas não encontradas. Certifique-se de compartilhar 'BD_ELE' e 'BD_INST' com o e-mail da conta de serviço como EDITOR.")
