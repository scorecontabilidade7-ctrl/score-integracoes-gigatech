import pandas as pd
import re
from pathlib import Path
from PyPDF2 import PdfReader
import pdfplumber
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
    capturar_vendedor = False

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

            if capturar_vendedor:
                if re.search(r'\d{2}/\d{2}/\d{4}', linha):
                    # É uma quebra de página que emendou direto na venda, cancela a captura
                    capturar_vendedor = False
                elif linha.upper() in ["DATA", "VENDA", "NÚMERO", "VENDANÚMERO", "CLIENTEVALOR", "VENDAS"]:
                    # Cabeçalhos sujos de quebra de página
                    capturar_vendedor = False
                    continue
                else:
                    # Remove eventual "SEM SUPERVISOR" suffix
                    vendedor_atual = re.sub(r"\s+SEM SUPERVISOR.*$", "", linha, flags=re.IGNORECASE).strip()
                    # Se houver mais de duas palavras, assumir que as duas últimas são o supervisor
                    parts = vendedor_atual.split()
                    if len(parts) > 2:
                        vendedor_atual = " ".join(parts[:-2])
                    capturar_vendedor = False
                    continue

            if "VENDEDOR SUPERVISOR" in linha.upper():
                capturar_vendedor = True
                continue

            if any(x in linha.upper() for x in ["TOTAL", "COMISSÃO", "TIPO VENDA", "VENDEDOR"]):
                continue

            if "SEM SUPERVISOR" in linha.upper():
                vendedor_atual = re.sub(r"\s+SEM SUPERVISOR.*$", "", linha, flags=re.IGNORECASE).strip()
                continue

            # Nova Regex Flexível baseada no formato real de extração do PyPDF2
            regex_completo = r'^(.*?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{5,})\s+(?:R\$)?\s*([\d\.,\-]+)\s*(?:R\$)?\s*([\d\.,\-]+)\s+(?:R\$)?\s*([\d\.,\-]+)\s*(NFC-e|Venda|NF-e|SAT|MFE|A Vista|Prazo|A Prazo|Venda NFC-e|Venda NF-e)$'
            
            match_completo = re.search(regex_completo, linha, re.IGNORECASE)
            
            if match_completo:
                cliente = match_completo.group(1).strip()
                data_str = match_completo.group(2)
                numero = match_completo.group(3)
                vl_total = safe_float(match_completo.group(4))
                comis_supervisor = safe_float(match_completo.group(5))
                comis_vendedor = safe_float(match_completo.group(6))
                tipo_venda = match_completo.group(7).strip()
            else:
                # Fallback caso seja um tipo de venda novo/diferente ou faltem dados
                match_fallback = re.search(r'^(.*?)\s+(\d{2}/\d{2}/\d{4})\s+(\d{5,})', linha)
                if match_fallback:
                    cliente = match_fallback.group(1).strip()
                    data_str = match_fallback.group(2)
                    numero = match_fallback.group(3)
                    # Tenta buscar tipo de venda conhecido no final da linha
                    tipo_venda = None
                    for t in ('venda', 'nfc-e', 'nf-e', 'sat', 'mfe', 'prazo', 'a vista', 'a prazo'):
                        if linha.lower().endswith(t):
                            tipo_venda = t
                            break
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

def process_fechamento_caixa(file_path: str, cliente_id: str):
    """Lê PDF de Fechamento de Caixa e insere no banco gigatech_fechamento_caixa."""
    print(f"[PROCESS] Processando PDF de Fechamento de Caixa: {file_path}")
    try:
        reader = PdfReader(file_path)
    except Exception as e:
        print(f"[ERRO] Falha ao ler {file_path}: {e}")
        return

    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"

    lines = text.split('\n')
    data_ext = None
    
    date_match = re.search(r"(\d{2}/\d{2}/\d{4})\s*Período:", text)
    if date_match:
        data_ext = date_match.group(1)
    else:
        date_match = re.search(r"Período:\s*(\d{2}/\d{2}/\d{4})", text)
        if date_match:
            data_ext = date_match.group(1)
            
    try:
        data_parsed = datetime.strptime(data_ext, "%d/%m/%Y").date().isoformat()
    except:
        data_parsed = None

    registros = []
    
    in_dinheiro = False
    in_suprimento = False
    in_sangria = False
    
    def format_val(v, motivo):
        v = v.replace("R$", "").strip()
        if motivo not in ("TOTAL VENDA", "ABERTURA"):
            return "-" + v
        return v
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line == "DINHEIRO":
            in_dinheiro = True
            in_suprimento = False
            in_sangria = False
            continue
        elif "SUPRIMENTO" in line:
            in_suprimento = True
            in_dinheiro = False
            in_sangria = False
            continue
        elif "SANGRIA" in line:
            in_sangria = True
            in_dinheiro = False
            in_suprimento = False
            continue
            
        if "Total Troco:" in line or "Total Troco :" in line:
            match = re.search(r"(R\$[\d\.,]+|[\d\.,]+)\s*Total\s*Troco", line)
            if not match:
                match = re.search(r"Total\s*Troco\s*:\s*(R\$[\d\.,]+|[\d\.,]+)", line)
            
            if match:
                motivo_troco = "TROCO"
                valor = safe_float(format_val(match.group(1), motivo_troco))
                registros.append({
                    "cliente_id": cliente_id,
                    "forma": "DINHEIRO",
                    "motivo": motivo_troco,
                    "data_caixa": data_parsed,
                    "valor": valor
                })
            
        if in_dinheiro:
            if "Total :" in line:
                match = re.search(r"(R\$[\d\.,]+|[\d\.,]+)\s*Total\s*:", line)
                if match:
                    motivo = "TOTAL VENDA"
                    valor = safe_float(format_val(match.group(1), motivo))
                    registros.append({
                        "cliente_id": cliente_id,
                        "forma": "DINHEIRO",
                        "motivo": motivo,
                        "data_caixa": data_parsed,
                        "valor": valor
                    })
                in_dinheiro = False
                
        elif in_suprimento:
            if "Total :" in line:
                in_suprimento = False
            else:
                match = re.search(r"^(.*?)\s*(R\$[\d\.,]+)$", line)
                if match:
                    motivo = match.group(1).strip()
                    valor = safe_float(format_val(match.group(2), motivo))
                    registros.append({
                        "cliente_id": cliente_id,
                        "forma": "SUPRIMENTOS",
                        "motivo": motivo,
                        "data_caixa": data_parsed,
                        "valor": valor
                    })
                    
        elif in_sangria:
            if "Total :" in line:
                in_sangria = False
            else:
                match = re.search(r"^(.*?)\s*(R\$[\d\.,]+)$", line)
                if match:
                    motivo = match.group(1).strip()
                    valor = safe_float(format_val(match.group(2), motivo))
                    registros.append({
                        "cliente_id": cliente_id,
                        "forma": "SANGRIA",
                        "motivo": motivo,
                        "data_caixa": data_parsed,
                        "valor": valor
                    })

    batch_insert("gigatech_fechamento_caixa", registros)


def parse_br_number(val):
    """Converte números formatados em padrão brasileiro para float com precisão."""
    if val is None:
        return 0.0
    s = str(val).replace("R$", "").replace(" ", "").strip()
    if not s:
        return 0.0
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0


def process_ranking_pdf(file_path: str, cliente_id: str, nome_loja: str = "", export_dir: str = None) -> pd.DataFrame:
    """
    Lê o PDF de Ranking de Vendedores, processa os dados de cada vendedor e exporta para XLSX no armazenamento local.
    """
    print(f"[PROCESS] Processando PDF de Ranking de Vendedores: {file_path}")
    registros = []
    empresa_info = {}

    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = [l.strip() for l in text.splitlines() if l.strip()]

                for line in lines:
                    period_match = re.search(r'Per[íi]odo:\s*(\d{2}/\d{2}/\d{4})\s*At[ée]\s*(\d{2}/\d{2}/\d{4})', line, re.IGNORECASE)
                    if period_match:
                        empresa_info['data_inicial'] = period_match.group(1)
                        empresa_info['data_final'] = period_match.group(2)
                    cnpj_match = re.search(r'CNPJ:\s*([\d\./\-]+)', line)
                    if cnpj_match:
                        empresa_info['cnpj'] = cnpj_match.group(1)

                ranking_regex = re.compile(
                    r'^(.*?)\s+([\d\.,]+)\s+(?:R\$\s*)?([\d\.,]+)\s+([\d\.,]+)\s+(?:R\$\s*)?([\d\.,]+)\s+([\d\.,]+)$'
                )

                is_in_ranking_section = False
                for line in lines:
                    if "RANKING DE VENDEDORES" in line.upper():
                        is_in_ranking_section = True
                        continue

                    if any(x in line.upper() for x in ["QUANTIDADE DE PRODUTOS VENDIDOS", "VALOR TOTAL DAS VENDAS", "TICKET M", "P.A M", "QUANTIDADE DE VENDAS"]):
                        is_in_ranking_section = False

                    if is_in_ranking_section:
                        if any(h in line.upper() for h in ["VENDEDOR", "QTD TOTAL", "VALOR TOTAL", "ITENS VENDIDOS", "TKM", "P.A."]):
                            continue

                        match = ranking_regex.search(line)
                        if match:
                            vendedor = match.group(1).strip()
                            qtd_vendas = parse_br_number(match.group(2))
                            valor_vendas = parse_br_number(match.group(3))
                            qtd_itens = parse_br_number(match.group(4))
                            tkm = parse_br_number(match.group(5))
                            pa = parse_br_number(match.group(6))

                            d_ini = empresa_info.get("data_inicial", "")
                            d_fim = empresa_info.get("data_final", "")

                            registros.append({
                                "cliente_id": cliente_id,
                                "loja": nome_loja,
                                "vendedor": vendedor,
                                "qtd_total_vendas": int(qtd_vendas) if qtd_vendas.is_integer() else qtd_vendas,
                                "valor_total_vendas": valor_vendas,
                                "qtd_total_itens_vendidos": int(qtd_itens) if qtd_itens.is_integer() else qtd_itens,
                                "ticket_medio": tkm,
                                "pecas_por_atendimento": pa,
                                "data_inicial": d_ini,
                                "data_final": d_fim
                            })
    except Exception as e:
        print(f"[ERRO] Falha ao ler PDF {file_path}: {e}")
        return pd.DataFrame()

    df = pd.DataFrame(registros)
    if df.empty:
        print(f"[AVISO] Nenhum registro extraído do PDF de ranking para o cliente {cliente_id}.")
        return df

    # Cálculo do P.A. Médio Geral (Total de Produtos Vendidos / Quantidade de Vendas)
    soma_vendas = df["qtd_total_vendas"].sum()
    soma_itens = df["qtd_total_itens_vendidos"].sum()
    pa_medio_calculado = round(soma_itens / soma_vendas, 3) if soma_vendas > 0 else 0.0

    # Linha consolidada no rodapé contendo apenas o P.A. Médio Geral
    linha_consolidada = {
        "cliente_id": cliente_id,
        "loja": nome_loja,
        "vendedor": "P.A. MÉDIO GERAL",
        "qtd_total_vendas": None,
        "valor_total_vendas": None,
        "qtd_total_itens_vendidos": None,
        "ticket_medio": None,
        "pecas_por_atendimento": pa_medio_calculado,
        "data_inicial": empresa_info.get("data_inicial", ""),
        "data_final": empresa_info.get("data_final", "")
    }

    df_export = pd.concat([df, pd.DataFrame([linha_consolidada])], ignore_index=True)

    # Salva no diretório local de exportações
    if not export_dir:
        export_dir = Path(__file__).parent / "ranking_exports"
    else:
        export_dir = Path(export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)

    d_ini_str = empresa_info.get("data_inicial", "").replace("/", "")
    d_fim_str = empresa_info.get("data_final", "").replace("/", "")
    nome_sanitizado = re.sub(r'[^\w\-_\. ]', '_', nome_loja).strip().replace(" ", "_") if nome_loja else cliente_id
    
    file_name = f"ranking_vendedores_{nome_sanitizado}_{d_ini_str}_{d_fim_str}.xlsx"
    xlsx_path = export_dir / file_name

    df_export.to_excel(xlsx_path, index=False)
    print(f"[SALVO] Relatório Ranking de Vendedores exportado com sucesso em XLSX: {xlsx_path}")
    return df_export

