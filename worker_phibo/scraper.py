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
        """Verifica se o modal amarelo de restrição de horário apareceu na tela."""
        try:
            alerta = page.locator("text=Esta funcionalidade está desabilitada").first
            if alerta.is_visible(timeout=3000):
                msg = alerta.inner_text().strip()
                print(f"[SCRAPER] [AVISO PHIBO] {msg}")
                raise PhiboWindowRestrictionError(
                    f"PHIBO bloqueou o download por estar fora da janela permitida (08:00-10:10 / a partir das 19:10). Mensagem: {msg}"
                )
        except PlaywrightTimeoutError:
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
                    page.locator("a:has-text('Vendas'), p-menubar, nav").first.wait_for(state="visible", timeout=45000)
                    print("[SCRAPER] [1/4] Login realizado com sucesso!")
                except Exception as e:
                    print(f"[SCRAPER] [AVISO] Timeout aguardando navbar pós-login: {e}")

                # 2. Navegação até Relação de vendas
                print("[SCRAPER] [2/4] Acessando tela 'Relação de vendas'...")

                for tentativa in range(4):
                    if page.get_by_text("Mês da Venda", exact=False).first.is_visible():
                        print("[SCRAPER] [2/4] Tela 'Relação de vendas' detectada com sucesso!")
                        break

                    print(f"[SCRAPER] [2/4] Tentativa {tentativa + 1}/4 de abrir menu 'Vendas' -> 'Relação de vendas'...")

                    # Fecha possíveis pop-ups/modais de aviso
                    try:
                        dialog_close = page.locator(".p-dialog-header-close, button:has-text('Fechar')").first
                        if dialog_close.is_visible(timeout=1000):
                            dialog_close.click()
                            time.sleep(1)
                    except Exception:
                        pass

                    # Dispara o clique no link de 'Relação de vendas' (aciona PrimeFaces AJAX)
                    clicked = page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('a.ui-menuitem-link, a'));
                        const link = links.find(el => el.textContent && el.textContent.includes('Relação de vendas'));
                        if (link) {
                            link.click();
                            return true;
                        }
                        return false;
                    }""")
                    print(f"[SCRAPER] [2/4] Clique no menu disparado via JS: {clicked}")

                    # Aguarda redirecionamento para app.phibo.com.br/vendas/relacao-vendas
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    time.sleep(3)

                # 3. Aba 'Mês da Venda'
                print("[SCRAPER] [3/4] Clicando na aba 'Mês da Venda'...")
                aba_mes = page.get_by_text("Mês da Venda", exact=False).first
                aba_mes.wait_for(state="visible", timeout=20000)
                aba_mes.click()
                page.wait_for_load_state("networkidle", timeout=30000)
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
                with page.expect_download(timeout=30000) as download_info:
                    btn_exportar.click()
                    
                    # Checagem imediata: se estiver fora da janela, detecta o pop-up
                    self.check_modal_bloqueio(page)

                download = download_info.value
                nome_arquivo = download.suggested_filename or f"relacaoVendasMes_{int(time.time())}.csv"
                destino = os.path.join(self.download_dir, nome_arquivo)
                download.save_as(destino)
                print(f"[SCRAPER] Download concluído com sucesso: {destino}")

                return destino

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
