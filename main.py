import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO

# --- 1. CONFIGURAÇÃO DE ACESSO (IDs DAS PLANILHAS) ---
# Substitua pelos IDs das suas planilhas (o código na URL entre /d/ e /edit)
ID_PLANILHA_ELE = "COLE_AQUI_O_ID_DA_PLANILHA_BD_ELE"
ID_PLANILHA_INST = "COLE_AQUI_O_ID_DA_PLANILHA_BD_INST"

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

def extrair_dados(disciplina):
    try:
        id_f = ID_PLANILHA_ELE if disciplina == "ELÉTRICA" else ID_PLANILHA_INST
        sh = client.open_by_key(id_f) 
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            df.columns = df.columns.str.strip() 
            return df, ws
        return pd.DataFrame(), None
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar {disciplina}: {e}")
        return pd.DataFrame(), None

# --- REGRAS DE STATUS AUTOMÁTICO ---
def calcular_status(previsto, inicio_prog, fim_prog, montagem):
    def limpo(v): return str(v).strip().lower() not in ["", "nan", "none", "-", "0"]
    
    if limpo(montagem): return "MONTADO"
    if limpo(inicio_prog) or limpo(fim_prog): return "EM ANDAMENTO / PROG"
    if limpo(previsto): return "PREVISTO"
    return "AGUARDANDO"

# --- INTERFACE OPERACIONAL ---
st.set_page_config(page_title="SISTEMA OPERACIONAL RNEST", layout="wide")
st.markdown("### 🛠️ GESTÃO OPERACIONAL RNEST")

df_ele, ws_ele = extrair_dados("ELÉTRICA")
df_ins, ws_ins = extrair_dados("INSTRUMENTAÇÃO")

# Dashboard Superior
c1, c2 = st.columns(2)
for col, df, label in zip([c1, c2], [df_ele, df_ins], ["⚡ ELÉTRICA", "🔬 INSTRUMENTAÇÃO"]):
    if not df.empty:
        total = len(df)
        concluidos = len(df[df['STATUS'].str.strip().str.upper() == 'MONTADO'])
        perc = (concluidos/total)*100 if total > 0 else 0
        col.write(f"**{label}:** {perc:.1f}% ({concluidos}/{total})")
        col.progress(perc/100)

st.divider()

# Menu Lateral
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO POR TAG", "📊 QUADRO GERAL", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO POR TAG":
        st.subheader(f"🛠️ Painel de Edição Individual - {disc}")
        
        lista_tags = sorted(df_atual['TAG'].unique())
        tag_sel = st.selectbox("Selecione o TAG para editar:", lista_tags)
        
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        with st.form("form_operacional"):
            st.markdown(f"**Editando: {tag_sel}**")
            
            # Primeira linha: Datas de Planejamento e Execução
            r1c1, r1c2, r1c3, r1c4 = st.columns(4)
            d_prev = r1c1.text_input("Data Previsto", value=dados_tag.get('PREVISTO', ''))
            d_ini = r1c2.text_input("Data Início Prog", value=dados_tag.get('DATA INIC PROG', ''))
            d_fim = r1c3.text_input("Data Fim Prog", value=dados_tag.get('DATA FIM PROG', ''))
            d_mont = r1c4.text_input("Data Montagem", value=dados_tag.get('DATA MONT', ''))
            
            # Segunda linha: Observações
            n_obs = st.text_input("Observações (Opcional)", value=dados_tag.get('OBS', ''))
            
            # Cálculo de Status em tempo real para visualização
            status_previsto = calcular_status(d_prev, d_ini, d_fim, d_mont)
            st.info(f"**Status Resultante:** {status_previsto}")
            
            if st.form_submit_button("💾 GRAVAR ALTERAÇÕES NA PLANILHA"):
                linha_sheets = idx_base + 2
                try:
                    # Gravação em lote para as colunas solicitadas
                    if 'PREVISTO' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['PREVISTO'], d_prev)
                    if 'DATA INIC PROG' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA INIC PROG'], d_ini)
                    if 'DATA FIM PROG' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA FIM PROG'], d_fim)
                    if 'DATA MONT' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['DATA MONT'], d_mont)
                    if 'STATUS' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['STATUS'], status_previsto)
                    if 'OBS' in cols_map: ws_atual.update_cell(linha_sheets, cols_map['OBS'], n_obs)
                    
                    st.success(f"✅ TAG {tag_sel} atualizado com sucesso!")
                    st.rerun() 
                except Exception as e:
                    st.error(f"Erro ao gravar: {e}")

    elif aba == "📊 QUADRO GERAL":
        st.subheader(f"Base de Dados Completa - {disc}")
        st.dataframe(df_atual, use_container_width=True)

    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Carga via Excel")
        buffer = BytesIO()
        pd.DataFrame(columns=['TAG', 'PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']).to_excel(buffer, index=False)
        st.download_button("📥 Baixar Modelo", buffer.getvalue(), "modelo_rnest.xlsx")
        
        up = st.file_uploader("Subir arquivo Excel", type="xlsx")
        if up and st.button("🚀 Processar"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            for _, r in df_up.iterrows():
                t = r['TAG'].strip()
                if t in df_atual['TAG'].values:
                    i = df_atual.index[df_atual['TAG'] == t][0] + 2
                    st_n = calcular_status(r.get('PREVISTO'), r.get('DATA INIC PROG'), r.get('DATA FIM PROG'), r.get('DATA MONT'))
                    # Atualiza colunas essenciais
                    for col in ['PREVISTO', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS', 'OBS']:
                        if col in cols_map:
                            val = st_n if col == 'STATUS' else r.get(col, '')
                            ws_atual.update_cell(i, cols_map[col], val)
            st.success("Sincronização concluída!")
            st.rerun()
else:
    st.warning("⚠️ Planilha vazia ou não encontrada. Verifique os IDs e as permissões.")
