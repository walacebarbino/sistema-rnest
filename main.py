import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- 1. CONFIGURAÇÃO DE ACESSO ---
# Esta parte resolve o erro de conexão e formatação da chave
try:
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    s_info = dict(st.secrets["gcp_service_account"])
    s_info["private_key"] = s_info["private_key"].replace("\\n", "\n")
    creds = Credentials.from_service_account_info(s_info, scopes=scope)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"Erro na Autenticação: {e}")
    st.stop()

st.set_page_config(page_title="SISTEMA RNEST", layout="wide")
st.sidebar.title("🛠️ GESTÃO RNEST")

disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

# --- 2. REGRA DE STATUS AUTOMÁTICA ---
def calcular_status(d_i, d_m):
    # Se DATA MONT (Montagem) estiver preenchida
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    # Se DATA INIC PROG (Programação) estiver preenchida
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    # Se nenhuma data estiver preenchida
    else:
        return "AGUARDANDO PROG"

try:
    # Abre a planilha correta (BD_ELE ou BD_INST)
    nome_plan = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_plan)
    ws = sh.get_worksheet(0)
    
    # get_all_values() evita o erro <Response [200]>
    valores = ws.get_all_values()
    
    if len(valores) > 0:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        # --- ABA: QUADRO GERAL ---
        if aba == "📊 Quadro Geral":
            st.header(f"Base de Dados: {disc}")
            st.dataframe(df, use_container_width=True)

        # --- ABA: LANÇAR INDIVIDUAL ---
        elif aba == "📝 Lançar Individual":
            st.header(f"Atualização Manual - {disc}")
            # Filtra tags não vazias
            tags_validas = [t for t in df['TAG'].unique() if t.strip() != ""]
            tag_sel = st.selectbox("Selecione o TAG:", tags_validas)
            
            idx_df = df.index[df['TAG'] == tag_sel][0]
            dados_atuais = df.iloc[idx_df]
            linha_google = idx_df + 2 

            with st.form("form_individual"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(dados_atuais.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(dados_atuais.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(dados_atuais.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(dados_atuais.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    # Aplica a regra de status
                    novo_status = calcular_status(d_i, d_m)
                    
                    # Colunas que vamos atualizar
                    campos = {
                        'DATA INIC PROG': d_i, 'DATA FIM PROG': d_f, 
                        'PREVISTO': d_p, 'DATA MONT': d_m, 'STATUS': novo_status
                    }
                    
                    for col_nome, valor in campos.items():
                        if col_nome in cols_map:
                            ws.update_cell(linha_google, cols_map[col_nome], str(valor))
                    
                    st.success(f"TAG {tag_sel} atualizado! Novo Status: {novo_status}")
                    st.rerun()

        # --- ABA: CARGA EM MASSA ---
        elif aba == "📤 Carga em Massa":
            st.header(f"Importar Dados via Excel (.xlsx) - {disc}")
            arquivo = st.file_uploader("Suba o ficheiro", type="xlsx")
            if arquivo:
                df_up = pd.read_excel(arquivo).astype(str).replace('nan', '')
                if st.button("🚀 PROCESSAR CARGA"):
                    for _, row in df_up.iterrows():
                        tag_up = str(row['TAG']).strip()
                        if tag_up in df['TAG'].values:
                            idx_g = df.index[df['TAG'] == tag_up][0] + 2
                            n_stat = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                            
                            # Atualiza as 4 colunas de data + Status
                            for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                                if c in df_up.columns and c in cols_map:
                                    ws.update_cell(idx_g, cols_map[c], str(row[c]))
                            if 'STATUS' in cols_map:
                                ws.update_cell(idx_g, cols_map['STATUS'], n_stat)
                    st.success("Toda a carga foi processada com sucesso!")
                    st.rerun()
    else:
        st.warning("Planilha sem dados.")

except Exception as e:
    st.error(f"Erro no processamento: {e}")
