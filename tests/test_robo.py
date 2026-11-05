"""Testes rapidos das partes que mais podem quebrar. Rodar com: python -m pytest"""
import json

import pytest

from src import leitura, prioridade, resiliencia, validacao


def registro_ok(**mudancas):
    base = {"id_solicitacao": "T-1", "data_hora": "2026-11-03 10:00", "canal": "app",
            "nome": "Fulano Teste", "bairro": "Mooca", "endereco": "Rua A, 1",
            "latitude": "-23.55", "longitude": "-46.60",
            "descricao": "Buraco grande na rua, me liga no (11) 91234-5678 ou fulano@email.com"}
    base.update(mudancas)
    return base


# Validacao e LGPD
def test_mascara_telefone_e_email_e_tira_o_nome():
    limpo, motivos = validacao.validar(registro_ok())
    assert motivos == []
    assert "[TELEFONE]" in limpo["descricao"] and "[EMAIL]" in limpo["descricao"]
    assert "91234" not in limpo["descricao"]
    assert "nome" not in limpo and limpo["cidadao"].startswith("cid_")


def test_mascara_cpf():
    texto, achados = validacao.mascarar_dados_pessoais("meu cpf 123.456.789-09")
    assert texto == "meu cpf [CPF]" and achados == ["cpf"]


@pytest.mark.parametrize("mudanca, motivo", [
    ({"descricao": "oi"}, "curta"),
    ({"data_hora": "2031-01-01 10:00"}, "futuro"),
    ({"data_hora": "ontem"}, "data inválida"),
    ({"bairro": "Atlantida", "latitude": "abc", "longitude": ""}, "localização"),
    ({"id_solicitacao": ""}, "identificador"),
])
def test_rejeita_dados_invalidos(mudanca, motivo):
    limpo, motivos = validacao.validar(registro_ok(**mudanca))
    assert limpo is None
    assert any(motivo in m for m in motivos)


def test_bairro_valido_sem_coordenada_usa_centro_do_bairro():
    limpo, _ = validacao.validar(registro_ok(latitude="", longitude=""))
    assert (limpo["latitude"], limpo["longitude"]) == (-23.5587, -46.5996)


# Leitura de arquivos
def test_le_csv_cp1252_com_ponto_e_virgula(tmp_path):
    arq = tmp_path / "legado.csv"
    arq.write_text("id_solicitacao;descricao\nX-1;Calçada quebrada perto da praça\n", encoding="cp1252")
    regs = leitura.ler_arquivo(arq)
    assert regs[0]["descricao"] == "Calçada quebrada perto da praça"


def test_json_corrompido_vira_arquivo_invalido(tmp_path):
    arq = tmp_path / "quebrado.json"
    arq.write_text('[{"id_solicitacao": "A', encoding="utf-8")
    with pytest.raises(leitura.ArquivoInvalido):
        leitura.ler_arquivo(arq)


def test_arquivo_ausente(tmp_path):
    with pytest.raises(FileNotFoundError):
        leitura.ler_arquivo(tmp_path / "nao_existe.csv")


def test_json_valido(tmp_path):
    arq = tmp_path / "ok.json"
    arq.write_text(json.dumps([{"id_solicitacao": "J-1", "descricao": "Poste apagado na rua"}]), encoding="utf-8")
    assert leitura.ler_arquivo(arq)[0]["id_solicitacao"] == "J-1"


# Resiliencia
def test_retry_recupera_depois_de_falhas():
    chamadas = {"n": 0}

    @resiliencia.com_retry(tentativas=3, espera_inicial=0, excecoes=(ConnectionError,))
    def instavel():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise ConnectionError("caiu")
        return "ok"

    assert instavel() == "ok" and chamadas["n"] == 3


def test_retry_desiste_e_relanca():
    @resiliencia.com_retry(tentativas=2, espera_inicial=0, excecoes=(ConnectionError,))
    def sempre_falha():
        raise ConnectionError("fora do ar")

    with pytest.raises(ConnectionError):
        sempre_falha()


# Prioridade (limpeza nao consulta a API de clima, entao o teste roda offline)
def test_risco_a_pessoas_vira_alta():
    r = prioridade.avaliar("limpeza", "Entulho na frente da creche, criança quase se machucou", "Mooca")
    assert r["prioridade"] == "ALTA" and r["urgente"]


def test_sem_risco_limpeza_e_baixa():
    r = prioridade.avaliar("limpeza", "Saco de lixo na calçada", "Mooca")
    assert r["prioridade"] == "BAIXA" and r["prazo_dias"] == 15


def test_chuva_forte_sobe_prioridade_de_bueiro(monkeypatch):
    # simula a API dizendo que vem 25 mm de chuva nas proximas 24h
    monkeypatch.setattr(prioridade, "chuva_prevista", lambda bairro: 25.0)
    r = prioridade.avaliar("drenagem", "Bueiro entupido de folhas na esquina", "Mooca")
    assert r["prioridade"] == "ALTA" and "chuva forte" in r["justificativa"]


def test_api_de_clima_fora_usa_caminho_seguro(monkeypatch):
    def api_caiu(*a, **k):
        raise prioridade.requests.ConnectionError("fora do ar")
    monkeypatch.setattr(prioridade, "_consultar_api", api_caiu)
    monkeypatch.setattr(prioridade, "_cache_disco", resiliencia.RegistroJSON("cache_clima_teste"))
    prioridade.reiniciar_cache_execucao()
    r = prioridade.avaliar("arvores", "Galho quebrado na calçada", "Itaquera")
    assert r["chuva_24h_mm"] is None and "indisponível" in r["justificativa"]
