import streamlit as st
import base64, json
import pandas as pd
from datetime import datetime
from gspread import authorize
from google.oauth2.service_account import Credentials
from io import BytesIO
import xlsxwriter
import logging
import plotly.express as px

###############################################################################
# LOGIN SECURITY
###############################################################################
def check_login():
    if "logged" not in st.session_state:
        st.session_state.logged = False

def login_form():
    st.title("Autenticação")
    pin_input = st.text_input("PIN de acesso", type="password")
    if st.button("Entrar"):
        secret_pin = st.secrets.get("APP_PIN", None)
        if secret_pin is None:
            st.error("PIN não configurado em st.secrets")
        elif pin_input == secret_pin:
            st.session_state.logged = True
            st.success("Acesso autorizado")
        else:
            st.error("PIN inválido")

###############################################################################
# GOOGLE SHEETS
###############################################################################
@st.cache_resource
def get_client():
    b64 = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
    creds_json = json.loads(base64.b64decode(b64))
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    return authorize(creds)

def load_sheet(spread_name: str, worksheet_name: str):
    gc = get_client()
    ws = gc.open(spread_name).worksheet(worksheet_name)
    values = ws.get_values()
    if not values:
        return pd.DataFrame(), ws
    df = pd.DataFrame(values[1:], columns=values[0])
    return df, ws

def batch_update_row(ws, row: int, columns: list, values: list):
    col_start = 1
    col_end = len(columns)
    ws.batch_update([{
        "range": f"{ws.title}!{chr(64+col_start)}{row}:{chr(64+col_end)}{row}",
        "values": [values]
    }])

def batch_delete_rows(ws, rows: list):
    rows = sorted(rows, reverse=True)
    for r in rows:
        ws.delete_rows(r)

###############################################################################
# TRANSFORM
###############################################################################
DATE_COLS = ["DATA_MONTADO", "DATA_INICIO", "DATA_FINAL"]

def to_datetime(df):
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    return df

def compute_status(row):
    if pd.notnull(row.get("DATA_MONTADO")):
        return "MONTADO"
    if pd.notnull(row.get("DATA_INICIO")) or pd.notnull(row.get("DATA_FINAL")):
        return "PROGRAMADO"
    return "AGUARDANDO PROG"

###############################################################################
# EXPORT EXCEL
###############################################################################
def export_excel(df: pd.DataFrame, titulo: str, disciplina: str, logo_path: str = None):
    output = BytesIO()
    current_week = datetime.now().isocalendar().week

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Dados", startrow=4, index=False)
        workbook = writer.book
        ws = writer.sheets["Dados"]

        header_fmt = workbook.add_format({"bold": True, "align": "center", "font_size": 14})
        ws.merge_range("A1:F1", titulo, header_fmt)
        ws.merge_range("A2:F2", f"{disciplina} - Semana {current_week}", header_fmt)

        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            ws.set_column(i, i, max_len)

        if logo_path:
            try:
                ws.insert_image("G1", logo_path, {"x_scale": 0.5, "y_scale": 0.5})
            except Exception:
                pass

    output.seek(0)
    return output

###############################################################################
# AUDIT LOG
###############################################################################
logging.basicConfig(filename="audit.log", level=logging.INFO)

def log_event(user, action, tag):
    logging.info(f"{datetime.now()} | {user} | {action} | {tag}")

###############################################################################
# UI: TAGS
###############################################################################
SPREAD = "PLANILHA_PROJETO"

def manage_tags():
    st.header("Gerenciar Tags")
    disciplina = st.selectbox("Disciplina", ["ELÉTRICA", "INSTRUMENTAÇÃO", "ESTRUTURA"])
    df, ws = load_sheet(SPREAD, disciplina)

    if df.empty:
        st.warning("Planilha vazia.")
        return

    df = to_datetime(df)
    df["STATUS"] = df.apply(compute_status, axis=1)

    tag = st.text_input("TAG para editar/deletar")
    if not tag:
        return

    matches = df[df["TAG"] == tag]
    if matches.empty:
        st.error("TAG não encontrada.")
        return
    if len(matches) > 1:
        st.error("TAG duplicada. Corrija a planilha.")
        return

    row_idx = matches.index[0] + 2
    st.dataframe(matches)

    data_original = matches["DATA_MONTADO"].iloc[0]
    nova_data = st.date_input("DATA MONTADO", data_original if pd.notnull(data_original) else None)

    if st.button("Salvar"):
        colunas = list(df.columns)
        valores = []
        for c in colunas:
            val = matches[c].iloc[0]
            if c == "DATA_MONTADO":
                val = nova_data.strftime("%Y-%m-%d") if nova_data else ""
            elif pd.notnull(val) and hasattr(val, "strftime"):
                val = val.strftime("%Y-%m-%d")
            valores.append(str(val))

        batch_update_row(ws, row_idx, colunas, valores)
        log_event("user", "edit", tag)
        st.success("Atualizado com sucesso.")

    if st.button("Deletar"):
        batch_delete_rows(ws, [row_idx])
        log_event("user", "delete", tag)
        st.success("Excluído.")

###############################################################################
# UI: CURVA S
###############################################################################
def curva_s():
    st.header("Curva S")
    disciplina = st.selectbox("Disciplina", ["ELÉTRICA", "INSTRUMENTAÇÃO", "ESTRUTURA"])
    df, ws = load_sheet(SPREAD, disciplina)

    df = to_datetime(df)
    df["STATUS"] = df.apply(compute_status, axis=1)

    df["MES"] = df["DATA_FINAL"].dt.to_period("M")
    hist = df.groupby("MES").size().reset_index(name="quantidade")
    hist["acumulado"] = hist["quantidade"].cumsum()

    st.subheader("Curva Acumulada")
    st.plotly_chart(px.line(hist, x="MES", y="acumulado"))

    st.subheader("Curva Mensal")
    st.plotly_chart(px.bar(hist, x="MES", y="quantidade"))

###############################################################################
# APP ENTRYPOINT
###############################################################################
check_login()

if not st.session_state.logged:
    login_form()
else:
    page = st.sidebar.selectbox("Menu", ["Tags", "Curva S"])
    if page == "Tags":
        manage_tags()
    elif page == "Curva S":
        curva_s()
