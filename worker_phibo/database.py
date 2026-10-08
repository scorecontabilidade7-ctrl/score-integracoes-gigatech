import os
from pathlib import Path
from datetime import datetime
import calendar
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega .env da raiz do projeto
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variáveis do Supabase ausentes no .env (SUPABASE_URL e SUPABASE_KEY)")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_active_clients(cliente_id: str = None):
    """
    Retorna os clientes ativos da tabela de configuração do PHIBO.
    Se cliente_id for fornecido, busca apenas ele.
    """
    query = supabase.table("phibo_clientes_config").select("*").eq("ativo", True)
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


def clean_vendas_mes(cliente_id: str, ano: int, mes: int):
    """
    Remove todas as vendas de um cliente para um determinado mês/ano
    para garantir idempotência (evitar duplicatas ao reprocessar).
    """
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dt_ini = f"{ano:04d}-{mes:02d}-01"
    dt_fim = f"{ano:04d}-{mes:02d}-{ultimo_dia:02d}"

    print(f"[BD] Limpando vendas existentes do cliente {cliente_id} no período {dt_ini} a {dt_fim}...")
    try:
        supabase.table("phibo_vendas")\
            .delete()\
            .eq("cliente_id", cliente_id)\
            .gte("data_venda", dt_ini)\
            .lte("data_venda", dt_fim)\
            .execute()
        print(f"[BD] Limpeza de vendas ({dt_ini} a {dt_fim}) concluída com sucesso.")
    except Exception as e:
        print(f"[ERRO] Falha ao limpar vendas do período: {e}")
        raise e
