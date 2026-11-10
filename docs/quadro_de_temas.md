# Quadro de temas

Seis temas da disciplina, cada um com função real no fluxo. O critério de escolha foi: o tema resolve parte do problema ou só estaria ali para constar?

## Tema 1: Automação web com Selenium

| | |
| :- | :- |
| **Onde** | T6, [src/rpa_portal.py](../src/rpa_portal.py) |
| **O que resolve** | Substitui a digitação manual: login no portal, preenchimento do formulário, registro e leitura do protocolo. |
| **Por que** | Sistemas públicos antigos raramente têm API; automatizar pela interface é o caso clássico de RPA. |
| **Detalhes** | Esperas explícitas (`WebDriverWait`) em vez de `sleep`; retry em erro 503; print da tela em falhas; Edge como alternativa se o Chrome não abrir; navegador sempre fechado (context manager); senha errada não gera tentativas repetidas de login. |
| **Portal simulado** | Automatizar um sistema público real com dados sintéticos geraria protocolos falsos. O portal local reproduz login, formulário e protocolo, e pode simular instabilidade (erro 503). |

## Tema 2: Arquivos e I/O

| | |
| :- | :- |
| **Onde** | T1, [src/leitura.py](../src/leitura.py); modo `vigiar` em [main.py](../main.py); estado em [src/resiliencia.py](../src/resiliencia.py) |
| **O que resolve** | Lê CSV em CP1252 com `;` (totem), CSV em UTF-8 (app), Excel (subprefeitura) e JSON (site). |
| **Por que** | A entrada do cidadão chega como arquivo, cada canal num formato e encoding. |
| **Conceitos aplicados** | **Encoding:** detecção com `charset_normalizer` e fallback UTF-8 → CP1252. **Chunking:** CSV lido em blocos de 500 linhas, só com as colunas necessárias e como texto. **Buffering:** hash SHA-256 calculado em blocos de 64 KB. **Modos:** `x` para o motivo da quarentena (nunca sobrescreve); estado gravado em `.tmp` e trocado de forma atômica. **Context manager:** todo arquivo aberto com `with`. **Generators:** leitores com `yield`. **watchdog:** detecta arquivos novos e espera a cópia terminar. |

## Tema 3: Automação de Excel

| | |
| :- | :- |
| **Onde** | T1 (leitura) e T9 (relatório), [src/relatorio.py](../src/relatorio.py) |
| **O que resolve** | Entrega o relatório pronto: resumo com indicadores e gráfico, abas por situação, cores por prioridade, filtros e cabeçalho congelado. |
| **Por que** | A prefeitura trabalha com Excel. Calamine lê rápido (com fallback para openpyxl); XlsxWriter permite formatação condicional e gráficos. |
| **Resiliência** | Se a planilha estiver aberta no Excel, o relatório JSON é gerado mesmo assim. |

## Tema 4: Tratamento de erros e logs

| | |
| :- | :- |
| **Onde** | Todas as tarefas; [src/resiliencia.py](../src/resiliencia.py) e [src/logs.py](../src/logs.py) |
| **O que resolve** | Nenhuma falha previsível interrompe a execução inteira. |
| **Por que** | É o que diferencia um script de um robô. |

| Falha | Caminho seguro |
| :- | :- |
| API de clima fora do ar | Timeout e 3 tentativas com espera crescente (1 s, 2 s); depois, última previsão salva (até 12 h) ou segue sem o critério. Após 2 falhas seguidas, o disjuntor suspende a API na execução. |
| Portal fora do ar | Checagem de saúde antes de abrir o navegador; solicitações vão para pendentes e são reprocessadas na próxima execução. |
| Portal instável (503) | Retry com espera exponencial em cada cadastro. |
| Senha errada | Sem novas tentativas de login; solicitações vão para pendentes. |
| Arquivo corrompido | Quarentena com o motivo; os demais seguem. |
| Arquivo ausente | Registro no log; execução continua. |
| Arquivo de estado bloqueado (sincronização, antivírus) | Até 10 novas tentativas de gravação; em último caso, gravação direta. |
| Dado inválido | Aba "Rejeitadas" com motivo e mensagem ao cidadão. |
| Execução repetida | Idempotência: nada é cadastrado em dobro. |
| Reenvio corrigido de pedido rejeitado | Assinatura do conteúdo detecta a mudança e o pedido é processado. |
| Erro inesperado | `try/except` final no `main.py` grava o traceback no log. |

Logs no console e em `saida/logs/`, no formato `hora | nível | módulo | mensagem`, com a tarefa (T1 a T9) em cada linha.

## Tema 5: RPA + IA/ML (HyperAutomation)

| | |
| :- | :- |
| **Onde** | T4 (classificação) e T8 (pontos críticos), [src/modelo.py](../src/modelo.py) |
| **O que resolve** | Interpreta o texto livre ("a rua tá parecendo queijo suíço", "bueiero") e informa categoria e confiança. |
| **Como** | TF-IDF de palavras e de trechos de caracteres (tolera erros de digitação) com Regressão Logística. Base desbalanceada de propósito (160 exemplos de pavimentação, 60 de árvores), tratada com `class_weight="balanced"`. |
| **Limiar** | Abaixo de 55% de confiança, a decisão vai para revisão humana. O valor sai de uma regra fixa, validada com validação cruzada aninhada. |
| **Integração** | `MODELO_EXTERNO` no `.env` permite usar um modelo treinado em outra disciplina; se for inválido, o robô volta ao próprio. |
| **KMeans** | Agrupa solicitações por localização e indica pontos críticos com link para o mapa. |
| **Por que não XGBoost** | Base pequena e textual; a Regressão Logística treina em menos de 1 s e permite ver o peso de cada palavra. |
| **Por que não LLM** | Opcional no enunciado. O modelo próprio roda offline, sem custo, não envia texto do cidadão a terceiros e é reproduzível. |

## Tema 6: BPM + qualidade de dados (GIGO)

| | |
| :- | :- |
| **Onde** | [docs/processo_as_is_to_be.md](processo_as_is_to_be.md); tarefas T1 a T9 em [src/pipeline.py](../src/pipeline.py); T3 em [src/validacao.py](../src/validacao.py) |
| **O que resolve** | O mapeamento AS-IS/TO-BE separa o repetitivo (triagem e digitação, para o robô) do que exige julgamento (casos ambíguos, para pessoas). As relações entre tarefas definem o código: a prioridade (T5) depende da categoria (T4) e o registro (T6) só ocorre após a validação (T3). |
| **GIGO** | Descrição curta, data no futuro, localização impossível e duplicatas são barradas antes do modelo. Dados pessoais são mascarados nessa etapa. |
| **Monitorar** | Indicadores de cada execução no JSON e na aba Resumo. |

**Complemento:** psutil registra memória e CPU de cada execução.

## Temas não usados

| Tema | Motivo |
| :- | :- |
| UiPath, Automation Anywhere, Blue Prism | Python é gratuito, multiplataforma e versionável no Git. |
| PyAutoGUI | Depende de coordenadas e resolução de tela; o Selenium interage direto com os elementos da página. |
| Pywinauto | O sistema legado é web, não desktop. |
| mmap, Dask, Vaex | Volume pequeno; o chunking do pandas atende. |
| Mineração de processos | Os logs já têm formato de eventos; fica como próximo passo. |
| Aprendizado por reforço | Não há ambiente com recompensa clara. |
| Tooling + MCP | Sem uso de LLM. |
