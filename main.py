"""
ZelaBot - ponto de entrada.

    python main.py            processa tudo que esta em entrada/ (do inicio ao fim)
    python main.py vigiar     fica vigiando a pasta entrada/ e processa cada arquivo novo
    python main.py avaliar    mede o modelo no conjunto de teste rotulado
    python main.py falhas     roda a demonstracao dos casos de falha
    python main.py treinar    retreina o classificador
    python main.py reset      apaga estado e saidas para rodar do zero
"""
import shutil
import sys
import time
from pathlib import Path

from src.config import (ARQ_MODELO, ARQ_TREINO, PASTA_ENTRADA, PASTA_ESTADO, PASTA_SAIDA,
                        PORTAL_EMBUTIDO, PORTAL_URL)
from src.logs import configurar_logs, obter_logger

log = obter_logger("main")


def subir_portal():
    """Sobe o portal simulado junto com o robo (se ja estiver rodando, so reaproveita)."""
    if not PORTAL_EMBUTIDO:
        return None
    from portal import servidor
    porta = int(PORTAL_URL.rsplit(":", 1)[-1].split("/")[0])
    try:
        srv = servidor.iniciar(porta)
        log.info("Portal simulado da prefeitura no ar em %s", PORTAL_URL)
        return srv
    except OSError:
        log.info("Porta %d ja em uso: usando o portal que ja esta rodando", porta)
        return None


def preparar():
    """Garante que existe base de treino e modelo antes de comecar."""
    if not ARQ_TREINO.exists():
        log.info("Base de treino nao encontrada, gerando dados sinteticos...")
        import runpy
        runpy.run_path(str(Path(__file__).parent / "dados" / "gerar_dados.py"), run_name="__main__")
    if not ARQ_MODELO.exists():
        from src import modelo
        modelo.treinar()


def cmd_executar():
    from src import pipeline
    preparar()
    srv = subir_portal()
    try:
        resumo = pipeline.executar()
        print("\nPlanilha:", resumo["relatorios"].get("planilha"))
        print("Execucao:", resumo["relatorios"].get("execucao"))
    finally:
        if srv:
            srv.shutdown()


def cmd_vigiar():
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    from src import leitura, pipeline
    preparar()
    srv = subir_portal()

    class NovoArquivo(FileSystemEventHandler):
        def on_created(self, evento):
            self._tratar(evento.src_path)

        def on_moved(self, evento):
            self._tratar(evento.dest_path)

        def _tratar(self, caminho):
            caminho = Path(caminho)
            if caminho.suffix.lower() not in leitura.EXTENSOES or caminho.name.startswith("~$"):
                return
            # espera o arquivo terminar de ser copiado (tamanho parar de mudar)
            tamanho = -1
            while caminho.exists() and caminho.stat().st_size != tamanho:
                tamanho = caminho.stat().st_size
                time.sleep(1)
            log.info("Arquivo novo detectado: %s", caminho.name)
            try:
                pipeline.executar([caminho])
            except Exception:
                log.exception("Erro inesperado ao processar %s (o vigia continua ativo)", caminho.name)

    observador = Observer()
    observador.schedule(NovoArquivo(), str(PASTA_ENTRADA), recursive=False)
    observador.start()
    log.info("Vigiando %s. Solte um arquivo .csv/.json/.xlsx la dentro. Ctrl+C para sair.", PASTA_ENTRADA)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Encerrando o vigia")
    finally:
        observador.stop()
        observador.join()
        if srv:
            srv.shutdown()


def cmd_avaliar():
    from src import avaliacao
    preparar()
    avaliacao.avaliar()


def cmd_falhas():
    from src import demo_falhas
    preparar()
    demo_falhas.rodar()


def cmd_treinar():
    from src import modelo
    modelo.treinar()


def cmd_reset():
    for pasta in (PASTA_ESTADO, PASTA_SAIDA):
        shutil.rmtree(pasta, ignore_errors=True)
        pasta.mkdir(exist_ok=True)
    dados_portal = Path(__file__).parent / "portal" / "dados_portal.json"
    dados_portal.unlink(missing_ok=True)
    print("Estado, saidas e banco do portal apagados. A pasta entrada/ foi mantida.")


COMANDOS = {"executar": cmd_executar, "vigiar": cmd_vigiar, "avaliar": cmd_avaliar,
            "falhas": cmd_falhas, "treinar": cmd_treinar, "reset": cmd_reset}

if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "executar"
    if comando != "reset":  # no reset o arquivo de log nao pode estar aberto (Windows trava)
        configurar_logs()
    if comando not in COMANDOS:
        print(__doc__)
        sys.exit(1)
    try:
        COMANDOS[comando]()
    except KeyboardInterrupt:
        log.info("Interrompido pelo usuario")
    except Exception:
        # ultima rede de seguranca: registra o erro completo no log antes de sair
        log.exception("Erro inesperado no comando '%s'", comando)
        sys.exit(1)
