# Quadro de temas

O enunciado pede pelo menos 3 temas da disciplina, cada um com função real no fluxo. Usamos 6. Antes de escolher, listamos tudo o que vimos ao longo do ano e nos perguntamos, para cada tema: **"isso resolve alguma parte do problema da zeladoria, ou só estaria aqui para constar?"**. O resultado está nas duas tabelas abaixo.

## 1. Temas usados

### Tema 1: Automação web com Selenium

| | |
| :- | :- |
| **O que é** | Biblioteca que controla o navegador como se fosse uma pessoa: abre páginas, preenche campos, clica e lê o resultado. |
| **Onde está no fluxo** | Tarefa T6, arquivo [src/rpa_portal.py](../src/rpa_portal.py). |
| **O que resolve** | É a parte mais "robô" do projeto. O servidor da prefeitura hoje abre um sistema web antigo, faz login e digita cada reclamação à mão. O ZelaBot faz exatamente isso: login, formulário, clique em registrar e leitura do número do protocolo. |
| **Por que escolhemos** | Sistemas públicos antigos quase nunca têm API. Automatizar pela interface é justamente o caso clássico de RPA. Usamos esperas explícitas (`WebDriverWait`) em vez de `sleep` fixo, que foi um dos cuidados vistos em aula. |
| **Detalhes que fizemos além do básico** | Retry quando o portal devolve erro 503; print da tela no primeiro registro e em toda falha; o navegador sempre fecha no final (context manager); se a senha estiver errada, o robô não fica insistindo no login. |

### Tema 2: Arquivos e I/O

| | |
| :- | :- |
| **O que é** | Leitura e escrita de arquivos em texto e binário, encodings, buffering, modos de abertura (`r`, `w`, `a`, `x`), context manager, chunking e monitoramento de pasta com watchdog. |
| **Onde está no fluxo** | Tarefa T1, arquivo [src/leitura.py](../src/leitura.py); modo `vigiar` no [main.py](../main.py); estado em [src/resiliencia.py](../src/resiliencia.py). |
| **O que resolve** | Cada canal manda os dados de um jeito. O totem antigo grava CSV em **CP1252** com `;`, o app manda CSV em **UTF-8** com `,`, a subprefeitura manda Excel e o site manda JSON. Sem tratar encoding, "Calçada" vira "CalÃ§ada" ou dá `UnicodeDecodeError`. |
| **Por que escolhemos** | Foi o tema que mais apareceu como problema real: a "entrada de dados do cidadão" que o enunciado cita chega como arquivo. |
| **Como cada conceito aparece** | **Encoding:** detecção automática com `charset_normalizer` e plano B que tenta UTF-8 e cai para CP1252 se der `UnicodeDecodeError`. **Chunking:** CSV lido em pedaços de 500 linhas (`chunksize`), só com as colunas necessárias (`usecols`) e tudo como texto (`dtype=str`), economizando RAM. **Buffering:** o hash SHA-256 do arquivo é calculado lendo blocos de 64 KB, sem carregar o arquivo inteiro. **Modos de abertura:** o `.motivo.txt` da quarentena é criado com modo `x` (nunca sobrescreve); o estado é salvo num `.tmp` e depois trocado, para não corromper se o robô cair no meio. **Context manager:** todo arquivo é aberto com `with`. **watchdog:** no modo `vigiar` o robô percebe sozinho quando um arquivo novo chega e espera ele terminar de ser copiado antes de ler. |

### Tema 3: Automação de Excel

| | |
| :- | :- |
| **O que é** | Ler e gerar planilhas por código. Na aula vimos que para volume grande vale ler com pandas + calamine e escrever com XlsxWriter. |
| **Onde está no fluxo** | T1 (leitura da planilha da subprefeitura) e T9 (relatório final), arquivo [src/relatorio.py](../src/relatorio.py). |
| **O que resolve** | A prefeitura trabalha com Excel. Em vez de alguém montar o relatório do dia na mão, o robô entrega uma planilha pronta: aba de resumo com indicadores e gráfico empilhado por categoria e prioridade, abas separadas por situação, cores por prioridade (vermelho, amarelo, verde), filtros e cabeçalho congelado. |
| **Por que escolhemos** | Seguimos a recomendação da aula: **calamine** para ler (motor em Rust, bem mais rápido; se não estiver instalado, o código cai para o openpyxl) e **XlsxWriter** para escrever (permite formatação condicional e gráficos nativos). |
| **Detalhe de resiliência** | Se a planilha anterior estiver aberta no Excel (o famoso `PermissionError`), o robô registra no log e gera o relatório em JSON mesmo assim. |

### Tema 4: Tratamento de erros e logs

| | |
| :- | :- |
| **O que é** | Garantir que o robô lide com falhas sem parar tudo, e registrar cada ação para monitorar e depurar depois. |
| **Onde está no fluxo** | Em todas as tarefas. Base em [src/resiliencia.py](../src/resiliencia.py) e [src/logs.py](../src/logs.py). |
| **O que resolve** | Robô que cai no primeiro erro não serve para nada. Cada falha previsível tem um caminho seguro definido (tabela abaixo). |
| **Por que escolhemos** | É requisito do enunciado, mas também é o que diferencia um script de um robô de verdade. |

| Falha | Caminho seguro |
| :- | :- |
| API de clima fora do ar | 3 tentativas, esperando 1 s e depois 2 s entre elas (a espera dobra a cada falha), cada uma com timeout; depois usa a última previsão salva (até 12h) ou segue sem esse critério. Após 2 falhas seguidas, um "disjuntor" para de chamar a API naquela execução. |
| Portal fora do ar | Checagem de saúde antes de abrir o navegador; se estiver fora, tudo vai para a fila de **pendentes**, que é reprocessada na próxima execução. |
| Portal instável (503) | Retry com espera exponencial em cada cadastro. |
| Senha errada | Não insiste; manda para pendentes e registra o erro. |
| Arquivo corrompido | Quarentena com o motivo; os outros arquivos seguem. |
| Arquivo ausente | Registra no log e continua. |
| Arquivo de estado travado (OneDrive, antivírus) | Tenta salvar de novo até 10 vezes, com espera crescente; se continuar travado, grava direto para não perder o dado. |
| Dado inválido | Aba "Rejeitadas" com o motivo e uma mensagem para o cidadão. |
| Rodar duas vezes | Idempotência: cada solicitação processada fica registrada e não é cadastrada de novo. |
| Pedido rejeitado reenviado corrigido | O robô guarda uma assinatura do conteúdo rejeitado; se o mesmo número volta com conteúdo diferente, processa de novo em vez de ignorar. |
| Erro inesperado | Último `try/except` no `main.py` grava o traceback completo no log. |

Os logs vão para o console e para `saida/logs/zelabot_<data>.log`, no formato `hora | nível | módulo | mensagem`, e cada linha diz em qual tarefa (T1 a T9) o robô estava.

### Tema 5: HyperAutomation (RPA + IA/ML)

| | |
| :- | :- |
| **O que é** | A evolução do RPA que só segue regras para um robô que também interpreta dados. Nas anotações: RPA executa regras, RPA + IA/ML interpreta e identifica padrões. |
| **Onde está no fluxo** | T4 (classificação) e T8 (pontos críticos), arquivo [src/modelo.py](../src/modelo.py). |
| **O que resolve** | O cidadão escreve do jeito dele ("a rua tá parecendo queijo suíço", "boca de lobo", "bueiero"). Uma regra fixa não dá conta disso. O classificador lê o texto livre e diz a categoria e o **quanto tem certeza**. |
| **Como foi feito** | TF-IDF de palavras (pega expressões como "boca de lobo") somado com TF-IDF de pedaços de letras (aguenta erro de digitação) e Regressão Logística. A base é **desbalanceada** de propósito (160 exemplos de buraco e só 60 de árvore, como na vida real), então usamos `class_weight="balanced"`. Também extraímos as palavras que mais pesam em cada categoria, para entender o modelo. |
| **Limiar de confiança** | Abaixo de 55% de confiança o robô não decide: manda para revisão humana. É isso que impede o robô de cadastrar "barulho do vizinho" como buraco. |
| **KMeans** | Agrupa as solicitações pela localização e mostra os pontos críticos (com link para o mapa), para a prefeitura planejar mutirões em vez de atender uma reclamação por vez. |
| **Por que não XGBoost** | Vimos XGBoost na ajuda com o modelo preditivo, mas aqui a base é pequena e de texto. Regressão Logística já teve bom resultado, treina em menos de 1 segundo e é mais fácil de explicar (dá para ver o peso de cada palavra). |
| **Por que não LLM** | O enunciado deixa opcional. Preferimos um modelo próprio porque roda sem internet, sem custo, sem mandar texto do cidadão para fora e com resultado reproduzível. |

### Tema 6: BPM (processo, tarefa e relação) + qualidade de dados (GIGO)

| | |
| :- | :- |
| **O que é** | Processo é o caminho completo, tarefa é cada passo, relação é como os passos se conectam. BPM é identificar, modelar, analisar, otimizar, automatizar e monitorar. GIGO: lixo entra, lixo sai. |
| **Onde está no fluxo** | Desenho em [docs/processo_as_is_to_be.md](processo_as_is_to_be.md); o [src/pipeline.py](../src/pipeline.py) implementa as tarefas T1 a T9 na ordem das relações; T3 em [src/validacao.py](../src/validacao.py). |
| **O que resolve** | Antes de programar, mapeamos como o processo funciona hoje (AS-IS) e como deveria funcionar (TO-BE). Foi esse mapa que mostrou que **a triagem e a digitação** eram as tarefas repetitivas e baseadas em regras (boas para RPA), enquanto **casos ambíguos** precisam continuar com pessoas. A relação entre tarefas também define o código: por exemplo, a prioridade (T5) depende da categoria (T4), e o registro (T6) só acontece se a validação (T3) passou. |
| **GIGO na prática** | A validação barra descrição curta demais ("oi"), data no futuro, localização impossível e linha duplicada **antes** de chegar ao modelo. Também é aqui que os dados pessoais são mascarados. |
| **Monitorar** | A etapa "monitorar" do BPM aparece no relatório de execução (JSON) e na aba Resumo, com indicadores de cada rodada. |

**Complemento: psutil.** Usamos para medir a memória e a CPU de cada execução, que vão para o relatório de execução. É pequeno, mas ajuda a saber se o robô aguentaria um volume maior.

## 2. Todos os temas vistos na disciplina (resumo) e o que fizemos com cada um

| Tema da disciplina | Resumo | Usamos? |
| :- | :- | :- |
| RPA e ferramentas de mercado (UiPath, Automation Anywhere, Blue Prism) | Automatizam tarefas repetitivas com desenvolvimento visual, muito usadas em empresas. | **Não.** Python é gratuito, roda em qualquer máquina e fica versionado no Git, o que facilita a reprodução pelo professor. |
| Python para automação | Alternativa gratuita e flexível para automações personalizadas. | **Sim**, é a base de todo o projeto. |
| PyAutoGUI | Automatiza mouse e teclado em qualquer aplicação, por coordenadas da tela. | **Não.** Depende da resolução e da posição das janelas, ficaria frágil. Como o sistema da prefeitura é web, o Selenium interage direto com os elementos da página. |
| Pywinauto | Automatiza aplicações Windows pelos componentes. | **Não.** Mesmo motivo: nosso sistema legado é web, não um programa desktop. |
| Selenium | Controla o navegador para automatizar sistemas web. | **Sim (Tema 1).** |
| Tratamento de erros | Faz o robô lidar com falhas inesperadas. | **Sim (Tema 4).** |
| Logs | Registram as ações para monitoramento e depuração. | **Sim (Tema 4).** |
| Processo, tarefa e relação | O caminho, os passos e como eles se conectam. | **Sim (Tema 6).** |
| BPM e AS-IS / TO-BE | Analisar, modelar, otimizar, automatizar e monitorar processos. "BPM otimiza o processo; RPA automatiza as tarefas." | **Sim (Tema 6).** |
| HyperAutomation | RPA + IA/ML + mineração de processos + integração + orquestração. | **Sim (Tema 5)**, na combinação RPA + ML + integração com API. Mineração de processos ficou como próximo passo (os logs já têm formato de eventos). |
| GIGO | Dados ruins geram resultados ruins, mesmo com sistema sofisticado. | **Sim (Tema 6).** Inclusive descobrimos GIGO no nosso próprio treino (ver evidências). |
| Texto x binário, encodings, buffering, file descriptor | Como os dados são representados, como caracteres viram bytes, como o I/O é otimizado e como o sistema identifica um arquivo aberto. | **Sim (Tema 2).** File descriptor fica implícito no uso de `with open(...)`. |
| `open()`, modos e context manager | `r` lê, `w` sobrescreve, `a` adiciona, `x` cria exclusivo; `with` fecha sozinho. | **Sim (Tema 2).** |
| Detecção automática de encoding, chunking, ler só as colunas necessárias, generators | Técnicas para arquivos grandes e com encoding desconhecido. | **Sim (Tema 2).** Os leitores são generators (`yield`). |
| mmap, Dask, Vaex | Para arquivos maiores que a memória. | **Não.** Nosso volume é pequeno; o chunking do pandas já resolve e demonstra a ideia. |
| watchdog | Monitoramento de pastas. | **Sim (Tema 2)**, no modo `vigiar`. |
| psutil | Monitora CPU, memória, disco e processos. | **Sim (complemento).** |
| Excel como automação; pandas + calamine para ler, XlsxWriter para escrever | Ferramentas certas para cada volume. | **Sim (Tema 3).** |
| Modelos preditivos (clusterização, KMeans, XGBoost, classificador, pesos, balanceamento) | Técnicas de ML vistas na ajuda com o modelo preditivo. | **Sim (Tema 5):** classificador, KMeans, pesos das palavras e balanceamento. XGBoost não (justificado acima). |
| Aprendizado por reforço | Sistemas que aprendem por tentativa e recompensa. | **Não.** Não temos um ambiente com recompensa clara; seria forçar o tema. |
| Tooling + MCP | Conectar modelos de IA a ferramentas e sistemas. | **Não.** Não usamos LLM. |
