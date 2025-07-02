from dotenv import load_dotenv
import sys
import os
import select
import logging

load_dotenv()  # Carrega as variáveis do .env

# ================= LOGGING SETUP =================
loglevel = os.environ.get("MY_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=loglevel,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def checa_credenciais_google():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        msg = (
            "ERRO: Variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não está definida ou o arquivo não existe.\n"
            "Defina a variável antes de rodar o programa.\n"
            "\n"
            "Exemplo no terminal Linux/Mac:\n"
            'export GOOGLE_APPLICATION_CREDENTIALS="/caminho/para/sua/credencial.json"\n'
            "Exemplo em código (NÃO recomendado para produção):\n"
            'os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/caminho/para/sua/credencial.json"\n'
        )
        sys.stderr.write(msg)
        sys.exit(1)
    else:
         logging.info(f"💡 Usando credenciais do arquivo: {cred_path}")

# Use sempre este check ANTES de importar qualquer SDK Google:
checa_credenciais_google()

import json
import vertexai
from vertexai.language_models import TextEmbeddingModel
import google.generativeai as genai
from google.generativeai import types
from google.auth import default # Para carregar credenciais automaticamente

from docx import Document
import numpy as np


def stdin_has_data():
    return not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.1)[0]

def ler_config(path_config):
    with open(path_config, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config

def extrair_texto_docx(cv_file):
    # Abre o documento
    document = Document(cv_file)

    return "\n".join([p.text for p in document.paragraphs])

def criar_embedding_batch(texto,modelo_nome):

    PROJECT_ID = os.environ.get('VERTEX_PROJECT', 'n8n-automatizando-ia-424719')
    REGION = os.environ.get('VERTEX_REGION', 'us-central1')

    vertexai.init(project=PROJECT_ID, location=REGION)
    # Inicializa o modelo de embedding
    modelo = TextEmbeddingModel.from_pretrained(modelo_nome)

    # Verifica se a entrada é uma string para sabermos como retornar o resultado
    is_single_item = isinstance(texto, str)

    # A API sempre espera uma lista, então garantimos isso aqui.
    # Se for uma string, a transformamos em uma lista com um único item.
    # Se já for uma lista, a usamos diretamente.
    payload = [texto] if is_single_item else texto

    # Caso uma lista vazia seja passada, retorna uma lista vazia para evitar erro na API
    if not payload:
        return []

    # Gera o embedding para o texto do CV
    try:
        embeddings_response = modelo.get_embeddings(payload)
        # Extrai os valores numéricos de cada objeto de embedding retornado
        vetores = [emb.values for emb in embeddings_response]

        # Se a entrada original era uma string, retorna apenas o primeiro (e único) vetor.
        # Caso contrário, retorna a lista completa de vetores.
        if is_single_item:
            return vetores[0]
        else:
            return vetores

    except Exception as e:
        raise RuntimeError(f"Erro ao gerar o embedding: {e}")


def calcular_similaridade(vetor_a, vetor_b):
    return float(np.dot(vetor_a, vetor_b) / (np.linalg.norm(vetor_a) * np.linalg.norm(vetor_b) + 1e-8))

# Adapte a função comparar_cv_vagas para receber código e descrição
def comparar_cv_vagas(cv_texto, vagas, modelo_embedding="text-multilingual-embedding-002", codigo_col="Code", descricao_col="Job Description"):

    resultado_ranking = []
    emb_cv = criar_embedding_batch(cv_texto, modelo_embedding)

    sys.stderr.write(f"Total de vagas: {len(vagas)}\n")

    for idx, vaga in enumerate(vagas):
        codigo = vaga['referencia'].get('Code')
        sys.stderr.write(f"Código da vaga {idx}: {codigo}\n")

        analise = vaga.get("analise", {}) 
        referencia = vaga.get('referencia', {})
        if not analise:  # Pula se o item não tiver a chave "vaga"
            logging.info(f"[IGNORADA] Vaga {codigo}: sem campo 'analise'.", file=sys.stderr)

        # Pega a descrição usando o nome da coluna dinâmico do seu JSON
        descricao = analise.get(descricao_col, "")
        logging.info("VAGA RECEBIDA:", vaga)
        logging.info("CHAVES:", vaga.keys())

        # Adapte para obter requisitos obrigatórios/desejáveis
        #reqs = vaga.get("requisitos_obrigatorios", []) + vaga.get("requisitos_desejaveis", [])
        obrigatorios = analise.get('requisitos_obrigatorios', [])
        desejaveis   = analise.get('requisitos_desejaveis', [])
        reqs = obrigatorios + desejaveis

        if not reqs:
            logging.info(f"[IGNORADA] Vaga {codigo}: sem requisitos obrigatórios nem desejáveis.", file=sys.stderr)
            continue

        logging.info(f"[PROCESSADA] Vaga {codigo}: processando normalmente.", file=sys.stderr)

        emb_reqs = criar_embedding_batch(reqs, modelo_embedding)
        logging.info("embedding retornado reqs:", emb_reqs)

        scores = [calcular_similaridade(emb_cv, emb_req) for emb_req in emb_reqs]

        if not scores: # Segurança extra para evitar divisão por zero
            continue

        detalhes = [
            {"requisito": req, "score": round(score, 4)}
            for req, score in zip(reqs, scores)
        ]
        score_geral = round(sum(scores) / len(scores), 4)
        resultado_ranking.append({
            "codigo": referencia.get(codigo_col, ""),
            "similaridade_geral": score_geral,
            "detalhes": detalhes
        })

    resultado_ranking.sort(key=lambda x: x["similaridade_geral"], reverse=True)
    return resultado_ranking


def main():

    config_path = os.environ.get('CONFIG_JSON_PATH', 'configs/linkedin.json')    
    config = ler_config(config_path)

    # Lê configurações
    vagas_json_path  = config['output_file_requirements']
    cv_docx_path  = config['input_file_cv']
    diretorio_saida = config['output_file_score']

    # Extrai texto do CV (.docx)
    cv_texto = extrair_texto_docx(cv_docx_path)

    # Lê as vagas do JSON no n8n como a entrada é via stdin a linha de baixo não é necesspara
    if stdin_has_data():
        entrada_json = sys.stdin.read()
    elif len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            entrada_json = f.read()
    else:
        logging.info("Nenhuma entrada fornecida! Use argumento de arquivo ou STDIN.")
        exit(1)

    vagas = json.loads(entrada_json)

    print("Tipo de vagas:", type(vagas), file=sys.stderr)
    print("Primeiro item de vagas:", vagas[0] if isinstance(vagas, list) else vagas, file=sys.stderr)

    # Se não é lista, faz virar lista
    if isinstance(vagas, dict):
        vagas = [vagas]
    elif not isinstance(vagas, list):
        raise ValueError("Formato de entrada inválido: deve ser lista ou objeto com chaves 'analise'/'referencia'.")

    ranking = comparar_cv_vagas(cv_texto, vagas)

    # Salva no arquivo
    with open(diretorio_saida, "w", encoding="utf-8") as f:
        f.write(json.dumps(ranking, ensure_ascii=False, indent=2))

    return ranking

if __name__ == '__main__':
    try:
        resultado = main()
        print(json.dumps(resultado, ensure_ascii=False))
    except Exception as e:
        sys.stderr.write(json.dumps({"error": str(e)},ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)    