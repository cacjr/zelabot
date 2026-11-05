"""
Logs do robo: tudo vai para o console e para um arquivo por dia em saida/logs/.
Assim da para saber depois o que o robo fez, em que ordem e onde deu erro.
"""
import logging
import sys
from datetime import datetime

from src.config import PASTA_LOGS

FORMATO = "%(asctime)s | %(levelname)-7s | %(name)-11s | %(message)s"


def configurar_logs(nivel=logging.INFO):
    raiz = logging.getLogger()
    if raiz.handlers:  # evita duplicar handlers se chamar duas vezes
        return
    raiz.setLevel(nivel)
    # no Windows o console as vezes usa CP1252 e o "MÉDIA" sai quebrado
    for fluxo in (sys.stdout, sys.stderr):
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    arquivo = PASTA_LOGS / f"zelabot_{datetime.now():%Y%m%d}.log"
    handler_arquivo = logging.FileHandler(arquivo, encoding="utf-8")
    handler_arquivo.setFormatter(logging.Formatter(FORMATO))

    handler_console = logging.StreamHandler()
    handler_console.setFormatter(logging.Formatter(FORMATO, datefmt="%H:%M:%S"))

    raiz.addHandler(handler_arquivo)
    raiz.addHandler(handler_console)

    # bibliotecas externas falam demais no nivel INFO
    for barulhento in ("selenium", "urllib3", "watchdog", "WDM"):
        logging.getLogger(barulhento).setLevel(logging.WARNING)


def obter_logger(nome):
    return logging.getLogger(nome)
