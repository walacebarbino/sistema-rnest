import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# 1. Configuração de Acesso Seguro
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

try:
    # Seleciona a planilha correta
    sh = client.open("BD_ELE") if disc == "ELÉTRICA" else client.open("BD_INST")
    ws = sh.get_worksheet(0)
    
    # Busca todos os valores e garante que não pegamos o objeto de resposta <200>
    data = ws.get_all_values()
    
    if len(data) > 0:
        # Cria o DataFrame com todas as colunas existentes na sua planilha
        df = pd.DataFrame(data[1:], columns=data[0])
        
        # Mapeia a posição de cada coluna pelo nome (Dinamismo para colunas extras)
        cols = {col: i + 1 for i, col in enumerate(data[0])}

        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados Completa: {disc}")
            st.dataframe(df, use_container_width=True)

        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização por TAG - {disc}")
            tag = st.selectbox("Selecione o TAG:", df['TAG'].unique())
            
            # Localiza a linha correta
            row_data = df.loc[df['TAG'] == tag]
            idx = row_data.index[0] + 2
            
            with st.form("f_ind"):
                c1, c2, c3 = st.columns(3)
                # Preenche com o valor atual ou vazio se não existir
                d_i = c1.text_input("DATA INIC PROG", value=str(row_data['DATA INIC PROG'].values[0]))
                d_f = c2.text_input("DATA FIM PROG", value=str(row_data['DATA FIM PROG'].values[0]))
                d_m = c3.text_input("DATA MONT", value=str(row_data['DATA MONT'].values[0]))
                
                # Tenta pré-selecionar o status atual
                status_atual = str(row_data['STATUS'].values[0])
                lista_status = ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"]
                default_index = lista_status.index(status_atual) if status_atual in lista_status else 0
                
                stat = st.selectbox("STATUS:", lista_status, index=default_index)
                
                if st.form_submit_button("SALVAR ALTERAÇÃO"):
                    # Atualiza apenas as colunas específicas, mantendo as outras intactas
                    ws.update_cell(idx, cols['DATA INIC PROG'], d_i)
                    ws.update_cell(idx, cols['DATA FIM PROG'], d_f)
                    ws.update_cell(idx, cols['DATA MONT'], d_m)
                    ws.update_cell(idx, cols['STATUS'], stat)
                    st.success(f"TAG {tag} atualizado com sucesso!")
                    st.rerun()

        elif aba == "📤 Carga em Massa":
            st.header(f"Importação em Massa - {disc}")
            st.write("O arquivo Excel deve conter a coluna **TAG** e as colunas que deseja atualizar.")
            file = st.file_uploader("Suba o Excel (.xlsx)", type="xlsx")
            
            if file:
                df_up = pd.read_excel(file)
                if st.button("🚀 PROCESSAR CARGA"):
                    for i, row in df_up.iterrows():
                        try:
                            # Procura a linha da TAG na base do Google
                            m_idx = df.index[df['TAG'] == str(row['TAG'])][0] + 2
                            
                            # Atualiza se a coluna existir no Excel enviado
                            if 'DATA INIC PROG' in df_up.columns:
                                ws.update_cell(m_idx, cols['DATA INIC PROG'], str(row['DATA INIC PROG']))
                            if 'DATA FIM PROG' in df_up.columns:
                                ws.update_cell(m_idx, cols['DATA FIM PROG'], str(row['DATA FIM PROG']))
                            if 'DATA MONT' in df_up.columns:
                                ws.update_cell(m_idx, cols['DATA MONT'], str(row['DATA MONT']))
                            if 'STATUS' in df_up.columns:
                                ws.update_cell(m_idx, cols['STATUS'], str(row['STATUS']))
                        except:
                            continue
                    st.success("Carga finalizada com sucesso!")
                    st.rerun()
    else:
        st.warning("A planilha parece estar vazia. Verifique se há cabeçalhos na primeira linha.")

except Exception as e:
    st.error(f"Erro de conexão ou formato: {e}")
    st.info("Dica: Verifique se os nomes das colunas na planilha são exatamente iguais aos do código.")
