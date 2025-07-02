### Sobre o Projeto

Este projeto automatiza fluxos de análise de vagas de emprego e avaliação de aderência de currículos utilizando [n8n](https://n8n.io/), scripts shell customizados e integração via Docker.  
Inclui um workflow n8n (JSON) que executa os scripts para análise de vagas, gera sugestões de melhorias para currículos, calcula score de aderência e orquestra tudo dentro do ambiente Docker.

---

## 📦 Pré-requisitos

- Docker & Docker Compose instalados
- Acesso ao seu projeto clonado via GitHub
- Arquivo `workflow.json` exportado do n8n
- Scripts e pastas necessários na pasta `/home/seu-usuario/projetos/linkedin-automacao/...`
- Variáveis de ambiente ajustadas no arquivo `.env` (veja abaixo)

---

## 🛠️ Instalação

1. **Clone seu projeto:**
   ```sh
   git clone https://github.com/seuusuario/suarepo.git
   cd suarepo
   ```

2. **Ajuste suas variáveis de ambiente**  
Crie um arquivo .env na raiz do projeto, baseado no exemplo abaixo:
```.env
#Configuração da aplicação
LINKEDIN_EMAIL=seu_email@exemplo.com
LINKEDIN_PASSWORD=sua_senha_linkedin
GEMINI_API_KEY=sua_chave_gemini
CONFIG_JSON_PATH=configs/linkedin.json

VERTEX_PROJECT=nome-do-projeto-vertex
VERTEX_REGION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/caminho/para/application_default_credentials.json

#Configuração para o n8n
SUBDOMAIN=nome-do-subdominio
DOMAIN_NAME=seu-dominio.com
N8N_RUNNERS_ENABLED=true
GENERIC_TIMEZONE=America/Sao_Paulo
DATA_FOLDER=/caminho/para/.n8n

#Usuários (UID e GID)
UID=1002
GID=1002
 ```

**Configuração das buscas e processamento (config.json)**

O arquivo config.json guarda os parâmetros e caminhos usados nos fluxos automatizados.

Exemplo: config.example.json

```json
{
  "keyword": ""COORDENADOR DE PROJETOS" OR "Project Manager" OR "Scrum Master"",
  "location": "Brasil",
  "driver_path": "chromedriver-linux64/chromedriver",
  "data_dir": "dados",
  "input_file_jobs": "dados/entrada/job_details.xlsx",
  "input_file_cv": "dados/cv/CV - Nome do Candidato.docx",
  "output_file_requirements": "output/analise_vagas_resultados.json",
  "output_file_error_requirements": "output/erros_analise_vagas.json",
  "output_file_score": "output/score.json",
  "output_dir": "output/",
  "log_dir": "logs/",
  "config_dir": "configs/",
  "col_linkedin_job_code": "Code",
  "col_linkedin_job_description": "Job Description"
}

```
```table
Descrição de cada chave
Chave	                           Descrição
keyword	                        Termos e cargos a buscar no LinkedIn
location	                        Localização das vagas
driver_path	                     Path do ChromeDriver
data_dir	                        Diretório dos dados de entrada
input_file_jobs	               Caminho para Excel de vagas abertas
input_file_cv	                  Caminho para o CV do candidato
output_file_requirements	      Saída dos requisitos extraídos das vagas
output_file_error_requirements	Saídas em caso de erro na análise das vagas
output_file_score	               Resultado do score entre vaga e CV
output_dir	                     Diretório de saída dos arquivos gerados
log_dir	                        Diretório dos logs
config_dir	                     Diretório dos arquivos de configuração
col_linkedin_job_code	         Nome da coluna do código da vaga
col_linkedin_job_description	   Nome da coluna da descrição da vaga
```
---
## 🐍 Requisitos de instalação
1. **Dependências Python**

**(Recomendado) Crie um ambiente virtual**
   ```sh
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```
**Instale as dependências**
   ```sh
pip install -r requirements.txt
   ```

## 🐳 Deploy com Docker/Docker Compose
Dockerfile e docker-compose.yml estão na raiz do projeto:

**Build & start all services**
   ```sh
docker-compose up --build
   ```

O serviço web ficará disponível em http://localhost:5678

Os dados persistem no volume local ./data

Variáveis são gerenciadas via arquivo .env

Para customizar, edite o arquivo docker-compose.yml

## 🔁 Importação de Workflow no n8n
**Passos para importar o workflow do n8n**

1. Acesse seu painel do n8n (⛓️ ex: http://localhost:5678).
2. Clique no menu de workflows > "Import".
3. Selecione o arquivo `workflows/linkdin.json`.
4. Configure as credenciais que forem solicitadas (conferir variáveis no .env/config.json).
5. Ative o workflow.

## 📂 Estrutura das Pastas

```
├── configs/
│   └── linkedin.json
├── dados/
│   ├── entrada/
│   └── cv/
├── output/
├── logs/
├── src/
│   ├── busca_vagas.py
│   ├── analisar_curriculo.py
│   └── ...
├── .env.example
├── config.example.json
├── requirements.txt
└── README.md
```

---

## 🚦 Como usar

1. **Importe o workflow no n8n**

- Acesse n8n pelo navegador (`http://localhost:5678` ou pela URL do domínio configurado)
- Importe o arquivo JSON do workflow (Menu > Import > cole o conteúdo do JSON enviado acima)

2. **Ajuste os scripts e permissões**

Certifique-se de que seus scripts shell (`run_linkedin.sh`, `run_cv_otimizado.sh`, `run_aderencia.sh`) estão funcionando e têm permissão de execução:

```sh
chmod +x linkedin-automacao/*.sh
```

3. **Dispare o fluxo**

**Ao inserir (ou alterar) um arquivo na pasta `/data/linkedin-automacao/dados/entrada`, o workflow será disparado automaticamente, seguindo a lógica definida:**

| 1. Trigger observa a pasta de entrada local. |
|---|


2. Executa o script de análise de vagas do LinkedIn.
3. Converte e padroniza o JSON gerado.
4. Executa os scripts para sugestão de melhoria de CV e análise de aderência.
5. Faz um merge dos resultados.

---

## 🔁 Atualizando os Workflows

Para novas versões do seu workflow, basta exportar do n8n e substituir o arquivo LINKDIN.JSON no projeto.

---

## 📝 Notas

- Recomendável expor o serviço atrás de um proxy reverso (NGINX, Traefik, etc) para produção.
- Se usar scripts que dependem de bibliotecas Python, instale suas dependências via `requirements.txt` no Dockerfile.
- Variáveis podem ser customizadas conforme necessário.
- O workflow pode ser expandido para outras integrações além do LinkedIn.

---
