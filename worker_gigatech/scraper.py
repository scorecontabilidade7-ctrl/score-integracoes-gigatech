import re
import os
import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

TMP_DIR = Path(__file__).parent / "tmp_downloads"
TMP_DIR.mkdir(parents=True, exist_ok=True)

def safe_click(locator):
    last_error = None
    for mode in ("normal", "force", "js"):
        try:
            locator.wait_for(state="attached", timeout=10000)
            try: locator.scroll_into_view_if_needed()
            except: pass

            if mode == "normal": locator.click(timeout=10000)
            elif mode == "force": locator.click(timeout=10000, force=True)
            else: locator.evaluate("el => el.click()")
            return
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Falha no clique: {last_error}")

def first_visible(page, selectors, timeout=30000):
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            return locator
        except: pass
    raise RuntimeError(f"Nenhum seletor encontrado.")

def login(page, url, user, pwd):
    print(f"[LOGIN] Acessando {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.fill("#j_username", user)
    page.fill("#j_password", pwd)
    safe_click(page.locator("#logar"))
    page.locator('xpath=//*[@id="menuform:um_venda"]/a').wait_for(state="visible", timeout=60000)

def fill_dates(page, form_id, data_inicial, data_final):
    # Encontra os inputs de data específicos do formulário ativo (ex: frmVenda, frmTitulo, etc)
    date_inputs = page.locator(f'//form[contains(@id,"{form_id}")]//input[contains(@class,"hasDatepicker")] >> visible=true')
    date_inputs.first.wait_for(state="visible", timeout=15000)
    count = date_inputs.count()
    if count >= 2:
        # Preenche data inicial
        date_inputs.nth(0).click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(300)
        date_inputs.nth(0).fill(data_inicial)
        date_inputs.nth(0).press("Tab")
        page.wait_for_timeout(500)
        
        # Preenche data final
        date_inputs.nth(1).click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(300)
        date_inputs.nth(1).fill(data_final)
        date_inputs.nth(1).press("Tab")
        page.wait_for_timeout(500)
    elif count == 1:
        # Se o formulário tiver apenas 1 campo de data (como no caso de relatórios que filtram apenas uma data por vez)
        date_inputs.first.click()
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.wait_for_timeout(300)
        date_inputs.first.fill(data_inicial)
        date_inputs.first.press("Tab")
        page.wait_for_timeout(500)

def capture_pdf_via_print_button(page, context, button_locator, dest_name):
    pdf_bytes = None
    def on_response(response):
        nonlocal pdf_bytes
        try:
            if "application/pdf" in (response.headers.get("content-type") or "").lower():
                body = response.body()
                if body and body[:4] == b"%PDF":
                    pdf_bytes = body
        except: pass
    
    context.on("response", on_response)
    popup_page = None
    try:
        with page.expect_popup(timeout=10000) as popup_info:
            safe_click(button_locator)
        popup_page = popup_info.value
        if popup_page:
            popup_page.wait_for_load_state("domcontentloaded", timeout=15000)
            popup_page.wait_for_timeout(3000)
    except: pass
    
    if pdf_bytes is None:
        try:
            with page.expect_download(timeout=10000) as download_info:
                safe_click(button_locator)
            download = download_info.value
            temp_path = download.path()
            with open(temp_path, "rb") as f:
                pdf_bytes = f.read()
        except: pass

    if popup_page and not popup_page.is_closed():
        popup_page.close()
    try: context.remove_listener("response", on_response)
    except: pass
    
    if pdf_bytes is None:
        raise RuntimeError("PDF não capturado.")

    dest_path = TMP_DIR / dest_name
    with open(dest_path, "wb") as f:
        f.write(pdf_bytes)
    return str(dest_path)


def extrair_dados(cliente_config, data_inicial, data_final):
    """
    Realiza o scraping para o cliente. Retorna um dict com os caminhos dos arquivos locais.
    """
    url = "https://app.mentorasolucoes.com.br/Voti-1.0.7/login.xhtml"
    user = cliente_config['email_login_giga']
    pwd = cliente_config['senha_login_giga']
    cliente_id = str(cliente_config['id'])
    
    arquivos = {}
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            login(page, url, user, pwd)
            
            # VENDAS EXCEL
            print("[SCRAPER] Baixando Vendas Excel")
            page.goto(page.url, wait_until="domcontentloaded")
            safe_click(page.locator('xpath=//*[@id="menuform:um_venda"]/a'))
            safe_click(page.locator('xpath=//*[@id="menuform:um_reltorios"]/a'))
            safe_click(page.locator('xpath=//*[@id="menuform:um_rfrm_rel_venda_detalhada_novo"]/a'))
            fill_dates(page, "frmVenda", data_inicial, data_final)
            page.wait_for_timeout(1000)
            btn = first_visible(page, [
                'xpath=//form[contains(@id,"frmVenda")]//button[not(contains(@class,"ui-splitbutton-menubutton")) and .//span[contains(normalize-space(.),"Exportar Xlsx")]]',
                'xpath=//button[.//span[normalize-space()="Exportar Xlsx"] and not(contains(@class, "ui-splitbutton-menubutton"))]'
            ])
            with page.expect_download(timeout=60000) as d:
                btn.click(timeout=30000, force=True)
            vendas_path = TMP_DIR / f"vendas_{cliente_id}.xls"
            shutil.copy(d.value.path(), vendas_path)
            arquivos["vendas_excel"] = str(vendas_path)

            # VENDEDOR PDF
            print("[SCRAPER] Baixando Vendas Vendedor PDF")
            safe_click(page.locator('xpath=//*[@id="menuform:um_reltorios9"]/a'))
            fill_dates(page, "frmTitulo", data_inicial, data_final)
            pdf_btn = first_visible(page, ['xpath=//*[@id="frmTitulo:j_idt142"]', 'xpath=//button[contains(.,"Imprimir")]'])
            arquivos["vendedores_pdf"] = capture_pdf_via_print_button(page, context, pdf_btn, f"vendedores_{cliente_id}.pdf")

            # ESTOQUE EXCEL
            print("[SCRAPER] Baixando Custo Estoque Excel")
            page.goto(page.url, wait_until="domcontentloaded")
            safe_click(page.locator('xpath=//*[@id="menuform:themes"]/a'))
            safe_click(page.locator('xpath=//*[@id="menuform:um_reltorios_Base"]/a'))
            safe_click(page.locator('xpath=//*[@id="menuform:frm_rel_custo_estoque"]/a'))
            page.wait_for_timeout(1000)
            btn_est = page.locator('xpath=//button[.//span[normalize-space()="Exportar"]]')
            with page.expect_download(timeout=60000) as d:
                safe_click(btn_est)
            estoque_path = TMP_DIR / f"estoque_{cliente_id}.xlsx"
            shutil.copy(d.value.path(), estoque_path)
            arquivos["estoque_excel"] = str(estoque_path)

            # CLIENTES NOVOS PDF
            print("[SCRAPER] Baixando Clientes Novos PDF")
            safe_click(page.locator('xpath=//*[@id="menuform:um_reltorios_cliente_periodo"]/a/span'))
            # fill_dates(page, data_inicial, data_final) # a interface as vezes nao tem
            pdf_btn_cli = first_visible(page, ['xpath=//*[@id="frmRelatorio:j_idt130"]', 'xpath=//button[contains(.,"Imprimir")]'])
            arquivos["clientes_pdf"] = capture_pdf_via_print_button(page, context, pdf_btn_cli, f"clientes_{cliente_id}.pdf")

        except Exception as e:
            print(f"[ERRO SCRAPER] {e}")
        finally:
            context.close()
            browser.close()
            
    return arquivos
