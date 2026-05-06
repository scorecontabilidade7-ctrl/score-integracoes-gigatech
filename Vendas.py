import os
import re
import requests
import pandas as pd

from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from PyPDF2 import PdfReader


# -----------------------------
# CONFIG
# -----------------------------

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = os.getenv("SUPABASE_BUCKET")

TABELA = "Vendas For Men"


# -----------------------------
# HEADERS
# -----------------------------

def headers_api():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


# -----------------------------
# DATA
# -----------------------------

def data_hoje():
    return datetime.now().strftime("%Y-%m-%d")


# -----------------------------
# STORAGE
# -----------------------------

def listar_pastas():
    endpoint = f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET}"

    r = requests.post(
        endpoint,
        headers=headers_api(),
        json={"prefix": "", "limit": 1000}
    )

    if r.status_code != 200:
        print(f"[ERRO] Falha ao listar pastas: {r.text}")
        return []

    return r.json()


def localizar_pasta_hoje():
    hoje = data_hoje()

    for item in listar_pastas():
        if item.get("name") == hoje:
            return hoje

    print(f"[AVISO] Pasta de hoje não encontrada: {hoje}")
    return None


def listar_arquivos_da_pasta(nome_pasta):
    endpoint = f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET}"

    r = requests.post(
        endpoint,
        headers=headers_api(),
        json={"prefix": nome_pasta, "limit": 1000}
    )

    if r.status_code != 200:
        print(f"[ERRO] Falha ao listar arquivos da pasta {nome_pasta}: {r.text}")
        return []

    return r.json()


# -----------------------------
# RELATÓRIOS
# -----------------------------

def encontrar_relatorios(nome_pasta):

    arquivos = listar_arquivos_da_pasta(nome_pasta)

    vendas = None
    vendas_num = -1

    vendedor = None
    vendedor_num = -1

    for item in arquivos:

        nome = item.get("name", "")

        m1 = re.search(r"Relatorio de Vendas (\d+)", nome)

        if m1 and "Vendedor" not in nome:
            n = int(m1.group(1))
            if n > vendas_num:
                vendas_num = n
                vendas = nome

        m2 = re.search(r"Relatorio de Vendas Vendedor (\d+)", nome)

        if m2:
            n = int(m2.group(1))
            if n > vendedor_num:
                vendedor_num = n
                vendedor = nome

    if not vendas:
        print("[AVISO] Relatório de vendas Excel não encontrado.")

    if not vendedor:
        print("[AVISO] Relatório de vendas por vendedor PDF não encontrado.")

    return vendas, vendedor


# -----------------------------
# DOWNLOAD
# -----------------------------

def baixar_arquivo(pasta, arquivo):

    if not arquivo:
        print("[AVISO] Nenhum arquivo informado para download.")
        return None

    endpoint = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{pasta}/{arquivo}"

    r = requests.get(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )

    if r.status_code != 200:
        print(f"[ERRO] Falha ao baixar arquivo {arquivo}: {r.status_code} - {r.text}")
        return None

    if not r.content:
        print(f"[AVISO] Arquivo vazio: {arquivo}")
        return None

    return r.content


# -----------------------------
# EXCEL
# -----------------------------

def ler_excel(conteudo):

    if not conteudo:
        print("[ERRO] Excel vazio ou não encontrado.")
        return pd.DataFrame()

    try:
        df = pd.read_excel(BytesIO(conteudo))
    except Exception as e:
        print(f"[ERRO] Falha ao ler Excel: {e}")
        return pd.DataFrame()

    colunas = [
        "Venda",
        "Descrição",
        "Qtd Vendida",
        "Valor unitário",
        "SubTotal",
        "Custo",
        "Lucro",
        "Data",
        "Departamento"
    ]

    ok = [c for c in colunas if c in df.columns]

    if not ok:
        print("[ERRO] Nenhuma coluna esperada foi encontrada no Excel.")
        return pd.DataFrame()

    df = df[ok]

    df = df.rename(columns={
        "Venda": "Cod Venda",
        "Qtd Vendida": "Quant Vendida",
        "Valor unitário": "Valor Unitário",
        "SubTotal": "Total"
    })

    return df


# -----------------------------
# PDF
# -----------------------------

def ler_pdf(conteudo):

    if not conteudo:
        print("[AVISO] PDF vazio ou não encontrado. Seguindo sem dados de vendedor.")
        return pd.DataFrame(columns=["Número venda", "Cliente", "Vendedor"])

    if not conteudo.startswith(b"%PDF"):
        print("[AVISO] O conteúdo baixado não é um PDF válido. Seguindo sem dados de vendedor.")
        print(f"[DEBUG] Início do conteúdo recebido: {conteudo[:100]}")
        return pd.DataFrame(columns=["Número venda", "Cliente", "Vendedor"])

    try:
        reader = PdfReader(BytesIO(conteudo))
    except Exception as e:
        print(f"[ERRO] Falha ao ler PDF: {e}")
        print("[AVISO] Seguindo sem dados de vendedor.")
        return pd.DataFrame(columns=["Número venda", "Cliente", "Vendedor"])

    vendedor_atual = None
    registros = []

    for pagina in reader.pages:

        try:
            texto = pagina.extract_text()
        except Exception:
            continue

        if not texto:
            continue

        for linha in texto.splitlines():

            linha = linha.strip()

            if not linha:
                continue

            if (
                "TOTAL" in linha.upper()
                or "COMISSÃO" in linha.upper()
                or "TIPO VENDA" in linha.upper()
                or linha.upper() == "VENDEDOR"
            ):
                continue

            if "SEM SUPERVISOR" in linha.upper():

                vendedor_atual = re.sub(
                    r"\s+SEM SUPERVISOR.*$",
                    "",
                    linha,
                    flags=re.IGNORECASE
                ).strip()

                continue

            match = re.search(
                r'^(.*?)\s+\d{2}/\d{2}/\d{4}\s+(\d{6,})',
                linha
            )

            if match:

                cliente = match.group(1).strip()
                numero = match.group(2)

                registros.append({
                    "Número venda": numero,
                    "Cliente": cliente,
                    "Vendedor": vendedor_atual
                })

    return pd.DataFrame(registros, columns=["Número venda", "Cliente", "Vendedor"])


# -----------------------------
# JOIN
# -----------------------------

def cruzar_dados(df_vendas, df_vendedor):

    if df_vendas.empty:
        print("[AVISO] DataFrame de vendas vazio. Nada para cruzar.")
        return pd.DataFrame()

    df_vendas = df_vendas.copy()
    df_vendas["Cod Venda"] = df_vendas["Cod Venda"].astype(str).str.strip()

    if df_vendedor.empty:
        print("[AVISO] Sem dados de vendedor. Inserindo vendas sem Cliente/Vendedor.")
        df_vendas["Cliente"] = None
        df_vendas["Vendedor"] = None
        return df_vendas

    df_vendedor = df_vendedor.copy()
    df_vendedor["Número venda"] = df_vendedor["Número venda"].astype(str).str.strip()

    df = df_vendas.merge(
        df_vendedor[["Número venda", "Cliente", "Vendedor"]],
        left_on="Cod Venda",
        right_on="Número venda",
        how="left"
    )

    return df.drop(columns=["Número venda"])


# -----------------------------
# FILTRO DUPLICADOS
# -----------------------------

def filtrar_novas_vendas(df):

    if df.empty:
        return df

    df = df.copy()

    df["Cod Venda"] = df["Cod Venda"].astype(str).str.strip()

    codigos = ",".join(df["Cod Venda"].unique().tolist())

    tabela = TABELA.replace(" ", "%20")

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/{tabela}"
        f"?select=Cod%20Venda&Cod%20Venda=in.({codigos})"
    )

    r = requests.get(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )

    if r.status_code != 200:
        raise Exception(r.text)

    existentes = {
        str(item["Cod Venda"]).strip()
        for item in r.json()
        if item.get("Cod Venda")
    }

    return df[~df["Cod Venda"].isin(existentes)]


# -----------------------------
# BUSCA ÚLTIMO ID
# -----------------------------

def buscar_ultimo_id():

    tabela = TABELA.replace(" ", "%20")

    endpoint = (
        f"{SUPABASE_URL}/rest/v1/{tabela}"
        f"?select=ID&order=ID.desc&limit=1"
    )

    r = requests.get(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
    )

    if r.status_code != 200:
        raise Exception(r.text)

    dados = r.json()

    if not dados:
        return 0

    return int(dados[0]["ID"])


# -----------------------------
# GERA IDS
# -----------------------------

def gerar_ids(df):

    df = df.copy()

    ultimo_id = buscar_ultimo_id()

    df.insert(
        0,
        "ID",
        range(ultimo_id + 1, ultimo_id + 1 + len(df))
    )

    return df


# -----------------------------
# NORMALIZA JSON
# -----------------------------

def normalizar_df(df):

    df = df.copy()

    colunas_numericas = [
        "Quant Vendida",
        "Valor Unitário",
        "Total",
        "Custo",
        "Lucro"
    ]

    def limpar_valor(x):

        if pd.isna(x):
            return None

        if isinstance(x, str):
            x = x.strip()

            if x == "":
                return None

        if isinstance(x, pd.Timestamp):
            return x.strftime("%Y-%m-%d %H:%M:%S")

        return x

    def converter_numero(x):

        if pd.isna(x):
            return None

        if isinstance(x, str):
            x = x.strip()

            if x == "":
                return None

            x = x.replace(".", "").replace(",", ".")

            return float(x)

        return x

    for col in df.columns:
        df[col] = df[col].apply(limpar_valor)

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(converter_numero)

    return df


# -----------------------------
# INSERT
# -----------------------------

def inserir_novas_vendas(df):

    if df.empty:
        print("\nNenhuma venda nova para inserir.")
        return

    tabela = TABELA.replace(" ", "%20")
    endpoint = f"{SUPABASE_URL}/rest/v1/{tabela}"

    df = gerar_ids(df)
    df = normalizar_df(df)

    payload = df.to_dict(orient="records")

    for registro in payload:
        for chave, valor in registro.items():

            if pd.isna(valor):
                registro[chave] = None

    r = requests.post(
        endpoint,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        },
        json=payload
    )

    if r.status_code not in [200, 201]:
        raise Exception(r.text)

    print(f"\n{len(df)} novas vendas inseridas.")


# -----------------------------
# MAIN
# -----------------------------

def main():

    pasta = localizar_pasta_hoje()

    if not pasta:
        print("[FINALIZADO] Nenhuma pasta encontrada para hoje.")
        return

    print(f"Pasta encontrada: {pasta}")

    rel_vendas, rel_vendedor = encontrar_relatorios(pasta)

    if not rel_vendas:
        print("[FINALIZADO] Relatório principal de vendas não encontrado.")
        return

    excel_bytes = baixar_arquivo(pasta, rel_vendas)
    pdf_bytes = baixar_arquivo(pasta, rel_vendedor)

    df_vendas = ler_excel(excel_bytes)

    if df_vendas.empty:
        print("[FINALIZADO] Nenhuma venda encontrada no Excel.")
        return

    df_vendedor = ler_pdf(pdf_bytes)

    df_final = cruzar_dados(df_vendas, df_vendedor)

    if df_final.empty:
        print("[FINALIZADO] Nenhum dado consolidado para processar.")
        return

    print("\nRELATÓRIO CONSOLIDADO:\n")
    print(df_final.to_string(index=False))

    novos = filtrar_novas_vendas(df_final)

    inserir_novas_vendas(novos)


if __name__ == "__main__":
    main()
