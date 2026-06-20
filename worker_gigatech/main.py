import os
import sys
import shutil
from datetime import datetime, timedelta
from dotenv import load_dotenv

from database import get_active_clients
from scraper import extrair_dados, TMP_DIR
from processor import (
    process_vendas_excel,
    process_vendedores_pdf,
    process_clientes_novos,
    process_estoque_excel
)

load_dotenv()

def limpar_tmp():
    """Apaga os arquivos temporários da pasta de downloads."""
    print("[SISTEMA] Limpando pasta temporária...")
    for filename in os.listdir(TMP_DIR):
        file_path = os.path.join(TMP_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"[ERRO] Falha ao deletar {file_path}: {e}")

def main():
    print("="*60)
    print(" INICIANDO ORQUESTRADOR GIGA TECH V2 (MULTI-TENANT)")
    print("="*60)
    
    # Parâmetros do Kestra via env vars (ou default)
    cliente_id = os.getenv("KESTRA_CLIENTE_ID")
    if cliente_id and cliente_id.strip().upper() == "TODOS":
        cliente_id = None

    # Se não vier data, significa que rodou pelo Cron (Agendador diário). Pegamos D-1 (ontem).
    ontem = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    
    data_inicial = os.getenv("KESTRA_DATA_INICIAL") or ontem
    data_final = os.getenv("KESTRA_DATA_FINAL") or ontem
    
    print(f"[PARAMS] Cliente ID: {cliente_id or 'TODOS'}")
    print(f"[PARAMS] Período: {data_inicial} até {data_final}\n")

    # 2. BUSCAR CLIENTES
    clientes = get_active_clients(cliente_id)
    if not clientes:
        print("[AVISO] Nenhum cliente ativo encontrado para processar.")
        sys.exit(0)
        
    print(f"[BD] {len(clientes)} cliente(s) ativo(s) encontrado(s).")
    
    # 3. LOOP DE CLIENTES
    for cliente in clientes:
        nome_loja = cliente.get("nome_loja", "Desconhecida")
        cid = str(cliente["id"])
        
        print("\n" + "-"*50)
        print(f"[CLIENTE] Iniciando processamento: {nome_loja} ({cid})")
        print("-"*50)
        
        # Limpar antes de iniciar o cliente
        limpar_tmp()
        
        # Extrair dados (Playwright)
        arquivos = extrair_dados(cliente, data_inicial, data_final)
        
        if not arquivos:
            print(f"[ERRO] Falha ao extrair dados do cliente {nome_loja}. Pulando para o próximo.")
            continue
            
        # 3) Limpar dados existentes do período para não duplicar (Idempotência)
        from database import clean_period_data
        try:
            clean_period_data(cid, data_inicial, data_final)
        except Exception as e:
            print(f"[ERRO] Falha ao limpar dados antigos do cliente {nome_loja}: {e}")
            continue

        # 4) Processar Arquivos e Inserir no Banco
        vendas = arquivos.get("vendas_excel")
        if vendas: process_vendas_excel(vendas, cid)
        
        vendedores = arquivos.get("vendedores_pdf")
        if vendedores: process_vendedores_pdf(vendedores, cid)
        
        clientes_pdf = arquivos.get("clientes_pdf")
        if clientes_pdf: process_clientes_novos(clientes_pdf, cid)
        
        estoque = arquivos.get("estoque_excel")
        if estoque: process_estoque_excel(estoque, cid)
        
        print(f"[CLIENTE] Processamento concluído para: {nome_loja}")

    # Limpeza final
    limpar_tmp()
    print("\n" + "="*60)
    print(" ORQUESTRADOR FINALIZADO COM SUCESSO!")
    print("="*60)

if __name__ == "__main__":
    main()
