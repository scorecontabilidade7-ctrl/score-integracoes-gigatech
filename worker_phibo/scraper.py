import os
import time
import platform
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

PHIBO_LOGIN_URL = "https://sistema.phibo.com.br/"


class PhiboWindowRestrictionError(Exception):
    """Exceção levantada quando o PHIBO exibe o modal de bloqueio de horário."""
    pass


class PhiboScraper:
    def __init__(self, headless: bool = True, download_dir: str = None, proxy: dict = None):
        self.headless = headless
        self.download_dir = download_dir or str(Path(__file__).resolve().parent / "tmp_downloads")
        self.proxy = proxy
        os.makedirs(self.download_dir, exist_ok=True)

    def check_modal_bloqueio(self, page: Page):
        """Verifica se a notificação/modal de restrição de horário apareceu na tela."""
        try:
            # 1. Verifica toast PrimeNG ou dialog
            alerta = page.locator(".p-toast, p-toast, p-dialog, .p-dialog, [role='dialog'], [role='alert']").filter(
                has_text="Esta funcionalidade está desabilitada"
            ).first
            if alerta.is_visible(timeout=3000):
                msg = alerta.inner_text().strip()
                print(f"[SCRAPER] [AVISO PHIBO] {msg}")
                raise PhiboWindowRestrictionError(
                    f"PHIBO bloqueou o download por estar fora da janela permitida (08:00-10:10 / a partir das 19:10). Mensagem: {msg}"
                )
            
            # 2. Verifica qualquer elemento de texto na página
            alerta_txt = page.locator("text=Esta funcionalidade está desabilitada").first
            if alerta_txt.is_visible(timeout=1000):
                msg = alerta_txt.inner_text().strip()
                print(f"[SCRAPER] [AVISO PHIBO] {msg}")
                raise PhiboWindowRestrictionError(
                    f"PHIBO bloqueou o download por estar fora da janela permitida (08:00-10:10 / a partir das 19:10). Mensagem: {msg}"
                )
        except PlaywrightTimeoutError:
            pass

    def fechar_modais_e_avisos(self, page: Page):
        """Fecha modais promocionais, avisos e pop-ups pós-login no PrimeFaces e PrimeNG."""
        if "sistema.phibo.com.br" not in page.url:
            return
        try:
            page.keyboard.press("Escape")
            time.sleep(0.2)
        except Exception:
            pass

        # Dispara via JS a limpeza de modais de marketing (formMarketing) e remoção de overlays bloqueadores
        try:
            page.evaluate("""() => {
                // 1. Remove overlays cinzas bloqueadoras de clique
                document.querySelectorAll('.ui-widget-overlay, .ui-dialog-mask, .p-dialog-mask').forEach(el => {
                    try { el.remove(); } catch(e) {}
                });

                // Se estiver no sistema legado PrimeFaces, remove seções de modal soltas e divs absolutas de anúncio
                if (window.location.hostname.includes('sistema.phibo')) {
                    document.querySelectorAll('section, div.absolute').forEach(el => {
                        try { el.remove(); } catch(e) {}
                    });
                }

                // 2. Clica em botões de fechar de modais conhecidos
                const closeBtns = document.querySelectorAll(
                    "[id*='formMarketing'] button, [id*='formMarketing'] a, [id*='formMarketing'] [id*='idt'], " +
                    "[id*='Marketing'] .ui-icon-closethick, [id*='Marketing'] [aria-label*='Close'], " +
                    ".ui-dialog-titlebar-close, .ui-dialog-header-close, .p-dialog-header-close, button[aria-label='Close'], button:has-text('Fechar')"
                );
                closeBtns.forEach(b => {
                    try { b.click(); } catch(e) {}
                });

                // 3. Esconde qualquer modal de marketing persistente
                document.querySelectorAll("[id*='Marketing'], [id*='marketing']").forEach(el => {
                    try { el.style.display = 'none'; } catch(e) {}
                });
            }""")
            time.sleep(0.3)
        except Exception:
            pass

        selectors_fechar = [
            "[id*='formMarketing'] [id*='idt']",
            "[id*='formMarketing'] button",
            "[id*='formMarketing'] a",
            ".ui-dialog-titlebar-close",
            ".p-dialog-header-close",
            "button[aria-label='Close']",
            "button:has(.pi-times)",
            "i.pi-times",
            "button:has-text('Fechar')",
            "button:has-text('Entendi')"
        ]
        for sel in selectors_fechar:
            try:
                elem = page.locator(sel).first
                if elem.is_visible(timeout=300):
                    elem.click()
                    time.sleep(0.3)
            except Exception:
                pass

    def _extract_vendas_via_api(
        self,
        access_token: str,
        is_mes_atual: bool,
        is_mes_anterior: bool,
        target_year: int,
        target_month: int,
        data_inicio: str = None,
        data_fim: str = None,
        proxy_dict: dict = None
    ) -> str | None:
        """
        Extrai o relatório de vendas diretamente via phibo-api.com.br usando o Bearer token
        e os cabeçalhos Client Hints homologados (contornando bloqueios de HeadlessChrome no WAF
        e eventual restrição de janela no botão de exportação).
        """
        import urllib.parse
        import json
        from datetime import timezone, timedelta
        import requests

        def to_iso(d_str: str) -> str:
            s = str(d_str).strip()
            if "/" in s:
                p = s.split("/")
                if len(p) == 3:
                    return f"{p[2].zfill(4)}-{p[1].zfill(2)}-{p[0].zfill(2)}"
            return s

        if data_inicio and data_fim:
            params = {
                "opcaoFiltro": "outroPeriodo",
                "dataInicialFiltro": to_iso(data_inicio),
                "dataFinalFiltro": to_iso(data_fim),
            }
        elif is_mes_atual:
            params = {"opcaoFiltro": "mesAtual"}
        elif is_mes_anterior:
            params = {"opcaoFiltro": "mesAnterior"}
        else:
            params = {
                "opcaoFiltro": "outroMes",
                "ano": str(target_year),
                "mes": str(target_month),
            }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "Origin": "https://app.phibo.com.br",
            "Referer": "https://app.phibo.com.br/",
            "sec-ch-ua": '"Microsoft Edge";v="155", "Chromium";v="155", "Not(A:Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "showloader": "true",
            "User-Agent": "Mozilla/5.0 (Linux; Android 16; Pixel 10) AppleWebKit/537.36 (KHTML, like Gecko) Edg/155.0.0.0 Mobile Safari/537.36",
        }

        proxies = None
        if proxy_dict and proxy_dict.get("server"):
            srv = proxy_dict["server"]
            usr = proxy_dict.get("username")
            pwd = proxy_dict.get("password")
            if usr and pwd and "://" in srv and "@" not in srv:
                scheme, rest = srv.split("://", 1)
                proxy_url = f"{scheme}://{urllib.parse.quote(usr)}:{urllib.parse.quote(pwd)}@{rest}"
            else:
                proxy_url = srv
            proxies = {"http": proxy_url, "https": proxy_url}

        destino = os.path.join(self.download_dir, "relacaoVendasMes.csv")

        # 1. Tentativa direta no endpoint oficial de exportação CSV
        try:
            url_exp = "https://www.phibo-api.com.br/relacaoVendas/periodo/exportar"
            print(f"[SCRAPER] [API DIRETA] Solicitando CSV em {url_exp} (params={params})...")
            resp = requests.get(url_exp, params=params, headers=headers, proxies=proxies, timeout=30)
            if resp.status_code == 200 and "Data da Venda" in resp.text:
                with open(destino, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(resp.text.lstrip("\ufeff"))
                print(f"[SCRAPER] [API DIRETA] CSV exportado com sucesso via API: {destino}")
                return destino
            else:
                print(f"[SCRAPER] [API DIRETA] Endpoint /exportar retornou HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e_exp:
            print(f"[SCRAPER] [API DIRETA] Aviso ao chamar /exportar: {e_exp}")

        # 2. Fallback 24/7 via endpoint JSON paginado (/relacaoVendas/periodo)
        try:
            url_list = "https://www.phibo-api.com.br/relacaoVendas/periodo"
            print(f"[SCRAPER] [API DIRETA] Buscando vendas via JSON paginado em {url_list}...")
            all_items = []
            page_num = 0
            while True:
                page_params = {**params, "page": page_num, "size": 200}
                resp = requests.get(url_list, params=page_params, headers=headers, proxies=proxies, timeout=30)
                if resp.status_code != 200:
                    print(f"[SCRAPER] [API DIRETA] Endpoint JSON retornou HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
                payload = resp.json()
                content = payload.get("content") or []
                all_items.extend(content)
                if payload.get("last", True) or not content:
                    break
                page_num += 1

            def fmt_brl(val: float) -> str:
                return f"{val:.2f}".replace(".", ",")

            tz_br = timezone(timedelta(hours=-3))
            linhas = ["Origem;Data da Venda;Hora;Cliente;Vendedor;Qtde;Sub Total;Desconto;Trocas;Cashback;Frete;Total"]
            for it in all_items:
                origem = (it.get("origemVenda") or "PDV").strip()
                dt_iso = (it.get("dataVenda") or "").strip()
                if "-" in dt_iso and len(dt_iso) >= 10:
                    p = dt_iso[:10].split("-")
                    dt_br = f"{p[2]}/{p[1]}/{p[0]}"
                else:
                    dt_br = dt_iso

                hora_br = "00:00"
                dh_raw = it.get("dataHoraVenda")
                if dh_raw:
                    try:
                        dt_obj = datetime.fromisoformat(str(dh_raw).replace("Z", "+00:00"))
                        hora_br = dt_obj.astimezone(tz_br).strftime("%H:%M")
                    except Exception:
                        pass

                fone = (it.get("clienteFone") or "").strip()
                nome = (it.get("clienteNome") or "").strip()
                cliente_str = f"{fone} - {nome}" if (fone and nome) else (nome or fone)
                vendedor = (it.get("vendedorNome") or "").strip()
                qtde = int(round(float(it.get("qtdeSomaItem") or 0)))
                sub_total = float(it.get("vlrSomaItemVendaTotal") or 0.0)
                desconto = float(it.get("valorDesconto") or 0.0) + float(it.get("valorCupom") or 0.0)
                trocas = float(it.get("vlrSomaDevolucaoTotal") or 0.0)
                cashback = float(it.get("valorCashbackPagto") or 0.0)
                frete = float(it.get("valorFrete") or 0.0)
                total = round(sub_total - desconto - trocas - cashback + frete, 2)

                linhas.append(
                    f"{origem};{dt_br};{hora_br};{cliente_str};{vendedor};{qtde};"
                    f"{fmt_brl(sub_total)};{fmt_brl(desconto)};{fmt_brl(trocas)};"
                    f"{fmt_brl(cashback)};{fmt_brl(frete)};{fmt_brl(total)}"
                )

            with open(destino, "w", encoding="utf-8-sig", newline="") as f:
                f.write("\n".join(linhas) + "\n")
            print(f"[SCRAPER] [API DIRETA] CSV montado via JSON ({len(all_items)} vendas) com sucesso: {destino}")
            return destino
        except Exception as e_json:
            print(f"[SCRAPER] [API DIRETA] Aviso ao buscar JSON paginado: {e_json}")
            return None

    def run_download_vendas(
        self,
        email: str,
        senha: str,
        ano: int = None,
        mes: int = None,
        data_inicio: str = None,
        data_fim: str = None
    ) -> str:
        agora = datetime.now()
        target_year = ano or agora.year
        target_month = mes or agora.month

        # Identifica se o alvo solicitado é o mês atual ou anterior
        is_mes_atual = (target_year == agora.year and target_month == agora.month)
        is_mes_anterior = False
        if target_year == agora.year and target_month == agora.month - 1:
            is_mes_anterior = True
        elif target_month == 12 and target_year == agora.year - 1 and agora.month == 1:
            is_mes_anterior = True

        periodo_log = f"{data_inicio} até {data_fim}" if (data_inicio and data_fim) else f"{target_month:02d}/{target_year}"
        print(f"[SCRAPER] Iniciando automação Playwright para usuário: {email} (Período: {periodo_log}, Headless: {self.headless})...")
        
        # Configuração de proxy (via construtor ou variáveis de ambiente)
        proxy_server = (self.proxy and self.proxy.get("server")) or os.environ.get("PHIBO_PROXY_SERVER") or os.environ.get("PROXY_SERVER")
        proxy_user = (self.proxy and self.proxy.get("username")) or os.environ.get("PHIBO_PROXY_USERNAME") or os.environ.get("PROXY_USERNAME")
        proxy_pass = (self.proxy and self.proxy.get("password")) or os.environ.get("PHIBO_PROXY_PASSWORD") or os.environ.get("PROXY_PASSWORD")

        proxy_dict = None
        if proxy_server:
            proxy_dict = {"server": proxy_server}
            if proxy_user:
                proxy_dict["username"] = proxy_user
            if proxy_pass:
                proxy_dict["password"] = proxy_pass
            print(f"[SCRAPER] [PROXY] Roteando conexão via proxy: {proxy_server.split('@')[-1]}")

        with sync_playwright() as p:
            # Argumentos de inicialização do navegador contra detecção e compatíveis com Docker
            launch_args = [
                "--start-maximized",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--allow-running-insecure-content",
                "--ignore-certificate-errors"
            ]

            launch_kwargs = {
                "headless": self.headless,
                "args": launch_args
            }
            if proxy_dict:
                launch_kwargs["proxy"] = proxy_dict

            try:
                browser = p.chromium.launch(
                    channel="chrome",
                    **launch_kwargs
                )
            except Exception:
                try:
                    browser = p.chromium.launch(
                        channel="msedge",
                        **launch_kwargs
                    )
                except Exception:
                    browser = p.chromium.launch(
                        **launch_kwargs
                    )

            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=ua,
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                accept_downloads=True
            )
            # Mascara flag do webdriver, spoof de hardware e WebGL contra bloqueios do WAF
            context.add_init_script("""
                try {
                    delete Object.getPrototypeOf(navigator).webdriver;
                } catch(e) {}
                try {
                    if (!window.chrome) {
                        window.chrome = {
                            runtime: {},
                            loadTimes: function() {},
                            csi: function() {},
                            app: {}
                        };
                    }
                } catch(e) {}
                try {
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US', 'en']
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8
                    });
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8
                    });
                } catch(e) {}
                try {
                    const getParam = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(param) {
                        if (param === 37445) return 'Google Inc. (Intel)';
                        if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';
                        return getParam.apply(this, arguments);
                    };
                    if (window.WebGL2RenderingContext) {
                        const getParam2 = WebGL2RenderingContext.prototype.getParameter;
                        WebGL2RenderingContext.prototype.getParameter = function(param) {
                            if (param === 37445) return 'Google Inc. (Intel)';
                            if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)';
                            return getParam2.apply(this, arguments);
                        };
                    }
                } catch(e) {}
            """)
            page = context.new_page()

            # Sobrescreve Client Hints (sec-ch-ua) via CDP nativo para remover "HeadlessChrome"
            try:
                cdp = context.new_cdp_session(page)
                cdp.send("Network.setUserAgentOverride", {
                    "userAgent": ua,
                    "acceptLanguage": "pt-BR,pt;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                    "platform": "Win32",
                    "userAgentMetadata": {
                        "brands": [
                            {"brand": "Microsoft Edge", "version": "155"},
                            {"brand": "Chromium", "version": "155"},
                            {"brand": "Not(A:Brand", "version": "24"}
                        ],
                        "fullVersion": "155.0.0.0",
                        "platform": "Windows",
                        "platformVersion": "15.0.0",
                        "architecture": "x86",
                        "model": "",
                        "mobile": False
                    }
                })
            except Exception as e_cdp:
                print(f"[SCRAPER] [AVISO CDP] {e_cdp}")

            # Intercepta chamada a refreshToken para responder com o token já existente (evita 403 de borda do WAF)
            def handle_refresh(route):
                request = route.request
                print(f"[SCRAPER] [INTERCEPTOR] Interceptando chamada a refreshToken: {request.url}")
                current_url = page.url
                token = ""
                refresh = ""
                if "token=" in current_url:
                    try:
                        import urllib.parse
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(current_url).query)
                        token = parsed.get("token", [""])[0]
                        refresh = parsed.get("refresh", [""])[0]
                    except Exception:
                        pass
                import json
                body_json = json.dumps({
                    "token": token,
                    "refreshToken": refresh or token,
                    "type": "Bearer"
                })
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Access-Control-Allow-Headers": "*",
                        "Access-Control-Allow-Methods": "GET, POST, OPTIONS"
                    },
                    body=body_json
                )
            page.route("**/auth/refreshToken/**", handle_refresh)

            # Captura erros de console do navegador para diagnóstico
            def on_console(msg):
                if msg.type == "error":
                    txt = msg.text
                    if "favicon" not in txt.lower():
                        print(f"[BROWSER ERROR] {txt[:200]}")
            page.on("console", on_console)

            # Captura respostas HTTP de erro para diagnóstico exato do servidor
            def on_response(response):
                if response.status >= 400:
                    try:
                        text = response.text()[:250].strip().replace('\n', ' ')
                    except Exception:
                        text = ""
                    print(f"[HTTP {response.status}] {response.request.method} {response.url} -> {text}")
            page.on("response", on_response)

            try:
                # 1. Login
                print("[SCRAPER] [1/4] Acessando sistema.phibo.com.br...")
                page.goto(PHIBO_LOGIN_URL, wait_until="networkidle", timeout=60000)

                print("[SCRAPER] [1/4] Preenchendo credenciais...")
                page.fill('#usuario', email)
                page.fill('#senha', senha)
                
                print("[SCRAPER] [1/4] Clicando em Acessar...")
                page.click("button:has-text('Acessar')")

                # Aguarda exibição da interface pós-login
                print("[SCRAPER] [1/4] Aguardando interface pós-login...")
                try:
                    page.locator("a:has-text('Vendas'), span:has-text('Vendas'), p-menubar, nav").first.wait_for(state="visible", timeout=45000)
                    print("[SCRAPER] [1/4] Login realizado com sucesso!")
                except Exception as e:
                    print(f"[SCRAPER] [AVISO] Timeout aguardando navbar pós-login: {e}")

                # Fecha quaisquer modais promocionais ou comunicados
                self.fechar_modais_e_avisos(page)

                # 2. Navegação até Relação de vendas
                print("[SCRAPER] [2/4] Acessando tela 'Relação de vendas'...")
                if "relacao-vendas" not in page.url:
                    menu_vendas = page.locator("li[role='menuitem']:has-text('Vendas'), a.ui-submenu-link:has-text('Vendas'), a:has-text('Vendas')").filter(has_text="Vendas").first
                    if menu_vendas.is_visible(timeout=5000):
                        menu_vendas.hover()
                        time.sleep(0.5)

                    clicked_js = page.evaluate("""() => {
                        const span = Array.from(document.querySelectorAll('span.ui-menuitem-text')).find(
                            s => s.textContent && s.textContent.includes('Relação de vendas')
                        );
                        if (span) {
                            const a = span.closest('a');
                            if (a) {
                                a.click();
                                return true;
                            }
                        }
                        return false;
                    }""")

                    if not clicked_js:
                        sub_relacao = page.locator("span.ui-menuitem-text:has-text('Relação de vendas')").first
                        if sub_relacao.is_visible(timeout=2000):
                            sub_relacao.click(force=True)

                    print("[SCRAPER] [2/4] Clique no item 'Relação de vendas' efetuado! Aguardando interface...")

                # 3. Captura do Token JWT na transição 'iniciojsf' e Extração Direta via API
                print("[SCRAPER] [3/4] Aguardando token de sessão pós-redirecionamento...")
                access_token = None
                for step_wait in range(30):
                    curr_url = page.url
                    if "token=" in curr_url:
                        try:
                            import urllib.parse
                            parsed_qs = urllib.parse.parse_qs(urllib.parse.urlparse(curr_url).query)
                            access_token = parsed_qs.get("token", [None])[0]
                            if access_token:
                                print("[SCRAPER] [3/4] Token JWT capturado da URL com sucesso!")
                                break
                        except Exception:
                            pass
                    if "app.phibo.com.br" in curr_url:
                        try:
                            access_token = page.evaluate("() => localStorage.getItem('token') || sessionStorage.getItem('token')")
                            if access_token:
                                print("[SCRAPER] [3/4] Token JWT capturado do Storage com sucesso!")
                                break
                        except Exception:
                            pass
                    page.wait_for_timeout(500)

                if access_token:
                    csv_api_path = self._extract_vendas_via_api(
                        access_token=access_token,
                        is_mes_atual=is_mes_atual,
                        is_mes_anterior=is_mes_anterior,
                        target_year=target_year,
                        target_month=target_month,
                        data_inicio=data_inicio,
                        data_fim=data_fim,
                        proxy_dict=proxy_dict,
                    )
                    if csv_api_path and os.path.exists(csv_api_path):
                        return csv_api_path

                # Fallback UI tradicional caso a extração direta via API não retorne
                for sec in range(15):
                    if "relacao-vendas" in page.url:
                        break
                    if "iniciojsf" in page.url and ("token=" in page.url or "rota=" in page.url):
                        if sec >= 3:
                            print(f"[SCRAPER] [3/4] Tela intermediária 'iniciojsf' detectada ({sec}s). Aplicando credenciais e navegando diretamente...")
                            try:
                                page.evaluate("""() => {
                                    const u = new URL(window.location.href);
                                    const token = u.searchParams.get('token');
                                    const refresh = u.searchParams.get('refresh');
                                    if (token) {
                                        localStorage.setItem('token', token);
                                        localStorage.setItem('origem', 'jsf');
                                        sessionStorage.setItem('token', token);
                                        sessionStorage.setItem('origem', 'jsf');
                                        if (refresh) {
                                            localStorage.setItem('refreshToken', refresh);
                                            sessionStorage.setItem('refreshToken', refresh);
                                        }
                                    }
                                }""")
                                page.wait_for_timeout(500)
                                page.goto("https://app.phibo.com.br/vendas/relacao-vendas", wait_until="domcontentloaded", timeout=30000)
                                break
                            except Exception as e_tok:
                                print(f"[SCRAPER] [3/4] Aviso na transição direta: {e_tok}")
                    page.wait_for_timeout(1000)

                print("[SCRAPER] [3/4] Aguardando aba 'Mês da Venda'...")
                aba_mes = page.locator("p-tab:has-text('Mês da Venda'), [role='tab']:has-text('Mês da Venda'), span:has-text('Mês da Venda')").first
                aba_mes.wait_for(state="visible", timeout=60000)
                print(f"[SCRAPER] [3/4] Aba 'Mês da Venda' carregada com sucesso! URL atual: {page.url}")

                aba_mes.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                time.sleep(2)

                # Função auxiliar para formatar DD/MM/AAAA
                def format_br_date(d_str: str) -> str:
                    s = str(d_str).strip()
                    if "-" in s:
                        p = s.split("-")
                        if len(p) == 3:
                            return f"{p[2].zfill(2)}/{p[1].zfill(2)}/{p[0]}"
                    return s

                # Caso 1: Período customizado com data_inicio e data_fim
                if data_inicio and data_fim:
                    dt_ini_str = format_br_date(data_inicio)
                    dt_fim_str = format_br_date(data_fim)
                    print(f"[SCRAPER] [3/4] Selecionando 'Outro período' ({dt_ini_str} até {dt_fim_str})...")

                    dropdown = page.locator("p-select[placeholder='Período'], .p-select, .p-dropdown").first
                    dropdown.click()
                    time.sleep(1)
                    page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text="Outro período").first.click()
                    time.sleep(1.5)

                    inp_ini = page.locator("input[placeholder='Data início']").first
                    inp_fim = page.locator("input[placeholder='Data fim']").first

                    inp_ini.click()
                    inp_ini.fill("")
                    inp_ini.press_sequentially(dt_ini_str, delay=30)
                    inp_ini.press("Tab")
                    time.sleep(0.5)

                    inp_fim.click()
                    inp_fim.fill("")
                    inp_fim.press_sequentially(dt_fim_str, delay=30)
                    inp_fim.press("Tab")
                    time.sleep(0.5)

                    print(f"[SCRAPER] [3/4] Datas preenchidas: {inp_ini.input_value()} até {inp_fim.input_value()}. Clicando em Pesquisar...")
                    btn_pesquisar = page.locator("button:has-text('Pesquisar')").first
                    btn_pesquisar.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)
                    print("[SCRAPER] [3/4] Filtro de período aplicado com sucesso!")

                # Caso 2: Mês anterior
                elif is_mes_anterior:
                    print(f"[SCRAPER] [3/4] Selecionando 'Mês anterior' ({target_month:02d}/{target_year})...")
                    dropdown = page.locator("p-select[placeholder='Período'], .p-select, .p-dropdown").first
                    dropdown.click()
                    time.sleep(1)
                    opcao_anterior = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text="Mês anterior").first
                    if not opcao_anterior.is_visible():
                        opcao_anterior = page.get_by_text("Mês anterior", exact=False).first
                    opcao_anterior.click()
                    time.sleep(1)

                    btn_pesquisar = page.locator("button:has-text('Pesquisar')").first
                    if btn_pesquisar.is_visible():
                        btn_pesquisar.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)
                    print("[SCRAPER] [3/4] Mês anterior selecionado com sucesso!")

                # Caso 3: Mês retroativo específico (Outro mês)
                elif not is_mes_atual:
                    print(f"[SCRAPER] [3/4] Período solicitado ({target_month:02d}/{target_year}) é mês retroativo. Selecionando no dropdown...")
                    dropdown = page.locator("p-select[placeholder='Período'], .p-select, .p-dropdown").first
                    dropdown.click()
                    time.sleep(1)
                    page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text="Outro mês").first.click()
                    time.sleep(1.5)

                    # Seleciona Ano se diferente do atual
                    if target_year != agora.year:
                        d_ano = page.locator("p-select[inputid='mesAnoInput'], p-select[placeholder='Ano']").first
                        if d_ano.is_visible():
                            d_ano.click()
                            time.sleep(1)
                            opt_ano = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text=str(target_year)).first
                            if opt_ano.is_visible():
                                opt_ano.click()
                                time.sleep(1)

                    # Seleciona Mês
                    meses_nomes = [
                        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
                    ]
                    nome_mes = meses_nomes[target_month] if 1 <= target_month <= 12 else str(target_month)
                    d_mes = page.locator("p-select[placeholder='Mês']").first
                    if d_mes.is_visible():
                        d_mes.click()
                        time.sleep(1)
                        opt_mes = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text=nome_mes).first
                        if not opt_mes.is_visible():
                            opt_mes = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text=f"{target_month:02d}").first
                        opt_mes.click()
                        time.sleep(1)

                    btn_pesquisar = page.locator("button:has-text('Pesquisar')").first
                    if btn_pesquisar.is_visible():
                        btn_pesquisar.click()
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(2)
                    print(f"[SCRAPER] [3/4] 'Outro mês' ({target_month:02d}/{target_year}) selecionado e aplicado com sucesso!")

                # 4. Localização e clique no botão Exportar
                print("[SCRAPER] [4/4] Localizando botão 'Exportar'...")
                btn_exportar = page.locator("button:has-text('Exportar')").first
                btn_exportar.scroll_into_view_if_needed()
                btn_exportar.wait_for(state="visible", timeout=15000)

                print("[SCRAPER] [4/4] Clicando em Exportar e aguardando download...")
                try:
                    with page.expect_download(timeout=12000) as download_info:
                        btn_exportar.click()
                        time.sleep(1.5)
                        # Checagem imediata: se estiver fora da janela, detecta o pop-up/toast
                        self.check_modal_bloqueio(page)

                    download = download_info.value
                    nome_arquivo = download.suggested_filename or f"relacaoVendasMes_{int(time.time())}.csv"
                    destino = os.path.join(self.download_dir, nome_arquivo)
                    download.save_as(destino)
                    print(f"[SCRAPER] Download concluído com sucesso: {destino}")

                    return destino
                except PlaywrightTimeoutError:
                    self.check_modal_bloqueio(page)
                    raise

            except Exception as e:
                try:
                    screenshot_path = os.path.join(self.download_dir, "erro_scraper.png")
                    page.screenshot(path=screenshot_path)
                    print(f"[SCRAPER] Screenshot de erro salvo em: {screenshot_path}")
                    print(f"[SCRAPER] URL no momento da falha: {page.url}")
                    # Extrai textos de possíveis modais de erro na tela
                    modais = page.locator(".p-dialog, [role='dialog'], p-confirmdialog, .p-toast, .swal2-modal, [class*='dialog'], [class*='modal']").all()
                    for m in modais:
                        try:
                            if m.is_visible():
                                txt = m.inner_text().strip().replace('\n', ' ')
                                if txt:
                                    print(f"[SCRAPER] [MODAL NA TELA] {txt}")
                        except Exception:
                            pass
                except Exception:
                    pass
                raise e
            finally:
                context.close()
                browser.close()
