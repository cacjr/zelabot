"""
TEMA: Qualidade de dados (GIGO: Garbage In, Garbage Out) + protecao de dados

Antes de qualquer IA, o robo confere se a solicitacao faz sentido. Dado ruim
nao segue no fluxo: vai para a aba "Rejeitadas" com o motivo e uma mensagem
pedindo para o cidadao completar.

Tambem e aqui que os dados pessoais saem de cena (LGPD):
  - o nome vira um pseudonimo (hash), e o nome original nao vai para nenhuma saida;
  - CPF, telefone e e-mail digitados no meio do texto sao mascarados ANTES
    de o texto chegar no modelo, no portal ou no relatorio.
"""
import hashlib
import os
import re
import unicodedata
from datetime import datetime, timedelta

from src.logs import obter_logger

log = obter_logger("validacao")

# Centroides aproximados (dado publico). Usados para validar e para consultar o clima.
BAIRROS = {
    "se": ("Sé", -23.5503, -46.6339),
    "mooca": ("Mooca", -23.5587, -46.5996),
    "pinheiros": ("Pinheiros", -23.5614, -46.7016),
    "itaquera": ("Itaquera", -23.5400, -46.4560),
    "capao redondo": ("Capão Redondo", -23.6720, -46.7790),
    "santana": ("Santana", -23.5020, -46.6250),
    "butanta": ("Butantã", -23.5710, -46.7080),
    "jabaquara": ("Jabaquara", -23.6460, -46.6410),
    "brasilandia": ("Brasilândia", -23.4690, -46.6890),
    "cidade tiradentes": ("Cidade Tiradentes", -23.5820, -46.4090),
}
# retangulo que cobre o municipio de Sao Paulo (aproximado)
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = -24.01, -23.35, -46.83, -46.36
MIN_CARACTERES = 15
MIN_PALAVRAS = 3

RE_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
RE_TELEFONE = re.compile(r"(\(?\d{2}\)?\s?)?9?\d{4}-?\d{4}\b")
RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def normalizar(texto: str) -> str:
    """minusculo e sem acento: 'Butantã' -> 'butanta'"""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def mascarar_dados_pessoais(texto: str) -> tuple[str, list[str]]:
    encontrados = []
    for regex, rotulo in ((RE_EMAIL, "[EMAIL]"), (RE_CPF, "[CPF]"), (RE_TELEFONE, "[TELEFONE]")):
        if regex.search(texto):
            encontrados.append(rotulo.strip("[]").lower())
            texto = regex.sub(rotulo, texto)
    return texto, encontrados


def pseudonimo(nome: str) -> str:
    # o "sal" fica no .env: sem ele nao da para refazer o hash a partir de uma lista de nomes
    sal = os.getenv("PSEUDONIMO_SAL", "troque-este-sal")
    return "cid_" + hashlib.sha256((sal + normalizar(nome)).encode()).hexdigest()[:10]


def _vazio(valor) -> bool:
    return valor is None or str(valor).strip() in ("", "nan", "None")


def _coordenada(valor):
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def validar(registro: dict) -> tuple[dict | None, list[str]]:
    """
    Devolve (registro_limpo, []) se estiver ok, ou (None, [motivos]) se nao.
    O registro limpo ja vem anonimizado.
    """
    motivos = []

    if _vazio(registro.get("id_solicitacao")):
        motivos.append("sem identificador")

    descricao = "" if _vazio(registro.get("descricao")) else " ".join(str(registro["descricao"]).split())
    if len(descricao) < MIN_CARACTERES or len(descricao.split()) < MIN_PALAVRAS:
        motivos.append("descrição muito curta para entender o problema")

    data = None
    try:
        data = datetime.fromisoformat(str(registro.get("data_hora")).strip())
        if data > datetime.now() + timedelta(days=1):
            motivos.append("data no futuro")
    except ValueError:
        motivos.append("data inválida")

    # localizacao: aceita bairro conhecido OU coordenada dentro de SP
    chave_bairro = normalizar(registro.get("bairro"))
    bairro = BAIRROS.get(chave_bairro)
    lat, lon = _coordenada(registro.get("latitude")), _coordenada(registro.get("longitude"))
    coord_ok = lat is not None and lon is not None and LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX
    if not bairro and not coord_ok:
        motivos.append("localização não identificada (bairro e coordenadas inválidos)")
    if bairro and not coord_ok:  # usa o centro do bairro
        lat, lon = bairro[1], bairro[2]

    if motivos:
        return None, motivos

    descricao_segura, achados = mascarar_dados_pessoais(descricao)
    if achados:
        log.info("%s: dados pessoais mascarados no texto (%s)",
                 registro["id_solicitacao"], ", ".join(achados))

    limpo = {
        "id_solicitacao": str(registro["id_solicitacao"]).strip(),
        "data_hora": data.strftime("%Y-%m-%d %H:%M"),
        "canal": registro.get("canal") or "desconhecido",
        "cidadao": pseudonimo(registro.get("nome") or ""),
        "bairro": bairro[0] if bairro else "Não informado",
        "endereco": "" if _vazio(registro.get("endereco")) else str(registro["endereco"]),
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "descricao": descricao_segura,
        "dados_pessoais_mascarados": ", ".join(achados),
        "arquivo_origem": registro.get("arquivo_origem", ""),
    }
    return limpo, []
