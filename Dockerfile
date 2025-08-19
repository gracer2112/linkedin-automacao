# dockerfile
FROM n8nio/n8n:latest

# Define o diretório de trabalho principal dentro do container para sua aplicação
# É uma boa prática usar /app ou /usr/src/app para o código da sua aplicação.
# No seu caso, o volume mount vai para /data/linkedin-automacao, então usaremos esse caminho.
WORKDIR /data/linkedin-automacao

# Instala Python e pip
USER root
RUN apk update && \
    apk add --no-cache python3 py3-pip libreoffice openjdk11 bash tree && \
    rm -rf /var/cache/apk/* 

# Garante que /bin/sh (o shell padrão no Alpine) exista e aponte para /bin/bash
# Isso é útil se algum script interno da imagem base esperar /bin/sh
RUN ln -sf /bin/bash /bin/sh

# Cria virtualenv isolado para dependências Python
RUN python3 -m venv /opt/venv

RUN addgroup -g 1002 user1002 && \
    adduser -D -u 1002 -G user1002 -h /data/linkedin-automacao/tmp_home_1002 user1002 
# Dá permissão total ao 'user1002' para acessar o ambiente virtual e o diretório de saída 'output'.
# Isso é crucial, pois o container rodará como 'user1002'.
RUN chown -R user1002:user1002 /opt/venv   

# Copia o requirements.txt para dentro do container
COPY requirements.txt .

# Instala as dependências Python usando o pip do venv.
# Agora, o '/opt/venv/bin/pip' deve ser encontrado corretamente.
RUN /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --break-system-packages --use-deprecated=legacy-resolver -r requirements.txt

# Garante que o diretório home temporário (/data/linkedin-automacao/tmp_home_1002)
# seja criado e de propriedade EXCLUSIVA do user1002 (UID 1002).
RUN mkdir -p /data/linkedin-automacao/tmp_home_1002 && \
    chown -R user1002:user1002 /data/linkedin-automacao/tmp_home_1002

# Isso garante que o diretório já exista com as permissões corretas antes do n8n tentar criá-lo.
RUN mkdir -p /data/linkedin-automacao/tmp_home_1002/.n8n && \
    chown -R user1002:user1002 /data/linkedin-automacao/tmp_home_1002/.n8n
    
# Supondo que você crie o diretório de alguma forma
RUN mkdir -p /data/linkedin-automacao/output && \
    chown -R user1002:user1002 /data/linkedin-automacao/output 

# Copia o restante dos arquivos da sua aplicação para o container.
COPY . .

RUN chown -R user1002:user1002 /data/linkedin-automacao    

#RUN chown -R node:node /data/linkedin-automacao

#RUN chown -R node:node /data/linkedin-automacao/output && \
#    chown -R user1002:user1002 /data/linkedin-automacao/output

# Define variáveis de ambiente que são importantes para o Python e para o PATH.
# Adiciona o diretório 'bin' do venv ao PATH, para que 'python' e 'pip' sejam encontrados.
ENV HOME=/data/linkedin-automacao/tmp_home_1002
ENV PATH="/opt/venv/bin:${PATH}"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Retorne o usuário padrão do n8n para segurança
USER user1002


# Comando padrão para quando o container é iniciado (pode ser sobrescrito pelo docker-compose)
# Isso permite que você entre no shell para inspecionar
#CMD ["bash"]

# (Opcional: Copie scripts python para dentro do container, se quiser)
# COPY ./meus-scripts/ /data/meus-scripts/

# (Opcional) Exemplo de cmd para rodar scripts python:
# CMD ["/data/venv/bin/python", "/data/meus-scripts/seuscript.py"]
