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
   Crie um arquivo `.env` (ou ajuste as variáveis diretamente no `docker-compose.yml`), exemplo:
   ```
   DOMAIN_NAME=seudominio.com
   SUBDOMAIN=n8n
   GENERIC_TIMEZONE=America/Sao_Paulo
   UID=1000
   GID=1000
   DATA_FOLDER=/caminho/para/sua/pasta/n8ndata
   ```

3. **Construa e suba os containers:**
   ```sh
   docker-compose up --build -d
   ```

---

## 📂 Estrutura das Pastas

```
projeto-root/
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
└── linkedin-automacao/
      ├── run_linkedin.sh
      ├── run_cv_otimizado.sh
      ├── run_aderencia.sh
      ├── output/
      │     └── analise_vagas_resultados.json
      └── dados/
            └── entrada/
```

---

## 🚦 Como usar

### 1. Importe o workflow no n8n

- Acesse n8n pelo navegador (`http://localhost:5678` ou pela URL do domínio configurado)
- Importe o arquivo JSON do workflow (Menu > Import > cole o conteúdo do JSON enviado acima)

### 2. Ajuste os scripts e permissões

Certifique-se de que seus scripts shell (`run_linkedin.sh`, `run_cv_otimizado.sh`, `run_aderencia.sh`) estão funcionando e têm permissão de execução:

```sh
chmod +x linkedin-automacao/*.sh
```

### 3. Dispare o fluxo

### Ao inserir (ou alterar) um arquivo na pasta `/data/linkedin-automacao/dados/entrada`, o workflow será disparado automaticamente, seguindo a lógica definida:

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
