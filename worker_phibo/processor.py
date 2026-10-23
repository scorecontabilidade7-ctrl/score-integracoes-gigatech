import csv
from datetime import datetime
from .database import batch_insert, clean_vendas_mes, clean_vendas_periodo


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


def process_vendas_csv(
    file_path: str,
    cliente_id: str,
    ano: int = None,
    mes: int = None,
    data_inicio: str = None,
    data_fim: str = None
) -> int:
    """
    Lê o CSV de Vendas gerado pelo PHIBO (relacaoVendasMes.csv),
    transforma os dados, remove vendas anteriores do período (idempotência),
    insere em lote no Supabase e realiza a conciliação/validação dos dados.
    """
    print(f"[PROCESS] Lendo arquivo de vendas PHIBO: {file_path}")
    
    rows = read_csv_rows(file_path)
    total_linhas_csv = len(rows)
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
    linhas_ignoradas = 0

    for row in rows:
        dt_venda = parse_date_br(row.get("Data da Venda"))
        if not dt_venda:
            linhas_ignoradas += 1
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

    # Totais calculados para auditoria e controle de valores
    total_itens_pecas = sum(r["quantidade"] for r in registros)
    total_faturamento = sum(r["valor_total"] for r in registros)
    total_descontos = sum(r["desconto"] for r in registros)
    total_subtotal = sum(r["sub_total"] for r in registros)

    # 1. Garantir idempotência: limpar dados do período antes de inserir
    if data_inicio and data_fim:
        dt_ini_iso = parse_date_br(data_inicio) or data_inicio
        dt_fim_iso = parse_date_br(data_fim) or data_fim
        clean_vendas_periodo(cliente_id, dt_ini_iso, dt_fim_iso)
    else:
        alvos_limpeza = [(ano, mes)] if (ano and mes) else list(meses_encontrados)
        for a, m in alvos_limpeza:
            clean_vendas_mes(cliente_id, a, m)

    # 2. Inserir em lote no Supabase
    inseridos_total = batch_insert("phibo_vendas", registros)

    # 3. Conciliação e Validação dos Dados
    divergencia_itens = len(registros) - inseridos_total
    if data_inicio and data_fim:
        periodo_str = f"{data_inicio} até {data_fim}"
    elif mes and ano:
        periodo_str = f"{mes:02d}/{ano}"
    else:
        periodo_str = f"{sorted(list(meses_encontrados))}"

    print("=" * 70)
    print(f"[AUDITORIA] CONCILIAÇÃO DE CARGA PHIBO - CLIENTE: {cliente_id}")
    print(f"[AUDITORIA] Período Alvo: {periodo_str}")
    print("-" * 70)
    print(f"• Linhas brutas no arquivo CSV:    {total_linhas_csv}")
    print(f"• Registros de vendas tratados:    {len(registros)}")
    if linhas_ignoradas > 0:
        print(f"• Linhas ignoradas (sem data):     {linhas_ignoradas}")
    print(f"• Registros gravados no Supabase:  {inseridos_total}")
    print(f"• Quantidade total de peças:       {total_itens_pecas}")
    print(f"• Subtotal das Vendas:             R$ {total_subtotal:,.2f}")
    print(f"• Total de Descontos concedidos:   R$ {total_descontos:,.2f}")
    print(f"• Faturamento Total Líquido (R$):  R$ {total_faturamento:,.2f}")
    print(f"• Divergência de Inserção:         {divergencia_itens} item(ns)")
    print("-" * 70)

    if divergencia_itens != 0:
        msg_erro = (
            f"[ERRO DE CONCILIAÇÃO] Divergência detectada! "
            f"Esperado gravar {len(registros)} vendas, mas o Supabase confirmou {inseridos_total}."
        )
        print(msg_erro)
        print("=" * 70)
        raise ValueError(msg_erro)

    print("[STATUS] 100% DOS DADOS CONCILIADOS E GRAVADOS COM SUCESSO!")
    print("=" * 70)

    return inseridos_total
