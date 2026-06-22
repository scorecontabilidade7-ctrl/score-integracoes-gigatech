import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variáveis do Supabase ausentes no .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_active_clients(cliente_id=None):
    """
    Retorna os clientes ativos da tabela de configuração.
    Se cliente_id for fornecido, busca apenas ele.
    """
    query = supabase.table("gigatech_clientes_config").select("*").eq("ativo", True)
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

def parse_dates(data_inicial: str, data_final: str):
    from datetime import datetime
    try:
        dt_ini = datetime.strptime(data_inicial, "%d/%m/%Y").date().isoformat()
        dt_fim = datetime.strptime(data_final, "%d/%m/%Y").date().isoformat()
    except:
        dt_ini = data_inicial
        dt_fim = data_final
    return dt_ini, dt_fim

def clean_vendas(cliente_id: str, data_inicial: str, data_final: str):
    dt_ini, dt_fim = parse_dates(data_inicial, data_final)
    print(f"[BD] Limpando vendas antigas de {dt_ini} a {dt_fim}...")
    supabase.table("gigatech_vendas").delete().eq("cliente_id", cliente_id).gte("data_venda", dt_ini).lte("data_venda", dt_fim).execute()

def clean_vendedores(cliente_id: str, data_inicial: str, data_final: str):
    dt_ini, dt_fim = parse_dates(data_inicial, data_final)
    print(f"[BD] Limpando vendedores antigos de {dt_ini} a {dt_fim}...")
    supabase.table("gigatech_vendedores").delete().eq("cliente_id", cliente_id).gte("data_venda", dt_ini).lte("data_venda", dt_fim).execute()

def clean_clientes_novos(cliente_id: str, data_inicial: str, data_final: str):
    dt_ini, dt_fim = parse_dates(data_inicial, data_final)
    print(f"[BD] Limpando clientes novos antigos de {dt_ini} a {dt_fim}...")
    supabase.table("gigatech_clientes_novos").delete().eq("cliente_id", cliente_id).gte("data_cadastro", dt_ini).lte("data_cadastro", dt_fim).execute()

def clean_estoque(cliente_id: str):
    print(f"[BD] Limpando estoque antigo para recadastro...")
    supabase.table("gigatech_estoque").delete().eq("cliente_id", cliente_id).execute()
