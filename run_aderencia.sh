#!/bin/bash
#run_aderencia.sh
export MY_LOG_LEVEL=WARNING
cd /data/linkedin-automacao
source venv/bin/activate
export GOOGLE_APPLICATION_CREDENTIALS="application_default_credentials.json"
venv/bin/python3 scripts/aderencia_cv_vaga_ia.py 2> logs/aderencia_logs.txt