from datetime import datetime

def _format_iso_date(date_str):
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if not date_str:
        return None
    val_date = date_str.split(" ")[0]
    if "T" in val_date:
        val_date = val_date.split("T")[0]
        
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val_date, fmt).date().isoformat()
        except ValueError:
            pass
    return val_date

def get_first_day_of_month(date_str):
    try:
        if "/" in date_str:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(day=1).date().isoformat()
    except Exception:
        return _format_iso_date(date_str)


def process_faturamento_json(json_data: dict, cliente_id: str, data_inicial: str) -> list:
    """
    Processa a resposta JSON do faturamento.
    O endpoint retorna um 'revenueList' que já agrega por profissional.
    """
    print("[API PROCESSADOR] Processando JSON de faturamento...")
    records = []
    revenue_list = json_data.get("revenueList", {})
    
    dt_faturamento = get_first_day_of_month(data_inicial)

    for prof, data in revenue_list.items():
        if not prof or str(prof).strip().upper() in ("VALOR TOTAL", "TOTAL", ""):
            continue
            
        valor = data.get("TotalRevenue")
        if not valor or float(valor) == 0:
            continue
            
        records.append({
            "cliente_id": cliente_id,
            "profissional": str(prof).strip(),
            "valor_faturamento": float(valor),
            "data": dt_faturamento
        })

    print(f"[API PROCESSADOR] {len(records)} registros de faturamento extraídos.")
    return records


def process_orcamentos_json(json_data: list, cliente_id: str) -> list:
    """
    Processa a lista de orçamentos vinda da API.
    Filtra apenas pelo mês atual.
    """
    print("[API PROCESSADOR] Processando JSON de orçamentos...")
    records = []
    
    hoje = datetime.today()
    mes_atual_prefix = f"{hoje.year}-{hoje.month:02d}"

    for item in json_data:
        rec = {"cliente_id": cliente_id}
        
        rec["data_criacao"] = _format_iso_date(item.get("CreateDate"))
        rec["data"] = _format_iso_date(item.get("Date")) or rec["data_criacao"]
        rec["status"] = str(item.get("Status")).strip() if item.get("Status") else None
        rec["motivo"] = None # API base não aparenta trazer 'motivo' de perda direto na raiz com clareza
        rec["profissional"] = item.get("DentistName")
        rec["paciente"] = item.get("PatientName")
        
        # Telefone
        tel = item.get("MobilePhone")
        rec["telefone"] = str(tel).strip() if tel else None
        
        # Procedimentos
        procedimentos_str = ""
        procs = item.get("ProcedureList", [])
        if procs:
            nomes = [p.get("OperationDescription", "") for p in procs if p.get("OperationDescription")]
            procedimentos_str = ", ".join(nomes)
        rec["procedimentos"] = procedimentos_str if procedimentos_str else None

        # Valores
        rec["valor"] = float(item.get("Amount", 0) or 0)
        rec["valor_total_com_desconto"] = float(item.get("FinalAmount", 0) or 0)
        rec["valor_total"] = rec["valor_total_com_desconto"]
        
        # Outros
        rec["observacoes"] = str(item.get("Notes")) if item.get("Notes") else None
        rec["como_conheceu"] = str(item.get("HowDidMeet")) if item.get("HowDidMeet") else None

        # Validar inserção (tem pac/prof e é do mês atual)
        if rec.get("paciente") or rec.get("profissional"):
            if rec.get("data") and str(rec["data"]).startswith(mes_atual_prefix):
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} orçamentos extraídos (mês atual: {mes_atual_prefix}).")
    return records


def process_primeiras_consultas_json(json_data: list, cliente_id: str, data_inicial: str) -> list:
    """
    Processa a lista de primeiras consultas vinda da API.
    """
    print("[API PROCESSADOR] Processando JSON de primeiras consultas...")
    records = []
    
    dt_cadastro = _format_iso_date(data_inicial)
    hoje = datetime.today()
    mes_atual_prefix = f"{hoje.year}-{hoje.month:02d}"
    
    for item in json_data:
        rec = {
            "cliente_id": cliente_id,
            "data_cadastro": dt_cadastro
        }
        
        rec["data"] = _format_iso_date(item.get("date") or item.get("CreateDate"))
        rec["status"] = str(item.get("StatusDescription")).strip() if item.get("StatusDescription") else None
        rec["nome"] = item.get("PatientName")
        rec["como_conheceu"] = str(item.get("HowDidMeet")).strip() if item.get("HowDidMeet") else None
        rec["observacoes"] = str(item.get("Notes")).strip() if item.get("Notes") else None
        
        if rec.get("nome") and rec.get("data"):
            if str(rec["data"]).startswith(mes_atual_prefix):
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} primeiras consultas extraídas (mês atual: {mes_atual_prefix}).")
    return records
