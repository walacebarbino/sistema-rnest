import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- 1. CONFIGURAÇÃO DE ACESSO (GOOGLE SHEETS) ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

# --- 2. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

# Menu Lateral
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

try:
    # Seleciona o arquivo baseado na disciplina escolhida
    nome_planilha = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_planilha)
    ws = sh.get_worksheet(0) # Abre a primeira aba do arquivo
    
    # LER DADOS (Forma segura para evitar o Erro 200)
    valores_brutos = ws.get_all_values()
    
    if len(valores_brutos) > 0:
        # Define os cabeçalhos (Linha 1) e os dados (Restante)
        cabecalhos = valores_brutos[0]
        dados = valores_brutos[1:]
        
        # Cria a tabela (DataFrame)
        df = pd.DataFrame(dados, columns=cabecalhos)
        
        # Mapeia onde está cada coluna para salvar depois (Ex: TAG está na coluna 1, STATUS na 5...)
        posicao_colunas = {nome: i + 1 for i, nome in enumerate(cabecalhos)}

        # --- ABA: QUADRO GERAL ---
        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.write(f"Exibindo todas as colunas encontradas em {nome_planilha}")
            st.dataframe(df, use_container_width=True)

        # --- ABA: LANÇAR INDIVIDUAL ---
        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização Manual - {disc}")
            
            if 'TAG' in df.columns:
                tag_lista = df['TAG'].unique()
                tag_alvo = st.selectbox("Escolha o TAG para editar:", tag_lista)
                
                # Puxa os dados atuais da linha selecionada
                dados_tag = df[df['TAG'] == tag_alvo].iloc[0]
                linha_planilha = df.index[df['TAG'] == tag_alvo][0] + 2
                
                with st.form("form_edicao"):
                    c1, c2, c3 = st.columns(3)
                    d_i = c1.text_input("DATA INIC PROG", value=str(dados_tag.get('DATA INIC PROG', '')))
                    d_f = c2.text_input("DATA FIM PROG", value=str(dados_tag.get('DATA FIM PROG', '')))
                    d_m = c3.text_input("DATA MONT", value=str(dados_tag.get('DATA MONT', '')))
                    
                    status_opcoes = ["AGUARDANDO PROG", "AGUARDANDO MONT", "MONTADO", "NÃO MONTADO"]
                    status_atual = str(dados_tag.get('STATUS', ''))
                    index_status = status_opcoes.index(status_atual) if status_atual in status_opcoes else 0
                    
                    novo_status = st.selectbox("STATUS:", status_opcoes, index=index_status)
                    
                    if st.form_submit_button("SALVAR NO GOOGLE SHEETS"):
                        # Atualiza apenas as células necessárias
                        ws.update_cell(linha_planilha, posicao_colunas['DATA INIC PROG'], d_i)
                        ws.update_cell(linha_planilha, posicao_colunas['DATA FIM PROG'], d_f)
                        ws.update_cell(linha_planilha, posicao_colunas['DATA MONT'], d_m)
                        ws.update_cell(linha_planilha, posicao_colunas['STATUS'], novo_status)
                        st.success(f"TAG {tag_alvo} atualizado!")
                        st.rerun()
            else:
                st.error("ERRO: Não encontrei uma coluna chamada 'TAG' na sua planilha.")

        # --- ABA: CARGA EM MASSA ---
        elif aba == "📤 Carga em Massa":
            st.header(f"Importação via Excel - {disc}")
            st.info("O Excel deve ter a coluna 'TAG' e as colunas: 'DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS'")
            arquivo_excel = st.file_uploader("Selecione o arquivo .xlsx", type="xlsx")
            
            if arquivo_excel:
                df_excel = pd.read_excel(arquivo_excel).astype(str)
                if st.button("🚀 INICIAR ATUALIZAÇÃO EM MASSA"):
                    barra_progresso = st.progress(0)
                    total_linhas = len(df_excel)
                    
                    for i, linha in df_excel.iterrows():
                        try:
                            # Localiza a TAG no Google Sheets
                            tag_planilha = str(linha['TAG'])
                            idx_google = df.index[df['TAG'] == tag_planilha][0] + 2
                            
                            # Atualiza as colunas se elas existirem no Excel
                            for col_nome in ['DATA INIC PROG', 'DATA FIM PROG', 'DATA MONT', 'STATUS']:
                                if col_nome in df_excel.columns:
                                    ws.update_cell(idx_google, posicao_colunas[col_nome], str(linha[col_nome]))
                        except:
                            continue # Se não achar a TAG, pula para a próxima
                        
                        barra_progresso.progress((i + 1) / total_linhas)
                    
                    st.success("Planilha Google atualizada com sucesso!")
                    st.rerun()
    else:
        st.error("A planilha parece estar vazia (sem dados na linha 1).")

except Exception as e:
    st.error(f"Ocorreu um problema: {e}")
    st.info("Verifique se as colunas TAG, DATA INIC PROG, DATA FIM PROG, DATA MONT e STATUS existem na sua planilha.")
