"""
Portal SIMULADO de zeladoria da prefeitura (o "sistema legado").

Na vida real o servidor publico abre um sistema web antigo, faz login e digita
cada solicitacao a mao. Aqui criamos uma versao local desse sistema para o robo
(Selenium) fazer exatamente isso. Nao e um sistema real de nenhuma prefeitura.

Rotas: /  (login) | /nova (formulario) | /registros (lista) | /saude (health check)

Variavel opcional PORTAL_FALHA_A_CADA=N: a cada N cadastros o portal responde
erro 503, para testar o retry do robo.
"""
import html
import json
import os
import secrets
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ARQ_DADOS = Path(__file__).resolve().parent / "dados_portal.json"
_trava = threading.Lock()
_sessoes = set()
_contador_posts = {"n": 0}

CSS = """
body{font-family:Verdana,Arial,sans-serif;background:#e9edf2;margin:0;font-size:13px}
.topo{background:#1f3b5a;color:#fff;padding:10px 16px;font-weight:bold}
.caixa{background:#fff;max-width:640px;margin:24px auto;padding:18px;border:1px solid #aab}
label{display:block;margin-top:10px;font-weight:bold}
input,select,textarea{width:100%;padding:5px;box-sizing:border-box;font:inherit}
button{margin-top:14px;padding:6px 18px;background:#2d5d8a;color:#fff;border:0;cursor:pointer}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd;padding:4px;text-align:left}
.ok{background:#dff3df;padding:10px;border:1px solid #8c8}.erro{background:#f8dddd;padding:10px;border:1px solid #c88}
"""


def _pagina(titulo, corpo):
    return (f"<!doctype html><html lang='pt-br'><head><meta charset='utf-8'><title>{titulo}</title>"
            f"<style>{CSS}</style></head><body><div class='topo'>Sistema de Zeladoria Urbana "
            f"(SIMULADO) | {titulo}</div><div class='caixa'>{corpo}</div></body></html>")


def _carregar():
    if ARQ_DADOS.exists():
        with open(ARQ_DADOS, encoding="utf-8") as f:
            return json.load(f)
    return {"seq": 0, "registros": []}


def _salvar(dados):
    with open(ARQ_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


class Portal(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silencia o log padrao do http.server
        pass

    def _responder(self, status, conteudo, extra_headers=None):
        corpo = conteudo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _logado(self):
        cookie = self.headers.get("Cookie", "")
        return any(f"sessao={s}" in cookie for s in _sessoes)

    def _form(self):
        tamanho = int(self.headers.get("Content-Length", 0))
        dados = parse_qs(self.rfile.read(tamanho).decode("utf-8"))
        return {k: v[0] for k, v in dados.items()}

    def do_GET(self):
        rota = urlparse(self.path).path
        if rota == "/saude":
            return self._responder(200, "ok")
        if rota == "/":
            return self._responder(200, _pagina("Login", """
                <form method='post' action='/login'>
                <label>Usuário</label><input id='usuario' name='usuario'>
                <label>Senha</label><input id='senha' name='senha' type='password'>
                <button id='entrar' type='submit'>Entrar</button></form>"""))
        if not self._logado():
            return self._responder(302, "", {"Location": "/"})
        if rota == "/nova":
            opcoes_cat = "".join(f"<option value='{c}'>{c}</option>" for c in
                                 ["pavimentacao", "iluminacao", "limpeza", "drenagem", "arvores"])
            opcoes_pri = "".join(f"<option>{p}</option>" for p in ["ALTA", "MÉDIA", "BAIXA"])
            return self._responder(200, _pagina("Nova solicitação", f"""
                <form method='post' action='/nova'>
                <label>Nº externo</label><input id='id_externo' name='id_externo'>
                <label>Categoria</label><select id='categoria' name='categoria'>{opcoes_cat}</select>
                <label>Bairro</label><input id='bairro' name='bairro'>
                <label>Endereço</label><input id='endereco' name='endereco'>
                <label>Descrição</label><textarea id='descricao' name='descricao' rows='4'></textarea>
                <label>Prioridade</label><select id='prioridade' name='prioridade'>{opcoes_pri}</select>
                <label>Órgão responsável</label><input id='orgao' name='orgao'>
                <button id='registrar' type='submit'>Registrar</button></form>"""))
        if rota == "/registros":
            dados = _carregar()
            linhas = "".join(
                f"<tr><td>{html.escape(r['protocolo'])}</td><td>{html.escape(r['id_externo'])}</td>"
                f"<td>{html.escape(r['categoria'])}</td><td>{html.escape(r['prioridade'])}</td>"
                f"<td>{html.escape(r['bairro'])}</td></tr>" for r in dados["registros"])
            return self._responder(200, _pagina("Registros", f"""
                <table><tr><th>Protocolo</th><th>Nº externo</th><th>Categoria</th>
                <th>Prioridade</th><th>Bairro</th></tr>{linhas}</table>"""))
        self._responder(404, _pagina("Erro", "Página não encontrada"))

    def do_POST(self):
        rota = urlparse(self.path).path
        if rota == "/login":
            form = self._form()
            usuario_ok = secrets.compare_digest(form.get("usuario", ""), os.getenv("PORTAL_USUARIO", ""))
            senha_ok = secrets.compare_digest(form.get("senha", ""), os.getenv("PORTAL_SENHA", ""))
            if usuario_ok and senha_ok and os.getenv("PORTAL_SENHA"):
                token = secrets.token_hex(8)
                _sessoes.add(token)
                return self._responder(302, "", {"Location": "/nova", "Set-Cookie": f"sessao={token}; Path=/"})
            return self._responder(401, _pagina("Login", "<p class='erro' id='erro'>Usuário ou senha inválidos</p>"))

        if rota == "/nova":
            if not self._logado():
                return self._responder(302, "", {"Location": "/"})
            form = self._form()
            falha_a_cada = int(os.getenv("PORTAL_FALHA_A_CADA", "0") or 0)
            with _trava:
                _contador_posts["n"] += 1
                if falha_a_cada and _contador_posts["n"] % falha_a_cada == 0:
                    return self._responder(503, _pagina("Erro", "<p class='erro' id='erro'>Serviço "
                                                         "temporariamente indisponível (503)</p>"))
                dados = _carregar()
                # o proprio portal tambem nao duplica: mesmo n externo devolve o mesmo protocolo
                existente = next((r for r in dados["registros"] if r["id_externo"] == form.get("id_externo")), None)
                if existente:
                    protocolo = existente["protocolo"]
                else:
                    dados["seq"] += 1
                    protocolo = f"ZEL-{datetime.now():%Y}-{dados['seq']:06d}"
                    dados["registros"].append({
                        "protocolo": protocolo, "registrado_em": datetime.now().isoformat(timespec="seconds"),
                        **{k: form.get(k, "") for k in ("id_externo", "categoria", "bairro", "endereco",
                                                         "descricao", "prioridade", "orgao")}})
                    _salvar(dados)
            return self._responder(200, _pagina("Registrado", f"""
                <p class='ok'>Solicitação registrada. Protocolo: <b id='protocolo'>{protocolo}</b></p>
                <a id='nova' href='/nova'>Registrar outra</a>"""))
        self._responder(404, _pagina("Erro", "Página não encontrada"))


class Servidor(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # o Chrome fecha conexoes "keep-alive" sem avisar; isso nao e erro do portal
        import sys
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            super().handle_error(request, client_address)


def iniciar(porta=8765) -> ThreadingHTTPServer:
    servidor = Servidor(("127.0.0.1", porta), Portal)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return servidor


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    print("Portal simulado em http://127.0.0.1:8765 (Ctrl+C para sair)")
    srv = Servidor(("127.0.0.1", 8765), Portal)
    srv.serve_forever()
