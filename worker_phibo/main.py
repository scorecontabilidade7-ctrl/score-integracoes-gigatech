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
    parser.add_argument("--data-inicio", "--data-inicial", type=str, dest="data_inicio", help="Data início (DD/MM/AAAA ou AAAA-MM-DD)")
    parser.add_argument("--data-fim", "--data-final", type=str, dest="data_fim", help="Data fim (DD/MM/AAAA ou AAAA-MM-DD)")
    parser.add_argument("--headed", action="store_true", help="Abre o navegador visível (Playwright)")
    parser.add_argument("--test-offline", action="store_true", help="Executa o teste com o CSV de amostra sem abrir o navegador")
    return parser.parse_args()


def run_pipeline():
    args = parse_arguments()
    agora = datetime.now()

    env_cid = os.environ.get("PHIBO_CLIENTE_ID")
    env_month = os.environ.get("PHIBO_MES")
    env_year = os.environ.get("PHIBO_ANO")
    env_dt_ini = os.environ.get("PHIBO_DATA_INICIAL") or os.environ.get("KESTRA_DATA_INICIAL")
    env_dt_fim = os.environ.get("PHIBO_DATA_FINAL") or os.environ.get("KESTRA_DATA_FINAL")

    data_inicio = args.data_inicio or (env_dt_ini.strip() if env_dt_ini and env_dt_ini.strip() else None)
    data_fim = args.data_fim or (env_dt_fim.strip() if env_dt_fim and env_dt_fim.strip() else None)

    if data_inicio and (not env_month or not str(env_month).strip()):
        clean_dt = str(data_inicio).strip()
        if "/" in clean_dt:
            partes = clean_dt.split("/")
            if len(partes) == 3:
                env_month = partes[1]
                env_year = partes[2]
            elif len(partes) == 2:
                env_month = partes[1]
                env_year = str(agora.year)
        elif "-" in clean_dt:
            partes = clean_dt.split("-")
            if len(partes) == 3:
                env_year = partes[0]
                env_month = partes[1]
            elif len(partes) == 2:
                env_month = partes[0]
                env_year = str(agora.year)

    target_client_id = args.client_id or (env_cid if env_cid and env_cid.strip() and env_cid != "TODOS" else None)
    ano = args.year or (int(env_year) if env_year and str(env_year).isdigit() else agora.year)
    mes = args.month or (int(env_month) if env_month and str(env_month).isdigit() else agora.month)

    periodo_display = f"{data_inicio} até {data_fim}" if (data_inicio and data_fim) else f"{mes:02d}/{ano}"

    print("=" * 60)
    print("[INICIO] INICIANDO WORKER PHIBO")
    print(f"[DATA] Periodo Alvo: {periodo_display}")
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
        total = process_vendas_csv(str(sample_file), cliente_id, ano=ano, mes=mes, data_inicio=data_inicio, data_fim=data_fim)
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

    lojas_sucesso = []
    lojas_falha = []

    for cliente in clientes:
        cid = cliente["id"]
        nome = cliente["nome_loja"]
        email = cliente.get("email_login_phibo")
        senha = cliente.get("senha_login_phibo")

        print("-" * 50)
        print(f"[LOJA] Processando Loja: {nome} (ID: {cid})")

        if not email or not senha:
            erro_msg = f"Credenciais ausentes para a loja {nome}."
            print(f"[ERRO] {erro_msg} Pulando...")
            lojas_falha.append({"loja": nome, "motivo": erro_msg})
            continue

        try:
            # Download via Playwright
            csv_path = scraper.run_download_vendas(
                email, senha, ano=ano, mes=mes, data_inicio=data_inicio, data_fim=data_fim
            )

            # Processamento e Gravação no Supabase
            total = process_vendas_csv(
                csv_path, cid, ano=ano, mes=mes, data_inicio=data_inicio, data_fim=data_fim
            )
            print(f"[SUCESSO] Loja {nome} processada: {total} vendas gravadas.")
            lojas_sucesso.append({"loja": nome, "total_vendas": total})

        except PhiboWindowRestrictionError as we:
            print(f"[AVISO HORARIO] {we}")
            lojas_falha.append({"loja": nome, "motivo": str(we)})
        except Exception as e:
            print(f"[ERRO] Falha ao processar loja {nome}: {e}")
            lojas_falha.append({"loja": nome, "motivo": str(e)})

    print("=" * 60)
    print(f"[RESUMO] WORKER PHIBO FINALIZADO.")
    print(f"• Lojas com Sucesso: {len(lojas_sucesso)} -> {[l['loja'] for l in lojas_sucesso]}")
    print(f"• Lojas com Falha:   {len(lojas_falha)} -> {[l['loja'] for l in lojas_falha]}")
    print("=" * 60)

    if lojas_falha:
        print(f"[ERRO GERAL] Houve falha no processamento de {len(lojas_falha)} loja(s).")
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
