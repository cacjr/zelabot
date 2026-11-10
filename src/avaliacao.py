"""
Avaliacao do robo num conjunto de TESTE ROTULADO escrito a mao
(dados/teste/teste_rotulado.csv), separado da base de treino.

Mede:
  1) o classificador sozinho (acuracia, F1 por classe, matriz de confusao);
  2) uma linha de base simples por palavras-chave, para ver se o ML vale a pena;
  3) o robo completo com o limiar de confianca (quanto ele automatiza, quanto acerta
     no que automatiza e quantos erros ele "segura" na revisao humana);
  4) a regra de urgencia (pegou os casos de risco?).
Tudo e salvo em docs/evidencias/.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, f1_score,
                             precision_score, recall_score)

from src import modelo
from src.config import ARQ_TESTE, LIMIAR_CONFIANCA, RAIZ
from src.logs import obter_logger
from src.prioridade import detectar_risco
from src.validacao import normalizar

log = obter_logger("avaliacao")
PASTA_EVID = RAIZ / "docs" / "evidencias"

# Linha de base: o que um robo SEM machine learning faria (regra fixa de palavra-chave)
PALAVRAS_CHAVE = {
    "pavimentacao": ["buraco", "asfalto", "cratera", "pavimento"],
    "iluminacao": ["poste", "lampada", "luz", "iluminacao"],
    "limpeza": ["lixo", "entulho", "sujeira"],
    "drenagem": ["bueiro", "alaga", "boca de lobo", "enchente"],
    "arvores": ["arvore", "galho", "poda"],
}


def classificar_por_palavra(texto):
    t = normalizar(texto)
    pontos = {cat: sum(p in t for p in palavras) for cat, palavras in PALAVRAS_CHAVE.items()}
    melhor = max(pontos, key=pontos.get)
    return melhor if pontos[melhor] > 0 else "sem_resposta"


def _metricas_robo(df, limiar):
    automatico = df["confianca"] >= limiar
    no_escopo = df["categoria_esperada"] != "fora_escopo"
    acerto = df["prevista"] == df["categoria_esperada"]
    auto_escopo = automatico & no_escopo
    return {
        "limiar": limiar,
        "automatizadas_pct": round(100 * automatico.mean(), 1),
        "acerto_nas_automatizadas_pct": round(100 * acerto[automatico].mean(), 1) if automatico.any() else None,
        "erros_silenciosos": int((automatico & ~acerto).sum()),
        "fora_escopo_para_revisao": f"{int((~automatico & ~no_escopo).sum())}/{int((~no_escopo).sum())}",
        "erros_seguros_na_revisao": int((~automatico & no_escopo & ~acerto).sum()),
        "acertos_mandados_a_revisao": int((~automatico & no_escopo & acerto).sum()),
        "automatizadas_no_escopo": int(auto_escopo.sum()),
    }


def intervalo_95(acertos):
    """
    Intervalo de confianca de 95% (Wilson) para uma taxa de acerto.
    Com amostra pequena o intervalo fica largo, e isso precisa aparecer no relatorio.
    Escolhemos Wilson porque ele continua informativo mesmo quando acerta 100%
    (o bootstrap, por exemplo, devolveria [100, 100] para 23 de 23).
    """
    acertos = np.asarray(acertos, dtype=float)
    n = len(acertos)
    if n == 0:
        return None
    p, z = acertos.mean(), 1.96
    centro = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    margem = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / (1 + z**2 / n)
    return [round(100 * float(centro - margem), 1), round(100 * float(min(1.0, centro + margem)), 1)]


def avaliar_lote_de_entrada(clf):
    """
    Mede as decisoes do robo nos 31 registros da pasta entrada/, comparando com o
    gabarito rotulado pelo grupo (dados/teste/gabarito_entrada.csv). Usa as mesmas
    funcoes do robo (leitura, validacao, modelo e regra de risco), sem o portal,
    entao nao mexe no estado nem cadastra nada.
    """
    from src import leitura, validacao
    from src.config import PASTA_ENTRADA

    gabarito = pd.read_csv(RAIZ / "dados" / "teste" / "gabarito_entrada.csv", dtype=str).fillna("")
    gabarito = gabarito.set_index("id_solicitacao")
    vistos, linhas = set(), []
    for arq in leitura.listar_arquivos(PASTA_ENTRADA):
        try:
            registros = leitura.ler_arquivo(arq)
        except (leitura.ArquivoInvalido, FileNotFoundError):
            continue  # o corrompido vai para quarentena no robo; aqui so pulamos
        for r in registros:
            rid = str(r.get("id_solicitacao")).strip()
            if rid in vistos or rid not in gabarito.index:
                continue
            vistos.add(rid)
            limpo, motivos = validacao.validar(r)
            if motivos:
                decisao, categoria, urgente = "rejeitar", "", False
            else:
                pred = modelo.classificar(clf, [limpo["descricao"]])[0]
                decisao = "revisao" if pred["precisa_revisao"] else "processar"
                categoria, urgente = pred["categoria"], detectar_risco(limpo["descricao"])
            g = gabarito.loc[rid]
            linhas.append({"id_solicitacao": rid, "esperado": g["resultado_esperado"],
                           "categoria_esperada": g["categoria_esperada"], "decisao": decisao,
                           "categoria_robo": categoria, "urgente_esperado": int(g["urgente_esperado"]),
                           "urgente_robo": int(urgente)})
    df = pd.DataFrame(linhas)

    rejeitar = df["esperado"] == "rejeitar"
    fora = df["esperado"] == "revisao"
    escopo = df["esperado"] == "processar"
    automatico = df["decisao"] == "processar"
    certo_auto = automatico & escopo & (df["categoria_robo"] == df["categoria_esperada"])
    erro_silencioso = automatico & ~certo_auto
    # para a urgencia so contam os pedidos que passaram da validacao
    validos = df["decisao"] != "rejeitar"
    u_esp, u_robo = df.loc[validos, "urgente_esperado"], df.loc[validos, "urgente_robo"]

    df.to_csv(PASTA_EVID / "avaliacao_lote_entrada.csv", index=False, encoding="utf-8")
    return {
        "registros_unicos": len(df),
        "rejeicoes_corretas": f"{int((rejeitar & (df['decisao'] == 'rejeitar')).sum())}/{int(rejeitar.sum())}",
        "fora_do_escopo_para_revisao": f"{int((fora & (df['decisao'] == 'revisao')).sum())}/{int(fora.sum())}",
        "automatizadas": int(automatico.sum()),
        "automatizadas_com_categoria_certa": f"{int(certo_auto.sum())}/{int(automatico.sum())}",
        "intervalo_95_acerto_automatizadas": intervalo_95(certo_auto[automatico]),
        "no_escopo_mandadas_a_revisao": int((escopo & (df["decisao"] == "revisao")).sum()),
        "erros_silenciosos": int(erro_silencioso.sum()),
        "urgencia_recall": f"{int((u_esp.eq(1) & u_robo.eq(1)).sum())}/{int(u_esp.eq(1).sum())}",
        "urgencia_alarmes_falsos": df.loc[validos & df["urgente_esperado"].eq(0) & df["urgente_robo"].eq(1),
                                          "id_solicitacao"].tolist(),
        "urgentes_perdidos": df.loc[validos & df["urgente_esperado"].eq(1) & df["urgente_robo"].eq(0),
                                    "id_solicitacao"].tolist(),
    }


def avaliar():
    PASTA_EVID.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ARQ_TESTE, encoding="utf-8")
    clf = modelo.carregar()
    preds = modelo.classificar(clf, df["texto"].tolist(), limiar=LIMIAR_CONFIANCA)
    df["prevista"] = [p["categoria"] for p in preds]
    df["confianca"] = [p["confianca"] for p in preds]
    df["segunda_opcao"] = [p["segunda_opcao"] for p in preds]
    df["base_palavras"] = df["texto"].map(classificar_por_palavra)
    df["risco_detectado"] = df["texto"].map(detectar_risco).astype(int)

    esc = df[df["categoria_esperada"] != "fora_escopo"]
    y, yp, yb = esc["categoria_esperada"], esc["prevista"], esc["base_palavras"]
    rel = classification_report(y, yp, output_dict=True, zero_division=0)

    resultado = {
        "amostra": {"total": len(df), "no_escopo": len(esc), "fora_escopo": int((df["categoria_esperada"] == "fora_escopo").sum()),
                    "por_categoria": df["categoria_esperada"].value_counts().to_dict()},
        "classificador_ml": {
            "acuracia": round(accuracy_score(y, yp), 3),
            "f1_macro": round(f1_score(y, yp, average="macro"), 3),
            "por_classe": {c: {"precisao": round(rel[c]["precision"], 2), "recall": round(rel[c]["recall"], 2),
                               "f1": round(rel[c]["f1-score"], 2), "n": int(rel[c]["support"])}
                           for c in modelo.CATEGORIAS},
        },
        "linha_de_base_palavras_chave": {
            "acuracia": round(accuracy_score(y, yb), 3),
            "f1_macro": round(f1_score(y, yb, average="macro", labels=modelo.CATEGORIAS, zero_division=0), 3),
            "sem_resposta": int((yb == "sem_resposta").sum()),
        },
        "robo_com_limiar": _metricas_robo(df, LIMIAR_CONFIANCA),
        "varredura_limiar": [_metricas_robo(df, round(l, 2)) for l in np.arange(0.30, 0.71, 0.05)],
        "regra_de_urgencia": {
            "recall": round(recall_score(df["urgente_esperado"], df["risco_detectado"]), 3),
            "precisao": round(precision_score(df["urgente_esperado"], df["risco_detectado"]), 3),
            "urgentes_reais": int(df["urgente_esperado"].sum()),
            "urgentes_perdidos": df.loc[(df["urgente_esperado"] == 1) & (df["risco_detectado"] == 0), "texto"].tolist(),
            "alarmes_falsos": df.loc[(df["urgente_esperado"] == 0) & (df["risco_detectado"] == 1), "texto"].tolist(),
        },
        "palavras_que_mais_pesam": modelo.palavras_mais_importantes(clf),
    }
    automatico = df["confianca"] >= LIMIAR_CONFIANCA
    resultado["intervalos_95_wilson"] = {
        "acuracia_ml_no_escopo": intervalo_95(yp == y),
        "acerto_nas_automatizadas": intervalo_95((df["prevista"] == df["categoria_esperada"])[automatico]),
    }
    resultado["lote_de_entrada_com_gabarito"] = avaliar_lote_de_entrada(clf)

    # erros para analise
    erros = df[(df["prevista"] != df["categoria_esperada"])].copy()
    erros["foi_para_revisao"] = erros["confianca"] < LIMIAR_CONFIANCA
    erros[["texto", "categoria_esperada", "prevista", "confianca", "segunda_opcao", "foi_para_revisao"]] \
        .sort_values("confianca", ascending=False).to_csv(PASTA_EVID / "avaliacao_erros.csv", index=False, encoding="utf-8")
    df.to_csv(PASTA_EVID / "avaliacao_predicoes.csv", index=False, encoding="utf-8")

    # matriz de confusao (so as categorias do escopo)
    cm = confusion_matrix(y, yp, labels=modelo.CATEGORIAS)
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(5), modelo.CATEGORIAS, rotation=35, ha="right")
    ax.set_yticks(range(5), modelo.CATEGORIAS)
    for i in range(5):
        for j in range(5):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if cm[i, j] > cm.max() / 2 else "black")
    ax.set_xlabel("Previsto pelo modelo")
    ax.set_ylabel("Rótulo correto")
    ax.set_title(f"Matriz de confusão (teste, n={len(esc)})")
    fig.tight_layout()
    fig.savefig(PASTA_EVID / "matriz_confusao.png", dpi=130)
    plt.close(fig)

    with open(PASTA_EVID / "avaliacao_resultados.json", "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    r, b, rb, u = (resultado["classificador_ml"], resultado["linha_de_base_palavras_chave"],
                   resultado["robo_com_limiar"], resultado["regra_de_urgencia"])
    log.info("ML: acuracia %.1f%% | F1 macro %.3f (n=%d)", r["acuracia"] * 100, r["f1_macro"], len(esc))
    log.info("Linha de base palavras-chave: acuracia %.1f%% | F1 macro %.3f | %d sem resposta",
             b["acuracia"] * 100, b["f1_macro"], b["sem_resposta"])
    log.info("Robo (limiar %.2f): automatiza %.1f%%, acerta %.1f%% do que automatiza, %d erros silenciosos, "
             "fora do escopo para revisao: %s", LIMIAR_CONFIANCA, rb["automatizadas_pct"],
             rb["acerto_nas_automatizadas_pct"], rb["erros_silenciosos"], rb["fora_escopo_para_revisao"])
    log.info("Urgencia: recall %.2f | precisao %.2f", u["recall"], u["precisao"])
    ic = resultado["intervalos_95_wilson"]
    log.info("Intervalo de 95%%: acuracia ML %s%% | acerto nas automatizadas %s%%",
             ic["acuracia_ml_no_escopo"], ic["acerto_nas_automatizadas"])
    lote = resultado["lote_de_entrada_com_gabarito"]
    log.info("Lote de entrada (gabarito): rejeicoes %s | fora do escopo p/ revisao %s | categoria certa %s "
             "| erros silenciosos %d | urgencia %s", lote["rejeicoes_corretas"], lote["fora_do_escopo_para_revisao"],
             lote["automatizadas_com_categoria_certa"], lote["erros_silenciosos"], lote["urgencia_recall"])
    log.info("Arquivos salvos em %s", PASTA_EVID.relative_to(RAIZ))
    return resultado
