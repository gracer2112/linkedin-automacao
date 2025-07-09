#!/bin/bash
echo -e "\n==== Inicio $(date) ====" 2>> /data/linkedin-automacao/logs/cv_aplicador.txt

#whoami 2>&1
#id 2>&1

#export HOME=/data/linkedin-automacao/tmp_home_1002
export MY_LOG_LEVEL=WARNING

cd /data/linkedin-automacao 2>&1

source venv/bin/activate 2>&1
#export GOOGLE_APPLICATION_CREDENTIALS="application_default_credentials.json"

venv/bin/python3 scripts/cv_aplicador.py 2>&1

#chown -R 1002:1002 output 2>&1
#chmod -R 775 output 2>&1

echo -e "\n==== Fim $(date) ====" 2>> logs/cv_aplicador.txt