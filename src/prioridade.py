"""
TEMA: Regras inteligentes + integracao com API publica

A prioridade NAO e decidida por uma caixa-preta. Ela soma pontos explicaveis:
  - peso base da categoria (que veio do modelo de ML);
  - palavras de RISCO A PESSOAS no texto (fio solto, crianca, escola...) => ALTA direto;
  - reincidencia ("ja reclamei", "faz 2 semanas") => +1;
  - previsao de CHUVA FORTE para o bairro (API Open-Meteo) em casos de bueiro
    ou arvore => +2, porque a chuva transforma um problema em emergencia.
Cada ponto vira uma frase na coluna "justificativa", para o servidor entender o porque.

A chamada da API tem timeout, retry com espera e um cache em disco. Se a API
cair, o robo usa a ultima previsao conhecida ou segue sem o criterio de chuva,
mas nunca para.
"""
import re
import time

import requests

from src.config import CHUVA_FORTE_MM, CLIMA_API_URL, TIMEOUT_SEGUNDOS
from src.logs import obter_logger
from src.resiliencia import RegistroJSON, com_retry, resumir_erro
from src.validacao import BAIRROS, normalizar

log = obter_logger("prioridade")

PESO_CATEGORIA = {"pavimentacao": 2, "iluminacao": 2, "drenagem": 2, "arvores": 2, "limpeza": 1}
ORGAO = {
    "pavimentacao": "Subprefeitura - Conservação de Vias",
    "iluminacao": "Departamento de Iluminação Pública",
    "limpeza": "Limpeza Urbana",
    "drenagem": "Subprefeitura - Drenagem",
    "arvores": "Subprefeitura - Manejo de Árvores",
}
PRAZO_DIAS = {"ALTA": 2, "MÉDIA": 7, "BAIXA": 15}
SENSIVEL_A_CHUVA = {"drenagem", "arvores"}

# padroes de risco (texto ja normalizado: minusculo e sem acento)
RISCOS = {
    "risco elétrico": r"fio (solto|exposto|caido)|faisca|choque",
    "pessoas vulneráveis por perto": r"crianca|idos[oa]|cadeirante|gestante|escola|creche|hospital|posto de saude",
    "risco de queda ou acidente": r"\bcai(u|ndo|r)\b|queda|acidente|motoqueir|desab|cratera|inclinad|pendurad|ameacando",
    "água invadindo casas": r"entra(r|ndo)? nas casas|invad|transbord",
    "via bloqueada": r"bloque|interdit",
    "buraco sem proteção": r"sem (tampa|grade)|tampa.{0,15}quebrad",
}
REINCIDENCIA = r"ja reclamei|de novo|faz (uns |mais de )?\d+ (dias|semanas|mes)|ha \d+ (dias|semanas)|ha dias|semanas"

_cache_disco = None
_cache_execucao = {}
# "disjuntor": depois de 2 falhas seguidas, para de chamar a API nesta execucao
# (nao adianta esperar o retry 10 vezes se o servico claramente caiu)
_disjuntor = {"falhas_seguidas": 0, "aberto": False}


def reiniciar_cache_execucao():
    _cache_execucao.clear()
    _disjuntor.update(falhas_seguidas=0, aberto=False)


class RespostaInvalida(Exception):
    pass


@com_retry(excecoes=(requests.RequestException, RespostaInvalida))
def _consultar_api(lat, lon) -> float:
    params = {"latitude": lat, "longitude": lon, "hourly": "precipitation",
              "forecast_days": 2, "timezone": "America/Sao_Paulo"}
    resposta = requests.get(CLIMA_API_URL, params=params, timeout=TIMEOUT_SEGUNDOS)
    resposta.raise_for_status()
    chuva = resposta.json().get("hourly", {}).get("precipitation")
    if not isinstance(chuva, list) or not chuva:
        raise RespostaInvalida("API respondeu sem dados de precipitacao")
    return round(sum(v or 0 for v in chuva[:24]), 1)  # proximas 24h


def chuva_prevista(bairro: str):
    """mm de chuva nas proximas 24h para o CENTRO do bairro (nunca a casa do cidadao)."""
    global _cache_disco
    if _cache_disco is None:
        _cache_disco = RegistroJSON("cache_clima")
    if bairro in _cache_execucao:
        return _cache_execucao[bairro]

    centro = BAIRROS.get(normalizar(bairro))
    if not centro:
        return None
    lat, lon = round(centro[1], 2), round(centro[2], 2)
    try:
        if _disjuntor["aberto"]:
            raise RespostaInvalida("disjuntor aberto, API ignorada nesta execucao")
        mm = _consultar_api(lat, lon)
        _cache_disco.definir(bairro, {"mm": mm, "quando": time.time()})
        _disjuntor["falhas_seguidas"] = 0
    except Exception as erro:
        if not _disjuntor["aberto"]:
            _disjuntor["falhas_seguidas"] += 1
            if _disjuntor["falhas_seguidas"] >= 2:
                _disjuntor["aberto"] = True
                log.error("API de clima falhou 2 vezes seguidas: disjuntor aberto nesta execucao")
        guardado = _cache_disco.get(bairro)
        if guardado and time.time() - guardado["quando"] < 12 * 3600:
            mm, fonte = guardado["mm"], "cache (API fora do ar)"
        else:
            mm, fonte = None, "indisponivel"
        log.warning("Clima de %s: %s. Usando %s.", bairro, resumir_erro(erro, 60), fonte)
    _cache_execucao[bairro] = mm
    return mm


def avaliar(categoria: str, descricao: str, bairro: str) -> dict:
    texto = normalizar(descricao)
    pontos = PESO_CATEGORIA.get(categoria, 1)
    motivos = [f"categoria {categoria} (peso {pontos})"]

    riscos = [nome for nome, padrao in RISCOS.items() if re.search(padrao, texto)]
    if riscos:
        motivos.append("RISCO: " + ", ".join(riscos))

    if re.search(REINCIDENCIA, texto):
        pontos += 1
        motivos.append("problema antigo ou reincidente (+1)")

    mm = None
    if categoria in SENSIVEL_A_CHUVA:
        mm = chuva_prevista(bairro)
        if mm is None:
            motivos.append("previsão de chuva indisponível (critério ignorado)")
        elif mm >= CHUVA_FORTE_MM:
            pontos += 2
            motivos.append(f"chuva forte prevista: {mm} mm em 24h (+2)")
        else:
            motivos.append(f"chuva prevista baixa: {mm} mm em 24h")

    if riscos or pontos >= 4:
        nivel = "ALTA"
    elif pontos >= 2:
        nivel = "MÉDIA"
    else:
        nivel = "BAIXA"

    return {
        "prioridade": nivel,
        "pontuacao": pontos,
        "urgente": bool(riscos),
        "chuva_24h_mm": mm,
        "orgao_responsavel": ORGAO.get(categoria, "Triagem manual"),
        "prazo_dias": PRAZO_DIAS[nivel],
        "justificativa": "; ".join(motivos),
    }


def detectar_risco(descricao: str) -> bool:
    """Usado na avaliacao: so a parte de risco, sem depender da API."""
    texto = normalizar(descricao)
    return any(re.search(p, texto) for p in RISCOS.values())
