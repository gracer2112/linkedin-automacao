# dockerfile
# Estágio 1: Builder de dependências e N8N
# Começamos com uma imagem Node.js que inclui o apt-get
FROM node:22-bullseye-slim AS builder

# Instalação de dependências de sistema (Python, Java, LibreOffice, Bash, Tree)
USER root
RUN apt-get update -y --no-install-recommends && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        libreoffice \
        openjdk-11-jdk \
        bash \
        tree \
    # Limpa o cache do apt para manter o tamanho da imagem menor
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Instala o n8n globalmente via npm. Usaremos a versão 2.9.3 para garantir o patch de segurança.
# Você pode usar 'n8n@latest' se quiser sempre a versão mais recente da série 2.x.
RUN npm install -g n8n@2.9.4

# Cria o usuário e grupo dedicados para a aplicação
# Cria o usuário e grupo dedicados para a aplicação
RUN groupadd --gid 1002 user1002 && \
    useradd --uid 1002 --gid 1002 --no-create-home --home-dir /data/linkedin-automacao/tmp_home_1002 user1002

# Cria virtualenv isolado para dependências Python
RUN python3 -m venv /opt/venv && \
    chown -R user1002:user1002 /opt/venv

# Copia o requirements.txt para dentro do container
COPY requirements.txt .

# Instala as dependências Python usando o pip do venv.
RUN /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --break-system-packages --use-deprecated=legacy-resolver -r requirements.txt

# Define variáveis de ambiente que são importantes para o Python e para o PATH.
ENV HOME=/data/linkedin-automacao/tmp_home_1002
RUN mkdir -p /data/linkedin-automacao/tmp_home_1002 && \
    mkdir -p /data/linkedin-automacao/tmp_home_1002/.n8n && \
    mkdir -p /data/linkedin-automacao/output && \
    chown -R user1002:user1002 /data/linkedin-automacao/tmp_home_1002 && \
    chown -R user1002:user1002 /data/linkedin-automacao/output 
    
ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Define o diretório de trabalho principal para a aplicação
WORKDIR /data/linkedin-automacao

# Copia o restante dos arquivos da sua aplicação para o container
COPY . .
RUN chown -R user1002:user1002 /data/linkedin-automacao

# Retorna o usuário padrão do n8n para segurança
USER user1002

# Expõe a porta que o n8n utiliza
EXPOSE 5678

# Comando padrão para quando o container é iniciado (pode ser sobrescrito pelo docker-compose)
CMD ["n8n"]