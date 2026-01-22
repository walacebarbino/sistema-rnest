import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
import base64
import json
import plotly.express as px
from io import BytesIO
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA G-MONT", layout="wide")

# --- CSS PARA ALINHAMENTO E PADRONIZAÇÃO DAS CAIXAS ---
st.markdown("""
    <style>
    [data-testid="column"] { padding-left: 5px !important; padding-right: 5px !important; }
    .stDateInput div, .stTextInput div { height: 45px !important; }
    label p { font-weight: bold !important; font-size: 14px !important; min-height: 25px; }
    input:disabled { 
        background-color: #1e293b !important; 
        color: #60a5fa !important; 
        opacity: 1 !important; 
        -webkit-text-fill-color: #60a5fa !important; 
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONTROLE DE ACESSO ---
if 'logado' not in st.session_state:
    st.session_state['logado'] = False

def tela_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        try: st.image("LOGO2.png", width=200)
        except: st.header("G-MONT")
        st.subheader("🔐 ACESSO RESTRITO")
        pin = st.text_input("Digite o PIN:", type="password", max_chars=4)
        if st.button("ENTRAR NO SISTEMA"):
            if pin == "1234":
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
            df.columns = df.columns.str.strip()
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace(['nan', 'None', 'NaT', 'null', 'empty', '-'], '')
            return df, ws
        return pd.DataFrame(), None
    except Exception as e:
        st.error(f"Erro ao ler planilha {nome_planilha}: {e}")
        return pd.DataFrame(), None

# --- LÓGICA DE STATUS REVISADA ---
def calcular_status_tag(d_i, d_f, d_m):
    def tem_data(v): 
        v_str = str(v).strip()
        return v_str != "" and v_str != "None" and v_str != "nan"
    
    if tem_data(d_m): 
        return "MONTADO"
    if tem_data(d_i) or tem_data(d_f): 
        return "PROGRAMADO"
    return "AGUARDANDO PROG"

# --- CARREGAMENTO INICIAL ---
df_ele, ws_ele = extrair_dados("BD_ELE")
df_ins, ws_ins = extrair_dados("BD_INST")

# --- BARRA LATERAL ---
st.sidebar.image("LOGO2.png", width=120)
st.sidebar.divider()
disc = st.sidebar.selectbox("TRABALHAR COM:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("AÇÃO:", ["📝 EDIÇÃO E QUADRO", "📊 CURVA S", "📋 RELATÓRIOS", "📤 CARGA EM MASSA"])

df_atual = df_ele if disc == "ELÉTRICA" else df_ins
ws_atual = ws_ele if disc == "ELÉTRICA" else ws_ins

st.markdown(f"### 🛠️ GESTÃO MONTAGEM {disc} - RNEST")
st.divider()

if not df_atual.empty:
    # Garante que o Status esteja sempre calculado para os relatórios
    df_atual['STATUS'] = df_atual.apply(lambda r: calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT','')), axis=1)
    cols_map = {col: i + 1 for i, col in enumerate(df_atual.columns)}

    # --- ABA 1: EDIÇÃO E QUADRO ---
    if aba == "📝 EDIÇÃO E QUADRO":
        st.subheader("🛠️ Edição por TAG")
        tag_sel = st.selectbox("Selecione o TAG:", sorted(df_atual['TAG'].unique()))
        idx_base = df_atual.index[df_atual['TAG'] == tag_sel][0]
        dados_tag = df_atual.iloc[idx_base]
        
        def conv_data(texto):
            try: return datetime.strptime(str(texto), "%d/%m/%Y").date()
            except: return None

        with st.form("form_edit"):
            st.markdown(f"**TAG: {tag_sel}**")
            c1, c2, c3, c4 = st.columns(4)
            v_ini = c1.date_input("Início Prog", value=conv_data(dados_tag.get('DATA INIC PROG')), format="DD/MM/YYYY")
            v_fim = c2.date_input("Fim Prog", value=conv_data(dados_tag.get('DATA FIM PROG')), format="DD/MM/YYYY")
            v_mont = c3.date_input("Data Montagem", value=conv_data(dados_tag.get('DATA MONT')), format="DD/MM/YYYY")
            
            st_auto = calcular_status_tag(v_ini.strftime("%d/%m/%Y") if v_ini else "", 
                                          v_fim.strftime("%d/%m/%Y") if v_fim else "", 
                                          v_mont.strftime("%d/%m/%Y") if v_mont else "")
            c4.text_input("Status Atual", value=st_auto, disabled=True)
            
            v_obs = st.text_input("Observação:", value=dados_tag.get('OBS', ''))
            
            if st.form_submit_button("💾 SALVAR ALTERAÇÃO"):
                f_ini = v_ini.strftime("%d/%m/%Y") if v_ini else ""
                f_fim = v_fim.strftime("%d/%m/%Y") if v_fim else ""
                f_mont = v_mont.strftime("%d/%m/%Y") if v_mont else ""
                novo_st = calcular_status_tag(f_ini, f_fim, f_mont)
                
                linha = idx_base + 2
                campos = {'DATA INIC PROG': f_ini, 'DATA FIM PROG': f_fim, 'DATA MONT': f_mont, 'STATUS': novo_st, 'OBS': v_obs}
                for col, val in campos.items():
                    if col in cols_map: ws_atual.update_cell(linha, cols_map[col], val)
                st.success("Salvo com sucesso!")
                st.rerun()
        st.dataframe(df_atual, use_container_width=True, hide_index=True)

    # --- ABA 2: CURVA S ---
    elif aba == "📊 CURVA S":
        def gerar_curva_data(df):
            df_c = df.copy()
            for c in ['DATA FIM PROG', 'DATA MONT']:
                if c in df_c.columns:
                    df_c[c] = pd.to_datetime(df_c[c], dayfirst=True, errors='coerce')
            datas = pd.concat([df_c[c] for c in ['DATA FIM PROG', 'DATA MONT'] if c in df_c.columns]).dropna()
            if datas.empty: return None
            eixo_x = pd.date_range(start=datas.min(), end=datas.max(), freq='D')
            df_res = pd.DataFrame(index=eixo_x)
            for c, label in zip(['DATA FIM PROG', 'DATA MONT'], ['PROGRAMADO', 'REALIZADO']):
                if c in df_c.columns:
                    df_res[label] = [len(df_c[df_c[c] <= d]) for d in eixo_x]
            return df_res

        col_g1, col_g2 = st.columns(2)
        with col_g1:
            if not df_ele.empty:
                p_ele = (len(df_ele[df_ele['STATUS']=='MONTADO'])/len(df_ele))*100
                st.write(f"**⚡ ELÉTRICA: {p_ele:.1f}%**")
                st.progress(p_ele/100)
                res_ele = gerar_curva_data(df_ele)
                if res_ele is not None: st.plotly_chart(px.line(res_ele, title="Curva S - ELÉTRICA"), use_container_width=True)
        with col_g2:
            if not df_ins.empty:
                p_ins = (len(df_ins[df_ins['STATUS']=='MONTADO'])/len(df_ins))*100
                st.write(f"**🔬 INSTRUMENTAÇÃO: {p_ins:.1f}%**")
                st.progress(p_ins/100)
                res_ins = gerar_curva_data(df_ins)
                if res_ins is not None: st.plotly_chart(px.line(res_ins, title="Curva S - INSTRUMENTAÇÃO"), use_container_width=True)

    # --- ABA 3: RELATÓRIOS ---
    elif aba == "📋 RELATÓRIOS":
        st.subheader("📊 Painel de Controle")
        total = len(df_atual)
        montados = len(df_atual[df_atual['STATUS'] == 'MONTADO'])
        programados = len(df_atual[df_atual['STATUS'] == 'PROGRAMADO'])
        aguardando = len(df_atual[df_atual['STATUS'] == 'AGUARDANDO PROG'])
        
        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
        c_m1.metric("Total TAGs", total)
        c_m2.metric("Montados ✅", montados)
        c_m3.metric("Programados 📅", programados)
        c_m4.metric("Aguardando ⏳", aguardando)
        
        st.divider()
        
        # TÍTULO ALTERADO CONFORME SOLICITAÇÃO
        st.markdown("### 📋 PROGRAMADO PRODUÇÃO")
        df_prod = df_atual[df_atual['STATUS'] == 'PROGRAMADO'].copy()
        if not df_prod.empty:
            cols_prod = ['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'DESCRIÇÃO', 'ÁREA', 'OBS']
            df_prod_show = df_prod[[c for c in cols_prod if c in df_prod.columns]]
            st.dataframe(df_prod_show, use_container_width=True, hide_index=True)
            
            buf_p = BytesIO()
            with pd.ExcelWriter(buf_p, engine='xlsxwriter') as writer:
                df_prod_show.to_excel(writer, index=False, sheet_name='PRODUCAO')
            st.download_button("📥 BAIXAR LISTA PROGRAMADO PRODUÇÃO", buf_p.getvalue(), f"producao_{disc}.xlsx", use_container_width=True)
        else:
            st.warning("Nenhum item com status PROGRAMADO.")

        st.divider()
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### 🚩 Pendências Totais")
            df_pend = df_atual[df_atual['STATUS'] != 'MONTADO']
            df_pend_show = df_pend[['TAG', 'STATUS', 'OBS']] if 'OBS' in df_pend.columns else df_pend[['TAG', 'STATUS']]
            st.dataframe(df_pend_show, use_container_width=True, hide_index=True)
            buf_pend = BytesIO()
            with pd.ExcelWriter(buf_pend, engine='xlsxwriter') as writer:
                df_pend_show.to_excel(writer, index=False)
            st.download_button("📥 Exportar Pendências", buf_pend.getvalue(), "pendencias.xlsx")

        with col_r:
            st.markdown("#### 📈 Realizado (7 Dias)")
            df_atual['DT_TEMP'] = pd.to_datetime(df_atual['DATA MONT'], dayfirst=True, errors='coerce')
            df_sem = df_atual[df_atual['DT_TEMP'] >= (datetime.now() - timedelta(days=7))]
            df_sem_show = df_sem[['TAG', 'DATA MONT', 'OBS']] if 'OBS' in df_sem.columns else df_sem[['TAG', 'DATA MONT']]
            st.dataframe(df_sem_show, use_container_width=True, hide_index=True)
            buf_sem = BytesIO()
            with pd.ExcelWriter(buf_sem, engine='xlsxwriter') as writer:
                df_sem_show.to_excel(writer, index=False)
            st.download_button("📥 Exportar Realizado", buf_sem.getvalue(), "realizado_semana.xlsx")

    # --- ABA 4: CARGA EM MASSA ---
    elif aba == "📤 CARGA EM MASSA":
        st.subheader("Carga e Download")
        c_exp1, c_exp2 = st.columns(2)
        with c_exp1:
            st.info("📥 **MODELO**")
            col_mod = ['TAG', 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']
            df_mod = df_atual[[c for c in col_mod if c in df_atual.columns]]
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                df_mod.to_excel(writer, index=False)
            st.download_button("Baixar Modelo", buf.getvalue(), f"modelo_{disc}.xlsx", use_container_width=True)
        with c_exp2:
            st.success("📂 **FULL EXPORT**")
            buf_f = BytesIO()
            with pd.ExcelWriter(buf_f, engine='xlsxwriter') as writer:
                df_atual.to_excel(writer, index=False)
            st.download_button("Exportar Base Completa", buf_f.getvalue(), f"DB_{disc}.xlsx", use_container_width=True)
            
        st.divider()
        up = st.file_uploader("Selecione o arquivo Excel atualizado:", type="xlsx")
        if up and st.button("CONFIRMAR CARGA"):
            df_up = pd.read_excel(up).astype(str).replace('nan', '')
            prog = st.progress(0)
            for i, (_, r) in enumerate(df_up.iterrows()):
                if r['TAG'] in df_atual['TAG'].values:
                    idx = df_atual.index[df_atual['TAG'] == r['TAG']][0] + 2
                    s_auto = calcular_status_tag(r.get('DATA INIC PROG',''), r.get('DATA FIM PROG',''), r.get('DATA MONT',''))
                    for col in ['DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'OBS']:
                        if col in cols_map: ws_atual.update_cell(idx, cols_map[col], r.get(col, ''))
                    if 'STATUS' in cols_map: ws_atual.update_cell(idx, cols_map['STATUS'], s_auto)
                prog.progress((i + 1) / len(df_up))
            st.success("Dados importados!")
            st.rerun()

if st.sidebar.button("🚪 SAIR"):
    st.session_state['logado'] = False
    st.rerun()
