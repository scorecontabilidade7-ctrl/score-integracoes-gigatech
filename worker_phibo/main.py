import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Garante suporte UTF-8 no terminal Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Garante importação dos módulos locais do worker_phibo
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(CURRENT_DIR.parent))

from worker_phibo.database import get_active_clients, supabase
from worker_phibo.processor import process_vendas_csv
from worker_phibo.scraper import PhiboScraper, PhiboWindowRestrictionError


def parse_arguments():
    parser = argparse.ArgumentParser(description="Orquestrador do Robô PHIBO (Vendas & Estoque)")
    parser.add_argument("--client-id", type=str, help="UUID do cliente específico a processar")
    parser.add_argument("--month", type=int, help="Mês específico para extração (ex: 10)")
    parser.add_argument("--year", type=int, help="Ano específico para extração (ex: 2026)")
    parser.add_argument("--headed", action="store_true", help="Abre o navegador visível (Playwright)")
    parser.add_argument("--test-offline", action="store_true", help="Executa o teste com o CSV de amostra sem abrir o navegador")
    return parser.parse_args()


def run_pipeline():
    args = parse_arguments()
    agora = datetime.now()

    env_cid = os.environ.get("PHIBO_CLIENTE_ID")
    env_month = os.environ.get("PHIBO_MES")
    env_year = os.environ.get("PHIBO_ANO")

    target_client_id = args.client_id or (env_cid if env_cid and env_cid.strip() and env_cid != "TODOS" else None)
    ano = args.year or (int(env_year) if env_year and env_year.isdigit() else agora.year)
    mes = args.month or (int(env_month) if env_month and env_month.isdigit() else agora.month)

    print("=" * 60)
    print("[INICIO] INICIANDO WORKER PHIBO")
    print(f"[DATA] Periodo Alvo: {mes:02d}/{ano}")
    print(f"[MODO] {'TESTE OFFLINE' if args.test_offline else 'ONLINE (PLAYWRIGHT)'}")
    print("=" * 60)

    # 1. Obter clientes
    if args.test_offline:
        clientes = get_active_clients(target_client_id)
        if not clientes:
            print("[TESTE] Nenhum cliente encontrado no Supabase. Criando loja de teste temporária...")
            res = supabase.table("phibo_clientes_config").insert({
                "nome_loja": "Loja PHIBO Teste",
                "email_login_phibo": "teste@phibo.com.br",
                "senha_login_phibo": "teste123",
                "ativo": True
            }).execute()
            cliente_id = res.data[0]["id"]
            print(f"[TESTE] Loja de teste criada com ID: {cliente_id}")
        else:
            cliente_id = clientes[0]["id"]
            print(f"[TESTE] Usando cliente existente: {clientes[0]['nome_loja']} ({cliente_id})")

        sample_file = CURRENT_DIR / "tmp_downloads" / "sample_vendas.csv"
        if not sample_file.exists():
            print(f"[ERRO] Arquivo de amostra não encontrado em: {sample_file}")
            sys.exit(1)

        print(f"[TESTE] Processando arquivo de amostra offline: {sample_file}")
        total = process_vendas_csv(str(sample_file), cliente_id, ano=ano, mes=mes)
        print("=" * 60)
        print(f"[SUCESSO] TESTE OFFLINE FINALIZADO! ({total} registros gravados)")
        print("=" * 60)
        return

    # 2. Execução Online (Playwright)
    clientes = get_active_clients(target_client_id)
    if not clientes:
        print("[AVISO] Nenhum cliente ativo encontrado na tabela phibo_clientes_config.")
        return

    print(f"[INFO] {len(clientes)} cliente(s) ativo(s) encontrado(s).")
    scraper = PhiboScraper(headless=not args.headed)

    for cliente in clientes:
        cid = cliente["id"]
        nome = cliente["nome_loja"]
        email = cliente.get("email_login_phibo")
        senha = cliente.get("senha_login_phibo")

        print("-" * 50)
        print(f"[LOJA] Processando Loja: {nome} (ID: {cid})")

        if not email or not senha:
            print(f"[ERRO] Credenciais ausentes para a loja {nome}. Pulando...")
            continue

        try:
            # Download via Playwright
            csv_path = scraper.run_download_vendas(email, senha, ano=ano, mes=mes)

            # Processamento e Gravação no Supabase
            total = process_vendas_csv(csv_path, cid, ano=ano, mes=mes)
            print(f"[SUCESSO] Loja {nome} processada: {total} vendas gravadas.")

        except PhiboWindowRestrictionError as we:
            print(f"[AVISO HORARIO] {we}")
        except Exception as e:
            print(f"[ERRO] Falha ao processar loja {nome}: {e}")

    print("=" * 60)
    print("[FIM] WORKER PHIBO FINALIZADO.")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
