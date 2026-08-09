"""Configuração compartilhada dos testes.

O código de produção vive em `src/` e usa imports "soltos" (ex.: `from
schemas import VendasSchema`), pensados para rodar com `src/` como
diretório de trabalho — é assim que `analise.py` é chamado hoje
(`cd src && python analise.py ...`). Para os testes conseguirem importar
esses módulos sem precisar duplicar essa convenção, adicionamos `src/` ao
`sys.path` uma única vez aqui.
"""
import sys
from pathlib import Path

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
SRC = RAIZ_PROJETO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DADOS_ORIGEM = RAIZ_PROJETO / "data" / "raw" / "vendas_eletronicos_1S2026.db"
BASELINE_ANALISE = FIXTURES / "baseline_analise.sqlite"
