import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variáveis do Supabase ausentes no .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_active_clients(cliente_id=None):
    """
    Retorna os clientes ativos da tabela de configuração do Clinicorp.
    Se cliente_id for fornecido, busca apenas ele.
    """
    query = supabase.table("clinicorp_clientes_config").select("*").eq("ativo", True)
    if cliente_id:
        query = query.eq("id", cliente_id)
        
    res = query.execute()
    return res.data


def batch_insert(table_name: str, data: list, batch_size: int = 500):
    """
    Insere dados em lote na tabela do Supabase.
    """
    if not data:
        print(f"[BD] Nenhuma linha para inserir na tabela {table_name}.")
        return

    total = len(data)
    print(f"[BD] Inserindo {total} registros na tabela {table_name} (lotes de {batch_size})...")
    
    for i in range(0, total, batch_size):
        lote = data[i:i + batch_size]
        try:
            supabase.table(table_name).insert(lote).execute()
            print(f"[BD] {table_name}: Inseridos {i + len(lote)}/{total}")
        except Exception as e:
            print(f"[ERRO] Falha ao inserir lote em {table_name}: {e}")
            raise e


def clean_period_data(cliente_id: str, data_inicial: str, data_final: str):
    """
    Remove dados do período e do cliente especificado para evitar duplicatas.
    Para faturamento, remove do primeiro dia do mês de início do período.
    Formato esperado: dd/mm/yyyy ou yyyy-mm-dd
    """
    try:
        dt_ini = datetime.strptime(data_inicial, "%d/%m/%Y").date().isoformat()
        dt_fim = datetime.strptime(data_final, "%d/%m/%Y").date().isoformat()
        dt_faturamento = datetime.strptime(data_inicial, "%d/%m/%Y").replace(day=1).date().isoformat()
    except Exception:
        try:
            dt_ini = datetime.strptime(data_inicial, "%Y-%m-%d").date().isoformat()
            dt_fim = datetime.strptime(data_final, "%Y-%m-%d").date().isoformat()
            dt_faturamento = datetime.strptime(data_inicial, "%Y-%m-%d").replace(day=1).date().isoformat()
        except Exception:
            dt_ini = data_inicial
            dt_fim = data_final
            dt_faturamento = data_inicial

    print(f"[BD] Limpando dados retroativos (orçamentos, consultas e faturamento) para o período {dt_ini} a {dt_fim} via RPC...")
    
    try:
        supabase.rpc("delete_clinicorp_data", {
            "p_cliente_id": cliente_id,
            "p_dt_ini": dt_ini,
            "p_dt_fim": dt_fim,
            "p_dt_faturamento": dt_faturamento
        }).execute()
        print("[BD] Limpeza de dados antigos concluída com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao executar a RPC delete_clinicorp_data: {e}")
        raise e
