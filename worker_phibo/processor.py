import csv
from datetime import datetime
from .database import batch_insert, clean_vendas_mes


def safe_float(val) -> float:
    """Converte valores com vírgula ou string para float com segurança."""
    if val is None or val == "":
        return 0.0
    val_str = str(val).strip().replace("R$", "").replace(" ", "")
    # Se tiver separador de milhar com ponto e decimal com vírgula: 1.234,56 -> 1234.56
    if "." in val_str and "," in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
    try:
        return float(val_str)
    except:
        return 0.0


def safe_int(val) -> int:
    """Converte valores numéricos para int com segurança."""
    try:
        return int(float(str(val).replace(",", ".")))
    except:
        return 0


def parse_date_br(val) -> str | None:
    """Converte '01/10/2026' ou '2026-10-01' para 'YYYY-MM-DD'."""
    if not val:
        return None
    val_str = str(val).strip()
    if "/" in val_str:
        parts = val_str.split("/")
        if len(parts) == 3:
            day, month, year = parts
            return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
    elif "-" in val_str and len(val_str) >= 10:
        return val_str[:10]
    return None


def parse_time_br(val) -> str:
    """Converte '09:55' para '09:55:00'."""
    if not val:
        return "00:00:00"
    val_str = str(val).strip()
    if len(val_str) == 5 and ":" in val_str:
        return f"{val_str}:00"
    return val_str


def parse_cliente(cliente_raw: str):
    """
    Extrai telefone e nome de formatos como:
    '(88) 99607-0075 - JOANA AVILA'
    """
    if not cliente_raw:
        return None, None

    raw = str(cliente_raw).strip()
    if " - " in raw:
        partes = raw.split(" - ", 1)
        telefone = partes[0].strip()
        nome = partes[1].strip()
        return telefone, nome
    
    return None, raw


def read_csv_rows(file_path: str):
    """Lê as linhas do CSV testando encodings utf-8-sig e latin1."""
    encodings = ["utf-8-sig", "utf-8", "latin1"]
    for enc in encodings:
        try:
            with open(file_path, mode="r", encoding=enc, errors="replace") as f:
                # Detecta delimitador ou usa ';'
                sample = f.read(2048)
                delimiter = ";" if ";" in sample else ","
                f.seek(0)
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = [
                    {k.strip(): v for k, v in row.items() if k is not None}
                    for row in reader
                ]
                if rows:
                    return rows
        except Exception:
            continue
    return []


def process_vendas_csv(file_path: str, cliente_id: str, ano: int = None, mes: int = None) -> int:
    """
    Lê o CSV de Vendas gerado pelo PHIBO (relacaoVendasMes.csv),
    transforma os dados, remove vendas anteriores do período (idempotência)
    e insere em lote no Supabase.
    """
    print(f"[PROCESS] Lendo arquivo de vendas PHIBO: {file_path}")
    
    rows = read_csv_rows(file_path)
    if not rows:
        print("[AVISO] Arquivo CSV não contém linhas para processamento.")
        return 0

    primeira_linha = rows[0]
    colunas_obrigatorias = ["Data da Venda", "Hora", "Total"]
    for col in colunas_obrigatorias:
        if col not in primeira_linha:
            raise ValueError(
                f"Coluna obrigatória '{col}' ausente no CSV do PHIBO. "
                f"Colunas encontradas: {list(primeira_linha.keys())}"
            )

    registros = []
    meses_encontrados = set()

    for row in rows:
        dt_venda = parse_date_br(row.get("Data da Venda"))
        if not dt_venda:
            continue

        # Identificar mês/ano a partir dos dados
        dt_obj = datetime.strptime(dt_venda, "%Y-%m-%d")
        meses_encontrados.add((dt_obj.year, dt_obj.month))

        cliente_raw = row.get("Cliente", "")
        cliente_tel, cliente_nome = parse_cliente(cliente_raw)

        registros.append({
            "cliente_id": cliente_id,
            "origem": str(row.get("Origem", "PDV")).strip(),
            "data_venda": dt_venda,
            "hora_venda": parse_time_br(row.get("Hora")),
            "cliente_nome": cliente_nome,
            "cliente_telefone": cliente_tel,
            "cliente_completo": str(cliente_raw).strip() if cliente_raw else None,
            "vendedor": str(row.get("Vendedor", "")).strip() if row.get("Vendedor") else None,
            "quantidade": safe_int(row.get("Qtde", 0)),
            "sub_total": safe_float(row.get("Sub Total", 0)),
            "desconto": safe_float(row.get("Desconto", 0)),
            "trocas": safe_float(row.get("Trocas", 0)),
            "cashback": safe_float(row.get("Cashback", 0)),
            "frete": safe_float(row.get("Frete", 0)),
            "valor_total": safe_float(row.get("Total", 0)),
        })

    if not registros:
        print("[AVISO] Nenhuma linha válida para inserção após parsing.")
        return 0

    # 1. Garantir idempotência: limpar dados dos meses presentes no arquivo
    alvos_limpeza = [(ano, mes)] if (ano and mes) else list(meses_encontrados)
    for a, m in alvos_limpeza:
        clean_vendas_mes(cliente_id, a, m)

    # 2. Inserir em lote no Supabase
    batch_insert("phibo_vendas", registros)
    print(f"[PROCESS] Sucesso! {len(registros)} vendas processadas e gravadas no Supabase.")
    return len(registros)
