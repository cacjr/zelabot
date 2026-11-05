"""
TEMA: Machine Learning (classificador de texto + clusterizacao)

1) Classificador: le a descricao do cidadao e diz a categoria do problema
   (pavimentacao, iluminacao, limpeza, drenagem ou arvores) com uma CONFIANCA.
   - TF-IDF de palavras (pega "boca de lobo") + TF-IDF de pedacos de letras
     (aguenta erro de digitacao tipo "bueiero").
   - Regressao Logistica com class_weight="balanced", porque a base e
     desbalanceada (tem bem mais buraco do que arvore).
   - Se a confianca ficar abaixo do limiar, o robo NAO decide: manda para revisao humana.

2) KMeans: agrupa as solicitacoes pela localizacao para achar "pontos criticos"
   (lugares com muitas reclamacoes juntas), util para a prefeitura planejar mutirao.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.pipeline import FeatureUnion, Pipeline

from src.config import ARQ_MODELO, ARQ_TREINO, LIMIAR_CONFIANCA
from src.logs import obter_logger
from src.validacao import normalizar

log = obter_logger("modelo")

CATEGORIAS = ["pavimentacao", "iluminacao", "limpeza", "drenagem", "arvores"]


def criar_pipeline() -> Pipeline:
    vetorizador = FeatureUnion([
        ("palavras", TfidfVectorizer(preprocessor=normalizar, ngram_range=(1, 2), min_df=1)),
        ("letras", TfidfVectorizer(preprocessor=normalizar, analyzer="char_wb",
                                   ngram_range=(3, 5), min_df=2, sublinear_tf=True)),
    ])
    classificador = LogisticRegression(class_weight="balanced", max_iter=2000, C=4.0)
    return Pipeline([("tfidf", vetorizador), ("clf", classificador)])


def treinar(salvar=True) -> Pipeline:
    if not ARQ_TREINO.exists():
        raise FileNotFoundError(
            f"Base de treino nao encontrada em {ARQ_TREINO}. Rode: python dados/gerar_dados.py")
    df = pd.read_csv(ARQ_TREINO, encoding="utf-8").dropna()
    log.info("Treinando com %d exemplos. Distribuicao: %s",
             len(df), df["categoria"].value_counts().to_dict())

    pipeline = criar_pipeline()
    # validacao cruzada so como sanidade (base sintetica, vai dar alto mesmo)
    f1 = cross_val_score(pipeline, df["texto"], df["categoria"], cv=5, scoring="f1_macro")
    log.info("F1 macro na validacao cruzada (base de treino sintetica): %.3f", f1.mean())

    pipeline.fit(df["texto"], df["categoria"])
    if salvar:
        joblib.dump(pipeline, ARQ_MODELO)
        log.info("Modelo salvo em %s", ARQ_MODELO.name)
    return pipeline


def carregar() -> Pipeline:
    """Carrega o modelo salvo; se nao existir ou estiver quebrado, treina de novo."""
    if ARQ_MODELO.exists():
        try:
            return joblib.load(ARQ_MODELO)
        except Exception as erro:
            log.warning("Modelo salvo ilegivel (%s). Vou treinar de novo.", erro)
    return treinar()


def classificar(modelo: Pipeline, textos: list[str], limiar=LIMIAR_CONFIANCA) -> list[dict]:
    probabilidades = modelo.predict_proba(textos)
    classes = modelo.classes_
    resultado = []
    for linha in probabilidades:
        ordem = np.argsort(linha)[::-1]
        melhor, segunda = ordem[0], ordem[1]
        confianca = float(linha[melhor])
        resultado.append({
            "categoria": classes[melhor],
            "confianca": round(confianca, 3),
            "segunda_opcao": f"{classes[segunda]} ({linha[segunda]:.0%})",
            "precisa_revisao": confianca < limiar,
        })
    return resultado


def palavras_mais_importantes(modelo: Pipeline, n=6) -> dict:
    """Mostra quais palavras mais pesam em cada categoria (ajuda a explicar o modelo)."""
    vetor_palavras = modelo.named_steps["tfidf"].transformer_list[0][1]
    nomes = vetor_palavras.get_feature_names_out()
    coef = modelo.named_steps["clf"].coef_[:, :len(nomes)]
    return {cat: [nomes[i] for i in np.argsort(coef[k])[::-1][:n]]
            for k, cat in enumerate(modelo.classes_)}


def pontos_criticos(df: pd.DataFrame, max_grupos=5) -> pd.DataFrame:
    """KMeans nas coordenadas. Devolve um resumo por grupo (centro, qtd, categoria mais comum)."""
    if len(df) < 4:
        return pd.DataFrame()
    k = min(max_grupos, max(2, len(df) // 4))
    km = KMeans(n_clusters=k, n_init=10, random_state=42)
    df = df.copy()
    df["grupo"] = km.fit_predict(df[["latitude", "longitude"]].astype(float))
    resumo = (df.groupby("grupo")
                .agg(qtd_solicitacoes=("id_solicitacao", "count"),
                     bairros=("bairro", lambda s: ", ".join(sorted(set(s)))),
                     categoria_mais_comum=("categoria", lambda s: s.mode().iat[0]),
                     prioridade_alta=("prioridade", lambda s: int((s == "ALTA").sum())))
                .reset_index())
    resumo["centro_lat"] = km.cluster_centers_[resumo["grupo"], 0].round(4)
    resumo["centro_lon"] = km.cluster_centers_[resumo["grupo"], 1].round(4)
    resumo["mapa"] = ("https://www.openstreetmap.org/?mlat=" + resumo["centro_lat"].astype(str)
                      + "&mlon=" + resumo["centro_lon"].astype(str) + "#map=15/"
                      + resumo["centro_lat"].astype(str) + "/" + resumo["centro_lon"].astype(str))
    return resumo.sort_values("qtd_solicitacoes", ascending=False)
