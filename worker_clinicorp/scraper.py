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
            locator.wait_for(state="attached", timeout=15000)
            try:
                locator.scroll_into_view_if_needed()
            except:
                pass

            if mode == "normal":
                locator.click(timeout=15000)
            elif mode == "force":
                locator.click(timeout=15000, force=True)
            else:
                locator.evaluate("el => el.click()")
            return
        except Exception as e:
            last_error = e
    raise RuntimeError(f"Falha no clique: {last_error}")

def fill_date(page, selector, date_str):
    """
    Preenche um campo de data no Clinicorp de forma robusta e programática,
    evitando que o Datepicker se abra e crie overlays que interceptam cliques.
    """
    print(f"[SCRAPER] Preenchendo campo '{selector}' com a data '{date_str}'")
    locator = page.locator(selector)
    locator.wait_for(state="attached", timeout=15000)
    
    # Extrai o ID do seletor (ex: id=From -> From)
    el_id = selector.split("=")[-1]
    
    js_code = f"""
        const el = document.getElementById("{el_id}");
        if (el) {{
            el.removeAttribute("readonly");
            try {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
                setter.call(el, "{date_str}");
            }} catch(e) {{}}
            el.value = "{date_str}";
            el.dispatchEvent(new Event("input", {{ bubbles: true }}));
            el.dispatchEvent(new Event("change", {{ bubbles: true }}));
            el.blur();
        }}
    """
    page.evaluate(js_code)
    page.wait_for_timeout(500)

def extrair_dados(cliente_config, data_inicial, data_final):
    """
    Realiza o login e scraping no Clinicorp.
    Retorna um dicionário com os caminhos dos arquivos Excel baixados.
    """
    url = "https://sistema.clinicorp.com/"
    user = cliente_config['email_login_clinicorp']
    pwd = cliente_config['senha_login_clinicorp']
    cliente_id = str(cliente_config['id'])
    
    arquivos = {}
    
    with sync_playwright() as p:
        print("[SCRAPER] Iniciando navegador...")
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            print(f"[SCRAPER] Acessando {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Login
            page.fill('xpath=//*[@id="login-username-input"]', user)
            page.fill('xpath=//*[@id="login-password-input"]', pwd)
            safe_click(page.locator('xpath=//*[@id="app"]/div[2]/div/div/div[1]/div/div[2]/div/div/button[1]'))
            
            # Aguardar e clicar no botão da clínica/unidade
            btn_clinica = page.locator('xpath=//*[@id="shell-root"]/div/div/main/div/section/button[5]')
            btn_clinica.wait_for(state="visible", timeout=60000)
            safe_click(btn_clinica)
            
            # Aguardar o carregamento inicial da área restrita
            page.wait_for_timeout(5000)
            
            # Configure default download path via CDP session
            client = context.new_cdp_session(page)
            client.send(
                "Browser.setDownloadBehavior",
                {
                    "behavior": "allow",
                    "downloadPath": str(TMP_DIR.resolve())
                }
            )

            # 1. DOWNLOAD FATURAMENTO
            print("[SCRAPER] Navegando para Faturamento...")
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[6]/li/div/div[2]/div'))
            page.wait_for_timeout(500)
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[6]/li/ul/li[4]/div/div/div'))
            page.wait_for_timeout(2000)

            # Preencher datas no Faturamento
            fill_date(page, "id=From", data_inicial)
            fill_date(page, "id=To", data_final)

            # Selecionar "Dentista/Profissional" (type_2)
            safe_click(page.locator('xpath=//*[@id="type_2"]'))
            
            # Filtrar
            safe_click(page.locator('xpath=//*[@id="wrap"]/div[1]/div[4]/button'))
            page.wait_for_timeout(4000)

            # Baixar Excel de Faturamento
            print("[SCRAPER] Baixando Faturamento.xlsx")
            try:
                btn_down_fat = page.locator('xpath=//*[@id="table"]/div/div[1]/button[1]/span[1]')
                btn_down_fat.wait_for(state="visible", timeout=5000)
                with page.expect_download(timeout=60000) as download_info:
                    safe_click(btn_down_fat)
                
                faturamento_path = TMP_DIR / f"faturamento_{cliente_id}.xlsx"
                shutil.copy(download_info.value.path(), faturamento_path)
                arquivos["faturamento_excel"] = str(faturamento_path)
            except Exception:
                print("[SCRAPER] Nenhum dado de Faturamento encontrado neste período (tabela vazia).")

            # 2. DOWNLOAD ORÇAMENTOS
            print("[SCRAPER] Navegando para Orçamentos...")
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[5]/li/div/div[2]/div'))
            page.wait_for_timeout(500)
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[5]/li/ul/li[8]/div/div/div'))
            page.wait_for_timeout(2000)

            # Preencher datas nos Orçamentos
            fill_date(page, "id=from", data_inicial)
            fill_date(page, "id=to", data_final)

            # Filtrar
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[2]/div/div[1]/button'))
            page.wait_for_timeout(4000)

            # Baixar Excel de Orçamentos
            print("[SCRAPER] Baixando Orçamentos.xlsx")
            try:
                btn_down_orc = page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[2]/div/div[2]/div[2]/div/button[1]/span[1]')
                btn_down_orc.wait_for(state="visible", timeout=5000)
                with page.expect_download(timeout=60000) as download_info_2:
                    safe_click(btn_down_orc)

                orcamentos_path = TMP_DIR / f"orcamentos_{cliente_id}.xlsx"
                shutil.copy(download_info_2.value.path(), orcamentos_path)
                arquivos["orcamentos_excel"] = str(orcamentos_path)
            except Exception:
                print("[SCRAPER] Nenhum dado de Orçamentos encontrado neste período (tabela vazia).")

            # 3. DOWNLOAD PRIMEIRA CONSULTA
            print("[SCRAPER] Navegando para Primeiras Consultas...")
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[1]/li/div'))
            page.wait_for_timeout(500)
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[1]/li/ul/li[8]/div/div/div'))
            page.wait_for_timeout(2000)

            # Preencher datas nas Primeiras Consultas
            fill_date(page, "id=periodFrom", data_inicial)
            fill_date(page, "id=periodTo", data_final)

            # Clicar no checkbox de input[3] (como no script antigo)
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[2]/div/div[2]/input[3]'))
            
            # Filtrar
            safe_click(page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[2]/div/div[1]/button'))
            page.wait_for_timeout(4000)

            # Baixar Excel de Consultas
            print("[SCRAPER] Baixando Primeira Consulta.xlsx")
            try:
                btn_down_cons = page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[2]/div/div[3]/div[3]/div/div[1]/div/button[1]/span[1]')
                btn_down_cons.wait_for(state="visible", timeout=5000)
                with page.expect_download(timeout=60000) as download_info_3:
                    safe_click(btn_down_cons)

                consultas_path = TMP_DIR / f"consultas_{cliente_id}.xlsx"
                shutil.copy(download_info_3.value.path(), consultas_path)
                arquivos["primeira_consulta_excel"] = str(consultas_path)
            except Exception:
                print("[SCRAPER] Nenhum dado de Primeiras Consultas encontrado neste período (tabela vazia).")
            
            print("[SCRAPER] Todos os arquivos foram baixados com sucesso!")

        except Exception as e:
            print(f"[ERRO SCRAPER] {e}")
            try:
                page.screenshot(path=str(TMP_DIR / "error_screenshot.png"), full_page=True)
                print(f"[SCRAPER] Screenshot salvo em {TMP_DIR / 'error_screenshot.png'}")
            except:
                pass
            raise e
        finally:
            context.close()
            browser.close()
            
    return arquivos
