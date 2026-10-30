import os
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError

PHIBO_LOGIN_URL = "https://sistema.phibo.com.br/"


class PhiboWindowRestrictionError(Exception):
    """Exceção levantada quando o PHIBO exibe o modal de bloqueio de horário."""
    pass


class PhiboScraper:
    def __init__(self, headless: bool = True, download_dir: str = None):
        self.headless = headless
        self.download_dir = download_dir or str(Path(__file__).resolve().parent / "tmp_downloads")
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
        
        with sync_playwright() as p:
            # Argumentos de inicialização do navegador contra detecção e compatíveis com Docker
            launch_args = [
                "--start-maximized",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]

            try:
                browser = p.chromium.launch(
                    headless=self.headless,
                    channel="chrome",
                    args=launch_args
                )
            except Exception:
                try:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        channel="msedge",
                        args=launch_args
                    )
                except Exception:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        args=launch_args
                    )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="pt-BR",
                timezone_id="America/Sao_Paulo",
                accept_downloads=True
            )
            # Mascara flag do webdriver contra bloqueios do WAF/Cloudflare
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            page = context.new_page()

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

                    print("[SCRAPER] [2/4] Clique no item 'Relação de vendas' efetuado! Aguardando transição...")
                    page.wait_for_url("**/relacao-vendas**", timeout=60000)
                    print(f"[SCRAPER] [2/4] URL 'relacao-vendas' alcançada com sucesso! ({page.url})")
                    time.sleep(2)

                # 3. Aba 'Mês da Venda'
                print("[SCRAPER] [3/4] Clicando na aba 'Mês da Venda'...")

                aba_mes = page.locator("p-tab:has-text('Mês da Venda'), [role='tab']:has-text('Mês da Venda'), span:has-text('Mês da Venda')").first
                try:
                    aba_mes.wait_for(state="visible", timeout=30000)
                except Exception:
                    aba_mes = page.get_by_text("Mês da Venda", exact=False).first
                    aba_mes.wait_for(state="visible", timeout=20000)

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
                except Exception:
                    pass
                raise e
            finally:
                context.close()
                browser.close()
