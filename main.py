import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO E DATA BASE ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")
DATA_INICIO_OBRA = datetime(2025, 9, 29) # Segunda-feira da Semana 01

# --- CSS PARA PADRONIZAÇÃO ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; min-height: 25px; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def get_dates_from_week(week_number):
    """Retorna a segunda e a sexta de uma determinada semana da obra."""
    monday = DATA_INICIO_OBRA + timedelta(weeks=(week_number - 1))
    friday = monday + timedelta(days=4)
    return monday.date(), friday.date()

def calcular_status_tag(d_i, d_f, d_m):
    def tem(v): return str(v).strip() not in ["", "None", "nan", "-"]
    if tem(d_m): return "MONTADO"
    if tem(d_i) or tem(d_f): return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CONEXÃO GOOGLE SHEETS (Simplificada) ---
@st.cache_resource
def conectar_google():
    try:
        b64_creds = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
        creds_dict = json.loads(base64.b64decode(base64_creds))
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except: st.error("Erro na conexão com Google."); st.stop()

client = conectar_google()

def extrair_dados(nome_planilha):
    try:
        sh = client.open(nome_planilha)
        ws = sh.get_worksheet(0)
        data = ws.get_all_values()
        if len(data) > 1:
            df = pd.DataFrame(data[1:], columns=data[0])
            for col in df.columns: df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', '-'], '')
            return df, ws
        return pd.DataFrame(), None
    except: return pd.DataFrame(), None

# --- CARREGAMENTO ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

st.sidebar.image("LOGO2.png", width=120)
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

if not df_atual.empty:
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader(f"🛠️ Edição por TAG - {disc}")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]

        with st.form("form_v2"):
            st.markdown(f"📌 **TAG: {tag_sel}**")
            
            # Linha 1: Seleção da Semana e Status
            c_sem, c_stat = st.columns([1, 1])
            sem_atual = dados_tag.get('SEMANA OBRA', '17')
            sem_escolhida = c_sem.number_input("SEMANA OBRA:", min_value=1, max_value=100, value=int(sem_atual) if sem_atual.isdigit() else 17)
            
            # Cálculo automático sugerido (Segunda a Sexta)
            sug_ini, sug_fim = get_dates_from_week(sem_escolhida)
            
            # Linha 2: Datas (Abertas para edição manual se precisar de Sab/Dom)
            c1, c2, c3 = st.columns(3)
            
            def parse_dt(v, default):
                try: return datetime.strptime(v, "%d/%m/%Y").date()
                except: return default

            v_ini = c1.date_input("Início Prog", value=parse_dt(dados_tag.get('DATA INIC PROG'), sug_ini), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=parse_dt(dados_tag.get('DATA FIM PROG'), sug_fim), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=parse_dt(dados_tag.get('DATA MONT'), None), format="DD/MM/YYYY")

            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                novo_st = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                updates = {
                    'SEMANA OBRA': str(sem_escolhida),
                    'DATA INIC PROG': f_ini,
                    'DATA FIM PROG': f_fim,
                    'DATA MONT': f_mont,
                    'STATUS': novo_st,
                    'OBS': v_obs
                }
                
                for col, val in updates.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                
                st.success(f"TAG {tag_sel} atualizado para a Semana {sem_escolhida}!")
                st.rerun()

    elif aba == "📋 RELATÓRIOS":
        st.subheader("📋 PROGRAMADO PRODUÇÃO")
        # Força o recálculo do status para exibição correta
        df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
        
        # Filtro por Semana no Relatório
        semana_filtro = st.selectbox("Filtrar por Semana de Obra:", sorted(df_atual['SEMANA OBRA'].unique(), reverse=True))
        df_prod = df_atual[(df_atual['STATUS'] == 'PROGRAMADO') & (df_atual['SEMANA OBRA'] == semana_filtro)]
        
        st.dataframe(df_prod[['TAG', 'SEMANA OBRA', 'DATA INIC PROG', 'DATA FIM PROG', 'OBS']], use_container_width=True, hide_index=True)
        
        if not df_prod.empty:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_prod.to_excel(writer, index=False)
            st.download_button("📥 BAIXAR LISTA PROGRAMADO PRODUÇÃO", buf.getvalue(), f"producao_sem_{semana_filtro}.xlsx")
