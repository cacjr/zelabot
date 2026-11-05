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
    log.info("Arquivos salvos em %s", PASTA_EVID.relative_to(RAIZ))
    return resultado
