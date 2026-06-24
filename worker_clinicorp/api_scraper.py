import requests
from playwright.sync_api import sync_playwright
from datetime import datetime

def get_auth_token(cliente_config):
    """
    Realiza login via Playwright apenas para interceptar o tráfego de rede
    e capturar o token de autenticação (Bearer Token).
    Assim que captura, fecha o navegador.
    """
    url = "https://sistema.clinicorp.com/"
    user = cliente_config['email_login_clinicorp']
    pwd = cliente_config['senha_login_clinicorp']
    
    print(f"[API SCRAPER] Iniciando login para {user} com objetivo de capturar Token...")
    token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.fill('xpath=//*[@id="login-username-input"]', user)
            page.fill('xpath=//*[@id="login-password-input"]', pwd)
            
            # Clicar em Entrar
            btn_login = page.locator('xpath=//*[@id="app"]/div[2]/div/div/div[1]/div/div[2]/div/div/button[1]')
            btn_login.click()
            
            print("[API SCRAPER] Aguardando requisição com Bearer Token...")
            # Espera até que alguma requisição tenha o header Authorization com "Bearer"
            with page.expect_request(
                lambda req: "authorization" in req.headers and "Bearer" in req.headers["authorization"], 
                timeout=45000
            ) as auth_req:
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
