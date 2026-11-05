"""
Gera os dados SINTETICOS usados no projeto.

1) dados/treino/solicitacoes_treino.csv -> base rotulada para treinar o classificador
   (montada por templates, com variacoes e erros de digitacao de proposito).
2) entrada/ -> lotes de exemplo que o robo vai processar, cada um num formato
   diferente (CSV UTF-8, CSV antigo em CP1252, planilha Excel, JSON e um JSON quebrado).

Nenhum dado aqui e real. Nomes, CPFs e telefones sao inventados.
O conjunto de TESTE (dados/teste/teste_rotulado.csv) NAO e gerado aqui: ele foi
escrito a mao, com outro vocabulario, justamente para a avaliacao ser mais honesta.

Uso: python dados/gerar_dados.py
"""
import json
import random
from pathlib import Path

import pandas as pd

SEMENTE = 42
RAIZ = Path(__file__).resolve().parent.parent
random.seed(SEMENTE)

# Centroides aproximados de alguns bairros de Sao Paulo (informacao publica)
BAIRROS = {
    "Sé": (-23.5503, -46.6339),
    "Mooca": (-23.5587, -46.5996),
    "Pinheiros": (-23.5614, -46.7016),
    "Itaquera": (-23.5400, -46.4560),
    "Capão Redondo": (-23.6720, -46.7790),
    "Santana": (-23.5020, -46.6250),
    "Butantã": (-23.5710, -46.7080),
    "Jabaquara": (-23.6460, -46.6410),
    "Brasilândia": (-23.4690, -46.6890),
    "Cidade Tiradentes": (-23.5820, -46.4090),
}

RUAS = ["Rua das Flores", "Av. Brasil", "Rua Sete de Setembro", "Rua do Comércio",
        "Av. Paulista", "Rua Augusta", "Rua da Mooca", "Estrada do M'Boi Mirim",
        "Rua Voluntários da Pátria", "Av. Itaquera", "Rua Cardeal Arcoverde",
        "Rua Domingos de Morais", "Av. Inajar de Souza", "Rua dos Têxteis"]

# ===========================================================================
# 1) Base de treino por templates
# ===========================================================================
TEMPLATES = {
    "pavimentacao": {
        "frases": [
            "tem um {obj} {intens} na {lugar}",
            "{obj} na {lugar} esta {estado}",
            "preciso de reparo no {obj} da {lugar}",
            "o asfalto da {lugar} {estado}",
            "carros desviando de um {obj} na {lugar}",
            "pedido de tapa buraco na {lugar}",
            "{obj} {intens} perto da {lugar}, ja estourou pneu",
            "a {lugar} ta cheia de {obj}",
        ],
        "obj": ["buraco", "cratera", "asfalto afundado", "pavimento quebrado",
                "valeta no asfalto", "remendo solto", "afundamento"],
        "estado": ["todo esburacado", "cedendo", "quebrado", "afundando",
                   "cheio de remendo mal feito", "rachado"],
    },
    "iluminacao": {
        "frases": [
            "{obj} {estado} na {lugar}",
            "a {lugar} esta toda escura, {obj} {estado}",
            "trocar lampada do {obj} na {lugar}",
            "{obj} {estado} faz {tempo}",
            "rua sem luz a noite, {obj} {estado}",
            "o {obj} da {lugar} fica piscando",
            "{obj} aceso de dia e apagado a noite na {lugar}",
        ],
        "obj": ["poste", "lampada do poste", "luminaria", "iluminacao publica",
                "refletor da praca", "luz do poste"],
        "estado": ["apagado", "queimado", "sem funcionar", "piscando",
                   "com a lampada queimada", "desligado"],
    },
    "limpeza": {
        "frases": [
            "{obj} acumulado na {lugar}",
            "jogaram {obj} na {lugar}",
            "a coleta nao passou e tem {obj} na {lugar}",
            "pedido de remocao de {obj} na {lugar}",
            "{obj} {intens} na calcada da {lugar}, ta com mau cheiro",
            "descarte irregular de {obj} na {lugar}",
            "a {lugar} virou ponto de {obj}",
        ],
        "obj": ["lixo", "entulho", "sofa velho", "restos de obra", "sacos de lixo",
                "moveis velhos", "lixo e entulho", "caçamba lotada", "animal morto"],
        "estado": ["espalhado", "acumulado"],
    },
    "drenagem": {
        "frases": [
            "{obj} {estado} na {lugar}",
            "quando chove a {lugar} {alaga}",
            "{obj} {estado} e a agua nao escoa na {lugar}",
            "pedido de limpeza de {obj} na {lugar}",
            "a {lugar} {alaga} toda vez que chove forte",
            "{obj} sem tampa na {lugar}",
            "agua parada e {obj} {estado} na {lugar}",
        ],
        "obj": ["bueiro", "boca de lobo", "galeria pluvial", "corrego", "sarjeta",
                "grelha de escoamento"],
        "estado": ["entupido", "transbordando", "cheio de lixo", "quebrado",
                   "obstruido", "sem tampa"],
        "alaga": ["alaga", "vira um rio", "enche de agua", "fica alagada",
                  "inunda"],
    },
    "arvores": {
        "frases": [
            "{obj} {estado} na {lugar}",
            "pedido de poda de {obj} na {lugar}",
            "{obj} {estado} encostando nos fios na {lugar}",
            "uma {obj} caiu na {lugar}",
            "{obj} com cupim {estado} na {lugar}",
            "galhos da {obj} {estado} sobre a calcada da {lugar}",
            "raiz da {obj} levantou a calcada na {lugar}",
        ],
        "obj": ["arvore", "galho", "arvore grande", "galhada", "tronco",
                "arvore antiga"],
        "estado": ["inclinada", "ameacando cair", "seca", "com galho quebrado",
                   "muito alta", "rachada", "pendurado"],
    },
}
INTENSIDADE = ["enorme", "grande", "perigoso", "gigante", "muito grande", "", ""]
LUGARES = ["rua", "avenida", "esquina", "praca", "rua de casa", "frente da escola",
           "frente do mercado", "travessa", "viela", "rua principal do bairro"]
TEMPOS = ["uma semana", "dias", "um mes", "mais de 15 dias", "muito tempo"]
ABERTURAS = ["", "", "bom dia, ", "ola, ", "por favor, ", "gostaria de avisar que ",
             "boa tarde prefeitura, ", "socorro, "]
FECHAMENTOS = ["", "", " ninguem resolve", " favor verificar", " obrigado",
               " ja reclamei antes", " urgente", " ta perigoso"]


def bagunca(texto: str) -> str:
    """Simula erros comuns de digitacao do cidadao (sem acento, letra trocada)."""
    if random.random() < 0.25:
        i = random.randrange(len(texto))
        texto = texto[:i] + texto[i + 1:]
    if random.random() < 0.2:
        texto = texto.upper()
    return texto


def frase_treino(cat: str) -> str:
    t = TEMPLATES[cat]
    frase = random.choice(t["frases"])
    preenchimento = {
        "obj": random.choice(t["obj"]),
        "estado": random.choice(t["estado"]),
        "intens": random.choice(INTENSIDADE),
        "lugar": random.choice(LUGARES),
        "tempo": random.choice(TEMPOS),
        "alaga": random.choice(t.get("alaga", ["alaga"])),
    }
    texto = random.choice(ABERTURAS) + frase.format(**preenchimento) + random.choice(FECHAMENTOS)
    return bagunca(" ".join(texto.split()))


def gerar_treino():
    # Base propositalmente DESBALANCEADA (como na vida real: buraco e lixo
    # aparecem muito mais que arvore). O modelo usa class_weight="balanced".
    quantidades = {"pavimentacao": 160, "limpeza": 140, "iluminacao": 110,
                   "drenagem": 80, "arvores": 60}
    linhas = []
    for cat, qtd in quantidades.items():
        vistos = set()
        while len([l for l in linhas if l["categoria"] == cat]) < qtd:
            texto = frase_treino(cat)
            if texto not in vistos:
                vistos.add(texto)
                linhas.append({"texto": texto, "categoria": cat})
    df = pd.DataFrame(linhas).sample(frac=1, random_state=SEMENTE)
    destino = RAIZ / "dados" / "treino" / "solicitacoes_treino.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False, encoding="utf-8")
    print(f"treino: {len(df)} linhas -> {destino.relative_to(RAIZ)}")


# ===========================================================================
# 2) Lotes de entrada (textos escritos a mao, diferentes dos templates)
# ===========================================================================
NOMES = ["Ana Teste", "Bruno Ficticio", "Carla Exemplo", "Diego Sintetico",
         "Elisa Modelo", "Fabio Demo", "Gabi Simulada", "Heitor Fake",
         "Iara Amostra", "Joao Inventado", "Kelly Prototipo", "Lucas Mock"]

TEXTOS_APP = [
    "Tem um buraco enorme na frente do número 120, já vi moto caindo ali semana passada",
    "Poste apagado na esquina faz uns 10 dias, tá muito perigoso voltar a pé à noite",
    "Jogaram um sofá e um monte de entulho na calçada, não dá pra passar com carrinho de bebê",
    "Bueiro entupido, qualquer chuvinha a rua vira um rio. Meu telefone é (11) 98765-4321",
    "A árvore da praça está inclinada e com rachadura no tronco, tem fio passando do lado, risco de cair em cima das crianças",
    "Asfalto afundou perto do ponto de ônibus",
    "Lâmpada do poste fica piscando a noite toda",
    "Galho pendurado em cima da calçada da escola",
    "Lixo acumulado há 2 semanas, já tem rato aparecendo",
    "Bueiro sem tampa no meio da calçada, um idoso quase caiu dentro",
]
TEXTOS_TOTEM = [  # sistema antigo, salva em CP1252 com ';'
    "Calçada toda quebrada e cheia de buraco na Rua do Comércio",
    "Rua escura, a iluminação pública não funciona desde o mês passado",
    "Caçamba de entulho largada há dias ocupando a rua",
    "Córrego transbordando quando chove e a água entra nas casas",
    "Raiz da árvore levantou toda a calçada, cadeirante não consegue passar",
    "Preciso de poda, os galhos estão encostando na fiação",
    "oi",  # curto demais: deve ser rejeitado pela validacao
]
TEXTOS_SUBPREF = [  # planilha que a subprefeitura manda
    "Cratera aberta depois da obra da companhia de água, carro já caiu dentro",
    "Refletor da quadra pública queimado",
    "Descarte irregular de móveis velhos na viela",
    "Boca de lobo cheia de lixo e folhas",
    "Árvore seca com cupim ameaçando cair em cima de casa",
    "Barulho de festa do vizinho toda madrugada",  # fora do escopo de zeladoria
    "Sinal de trânsito com defeito no cruzamento",  # ambiguo / fora do escopo
]
TEXTOS_SITE = [
    "Rua inteira esburacada, o ônibus nem quer mais entrar no bairro",
    "Poste com fio solto pendurado e soltando faísca, perigo de choque!!",
    "Animal morto na calçada há 3 dias, cheiro insuportável",
    "Sarjeta obstruída, água parada e foco de dengue. CPF 123.456.789-09 para contato",
    "Pedido de poda de árvore grande em frente ao posto de saúde",
]


def registro(i, prefixo, texto, canal, bairro=None, data="2026-11-03 09:00"):
    bairro = bairro or random.choice(list(BAIRROS))
    lat, lon = BAIRROS[bairro]
    return {
        "id_solicitacao": f"{prefixo}-{i:04d}",
        "data_hora": data,
        "canal": canal,
        "nome": random.choice(NOMES),
        "bairro": bairro,
        "endereco": f"{random.choice(RUAS)}, {random.randint(10, 2500)}",
        # jitter pequeno para os pontos nao ficarem todos em cima do centroide
        "latitude": round(lat + random.uniform(-0.008, 0.008), 5),
        "longitude": round(lon + random.uniform(-0.008, 0.008), 5),
        "descricao": texto,
    }


def gerar_entrada():
    pasta = RAIZ / "entrada"
    pasta.mkdir(exist_ok=True)

    # (a) App 156, CSV em UTF-8. Inclui uma linha DUPLICADA e uma sem bairro valido
    app = [registro(i + 1, "APP", t, "app", data=f"2026-11-03 {8 + i % 10:02d}:15")
           for i, t in enumerate(TEXTOS_APP)]
    app.append(dict(app[0]))  # duplicata exata (o robo deve ignorar)
    ruim = registro(99, "APP", "Buraco gigante na rua, carro quebrou a roda", "app")
    ruim["bairro"], ruim["latitude"], ruim["longitude"] = "Bairro Inexistente", "abc", ""
    app.append(ruim)
    pd.DataFrame(app).to_csv(pasta / "app156_2026-11-03.csv", index=False, encoding="utf-8")

    # (b) Totem antigo: CSV com ';' e encoding CP1252 (Windows). Tem data no futuro.
    totem = [registro(i + 1, "TOT", t, "totem") for i, t in enumerate(TEXTOS_TOTEM)]
    totem[1]["data_hora"] = "2031-01-01 10:00"  # data invalida (futuro)
    pd.DataFrame(totem).to_csv(pasta / "totem_legado.csv", index=False, sep=";", encoding="cp1252")

    # (c) Planilha da subprefeitura (Excel)
    sub = [registro(i + 1, "SUB", t, "subprefeitura") for i, t in enumerate(TEXTOS_SUBPREF)]
    pd.DataFrame(sub).to_excel(pasta / "subprefeitura_lote.xlsx", index=False)

    # (d) Formulario do site, exportado em JSON
    site = [registro(i + 1, "WEB", t, "site") for i, t in enumerate(TEXTOS_SITE)]
    with open(pasta / "formulario_site.json", "w", encoding="utf-8") as f:
        json.dump(site, f, ensure_ascii=False, indent=2)

    # (e) Arquivo corrompido (exportacao interrompida no meio)
    with open(pasta / "exportacao_interrompida.json", "w", encoding="utf-8") as f:
        f.write('[{"id_solicitacao": "ERR-0001", "descricao": "Buraco na ')

    total = len(app) + len(totem) + len(sub) + len(site)
    print(f"entrada: 5 arquivos, {total} registros (+1 arquivo corrompido) -> entrada/")


if __name__ == "__main__":
    gerar_treino()
    gerar_entrada()
