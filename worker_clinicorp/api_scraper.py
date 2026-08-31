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

def get_auth_token(cliente_config):
    """
    Realiza login via Playwright apenas para interceptar o tráfego de rede
    e capturar o token de autenticação (Bearer Token).
    Assim que captura, fecha o navegador imediatamente.
    """
    url = "https://sistema.clinicorp.com/"
    user = cliente_config['email_login_clinicorp']
    pwd = cliente_config['senha_login_clinicorp']
    
    print(f"[API SCRAPER] Iniciando login para {user} para obter Bearer Token...")
    token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.fill('xpath=//*[@id="login-username-input"]', user)
            page.fill('xpath=//*[@id="login-password-input"]', pwd)
            
            print("[API SCRAPER] Aguardando requisição com Bearer Token...")
            with page.expect_request(
                lambda req: "authorization" in req.headers and "Bearer" in req.headers["authorization"], 
                timeout=45000
            ) as auth_req:
                safe_click(page.locator('xpath=//*[@id="app"]/div[2]/div/div/div[1]/div/div[2]/div/div/button[1]'))
                token = auth_req.value.headers["authorization"]
                print("[API SCRAPER] Token capturado com sucesso!")

        except Exception as e:
            print(f"[ERRO API SCRAPER] Falha ao capturar token: {e}")
            raise e
        finally:
            context.close()
            browser.close()
            
    return token

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
    """
    Busca relatório de todos os Agendamentos Gerais direto via API REST.
    """
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    url = f"https://api.clinicorp.com/solution/api/reports/appointment/all?from={d_ini}&to={d_fim}&status=ALL&_AccessPath=*.Appointment.RunGeneralReport"
    
    print(f"[API SCRAPER] Buscando Agendamentos Gerais ({d_ini} a {d_fim})...")
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    res_json = resp.json()
    return res_json.get("list", res_json if isinstance(res_json, list) else [])

def fetch_procedimentos_executados(token, data_inicial, data_final):
    """
    Busca relatório de Procedimentos Executados direto via API REST.
    """
    d_ini = _format_date_for_api(data_inicial)
    d_fim = _format_date_for_api(data_final)
    
    headers = {
        "Authorization": token,
        "Accept": "application/json"
    }

    url = f"https://api.clinicorp.com/api/treatment/get_executed_clinical_sheet_items?from={d_ini}&to={d_fim}&_AccessPath=*.ClinicalRecord.RunExecutedProceduresReport"
    print(f"[API SCRAPER] Buscando Procedimentos Executados ({d_ini} a {d_fim})...")
    
    try:
        resp = requests.get(url, headers=headers, timeout=45)
        resp.raise_for_status()
        res_json = resp.json()
        data_list = res_json.get("list", [])
        print(f"[API SCRAPER] {len(data_list)} procedimentos executados retornados da API.")
        return data_list
    except Exception as e:
        print(f"[ERRO API SCRAPER] Falha ao buscar procedimentos executados: {e}")
        return []

