"""
Tratamento de erros reaproveitavel: retry com espera exponencial e
controle de idempotencia (nao processar a mesma solicitacao duas vezes).
"""
import functools
import json
import time
from datetime import datetime

from src.config import ESPERA_INICIAL, MAX_TENTATIVAS, PASTA_ESTADO
from src.logs import obter_logger

log = obter_logger("resiliencia")


def resumir_erro(erro, limite=110):
    """Mensagem curta para o log (erro de conexao do requests e enorme)."""
    texto = str(erro).split(" (Caused by")[0]
    return f"{type(erro).__name__}: {texto[:limite]}"


def com_retry(tentativas=None, espera_inicial=None, excecoes=(Exception,)):
    """
    Decorator: se a funcao falhar com uma das `excecoes`, tenta de novo
    esperando 1s, 2s, 4s... (backoff exponencial). Se esgotar as tentativas,
    relanca o ultimo erro para quem chamou decidir o caminho seguro.
    """
    def decorator(funcao):
        @functools.wraps(funcao)
        def wrapper(*args, **kwargs):
            total = tentativas or MAX_TENTATIVAS
            espera = espera_inicial if espera_inicial is not None else ESPERA_INICIAL
            for tentativa in range(1, total + 1):
                try:
                    return funcao(*args, **kwargs)
                except excecoes as erro:
                    if tentativa == total:
                        log.error("%s falhou apos %d tentativas: %s",
                                  funcao.__name__, total, resumir_erro(erro))
                        raise
                    log.warning("%s falhou (tentativa %d/%d): %s. Nova tentativa em %.1fs",
                                funcao.__name__, tentativa, total, resumir_erro(erro), espera)
                    time.sleep(espera)
                    espera *= 2
        return wrapper
    return decorator


class RegistroJSON:
    """Pequeno 'banco' em JSON, salvo de forma atomica (escreve num .tmp e troca)."""

    def __init__(self, nome):
        self.caminho = PASTA_ESTADO / f"{nome}.json"
        self.dados = self._carregar()

    def _carregar(self):
        if not self.caminho.exists():
            return {}
        try:
            with open(self.caminho, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as erro:
            # estado corrompido nao pode derrubar o robo: guarda copia e recomeca
            backup = self.caminho.with_suffix(f".corrompido_{datetime.now():%H%M%S}")
            self.caminho.replace(backup)
            log.error("Estado %s corrompido (%s). Backup em %s", self.caminho.name, erro, backup.name)
            return {}

    def salvar(self):
        temporario = self.caminho.with_suffix(".tmp")
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2)
        # OneDrive/antivirus podem travar o arquivo por um instante enquanto
        # sincronizam/verificam: tenta a troca de novo antes de desistir
        for tentativa in range(10):
            try:
                temporario.replace(self.caminho)
                return
            except PermissionError:
                time.sleep(0.1 * (tentativa + 1))
        # ultimo recurso: grava direto no arquivo final (perde a atomicidade, mas nao perde o dado)
        log.warning("Troca atomica de %s bloqueada pelo sistema. Gravando direto.", self.caminho.name)
        with open(self.caminho, "w", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False, indent=2)
        temporario.unlink(missing_ok=True)

    def __contains__(self, chave):
        return chave in self.dados

    def get(self, chave, padrao=None):
        return self.dados.get(chave, padrao)

    def definir(self, chave, valor):
        self.dados[chave] = valor
        self.salvar()

    def remover(self, chave):
        if self.dados.pop(chave, None) is not None:
            self.salvar()
