#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# search_linkedin.py
"""
Script para busca e coleta automatizada de vagas no LinkedIn.
Padronizado conforme a arquitetura do projeto linkedin-automacao,
utilizando variáveis de ambiente e arquivos de configuração JSON.
"""

import sys
import os
import json
import logging
import time, datetime
import math
import pandas as pd
import openpyxl  # Necessário para o Pandas ler/escrever .xlsx
import urllib.parse # Para codificar URLs

from dotenv import load_dotenv
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, WebDriverException, TimeoutException


# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# ================= CONFIGURAÇÃO DE LOGGING =================
# Configura o logger para seguir o padrão dos outros scripts
MY_LOG_LEVEL = os.environ.get("MY_LOG_LEVEL", "INFO").upper() # Obtém de .env ou usa INFO
logger = logging.getLogger(__name__)
logger.setLevel(MY_LOG_LEVEL)

# Garante que o handler de stream só seja adicionado uma vez
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ================= FUNÇÕES DE UTILIDADE =================
def log_erro(mensagem):
    """Função padronizada para log de erros, direcionando para stderr."""
    logging.error(mensagem)
    print(f"ERRO: {mensagem}", file=sys.stderr)

def carregar_configuracoes_json(caminho_arquivo):
    """Carrega configurações do arquivo JSON especificado."""
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            configuracoes = json.load(arquivo)
            logger.info(f"Configurações carregadas de: {caminho_arquivo}")
            return configuracoes
    except FileNotFoundError:
        log_erro(f"Arquivo de configuração não encontrado: {caminho_arquivo}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log_erro(f"Erro ao decodificar JSON: {e}")
        sys.exit(1)
    except Exception as e:
        log_erro(f"Erro inesperado ao carregar configurações: {e}")
        sys.exit(1)

# ================= CLASSE PRINCIPAL: EasyApplyLinkedin =================
class EasyApplyLinkedin:

    # =====================================================================
    # CONSTANTES DE SELETORES (Mantidas dentro da classe por enquanto)
    # =====================================================================
    PAGINATION_STATUS_CLASS = "jobs-search-pagination__page-state"
    RESULTS_LIST_TITLE_ID = "results-list__title"
    SCAFFOLD_LAYOUT_LIST_XPATH = "./ancestor::div[contains(@class, 'scaffold-layout__list') and @tabindex='-1']"
    JOB_CARD_OCCLUDABLE_ID_CSS = "li[data-occludable-job-id]"
    JOB_CARD_LINK_CSS = "a.job-card-container__link"
    BUTTON_NEXT_PAGE_ARIA_LABEL = "Ver próxima página"
    JOBS_SEARCH_RESULTS_SUBTITLE_CLASS = 'jobs-search-results-list__subtitle'

    # Seletores para os detalhes da vaga (lado direito)
    JOB_DETAILS_COMPANY_CLASS = "job-details-jobs-unified-top-card__company-name"
    JOB_DETAILS_INSIGHT_CLASS = "job-details-fit-level-preferences"
    JOB_DETAILS_PRIMARY_DESC_CLASS = "job-details-jobs-unified-top-card__primary-description-container"
    JOB_DESCRIPTION_CLASS = "jobs-box__html-content" # Para a descrição da vaga

    # Seletores para botões de aplicação (Easy Apply, Employer site)
    BUTTON_EMPLOYER_SITE_ARIA_LABEL = "Candidatar-se" # Botão que leva para o site do empregador
    BUTTON_EASY_APPLY_CLASS = "jobs-apply-button.artdeco-button.artdeco-button--3.artdeco-button--primary.ember-view" # Botão Easy Apply
    BUTTON_SUBMIT_APPLICATION_ARIA_LABEL = "Enviar candidatura" # Botão final de submissão no modal
    BUTTON_CLOSE_MODAL_ARIA_LABEL = "Fechar" # Botão para fechar modais (tanto de erro quanto de sucesso)
    BUTTON_CONFIRM_DISCARD_CLASS = "artdeco-button.artdeco-button--2.artdeco-button--secondary.ember-view.artdeco-modal__confirm-dialog-btn" # Confirmar descarte no modal
    BUTTON_DISCARD_SUCCESS_MODAL_CLASS = "artdeco-button.artdeco-button--circle.artdeco-button--muted.artdeco-button--2.artdeco-button--tertiary.ember-view.artdeco-modal__dismiss" # Botão de fechar modal de sucesso

    def __init__(self, config_data):
        """Inicializa a classe com as configurações carregadas."""
        # Credenciais do LinkedIn - lidas diretamente do .env
        self.email = os.environ.get('LINKEDIN_EMAIL')
        self.password = os.environ.get('LINKEDIN_PASSWORD')
        
        if not self.email or not self.password:
            log_erro("LINKEDIN_EMAIL e LINKEDIN_PASSWORD devem estar definidos no arquivo .env")
            sys.exit(1)

        # Configurações gerais do scraper a partir do linkedin.json
        self.keyword = config_data.get('keyword', '')
        self.location = config_data.get('location', 'Brasil') 
        self.geo_id = config_data.get('linkedin_search_geo_id', None)
        if not self.geo_id:
            log_erro("linkedin_search_geo_id não configurado no linkedin.json. É obrigatório para a busca.")
            sys.exit(1)

        self.driver_path = config_data.get('driver_path', None) 
        self.output_file = config_data.get('input_file_jobs', 'dados/entrada/job_details.xlsx')
        self.error_backup_file = config_data.get('linkedin_error_backup_file', 'logs/job_details_error_backup.xlsx')
        
        # Novas configurações para controle do scraping
        self.max_jobs_to_scrape = config_data.get('max_jobs_to_scrape', 100)
        self.headless_mode = config_data.get('headless_mode', True)
        self.delay_min = config_data.get('delay_min_seconds', 2)
        self.delay_max = config_data.get('delay_max_seconds', 5)

        # Configurações de filtros (NOVAS CHAVES)
        self.apply_easy_apply_filter = config_data.get('apply_easy_apply_filter', True)
        self.apply_date_filter = config_data.get('apply_date_filter', True)
        self.apply_remote_filter = config_data.get('apply_remote_filter', True)
        self.apply_presencial_filter = config_data.get('apply_presencial_filter', True)
        self.apply_hibrido_filter = config_data.get('apply_hibrido_filter', True)


        # Codifica as palavras-chave para URL
        self.encoded_keyword = urllib.parse.quote_plus(self.keyword)

        self.job_details = []
        self.driver = None
        self.seen_job_ids = set() 
        
        logger.info("EasyApplyLinkedin inicializado com sucesso com as configurações carregadas.")

    def _safe_find_element(self, by, value, timeout=5, wait_type=EC.presence_of_element_located):
        """
        Tenta encontrar um elemento de forma segura, usando WebDriverWait.
        Retorna o elemento se encontrado, None caso contrário.
        """
        try:
            logger.debug(f"Tentando encontrar elemento: {by}={value}")
            return WebDriverWait(self.driver, timeout).until(wait_type((by, value)))
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
            logger.debug(f"Elemento não encontrado ou indisponível após {timeout}s: {by}={value}")
            return None

    def _close_application_modal(self):
        """
        Tenta fechar qualquer modal de aplicação aberta, seja por descarte ou por sucesso.
        """
        logger.info("Tentando fechar modal de aplicação...")
        try:
            # Tenta fechar o modal principal (botão 'Fechar')
            discard_button = self._safe_find_element(By.XPATH, f"//button[contains(@aria-label,'{self.BUTTON_CLOSE_MODAL_ARIA_LABEL}')]", timeout=3)
            if discard_button:
                self.wait.until(EC.element_to_be_clickable(discard_button)).click()
                logger.info("Botão 'Fechar' clicado.")
                # Tenta confirmar o descarte se for um modal de confirmação
                discard_confirm = self._safe_find_element(By.CLASS_NAME, self.BUTTON_CONFIRM_DISCARD_CLASS, timeout=3)
                if discard_confirm:
                    self.wait.until(EC.element_to_be_clickable(discard_confirm)).click()
                    logger.info("Confirmação de descarte clicada.")
                else:
                    logger.debug("Nenhum botão de confirmação de descarte encontrado. Modal deve ter fechado.")
                return True
            else:
                # Tenta fechar o modal de sucesso (botão de fechar modal)
                discard_success_modal = self._safe_find_element(By.CLASS_NAME, self.BUTTON_DISCARD_SUCCESS_MODAL_CLASS, timeout=2)
                if discard_success_modal:
                    self.wait.until(EC.element_to_be_clickable(discard_success_modal)).click()
                    logger.info("Botão de descarte/fechar modal de sucesso clicado.")
                    return True
            logger.info("Nenhum modal de aplicação para fechar encontrado.")
            return False
        except Exception as e:
            logger.warning(f"Erro ao tentar fechar modal: {e}")
            return False

    def setup_driver(self):
        """Configura e inicializa o driver do Chrome."""
        chrome_options = webdriver.ChromeOptions()
        
        if self.headless_mode:
            chrome_options.add_argument('--headless')
            logger.info("Modo Headless ativado.")
        else:
            logger.info("Modo Headless desativado.")

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--page-load-strategy=eager')
        #chrome_options.add_argument('--window-size=992,1080')        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        options = Options()
        options.add_experimental_option("detach", True)

        try:
            if self.driver_path and os.path.exists(self.driver_path):
                service = Service(self.driver_path)
                logger.info(f"Usando ChromeDriver do caminho configurado: {self.driver_path}")
            else:
                service = Service(ChromeDriverManager().install())
                logger.info("Baixando e usando o ChromeDriver mais recente via WebDriverManager.")
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10) 
            self.driver.maximize_window()   
            self.driver.implicitly_wait(15) 
            self.driver.set_page_load_timeout(60)
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("WebDriver do Chrome configurado com sucesso.")
            return True
        except Exception as e:
            log_erro(f"Erro ao configurar/inicializar o WebDriver do Chrome: {e}")
            return False
        
    def login_linkedin(self):
        """Realiza login no LinkedIn."""
        try:
            logger.info("Iniciando processo de login no LinkedIn.")
            self.driver.get("https://www.linkedin.com/login")
            time.sleep(self.delay_min)
            
            email_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            email_field.send_keys(self.email)
            time.sleep(self.delay_min)
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.send_keys(self.password)
            time.sleep(self.delay_min)
            
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()
            
            WebDriverWait(self.driver, 30).until(
                EC.any_of(
                    EC.url_contains("linkedin.com/feed"),
                    EC.url_contains("linkedin.com/jobs"),
                    EC.presence_of_element_located((By.ID, "global-nav-typeahead")),
                )
            )
            
            logger.info("Login realizado com sucesso.")
            time.sleep(self.delay_max)
            return True
            
        except TimeoutException:
            log_erro("Timeout durante o login - verifique credenciais ou conexão.")
            return False
        except NoSuchElementException as e:
            log_erro(f"Elemento não encontrado durante login: {e}")
            return False
        except Exception as e:
            log_erro(f"Erro inesperado durante login: {e}")
            return False


    def search_jobs(self):
        """Busca vagas no LinkedIn baseado nas palavras-chave e localização, usando geoId."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Tentativa {attempt + 1}/{max_retries}: Iniciando busca por vagas com keyword: '{self.keyword}' e geoId: '{self.geo_id}'")
                
                search_url = (
                    f"https://www.linkedin.com/jobs/search/?geoId={self.geo_id}"
                    f"&keywords={self.encoded_keyword}"
                    f"&origin=JOB_SEARCH_PAGE_SEARCH_BUTTON&refresh=true" # CORRIGIDO: Removido '&' duplicado
                )
                self.driver.get(search_url)
                
                # Aguarda carregamento da página de resultados, esperando pelo primeiro item da lista de vagas
                WebDriverWait(self.driver, 45).until(
                    EC.visibility_of_element_located((By.CLASS_NAME, "scaffold-layout__list-item")) 
                )
                
                logger.info("Página de busca de vagas carregada com sucesso e o primeiro item de vaga está visível!")
                time.sleep(self.delay_max)
                return True
                
            except TimeoutException:
                logger.warning(f"Timeout na tentativa {attempt + 1} ao carregar página de busca de vagas. Tentando novamente...")
                time.sleep(5)
                continue
            except Exception as e:
                log_erro(f"Erro inesperado na tentativa {attempt + 1} ao buscar vagas: {e}")
                time.sleep(5)
                continue
        
        log_erro("Falha em todas as tentativas de carregar a página de busca de vagas.")
        return False

    def apply_filters(self):
        """Inicia o processo de aplicação de filtros no LinkedIn."""
        logger.info("Iniciando aplicação de filtros.")
        
        # 1. Tentar abrir o modal de 'Todos os filtros'
        try:
            all_filters_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Todos os filtros')] | //button[contains(@aria-label, 'Exibir todos os filtros')]"))
            )
            all_filters_button.click()
            logger.info("Modal 'Todos os filtros' aberto.")
            time.sleep(self.delay_min)
            # Esperar por um elemento dentro do modal para garantir que ele carregou
            WebDriverWait(self.driver, 15).until( # Tempo limite aumentado para 15s
                EC.visibility_of_element_located((By.XPATH, "//div[@class='search-reusables__secondary-advanced-filters-sub-header' and contains(., 'Filtrar apenas')]"))
            )
            logger.info("Modal de filtros carregado e o cabeçalho 'Filtrar apenas' está visível.")

        except TimeoutException:
            logger.error("Tempo esgotado! Não foi possível encontrar/clicar no botão 'Todos os filtros' ou o cabeçalho 'Filtrar apenas' não apareceu. Pode ser que o modal não abriu ou a estrutura HTML mudou.")
            return False # Falha ao abrir o modal, não é possível aplicar filtros
        except Exception as e:
            logger.error(f"Erro inesperado ao tentar abrir o modal 'Todos os filtros': {e}")
            return False 

        # 2. Aplicar Candidatura Simplificada
        if self.apply_easy_apply_filter:
            self._apply_easy_apply_filter()
            time.sleep(self.delay_min)

        # 3. Aplicar Último mês (Data de publicação)
        if self.apply_date_filter:
            self._apply_date_filter()
            time.sleep(self.delay_min)

        # 4. Aplicar filtros de local de trabalho (agora separados)
        # Atenção: Se você ativar mais de um desses, o LinkedIn pode se comportar de forma inesperada.
        # Idealmente, ative apenas o que deseja ou combine-os logicamente.
        if self.apply_remote_filter:
            if not self._apply_remote_filter():
                logger.warning("Falha ao aplicar filtro 'Remoto'.")
            time.sleep(self.delay_min)

        if self.apply_presencial_filter:
            if not self._apply_presencial_filter():
                logger.warning("Falha ao aplicar filtro 'Presencial'.")
            time.sleep(self.delay_min)

        if self.apply_hibrido_filter:
            if not self._apply_hibrido_filter():
                logger.warning("Falha ao aplicar filtro 'Híbrido'.")
            time.sleep(self.delay_min)
        
        # 5. Clicar em 'Mostrar resultados' ou 'Aplicar' dentro do modal
        try:
            # CORREÇÃO CRÍTICA AQUI: Usando o atributo data-test para maior robustez
            show_results_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@data-test-reusables-filters-modal-show-results-button='true']"))
            )
            show_results_button.click()
            logger.info("Botão 'Mostrar resultados' clicado com sucesso usando data-test attribute.")
            time.sleep(self.delay_max)
            return True
        except TimeoutException:
            logger.warning("Timeout: Botão 'Mostrar resultados' (data-test) não encontrado. Verifique se os filtros foram aplicados e o modal fechado manualmente.")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao clicar em 'Mostrar resultados'/'Aplicar': {e}")
            return False

    def _apply_easy_apply_filter(self):
        """Aplica o filtro de Candidatura Simplificada (toggle)."""
        try:
            logger.info("Tentando aplicar filtro 'Candidatura Simplificada'...")
            
            # XPath robusto para o elemento INPUT real (o checkbox/toggle)
            # Ele busca o input com role='switch' e type='checkbox' dentro do fieldset
            # que contém um h3 ou legend com o texto 'Candidatura simplificada'.
            filter_input_xpath = "//fieldset[contains(., 'Candidatura simplificada')]//input[@role='switch' and @type='checkbox']"            
            easy_apply_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, filter_input_xpath))
            )
            
            # Verifica o estado atual do filtro (aria-checked)
            is_checked = easy_apply_input.get_attribute("aria-checked") == "true"
            
            if not is_checked:
                logger.info("Filtro 'Candidatura Simplificada' está DESATIVADO. Ativando...")
                # Usa JavaScript para clicar no elemento. Isso é mais robusto
                # e contorna muitos problemas de elemento não-clicável.
                self.driver.execute_script("arguments[0].click();", easy_apply_input)
                
                # Opcional: Esperar que o atributo 'aria-checked' mude para 'true',
                # confirmando que o clique foi efetivo e o estado mudou.
                WebDriverWait(self.driver, 5).until(
                    EC.text_to_be_present_in_element_attribute(
                        (By.XPATH, filter_input_xpath), "aria-checked", "true"
                    )
                )
                logger.info("Filtro 'Candidatura Simplificada' ativado com sucesso!")
            else:
                logger.info("Filtro 'Candidatura Simplificada' já estava ativado.")
            
            return True
            
        except TimeoutException:
            logger.warning("Timeout: Elemento do filtro 'Candidatura Simplificada' não encontrado ou não foi possível confirmar a ativação.")
            return False
        except Exception as e:
            logger.warning(f"Erro ao aplicar filtro 'Candidatura Simplificada': {e}. Detalhes: {e}")
            return False
        
    def _apply_date_filter(self):
        """Aplica o filtro de data (Último mês)."""
        try:
            logger.info("Tentando aplicar filtro 'Último mês'...")
            
            # XPath CORRIGIDO:
            # 1. 'Data do anúncio' no fieldset (usando '.')
            # 2. Caminho completo para o span dentro da label (label/p/span)
            label_xpath = "//label[contains(., 'Último mês') or contains(., 'Past month')]"
            
            logger.debug(f"XPath para o LABEL 'Último mês': {label_xpath}")
            
            label_last_month = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )
            logger.info("LABEL 'Último mês' encontrado.")
            
            # PASSO 2: Encontrar o INPUT radio button que é o irmão anterior (preceding-sibling) do LABEL
            # Este é o relacionamento que você identificou e que funciona!
            radio_button_xpath = "./preceding-sibling::input[@type='radio']"
            
            last_month_radio = label_last_month.find_element(By.XPATH, radio_button_xpath)
            logger.info("INPUT radio button associado ao 'Último mês' encontrado.")

            # PASSO 3: Verificar se o radio button já está selecionado e clicar se não estiver
            if not last_month_radio.is_selected():
                logger.info("Filtro 'Último mês' não selecionado. Selecionando...")
                # Usa JavaScript para clicar no radio button (a forma mais robusta de clique)
                self.driver.execute_script("arguments[0].click();", last_month_radio)
                
                # Espera a confirmação de que o radio button foi selecionado
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_selected(last_month_radio) # EC.element_to_be_selected pode receber o elemento diretamente
                )
                logger.info("Filtro 'Último mês' aplicado com sucesso!")
            else:
                logger.info("Filtro 'Último mês' já estava selecionado.")
            
            return True
            
        except TimeoutException:
            logger.warning("Timeout: Elemento do filtro 'Último mês' não encontrado ou não foi possível confirmar a seleção.")
            return False
        except Exception as e:
            logger.warning(f"Erro ao aplicar filtro 'Último mês': {e}. Detalhes: {e}")
            return False

    def _apply_remote_filter(self):
        """Aplica o filtro de trabalho remoto."""
        try:
            logger.info("Tentando aplicar filtro 'Remoto' com abordagem comprovada...")
            
            # PASSO 1: Encontrar o elemento LABEL que contém o texto "Remoto"
            # O '.' (ponto) no XPath pega o texto de todos os descendentes, então funciona mesmo se o texto estiver em span/p.
            # Inclui a variação em inglês para robustez internacional.
            # A estrutura é similar ao filtro de data.
            label_xpath = "//label[contains(., 'Remoto') or contains(., 'Remote')]"
            
            logger.debug(f"XPath para o LABEL 'Remoto': {label_xpath}")
            
            label_remote = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )
            logger.info("LABEL 'Remoto' encontrado.")

            # PASSO 2: Encontrar o INPUT checkbox que é o irmão anterior (preceding-sibling) do LABEL
            # Note que é um checkbox, mas a lógica de navegação é a mesma do radio button.
            checkbox_xpath = "./preceding-sibling::input[@type='checkbox']"
            
            remote_checkbox = label_remote.find_element(By.XPATH, checkbox_xpath)
            logger.info("INPUT checkbox associado ao 'Remoto' encontrado.")

            # PASSO 3: Verificar se o checkbox já está selecionado e clicar se não estiver
            # Para checkboxes, usamos is_selected()
            if not remote_checkbox.is_selected():
                logger.info("Filtro 'Remoto' não selecionado. Selecionando...")
                # Usa JavaScript para clicar no checkbox (a forma mais robusta de clique)
                self.driver.execute_script("arguments[0].click();", remote_checkbox)
                
                # Espera a confirmação de que o checkbox foi selecionado
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_selected(remote_checkbox) 
                )
                logger.info("Filtro 'Remoto' aplicado com sucesso!")
            else:
                logger.info("Filtro 'Remoto' já estava selecionado.")
            
            return True
            
        except TimeoutException:
            logger.warning("Timeout: Elemento do filtro 'Remoto' não encontrado ou não foi possível confirmar a seleção.")
            print("DEBUG: Timeout in _apply_remote_filter. Verifique a visibilidade da UI e XPaths.")
            return False
        except NoSuchElementException:
            logger.warning("Elemento do filtro 'Remoto' (label ou input) não encontrado. Verifique se o modal de filtros está aberto e a estrutura HTML.")
            print("DEBUG: NoSuchElementException in _apply_remote_filter. Elemento não presente. Verifique o HTML.")
            return False
        except Exception as e:
            logger.warning(f"Erro inesperado ao aplicar filtro 'Remoto': {e}. Detalhes: {e}")
            print(f"DEBUG: Erro em _apply_remote_filter: {e}")
            return False

    def _apply_presencial_filter(self):
        """Aplica o filtro de trabalho presencial."""
        try:
            logger.info("Tentando aplicar filtro 'Presencial'...")
            
            # PASSO 1: Encontrar o elemento LABEL que contém o texto "Presencial"
            label_xpath = "//label[contains(., 'Presencial') or contains(., 'In-person')]"
            
            logger.debug(f"XPath para o LABEL 'Presencial': {label_xpath}")
            
            label_presencial = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )
            logger.info("LABEL 'Presencial' encontrado.")

            # PASSO 2: Encontrar o INPUT checkbox que é o irmão anterior (preceding-sibling) do LABEL
            checkbox_xpath = "./preceding-sibling::input[@type='checkbox']"
            
            presencial_checkbox = label_presencial.find_element(By.XPATH, checkbox_xpath)
            logger.info("INPUT checkbox associado ao 'Presencial' encontrado.")

            # PASSO 3: Verificar se o checkbox já está selecionado e clicar se não estiver
            if not presencial_checkbox.is_selected():
                logger.info("Filtro 'Presencial' não selecionado. Selecionando...")
                self.driver.execute_script("arguments[0].click();", presencial_checkbox)
                
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_selected(presencial_checkbox) 
                )
                logger.info("Filtro 'Presencial' aplicado com sucesso!")
            else:
                logger.info("Filtro 'Presencial' já estava selecionado.")
            
            return True
            
        except TimeoutException:
            logger.warning("Timeout: Elemento do filtro 'Presencial' não encontrado ou não foi possível confirmar a seleção.")
            print("DEBUG: Timeout in _apply_presencial_filter. Verifique a visibilidade da UI e XPaths.")
            return False
        except NoSuchElementException:
            logger.warning("Elemento do filtro 'Presencial' (label ou input) não encontrado. Verifique se o modal de filtros está aberto e a estrutura HTML.")
            print("DEBUG: NoSuchElementException in _apply_presencial_filter. Elemento não presente. Verifique o HTML.")
            return False
        except Exception as e:
            logger.warning(f"Erro inesperado ao aplicar filtro 'Presencial': {e}. Detalhes: {e}")
            print(f"DEBUG: Erro em _apply_presencial_filter: {e}")
            return False

    def _apply_hibrido_filter(self):
        """Aplica o filtro de trabalho híbrido."""
        try:
            logger.info("Tentando aplicar filtro 'Híbrido'...")
            
            # PASSO 1: Encontrar o elemento LABEL que contém o texto "Híbrido"
            label_xpath = "//label[contains(., 'Híbrido') or contains(., 'Hybrid')]"
            
            logger.debug(f"XPath para o LABEL 'Híbrido': {label_xpath}")
            
            label_hibrido = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, label_xpath))
            )
            logger.info("LABEL 'Híbrido' encontrado.")

            # PASSO 2: Encontrar o INPUT checkbox que é o irmão anterior (preceding-sibling) do LABEL
            checkbox_xpath = "./preceding-sibling::input[@type='checkbox']"
            
            hibrido_checkbox = label_hibrido.find_element(By.XPATH, checkbox_xpath)
            logger.info("INPUT checkbox associado ao 'Híbrido' encontrado.")

            # PASSO 3: Verificar se o checkbox já está selecionado e clicar se não estiver
            if not hibrido_checkbox.is_selected():
                logger.info("Filtro 'Híbrido' não selecionado. Selecionando...")
                self.driver.execute_script("arguments[0].click();", hibrido_checkbox)
                
                WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_selected(hibrido_checkbox) 
                )
                logger.info("Filtro 'Híbrido' aplicado com sucesso!")
            else:
                logger.info("Filtro 'Híbrido' já estava selecionado.")
            
            return True
            
        except TimeoutException:
            logger.warning("Timeout: Elemento do filtro 'Híbrido' não encontrado ou não foi possível confirmar a seleção.")
            print("DEBUG: Timeout in _apply_hibrido_filter. Verifique a visibilidade da UI e XPaths.")
            return False
        except NoSuchElementException:
            logger.warning("Elemento do filtro 'Híbrido' (label ou input) não encontrado. Verifique se o modal de filtros está aberto e a estrutura HTML.")
            print("DEBUG: NoSuchElementException in _apply_hibrido_filter. Elemento não presente. Verifique o HTML.")
            return False
        except Exception as e:
            logger.warning(f"Erro inesperado ao aplicar filtro 'Híbrido': {e}. Detalhes: {e}")
            print(f"DEBUG: Erro em _apply_hibrido_filter: {e}")
            return False

    def submmit_application(self, job_card_element, visualizado):
        """
        Submete o CV para vagas com candidatura simplificada e gera dataframe.
        job_card_element: O elemento web que representa o cartão da vaga na lista.
        """
        job_details = {
            'Visualizado': visualizado,
            'Company': '',
            'Job Info': '',
            'Job Description': '',
            'Title': 'N/A', # Será preenchido após clicar e extrair
            'Link': 'N/A',  # Será preenchido após clicar e extrair
            'Code': 'N/A',  # Será preenchido após clicar e extrair
            'Easy Apply': "No",
            'Sent Resume': "No"
        }

        # Extrair link e título ANTES de clicar, para robustez contra StaleElement
        try:
            job_link_element = job_card_element.find_element(By.CSS_SELECTOR, self.JOB_CARD_LINK_CSS)
            job_link = job_link_element.get_attribute('href')
            job_title_text = job_link_element.find_element(By.CSS_SELECTOR, 'span[aria-hidden="true"]').get_attribute('textContent').strip()

            job_details['Title'] = job_title_text
            job_details['Link'] = job_link
            job_details['Code'] = job_link.split("view/")[1].split("/")[0] if "view/" in job_link else 'N/A'

            logger.info(f"Processando vaga: {job_details['Title']} (Código: {job_details['Code']})")

            # Clicar no anúncio da vaga para abrir os detalhes
            self.wait.until(EC.element_to_be_clickable(job_card_element)).click()
            logger.info("Anúncio da vaga clicado. Aguardando detalhes da vaga...")

            # Esperar que o painel de detalhes da vaga carregue
            self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "jobs-search__job-details--container")))
            time.sleep(self.delay_min) # Pequena pausa para garantir renderização de elementos
            logger.debug("Painel de detalhes da vaga carregado.")

        except StaleElementReferenceException:
            logger.warning(f"Elemento job_card_element ficou obsoleto. Pulando esta vaga: {job_details.get('Title', 'N/A')}.")
            return job_details
        except TimeoutException:
            logger.error(f"Não foi possível clicar no anúncio ou carregar os detalhes da vaga: {job_details.get('Title', 'N/A')}. Pulando.")
            return job_details
        except Exception as e:
            logger.error(f"Erro inesperado ao clicar no anúncio ou carregar detalhes: {e}. Pulando: {job_details.get('Title', 'N/A')}")
            return job_details

        # 2. Extrair informações detalhadas da vaga
        # Usar get_attribute('textContent') para garantir a extração de texto visível ou não
        job_company_elem = self._safe_find_element(By.CLASS_NAME, self.JOB_DETAILS_COMPANY_CLASS)
        if job_company_elem:
            job_details['Company'] = job_company_elem.get_attribute('textContent').strip()

        job_info_tempo_elem = self._safe_find_element(By.CLASS_NAME, self.JOB_DETAILS_PRIMARY_DESC_CLASS)
        job_info_loc_elem = self._safe_find_element(By.CLASS_NAME, self.JOB_DETAILS_INSIGHT_CLASS)
        if job_info_tempo_elem and job_info_loc_elem:
            job_details['Job Info'] = f"{job_info_tempo_elem.get_attribute('textContent').strip()}/{job_info_loc_elem.get_attribute('textContent').strip()}"
        elif job_info_tempo_elem:
            job_details['Job Info'] = job_info_tempo_elem.get_attribute('textContent').strip()
        elif job_info_loc_elem:
            job_details['Job Info'] = job_info_loc_elem.get_attribute('textContent').strip()

        job_description_elem = self._safe_find_element(By.CLASS_NAME, self.JOB_DESCRIPTION_CLASS)
        if job_description_elem:
            job_details['Job Description'] = job_description_elem.get_attribute('textContent').strip()


        # 3. Determinar o tipo de aplicação e tentar submeter

        # Caso 1: Botão "Candidatar-se" (leva para o site do empregador)
        employer_site_button = self._safe_find_element(By.XPATH, f"//button[contains(@aria-label,'{self.BUTTON_EMPLOYER_SITE_ARIA_LABEL}')]", timeout=3, wait_type=EC.element_to_be_clickable)
        if employer_site_button:
            job_details['Easy Apply'] = "Employer"
            job_details['Sent Resume'] = "No" # Não enviamos o CV ainda
            logger.info('Vaga direciona para o site do empregador. Não será aplicada automaticamente.')
            # Não clica no botão, apenas registra e retorna.
            self._close_application_modal() # Tenta fechar o painel de detalhes da vaga

            return job_details

        # Caso 2: Botão "Candidatura Simplificada"
        easy_apply_button = self._safe_find_element(By.CLASS_NAME, self.BUTTON_EASY_APPLY_CLASS, timeout=3, wait_type=EC.element_to_be_clickable)
        if easy_apply_button:
            logger.info('Vaga possui "Candidatura Simplificada".')
            job_details['Easy Apply'] = "Yes" # É uma candidatura simplificada

            try:
                # Clicar no botão de Candidatura Simplificada
                easy_apply_button.click()
                logger.info("Clicado em 'Candidatura Simplificada'.")

                # Esperar que o modal da aplicação apareça e tentar encontrar o botão de 'Enviar candidatura'
                submit_button = self._safe_find_element(By.XPATH, f"//button[contains(@aria-label,'{self.BUTTON_SUBMIT_APPLICATION_ARIA_LABEL}')]", timeout=5, wait_type=EC.element_to_be_clickable)

                if submit_button:
                    # Se o botão de 'Enviar candidatura' for encontrado, significa que é um passo direto
                    self.wait.until(EC.element_to_be_clickable(submit_button)).click()
                    logger.info("Botão 'Enviar candidatura' clicado. CV enviado!")
                    job_details['Sent Resume'] = "Yes"
                else:
                    logger.warning("Botão de 'Enviar candidatura' não encontrado no modal de Candidatura Simplificada.")
                    logger.warning("Possíveis cenários: aplicação multi-passos (não suportado por esta função), já aplicada, ou erro inesperado.")
                    job_details['Sent Resume'] = "No" # Ou "Check Manually"
            except TimeoutException:
                logger.error("Timeout ao esperar por elementos no modal de Candidatura Simplificada. Fechando modal.")
                job_details['Sent Resume'] = "No" # Não foi possível submeter
            except Exception as e:
                logger.error(f"Erro inesperado durante a Candidatura Simplificada: {e}. Fechando modal.")
                job_details['Sent Resume'] = "Error" # Ocorreu um erro
            finally:
                self._close_application_modal() # Tenta fechar o modal, independentemente do sucesso

            return job_details

        # Caso 3: Não há botão de "Candidatar-se" nem "Candidatura Simplificada"
        # Isso geralmente significa que a vaga já foi aplicada, ou não está mais disponível,
        # ou o LinkedIn está mostrando um status de "Aplicado".
        else:
            try:
                # Exemplo: Procurar por texto "Candidatura enviada" ou "Aplicado" no card de detalhes da vaga
                applied_text_element = self._safe_find_element(By.XPATH, "//*[contains(text(), 'Candidatura enviada')] | //*[contains(text(), 'Aplicado')]", timeout=2)
                if applied_text_element:
                    job_details['Easy Apply'] = "Yes" # Se foi aplicada, era uma vaga de Easy Apply
                    job_details['Sent Resume'] = "Yes"
                    logger.info("Vaga já identificada como 'Aplicada' ou 'Candidatura enviada'.")
                else:
                    logger.warning("Nenhum botão de aplicação encontrado e nenhum status de 'Aplicado'. Vaga pode estar fechada ou ser um erro.")
                    # Manter o status original de 'No'
            except TimeoutException:
                logger.warning("Nenhum botão de aplicação encontrado e nenhum status de 'Aplicado' visível após clique. Vaga pode estar fechada ou ser um erro.")
            except Exception as e:
                logger.error(f"Erro ao verificar status de 'Aplicado': {e}")
            finally:
                self._close_application_modal() # Tenta fechar o painel de detalhes da vaga
        
        logger.info(f"Detalhes da vaga '{job_details['Title']}' adicionados. Status Easy Apply: {job_details['Easy Apply']}, Sent Resume: {job_details['Sent Resume']}")
        return job_details


    def scroll_and_collect_jobs(self):
        """Rola a página e coleta as vagas até o limite definido."""
        logger.info("Iniciando rolagem e coleta de vagas.")
        #self.driver.set_window_size(991, 1080)
        time.sleep(2)
        jobs_collected = 0
        last_height = 0
        # --- Definição de variáveis que estavam faltando ---
        items_per_page = 25  # Valor comum para o LinkedIn, ajuste se necessário        
        # --- Obter o número total de vagas exibido na interface ---
        total_results_int = 0
        total_pages_int = 1  

        # Tentativa primária: Obter total de resultados do subtítulo da lista
        try:
            total_results_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'jobs-search-results-list__subtitle'))
            )
            total_results_txt = total_results_element.get_attribute('textContent')
            # Extrai apenas os dígitos do texto (ex: "39 resultados" -> 39)
            total_results_int = int(''.join(filter(str.isdigit, total_results_txt.split(' ', 1)[0].replace('.', ''))))
            logger.info(f"Total de vagas encontrado no subtítulo: {total_results_int}")
            
            # Calcula o total de páginas com base nos resultados totais
            total_pages_int = math.ceil(total_results_int / items_per_page)
            logger.info(f"Total de páginas calculado a partir de resultados: {total_pages_int}")

        except Exception as e:
            logger.warning(f"Não foi possível determinar o total de vagas a partir do subtítulo: {e}. Tentando fallback com o estado da paginação...")

        # Fallback secundário: Extrair total de páginas do elemento de estado da paginação
        try:
            page_state_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "jobs-search-pagination__page-state"))
            )
            page_state_text = page_state_element.get_attribute('textContent')
            logger.debug(f"Texto do elemento de paginação (via textContent): '{page_state_text}'")
            # Extrai o último número da string (o total de páginas)
            total_pages_str = page_state_text.split(' de ')[-1]
            total_pages_int = int(total_pages_str.strip())
            logger.info(f"Total de páginas de resultados identificado: {total_pages_int}")
        except Exception as e:
            logger.warning(f"Não foi possível determinar o total de páginas de forma explícita: {e}. Usando o cálculo anterior ou padrão.")
            # Fallback para o cálculo existente ou um padrão se necessário
            try:
                # Assuming total_results_int and items_per_page are already defined
                total_pages_int = math.ceil(total_results_int / items_per_page)
            except NameError: # Fallback if total_results_int not found
                total_pages_int = 1 # Minimum 1 page

        current_page = 1 # Inicializa current_page para o loop de paginação

        # --- Loop principal para iterar sobre as páginas ---
        while current_page <= total_pages_int and jobs_collected < self.max_jobs_to_scrape:
            logger.info(f"Processando página {current_page} de {total_pages_int}")

            # Localização do painel rolável (painel esquerdo com a lista de vagas)
            try:
                anchor_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "results-list__title"))
                )
                logger.debug("Elemento âncora 'results-list__title' encontrado.")
                
                results_panel = anchor_element.find_element(
                    By.XPATH, 
                    "./ancestor::div[contains(@class, 'scaffold-layout__list') and @tabindex='-1']"
                )
                logger.info("Painel de resultados 'scaffold-layout__list' encontrado via navegação a partir do elemento âncora.")
                
            except TimeoutException:
                logger.error("Elemento âncora ou painel rolável não encontrado após o tempo limite. Verifique o HTML. Encerrando coleta.")
                self.driver.save_screenshot(f"debug_results_panel_timeout_page_{current_page}.png")
                with open(f"debug_results_panel_timeout_page_{current_page}.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                return False # Retorna False para sinalizar falha e parar a execução
            except NoSuchElementException:
                logger.error("Painel rolável 'scaffold-layout__list' não encontrado como ancestral do elemento âncora. Verifique a estrutura HTML. Encerrando coleta.")
                self.driver.save_screenshot(f"debug_panel_ancestor_not_found_page_{current_page}.png")
                with open(f"debug_panel_ancestor_not_found_page_{current_page}.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                return False # Retorna False para sinalizar falha e parar a execução
            except Exception as e:
                logger.error(f"Erro inesperado ao encontrar o painel de resultados: {e}. Encerrando coleta.")
                return False # Retorna False para sinalizar falha e parar a execução

            if not results_panel:
                logger.error("Painel de resultados não foi definido. Interrompendo a coleta.")
                break

            logger.info(f"Painel de resultados encontrado: Tag '{results_panel.tag_name}' com classes: '{results_panel.get_attribute('class')}'")

            # --- Loop interno para rolagem e coleta de vagas na PÁGINA ATUAL ---
            last_height = self.driver.execute_script("return arguments[0].scrollHeight", results_panel) # Altura inicial do painel
            scroll_attempts = 0
            MAX_SCROLL_ATTEMPTS = 3 # Reduzido, pois não há carregamento dinâmico dentro da página

            while scroll_attempts < MAX_SCROLL_ATTEMPTS:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", results_panel)
                time.sleep(self.delay_min) 
                
                new_height = self.driver.execute_script("return arguments[0].scrollHeight", results_panel)
                logger.debug(f"Tentativa de rolagem {scroll_attempts + 1}: altura {last_height} -> {new_height}")

                scroll_attempts += 1
                if new_height == last_height: # Se a altura não mudou, chegamos ao fim da rolagem
                    logger.info("Altura do painel não mudou - fim da rolagem na página atual.")
                    break
                last_height = new_height
                
            # --- Coleta de cartões de vaga na PÁGINA ATUAL ---
            job_cards_on_page = results_panel.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
            logger.info(f"Encontrados {len(job_cards_on_page)} cartões de vaga na página {current_page} após rolagem.")
            
            for i, card in enumerate(job_cards_on_page):
                job_link = None
                job_title = None
                
            for i, card in enumerate(job_cards_on_page):
                job_link = None
                job_title = None
                job_id = card.get_attribute('data-occludable-job-id') # Já está pegando o ID, ótimo!

                try:
                    # **NOVA ETAPA DE FORÇAR O CARREGAMENTO DO CONTEÚDO**
                    # 1. Rolagem explícita para a visualização: Garante que o card está visível na tela
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", card)
                    time.sleep(1) # Pequena pausa para a rolagem terminar

                    # 2. Hover sobre o card: Muitas vezes, o hover ativa o lazy loading
                    hover = ActionChains(self.driver).move_to_element(card)
                    hover.perform()
                    
                    # 3. Aumentar o tempo de espera APÓS o hover para dar mais chance de carregamento
                    # Tente 3, 4 ou até 5 segundos. Comece com 4 segundos.
                    time.sleep(4) 
                    
                    # 4. Agora, tente encontrar o elemento do link com WebDriverWait (que já está configurado com seu tempo alto)
                    # O XPath continua o mesmo, pois o HTML esperado é esse.
                    job_link_locator = (By.XPATH, 
                        f"//li[@data-occludable-job-id='{job_id}']//a[contains(@class, 'job-card-container__link') and contains(@class, 'job-card-list__title--link')]"
                    )
                    
                    link_element_found_by_wait = self.wait.until(
                        EC.visibility_of_element_located(job_link_locator), # Continua sendo o correto, pois o elemento PRECISA estar visível
                        message=f"Timed out waiting for job link to become visible for card ID: {job_id}"
                    )
                    
                    job_link = link_element_found_by_wait.get_attribute('href')
                    
                    # O título (<strong>) está dentro do <a>. Podemos pegá-lo diretamente do link_element_found_by_wait
                    job_title_element = link_element_found_by_wait.find_element(By.TAG_NAME, 'strong')
                    job_title = job_title_element.text.strip()
                    
                    logger.info(f"Link da vaga encontrado: {job_link}, Título: {job_title}")

                except (NoSuchElementException, TimeoutException) as e:
                    logger.warning(f"Não foi possível encontrar o link/título da vaga para o card {i+1} (ID: {job_id if 'job_id' in locals() else 'N/A'}). Pulando este card. Erro: {type(e).__name__}: {e}")
                    # Loga o HTML do card NO MOMENTO DA EXCEÇÃO (será o HTML vazio neste caso)
                    logger.debug(f"HTML do card problemático (empty or content not loaded): {card.get_attribute('outerHTML')}")
                    continue

                try:
                    visualizado_locator = (By.XPATH, 
                        f"//li[@data-occludable-job-id='{job_id}']//li[contains(@class, 'job-card-container__footer-item') and contains(@class, 'job-card-container__footer-job-state') and contains(@class, 't-bold')]"
                    )
                    
                    # Espera que o elemento "Visualizado" esteja presente (não precisa ser visível se for só para extrair texto)
                    viewed_badge_element = self.wait.until(
                        EC.presence_of_element_located(visualizado_locator),
                        message=f"Timed out waiting for 'Visualizado' badge for card ID: {job_id}"
                    )
                    visualizado = viewed_badge_element.text.strip()
                except (NoSuchElementException,TimeoutException):
                        visualizado = ""
                        continue

                if job_link and job_link not in self.seen_job_ids:
                    try:
                        job_data = self.submmit_application(card,visualizado)
                        
                        if job_data and job_data.get('Link'):
                            self.job_details.append(job_data)
                            self.seen_job_ids.add(job_data['Link'])
                            jobs_collected += 1
                            logger.info(f"Coletada vaga: '{job_data.get('Title', 'N/A')}' (Total: {jobs_collected}/{self.max_jobs_to_scrape})")
                            
                            if jobs_collected >= self.max_jobs_to_scrape:
                                logger.info(f"Limite de {self.max_jobs_to_scrape} vagas atingido. Encerrando coleta de cartões.")
                                break
                    except WebDriverException as card_exc:
                        logger.warning(f"Erro ao processar cartão de vaga {job_link}: {card_exc}. Pulando este cartão.")
                        self.driver.save_screenshot(f"debug_card_error_{time.time()}.png")
                        with open(f"debug_card_error_{time.time()}.html", "w", encoding="utf-8") as f:
                            f.write(self.driver.page_source)
                    except Exception as e_card:
                        logger.error(f"Erro inesperado ao processar cartão de vaga {job_link}: {e_card}")

                # Verifica novamente se o limite de vagas foi atingido após processar todos os cartões da página
                if jobs_collected >= self.max_jobs_to_scrape:
                    logger.info("Limite total de vagas atingido. Encerrando coleta.")
                    break # Sai do loop principal de paginação

            # --- Navegação para a próxima página ---
            if current_page < total_pages_int:
                try:
                    # Busca o botão "Ver próxima página" baseado no HTML fornecido
                    next_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Ver próxima página']"))
                    )
                    self.driver.execute_script("arguments[0].click();", next_button)
                    logger.info(f"Clicou no botão 'Ver próxima página' para a página {current_page + 1}.")
                    time.sleep(self.delay_min * 2)
                    current_page += 1
                    last_height = 0
                    scroll_attempts = 0 
                except TimeoutException:
                    logger.warning("Botão 'Ver próxima página' não encontrado ou não clicável. Finalizando paginação.")
                    break
                except Exception as e:
                    logger.error(f"Erro ao tentar avançar para a próxima página: {e}")
                    break
            else:
                logger.info("Última página processada. Encerrando coleta.")
                break

        logger.info(f"Rolagem e coleta concluídas. Total de vagas coletadas: {jobs_collected}")
        return True

    def extract_job_details_from_link(self, job_link):
        """Extrai detalhes de uma vaga específica usando seu link."""
        current_url = self.driver.current_url # Salva a URL da página de busca
        try:
            self.driver.get(job_link)
            time.sleep(self.delay_min) 

            job_data = {}
            job_data['Link'] = job_link
            
            try:
                job_code = job_link.split('/view/')[1].split('/')[0]
                job_data['Code'] = job_code
            except IndexError:
                job_data['Code'] = "N/A_CODE"
                logger.warning(f"Não foi possível extrair o código da vaga do link: {job_link}")
            
            job_data['Title'] = self.safe_find_element_text(By.CSS_SELECTOR, "h1.job-details-jobs-unified-top-card__job-title")
            job_data['Company'] = self.safe_find_element_text(By.CSS_SELECTOR, "a.job-details-jobs-unified-top-card__company-name")
            job_data['Location'] = self.safe_find_element_text(By.CSS_SELECTOR, ".job-details-jobs-unified-top-card__bullet")
            
            try:
                description_element = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-description-content__text.jobs-description-content__text--stretch"))
                )
                try:
                    show_more_button = description_element.find_element(By.XPATH, ".//button[contains(@aria-label, 'Mostrar mais')]")
                    show_more_button.click()
                    time.sleep(self.delay_min)
                except NoSuchElementException:
                    pass 
                
                job_data['Job Description'] = description_element.text.strip()
            except TimeoutException:
                job_data['Job Description'] = "Descrição não disponível"
            except Exception as e:
                job_data['Job Description'] = f"Erro ao coletar descrição: {e}"
                logger.warning(f"Erro ao coletar descrição para {job_link}: {e}")

            job_data['Date Scraped'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            self.driver.get(current_url)
            time.sleep(self.delay_min)
            
            return job_data
        except Exception as e:
            logger.error(f"Erro ao extrair detalhes da vaga do link {job_link}: {e}")
            self.driver.get(current_url) 
            time.sleep(self.delay_min)
            return None

    def safe_find_element_text(self, by_method, selector, default="N/A"):
        """Busca um elemento de forma segura e retorna seu texto ou um valor padrão."""
        try:
            element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((by_method, selector))
            )
            return element.text.strip()
        except TimeoutException:
            return default
        except NoSuchElementException:
            return default
        except Exception as e:
            logger.debug(f"Erro ao encontrar elemento '{selector}': {e}")
            return default

    def save_jobs_data(self):
        """Salva os dados coletados em arquivo Excel."""
        if not self.job_details:
            logger.warning("Nenhuma vaga foi coletada para salvar.")
            return False
        
        df = pd.DataFrame(self.job_details)
        
        output_dir = os.path.dirname(self.output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        try:
            df.to_excel(self.output_file, index=False)
            logger.info(f"Dados das vagas salvos com sucesso em: {self.output_file}")
            logger.info(f"Total de vagas salvas: {len(self.job_details)}")
            return True
        except Exception as e:
            log_erro(f"Erro ao salvar dados em {self.output_file}: {e}")
            try:
                backup_dir = os.path.dirname(self.error_backup_file)
                if backup_dir:
                    os.makedirs(backup_dir, exist_ok=True)
                df.to_excel(self.error_backup_file, index=False)
                logger.info(f"Dados de backup salvos em: {self.error_backup_file}")
            except Exception as backup_e:
                logger.critical(f"Erro crítico: Não foi possível salvar nem o arquivo principal nem o backup: {backup_e}")
            return False

    def cleanup(self):
        """Fecha o driver do Selenium de forma segura."""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver do Chrome fechado com sucesso.")
        except WebDriverException as e:
            logger.error(f"Erro ao fechar o driver: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao fechar o driver: {e}")

    def easy_apply(self):
        """Método principal que executa todo o fluxo de busca e coleta de vagas."""
        logger.info("=== INICIANDO PROCESSO DE BUSCA E COLETA DE VAGAS NO LINKEDIN ===")
        try:
            if not self.setup_driver():
                log_erro("Falha ao configurar o driver. Abortando.")
                return False
            
            if not self.login_linkedin():
                log_erro("Falha no login. Abortando.")
                return False
            
            if not self.search_jobs():
                log_erro("Falha na busca de vagas. Abortando.")
                return False
            
            # Aplica os filtros (AGORA CHAMANDO A NOVA FUNÇÃO CENTRALIZADA)
            if not self.apply_filters():
                logger.warning("Falha ao aplicar um ou mais filtros.")
            time.sleep(self.delay_min)
            
            if not self.scroll_and_collect_jobs():
                log_erro("Falha durante a rolagem e coleta de vagas. Abortando.")
                return False
            
            if not self.save_jobs_data():
                log_erro("Falha ao salvar os dados coletados. Abortando.")
                return False
            
            logger.info("=== PROCESSO DE BUSCA E COLETA DE VAGAS CONCLUÍDO COM SUCESSO ===")
            return True
        except Exception as e:
            log_erro(f"Um erro inesperado ocorreu no fluxo principal de automação: {e}")
            if self.job_details:
                try:
                    df_error = pd.DataFrame(self.job_details)
                    df_error.to_excel(self.error_backup_file, index=False)
                    logger.info(f"Dados parciais salvos em backup: {self.error_backup_file}")
                except Exception as backup_e:
                    logger.error(f"Erro ao salvar dados de backup após falha: {backup_e}")
            return False
        finally:
            self.cleanup()


# ================= FUNÇÃO PRINCIPAL DO SCRIPT =================
def main():
    # Caminho do arquivo de configuração
    config_path = os.environ.get('CONFIG_JSON_PATH', 'configs/linkedin.json')
    configs = carregar_configuracoes_json(config_path)

    try:
        bot = EasyApplyLinkedin(configs)
        success = bot.easy_apply()
        
        if success:
            logger.info("Script search_linkedin.py executado com sucesso.")
            sys.exit(0)
        else:
            log_erro("Script search_linkedin.py finalizou com falhas.")
            sys.exit(1)
            
    except Exception as e:
        log_erro(f"Erro no fluxo principal de search_linkedin.py: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()