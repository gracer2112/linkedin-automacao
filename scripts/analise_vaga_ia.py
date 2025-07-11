#analise_vaga_ia.py
import sys
from dotenv import load_dotenv
import os
import json
import logging
import time

import google.generativeai as genai
from google.generativeai import types
from google.auth import default # Para carregar credenciais automaticamente
import pandas as pd

# ================= LOGGING SETUP =================
loglevel = os.environ.get("MY_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=loglevel,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ==== PASSO 1: Carregar variáveis de ambiente seguras ====
load_dotenv()  # Carrega automaticamente as variáveis do .env

def carrega_chave():
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        log_erro("Chave de API do Google não encontrada (GEMINI_API_KEY).")
        sys.exit(1)
        
    genai.configure(api_key=gemini_api_key)
    return genai


def log_erro(msg):
    """Escreve um erro formatado no stderr (como JSON)."""
    sys.stderr.write(json.dumps({"error": str(msg)}, ensure_ascii=False, indent=2) + '\n')
    sys.stderr.flush()

# Carregando configurações do linkedin.json
def carregar_configuracoes_json(caminho_config='configs/linkedin.json'):
    try:
        with open(caminho_config, 'r', encoding='utf-8') as f:
            configs = json.load(f)
        return configs
    except Exception as e:
        log_erro(f"Erro ao carregar configurações: {e}")
        sys.exit(1)

# ==== PASSO 4: Salvar resultados e erros em JSON ====
def salvar_json(dados, caminho):
    try:
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log_erro(f"Erro ao salvar JSON ({caminho}): {e}")

# ==== PASSO 3: Função para ler dados ====
def ler_vagas_do_excel(arquivo_excel, coluna_visualizado="Visualizado"):
    try:
        if not os.path.isfile(arquivo_excel):
            raise FileNotFoundError(f"Arquivo {arquivo_excel} não encontrado.")
        df = pd.read_excel(arquivo_excel)

        if coluna_visualizado in df.columns:
            df_visualizado = df[df[coluna_visualizado].isna() | (df[coluna_visualizado] == "")].copy()
        else:
            df_visualizado = df  # Se não existir, processa tudo

        #df_visualizado = df_visualizado.head(2) #comentar após testar
        return df_visualizado  # DataFrame 
    except Exception as e:
        log_erro(f"Erro ao ler o Excel: {e}")
        sys.exit(1)

# ==== PASSO 2: Função para análise de vaga (usando a API do Gemini) ====
def analisar_vaga(genai, texto_vaga, indice,codigo,modelo="gemini-1.5-flash"):
#def analisar_vaga(genai, texto_vaga, indice,codigo,modelo="gemini-2.5-flash-preview-05-20"):
    result = None

    prompt = f"""
    Aja como um analista de RH.
    Analise a seguinte descrição de vaga e extraia as informações solicitadas no formato JSON.
    O JSON deve ter a seguinte estrutura e incluir apenas as chaves mencionadas:
    {{
    "titulo": "",
    "localizacao": "",
    "senioridade": "",
    "requisitos_obrigatorios": [],
    "requisitos_desejaveis": [],
    "soft_skills": [],
    "hard_skills": []
    }}
    Descrição da vaga:
    {texto_vaga}
    """
    generate_text=""

    if pd.isna(texto_vaga) or not isinstance(texto_vaga, str) or texto_vaga.strip() == "":
        log_erro(f"Descrição da vaga {indice+1} {codigo} está vazia ou inválida. Pulando.")
        return None, "vaga vazia ou inválida"
               
    try:
        modelo = genai.GenerativeModel(modelo)
        logging.info(f"\nAnalisando a vaga {indice + 1}  {codigo}")
    except Exception as e:
        log_erro(f"Erro ao carregar o modelo: {e}")
        return None, f"Erro ao carregar o modelo: {e}"

    try:
        # Chamada para gerar o conteúdo
        config =  genai.types.GenerationConfig(temperature=0.7,response_mime_type="application/json")
        result = modelo.generate_content(
            prompt,  # Usando a nova API com Part
            generation_config=config
            )
    except Exception as e:
        log_erro(f"Erro ao chamar a API do modelo: {e}")
        return None, f"Erro ao chamar o modelo: {e}"

    # Limpa o texto removendo espaços extras e quebras de linha
    texto_limpo = result.text.strip()

    # Remover os marcadores de bloco de código Markdown
    if texto_limpo.startswith("```json"):
        texto_limpo = texto_limpo[len("```json"):]
    if texto_limpo.startswith("```"): # Caso seja apenas ```
        texto_limpo = texto_limpo[len("```"):]
    if texto_limpo.endswith("```"):
        texto_limpo = texto_limpo[:-len("```")]
    
    # Remove markdown code blocks (tolerando espaçamentos)
    texto_limpo = texto_limpo.replace("```json", "").replace("```", "").strip()

    try:
        # Certifique-se de que cleaned_text não está vazio após a limpeza
        if not texto_limpo:
            raise json.JSONDecodeError("String vazia após limpeza dos marcadores", "", 0)
        
        dados_json = json.loads(texto_limpo)

        return dados_json, None

    except json.JSONDecodeError as e:
        log_erro(f"Erro ao decodificar JSON após strip para a vaga {indice} {codigo}: {e}")
        #log_erro(f"Conteúdo problemático (após strip): {repr(texto_limpo)}")
        return None, f"Erro ao decodificar JSON: {e}"

    except Exception as e:
        log_erro(f"Erro inesperado ao processar a vaga {indice} {codigo}: {e}")
        return None, f"Erro inesperado: {e}"

# ==== PASSO 5: Função principal de processamento ====
def processar_todas_as_vagas_excel(config_cam):
    # Lê configurações
    arquivo_entrada = config_cam['input_file_jobs']
    arquivo_saida = config_cam['output_file_requirements']
    arquivo_erro = config_cam.get('output_file_error_requirements', "erros_analise_vagas.json")
    coluna_descricao = config_cam.get('col_linkedin_job_description', "Description")
    coluna_codigo = config_cam.get('col_linkedin_job_code', "Code")
    coluna_visualizado = config_cam.get('col_linkedin_job_visualizado', "Visualizado")   

    df = ler_vagas_do_excel(arquivo_entrada, coluna_visualizado)
    resultados_analise = []
    erros_analise = []

    genai=carrega_chave()

    for idx, row in df.iterrows():
        texto_vaga = row.get(coluna_descricao, "")
        logging.info(f"Processando vaga {idx+1} de {len(df)}...")
        resultado, erro = analisar_vaga(genai, texto_vaga,idx, row.get("Code"))
        vaga_dict = row.to_dict()

        code = vaga_dict.get("Code")
        if pd.notna(code) and code != "":
            try:
                codigo_final = str(int(float(code)))
            except (ValueError, TypeError):
                codigo_final = str(code)
        else:
            codigo_final = ""        

        ref = {
            "Code": codigo_final,
            "Company": vaga_dict.get("Company") if pd.notna(vaga_dict.get("Company")) else "",
            "Link": vaga_dict.get("Link") if pd.notna(vaga_dict.get("Link")) else "",
        }

        if resultado is not None:
            resultados_analise.append({
                "analise": resultado,
                "referencia": {
                "Code": ref["Code"],
                "Company": ref["Company"],
                "Link": ref["Link"],
                }
            })
        else:
            log_erro(f"Erro na vaga {idx+1}: {erro}")
            erros_analise.append({
                "Code": ref["Code"],
                "erro": erro
            })
            
        time.sleep(1)  # Respeita limites de API

    salvar_json(resultados_analise, arquivo_saida)
    if erros_analise:
        salvar_json(erros_analise, "erros_analise_vagas.json")
        logging.info(f"\n{len(resultados_analise)} vagas processadas com sucesso.")
        logging.info(f"{len(erros_analise)} vagas tiveram erro. Veja 'erros_analise_vagas.json'.")
    else:
        logging.info(f"\nSucesso! Todas as {len(resultados_analise)} vagas processadas.")
        # n8n espera saída via STDOUT
    return resultados_analise        

# ==== PASSO 6: Execução Principal ====
if __name__ == "__main__":
    # Entrada do n8n: caminho do JSON de config
    config_path = os.environ.get('CONFIG_JSON_PATH', 'configs/linkedin.json')
    config = carregar_configuracoes_json(config_path) 
    saida=processar_todas_as_vagas_excel(config)


    # Retorno apropriado para n8n
    print(json.dumps(saida, ensure_ascii=False, indent=2))
