from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin
import mimetypes
import os
import re
import time
import requests
import unicodedata


def load_config():
    env = Path(__file__).parent / ".env"

    print("[DEBUG] Caminho do .env:", env)
    print("[DEBUG] Existe .env?", env.exists())

    if env.exists():
        load_dotenv(env)
    else:
        raise FileNotFoundError(f"Arquivo .env não encontrado em: {env}")

    config = {k: os.getenv(k) for k in (
        "APP_URL", "APP_USER", "APP_SENHA",
        "SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_BUCKET"
    )}

    print("\n[DEBUG] Variáveis carregadas:")
    for k, v in config.items():
        if k == "SUPABASE_KEY" and v:
            print(f"{k}: OK -> {v[:20]}...")
        else:
            print(f"{k}: {'OK' if v else 'VAZIO'} -> {v}")

    if not all(config.values()):
        raise ValueError("Variáveis de ambiente não configuradas corretamente.")

    return config


REPORT_PATTERNS = {
    "Relatorio de Vendas": re.compile(r"^Relatorio de Vendas (\d+)\.", re.IGNORECASE),
    "Relatorio de Vendas Vendedor": re.compile(r"^Relatorio de Vendas Vendedor (\d+)\.", re.IGNORECASE),
    "Relatorio de Clientes Novos": re.compile(r"^Relatorio de Clientes Novos (\d+)\.", re.IGNORECASE),
    "Relatorio de Custo Estoque": re.compile(r"^Relatorio de Custo Estoque (\d+)\.", re.IGNORECASE),
}


def normalize_name(name: str):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", re.sub(r'[<>:"/\\|?*]', "_", name)).strip()


def list_files(session, config, folder):
    print(f"[SUPABASE] Listando arquivos da pasta: {folder}")

    r = session.post(
        f'{config["SUPABASE_URL"]}/storage/v1/object/list/{config["SUPABASE_BUCKET"]}',
        headers={"Content-Type": "application/json"},
        json={"prefix": folder},
        timeout=30
    )

    print(f"[SUPABASE] Status listagem: {r.status_code}")
    print(f"[SUPABASE] Resposta listagem: {r.text}")

    if r.status_code != 200:
        raise RuntimeError(f"Erro ao listar arquivos no Supabase: {r.status_code} | {r.text}")

    return [i["name"] for i in r.json() if i.get("name")]


def build_filename(session, config, folder, base, original):
    ext = Path(original).suffix or ".xlsx"

    nums = [
        int(m.group(1))
        for f in list_files(session, config, folder)
        if (m := REPORT_PATTERNS[base].match(normalize_name(f)))
    ]

    filename = f"{base} {max(nums, default=0) + 1}{ext}"
    print(f"[ARQUIVO] Nome gerado: {filename}")
    return filename


def upload_bytes(session, config, data, name, folder, retries=3):
    name = normalize_name(name)
    path = f"{folder}/{name}"
    url = f'{config["SUPABASE_URL"]}/storage/v1/object/{config["SUPABASE_BUCKET"]}/{path}'
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"

    print("\n[UPLOAD] Iniciando upload")
    print(f"[UPLOAD] Bucket: {config['SUPABASE_BUCKET']}")
    print(f"[UPLOAD] Caminho: {path}")
    print(f"[UPLOAD] Tamanho arquivo: {len(data)} bytes")
    print(f"[UPLOAD] Mime: {mime}")

    last_response = None

    for attempt in range(1, retries + 1):
        print(f"[UPLOAD] Tentativa {attempt}/{retries}")

        last_response = session.post(
            url,
            headers={
                "Content-Type": mime,
                "x-upsert": "true"
            },
            data=data,
            timeout=60
        )

        print(f"[UPLOAD] Status: {last_response.status_code}")
        print(f"[UPLOAD] Resposta: {last_response.text}")

        if last_response.status_code in (200, 201):
            print("[UPLOAD] Arquivo enviado com sucesso")
            return

        if attempt < retries:
            time.sleep(2 ** (attempt - 1))

    raise RuntimeError(f"Erro no upload: {last_response.status_code} | {last_response.text}")


def safe_click(locator):
    last_error = None

    for mode in ("normal", "force", "js"):
        try:
            locator.wait_for(state="attached", timeout=10000)

            try:
                locator.scroll_into_view_if_needed()
            except Exception:
                pass

            if mode == "normal":
                locator.click(timeout=10000)
            elif mode == "force":
                locator.click(timeout=10000, force=True)
            else:
                locator.evaluate("el => el.click()")

            return

        except Exception as e:
            last_error = e

    raise RuntimeError(f"Falha no clique: {last_error}")


def wait_until_visible(locator, timeout=5000):
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def first_visible(page, selectors, timeout=30000):
    last_error = None

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state="visible", timeout=timeout)
            return locator
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Nenhum seletor encontrado. Último erro: {last_error}")


def ensure_menu(menu, submenu):
    try:
        if submenu.is_visible():
            return
    except Exception:
        pass

    safe_click(menu)

    if wait_until_visible(submenu, 4000):
        return

    safe_click(menu)

    if wait_until_visible(submenu, 5000):
        return

    raise RuntimeError("Não foi possível abrir o submenu.")


def click_with_scroll(page, locator, max_attempts=20, wheel_px=1200, wait_ms=800):
    last_error = None

    for _ in range(max_attempts):
        try:
            safe_click(locator)
            return
        except Exception as e:
            last_error = e
            page.mouse.wheel(0, wheel_px)
            page.wait_for_timeout(wait_ms)

    raise RuntimeError(f"Não foi possível clicar após rolagem: {last_error}")


def safe_run(name, fn):
    print("\n" + "=" * 70)
    print(f"[INICIANDO] {name}")
    print("=" * 70)

    try:
        fn()
        print(f"[OK] {name} concluído e enviado para o Supabase")
        return True

    except Exception as e:
        print(f"[ERRO] {name}")
        print(f"[DETALHE] {e}")
        return False


def login(page, config):
    print("[LOGIN] Acessando sistema")

    page.goto(config["APP_URL"], wait_until="domcontentloaded", timeout=60000)
    page.fill("#j_username", config["APP_USER"])
    page.fill("#j_password", config["APP_SENHA"])
    safe_click(page.locator("#logar"))

    page.locator('xpath=//*[@id="menuform:um_venda"]/a').wait_for(
        state="visible",
        timeout=60000
    )

    print("[LOGIN] Login realizado com sucesso")


def voltar_inicio(page, config):
    print("[NAVEGAÇÃO] Voltando para início")

    page.goto(config["APP_URL"], wait_until="domcontentloaded", timeout=60000)

    try:
        page.locator('xpath=//*[@id="menuform:um_venda"]/a').wait_for(
            state="visible",
            timeout=10000
        )
        return
    except Exception:
        login(page, config)


def open_sales_menu(page):
    print("[MENU] Abrindo menu de vendas")

    page.goto(page.url, wait_until="domcontentloaded", timeout=60000)

    venda = page.locator('xpath=//*[@id="menuform:um_venda"]/a')
    venda.wait_for(state="visible", timeout=30000)
    safe_click(venda)

    relatorios = page.locator('xpath=//*[@id="menuform:um_reltorios"]/a')
    relatorios.wait_for(state="visible", timeout=30000)
    safe_click(relatorios)


def capture_pdf_old_logic(page, context, button_locator, original_name):
    print("[PDF] Tentando capturar PDF")

    pdf_bytes = None
    pdf_url = None
    popup_page = None

    def on_response(response):
        nonlocal pdf_bytes, pdf_url

        try:
            content_type = (response.headers.get("content-type") or "").lower()

            if "application/pdf" in content_type:
                body = response.body()

                if body and body[:4] == b"%PDF":
                    pdf_bytes = body
                    pdf_url = response.url
                    print(f"[PDF] PDF capturado via response: {pdf_url}")

        except Exception:
            pass

    context.on("response", on_response)

    try:
        popup_opened = False

        try:
            with page.expect_popup(timeout=10000) as popup_info:
                safe_click(button_locator)

            popup_page = popup_info.value
            popup_opened = True
            print("[PDF] Popup aberto")

        except Exception:
            popup_page = None
            print("[PDF] Nenhum popup detectado")

        if popup_opened and popup_page:
            try:
                popup_page.wait_for_load_state("domcontentloaded", timeout=20000)
                popup_page.wait_for_timeout(3000)
                print(f"[PDF] URL popup: {popup_page.url}")
            except Exception:
                pass

            if pdf_bytes is None:
                try:
                    response = popup_page.goto(
                        popup_page.url,
                        wait_until="networkidle",
                        timeout=15000
                    )

                    if response:
                        content_type = (response.headers.get("content-type") or "").lower()
                        body = response.body()

                        if "application/pdf" in content_type and body[:4] == b"%PDF":
                            pdf_bytes = body
                            pdf_url = response.url

                except Exception:
                    pass

            if pdf_bytes is None:
                urls = []
                selectors = [
                    ("embed", "src"),
                    ("iframe", "src"),
                    ("object", "data"),
                    ("a", "href")
                ]

                for selector, attr in selectors:
                    try:
                        loc = popup_page.locator(selector)

                        for i in range(loc.count()):
                            value = loc.nth(i).get_attribute(attr)

                            if value:
                                urls.append(urljoin(popup_page.url, value))

                    except Exception:
                        pass

                for url in dict.fromkeys(urls):
                    try:
                        response = popup_page.goto(
                            url,
                            wait_until="networkidle",
                            timeout=15000
                        )

                        if response:
                            content_type = (response.headers.get("content-type") or "").lower()
                            body = response.body()

                            if "application/pdf" in content_type and body[:4] == b"%PDF":
                                pdf_bytes = body
                                pdf_url = response.url
                                break

                    except Exception:
                        pass

        if pdf_bytes is None:
            try:
                if popup_page and not popup_page.is_closed():
                    popup_page.close()
            except Exception:
                pass

            try:
                print("[PDF] Tentando capturar via download")

                with page.expect_download(timeout=10000) as download_info:
                    safe_click(button_locator)

                download = download_info.value

                if failure := download.failure():
                    raise RuntimeError(failure)

                temp_path = download.path()

                if not temp_path:
                    raise RuntimeError("Arquivo temporário não encontrado")

                with open(temp_path, "rb") as f:
                    pdf_bytes = f.read()

                if not pdf_bytes:
                    raise RuntimeError("Arquivo PDF vazio")

                print(f"[PDF] PDF baixado com sucesso: {len(pdf_bytes)} bytes")

                return pdf_bytes, download.suggested_filename or original_name

            except Exception as e:
                raise RuntimeError(f"PDF não retornado via popup/response/download. Detalhe: {e}")

        print(f"[PDF] PDF capturado com sucesso: {len(pdf_bytes)} bytes")

        return pdf_bytes, Path(pdf_url.split("?")[0]).name if pdf_url else original_name

    finally:
        try:
            context.remove_listener("response", on_response)
        except Exception:
            pass

        try:
            if popup_page and not popup_page.is_closed():
                popup_page.close()
        except Exception:
            pass


def relatorio_vendas(page, session, config, folder):
    open_sales_menu(page)

    safe_click(page.locator('xpath=//*[@id="menuform:um_rfrm_rel_venda_detalhada_novo"]/a'))

    campo_data = first_visible(page, [
        'xpath=//form[contains(@id,"frmVenda")]//input[contains(@id,"_input")]',
        "#frmVenda\\:j_idt159_input"
    ])

    campo_data.fill(datetime.now().strftime("%d/%m/%Y"))
    campo_data.press("Tab")

    page.wait_for_timeout(1500)

    print("[RELATÓRIO] Baixando Relatório de Vendas - Exportar Xlsx")

    # Botão principal do SplitButton: Exportar Xlsx.
    # Não usar o botão da setinha, que normalmente termina com "_button".
    botao_exportar_xlsx = first_visible(page, [
        '#frmVenda\\:j_idt171',
        'xpath=//form[contains(@id,"frmVenda")]//button[not(contains(@id,"_button")) and .//span[normalize-space()="Exportar Xlsx"]]',
        'xpath=//form[contains(@id,"frmVenda")]//button[not(contains(@class,"ui-splitbutton-menubutton")) and .//span[contains(normalize-space(.),"Exportar Xlsx")]]',
        'xpath=//form[contains(@id,"frmVenda")]//*[normalize-space()="Exportar Xlsx"]/ancestor::button[not(contains(@id,"_button"))][1]'
    ])

    botao_exportar_xlsx.wait_for(state="visible", timeout=30000)

    try:
        botao_exportar_xlsx.scroll_into_view_if_needed()
    except Exception:
        pass

    page.wait_for_timeout(1000)

    with page.expect_download(timeout=60000) as d:
        botao_exportar_xlsx.click(timeout=30000, force=True)

    file = d.value

    if failure := file.failure():
        raise RuntimeError(failure)

    temp_path = file.path()

    if not temp_path:
        raise RuntimeError("Arquivo não encontrado")

    with open(temp_path, "rb") as f:
        data = f.read()

    if not data:
        raise RuntimeError("Arquivo vazio")

    print(f"[DOWNLOAD] Relatório de Vendas baixado: {len(data)} bytes")

    name = build_filename(
        session,
        config,
        folder,
        "Relatorio de Vendas",
        file.suggested_filename or "Relatorio Venda.xlsx"
    )

    upload_bytes(session, config, data, name, folder)


def relatorio_vendedor(page, context, session, config, folder):
    open_sales_menu(page)

    safe_click(page.locator('xpath=//*[@id="menuform:um_reltorios9"]/a'))

    campo_data = first_visible(page, [
        'xpath=//form[contains(@id,"frmTitulo")]//input[contains(@id,"_input")]',
        'xpath=//*[@id="frmTitulo:j_idt133_input"]'
    ])

    campo_data.fill(datetime.now().strftime("%d/%m/%Y"))

    pdf_button = first_visible(page, [
        'xpath=//form[contains(@id,"frmTitulo")]//button[contains(.,"Imprimir")]',
        'xpath=//form[contains(@id,"frmTitulo")]//button[.//span[contains(normalize-space(.),"Imprimir")]]',
        'xpath=//*[@id="frmTitulo:j_idt142"]'
    ], timeout=15000)

    pdf, original = capture_pdf_old_logic(
        page,
        context,
        pdf_button,
        "Relatorio Vendas por Vendedor.pdf"
    )

    name = build_filename(
        session,
        config,
        folder,
        "Relatorio de Vendas Vendedor",
        original if original.endswith(".pdf") else "relatorio.pdf"
    )

    upload_bytes(session, config, pdf, name, folder)


def relatorio_clientes(page, context, session, config, folder):
    voltar_inicio(page, config)

    safe_click(page.locator('xpath=//*[@id="menuform:themes"]/a/span[1]'))

    base = page.locator('xpath=//*[@id="menuform:um_reltorios_Base"]/a/span[1]')
    base.wait_for(state="attached", timeout=30000)
    click_with_scroll(page, base)

    cliente = page.locator('xpath=//*[@id="menuform:um_reltorios_cliente_periodo"]/a/span')
    cliente.wait_for(state="visible", timeout=15000)
    safe_click(cliente)

    pdf_button = first_visible(page, [
        'xpath=//form[contains(@id,"frmRelatorio")]//button[contains(.,"Imprimir")]',
        'xpath=//form[contains(@id,"frmRelatorio")]//button[.//span[contains(normalize-space(.),"Imprimir")]]',
        'xpath=//*[@id="frmRelatorio:j_idt130"]',
        'xpath=//*[@id="frmRelatorio:j_idt130"]/span[2]'
    ], timeout=15000)

    pdf, original = capture_pdf_old_logic(
        page,
        context,
        pdf_button,
        "Relatorio Clientes Novos.pdf"
    )

    name = build_filename(
        session,
        config,
        folder,
        "Relatorio de Clientes Novos",
        original if original.endswith(".pdf") else "clientes.pdf"
    )

    upload_bytes(session, config, pdf, name, folder)


def relatorio_estoque(page, session, config, folder):
    voltar_inicio(page, config)

    menu = page.locator('xpath=//*[@id="menuform:themes"]/a')
    base = page.locator('xpath=//*[@id="menuform:um_reltorios_Base"]/a')
    custo = page.locator('xpath=//*[@id="menuform:frm_rel_custo_estoque"]/a')

    menu.wait_for(state="attached", timeout=30000)

    ensure_menu(menu, base)
    page.wait_for_timeout(600)

    ensure_menu(base, custo)
    page.wait_for_timeout(600)

    safe_click(custo)

    button = page.locator('xpath=//*[@id="frmTitulo:j_idt138"]')
    button.wait_for(state="visible", timeout=30000)

    print("[RELATÓRIO] Baixando Relatório de Custo Estoque")

    with page.expect_download(timeout=30000) as d:
        safe_click(button)

    file = d.value

    if failure := file.failure():
        raise RuntimeError(failure)

    temp_path = file.path()

    if not temp_path:
        raise RuntimeError("Arquivo não encontrado")

    with open(temp_path, "rb") as f:
        data = f.read()

    if not data:
        raise RuntimeError("Arquivo vazio")

    print(f"[DOWNLOAD] Relatório de Estoque baixado: {len(data)} bytes")

    name = build_filename(
        session,
        config,
        folder,
        "Relatorio de Custo Estoque",
        file.suggested_filename or "Relatorio Custo Estoque.xlsx"
    )

    upload_bytes(session, config, data, name, folder)


def main():
    config = load_config()
    folder = datetime.now().strftime("%Y-%m-%d")

    print("\n[EXECUÇÃO] Pasta Supabase do dia:", folder)

    session = requests.Session()
    session.headers.update({
        "apikey": config["SUPABASE_KEY"],
        "Authorization": f'Bearer {config["SUPABASE_KEY"]}',
    })

    resultados = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        try:
            login(page, config)

            resultados["Relatorio de Vendas"] = safe_run(
                "Relatorio de Vendas",
                lambda: relatorio_vendas(page, session, config, folder)
            )

            resultados["Relatorio de Vendas Vendedor"] = safe_run(
                "Relatorio de Vendas Vendedor",
                lambda: relatorio_vendedor(page, context, session, config, folder)
            )

            resultados["Relatorio de Clientes Novos"] = safe_run(
                "Relatorio de Clientes Novos",
                lambda: relatorio_clientes(page, context, session, config, folder)
            )

            resultados["Relatorio de Custo Estoque"] = safe_run(
                "Relatorio de Custo Estoque",
                lambda: relatorio_estoque(page, session, config, folder)
            )

            print("\n" + "=" * 70)
            print("[RESUMO FINAL]")
            print("=" * 70)

            for nome, status in resultados.items():
                print(f"{nome}: {'OK' if status else 'ERRO'}")

        finally:
            print("\n[FINALIZANDO] Fechando navegador e sessão")
            context.close()
            browser.close()
            session.close()


if __name__ == "__main__":
    main()
