import os
import sys
import shutil
from datetime import datetime
from dotenv import load_dotenv

from database import get_active_clients, batch_insert
from scraper import extrair_dados, TMP_DIR
from processor import (
    process_faturamento_excel,
    process_orcamentos_excel,
    process_primeira_consulta_excel
)

load_dotenv()

def limpar_tmp():
    """Apaga os arquivos temporários da pasta de downloads."""
    print("[SISTEMA] Limpando pasta temporária...")
    if TMP_DIR.exists():
        for filename in os.listdir(TMP_DIR):
            file_path = os.path.join(TMP_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"[ERRO] Falha ao deletar {file_path}: {e}")

def main():
    print("="*60)
    print(" INICIANDO ORQUESTRADOR CLINICORP (MULTI-TENANT)")
    print("="*60)
    
    # Parâmetros do Kestra via env vars (ou default)
    cliente_id = os.getenv("KESTRA_CLIENTE_ID")
    if cliente_id and cliente_id.strip().upper() == "TODOS":
        cliente_id = None

    # Se não vier data, pegamos D-0 (hoje).
    hoje = datetime.now().strftime("%d/%m/%Y")
    
    data_inicial = os.getenv("KESTRA_DATA_INICIAL") or hoje
    data_final = os.getenv("KESTRA_DATA_FINAL") or hoje
    
    print(f"[PARAMS] Cliente ID: {cliente_id or 'TODOS'}")
    print(f"[PARAMS] Período: {data_inicial} até {data_final}\n")

    # 1. BUSCAR CLIENTES
    clientes = get_active_clients(cliente_id)
    if not clientes:
        print("[AVISO] Nenhum cliente ativo encontrado para processar no Clinicorp.")
        sys.exit(0)
        
    print(f"[BD] {len(clientes)} cliente(s) ativo(s) encontrado(s) no Clinicorp.")
    
    # 2. LOOP DE CLIENTES
    for cliente in clientes:
        nome_loja = cliente.get("nome_loja", "Desconhecida")
        cid = str(cliente["id"])
        
        print("\n" + "-"*50)
        print(f"[CLIENTE] Iniciando processamento: {nome_loja} ({cid})")
        print("-"*50)
        
        # Limpar antes de iniciar o cliente
        limpar_tmp()
        
        # Extrair dados (Playwright)
        try:
            arquivos = extrair_dados(cliente, data_inicial, data_final)
        except Exception as e:
            print(f"[ERRO] Erro crítico no Playwright para o cliente {nome_loja}: {e}. Pulando para o próximo.")
            continue
            
        if not arquivos:
            print(f"[ERRO] Falha ao extrair dados do cliente {nome_loja}. Pulando para o próximo.")
            continue
            
        # 3) Limpar e Processar Arquivos Individualmente (Idempotência sob demanda)
        from database import (
            clean_faturamento,
            clean_orcamentos,
            clean_primeiras_consultas
        )

        faturamento_file = arquivos.get("faturamento_excel")
        if faturamento_file:
            try:
                clean_faturamento(cid, data_inicial)
                faturamento_records = process_faturamento_excel(faturamento_file, cid, data_inicial)
                if faturamento_records:
                    batch_insert("clinicorp_faturamento_profissional", faturamento_records)
            except Exception as e:
                print(f"[ERRO] Falha ao limpar/processar faturamento do cliente {nome_loja}: {e}")
        
        import calendar
        hoje = datetime.today()
        ultimo_dia = calendar.monthrange(hoje.year, hoje.month)[1]
        data_ini_mes = f"01/{hoje.month:02d}/{hoje.year}"
        data_fim_mes = f"{ultimo_dia:02d}/{hoje.month:02d}/{hoje.year}"

        orcamentos_file = arquivos.get("orcamentos_excel")
        if orcamentos_file:
            try:
                clean_orcamentos(cid, data_ini_mes, data_fim_mes)
                orcamentos_records = process_orcamentos_excel(orcamentos_file, cid)
                if orcamentos_records:
                    batch_insert("clinicorp_orcamentos", orcamentos_records)
            except Exception as e:
                print(f"[ERRO] Falha ao limpar/processar orçamentos do cliente {nome_loja}: {e}")
        
        consultas_file = arquivos.get("primeira_consulta_excel")
        if consultas_file:
            try:
                clean_primeiras_consultas(cid, data_ini_mes, data_fim_mes)
                consultas_records = process_primeira_consulta_excel(consultas_file, cid, data_inicial)
                if consultas_records:
                    batch_insert("clinicorp_primeiras_consultas", consultas_records)
            except Exception as e:
                print(f"[ERRO] Falha ao limpar/processar primeiras consultas do cliente {nome_loja}: {e}")
        
        print(f"[CLIENTE] Processamento concluído para: {nome_loja}")

    # Limpeza final
    limpar_tmp()
    print("\n" + "="*60)
    print(" ORQUESTRADOR CLINICORP FINALIZADO COM SUCESSO!")
    print("="*60)

if __name__ == "__main__":
    main()
