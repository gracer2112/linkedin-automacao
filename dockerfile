FROM n8nio/n8n:latest

# Instala Python e pip
USER root
RUN apk add --no-cache  python3 py3-pip libreoffice openjdk8-jre

# Cria virtualenv isolado para dependências Python
RUN python3 -m venv /data/venv

# Dá permissão de leitura (e execução) ao venv para o usuário node
RUN chown -R node:node /data/venv

# Copia o requirements.txt para dentro do container
COPY requirements.txt /data/requirements.txt

# Use o pip do venv diretamente
RUN /data/venv/bin/pip install --upgrade pip && \
    /data/venv/bin/pip install --break-system-packages -r /data/requirements.txt

# Criação do user1002 e home
RUN addgroup -g 1002 user1002 && \
    adduser -D -u 1002 -G user1002 -h /data/linkedin-automacao/tmp_home_1002 user1002
RUN mkdir -p /data/linkedin-automacao/tmp_home_1002 && \
    chown -R user1002:user1002 /data/linkedin-automacao/tmp_home_1002

# Supondo que você crie o diretório de alguma forma
RUN mkdir -p /data/linkedin-automacao/output
RUN chown -R node:node /data/linkedin-automacao/output

ENV HOME=/data/linkedin-automacao/tmp_home_1002

# Retorne o usuário padrão do n8n para segurança
USER user1002
#USER node

# (Opcional: Copie scripts python para dentro do container, se quiser)
# COPY ./meus-scripts/ /data/meus-scripts/

# (Opcional) Exemplo de cmd para rodar scripts python:
# CMD ["/data/venv/bin/python", "/data/meus-scripts/seuscript.py"]