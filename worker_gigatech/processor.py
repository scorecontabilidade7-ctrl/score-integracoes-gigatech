import pandas as pd
import re
from PyPDF2 import PdfReader
from datetime import datetime
from database import batch_insert

def safe_float(val):
    try:
        return float(str(val).replace(".", "").replace(",", ".").replace("R$", "").strip())
    except:
        return 0.0

def read_robust_excel(file_path: str) -> pd.DataFrame:
    """Tenta ler um arquivo Excel de várias maneiras para suportar extensões inconsistentes ou formatos HTML/CSV ocultos."""
    try:
        # 1. Tenta ler normal (padrão openpyxl ou xlrd baseado na extensão)
        return pd.read_excel(file_path)
    except Exception as e:
        print(f"[AVISO] Tentativa 1 de leitura falhou, tentando engine='xlrd'... Erro: {e}")
        try:
            # 2. Tenta forçar engine='xlrd' para arquivos .xls salvos com extensão .xlsx
            return pd.read_excel(file_path, engine='xlrd')
        except Exception as e2:
            print(f"[AVISO] Tentativa 2 de leitura falhou, tentando read_html... Erro: {e2}")
            try:
                # 3. Tenta ler como tabela HTML (ERPs antigos costumam gerar HTML com extensão .xls/.xlsx)
                dfs = pd.read_html(file_path)
                if dfs:
                    return dfs[0]
                else:
                    raise ValueError("Nenhuma tabela encontrada no HTML")
            except Exception as e3:
                print(f"[AVISO] Tentativa 3 de leitura falhou, tentando read_csv... Erro: {e3}")
                try:
                    # 4. Tenta ler como CSV (com delimitador automático)
                    return pd.read_csv(file_path, sep=None, engine='python')
                except Exception as e4:
                    raise RuntimeError(f"Todos os parsers falharam (Excel, HTML, CSV). Erro original: {e}. Erro final: {e4}")

def process_vendas_excel(file_path: str, cliente_id: str):
    """Lê Excel de Vendas e insere no banco gigatech_vendas."""
    print(f"[PROCESS] Processando Excel de Vendas: {file_path}")
    try:
        df = read_robust_excel(file_path)
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}")
        return

    colunas_esperadas = ["Venda", "Descrição", "Qtd.Vendida", "Valor unitário", "SubTotal", "Custo", "Lucro", "Data", "Cod.Barra"]
    ok = [c for c in colunas_esperadas if c in df.columns]
    
    if not ok:
        print("[AVISO] Colunas não encontradas no Excel.")
        return

    df = df.dropna(subset=[c for c in ["Venda", "Data"] if c in df.columns])
    
    registros = []
    for _, row in df.iterrows():
        try:
            # Pandas normalmente transforma a Data em Timestamp, cujo str() é "YYYY-MM-DD ..."
            data_val = str(row.get("Data", ""))
            data_parsed = None
            if len(data_val) >= 10:
                # Vamos tentar ler nos dois formatos possíveis
                data_str = data_val[:10]
                if "-" in data_str and data_str[:4].isdigit():
                    # Formato YYYY-MM-DD
                    data_parsed = data_str
                else:
                    data_parsed = datetime.strptime(data_str, "%d/%m/%Y").date().isoformat()
        except:
            data_parsed = None

        registros.append({
            "cliente_id": cliente_id,
            "data_venda": data_parsed,
            "n_cupom": str(row.get("Venda", "")).strip(),
            "produto": str(row.get("Descrição", row.get("Descriçao", ""))).strip(),
            "ean": str(row.get("EAN", row.get("Cod.Barra", row.get("Cód Barra", "")))).strip(),
            "quantidade": safe_float(row.get("Qtd.Vendida", 0)),
            "valor_venda": safe_float(row.get("SubTotal", 0)),
            "custo": safe_float(row.get("Custo", 0)),
            "margem": safe_float(row.get("Lucro", 0)),
            "departamento": str(row.get("Departamento", "")).strip(),
            "valor_unitario": safe_float(row.get("Valor unitário", row.get("Valor unitario", 0)))
        })

    batch_insert("gigatech_vendas", registros)


def process_vendedores_pdf(file_path: str, cliente_id: str):
    """Lê PDF de Vendas por Vendedor e insere no banco gigatech_vendedores."""
    print(f"[PROCESS] Processando PDF de Vendedores: {file_path}")
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}")
        return

    registros = []
    vendedor_atual = None

    for pagina in reader.pages:
        try:
            texto = pagina.extract_text()
        except:
            continue

        if not texto:
            continue

        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha: continue

            if any(x in linha.upper() for x in ["TOTAL", "COMISSÃO", "TIPO VENDA", "VENDEDOR"]):
                continue

            if "SEM SUPERVISOR" in linha.upper():
                vendedor_atual = re.sub(r"\s+SEM SUPERVISOR.*$", "", linha, flags=re.IGNORECASE).strip()
                continue

            # Tenta a regex completa com os novos campos financeiros e comissões
            match_completo = re.search(
                r'^(.*?)\s+(NFC-e|Venda|NF-e|SAT|MFE|A Vista|Prazo|A Prazo|Venda NFC-e|Venda NF-e)\s+(\d{2}/\d{2}/\d{4})\s+(\d{5,})\s+(?:R\$)?\s*([\d\.,\-]+)\s+(?:R\$)?\s*([\d\.,\-]+)\s+(?:R\$)?\s*([\d\.,\-]+)', 
                linha, 
                re.IGNORECASE
            )
            
            if match_completo:
                cliente = match_completo.group(1).strip()
                tipo_venda = match_completo.group(2).strip()
                data_str = match_completo.group(3)
                numero = match_completo.group(4)
                vl_total = safe_float(match_completo.group(5))
                comis_vendedor = safe_float(match_completo.group(6))
                comis_supervisor = safe_float(match_completo.group(7))
            else:
                # Fallback caso seja um tipo de venda novo/diferente
                match_fallback = re.search(r'^(.*?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{5,})', linha)
                if match_fallback:
                    cliente_completo = match_fallback.group(1).strip()
                    # Tenta extrair a última palavra como tipo de venda se for comum
                    parts = cliente_completo.rsplit(' ', 1)
                    if len(parts) > 1 and parts[1].lower() in ('venda', 'nfc-e', 'nf-e', 'sat', 'mfe', 'prazo'):
                        cliente = parts[0].strip()
                        tipo_venda = parts[1].strip()
                    else:
                        cliente = cliente_completo
                        tipo_venda = None
                    data_str = match_fallback.group(2)
                    numero = match_fallback.group(3)
                    vl_total = None
                    comis_vendedor = None
                    comis_supervisor = None
                else:
                    continue
                
            try:
                data_parsed = datetime.strptime(data_str, "%d/%m/%Y").date().isoformat()
            except:
                data_parsed = None

            registros.append({
                "cliente_id": cliente_id,
                "data_venda": data_parsed,
                "n_cupom": numero,
                "nome_vendedor": vendedor_atual,
                "nome_cliente": cliente,
                "tipo_venda": tipo_venda,
                "valor_total": vl_total,
                "comissao_vendedor": comis_vendedor,
                "comissao_supervisor": comis_supervisor
            })

    batch_insert("gigatech_vendedores", registros)


def process_clientes_novos(file_path: str, cliente_id: str):
    """Lê PDF de Clientes Novos e insere no banco gigatech_clientes_novos."""
    print(f"[PROCESS] Processando PDF de Clientes Novos: {file_path}")
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}")
        return

    registros = []
    
    for pagina in reader.pages:
        try:
            texto = pagina.extract_text()
        except:
            continue

        if not texto:
            continue

        for linha in texto.splitlines():
            linha = linha.strip()
            if not linha: continue

            # Regex para ignorar cabeçalhos e rodapés
            if re.search(r'GIGA TECH|RELATÓRIO DE CLIENTE|Código|TOTAL DE CLIENTES|Nome Documento E-Mail Cadastro', linha, re.IGNORECASE):
                continue
            if linha.startswith("de ") or "Cep:" in linha or "Complemento:" in linha or "Período" in linha or "Até" in linha:
                continue
                
            match = re.search(r'^([A-ZÀ-Úa-z0-9\s\.\-\/&]+?)(?=\s+(?:\d{11,14}|\S+@\S+|\d{2}/\d{2}/\d{4}))', linha)
            match_data = re.search(r'(\d{2}/\d{2}/\d{4})', linha)
            
            if match and match_data:
                nome_cliente = match.group(1).strip()
                data_str = match_data.group(1)
                
                # remover cpf/cnpj do final do nome se existir
                nome_cliente = re.sub(r'\s+\d{2,3}\.\d{3}\.\d{3}/?\d{0,4}-?\d{2}$', '', nome_cliente).strip()
                
                try:
                    data_parsed = datetime.strptime(data_str, "%d/%m/%Y").date().isoformat()
                except:
                    data_parsed = None

                registros.append({
                    "cliente_id": cliente_id,
                    "nome_cliente": nome_cliente,
                    "data_cadastro": data_parsed
                })

    batch_insert("gigatech_clientes_novos", registros)


def process_estoque_excel(file_path: str, cliente_id: str):
    """Lê Excel de Custo de Estoque e insere no banco gigatech_estoque."""
    print(f"[PROCESS] Processando Excel de Estoque: {file_path}")
    try:
        df = read_robust_excel(file_path)
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}")
        return

    print(f"[DEBUG ESTOQUE] Colunas: {df.columns.tolist()}")
    
    if "DES_PRODUTO" in df.columns:
        df = df.dropna(subset=["DES_PRODUTO"])
    elif "Descrição" in df.columns:
        df = df.dropna(subset=["Descrição"])
    
    def clean_val(v):
        if pd.isna(v) or v is None:
            return None
        val_str = str(v).strip()
        return val_str if val_str else None

    registros = []
    for _, row in df.iterrows():
        # Validar EAN
        ean = str(row.get("COD_EAN", row.get("EAN", row.get("Cód Barra", row.get("Cód. Barra", row.get("Cod.Barra", "")))))).strip()
        if ean.lower() == "nan" or not ean:
            continue
            
        registros.append({
            "cliente_id": cliente_id,
            "ean": ean,
            "produto": clean_val(row.get("DES_PRODUTO", row.get("Descrição", ""))),
            "quantidade": safe_float(row.get("QTD_ESTOQUE_ATUAL", row.get("Estoque Atual", 0))),
            "valor_venda": safe_float(row.get("VAL_VENDA", row.get("P. Venda", row.get("Preço Venda", 0)))),
            "custo": safe_float(row.get("VAL_CUSTO", row.get("Preço Compra", row.get("Custo", 0)))),
            "marca": clean_val(row.get("DES_MARCA", row.get("Marca"))),
            "cor": clean_val(row.get("COR", row.get("Cor"))),
            "departamento": clean_val(row.get("DEPARTAMENTO", row.get("Departamento")))
        })

    batch_insert("gigatech_estoque", registros)
