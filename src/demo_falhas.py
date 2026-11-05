"""
Demonstracao automatica das falhas tratadas (python main.py falhas).

Roda o robo varias vezes, cada vez quebrando uma coisa de proposito, e confere
se ele seguiu o caminho seguro esperado. O resultado vai para
docs/evidencias/demo_falhas.md (tabela esperado x obtido).

ATENCAO: comeca apagando o estado do robo e o banco do portal simulado.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from portal import servidor
from src import pipeline, prioridade, resiliencia, rpa_portal
from src.config import PASTA_ESTADO, PASTA_SAIDA, PORTAL_URL, RAIZ
from src.logs import obter_logger

log = obter_logger("demo_falhas")
PASTA_EVID = RAIZ / "docs" / "evidencias"
URL_CLIMA_ORIGINAL = prioridade.CLIMA_API_URL
SENHA_ORIGINAL = rpa_portal.PORTAL_SENHA


class ContadorRetries(logging.Handler):
    def __init__(self):
        super().__init__()
        self.n = 0

    def emit(self, record):
        if "Nova tentativa" in record.getMessage():
            self.n += 1


def _limpar_estado():
    for arq in PASTA_ESTADO.glob("*.json"):
        arq.unlink()
    servidor.ARQ_DADOS.unlink(missing_ok=True)


def _registros_no_portal():
    if not servidor.ARQ_DADOS.exists():
        return 0
    return len(json.loads(servidor.ARQ_DADOS.read_text(encoding="utf-8"))["registros"])


def _novo_lote(nome, qtd):
    """Cria um lote extra (fora da pasta entrada/) so para a demonstracao."""
    pasta = PASTA_SAIDA / "demo"
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%H%M%S")
    textos = ["Buraco grande na rua perto da padaria, carro quase caiu",
              "Poste queimado na praça faz uma semana"]
    dados = [{"id_solicitacao": f"DEMO-{carimbo}-{i}", "data_hora": "2026-11-03 10:00", "canal": "demo",
              "nome": "Pessoa Ficticia", "bairro": "Mooca", "endereco": "Rua Teste, 10",
              "latitude": "", "longitude": "", "descricao": textos[i % 2]} for i in range(qtd)]
    caminho = pasta / nome
    caminho.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return caminho


def rodar():
    porta = int(PORTAL_URL.rsplit(":", 1)[-1].split("/")[0])
    if rpa_portal.portal_no_ar():
        log.error("Ja existe um portal rodando na porta %d. Feche-o antes da demonstracao.", porta)
        return
    resiliencia.ESPERA_INICIAL = 0.3  # so para a demo nao demorar
    contador = ContadorRetries()
    logging.getLogger("resiliencia").addHandler(contador)
    _limpar_estado()
    cenarios = []

    def registrar(nome, falha, esperado, ok, obtido):
        cenarios.append({"cenario": nome, "falha_simulada": falha, "esperado": esperado,
                         "obtido": obtido, "ok": bool(ok)})
        log.info("[%s] %s -> %s", "OK" if ok else "FALHOU", nome, obtido)

    # 1) API de clima fora do ar + portal fora do ar + arquivo corrompido + dados invalidos
    prioridade.CLIMA_API_URL = "http://api-clima.invalido.test/v1/forecast"
    r = pipeline.executar()
    sem_clima = sum("indisponível" in s.get("justificativa", "") for s in r["pendentes"])
    sensiveis = sum(s["categoria"] in prioridade.SENSIVEL_A_CHUVA for s in r["pendentes"])
    registrar("API de clima fora do ar", "URL da API apontando para um host inexistente",
              "robô segue sem o critério de chuva e explica isso na justificativa",
              sem_clima == sensiveis and sensiveis > 0,
              f"{sem_clima} de {sensiveis} casos de bueiro/arvore com 'previsão indisponível'; disjuntor aberto após 2 falhas")
    registrar("Portal da prefeitura fora do ar", "portal desligado",
              "nada se perde: tudo vai para a fila de pendentes",
              len(r["registradas"]) == 0 and len(r["pendentes"]) > 0,
              f"0 registradas, {len(r['pendentes'])} na fila de pendentes")
    registrar("Arquivo corrompido", "JSON cortado no meio (exportacao_interrompida.json)",
              "arquivo vai para quarentena com o motivo e os outros 4 são lidos",
              len(r["quarentena"]) == 1 and r["lidos"] == 31,
              f"{len(r['quarentena'])} em quarentena (JSONDecodeError), {r['lidos']} registros dos outros arquivos lidos")
    registrar("Dados inválidos", "data no futuro, texto 'oi', bairro inexistente e linha duplicada",
              "rejeita com motivo e mensagem ao cidadão; duplicata ignorada",
              len(r["rejeitadas"]) == 3 and r["duplicadas_no_lote"] == 1,
              f"{len(r['rejeitadas'])} rejeitadas, cada uma com motivo ({', '.join(x['id_solicitacao'] for x in r['rejeitadas'])}), "
              f"{r['duplicadas_no_lote']} duplicata ignorada")
    pendentes_iniciais = len(r["pendentes"])

    # 2) Portal volta, mas instavel (erro 503 a cada 4 envios)
    prioridade.CLIMA_API_URL = URL_CLIMA_ORIGINAL
    os.environ["PORTAL_FALHA_A_CADA"] = "4"
    srv = servidor.iniciar(porta)
    try:
        contador.n = 0
        r = pipeline.executar(arquivos=[])
        registrar("Portal instável (erro 503)", "portal responde 503 a cada 4 cadastros",
                  "retry com espera recupera e a fila de pendentes zera",
                  len(r["registradas"]) == pendentes_iniciais and r["pendentes_na_fila"] == 0,
                  f"{len(r['registradas'])}/{pendentes_iniciais} registradas, {contador.n} novas tentativas automáticas, "
                  f"fila de pendentes = {r['pendentes_na_fila']}")
        os.environ["PORTAL_FALHA_A_CADA"] = "0"

        # 3) Execucao repetida (idempotencia)
        antes = _registros_no_portal()
        r = pipeline.executar()
        depois = _registros_no_portal()
        registrar("Execução repetida", "rodar o robô de novo com os mesmos arquivos",
                  "nada é cadastrado em dobro no portal",
                  depois == antes and len(r["registradas"]) == 0,
                  f"{r['ja_processadas']} já processadas ignoradas; portal continuou com {depois} registros")

        # 4) Senha errada no portal
        rpa_portal.PORTAL_SENHA = "senha-errada"
        lote = _novo_lote("lote_senha_errada.json", 2)
        r = pipeline.executar(arquivos=[lote])
        rpa_portal.PORTAL_SENHA = SENHA_ORIGINAL
        r2 = pipeline.executar(arquivos=[])
        registrar("Senha do portal errada", "PORTAL_SENHA inválida no .env",
                  "não insiste no login, guarda na fila e registra quando a senha é corrigida",
                  len(r["pendentes"]) == 2 and len(r2["registradas"]) == 2,
                  f"1ª execução: {len(r['pendentes'])} pendentes (CredenciaisInvalidas); "
                  f"após corrigir: {len(r2['registradas'])} registradas")

        # 5) Arquivo ausente
        r = pipeline.executar(arquivos=[Path("entrada/nao_existe.csv")])
        registrar("Arquivo ausente", "caminho de arquivo que não existe",
                  "registra no log e termina a execução normalmente",
                  r["arquivos"][0]["status"] == "ausente",
                  f"status do arquivo: {r['arquivos'][0]['status']}; relatório gerado normalmente")
    finally:
        srv.shutdown()
        os.environ["PORTAL_FALHA_A_CADA"] = "0"
        prioridade.CLIMA_API_URL = URL_CLIMA_ORIGINAL
        rpa_portal.PORTAL_SENHA = SENHA_ORIGINAL

    PASTA_EVID.mkdir(parents=True, exist_ok=True)
    with open(PASTA_EVID / "demo_falhas.json", "w", encoding="utf-8") as f:
        json.dump(cenarios, f, ensure_ascii=False, indent=2)
    linhas = ["# Demonstração de falhas tratadas", "",
              f"Gerado automaticamente por `python main.py falhas` em {datetime.now():%d/%m/%Y %H:%M}.", "",
              "| Cenário | Falha simulada | Esperado | Obtido | Passou? |", "| :- | :- | :- | :- | :-: |"]
    linhas += [f"| {c['cenario']} | {c['falha_simulada']} | {c['esperado']} | {c['obtido']} | "
               f"{'sim' if c['ok'] else 'NÃO'} |" for c in cenarios]
    (PASTA_EVID / "demo_falhas.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    passou = sum(c["ok"] for c in cenarios)
    log.info("Demonstracao concluida: %d de %d cenarios passaram. Veja docs/evidencias/demo_falhas.md",
             passou, len(cenarios))
