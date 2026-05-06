#!/bin/bash

set -e

# Executa o bootstrap de schema/migrações antes do app subir.
python -c 'from banco import criar_tabelas_e_migrar; criar_tabelas_e_migrar()'

# Inicia a aplicação Streamlit na porta fornecida pelo Render.
streamlit run app.py --server.port "${PORT:-8501}" --server.address 0.0.0.0
