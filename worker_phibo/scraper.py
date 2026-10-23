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
        try:
            page.keyboard.press("Escape")
            time.sleep(0.2)
        except Exception:
            pass

        # Dispara via JS a limpeza de modais de marketing (formMarketing) e remoção de overlays bloqueadores
        try:
            page.evaluate("""() => {
                // 1. Remove seções e overlays cinzas bloqueadoras de clique
                document.querySelectorAll('section, div.absolute, .ui-widget-overlay, .ui-dialog-mask, .p-dialog-mask').forEach(el => {
                    try { el.remove(); } catch(e) {}
                });

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

    def run_download_vendas(self, email: str, senha: str, ano: int = None, mes: int = None) -> str:
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

        print(f"[SCRAPER] Iniciando automação Playwright para usuário: {email} (Período: {target_month:02d}/{target_year}, Headless: {self.headless})...")
        
        with sync_playwright() as p:
            # Tenta utilizar o Google Chrome nativo do sistema ou Edge
            try:
                browser = p.chromium.launch(
                    headless=self.headless,
                    channel="chrome",
                    args=["--start-maximized", "--no-sandbox", "--disable-setuid-sandbox"]
                )
            except Exception:
                try:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        channel="msedge",
                        args=["--start-maximized", "--no-sandbox", "--disable-setuid-sandbox"]
                    )
                except Exception:
                    browser = p.chromium.launch(
                        headless=self.headless,
                        args=["--start-maximized", "--no-sandbox", "--disable-setuid-sandbox"]
                    )

            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True
            )
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

                for tentativa in range(3):
                    self.fechar_modais_e_avisos(page)

                    if "relacao-vendas" in page.url and page.locator("p-tab:has-text('Mês da Venda'), [role='tab']:has-text('Mês da Venda')").first.is_visible():
                        print("[SCRAPER] [2/4] Tela 'Relação de vendas' detectada com sucesso!")
                        break

                    print(f"[SCRAPER] [2/4] Tentativa {tentativa + 1}/3 de abrir menu 'Vendas' -> 'Relação de vendas'...")

                    # 1. Se estiver no sistema legado sistema.phibo.com.br:
                    if "sistema.phibo.com.br" in page.url:
                        try:
                            # Hover no menu Vendas
                            menu_vendas = page.locator("li[role='menuitem']:has-text('Vendas'), a.ui-submenu-link:has-text('Vendas'), a:has-text('Vendas')").filter(has_text="Vendas").first
                            if menu_vendas.is_visible(timeout=3000):
                                menu_vendas.hover()
                                time.sleep(0.5)

                            # Dispara o clique no item de submenu via JS (evita fechamento acidental de dropdown)
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
                        except Exception as e_click:
                            print(f"[SCRAPER] [2/4] Aviso clique no menu: {e_click}")

                    # 2. Aguarda a transição natural: sistema.phibo -> iniciojsf?token=... -> /vendas/relacao-vendas
                    try:
                        page.wait_for_url("**/relacao-vendas**", timeout=30000)
                        print("[SCRAPER] [2/4] URL 'relacao-vendas' alcançada com sucesso!")
                        break
                    except Exception:
                        if "iniciojsf" in page.url or "token=" in page.url:
                            print("[SCRAPER] [2/4] Processamento do token em andamento na tela intermediária, aguardando...")
                            try:
                                page.wait_for_url("**/relacao-vendas**", timeout=20000)
                                break
                            except Exception:
                                pass
                        time.sleep(2)

                # 3. Aba 'Mês da Venda'
                print("[SCRAPER] [3/4] Clicando na aba 'Mês da Venda'...")
                self.fechar_modais_e_avisos(page)

                aba_mes = page.locator("p-tab:has-text('Mês da Venda'), [role='tab']:has-text('Mês da Venda')").first
                try:
                    aba_mes.wait_for(state="visible", timeout=30000)
                except Exception:
                    aba_mes = page.get_by_text("Mês da Venda", exact=False).first
                    aba_mes.wait_for(state="visible", timeout=15000)

                aba_mes.click()
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                time.sleep(2)

                if is_mes_anterior:
                    print(f"[SCRAPER] [3/4] Selecionando 'Mês anterior' ({target_month:02d}/{target_year})...")
                    dropdown = page.locator("p-select, .p-select, .p-dropdown").first
                    dropdown.click()
                    time.sleep(1)
                    opcao_anterior = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text="Mês anterior").first
                    if not opcao_anterior.is_visible():
                        opcao_anterior = page.get_by_text("Mês anterior", exact=False).first
                    opcao_anterior.click()
                    page.wait_for_load_state("networkidle", timeout=30000)
                    time.sleep(2)
                    print("[SCRAPER] [3/4] Mês anterior selecionado com sucesso!")
                elif not is_mes_atual:
                    print(f"[SCRAPER] [3/4] Período solicitado ({target_month:02d}/{target_year}) é retroativo. Selecionando no dropdown...")
                    dropdown = page.locator("p-select, .p-select, .p-dropdown").first
                    dropdown.click()
                    time.sleep(1)
                    opcao_outro = page.locator(".p-select-option, li[role='option'], .p-dropdown-item").filter(has_text="Outro mês").first
                    if opcao_outro.is_visible():
                        opcao_outro.click()
                        page.wait_for_load_state("networkidle", timeout=30000)
                        time.sleep(2)
                        print("[SCRAPER] [3/4] 'Outro mês' selecionado no dropdown.")

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
