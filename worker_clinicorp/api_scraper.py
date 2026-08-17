import os
import shutil
from pathlib import Path
import requests
from playwright.sync_api import sync_playwright
from datetime import datetime

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
    print(f"[API SCRAPER] Preenchendo campo '{selector}' com a data '{date_str}'")
    locator = page.locator(selector)
    try:
        locator.wait_for(state="attached", timeout=10000)
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
    except Exception as e:
        print(f"[API SCRAPER] Aviso ao preencher data em {selector}: {e}")

def get_auth_token_and_agendamentos(cliente_config, data_inicial, data_final):
    """
    Realiza login via Playwright, captura o Bearer Token para as APIs de Faturamento,
    Orçamentos e Primeiras Consultas, e também realiza a extração do relatório
    de Agendamentos Gerais.
    """
    url = "https://sistema.clinicorp.com/"
    user = cliente_config['email_login_clinicorp']
    pwd = cliente_config['senha_login_clinicorp']
    cliente_id = str(cliente_config['id'])
    
    print(f"[API SCRAPER] Iniciando login para {user}...")
    token = None
    agendamentos_file = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.fill('xpath=//*[@id="login-username-input"]', user)
            page.fill('xpath=//*[@id="login-password-input"]', pwd)
            
            # Clicar em Entrar
            btn_login = page.locator('xpath=//*[@id="app"]/div[2]/div/div/div[1]/div/div[2]/div/div/button[1]')
            btn_login.click()
            
            print("[API SCRAPER] Aguardando requisição com Bearer Token...")
            with page.expect_request(
                lambda req: "authorization" in req.headers and "Bearer" in req.headers["authorization"], 
                timeout=45000
            ) as auth_req:
                token = auth_req.value.headers["authorization"]
                print("[API SCRAPER] Token capturado com sucesso!")

            # Clicar na clínica/unidade se necessário
            page.wait_for_timeout(3000)
            try:
                btn_clinica = page.locator('xpath=//*[@id="shell-root"]/div/div/main/div/section/button[5] | //button[contains(.,"Clinic")] | //button[contains(.,"Unidade")]')
                if btn_clinica.count() > 0:
                    btn_clinica.first.click(timeout=10000)
                    page.wait_for_timeout(3000)
            except Exception:
                pass

            # Navegar para Relatórios -> Agendamentos -> Geral
            try:
                print("[API SCRAPER] Navegando para Relatórios > Agendamentos > Geral...")
                menu_agend = page.locator('xpath=//*[@id="show_screen_div"]/div/div/div[1]/ul/div[1]/li/div | text="Agendamentos"').first
                if menu_agend.count() > 0:
                    safe_click(menu_agend)
                    page.wait_for_timeout(1000)

                btn_geral = page.locator('text="Geral"').first
                if btn_geral.count() > 0:
                    safe_click(btn_geral)
                    page.wait_for_timeout(2000)

                for f_id in ("id=From", "id=from", "id=periodFrom", "id=De", "id=de"):
                    if page.locator(f_id).count() > 0:
                        fill_date(page, f_id, data_inicial)
                        break
                
                for t_id in ("id=To", "id=to", "id=periodTo", "id=Ate", "id=ate"):
                    if page.locator(t_id).count() > 0:
                        fill_date(page, t_id, data_final)
                        break

                btn_listar = page.locator('button:has-text("Listar"), button:has-text("Filtrar")').first
                if btn_listar.count() > 0:
                    safe_click(btn_listar)
                    page.wait_for_timeout(4000)

                print("[API SCRAPER] Baixando planilha de Agendamentos Gerais...")
                with page.expect_download(timeout=60000) as download_info:
                    export_btn = page.locator('button:has(svg), a:has(svg), button.btn-outline-primary').last
                    safe_click(export_btn)

                agend_path = TMP_DIR / f"agendamentos_geral_{cliente_id}.xlsx"
                shutil.copy(download_info.value.path(), agend_path)
                agendamentos_file = str(agend_path)
                print(f"[API SCRAPER] Arquivo de agendamentos salvo em {agendamentos_file}")
            except Exception as e:
                print(f"[API SCRAPER] Aviso ao baixar planilha de Agendamentos Gerais: {e}")

        except Exception as e:
            print(f"[ERRO API SCRAPER] Falha no login ou extração: {e}")
            raise e
        finally:
            context.close()
            browser.close()
            
    return token, agendamentos_file


def _format_date_for_api(date_str):
    """Converte DD/MM/YYYY ou YYYY-MM-DD para YYYY-MM-DD exigido na query."""
    try:
        if "/" in date_str:
            return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        return date_str
    except:
        return date_str

def fetch_orcamentos(token, data_inicial, data_final, clinic_id="0"):
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    url = f"https://api.clinicorp.com/solution/api/treatment/list_all_estimates?from={d_ini}&to={d_fim}&status=ALL&clinic_id={clinic_id}&getProcedures=X&_AccessPath=*.Estimate.RunEstimatesReport"
    
    print(f"[API SCRAPER] Buscando Orçamentos ({d_ini} a {d_fim})...")
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("list", [])

def fetch_faturamento(token, data_inicial, data_final):
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    url = f"https://api.clinicorp.com/solution/api/treatment/list_expertise_revenue?Type=DENTIST&from={d_ini}&to={d_fim}&NotAggregate=X&_AccessPath=*.FinancialReports.RunSalesReport"
    
    print(f"[API SCRAPER] Buscando Faturamento ({d_ini} a {d_fim})...")
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def fetch_primeiras_consultas(token, data_inicial, data_final):
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    url = f"https://api.clinicorp.com/solution/api/reports/appointment/first-time?from={d_ini}&to={d_fim}&_AccessPath=*.Appointment.RunFirstVisitReport"
    
    print(f"[API SCRAPER] Buscando Primeiras Consultas ({d_ini} a {d_fim})...")
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("list", [])

def fetch_agendamentos_geral(token, data_inicial, data_final):
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    url = f"https://api.clinicorp.com/solution/api/reports/appointment/general?from={d_ini}&to={d_fim}&status=ALL&_AccessPath=*.Appointment.RunGeneralReport"
    
    print(f"[API SCRAPER] Buscando Agendamentos Gerais ({d_ini} a {d_fim})...")
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            res_json = resp.json()
            return res_json.get("list", res_json if isinstance(res_json, list) else [])
    except Exception as e:
        print(f"[API SCRAPER] Aviso ao buscar API de agendamentos gerais: {e}")
    return []

