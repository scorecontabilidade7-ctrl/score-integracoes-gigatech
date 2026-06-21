import pandas as pd
import unicodedata
from datetime import datetime
from pathlib import Path

def normalize_column_name(col):
    """
    Remove acentos, converte para minúsculas, remove caracteres especiais e substitui espaços por '_'.
    """
    if pd.isna(col) or col is None:
        return ""
    col_str = str(col)
    col_str = unicodedata.normalize('NFKD', col_str).encode('ASCII', 'ignore').decode('utf-8')
    col_str = col_str.lower().strip()
    col_str = col_str.replace(' ', '_').replace('?', '').replace('-', '_').replace('$', '').replace('__', '_')
    return col_str

def to_float(val):
    """
    Converte valores monetários ou numéricos do formato BR ("1.250,50") para float.
    """
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    if ',' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    try:
        return float(val_str)
    except ValueError:
        return None

def format_phone(val):
    """
    Formata campos de telefone para string limpa.
    """
    if pd.isna(val) or val is None:
        return None
    try:
        # Se for científico ou float (ex: 8.581945e+09)
        val_float = float(val)
        return str(int(val_float))
    except:
        return str(val).strip()

def format_date(val):
    """
    Converte datas em strings de formatos variados para formato ISO (YYYY-MM-DD).
    """
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    # Pega apenas a data antes do espaço (caso venha com timestamp)
    val_date = val_str.split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(val_date, fmt).date().isoformat()
        except ValueError:
            pass
    return val_date

def get_first_day_of_month(date_str):
    """
    Retorna o primeiro dia do mês de uma data em formato dd/mm/yyyy ou yyyy-mm-dd.
    """
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        return dt.replace(day=1).date().isoformat()
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(day=1).date().isoformat()
        except Exception:
            return date_str


def process_faturamento_excel(file_path: str, cliente_id: str, data_inicial: str) -> list:
    """
    Processa o arquivo Faturamento.xlsx.
    Filtra linhas vazias e a linha de 'Valor Total', e atribui a data para o 1º dia do mês filtrado.
    """
    print(f"[PROCESSADOR] Processando faturamento: {file_path}")
    if not Path(file_path).exists():
        print(f"[PROCESSADOR] [ERRO] Arquivo não encontrado: {file_path}")
        return []

    df = pd.read_excel(file_path)
    if df.empty:
        return []

    # Normalizar nomes das colunas
    df.columns = [normalize_column_name(col) for col in df.columns]
    
    # Identificar a coluna do profissional (primeira coluna) e do valor (última coluna)
    col_prof = df.columns[0]
    col_valor = df.columns[-1]

    # Primeiro dia do mês da extração
    dt_faturamento = get_first_day_of_month(data_inicial)

    records = []
    for _, row in df.iterrows():
        prof = row[col_prof]
        val = row[col_valor]

        if pd.isna(prof) or str(prof).strip().upper() in ("VALOR TOTAL", "TOTAL", ""):
            continue

        valor_fat = to_float(val)
        if valor_fat is None or valor_fat == 0:
            continue

        records.append({
            "cliente_id": cliente_id,
            "profissional": str(prof).strip(),
            "valor_faturamento": valor_fat,
            "data": dt_faturamento
        })

    print(f"[PROCESSADOR] {len(records)} registros de faturamento profissional extraídos.")
    return records


def process_orcamentos_excel(file_path: str, cliente_id: str) -> list:
    """
    Processa o arquivo Orçamentos.xlsx.
    """
    print(f"[PROCESSADOR] Processando orçamentos: {file_path}")
    if not Path(file_path).exists():
        print(f"[PROCESSADOR] [ERRO] Arquivo não encontrado: {file_path}")
        return []

    df = pd.read_excel(file_path)
    if df.empty:
        return []

    # Normalizar nomes de colunas
    df.columns = [normalize_column_name(col) for col in df.columns]

    # Mapeamento robusto de colunas normalized -> db fields
    col_mapping = {
        "data_criacao": "data_criacao",
        "data_criaco": "data_criacao",
        "data": "data",
        "status": "status",
        "motivo": "motivo",
        "profissional": "profissional",
        "paciente": "paciente",
        "telefone": "telefone",
        "procedimentos": "procedimentos",
        "valor": "valor",
        "valor_total_com_desconto": "valor_total_com_desconto",
        "observacoes": "observacoes",
        "observaões": "observacoes",
        "observaoes": "observacoes",
        "como_conheceu": "como_conheceu",
        "desconto_porcentagem": "desconto_porcentagem",
        "desconto_reais": "desconto_reais",
        "valor_total": "valor_total",
        "ticket_medio": "ticket_medio",
        "ticket_medio": "ticket_medio"
    }

    records = []
    for _, row in df.iterrows():
        rec = {"cliente_id": cliente_id}
        
        # Mapeia colunas existentes no DataFrame
        for col_name in df.columns:
            db_field = col_mapping.get(col_name)
            if db_field:
                val = row[col_name]
                
                # Tratamento específico de tipos
                if db_field in ("data_criacao", "data"):
                    rec[db_field] = format_date(val)
                elif db_field in ("valor", "valor_total_com_desconto", "desconto_porcentagem", "desconto_reais", "valor_total", "ticket_medio"):
                    rec[db_field] = to_float(val)
                elif db_field == "telefone":
                    rec[db_field] = format_phone(val)
                else:
                    rec[db_field] = str(val).strip() if not pd.isna(val) else None
        
        # Só adiciona se tiver paciente ou profissional preenchido (linha válida)
        if rec.get("paciente") or rec.get("profissional"):
            records.append(rec)

    print(f"[PROCESSADOR] {len(records)} orçamentos extraídos.")
    return records


def process_primeira_consulta_excel(file_path: str, cliente_id: str) -> list:
    """
    Processa o arquivo Primeira Consulta.xlsx.
    """
    print(f"[PROCESSADOR] Processando primeiras consultas: {file_path}")
    if not Path(file_path).exists():
        print(f"[PROCESSADOR] [ERRO] Arquivo não encontrado: {file_path}")
        return []

    df = pd.read_excel(file_path)
    if df.empty:
        return []

    df.columns = [normalize_column_name(col) for col in df.columns]

    col_mapping = {
        "data": "data",
        "status": "status",
        "nome": "nome",
        "como_conheceu": "como_conheceu",
        "observacoes": "observacoes",
        "observaões": "observacoes",
        "observaoes": "observacoes"
    }

    records = []
    for _, row in df.iterrows():
        rec = {"cliente_id": cliente_id}
        
        for col_name in df.columns:
            db_field = col_mapping.get(col_name)
            if db_field:
                val = row[col_name]
                if db_field == "data":
                    rec[db_field] = format_date(val)
                else:
                    rec[db_field] = str(val).strip() if not pd.isna(val) else None
        
        if rec.get("nome") and rec.get("data"):
            records.append(rec)

    print(f"[PROCESSADOR] {len(records)} primeiras consultas extraídas.")
    return records
