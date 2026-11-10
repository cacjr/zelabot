# ZelaBot: robô de zeladoria urbana com RPA + IA

**Global Solution 2026.2 | AI for Robotic Process Automation (RPA + IA)**

O ZelaBot é um robô que recebe as reclamações de zeladoria dos moradores (buraco, poste apagado, lixo, bueiro entupido, árvore com risco de cair), entende o que cada uma pede, decide a prioridade, registra tudo no sistema da prefeitura com um protocolo e devolve uma resposta para o cidadão. O que ele não tem certeza, ele não chuta: manda para uma pessoa revisar.

## Integrantes

| Nome | RM |
| :- | :- |
| Claudio Alves | RM568565 |
| Gustavo Duarte | RM567066 |
| Leonardo Pereira | RM567836 |

## Onde está cada exigência do enunciado

Para facilitar a correção, cada item do enunciado e do barema aponta para onde ele está no repositório.

| Exigência | Onde está |
| :- | :- |
| Código executável do início ao fim, com ponto de entrada claro | `python main.py` ([main.py](main.py)), seção [Como executar](#como-executar) |
| README com integrantes, problema, como executar e como configurar as chaves | Este arquivo |
| Quadro de temas (mínimo de 3, com função real e justificativa) | [Quadro de temas](#quadro-de-temas) abaixo e [docs/quadro_de_temas.md](docs/quadro_de_temas.md) |
| Evidências: execução com dados de teste, resultado medido e caso de falha tratado | [docs/evidencias_validacao.md](docs/evidencias_validacao.md) e [docs/evidencias/](docs/evidencias/) |
| Conjunto de teste rotulado, análise dos erros e limites (diferencial) | [dados/teste/](dados/teste/) e seções 2, 4 e 5 das evidências |
| Timeout, retry com espera, idempotência, relatório de execução e revisão humana (diferencial) | [Resiliência](docs/quadro_de_temas.md#tema-4-tratamento-de-erros-e-logs) e `python main.py falhas` |
| Proteção de dados, ética e ODS | [Seção abaixo](#proteção-de-dados-ética-e-ods) e [docs/dados_etica_ods.md](docs/dados_etica_ods.md) |
| Chaves fora do código | [.env.example](.env.example) (o `.env` real está no `.gitignore`) |
| Só ferramentas gratuitas e dados sintéticos | Python, bibliotecas open source, API Open-Meteo sem chave, dados gerados por [dados/gerar_dados.py](dados/gerar_dados.py) |

## O problema

Quem mora numa cidade grande conhece a história: você reclama do buraco pelo app, o vizinho reclama do mesmo buraco pelo totem, a subprefeitura manda uma planilha, e alguém da prefeitura precisa ler tudo isso, entender do que se trata, descobrir para qual setor mandar, decidir o que é urgente e digitar uma por uma num sistema antigo. Esse trabalho manual é lento, repetitivo e cheio de chance de erro. O resultado aparece para o cidadão como demora e falta de resposta, e o pior caso é quando algo perigoso (um fio soltando faísca, uma árvore prestes a cair perto de uma escola) fica na fila junto com um saco de lixo.

**Público afetado:** moradores que usam os canais de zeladoria (principalmente de bairros periféricos, onde os problemas costumam se acumular) e os servidores da triagem, que hoje gastam o dia copiando e colando.

**O que o protótipo faz:** automatiza a triagem e o registro de ponta a ponta, deixando o servidor livre para os casos que realmente precisam de julgamento humano.

## Como o robô funciona

```mermaid
flowchart LR
    A[Pasta entrada/<br>CSV, Excel, JSON] ==> B[T1 Ler arquivos<br>encoding + chunking]
    B ==> C[T2 Tirar duplicadas<br>idempotência]
    C ==> D[T3 Validar dados<br>GIGO + LGPD]
    D ==> E[T4 Classificar<br>modelo de ML]
    E ==> F[T5 Priorizar<br>regras + API de clima]
    F ==> G[T6 Registrar no portal<br>Selenium]
    G ==> H[T7 Responder cidadão]
    H ==> I[T8 Pontos críticos<br>KMeans]
    I ==> J[T9 Relatórios<br>Excel + JSON + log]
    B -. arquivo ruim .-> Q[(Quarentena)]
    D -. dado inválido .-> R[(Rejeitadas +<br>mensagem ao cidadão)]
    E -. confiança baixa .-> S[(Revisão humana)]
    G -. portal fora do ar .-> P[(Pendentes<br>reprocessa depois)]
```

As linhas pontilhadas são os **caminhos seguros**: cada tipo de problema vai para uma fila própria, com o motivo registrado, e o restante continua rodando. Nada para a execução inteira.

O "sistema da prefeitura" é um **portal web simulado** que fizemos (pasta `portal/`), com login e formulário, para o robô ter onde trabalhar de verdade. Ele roda localmente e sobe junto com o robô.

## Quadro de temas

Usamos 6 temas da disciplina, cada um fazendo uma parte real do fluxo. O detalhamento de cada um, e a lista dos temas que decidimos **não** usar (com o motivo), estão em [docs/quadro_de_temas.md](docs/quadro_de_temas.md).

| Tema | Onde foi usado no fluxo | O que resolve | Por que escolhemos |
| :- | :- | :- | :- |
| **1. Automação web com Selenium** | T6, [src/rpa_portal.py](src/rpa_portal.py) | Faz login no portal e cadastra cada solicitação como um servidor faria, com espera explícita, retry e print da tela quando dá erro. Elimina a digitação manual. | Sistemas públicos antigos quase nunca têm API, então automatizar pela interface é o caso clássico de RPA. Preferimos Selenium a PyAutoGUI porque ele encontra os campos pela página, e não por coordenadas da tela. |
| **2. Arquivos e I/O** (encoding, chunking, modos de abertura, monitoramento de pasta com watchdog) | T1, [src/leitura.py](src/leitura.py) e modo `vigiar` do [main.py](main.py) | Lê o que cada canal manda do seu jeito: CSV em UTF-8, CSV antigo em CP1252 com `;`, Excel e JSON. Arquivo quebrado vai para quarentena. No modo vigia, processa sozinho cada arquivo que chega. | A "entrada do cidadão" que o enunciado cita chega como arquivo, e cada canal grava diferente. Sem tratar encoding, "Calçada" vira "CalÃ§ada" ou o robô quebra. |
| **3. Automação de Excel** (pandas + calamine para ler, XlsxWriter para escrever) | T1 e T9, [src/relatorio.py](src/relatorio.py) | Lê a planilha da subprefeitura e gera a planilha final para a equipe, com abas por situação, cores por prioridade, filtros e gráfico. | A prefeitura trabalha com Excel. Seguimos a recomendação da aula: calamine para ler rápido e XlsxWriter para escrever com formatação e gráfico. |
| **4. Tratamento de erros e logs** | Todo o fluxo, [src/resiliencia.py](src/resiliencia.py) e [src/logs.py](src/logs.py) | Retry com espera exponencial, timeout, disjuntor, fila de pendentes, quarentena, idempotência e log de cada passo. O robô não cai por causa de uma falha previsível. | É o que diferencia um script de um robô: API, portal e arquivos falham na vida real, e cada falha precisa de um caminho seguro. |
| **5. HyperAutomation: RPA + IA/ML** (classificador, balanceamento, KMeans) | T4 e T8, [src/modelo.py](src/modelo.py) | O classificador entende o texto livre do cidadão; o limiar de confiança decide quando chamar um humano; o KMeans acha pontos críticos para a prefeitura planejar mutirões. | Uma regra fixa por palavra-chave não entende "a rua tá parecendo queijo suíço". Medimos: o ML acertou 86,3% contra 70,6% da regra. Não usamos LLM para não mandar texto do cidadão para fora e manter o resultado reproduzível. |
| **6. BPM (processo, tarefa e relação) + qualidade de dados (GIGO)** | Estrutura do [src/pipeline.py](src/pipeline.py) e T3, [src/validacao.py](src/validacao.py) | Mapeamos o processo AS-IS e desenhamos o TO-BE ([docs/processo_as_is_to_be.md](docs/processo_as_is_to_be.md)); o código segue esse desenho, tarefa por tarefa. A validação barra dado ruim antes da IA. | Foi o mapa do processo que mostrou o que é repetitivo (vai para o robô) e o que exige julgamento (fica com pessoas). E lixo entra, lixo sai: um modelo bom não salva um dado ruim. |

Complemento: o **psutil** mede memória e CPU de cada execução e isso vai para o relatório de execução.

### Como os temas se combinam

Os temas não estão lado a lado; um depende do outro. O **watchdog** percebe que chegou um arquivo, o tema de **Arquivos e I/O** lê esse arquivo do jeito certo, a **validação (GIGO)** garante que só dado bom chega ao **modelo de ML**, a categoria do modelo alimenta as **regras de prioridade** (que também consultam uma API pública), e só então o **Selenium** registra no portal. No fim, o **Excel** organiza tudo para a equipe. O **tratamento de erros e logs** envolve todas as etapas, e o desenho **BPM** define a ordem. Se uma peça falha, ela não leva as outras junto: o problema vai para a fila dele (quarentena, rejeitadas, revisão humana ou pendentes).

## Como executar

**Pré-requisitos:** Python 3.10 ou mais novo (desenvolvido e testado no 3.13) e Google Chrome instalado. Na primeira execução o Selenium baixa sozinho o driver do Chrome (precisa de internet).

1) Clonar o repositório e entrar na pasta:

```bash
git clone <url-do-repositorio>
```

```bash
cd zelabot
```

2) Criar e ativar um ambiente virtual (Windows):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

No Linux ou Mac, a ativação é `source .venv/bin/activate`.

3) Instalar as dependências:

```bash
pip install -r requirements.txt
```

4) Criar o arquivo de configuração a partir do modelo (no Linux ou Mac, use `cp` no lugar de `copy`). Ele já funciona como está; se quiser, troque a senha do portal e o sal do pseudônimo:

```bash
copy .env.example .env
```

5) Rodar o robô:

```bash
python main.py
```

Pronto. O robô sobe o portal simulado, processa os 5 arquivos de exemplo da pasta `entrada/` e gera a planilha e o relatório em `saida/relatorios/`. Leva uns 20 a 30 segundos. O resultado esperado no fim do log é:

```
FIM: 31 lidos | 23 registradas | 4 revisao humana | 3 rejeitadas | 0 pendentes | 1 quarentena | 0 ja processadas
```

### Outros comandos

| Comando | O que faz |
| :- | :- |
| `python main.py` | Execução completa, do início ao fim |
| `python main.py vigiar` | Fica vigiando a pasta `entrada/` e processa cada arquivo novo sozinho (execução sem intervenção) |
| `python main.py avaliar` | Mede o modelo no conjunto de teste rotulado e as decisões do robô no lote de entrada com gabarito; salva em `docs/evidencias/` |
| `python main.py falhas` | Roda 9 cenários de falha de propósito e confere se o robô seguiu o caminho seguro |
| `python main.py treinar` | Retreina o classificador |
| `python main.py reset` | Apaga estado e saídas para rodar do zero (a pasta `entrada/` é mantida) |
| `python -m pytest` | Roda os 20 testes automatizados (também rodam no GitHub Actions a cada push) |

Para rodar sem ninguém por perto, dá para deixar o `python main.py vigiar` aberto, ou agendar o `python main.py` no Agendador de Tarefas do Windows (ou no `cron`, no Linux). Como o robô é idempotente, rodar várias vezes por dia não duplica nada.

Dica para apresentação: colocando `NAVEGADOR_VISIVEL=1` no `.env`, dá para ver o Chrome preenchendo o portal sozinho.

### Problemas comuns

| O que aconteceu | Por quê | O que fazer |
| :- | :- | :- |
| Rodei de novo e apareceu `0 registradas ... 31 ja processadas` | É a idempotência: o robô lembra o que já fez e não cadastra em dobro | `python main.py reset` e depois `python main.py` |
| `0 registradas` e muitas `pendentes`, com erro do Chrome no log | Chrome não instalado ou sem internet para baixar o driver na primeira vez | Instale o Chrome ou aponte um driver em `CHROMEDRIVER_PATH` no `.env`; na próxima execução as pendentes são registradas sozinhas |
| `Porta 8765 ja em uso` | Já existe um portal rodando (por exemplo, de outra execução) | Normal: o robô reaproveita esse portal |
| Linhas `ERROR` sobre quarentena, rejeição ou API | São os problemas colocados de propósito nos dados de exemplo | Nada; é o robô mostrando os caminhos seguros |
| Pasta dentro do OneDrive dá "Acesso negado" | O OneDrive trava arquivos enquanto sincroniza | Já tratado: o robô tenta salvar de novo sozinho |

## Como configurar as chaves

Nenhuma senha ou chave fica no código. Tudo vem do arquivo `.env`, que está no `.gitignore` e **nunca vai para o repositório**. O arquivo `.env.example` mostra o formato:

| Variável | Para que serve |
| :- | :- |
| `PORTAL_USUARIO` / `PORTAL_SENHA` | Login do robô no portal da prefeitura. O portal simulado aceita o que estiver aqui. |
| `PSEUDONIMO_SAL` | Texto secreto usado para gerar o pseudônimo do cidadão (sem ele não dá para "desfazer" o pseudônimo testando nomes). |
| `CLIMA_API_URL` | API pública Open-Meteo. É gratuita e **não precisa de chave**. |
| `LIMIAR_CONFIANCA` | Abaixo desse valor o robô manda para revisão humana (padrão 0,55; a escolha está explicada nas evidências). |
| `TIMEOUT_SEGUNDOS`, `MAX_TENTATIVAS`, `ESPERA_INICIAL` | Controle de timeout e retry. |
| `CHROMEDRIVER_PATH` | Opcional. Caminho de um chromedriver já instalado, para máquinas sem internet ou que bloqueiam download. |

Não usamos LLM, então não existe chave de API paga no projeto.

## O que o robô entrega

Cada execução gera em `saida/`:

- `relatorios/relatorio_<data>.xlsx`: planilha com as abas **Resumo** (indicadores e gráfico), **Registradas** (com protocolo, prioridade, justificativa e mensagem ao cidadão), **Revisão humana** (urgentes primeiro), **Rejeitadas**, **Pendentes**, **Pontos críticos** e **Arquivos lidos**;
- `relatorios/execucao_<data>.json`: relatório de execução completo (o que entrou, o que saiu, tempo, memória);
- `logs/zelabot_<data>.log`: log de cada passo;
- `quarentena/`: arquivos que não puderam ser lidos, com um `.motivo.txt` ao lado;
- `prints/`: telas capturadas pelo Selenium.

Um exemplo de cada um já está em [docs/evidencias/](docs/evidencias/), para quem quiser ver sem rodar.

## Evidências de validação

Resumo (detalhes, análise dos erros e limites em [docs/evidencias_validacao.md](docs/evidencias_validacao.md)):

- **Execução de ponta a ponta** com 5 arquivos e 31 registros: 23 registradas no portal com protocolo, 4 para revisão humana, 3 rejeitadas com motivo, 1 duplicata ignorada e 1 arquivo corrompido em quarentena.
- **Lote de entrada comparado com gabarito rotulado** ([dados/teste/gabarito_entrada.csv](dados/teste/gabarito_entrada.csv)): 3/3 rejeições corretas, 2/2 pedidos fora do escopo mandados para revisão, **23/23 automatizadas na categoria certa** (intervalo de 95%: 85,7% a 100%) e nenhum erro silencioso.
- **Conjunto de teste rotulado** (59 frases escritas à mão, separadas do treino): o modelo acertou **86,3%** das 51 frases do escopo (intervalo de 95%: 74,3% a 93,2%), contra **70,6%** de uma regra simples por palavra-chave. Com o limiar de confiança, o robô automatiza **71%** dos casos e acerta **92,9%** do que automatiza; 7 dos 8 pedidos fora do escopo foram para revisão humana.
- **Regra de urgência:** 13 de 14 casos de risco no teste (recall 0,93) e 8 de 10 no lote de entrada; os erros estão analisados nas evidências.
- **Falhas tratadas:** 9 de 9 cenários passaram ([docs/evidencias/demo_falhas.md](docs/evidencias/demo_falhas.md)): API fora do ar, portal fora do ar, portal instável com erro 503, senha errada, arquivo corrompido, arquivo ausente, dado inválido, execução repetida e reenvio corrigido de um pedido rejeitado.
- **20 testes automatizados** passando, também no GitHub Actions.

## Proteção de dados, ética e ODS

O protótipo usa apenas dados sintéticos, e mesmo assim foi construído como se os dados fossem reais: o nome do cidadão vira um pseudônimo, CPF, telefone e e-mail digitados no texto são mascarados antes de chegar ao modelo, ao portal ou ao relatório, e a única informação enviada para fora (API de clima) é o centro do bairro, nunca o endereço da pessoa. A IA não toma decisões escondidas: toda prioridade vem com uma justificativa em texto, o que tem baixa confiança vai para um humano e nenhum pedido é negado sem uma mensagem explicando o que faltou. Reconhecemos um risco importante: o robô só enxerga quem reclama, e bairros com menos acesso digital podem parecer "sem problemas" no mapa de pontos críticos. A solução se conecta ao **ODS 11** (cidades mais seguras, incluindo prevenção de alagamentos), ao **ODS 16** (instituições mais eficazes e transparentes) e ao **ODS 10** (redução de desigualdades, desde que esse viés seja acompanhado). Análise completa em [docs/dados_etica_ods.md](docs/dados_etica_ods.md).

## Limites e próximos passos

- A base de treino é sintética e pequena. O próximo passo seria treinar com reclamações reais anonimizadas (existem bases públicas de canais de atendimento).
- As amostras são pequenas (59 frases de teste e 30 registros de entrada), por isso mostramos intervalos de confiança: eles são largos, e isso é honesto.
- O limiar de 0,55 foi escolhido olhando o próprio conjunto de teste, então o número real em produção tende a ser um pouco pior. O certo seria separar um conjunto de validação.
- Os pontos críticos do KMeans não foram validados contra dados de vistoria; servem como apoio, não como verdade.
- O portal é simulado. Num sistema real, os seletores do Selenium precisariam ser ajustados, e o ideal seria usar uma API do sistema quando ela existir.
- Os logs que o robô gera já têm o formato de eventos (quem, o quê, quando), o que permitiria aplicar mineração de processos para achar gargalos no futuro.

## Estrutura do repositório

```
zelabot/
├── main.py                  ponto de entrada (todos os comandos)
├── src/
│   ├── pipeline.py          orquestra o processo T1 a T9
│   ├── leitura.py           tema Arquivos e I/O
│   ├── validacao.py         GIGO + LGPD
│   ├── modelo.py            classificador + KMeans
│   ├── prioridade.py        regras inteligentes + API de clima
│   ├── rpa_portal.py        robô Selenium
│   ├── relatorio.py         planilha (XlsxWriter) + JSON
│   ├── resiliencia.py       retry, idempotência, estado
│   ├── logs.py              configuração de logs
│   ├── avaliacao.py         métricas, gabarito e intervalos de confiança
│   ├── demo_falhas.py       demonstração automática das falhas
│   └── config.py            leitura do .env
├── portal/servidor.py       portal da prefeitura simulado
├── dados/
│   ├── gerar_dados.py       gera os dados sintéticos
│   ├── treino/              base de treino (sintética)
│   └── teste/               teste rotulado (escrito à mão) e gabarito do lote de entrada
├── entrada/                 arquivos de exemplo que o robô processa
├── tests/                   testes automatizados (pytest)
├── docs/                    quadro de temas, processo, evidências, ética
├── .github/workflows/       testes automáticos no GitHub Actions
├── .env.example             modelo de configuração (sem segredos)
└── requirements.txt
```
