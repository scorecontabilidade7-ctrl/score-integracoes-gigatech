import requests
from datetime import datetime
import os
import re
import pandas as pd
from io import BytesIO
from urllib.parse import quote
from decimal import Decimal, InvalidOperation

from dotenv import load_dotenv
load_dotenv()

# ==============================
# CONFIGURAÇÕES (ENV VARIABLES)
# ==============================
url_supabase = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET")
SUPABASE_FOLDER_BASE = os.getenv("SUPABASE_FOLDER_BASE", "")
SUPABASE_TABLE_ESTOQUE = os.getenv("SUPABASE_TABLE_ESTOQUE")


# ==============================
# GERAR DATA NO FORMATO YYYY-MM-DD
# ==============================
def get_today_folder():
    today = datetime.now()
    return today.strftime("%Y-%m-%d")


# ==============================
# MONTAR CAMINHO DA PASTA
# ==============================
def build_folder_path():
    folder_date = get_today_folder()
    
    if SUPABASE_FOLDER_BASE:
        return f"{SUPABASE_FOLDER_BASE}/{folder_date}"
    else:
        return folder_date


# ==============================
# LISTAR ARQUIVOS DA PASTA
# ==============================
def list_files_from_folder(folder_path):
    url = f"{url_supabase}/storage/v1/object/list/{SUPABASE_BUCKET}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "prefix": folder_path
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"Erro ao acessar Supabase: {response.status_code}")
        print(response.text)
        return None

    return response.json()


# ==============================
# PEGAR RELATÓRIO DE CUSTO DE ESTOQUE COM MAIOR NÚMERO
# ==============================
def get_latest_custo_estoque(files):
    latest_file = None
    latest_number = -1

    for file in files:
        name = file.get("name", "")

        match = re.search(r"relat[oó]rio de custo estoque\s*(\d+)", name, re.IGNORECASE)

        if match:
            number = int(match.group(1))

            if number > latest_number:
                latest_number = number
                latest_file = file

    return latest_file


# ==============================
# LER PLANILHA EXCEL DIRETO DO SUPABASE
# ==============================
def read_excel_from_supabase(folder_path, file_name):
    file_path = f"{folder_path}/{file_name}"
    url = f"{url_supabase}/storage/v1/object/{SUPABASE_BUCKET}/{file_path}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Erro ao ler arquivo: {response.status_code}")
        print(response.text)
        return None

    df = pd.read_excel(BytesIO(response.content))

    return df


# ==============================
# LER TABELA ESTOQUE DO SUPABASE COM PAGINAÇÃO
# ==============================
def read_estoque_table_from_supabase():
    table_name = quote(SUPABASE_TABLE_ESTOQUE, safe="")
    url = f"{url_supabase}/rest/v1/{table_name}?select=*"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }

    todos_registros = []
    inicio = 0
    limite = 1000

    while True:
        headers_paginado = headers.copy()
        headers_paginado["Range"] = f"{inicio}-{inicio + limite - 1}"

        response = requests.get(url, headers=headers_paginado)

        if response.status_code not in [200, 206]:
            print(f"Erro ao ler tabela do Supabase: {response.status_code}")
            print(response.text)
            return None

        registros = response.json()

        if not registros:
            break

        todos_registros.extend(registros)

        if len(registros) < limite:
            break

        inicio += limite

    return pd.DataFrame(todos_registros)


# ==============================
# NORMALIZAR DECIMAL
# ==============================
def normalizar_decimal(valor):
    if pd.isna(valor):
        return Decimal("0.00")

    valor = str(valor).strip()
    valor = valor.replace("R$", "")
    valor = valor.replace(" ", "")

    if "," in valor:
        valor = valor.replace(".", "")
        valor = valor.replace(",", ".")

    try:
        return Decimal(valor).quantize(Decimal("0.01"))
    except InvalidOperation:
        return Decimal("0.00")


def decimal_para_json(valor):
    if valor == valor.to_integral():
        return int(valor)

    return float(valor)


# ==============================
# NORMALIZAR VALORES PARA COMPARAÇÃO
# ==============================
def normalizar_valor(valor):
    return normalizar_decimal(valor)


def normalizar_quantidade(valor):
    if pd.isna(valor):
        return Decimal("0")

    valor = str(valor).strip()
    valor = valor.replace(" ", "")

    if "," in valor and "." in valor:
        valor = valor.replace(".", "")
        valor = valor.replace(",", ".")
    elif "," in valor:
        valor = valor.replace(",", ".")

    try:
        return Decimal(valor)
    except InvalidOperation:
        return Decimal("0")


def normalizar_ean(valor):
    if pd.isna(valor):
        return ""

    valor = str(valor).strip()

    try:
        return str(int(float(valor)))
    except:
        return valor.replace(".0", "").strip()


# ==============================
# ATUALIZAR ITEM NO SUPABASE
# ==============================
def update_item_estoque_supabase(item):
    table_name = quote(SUPABASE_TABLE_ESTOQUE, safe="")
    ean = quote(str(item["EAN"]), safe="")
    url = f"{url_supabase}/rest/v1/{table_name}?EAN=eq.{ean}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    payload = {
        "Custo": float(item["Novo Custo"]),
        "Valor de Venda": float(item["Novo Valor de Venda"]),
        "Quantidade": decimal_para_json(item["Nova Quantidade"])
    }

    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code not in [200, 204]:
        print(f"Erro ao atualizar EAN {item['EAN']}: {response.status_code}")
        print(response.text)
        return False

    return True


# ==============================
# INSERIR ITEM NO SUPABASE
# ==============================
def insert_item_estoque_supabase(item):
    table_name = quote(SUPABASE_TABLE_ESTOQUE, safe="")
    url = f"{url_supabase}/rest/v1/{table_name}"

    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    payload = {
        "EAN": item["EAN"],
        "Descricao": item["Descricao"],
        "Custo": float(item["Novo Custo"]),
        "Valor de Venda": float(item["Novo Valor de Venda"]),
        "Quantidade": decimal_para_json(item["Nova Quantidade"])
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 409:
        atualizado = update_item_estoque_supabase(item)
        return atualizado

    if response.status_code not in [200, 201, 204]:
        print(f"Erro ao inserir EAN {item['EAN']}: {response.status_code}")
        print(response.text)
        return False

    return True


# ==============================
# COMPARAR ESTOQUE
# ==============================
def comparar_estoque(df_arquivo, df_supabase):
    colunas_arquivo = ["COD_EAN", "VAL_CUSTO_TOTAL", "VAL_VENDA", "QTD_ESTOQUE_ATUAL"]
    colunas_supabase = ["EAN", "Custo", "Valor de Venda", "Quantidade"]

    for coluna in colunas_arquivo:
        if coluna not in df_arquivo.columns:
            print(f"Coluna não encontrada no arquivo: {coluna}")
            return None, None

    for coluna in colunas_supabase:
        if coluna not in df_supabase.columns:
            print(f"Coluna não encontrada no Supabase: {coluna}")
            return None, None

    df_arquivo = df_arquivo.copy()
    df_supabase = df_supabase.copy()

    df_arquivo["COD_EAN"] = df_arquivo["COD_EAN"].apply(normalizar_ean)
    df_supabase["EAN"] = df_supabase["EAN"].apply(normalizar_ean)

    df_arquivo = df_arquivo[df_arquivo["COD_EAN"] != ""]
    df_supabase = df_supabase[df_supabase["EAN"] != ""]

    df_arquivo["VAL_CUSTO_TOTAL"] = df_arquivo["VAL_CUSTO_TOTAL"].apply(normalizar_valor)
    df_supabase["Custo"] = df_supabase["Custo"].apply(normalizar_valor)

    df_arquivo["VAL_VENDA"] = df_arquivo["VAL_VENDA"].apply(normalizar_valor)
    df_supabase["Valor de Venda"] = df_supabase["Valor de Venda"].apply(normalizar_valor)

    df_arquivo["QTD_ESTOQUE_ATUAL"] = df_arquivo["QTD_ESTOQUE_ATUAL"].apply(normalizar_quantidade)
    df_supabase["Quantidade"] = df_supabase["Quantidade"].apply(normalizar_quantidade)

    df_arquivo = df_arquivo.drop_duplicates(subset=["COD_EAN"], keep="last")
    df_supabase = df_supabase.drop_duplicates(subset=["EAN"], keep="last")

    eans_supabase = set(df_supabase["EAN"].astype(str).str.strip())

    df_comparado = df_arquivo.merge(
        df_supabase,
        left_on="COD_EAN",
        right_on="EAN",
        how="inner"
    )

    df_novos = df_arquivo[
        ~df_arquivo["COD_EAN"].astype(str).str.strip().isin(eans_supabase)
    ]

    alterados = []
    novos = []

    for _, row in df_comparado.iterrows():
        mudancas = []

        if row["VAL_CUSTO_TOTAL"] != row["Custo"]:
            mudancas.append(f"Custo: {row['Custo']} -> {row['VAL_CUSTO_TOTAL']}")

        if row["VAL_VENDA"] != row["Valor de Venda"]:
            mudancas.append(f"Valor de Venda: {row['Valor de Venda']} -> {row['VAL_VENDA']}")

        if row["QTD_ESTOQUE_ATUAL"] != row["Quantidade"]:
            mudancas.append(f"Quantidade: {row['Quantidade']} -> {row['QTD_ESTOQUE_ATUAL']}")

        if mudancas:
            alterados.append({
                "EAN": str(row["EAN"]).strip(),
                "Descricao": row.get("DES_PRODUTO", row.get("Descricao", "")),
                "Alteracoes": " | ".join(mudancas),
                "Novo Custo": row["VAL_CUSTO_TOTAL"],
                "Novo Valor de Venda": row["VAL_VENDA"],
                "Nova Quantidade": row["QTD_ESTOQUE_ATUAL"]
            })

    for _, row in df_novos.iterrows():
        ean = str(row["COD_EAN"]).strip()

        if ean in eans_supabase:
            continue

        novos.append({
            "EAN": ean,
            "Descricao": row.get("DES_PRODUTO", row.get("Descricao", "")),
            "Novo Custo": row["VAL_CUSTO_TOTAL"],
            "Novo Valor de Venda": row["VAL_VENDA"],
            "Nova Quantidade": row["QTD_ESTOQUE_ATUAL"]
        })

    return alterados, novos


# ==============================
# EXECUÇÃO PRINCIPAL
# ==============================
def main():
    folder_path = build_folder_path()
    print(f"Buscando arquivos na pasta: {folder_path}")

    files = list_files_from_folder(folder_path)

    if not files:
        print("Nenhum arquivo encontrado ou erro na requisição.")
        return

    latest_file = get_latest_custo_estoque(files)

    if not latest_file:
        print("Nenhum relatório de custo de estoque encontrado.")
        return

    print(f"\nRelatório selecionado: {latest_file.get('name')}")

    df_arquivo = read_excel_from_supabase(folder_path, latest_file.get("name"))

    if df_arquivo is None:
        return

    df_supabase = read_estoque_table_from_supabase()

    if df_supabase is None:
        return

    print(f"Total de itens no arquivo: {len(df_arquivo)}")
    print(f"Total de itens lidos do Supabase: {len(df_supabase)}")

    itens_alterados, itens_novos = comparar_estoque(df_arquivo, df_supabase)

    if itens_alterados is None or itens_novos is None:
        return

    if not itens_alterados and not itens_novos:
        print("\nNenhum item alterado ou novo encontrado.")
        return

    if itens_alterados:
        print("\nItens alterados encontrados:")

        for item in itens_alterados:
            print(f"\nEAN: {item['EAN']}")
            print(f"Descrição: {item['Descricao']}")
            print(f"Alterações: {item['Alteracoes']}")
            print(f"Quantidade enviada: {item['Nova Quantidade']}")

            atualizado = update_item_estoque_supabase(item)

            if atualizado:
                print("Status: Atualizado no Supabase")

    if itens_novos:
        print("\nItens novos encontrados:")

        for item in itens_novos:
            print(f"\nEAN: {item['EAN']}")
            print(f"Descrição: {item['Descricao']}")
            print(f"Quantidade enviada: {item['Nova Quantidade']}")

            inserido = insert_item_estoque_supabase(item)

            if inserido:
                print("Status: Inserido no Supabase")


if __name__ == "__main__":
    main()