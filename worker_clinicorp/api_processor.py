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
        
    if len(val_date) == 8 and val_date.isdigit():
        return f"{val_date[:4]}-{val_date[4:6]}-{val_date[6:8]}"

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


def process_agendamentos_geral_json(json_data: list, cliente_id: str, data_inicial: str = None, data_final: str = None) -> list:
    """
    Processa a lista de agendamentos gerais vinda da API.
    """
    print("[API PROCESSADOR] Processando JSON de agendamentos gerais...")
    records = []

    dt_ini = _format_iso_date(data_inicial) if data_inicial else None
    dt_fim = _format_iso_date(data_final) if data_final else None
    hoje = datetime.today()
    mes_prefix = dt_ini[:7] if dt_ini else f"{hoje.year}-{hoje.month:02d}"

    for item in json_data:
        rec = {"cliente_id": cliente_id}

        raw_date = item.get("date") or item.get("Date") or item.get("AtomicDate") or item.get("CreateDate") or item.get("appointment_date")
        rec["data"] = _format_iso_date(raw_date)
        rec["id_agendamento"] = str(item.get("id") or item.get("AppointmentId") or "").strip() or None
        rec["paciente"] = (item.get("PatientName") or item.get("patient_name") or item.get("Name") or item.get("name") or "").strip() or None
        rec["contato"] = str(item.get("MobilePhone") or item.get("phone") or item.get("Email") or item.get("contact") or "").strip() or None
        rec["horario"] = str(item.get("fromTime") or item.get("time") or item.get("ScheduleTime") or item.get("hour") or "").strip() or None
        rec["profissional"] = (item.get("UserName") or item.get("DentistName") or item.get("professional_name") or item.get("dentist") or "").strip() or None
        rec["status"] = str(item.get("StatusDescription") or item.get("status") or item.get("Status") or "").strip() or None
        rec["categoria"] = str(item.get("CategoryDescription") or item.get("category") or "").strip() or None
        rec["plano"] = str(item.get("HealthPlan") or item.get("plan") or "Particular").strip() or "Particular"

        if rec.get("data") and (rec.get("paciente") or rec.get("status") or rec.get("horario")):
            if dt_ini and dt_fim:
                if dt_ini <= rec["data"] <= dt_fim:
                    records.append(rec)
            elif dt_ini:
                if rec["data"].startswith(mes_prefix):
                    records.append(rec)
            else:
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} agendamentos gerais extraídos.")
    return records


def _parse_float(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        val_str = str(val).strip().replace("R$", "").replace(" ", "")
        if "," in val_str and "." in val_str:
            val_str = val_str.replace(".", "").replace(",", ".")
        elif "," in val_str:
            val_str = val_str.replace(",", ".")
        return float(val_str)
    except Exception:
        return 0.0


def process_procedimentos_executados_json(json_data: list, cliente_id: str, data_inicial: str = None, data_final: str = None) -> list:
    """
    Processa a lista de procedimentos executados vinda da API.
    """
    print("[API PROCESSADOR] Processando JSON de procedimentos executados...")
    records = []

    dt_ini = _format_iso_date(data_inicial) if data_inicial else None
    dt_fim = _format_iso_date(data_final) if data_final else None
    hoje = datetime.today()
    mes_prefix = dt_ini[:7] if dt_ini else f"{hoje.year}-{hoje.month:02d}"

    for item in json_data:
        rec = {"cliente_id": cliente_id}

        raw_date = item.get("ExecutedDate") or item.get("Date") or item.get("date") or item.get("CreateDate")
        rec["data_execucao"] = _format_iso_date(raw_date)
        rec["id_procedimento"] = str(item.get("id") or item.get("TreatmentId") or "").strip() or None
        rec["paciente"] = (item.get("PatientName") or item.get("patient_name") or item.get("Name") or "").strip() or None
        
        tel = item.get("MobilePhone") or item.get("phone") or item.get("Telephone") or item.get("contact")
        rec["telefone"] = str(tel).strip() if tel else None
        
        rec["profissional"] = (item.get("DentistName") or item.get("dentist_name") or item.get("UserName") or "").strip() or None
        rec["procedimento"] = (item.get("CharactDescription") or item.get("OperationDescription") or item.get("procedure_name") or item.get("ProcedureDescription") or "").strip() or None
        
        reg = item.get("Region") or item.get("Tooth") or item.get("Surface")
        rec["regiao"] = str(reg).strip() if reg else None

        raw_val = item.get("FinalAmount") if item.get("FinalAmount") is not None else (item.get("Amount") or item.get("Value") or item.get("Price") or item.get("valor") or 0)
        rec["valor"] = _parse_float(raw_val)

        if rec.get("data_execucao") and (rec.get("paciente") or rec.get("profissional") or rec.get("procedimento")):
            if dt_ini and dt_fim:
                if dt_ini <= rec["data_execucao"] <= dt_fim:
                    records.append(rec)
            elif dt_ini:
                if rec["data_execucao"].startswith(mes_prefix):
                    records.append(rec)
            else:
                records.append(rec)

    print(f"[API PROCESSADOR] {len(records)} procedimentos executados extraídos.")
    return records




