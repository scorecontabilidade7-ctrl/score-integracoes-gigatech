import os
import sys
import calendar
from datetime import datetime
from dotenv import load_dotenv

from database import (
    get_active_clients, 
    batch_insert,
    clean_faturamento,
    clean_orcamentos,
    clean_primeiras_consultas,
    remove_duplicados_orcamentos,
    remove_duplicados_primeiras_consultas
)
from api_scraper import (
    get_auth_token, 
    fetch_faturamento, 
    fetch_orcamentos, 
    fetch_primeiras_consultas
)
from api_processor import (
    process_faturamento_json, 
    process_orcamentos_json, 
    process_primeiras_consultas_json
)

load_dotenv()

def main():
    print("="*60)
    print(" INICIANDO ORQUESTRADOR CLINICORP (VIA API)")
    print("="*60)
    
    cliente_id = os.getenv("KESTRA_CLIENTE_ID")
    if cliente_id and cliente_id.strip().upper() == "TODOS":
        cliente_id = None

    hoje_dt = datetime.now()
    ultimo_dia = calendar.monthrange(hoje_dt.year, hoje_dt.month)[1]
    
    data_ini_mes_atual = f"01/{hoje_dt.month:02d}/{hoje_dt.year}"
    data_fim_mes_atual = f"{ultimo_dia:02d}/{hoje_dt.month:02d}/{hoje_dt.year}"

    data_inicial = os.getenv("KESTRA_DATA_INICIAL")
    data_final = os.getenv("KESTRA_DATA_FINAL")

    if not data_inicial:
        data_inicial = data_ini_mes_atual
    if not data_final:
        data_final = data_fim_mes_atual
    
    print(f"[PARAMS] Cliente ID: {cliente_id or 'TODOS'}")
    print(f"[PARAMS] Período: {data_inicial} até {data_final}\n")

    clientes = get_active_clients(cliente_id)
    if not clientes:
        print("[AVISO] Nenhum cliente ativo encontrado.")
        sys.exit(0)
        
    print(f"[BD] {len(clientes)} cliente(s) ativo(s).")
    
    for cliente in clientes:
        nome_loja = cliente.get("nome_loja", "Desconhecida")
        cid = str(cliente["id"])
        
        print("\n" + "-"*50)
        print(f"[CLIENTE] Iniciando processamento API: {nome_loja} ({cid})")
        print("-"*50)
        
        try:
            token = get_auth_token(cliente)
            if not token:
                print(f"[ERRO] Não foi possível obter token para {nome_loja}. Pulando...")
                continue
        except Exception as e:
            print(f"[ERRO] Falha no login do cliente {nome_loja}: {e}. Pulando...")
            continue
            
        # 1. Faturamento
        try:
            print("\n--- Processando Faturamento ---")
            json_fat = fetch_faturamento(token, data_inicial, data_final)
            if json_fat:
                clean_faturamento(cid, data_inicial)
                records_fat = process_faturamento_json(json_fat, cid, data_inicial)
                if records_fat:
                    batch_insert("clinicorp_faturamento_profissional", records_fat)
        except Exception as e:
            print(f"[ERRO] Falha ao processar faturamento de {nome_loja}: {e}")

        # 2. Orçamentos
        try:
            print("\n--- Processando Orçamentos ---")
            json_orc = fetch_orcamentos(token, data_inicial, data_final, clinic_id=0)
            if json_orc:
                clean_orcamentos(cid, data_inicial, data_final)
                records_orc = process_orcamentos_json(json_orc, cid)
                if records_orc:
                    batch_insert("clinicorp_orcamentos", records_orc)
                    remove_duplicados_orcamentos()
        except Exception as e:
            print(f"[ERRO] Falha ao processar orçamentos de {nome_loja}: {e}")

        # 3. Primeiras Consultas
        try:
            print("\n--- Processando Primeiras Consultas ---")
            json_cons = fetch_primeiras_consultas(token, data_inicial, data_final)
            if json_cons:
                clean_primeiras_consultas(cid, data_inicial, data_final)
                records_cons = process_primeiras_consultas_json(json_cons, cid, data_inicial)
                if records_cons:
                    batch_insert("clinicorp_primeiras_consultas", records_cons)
                    remove_duplicados_primeiras_consultas()
        except Exception as e:
            print(f"[ERRO] Falha ao processar primeiras consultas de {nome_loja}: {e}")
            
        print(f"[CLIENTE] Concluído para: {nome_loja}")

    print("\n" + "="*60)
    print(" ORQUESTRADOR CLINICORP (API) FINALIZADO COM SUCESSO!")
    print("="*60)

if __name__ == "__main__":
    main()
