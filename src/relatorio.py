"""
TEMA: Automacao de Excel (pandas + XlsxWriter)

Gera, a cada execucao:
  - uma planilha para a equipe da prefeitura, com abas separadas por situacao,
    cores por prioridade, filtros e um grafico de resumo;
  - um relatorio de execucao em JSON (o "diario de bordo" do robo).
XlsxWriter foi escolhido porque escreve rapido e permite formatacao e graficos.
"""
import json
from datetime import datetime

import pandas as pd

from src.config import PASTA_SAIDA
from src.logs import obter_logger

log = obter_logger("relatorio")
PASTA_RELATORIOS = PASTA_SAIDA / "relatorios"

COLS_REGISTRADAS = ["id_solicitacao", "protocolo", "prioridade", "categoria", "confianca", "bairro",
                    "endereco", "descricao", "orgao_responsavel", "prazo_dias", "chuva_24h_mm",
                    "justificativa", "canal", "cidadao", "mensagem_cidadao"]
COLS_REVISAO = ["id_solicitacao", "urgente", "descricao", "categoria", "confianca", "segunda_opcao",
                "motivo_revisao", "bairro", "canal", "mensagem_cidadao"]
COLS_PENDENTES = ["id_solicitacao", "prioridade", "categoria", "bairro", "descricao",
                  "motivo_pendencia", "mensagem_cidadao"]


def _tabela(lista, colunas):
    df = pd.DataFrame(lista)
    if df.empty:
        return pd.DataFrame(columns=colunas)
    return df[[c for c in colunas if c in df.columns]]


def _escrever_aba(writer, df, nome, larguras, formatos):
    df.to_excel(writer, sheet_name=nome, index=False, startrow=0)
    aba = writer.sheets[nome]
    for i, col in enumerate(df.columns):
        aba.set_column(i, i, larguras.get(col, 14), formatos["quebra"] if col in
                       ("descricao", "justificativa", "mensagem_cidadao", "motivos") else None)
    if len(df):
        aba.autofilter(0, 0, len(df), len(df.columns) - 1)
    aba.freeze_panes(1, 0)
    if "prioridade" in df.columns and len(df):
        c = df.columns.get_loc("prioridade")
        for texto, fmt in (("ALTA", "alta"), ("MÉDIA", "media"), ("BAIXA", "baixa")):
            aba.conditional_format(1, c, len(df), c, {"type": "cell", "criteria": "==",
                                                      "value": f'"{texto}"', "format": formatos[fmt]})
    return aba


def gerar(resumo: dict, criticos: pd.DataFrame) -> dict:
    PASTA_RELATORIOS.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    arq_xlsx = PASTA_RELATORIOS / f"relatorio_{carimbo}.xlsx"
    arq_json = PASTA_RELATORIOS / f"execucao_{carimbo}.json"

    registradas = _tabela(resumo["registradas"], COLS_REGISTRADAS)
    if len(registradas):
        ordem = {"ALTA": 0, "MÉDIA": 1, "BAIXA": 2}
        registradas = registradas.sort_values("prioridade", key=lambda s: s.map(ordem))
    revisao = _tabela(resumo["revisao_humana"], COLS_REVISAO)
    if len(revisao):  # urgentes primeiro, para o atendente ver logo
        revisao = revisao.sort_values("urgente", ascending=False)
        revisao["urgente"] = revisao["urgente"].map({True: "SIM", False: "não"})
        revisao = revisao.rename(columns={"categoria": "categoria_sugerida"})
    rejeitadas = _tabela(resumo["rejeitadas"], ["id_solicitacao", "arquivo_origem", "motivos", "mensagem_cidadao"])
    pendentes = _tabela(resumo["pendentes"], COLS_PENDENTES)

    larguras = {"descricao": 50, "justificativa": 55, "mensagem_cidadao": 60, "motivos": 45,
                "orgao_responsavel": 30, "protocolo": 17, "id_solicitacao": 13, "endereco": 28,
                "motivo_revisao": 35, "motivo_pendencia": 35, "segunda_opcao": 20, "cidadao": 16}

    try:
        with pd.ExcelWriter(arq_xlsx, engine="xlsxwriter") as writer:
            wb = writer.book
            f = {
                "titulo": wb.add_format({"bold": True, "font_size": 16, "font_color": "#1F3B5A"}),
                "rotulo": wb.add_format({"bold": True, "bg_color": "#E9EDF2", "border": 1}),
                "numero": wb.add_format({"border": 1, "align": "center"}),
                "quebra": wb.add_format({"text_wrap": True, "valign": "top"}),
                "alta": wb.add_format({"bg_color": "#F8C9C9", "font_color": "#8B0000", "bold": True}),
                "media": wb.add_format({"bg_color": "#FFF2B3", "font_color": "#7A5B00"}),
                "baixa": wb.add_format({"bg_color": "#D7F0D7", "font_color": "#1E5E1E"}),
            }

            # Aba Resumo
            aba = wb.add_worksheet("Resumo")
            writer.sheets["Resumo"] = aba
            aba.write("A1", "ZelaBot - Relatório de execução", f["titulo"])
            aba.write("A2", f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")
            indicadores = [
                ("Registros lidos", resumo["lidos"]),
                ("Registradas no portal", len(registradas)),
                ("Enviadas para revisão humana", len(revisao)),
                ("Rejeitadas (dados inválidos)", len(rejeitadas)),
                ("Pendentes (portal indisponível)", len(pendentes)),
                ("Duplicadas no lote (ignoradas)", resumo["duplicadas_no_lote"]),
                ("Já processadas antes (ignoradas)", resumo["ja_processadas"]),
                ("Arquivos em quarentena", len(resumo["quarentena"])),
                ("Tempo de execução (s)", resumo["duracao_s"]),
            ]
            aba.set_column("A:A", 36)
            aba.set_column("B:B", 12)
            for i, (rotulo, valor) in enumerate(indicadores, start=3):
                aba.write(i, 0, rotulo, f["rotulo"])
                aba.write(i, 1, valor, f["numero"])

            if len(registradas):
                cruz = pd.crosstab(registradas["categoria"], registradas["prioridade"])
                cruz = cruz.reindex(columns=[c for c in ["ALTA", "MÉDIA", "BAIXA"] if c in cruz.columns])
                cruz.to_excel(writer, sheet_name="Resumo", startrow=14, startcol=0)
                linhas = len(cruz)
                grafico = wb.add_chart({"type": "column", "subtype": "stacked"})
                cores = {"ALTA": "#D9534F", "MÉDIA": "#F0AD4E", "BAIXA": "#5CB85C"}
                for j, nivel in enumerate(cruz.columns, start=1):
                    grafico.add_series({
                        "name": nivel,
                        "categories": ["Resumo", 15, 0, 14 + linhas, 0],
                        "values": ["Resumo", 15, j, 14 + linhas, j],
                        "fill": {"color": cores[nivel]},
                    })
                grafico.set_title({"name": "Solicitações registradas por categoria e prioridade"})
                grafico.set_y_axis({"name": "Quantidade", "major_gridlines": {"visible": False}})
                grafico.set_size({"width": 620, "height": 330})
                aba.insert_chart("D3", grafico)

            _escrever_aba(writer, registradas, "Registradas", larguras, f)
            _escrever_aba(writer, revisao, "Revisão humana", larguras, f)
            _escrever_aba(writer, rejeitadas, "Rejeitadas", larguras, f)
            _escrever_aba(writer, pendentes, "Pendentes", larguras, f)
            if not criticos.empty:
                _escrever_aba(writer, criticos, "Pontos críticos", {"bairros": 40, "mapa": 60}, f)
            arquivos = pd.DataFrame(resumo["arquivos"] + [{"arquivo": q["arquivo"], "status": "quarentena",
                                                           "motivo": q["motivo"]} for q in resumo["quarentena"]])
            _escrever_aba(writer, arquivos, "Arquivos lidos", {"arquivo": 30, "motivo": 60}, f)
        log.info("Planilha gerada: %s", arq_xlsx.name)
    except (PermissionError, OSError) as erro:
        # caso classico: a planilha anterior esta aberta no Excel. Nao perde o JSON por isso.
        log.error("Nao consegui salvar a planilha (%s). O JSON sera gerado mesmo assim.", erro)
        arq_xlsx = None

    with open(arq_json, "w", encoding="utf-8") as fjson:
        json.dump(resumo, fjson, ensure_ascii=False, indent=2, default=str)
    log.info("Relatorio de execucao: %s", arq_json.name)
    return {"planilha": arq_xlsx, "execucao": arq_json}
