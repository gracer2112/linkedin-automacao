# dockerfile

FROM n8nio/n8n:latest

# Define o diretório de trabalho principal dentro do container para sua aplicação
# É uma boa prática usar /app ou /usr/src/app para o código da sua aplicação.
# No seu caso, o volume mount vai para /data/linkedin-automacao, então usaremos esse caminho.
WORKDIR /data/linkedin-automacao

# Instala Python e pip
USER root
RUN apk update && \
    apk add --no-cache python3 py3-pip libreoffice openjdk11 bash && \
    rm -rf /var/cache/apk/* 

# Garante que /bin/sh (o shell padrão no Alpine) exista e aponte para /bin/bash
# Isso é útil se algum script interno da imagem base esperar /bin/sh
RUN ln -sf /bin/bash /bin/sh

# Cria virtualenv isolado para dependências Python
RUN python3 -m venv ./venv

# Dá permissão de leitura (e execução) ao venv para o usuário node
RUN chown -R node:node ./venv

# Copia o requirements.txt para dentro do container
COPY requirements.txt .

# Use o pip do venv diretamente
RUN ./venv/bin/pip install --upgrade pip && \
    ./venv/bin/pip install --break-system-packages -r requirements.txt

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

# Comando padrão para quando o container é iniciado (pode ser sobrescrito pelo docker-compose)
# Isso permite que você entre no shell para inspecionar
CMD ["bash"]

# (Opcional: Copie scripts python para dentro do container, se quiser)
# COPY ./meus-scripts/ /data/meus-scripts/

# (Opcional) Exemplo de cmd para rodar scripts python:
# CMD ["/data/venv/bin/python", "/data/meus-scripts/seuscript.py"]