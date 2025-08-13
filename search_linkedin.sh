#!/bin/bash
#run_linkedin.sh
export MY_LOG_LEVEL=WARNING
export CONFIG_JSON_PATH="configs/linkedin.json"

cd /data/linkedin-automacao
source .venv/bin/activate
.venv/bin/python3 scripts/search_linkedin.py 2> logs/search_linkedin.txt