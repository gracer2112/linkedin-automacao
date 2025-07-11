# cv_sugestor.py

import sys
from dotenv import load_dotenv
import os
import json
from tenacity import retry, stop_after_attempt, wait_exponential, before_log
import logging
import ast
import re
import time

import google.generativeai as genai
from google.generativeai import types
from google.auth import default # Para carregar credenciais automaticamente

from docx import Document # Ainda precisamos disso para extrair texto do CV

# ================= LOGGING SETUP =================
loglevel = os.environ.get("MY_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger(__name__)
logger.setLevel(loglevel)

if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)



# ================= FUNÇÕES DO SCRIPT =================

def carrega_chave():
    """Carrega a chave da API do Gemini das variáveis de ambiente."""
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        logger.error("Chave de API do Google não encontrada (GEMINI_API_KEY).")
        sys.exit(1)
    genai.configure(api_key=gemini_api_key)
    return genai

def stdin_has_data():
    """Verifica se há dados na entrada padrão (stdin)."""
    import select
    if sys.stdin.isatty():
        return False
    rlist, _, _ = select.select([sys.stdin], [], [], 0)
    return bool(rlist)

def log_custom_before_sleep(retry_state):
    """Função que loga uma mensagem customizada antes de cada tentativa."""
    delay = retry_state.next_action.sleep
    logger.info(f"API retornou erro ou resposta inválida. Tentando novamente em {delay:.1f} segundos...")

def interpretar_resposta_ia(resposta_texto):
    """
    Interpreta e limpa a resposta da IA para garantir que seja um JSON válido.
    Lida com formatações extras como '```json' e garante que a saída seja uma lista.
    """
    logging.warning("Resposta da IA não parece ser um JSON puro. Validando entrada.")

    # Remove marcações de código e espaços em branco desnecessários
    cleaned_text = re.sub(r'```json\s*|```', '', resposta_texto).strip()

    if not cleaned_text:
        logging.warning("Resposta da IA estava vazia após a limpeza.")
        return []

    try:
        dados_convertidos = ast.literal_eval(cleaned_text)

        if isinstance(dados_convertidos, list):
            logging.info("Resposta da IA interpretada como uma lista de sugestões.")
            return dados_convertidos
        elif isinstance(dados_convertidos, dict):
            if 'sugestoes' in dados_convertidos and isinstance(dados_convertidos['sugestoes'], list):
                logging.info("Resposta da IA interpretada como um dicionário. Extraindo a lista 'sugestoes'.")
                return dados_convertidos['sugestoes']
            else:
                raise ValueError(f"Dicionário JSON não contém a chave 'sugestoes' ou o valor não é uma lista. Resposta recebida: {cleaned_text}")                
        else:
            raise ValueError(f"Resposta da IA não é uma lista ou dicionário válido. Tipo recebido: {type(dados_convertidos)}")
            
    except (ValueError, SyntaxError, TypeError) as e:
        logging.error(f"Erro de parsing ao interpretar a resposta da IA: {e}. Resposta bruta recebida: {resposta_texto}")
        raise
    except Exception as e:
        logging.error(f"Erro genérico inesperado ao interpretar resposta: {e}. Resposta bruta recebida: {resposta_texto}")
        raise
    
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10), # Espera 4s, 8s, 16s... até 10s max
    stop=stop_after_attempt(5), # Tenta 5 vezes
    reraise=True, # Se quiser que a exceção seja propagada após todas as tentativas
    before_sleep=log_custom_before_sleep
)

def sugerir_substituicoes(genai_model, texto_cv, requisitos_vaga, model="gemini-1.5-flash"):
    """
    Gera sugestões de substituição de termos no CV usando a API do Gemini.
    """
    prompt = f"""
Você é um especialista em RH e otimização de currículos. Analise o currículo e os requisitos da vaga abaixo.
Sugira substituições de termos no currículo para que ele se alinhe melhor aos requisitos da vaga.
Concentre-se em trocar jargões internos ou termos menos comuns por palavras-chave presentes na descrição da vaga ou mais reconhecidas no mercado.

**Formato da Resposta:**
Sua resposta deve ser ESTRITAMENTE um array JSON válido (uma lista de objetos JSON). Cada objeto deve conter duas chaves: "original" (o termo do CV) e "substituto" (a sugestão).
NÃO inclua nenhuma explicação, texto introdutório ou formatação extra. Apenas o array JSON.
Seja sucinto e prático, não sugira mais do que 4 itens!

### Exemplo de Saída Esperada:
[
  {{"original": "Termo Antigo 1", "substituto": "Termo Novo 1"}},
  {{"original": "Termo Antigo 2", "substituto": "Termo Novo 2"}}
]

-----------------
{texto_cv}
-----------------
Compare com estes requisitos da vaga:
{requisitos_vaga}
-----------------
"""
    try:
        logger.info(f"Enviando prompt para a IA (modelo: {model})...")
        modelo = genai_model.GenerativeModel(model)
        config = genai.types.GenerationConfig(temperature=0.7, response_mime_type="application/json")
        response = modelo.generate_content(
            prompt,
            generation_config=config
        )
        logger.info(f"DEBUG: repr(response.text) antes de interpretar:\n {repr(response.text)}")

        sugestoes_ia = interpretar_resposta_ia(response.text)
        logger.info(f"DEBUG: Sugestões interpretadas da IA: {sugestoes_ia}")
        return sugestoes_ia
    
    except Exception as e:
        logger.error(f"Ocorreu um erro ao chamar a API: {e}")
        logger.exception("Detalhes do erro na função sugerir_substituicoes")
        raise

def extrair_texto_docx(caminho_arquivo):
    """Extrai texto de um arquivo DOCX."""
    try:
        doc = Document(caminho_arquivo)
        texto = []
        for p in doc.paragraphs:
            texto.append(p.text)
        return "\n".join(texto)
    except Exception as e:
        logger.error(f"Erro ao extrair texto do DOCX '{caminho_arquivo}': {e}")
        sys.exit(1)

# ================= FLUXO PRINCIPAL =================

def main():
    load_dotenv()
    genai_instance = carrega_chave()
    all_vaga_suggestions = []

    try:
        # Carregar informações das configurações (para obter o caminho do CV)
        config_path = os.environ.get('CONFIG_JSON_PATH', 'configs/linkedin.json')
        with open(config_path, "r", encoding="utf-8") as file:
            linkedin_config = json.load(file)
    except Exception as e:
        logger.error(f"Erro ao carregar configuração: {e}")
        sys.exit(1)

    diretorio_cv = linkedin_config["input_file_cv"]

    # Lê as vagas (analisadas) do JSON (entrada via stdin ou arquivo)
    try:
        if stdin_has_data():
            entrada_json = sys.stdin.read().strip()
            logger.info("Lido JSON do stdin.")
        elif len(sys.argv) > 1:
            with open(sys.argv[1]) as f:
                entrada_json = f.read()
            logger.info(f"Lido JSON do arquivo {sys.argv[1]}.")
        else:
            logger.info("Nenhuma entrada de vagas fornecida! Use argumento de arquivo ou STDIN.")
            sys.exit(1)
        vagas_analisadas = json.loads(entrada_json)
        if not isinstance(vagas_analisadas, list):
            # Se for um único objeto, transforme em lista para processamento
            vagas_analisadas = [vagas_analisadas]

    except Exception as e:
        logger.error(f"Erro ao ler entrada de vagas: {e}")
        sys.exit(1)

    texto_cv = extrair_texto_docx(diretorio_cv)

    for vaga_dict in vagas_analisadas:
        analise = vaga_dict.get("analise", {})
        referencia = vaga_dict.get("referencia", {})

        # Extrair código da vaga de forma robusta
        code = referencia.get("Code", "SEM_CODIGO")
        codigo_vaga = str(int(float(code))) if isinstance(code, (int, float, str)) and str(code).isdigit() else str(code)

        logger.info(f"Iniciando geração de sugestões para a vaga: {codigo_vaga}")

        linhas_requisitos = []
        campos_lista = [
            "requisitos_obrigatorios",
            "requisitos_desejaveis",
            "soft_skills",
            "hard_skills"
        ]

        for campo in campos_lista:
            if campo in analise and isinstance(analise[campo], list):
                if analise[campo]: # Adiciona apenas se a lista não estiver vazia
                    linhas_requisitos.append(f"{campo.replace('_',' ').capitalize()}: {', '.join(analise[campo])}")
        
        # Adiciona outros campos que não são listas e não foram processados acima
        for campo, valor in analise.items():
            if campo not in campos_lista and not isinstance(valor, (list, dict)):
                linhas_requisitos.append(f"{campo}: {valor}")
        
        requisitos_texto = "\n".join(linhas_requisitos)

        if not requisitos_texto.strip():
            logger.warning(f"Requisitos de vaga vazios para {codigo_vaga}. Pulando geração de sugestões.")
            continue
        
        logger.info(f"Solicitando sugestões IA para vaga {codigo_vaga}...")
        sugestoes_ia = sugerir_substituicoes(genai_instance, texto_cv, requisitos_texto)
        time.sleep(3)
        logger.info(f"Sugestões recebidas para {codigo_vaga}: {sugestoes_ia}")

        # Adição da correção manual da idade (se ainda for necessária)
        # Idealmente, isso seria configurável ou parte de um pós-processamento separado
        # if sugestoes_ia is not None:
        #     sugestoes_ia.append({"original": "Brasileira, solteira, 52 anos, sem filhos",
        #                          "substituto": "Brasileira, solteira, 53 anos, sem filhos"})
        #     logger.info(f"Adicionada correção manual da idade. Total de sugestões: {len(sugestoes_ia)}")
        # else:
        #     sugestoes_ia = [] # Garante que sugestoes_ia é uma lista

        all_vaga_suggestions.append({
            "codigo": codigo_vaga,
            "referencia": referencia, # Manter a referência completa da vaga
            "sugestoes": sugestoes_ia if sugestoes_ia is not None else []
        })

    # Imprime o JSON consolidado de todas as sugestões para o stdout
    print(json.dumps(all_vaga_suggestions, ensure_ascii=False, indent=2))
    logger.info("Processo de geração de sugestões finalizado.")

if __name__ == "__main__":
    main()