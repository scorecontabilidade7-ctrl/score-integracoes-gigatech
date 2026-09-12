import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from database import get_active_clients, supabase, batch_insert, clean_ranking_vendedores
from scraper import (
    login,
    fill_dates,
    first_visible,
    safe_click,
    TMP_DIR
)
from processor import process_ranking_pdf

def parse_br_number(val):
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

def capture_daily_pdf(page, context, button_locator, timeout_ms=6000):
    """
    Tenta capturar o PDF de impressão com timeout otimizado para extração diária.
    Retorna os bytes do PDF ou None se não houver dados/impressão no dia.
    """
    pdf_bytes = None

    def on_response(response):
        nonlocal pdf_bytes
        try:
            content_type = (response.headers.get("content-type") or "").lower()
            if "application/pdf" in content_type or "octet-stream" in content_type:
                body = response.body()
                if body and body[:4] == b"%PDF":
                    pdf_bytes = body
        except:
            pass

    context.on("response", on_response)

    popup_page = None
    try:
        with page.expect_popup(timeout=timeout_ms) as popup_info:
            safe_click(button_locator)
        popup_page = popup_info.value
        if popup_page:
            try:
                popup_page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
                popup_page.wait_for_timeout(1000)
            except:
                pass
            try:
                popup_page.close()
            except:
                pass
    except:
        pass

    if pdf_bytes is None:
        try:
            with page.expect_download(timeout=timeout_ms) as download_info:
                safe_click(button_locator)
            download = download_info.value
            temp_path = download.path()
            if temp_path and os.path.exists(temp_path):
                with open(temp_path, "rb") as f:
                    pdf_bytes = f.read()
                try:
                    os.remove(temp_path)
                except:
                    pass
        except:
            pass

    return pdf_bytes


def extrair_ranking_do_pdf_bytes(pdf_bytes: bytes, cliente_id: str, nome_loja: str, data_venda_str: str) -> list:
    """Extrai os dados do PDF de ranking diretamente da memória."""
    import io
    import pdfplumber

    registros = []
    # Data em formato ISO YYYY-MM-DD
    try:
        data_iso = datetime.strptime(data_venda_str, "%d/%m/%Y").date().isoformat()
    except:
        data_iso = data_venda_str

    ranking_regex = re.compile(
        r'^(.*?)\s+([\d\.,]+)\s+(?:R\$\s*)?([\d\.,]+)\s+([\d\.,]+)\s+(?:R\$\s*)?([\d\.,]+)\s+([\d\.,]+)$'
    )

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = [l.strip() for l in text.splitlines() if l.strip()]
                is_in_ranking = False

                for line in lines:
                    if "RANKING DE VENDEDORES" in line.upper():
                        is_in_ranking = True
                        continue

                    if any(x in line.upper() for x in ["QUANTIDADE DE PRODUTOS VENDIDOS", "VALOR TOTAL DAS VENDAS", "TICKET M", "P.A M", "QUANTIDADE DE VENDAS"]):
                        is_in_ranking = False

                    if is_in_ranking:
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

                            registros.append({
                                "cliente_id": cliente_id,
                                "loja": nome_loja,
                                "vendedor": vendedor,
                                "data_venda": data_iso,
                                "qtd_total_vendas": int(qtd_vendas) if qtd_vendas.is_integer() else qtd_vendas,
                                "valor_total_vendas": valor_vendas,
                                "qtd_total_itens_vendidos": int(qtd_itens) if qtd_itens.is_integer() else qtd_itens,
                                "ticket_medio": tkm,
                                "pecas_por_atendimento": pa,
                            })
    except Exception as e:
        print(f"      [ERRO PARSER PDF] {e}")

    return registros


def obter_datas_com_vendas(cliente_id: str, dt_ini_iso: str, dt_fim_iso: str) -> list:
    """Busca no Supabase apenas as datas em que a loja realmente teve vendas registradas."""
    try:
        res = supabase.table("gigatech_vendas") \
            .select("data_venda") \
            .eq("cliente_id", cliente_id) \
            .gte("data_venda", dt_ini_iso) \
            .lte("data_venda", dt_fim_iso) \
            .execute()
        datas = sorted(list(set(r["data_venda"] for r in res.data if r.get("data_venda"))))
        # Converte de YYYY-MM-DD para DD/MM/YYYY
        datas_br = [datetime.strptime(d, "%Y-%m-%d").strftime("%d/%m/%Y") for d in datas]
        return datas_br
    except Exception as e:
        print(f"[AVISO] Falha ao consultar vendas para filtrar datas ativas: {e}")
        return []


def upload_excel_para_supabase(excel_path: str):
    """Lê uma planilha Excel de ranking gerada e envia para a tabela gigatech_ranking_vendedores."""
    print(f"\n[UPLOAD] Lendo arquivo Excel: {excel_path}")
    df = pd.read_excel(excel_path)
    if df.empty:
        print("[ERRO] Arquivo Excel está vazio.")
        return

    # Remove linha consolidada se houver
    if "vendedor" in df.columns:
        df = df[df["vendedor"] != "P.A. MÉDIO GERAL"]

    # Garante colunas esperadas
    registros = []
    for _, r in df.iterrows():
        # Formata data_venda
        d_val = r.get("data_venda") or r.get("data_inicial") or r.get("data")
        try:
            if isinstance(d_val, datetime):
                dt_iso = d_val.date().isoformat()
            elif isinstance(d_val, str) and "/" in d_val:
                dt_iso = datetime.strptime(d_val, "%d/%m/%Y").date().isoformat()
            else:
                dt_iso = str(d_val)[:10]
        except:
            dt_iso = str(d_val)

        registros.append({
            "cliente_id": str(r["cliente_id"]),
            "data_venda": dt_iso,
            "vendedor": str(r["vendedor"]).strip(),
            "qtd_total_vendas": int(r["qtd_total_vendas"]) if pd.notnull(r.get("qtd_total_vendas")) else 0,
            "valor_total_vendas": float(r["valor_total_vendas"]) if pd.notnull(r.get("valor_total_vendas")) else 0.0,
            "qtd_total_itens_vendidos": int(r["qtd_total_itens_vendidos"]) if pd.notnull(r.get("qtd_total_itens_vendidos")) else 0,
            "ticket_medio": float(r["ticket_medio"]) if pd.notnull(r.get("ticket_medio")) else 0.0,
            "pecas_por_atendimento": float(r["pecas_por_atendimento"]) if pd.notnull(r.get("pecas_por_atendimento")) else 0.0,
        })

    print(f"[UPLOAD] Inserindo {len(registros)} registros no Supabase (tabela gigatech_ranking_vendedores)...")
    batch_insert("gigatech_ranking_vendedores", registros)
    print("[UPLOAD] Concluído com sucesso!")


def processar_cliente_retroativo(cliente: dict, datas: list, headless: bool = True, save_db: bool = False):
    cliente_id = str(cliente["id"])
    nome_loja = cliente.get("nome_loja", cliente_id)
    url_login = "https://app.mentorasolucoes.com.br/Voti-1.0.7/login.xhtml"
    url_ranking = "https://app.mentorasolucoes.com.br/Voti-1.0.7/relatorios_vendas/frm_rel_ranking_vendedor.xhtml"
    user = cliente.get("email_login_giga")
    pwd = cliente.get("senha_login_giga")

    print("\n" + "=" * 65)
    print(f" LOJA: {nome_loja} ({cliente_id})")
    print(f" Total de dias a consultar: {len(datas)}")
    print("=" * 65)

    todos_registros = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            # 1. Login único por cliente
            login(page, url_login, user, pwd)
            print(f"[LOGIN] Login realizado com sucesso!")

            # 2. Navegar para a tela de Ranking
            print("[SCRAPER] Navegando para tela de Ranking...")
            page.goto(url_ranking, wait_until="domcontentloaded", timeout=60000)

            # Localizar botão de imprimir
            pdf_btn = first_visible(page, [
                'xpath=//form[contains(@id,"frmVenda")]//button[contains(.,"Imprimir") or .//span[contains(.,"Imprimir")]]',
                'xpath=//button[.//span[normalize-space()="Imprimir"]]'
            ])

            # 3. Loop dia a dia
            total_dias = len(datas)
            for idx, data_str in enumerate(datas, 1):
                progresso = f"[{idx}/{total_dias}] {data_str}"
                try:
                    # Preenche data de início e fim com o mesmo dia
                    fill_dates(page, "frmVenda", data_str, data_str)
                    page.wait_for_timeout(300)

                    # Captura PDF com timeout rápido
                    pdf_bytes = capture_daily_pdf(page, context, pdf_btn, timeout_ms=5000)

                    if not pdf_bytes:
                        print(f"  {progresso}: Sem dados de ranking (loja sem vendas).")
                        continue

                    # Extrai dados do PDF
                    linhas = extrair_ranking_do_pdf_bytes(pdf_bytes, cliente_id, nome_loja, data_str)
                    if linhas:
                        todos_registros.extend(linhas)
                        print(f"  {progresso}: OK ({len(linhas)} vendedores)")
                    else:
                        print(f"  {progresso}: PDF sem tabela de ranking.")

                except Exception as e:
                    print(f"  {progresso}: Erro no dia: {e}")
                    try:
                        page.goto(url_ranking, wait_until="domcontentloaded", timeout=30000)
                        pdf_btn = first_visible(page, [
                            'xpath=//form[contains(@id,"frmVenda")]//button[contains(.,"Imprimir") or .//span[contains(.,"Imprimir")]]',
                            'xpath=//button[.//span[normalize-space()="Imprimir"]]'
                        ])
                    except:
                        pass

        finally:
            context.close()
            browser.close()

    # 4. Exportar XLSX para a loja
    if todos_registros:
        df = pd.DataFrame(todos_registros)
        export_dir = Path(__file__).parent / "ranking_exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        d_ini_s = datas[0].replace("/", "")
        d_fim_s = datas[-1].replace("/", "")
        nome_sanitizado = re.sub(r'[^\w\-_\. ]', '_', nome_loja).strip().replace(" ", "_")
        file_name = f"ranking_diario_{nome_sanitizado}_{d_ini_s}_{d_fim_s}.xlsx"
        xlsx_path = export_dir / file_name

        df.to_excel(xlsx_path, index=False)
        print(f"\n[SALVO] Planilha diária gerada: {xlsx_path} ({len(df)} linhas extraídas)")

        # 5. Inserir no Supabase se solicitado
        if save_db:
            print(f"[BD] Inserindo {len(todos_registros)} registros no Supabase...")
            clean_ranking_vendedores(cliente_id, datas[0], datas[-1])
            # Formata para schema da tabela
            db_records = []
            for r in todos_registros:
                db_records.append({
                    "cliente_id": cliente_id,
                    "data_venda": r["data_venda"],
                    "vendedor": r["vendedor"],
                    "qtd_total_vendas": r["qtd_total_vendas"],
                    "valor_total_vendas": r["valor_total_vendas"],
                    "qtd_total_itens_vendidos": r["qtd_total_itens_vendidos"],
                    "ticket_medio": r["ticket_medio"],
                    "pecas_por_atendimento": r["pecas_por_atendimento"],
                })
            batch_insert("gigatech_ranking_vendedores", db_records)
            print(f"[BD] Registros inseridos com sucesso na tabela gigatech_ranking_vendedores!")

        return df
    else:
        print(f"\n[AVISO] Nenhum dado de ranking extraído para a loja {nome_loja}.")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Extração diária retroativa do Ranking de Vendedores (P.A.) do GigaTech.")
    parser.add_argument("--cliente-id", default=os.getenv("KESTRA_CLIENTE_ID") or "TODOS", help="ID do cliente ou TODOS")
    parser.add_argument("--data-ini", default="01/01/2026", help="Data inicial (DD/MM/AAAA)")
    parser.add_argument("--data-fim", default="11/09/2026", help="Data final (DD/MM/AAAA)")
    parser.add_argument("--only-sales-days", action="store_true", help="Consulta o banco e pula dias sem nenhuma venda (altamente recomendado)")
    parser.add_argument("--save-db", action="store_true", help="Salva automaticamente no Supabase após extrair")
    parser.add_argument("--upload-excel", default=None, help="Caminho de um XLSX já gerado para enviar ao Supabase")
    parser.add_argument("--no-headless", action="store_true", help="Abre o navegador visualmente")
    args = parser.parse_args()

    # Modo 1: Apenas subir um Excel existente para o banco
    if args.upload_excel:
        upload_excel_para_supabase(args.upload_excel)
        return

    # Modo 2: Extração dia a dia via scraper
    print("=" * 65)
    print(" 🚀 EXTRAÇÃO DIÁRIA RETROATIVA - RANKING DE VENDEDORES (P.A.)")
    print("=" * 65)
    print(f"Período     : {args.data_ini} até {args.data_fim}")
    print(f"Filtro Loja : {args.cliente_id}")
    print(f"Salvar BD   : {args.save_db}")
    print(f"Pular vazios: {args.only_sales_days}")

    # Gera a lista de todas as datas no período
    dt_ini = datetime.strptime(args.data_ini, "%d/%m/%Y")
    dt_fim = datetime.strptime(args.data_fim, "%d/%m/%Y")
    dias_totais = (dt_fim - dt_ini).days + 1
    todas_datas = [(dt_ini + timedelta(days=i)).strftime("%d/%m/%Y") for i in range(dias_totais)]

    # Buscar clientes ativos
    cid_param = None if args.cliente_id.upper() == "TODOS" else args.cliente_id
    clientes = get_active_clients(cid_param)
    if not clientes:
        print("[ERRO] Nenhum cliente ativo encontrado.")
        sys.exit(1)

    print(f"\n[BD] {len(clientes)} cliente(s) ativo(s) a processar.")

    todos_dfs = []
    for cliente in clientes:
        cid = str(cliente["id"])
        nome = cliente.get("nome_loja", cid)

        # Se --only-sales-days estiver ativo, filtra apenas datas que tiveram vendas no banco
        if args.only_sales_days:
            dt_ini_iso = dt_ini.date().isoformat()
            dt_fim_iso = dt_fim.date().isoformat()
            datas_loja = obter_datas_com_vendas(cid, dt_ini_iso, dt_fim_iso)
            if not datas_loja:
                print(f"\n[AVISO] {nome}: Nenhuma data de venda encontrada no banco para o período.")
                continue
            print(f"[FILTRO] {nome}: Reduzido de {len(todas_datas)} dias para {len(datas_loja)} dias com vendas!")
        else:
            datas_loja = todas_datas

        df_loja = processar_cliente_retroativo(
            cliente=cliente,
            datas=datas_loja,
            headless=not args.no_headless,
            save_db=args.save_db
        )
        if not df_loja.empty:
            todos_dfs.append(df_loja)

    # Se processou mais de uma loja, gera um XLSX consolidado geral
    if len(todos_dfs) > 1:
        df_geral = pd.concat(todos_dfs, ignore_index=True)
        export_dir = Path(__file__).parent / "ranking_exports"
        d_ini_s = args.data_ini.replace("/", "")
        d_fim_s = args.data_fim.replace("/", "")
        geral_path = export_dir / f"ranking_diario_CONSOLIDADO_{d_ini_s}_{d_fim_s}.xlsx"
        df_geral.to_excel(geral_path, index=False)
        print(f"\n" + "=" * 65)
        print(f" [OK] PLANILHA CONSOLIDADA GERAL SALVA: {geral_path}")
        print("=" * 65)

    print("\n" + "=" * 65)
    print(" EXTRAÇÃO DIÁRIA CONCLUÍDA COM SUCESSO!")
    print("=" * 65)

if __name__ == "__main__":
    main()
