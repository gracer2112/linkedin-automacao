### Sobre o Projeto

Automatize buscas de vagas, análise de requisitos e comparação com currículos usando integração com LinkedIn, APIs do Google Vertex, Gemini e fluxo com o n8n.

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
### Níveis de Log Disponíveis

```bash
| Nível     | Comando de Exemplo              |Descrição                                                                                                                                                         |
|-----------|---------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `DEBUG`   | `export MY_LOG_LEVEL=DEBUG`     | Mostra **todas** as mensagens. Útil para diagnóstico profundo de problemas.                                                                                      |
| `INFO`    | `export MY_LOG_LEVEL=INFO`      | Mostra mensagens informativas, como o progresso da execução e tentativas de reconexão (`retry`). **Recomendado para desenvolvimento e para acompanhar o fluxo.** |
| `WARNING` | `export MY_LOG_LEVEL=WARNING`   | Mostra apenas avisos e erros. O script não para, mas algo inesperado ocorreu. **Recomendado para execução em produção.**                                         |
| `ERROR`   | `export MY_LOG_LEVEL=ERROR`     | Mostra apenas mensagens de erros que podem ter interrompido uma tarefa específica.                                                                               |

```
### Como Executar

O script principal é executado através de um shell script que recebe dados via `stdin`.

**Estrutura do comando:**
```bash
cat [ARQUIVO_DE_ENTRADA] | ./[SCRIPT_DE_EXECUCAO].sh
```

**Exemplo real:**
```bash
cat /data/linkedin-automacao/output/analise_vagas_resultados.json | /data/linkedin-automacao/run_cv_sugestor.sh
```

---

### Exemplos Práticos de Execução

#### 1. Para Desenvolvimento (Ver logs de `retry`)

Para ver o fluxo completo da aplicação, incluindo as mensagens de "Tentando novamente...", use o nível `INFO`.

```bash
# Define o nível do log para INFO
export MY_LOG_LEVEL=INFO

# Executa o script
cat /data/linkedin-automacao/output/analise_vagas_resultados.json | /data/linkedin-automacao/run_cv_sugestor.sh
```

#### 2. Para Produção (Execução silenciosa)

Para rodar o script de forma mais limpa, mostrando apenas avisos importantes e erros, use o nível `WARNING`.

```bash
# Define o nível do log para WARNING
export MY_LOG_LEVEL=WARNING

# Executa o script
cat /data/linkedin-automacao/output/analise_vagas_resultados.json | /data/linkedin-automacao/run_cv_sugestor.sh
```

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
| Chave                            | Descrição                                                  |
|----------------------------------|------------------------------------------------------------|
| `keyword`                        | Termos e cargos a buscar no LinkedIn                       |
| `location`                       | Localização das vagas                                      |
| `driver_path`                    | Path do ChromeDriver                                       |
| `data_dir`                       | Diretório dos dados de entrada                             |
| `input_file_jobs`                | Caminho para Excel de vagas abertas                        |
| `input_file_cv`                  | Caminho para o CV do candidato                             |
| `output_file_requirements`       | Saída dos requisitos extraídos das vagas                   |
| `output_file_error_requirements` | Saídas em caso de erro na análise das vagas                |
| `output_file_score`              | Resultado do score entre vaga e CV                         |
| `output_dir`                     | Diretório de saída dos arquivos gerados                    |
| `log_dir`                        | Diretório dos logs                                         |
| `config_dir`                     | Diretório dos arquivos de configuração                     |
| `col_linkedin_job_code`          | Nome da coluna do código da vaga                           |
| `col_linkedin_job_description`   | Nome da coluna da descrição da vaga                        |

---
**Formato dos Arquivos de Entrada**

Os scripts deste projeto dependem de um formato específico para os dados de entrada, garantindo que as informações necessárias para a análise e sugestão sejam processadas corretamente.

*Arquivo Excel de Vagas (para analise_vaga_ia.py)*

Este é o arquivo de entrada inicial que contém as vagas a serem analisadas. O script analise_vaga_ia.py espera um arquivo Excel (.xls ou .xlsx) com as seguintes colunas. É crucial que os nomes das colunas correspondam exatamente ao que é esperado pelo script.

<table class="data-table">
  <thead>
    <tr>
      <th scope="col">Coluna Necessária</th>
      <th scope="col">Tipo</th>
      <th scope="col">Descrição</th>
      <th scope="col">Configuração Via <code>linkedin.json</code> / <code>.env</code> (Padrão)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>&lt;nome_da_coluna_descrição&gt;</code></td>
      <td><code>string</code></td>
      <td><strong>Obrigatória.</strong> Contém a descrição completa da vaga. O nome desta coluna é configurável pela chave <code>col_linkedin_job_description</code>, e <strong>DEVE corresponder exatamente ao nome da coluna no seu Excel (ex: <code>job_description</code>).</strong></td>
      <td><code>col_linkedin_job_description</code> (Padrão: <code>"Description"</code>)</td>
    </tr>
    <tr>
      <td><code>Code</code></td>
      <td><code>string</code></td>
      <td><strong>Obrigatória.</strong> Contém o identificador único para cada vaga. <strong>O script <code>analise_vaga_ia.py</code> acessa esta coluna pelo nome literal <code>"Code"</code>. A coluna no seu Excel DEVE ser nomeada <code>Code</code> (com "C" maiúsculo).</strong></td>
      <td><code>col_linkedin_job_code</code> (Padrão: <code>"Code"</code>)</td>
    </tr>
    <tr>
      <td><code>Visualizado</code></td>
      <td><code>string</code></td>
      <td>Coluna utilizada para filtrar vagas já processadas. Vagas com valor <code>NaN</code> (vazio) ou <code>""</code> (string vazia) nesta coluna serão processadas. O nome desta coluna é configurável pela chave <code>col_linkedin_job_visualizado</code>. <strong>(No <code>job_details.xlsx</code> fornecido, a coluna <code>muito_antigo</code> pode ser mapeada para esta chave via configuração).</strong></td>
      <td><code>col_linkedin_job_visualizado</code> (Padrão: <code>"Visualizado"</code>)</td>
    </tr>
    <tr>
      <td><code>Company</code></td>
      <td><code>string</code></td>
      <td>Nome da empresa associada à vaga. <strong>O script <code>analise_vaga_ia.py</code> acessa esta coluna pelo nome literal <code>"Company"</code>. A coluna no seu Excel DEVE ser nomeada <code>Company</code> (com "C" maiúsculo).</strong></td>
      <td>N/A</td>
    </tr>
    <tr>
      <td><code>Link</code></td>
      <td><code>string</code></td>
      <td>URL da vaga no LinkedIn ou outra plataforma. <strong>O script <code>analise_vaga_ia.py</code> acessa esta coluna pelo nome literal <code>"Link"</code>. A coluna no seu Excel DEVE ser nomeada <code>Link</code> (com "L" maiúsculo).</strong></td>
      <td>N/A</td>
    </tr>
    <tr>
      <td><code>[Outras Colunas Opcionais]</code></td>
      <td><code>variado</code></td>
      <td>Quaisquer outras colunas presentes no Excel serão lidas, mas não são processadas diretamente pelo <code>analise_vaga_ia.py</code> para a análise principal. Podem ser úteis para metadados ou para outros scripts da sua automação.</td>
      <td>N/A</td>
    </tr>
  </tbody>
</table>

*Exemplo de Conteúdo do Excel (Folha Sheet1):*

Abaixo, um exemplo com os nomes de coluna padrão (Description, Visualizado) e os nomes fixos (Code, Company, Link).

| Code     | Description                                                         | Company             | Link                                     | Visualizado | Localização     |
| :------- | :------------------------------------------------------------------ | :------------------ | :--------------------------------------- | :---------- | :-------------- |
| VAGA_001 | Desenvolvedor Python com experiência em Django e Docker.             | Tech Solutions Inc. | `https://www.linkedin.com/jobs/12345`  |             | Remoto          |
| VAGA_002 | Analista de Dados Pleno com Power BI e SQL.                         | Data Insights Ltda. | `https://www.linkedin.com/jobs/67890`  |             | São Paulo       |
| VAGA_003 | Especialista em Cloud AWS e Kubernetes.                             | Cloud Innovators     | `https://www.linkedin.com/jobs/abcde`  | `sim`       | Rio de Janeiro  |

_analise_vagas_resultados.json_

Este arquivo é a saída esperada do processo de análise de vagas e serve como entrada para scripts como o cv_sugestor.py e aderencia_cv_vaga_ia.py. Ele deve ser um array JSON, onde cada objeto representa uma vaga analisada e contém as seguintes chaves:

<table class="data-table"> 
  <thead>
    <tr>
      <th scope="col">Chave</th>
      <th scope="col">Tipo</th>
      <th scope="col">Descrição</th>
      <th scope="col">Exemplo (conteúdo real)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>analise</code></td>
      <td><code>object</code></td>
      <td>Objeto contendo a análise estruturada da vaga, conforme extraída pela IA (Gemini). Inclui:
          <li><code>titulo</code> (string): Título da vaga.</li>
          <li><code>localizacao</code> (string): Localização da vaga.</li>
          <li><code>senioridade</code> (string): Nível de senioridade.</li>
          <li><code>requisitos_obrigatorios</code> (array de strings): Lista de requisitos obrigatórios.</li>
          <li><code>requisitos_desejaveis</code> (array de strings): Lista de requisitos desejáveis.</li>
          <li><code>soft_skills</code> (array de strings): Lista de soft skills.</li>
          <li><code>hard_skills</code> (array de strings): Lista de hard skills.</li>
      </td>
      <td><code>{<br>&nbsp;&nbsp;"titulo": "Desenvolvedor Python",<br>&nbsp;&nbsp;"localizacao": "Remoto",<br>&nbsp;&nbsp;"senioridade": "Pleno",<br>&nbsp;&nbsp;"requisitos_obrigatorios": ["Python", "Django", "SQL"],<br>&nbsp;&nbsp;"requisitos_desejaveis": ["Docker", "Kubernetes"],<br>&nbsp;&nbsp;"soft_skills": ["Comunicação", "Trabalho em Equipe"],<br>&nbsp;&nbsp;"hard_skills": ["Desenvolvimento Backend"]<br>}</code></td>
    </tr>
    <tr>
      <td><code>referencia</code></td>
      <td><code>object</code></td>
      <td>Objeto contendo as informações de referência da vaga, provenientes do arquivo de entrada (Excel). Inclui:
          <li><code>Code</code> (string): Identificador único da vaga.</li>
          <li><code>Company</code> (string): Nome da empresa.</li>
          <li><code>Link</code> (string): URL da vaga original.</li>
      </td>
      <td><code>{<br>&nbsp;&nbsp;"Code": "VAGA_001",<br>&nbsp;&nbsp;"Company": "Tech Solutions Inc.",<br>&nbsp;&nbsp;"Link": "https://www.linkedin.com/jobs/12345"<br>}</code></td>
    </tr>
  </tbody>
</table>                          |

*Exemplo de Estrutura do JSON:*

```json
[
  {
    "analise": {
      "titulo": "Desenvolvedor Python Pleno",
      "localizacao": "Remoto",
      "senioridade": "Pleno",
      "requisitos_obrigatorios": [
        "Python",
        "Django",
        "SQL"
      ],
      "requisitos_desejaveis": [
        "Docker",
        "Kubernetes"
      ],
      "soft_skills": [
        "Comunicação",
        "Trabalho em Equipe"
      ],
      "hard_skills": [
        "Desenvolvimento Backend"
      ]
    },
    "referencia": {
      "Code": "VAGA_001",
      "Company": "Tech Solutions Inc.",
      "Link": "https://www.linkedin.com/jobs/12345"
    }
  },
  {
    "analise": {
      "titulo": "Analista de Dados",
      "localizacao": "São Paulo",
      "senioridade": "Pleno",
      "requisitos_obrigatorios": [
        "Análise de Dados",
        "SQL",
        "Power BI"
      ],
      "requisitos_desejaveis": [
        "Excel avançado",
        "Storytelling"
      ],
      "soft_skills": [
        "Pensamento Analítico"
      ],
      "hard_skills": [
        "Visualização de Dados"
      ]
    },
    "referencia": {
      "Code": "VAGA_002",
      "Company": "Data Insights Ltda.",
      "Link": "https://www.linkedin.com/jobs/67890"
    }
  }
]
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
