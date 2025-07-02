#!/bin/bash
export MY_LOG_LEVEL=WARNING
cd /data/linkedin-automacao
source venv/bin/activate
venv/bin/python3 scripts/analise_vaga_ia.py 2> logs/analise_vagas_logs.txt