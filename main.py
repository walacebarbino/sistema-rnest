import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

@st.cache_resource
def conectar_google():
    try:
        # Busca o dicionário dos Secrets
        s_info = dict(st.secrets["gcp_service_account"])
        
        # --- LIMPEZA AUTOMÁTICA DA CHAVE (MATA O ERRO DE 65 CARACTERES) ---
        key = s_info["private_key"]
        # Remove \n de texto, remove espaços extras e garante quebras reais
        key = key.replace("\\n", "\n").strip()
        
        # Reconstrói a chave garantindo que cada linha esteja limpa
        lines = [line.strip() for line in key.split('\n') if line.strip()]
        s_info["private_key"] = '\n'.join(lines)
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(s_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação (Verifique os Secrets): {e}")
        st.stop()

# Inicializa a conexão
client = conectar_google()

# --- REGRAS DE STATUS AUTOMÁTICO ---
def calcular_status(d_i, d_m):
    d_m_s = str(d_m).strip().lower()
    d_i_s = str(d_i).strip().lower()
    if d_m_s not in ["", "nan", "none", "-", "0"]: 
        return "MONTADO"
    if d_i_s not in ["", "nan", "none", "-", "0"]: 
        return "AGUARDANDO MONT"
    return "AGUARDANDO PROG"

# --- INTERFACE SIDEBAR ---
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Edição Individual", "📤 Carga em Massa"])

try:
    # Seleção da planilha baseada na disciplina
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    
    # Carregamento de dados
    valores = ws.get_all_values()
    if len(valores) > 1:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        # --- ABA: QUADRO GERAL ---
        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        # --- ABA: EDIÇÃO INDIVIDUAL ---
        elif aba == "📝 Edição Individual":
            st.header(f"Atualizar TAG - {disc}")
            tags = sorted([t for t in df['TAG'].unique() if t.strip() != ""])
            tag_sel = st.selectbox("Selecione o TAG:", tags)
            
            idx_df = df.index[df['TAG'] == tag_sel][0]
            linha_atual = df.iloc[idx_df]

            with st.form("form_edicao"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(linha_atual.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(linha_atual.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(linha_atual.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(linha_atual.get('DATA MONT', '')))
                
                if st.form_submit_button("💾 SALVAR"):
                    n_status = calcular_status(d_i, d_m)
                    campos = {
                        'DATA INIC PROG': d_i, 
                        'DATA FIM PROG': d_f, 
                        'PREVISTO': d_p, 
                        'DATA MONT': d_m, 
                        'STATUS': n_status
                    }
                    
                    for col_nome, valor in campos.items():
                        if col_nome in cols_map:
                            ws.update_cell(idx_df + 2, cols_map[col_nome], str(valor))
                    
                    st.success(f"TAG {tag_sel} atualizado com sucesso!")
                    st.rerun()

        # --- ABA: CARGA EM MASSA ---
        elif aba == "📤 Carga em Massa":
            st.header("Importar Planilha Excel (.xlsx)")
            uploaded_file = st.file_uploader("Escolha o arquivo", type="xlsx")
            
            if uploaded_file and st.button("🚀 PROCESSAR PLANILHA"):
                df_excel = pd.read_excel(uploaded_file).astype(str).replace('nan', '')
                for _, row in df_excel.iterrows():
                    tag_ex = str(row['TAG']).strip()
                    if tag_ex in df['TAG'].values:
                        idx_g = df.index[df['TAG'] == tag_ex][0] + 2
                        st_n = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                        
                        for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                            if c in cols_map:
                                ws.update_cell(idx_g, cols_map[c], str(row.get(c, '')))
                        
                        if 'STATUS' in cols_map:
                            ws.update_cell(idx_g, cols_map['STATUS'], st_n)
                
                st.success("Importação em massa concluída!")
                st.rerun()
    else:
        st.warning("A planilha selecionada está vazia.")

except Exception as e:
    st.error(f"Ocorreu um erro: {e}")
