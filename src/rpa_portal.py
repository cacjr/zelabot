"""
TEMA: Automacao web com Selenium (o "robo" de RPA propriamente dito)

Faz o que um servidor faria a mao no sistema da prefeitura:
abrir o navegador -> fazer login -> abrir o formulario -> preencher -> registrar
-> copiar o numero do protocolo.

Cuidados de RPA:
  - esperas EXPLICITAS (WebDriverWait) em vez de time.sleep fixo;
  - timeout de carregamento de pagina;
  - retry com espera quando o portal da erro;
  - print da tela quando algo falha (ajuda a depurar);
  - usuario e senha vem do .env, nunca do codigo;
  - o navegador e sempre fechado no final, mesmo com erro (context manager).
"""
from datetime import datetime

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from src.config import (CHROMEDRIVER_PATH, NAVEGADOR, NAVEGADOR_VISIVEL, PASTA_SAIDA,
                        PORTAL_SENHA, PORTAL_URL, PORTAL_USUARIO, TIMEOUT_SEGUNDOS)
from src.logs import obter_logger
from src.resiliencia import com_retry

log = obter_logger("rpa_portal")
PASTA_PRINTS = PASTA_SAIDA / "prints"


class PortalIndisponivel(Exception):
    pass


class ErroNoPortal(Exception):
    """O portal respondeu, mas com erro (ex.: 503)."""


class CredenciaisInvalidas(Exception):
    pass


@com_retry(excecoes=(requests.RequestException,))
def _checar_saude():
    requests.get(f"{PORTAL_URL}/saude", timeout=TIMEOUT_SEGUNDOS).raise_for_status()


def portal_no_ar() -> bool:
    try:
        _checar_saude()
        return True
    except requests.RequestException:
        return False


class RoboPortal:
    def __init__(self):
        if not PORTAL_USUARIO or not PORTAL_SENHA:
            raise CredenciaisInvalidas(
                "PORTAL_USUARIO/PORTAL_SENHA nao configurados. Copie o .env.example para .env")
        self.driver = None
        self.primeiro_print_feito = False

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *erro):
        self.fechar()
        return False  # nao engole excecoes

    @staticmethod
    def _criar_driver(nome):
        opcoes = webdriver.ChromeOptions() if nome == "chrome" else webdriver.EdgeOptions()
        if not NAVEGADOR_VISIVEL:
            opcoes.add_argument("--headless=new")
        opcoes.add_argument("--window-size=1100,900")
        if nome == "chrome":
            if CHROMEDRIVER_PATH:
                return webdriver.Chrome(options=opcoes, service=Service(CHROMEDRIVER_PATH))
            return webdriver.Chrome(options=opcoes)  # Selenium Manager acha o driver sozinho
        return webdriver.Edge(options=opcoes)

    def abrir(self):
        # "auto": tenta o Chrome e, se nao abrir, o Edge (que vem em todo Windows)
        ordem = ["chrome", "edge"] if NAVEGADOR == "auto" else [NAVEGADOR]
        falhas = []
        for nome in ordem:
            try:
                self.driver = self._criar_driver(nome)
                log.info("Navegador: %s", nome)
                break
            except WebDriverException as erro:
                falhas.append(f"{nome}: {(erro.msg or str(erro)).splitlines()[0][:90]}")
                log.warning("Nao consegui abrir o %s. %s", nome,
                            "Tentando o proximo navegador." if nome != ordem[-1] else "")
        if not self.driver:
            raise PortalIndisponivel("nenhum navegador abriu (" + " | ".join(falhas) + "). "
                                     "Instale o Chrome ou o Edge, ou defina CHROMEDRIVER_PATH no .env")
        self.driver.set_page_load_timeout(TIMEOUT_SEGUNDOS * 2)
        self.espera = WebDriverWait(self.driver, TIMEOUT_SEGUNDOS)
        self._login()

    def _login(self):
        self.driver.get(PORTAL_URL + "/")
        self.espera.until(EC.presence_of_element_located((By.ID, "usuario"))).send_keys(PORTAL_USUARIO)
        self.driver.find_element(By.ID, "senha").send_keys(PORTAL_SENHA)
        self.driver.find_element(By.ID, "entrar").click()
        self.espera.until(EC.any_of(EC.presence_of_element_located((By.ID, "registrar")),
                                    EC.presence_of_element_located((By.ID, "erro"))))
        if self.driver.find_elements(By.ID, "erro"):
            raise CredenciaisInvalidas("o portal recusou usuario/senha")
        log.info("Login no portal feito com sucesso")

    @com_retry(excecoes=(TimeoutException, ErroNoPortal, WebDriverException))
    def registrar(self, sol: dict) -> str:
        d = self.driver
        d.get(PORTAL_URL + "/nova")
        self.espera.until(EC.presence_of_element_located((By.ID, "registrar")))
        d.find_element(By.ID, "id_externo").send_keys(sol["id_solicitacao"])
        Select(d.find_element(By.ID, "categoria")).select_by_value(sol["categoria"])
        d.find_element(By.ID, "bairro").send_keys(sol["bairro"])
        d.find_element(By.ID, "endereco").send_keys(sol["endereco"])
        d.find_element(By.ID, "descricao").send_keys(sol["descricao"])
        Select(d.find_element(By.ID, "prioridade")).select_by_visible_text(sol["prioridade"])
        d.find_element(By.ID, "orgao").send_keys(sol["orgao_responsavel"])
        if not self.primeiro_print_feito:
            self.print_tela("formulario_preenchido")
        d.find_element(By.ID, "registrar").click()

        self.espera.until(EC.any_of(EC.presence_of_element_located((By.ID, "protocolo")),
                                    EC.presence_of_element_located((By.ID, "erro"))))
        erros = d.find_elements(By.ID, "erro")
        if erros:
            raise ErroNoPortal(erros[0].text)
        protocolo = d.find_element(By.ID, "protocolo").text.strip()
        if not self.primeiro_print_feito:
            self.print_tela("protocolo_gerado")
            self.primeiro_print_feito = True
        return protocolo

    def print_tela(self, nome):
        try:
            PASTA_PRINTS.mkdir(parents=True, exist_ok=True)
            caminho = PASTA_PRINTS / f"{datetime.now():%Y%m%d_%H%M%S}_{nome}.png"
            self.driver.save_screenshot(str(caminho))
            return caminho
        except WebDriverException:
            return None

    def fechar(self):
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
            self.driver = None
