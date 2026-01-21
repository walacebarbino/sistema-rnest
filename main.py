import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# 1. Configuração de Acesso Seguro (Secrets)
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# Configuração da página
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

# Seleção da Disciplina
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

# 2. Lógica para abrir a planilha correta conforme a seleção
try:
    if disc == "ELÉTRICA":
        sh = client.open("BD_ELE")
    else:
        sh = client.open("BD_INST")

    # Abre a primeira aba do arquivo selecionado
    ws = sh.get_worksheet(0)
data = ws.get_all_values()
# Cria o DataFrame usando a primeira linha como cabeçalho
df = pd.DataFrame(data[1:], columns=data[0])

    if aba == "📊 Quadro Geral":
        st.header(f"Base de Dados: {disc}")
        st.dataframe(df, use_container_width=True)

    elif aba == "📝 Lançar Individual":
        st.header(f"Atualização por TAG - {disc}")
        tag = st.selectbox("Selecione o TAG:", df['TAG'].unique())
        # Encontra a linha no Google Sheets (Pandas index + 2)
        idx = df.index[df['TAG'] == tag][0] + 2
        
        with st.form("f_ind"):
            c1, c2, c3 = st.columns(3)
            d_i = c1.text_input("DATA INIC PROG", value=str(df.at[idx-2, 'DATA INIC PROG']))
            d_f = c2.text_input("DATA FIM PROG", value=str(df.at[idx-2, 'DATA FIM PROG']))
            d_m = c3.text_input("DATA MONT", value=str(df.at[idx-2, 'DATA MONT']))
            stat = st.selectbox("STATUS:", ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"], 
                               index=["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"].index(df.at[idx-2, 'STATUS']) if df.at[idx-2, 'STATUS'] in ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"] else 0)
            
            if st.form_submit_button("SALVAR"):
                # Atualiza as colunas C, D, E e F na linha correspondente
                ws.update(f"C{idx}:F{idx}", [[d_i, d_f, d_m, stat]])
                st.success(f"TAG {tag} atualizado com sucesso!")
                st.rerun()

    elif aba == "📤 Carga em Massa":
        st.header(f"Importação em Massa - {disc}")
        st.info("O Excel deve ter exatamente as colunas: TAG, DATA INIC PROG, DATA FIM PROG, DATA MONT, STATUS")
        file = st.file_uploader("Suba o arquivo Excel (.xlsx)", type="xlsx")
        
        if file:
            df_up = pd.read_excel(file)
            if st.button("🚀 PROCESSAR CARGA"):
                progress_bar = st.progress(0)
                total = len(df_up)
                
                for i, row in df_up.iterrows():
                    try:
                        # Procura a linha da TAG na planilha do Google
                        match_idx = df.index[df['TAG'] == row['TAG']][0] + 2
                        ws.update(f"C{match_idx}:F{match_idx}", [[
                            str(row.get('DATA INIC PROG','')), 
                            str(row.get('DATA FIM PROG','')), 
                            str(row.get('DATA MONT','')), 
                            str(row.get('STATUS',''))
                        ]])
                    except:
                        st.warning(f"TAG {row['TAG']} não encontrada na base {disc}. Pulando...")
                    
                    progress_bar.progress((i + 1) / total)
                
                st.success("Processamento finalizado!")
                st.rerun()

except Exception as e:
    st.error(f"Erro ao conectar com a planilha {disc}: {e}")
    st.info("Verifique se você compartilhou as planilhas BD_ELE e BD_INST com o e-mail da conta de serviço.")
