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


def process_orcamentos_json(json_data: list, cliente_id: str, data_inicial: str = None) -> list:
    """
    Processa a lista de orçamentos vinda da API.
    Filtra pelo mês do período especificado (ou mês atual se não informado).
    """
    print("[API PROCESSADOR] Processando JSON de orçamentos...")
    records = []
    
    dt_ref = _format_iso_date(data_inicial) if data_inicial else None
    hoje = datetime.today()
    mes_prefix = dt_ref[:7] if dt_ref else f"{hoje.year}-{hoje.month:02d}"

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

        # Validar inserção (tem pac/prof e pertence ao mês do período)
        if rec.get("paciente") or rec.get("profissional"):
            if rec.get("data") and str(rec["data"]).startswith(mes_prefix):
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} orçamentos extraídos (mês referência: {mes_prefix}).")
    return records


def process_primeiras_consultas_json(json_data: list, cliente_id: str, data_inicial: str) -> list:
    """
    Processa a lista de primeiras consultas vinda da API.
    Filtra pelo mês do período especificado (ou mês atual se não informado).
    """
    print("[API PROCESSADOR] Processando JSON de primeiras consultas...")
    records = []
    
    dt_cadastro = _format_iso_date(data_inicial)
    hoje = datetime.today()
    mes_prefix = dt_cadastro[:7] if dt_cadastro else f"{hoje.year}-{hoje.month:02d}"
    
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
            if str(rec["data"]).startswith(mes_prefix):
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} primeiras consultas extraídas (mês referência: {mes_prefix}).")
    return records


def process_agendamentos_geral_json(json_data: list, cliente_id: str, data_inicial: str = None) -> list:
    """
    Processa a lista de agendamentos gerais vinda da API.
    """
    print("[API PROCESSADOR] Processando JSON de agendamentos gerais...")
    records = []

    dt_ref = _format_iso_date(data_inicial) if data_inicial else None
    hoje = datetime.today()
    mes_prefix = dt_ref[:7] if dt_ref else f"{hoje.year}-{hoje.month:02d}"

    for item in json_data:
        rec = {"cliente_id": cliente_id}

        rec["data"] = _format_iso_date(item.get("date") or item.get("Date") or item.get("CreateDate") or item.get("appointment_date"))
        rec["paciente"] = item.get("PatientName") or item.get("patient_name") or item.get("name")
        rec["contato"] = str(item.get("MobilePhone") or item.get("phone") or item.get("contact") or "").strip() or None
        rec["horario"] = str(item.get("time") or item.get("ScheduleTime") or item.get("hour") or "").strip() or None
        rec["agendado_por"] = item.get("CreatedByName") or item.get("scheduled_by")
        rec["profissional"] = item.get("DentistName") or item.get("professional_name") or item.get("dentist")
        rec["status"] = str(item.get("StatusDescription") or item.get("status") or item.get("Status") or "").strip() or None
        rec["categoria"] = str(item.get("CategoryDescription") or item.get("category") or "").strip() or None
        rec["plano"] = str(item.get("HealthPlan") or item.get("plan") or "Particular").strip() or None

        # Identificar tipo_registro (Compromisso vs Agendamento)
        status_val = rec.get("status") or ""
        cat_val = rec.get("categoria") or ""
        if "COMPROMISSO" in status_val.upper() or "COMPROMISSO" in cat_val.upper():
            rec["tipo_registro"] = "Compromisso"
        else:
            rec["tipo_registro"] = "Agendamento"

        if rec.get("data") and (rec.get("paciente") or rec.get("status")):
            if rec["data"].startswith(mes_prefix):
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} agendamentos gerais extraídos (mês referência: {mes_prefix}).")
    return records


