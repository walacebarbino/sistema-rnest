import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SISTEMA RNEST", layout="wide")

# --- CONEXÃO COM GOOGLE SHEETS ---
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        s_info = dict(st.secrets["gcp_service_account"])
        
        # Correção crucial para o erro de base64/padding
        # Isso limpa a chave de espaços e garante que as quebras de linha funcionem
        raw_key = s_info["private_key"]
        if "\\n" in raw_key:
            s_info["private_key"] = raw_key.replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(s_info, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Erro na Autenticação (Verifique os Secrets): {e}")
        st.stop()

client = conectar_google()

# --- REGRAS DE STATUS ---
def calcular_status(d_i, d_m):
    # Se houver DATA MONT (Montagem), está montado
    if d_m and str(d_m).strip() not in ["", "nan", "None", "-"]:
        return "MONTADO"
    # Se houver DATA INIC PROG (Programação), aguarda montagem
    elif d_i and str(d_i).strip() not in ["", "nan", "None", "-"]:
        return "AGUARDANDO MONT"
    # Se não houver nada, aguarda programação
    else:
        return "AGUARDANDO PROG"

# --- INTERFACE ---
st.sidebar.title("🛠️ GESTÃO RNEST")
disc = st.sidebar.selectbox("Disciplina:", ["ELÉTRICA", "INSTRUMENTAÇÃO"])
aba = st.sidebar.radio("Navegação:", ["📊 Quadro Geral", "📝 Lançar Individual", "📤 Carga em Massa"])

try:
    # Abre a planilha baseada na disciplina selecionada
    nome_planilha = "BD_ELE" if disc == "ELÉTRICA" else "BD_INST"
    sh = client.open(nome_planilha)
    ws = sh.get_worksheet(0)
    
    # Carrega os dados
    valores = ws.get_all_values()
    if len(valores) > 1:
        df = pd.DataFrame(valores[1:], columns=valores[0])
        cols_map = {col: i + 1 for i, col in enumerate(valores[0])}

        # --- ABA: QUADRO GERAL ---
        if aba == "📊 Quadro Geral":
            st.header(f"Quadro Geral: {disc}")
            st.dataframe(df, use_container_width=True)

        # --- ABA: LANÇAR INDIVIDUAL ---
        elif aba == "📝 Lançar Individual":
            st.header(f"Lançamento por TAG - {disc}")
            tags_disponiveis = [t for t in df['TAG'].unique() if t.strip() != ""]
            tag_sel = st.selectbox("Selecione o TAG:", tags_disponiveis)
            
            idx_df = df.index[df['TAG'] == tag_sel][0]
            linha_atual = df.iloc[idx_df]
            linha_google = idx_df + 2 

            with st.form("form_edit"):
                c1, c2, c3, c4 = st.columns(4)
                d_i = c1.text_input("DATA INIC PROG", value=str(linha_atual.get('DATA INIC PROG', '')))
                d_f = c2.text_input("DATA FIM PROG", value=str(linha_atual.get('DATA FIM PROG', '')))
                d_p = c3.text_input("PREVISTO", value=str(linha_atual.get('PREVISTO', '')))
                d_m = c4.text_input("DATA MONT", value=str(linha_atual.get('DATA MONT', '')))
                
                if st.form_submit_button("SALVAR"):
                    novo_status = calcular_status(d_i, d_m)
                    
                    # Dicionário de atualizações
                    campos = {
                        'DATA INIC PROG': d_i, 
                        'DATA FIM PROG': d_f, 
                        'PREVISTO': d_p, 
                        'DATA MONT': d_m, 
                        'STATUS': novo_status
                    }
                    
                    with st.spinner("Atualizando planilha..."):
                        for col_nome, valor in campos.items():
                            if col_nome in cols_map:
                                ws.update_cell(linha_google, cols_map[col_nome], str(valor))
                    
                    st.success(f"TAG {tag_sel} atualizado! Status: {novo_status}")
                    st.rerun()

        # --- ABA: CARGA EM MASSA ---
        elif aba == "📤 Carga em Massa":
            st.header(f"Importar Planilha Excel - {disc}")
            uploaded_file = st.file_uploader("Selecione o arquivo .xlsx", type="xlsx")
            
            if uploaded_file:
                df_excel = pd.read_excel(uploaded_file).astype(str).replace('nan', '')
                if st.button("🚀 PROCESSAR DADOS"):
                    processados = 0
                    for _, row in df_excel.iterrows():
                        tag_excel = str(row['TAG']).strip()
                        if tag_excel in df['TAG'].values:
                            idx_g = df.index[df['TAG'] == tag_excel][0] + 2
                            st_novo = calcular_status(row.get('DATA INIC PROG'), row.get('DATA MONT'))
                            
                            # Atualiza campos principais
                            for c in ['DATA INIC PROG', 'DATA FIM PROG', 'PREVISTO', 'DATA MONT']:
                                if c in df_excel.columns and c in cols_map:
                                    ws.update_cell(idx_g, cols_map[c], str(row[c]))
                            
                            # Atualiza Status
                            if 'STATUS' in cols_map:
                                ws.update_cell(idx_g, cols_map['STATUS'], st_novo)
                            processados += 1
                    
                    st.success(f"Carga concluída! {processados} registros atualizados.")
                    st.rerun()
    else:
        st.warning("A planilha selecionada está vazia (apenas cabeçalho ou nada).")

except Exception as e:
    st.error(f"Erro ao acessar dados: {e}")
