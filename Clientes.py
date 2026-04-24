import os
import re
import io
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional
from difflib import SequenceMatcher

import requests
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "")
SUPABASE_FOLDER_BASE = os.getenv("SUPABASE_FOLDER_BASE", "").strip("/")

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_BUCKET:
    raise ValueError(
        "Preencha SUPABASE_URL, SUPABASE_KEY e SUPABASE_BUCKET no .env"
    )

HEADERS_JSON = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

HEADERS_AUTH = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}


def normalize_name(name: str) -> str:
    if not name:
        return ""

    name = name.strip().lower()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = re.sub(r"\s+", " ", name)

    return name


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def today_folder() -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    return f"{SUPABASE_FOLDER_BASE}/{today}" if SUPABASE_FOLDER_BASE else today


def list_storage_files(folder_path: str) -> List[Dict]:
    url = f"{SUPABASE_URL}/storage/v1/object/list/{SUPABASE_BUCKET}"
    payload = {"prefix": folder_path}

    resp = requests.post(url, headers=HEADERS_JSON, json=payload, timeout=60)
    resp.raise_for_status()

    return resp.json()


def is_clientes_novos_pdf(name: str) -> bool:
    n = name.lower().strip()
    return "cliente" in n and "novo" in n and n.endswith(".pdf")


def extract_execution_number(name: str) -> int:
    match = re.search(r"(\d+)(?=\.pdf$)", name, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def choose_latest_client_pdf(files: List[Dict]) -> Optional[str]:
    candidates = []

    for f in files:
        name = f.get("name", "")
        if is_clientes_novos_pdf(name):
            candidates.append((extract_execution_number(name), name))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def download_storage_file(full_path: str) -> bytes:
    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{full_path}"

    resp = requests.get(url, headers=HEADERS_AUTH, timeout=120)
    resp.raise_for_status()

    return resp.content


def parse_date_br(date_str: str) -> Optional[str]:
    if not date_str:
        return None

    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def clean_nome(raw_nome: str) -> str:
    nome = raw_nome.strip()

    nome = re.sub(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b", "", nome).strip()
    nome = re.sub(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", "", nome).strip()
    nome = re.sub(r"\S+@\S+\.\S+", "", nome).strip()
    nome = re.sub(r"\s+", " ", nome).strip()

    return nome


def should_skip_line(line: str) -> bool:
    linha_lower = line.lower()

    skip_terms = [
        "documento",
        "e-mail",
        "email",
        "página",
        "pagina",
        "emitido",
        "relatório",
        "relatorio",
        "período",
        "periodo",
        "sobral - ce",
        "nome cadastro",
    ]

    if "nome" in linha_lower and "cadastro" in linha_lower:
        return True

    return any(term in linha_lower for term in skip_terms)


def extract_nome_cadastro_from_text(pdf_bytes: bytes) -> List[Dict]:
    resultados = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            if not text:
                print(f"[DEBUG] Página {page_num} sem texto.")
                continue

            linhas = [linha.strip() for linha in text.split("\n") if linha.strip()]
            print(f"[DEBUG] Página {page_num} - {len(linhas)} linhas encontradas")

            for linha in linhas:
                if should_skip_line(linha):
                    continue

                match_data = re.search(r"(\d{2}/\d{2}/\d{4})$", linha)

                if not match_data:
                    continue

                data_str = match_data.group(1)
                data_iso = parse_date_br(data_str)

                conteudo_sem_data = linha[:match_data.start()].strip()

                if not conteudo_sem_data:
                    continue

                nome = clean_nome(conteudo_sem_data)

                if len(nome) < 3:
                    continue

                if any(
                    termo in nome.lower()
                    for termo in [
                        "período",
                        "periodo",
                        "sobral - ce",
                        "emitido",
                        "relatório",
                        "relatorio",
                    ]
                ):
                    continue

                resultados.append(
                    {
                        "nome_cliente": nome,
                        "data_cadastro": data_iso,
                    }
                )

    unicos = {}

    for item in resultados:
        chave = (
            normalize_name(item["nome_cliente"]),
            item["data_cadastro"],
        )

        if chave not in unicos:
            unicos[chave] = item

    return list(unicos.values())


def fetch_existing_clients() -> List[Dict]:
    url = f"{SUPABASE_URL}/rest/v1/clientes"

    params = {
        "select": "id,nome_cliente,data_cadastro"
    }

    resp = requests.get(url, headers=HEADERS_AUTH, params=params, timeout=60)
    resp.raise_for_status()

    return resp.json()


def update_clients(records: List[Dict]) -> None:
    if not records:
        print("[INFO] Nenhum cliente para atualizar.")
        return

    url_base = f"{SUPABASE_URL}/rest/v1/clientes"

    headers = {
        **HEADERS_JSON,
        "Prefer": "return=representation",
    }

    updated_count = 0

    for record in records:
        client_id = record["id"]

        payload = {
            "nome_cliente": record["nome_cliente"],
            "data_cadastro": record["data_cadastro"],
        }

        url = f"{url_base}?id=eq.{client_id}"

        resp = requests.patch(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        updated_count += 1

    print(f"[INFO] {updated_count} cliente(s) atualizado(s) com sucesso.")


def insert_clients(records: List[Dict]) -> None:
    if not records:
        print("[INFO] Nenhum novo cliente para inserir.")
        return

    url = f"{SUPABASE_URL}/rest/v1/clientes"

    headers = {
        **HEADERS_JSON,
        "Prefer": "return=representation",
    }

    resp = requests.post(url, headers=headers, json=records, timeout=60)
    resp.raise_for_status()

    inserted = resp.json()

    print(f"[INFO] {len(inserted)} cliente(s) inserido(s) com sucesso.")


def sync_clients(rows: List[Dict], existing_clients: List[Dict]) -> None:
    inserts = []
    updates = []
    processed_keys = set()

    for row in rows:
        nome_pdf = row.get("nome_cliente", "").strip()
        data_pdf = row.get("data_cadastro")

        if not nome_pdf or not data_pdf:
            continue

        nome_pdf_norm = normalize_name(nome_pdf)

        key_lote = (nome_pdf_norm, data_pdf)

        if key_lote in processed_keys:
            print(f"[DEBUG] DUPLICADO NO PDF: {nome_pdf} - {data_pdf}")
            continue

        processed_keys.add(key_lote)

        exact_match = None

        for client in existing_clients:
            nome_banco = client.get("nome_cliente", "")
            data_banco = client.get("data_cadastro")

            if normalize_name(nome_banco) == nome_pdf_norm and data_banco == data_pdf:
                exact_match = client
                break

        if exact_match:
            print(f"[DEBUG] JÁ EXISTE IGUAL: {nome_pdf} - {data_pdf}")
            continue

        similar_match = None
        best_score = 0

        for client in existing_clients:
            nome_banco = client.get("nome_cliente", "")
            data_banco = client.get("data_cadastro")

            if data_banco != data_pdf:
                continue

            score = similarity(nome_pdf, nome_banco)

            if score > best_score:
                best_score = score
                similar_match = client

        if similar_match and best_score >= 0.80:
            nome_antigo = similar_match.get("nome_cliente")
            client_id = similar_match.get("id")

            if normalize_name(nome_antigo) != nome_pdf_norm:
                print(
                    f"[DEBUG] UPDATE: {nome_antigo} -> {nome_pdf} | "
                    f"Data: {data_pdf} | Similaridade: {best_score:.2f}"
                )

                updates.append(
                    {
                        "id": client_id,
                        "nome_cliente": nome_pdf,
                        "data_cadastro": data_pdf,
                    }
                )

            continue

        print(f"[DEBUG] INSERT: {nome_pdf} - {data_pdf}")

        inserts.append(
            {
                "nome_cliente": nome_pdf,
                "data_cadastro": data_pdf,
            }
        )

    update_clients(updates)
    insert_clients(inserts)


def main():
    try:
        folder = today_folder()
        print(f"[INFO] Pasta do dia: {folder}")

        files = list_storage_files(folder)

        if not files:
            print("[INFO] Nenhum arquivo encontrado na pasta.")
            return

        latest_pdf = choose_latest_client_pdf(files)

        if not latest_pdf:
            print("[INFO] Nenhum PDF de Clientes Novos encontrado.")
            print("[DEBUG] Arquivos encontrados:")

            for f in files:
                print("-", f.get("name", "sem nome"))

            return

        full_path = f"{folder}/{latest_pdf}"

        print(f"[INFO] Arquivo escolhido: {full_path}")

        pdf_bytes = download_storage_file(full_path)

        print(f"[INFO] PDF baixado com sucesso. Tamanho: {len(pdf_bytes)} bytes")

        rows = extract_nome_cadastro_from_text(pdf_bytes)

        print(f"[INFO] Registros extraídos do PDF: {len(rows)}")

        if not rows:
            print("[INFO] Nenhum registro válido foi extraído do PDF.")
            return

        print("\n===== DADOS EXTRAÍDOS =====")

        for item in rows[:20]:
            print(item)

        existing_clients = fetch_existing_clients()

        print(f"\n[INFO] Clientes já cadastrados no banco: {len(existing_clients)}")

        sync_clients(rows, existing_clients)

        print("[INFO] Processo finalizado com sucesso.")

    except requests.HTTPError as e:
        print(f"[ERRO HTTP] {e}")

        if e.response is not None:
            print("[DETALHE]", e.response.text)

    except Exception as e:
        print(f"[ERRO] {e}")


if __name__ == "__main__":
    main()