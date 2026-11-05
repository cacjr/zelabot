# Proteção de dados, ética e ODS

## Parágrafo-resumo (o que o enunciado pede)

O ZelaBot usa apenas dados sintéticos e uma API pública que não pede chave, mas foi construído como se lidasse com dados reais de cidadãos, seguindo os princípios de finalidade, necessidade e segurança da LGPD (Lei 13.709/2018): o nome vira um pseudônimo, CPF, telefone e e-mail escritos no texto são mascarados antes de chegarem ao modelo, ao portal ou ao relatório, e a única coisa que sai do computador é o centro do bairro, enviado para a previsão do tempo. Do lado ético, a IA não decide no escuro: toda prioridade vem com justificativa em texto, o que tem baixa confiança vai para uma pessoa, e ninguém fica sem resposta, nem quem foi rejeitado. O principal risco que enxergamos é o viés de participação: o robô só vê quem reclama, então bairros com menos acesso digital podem parecer "sem problemas". O protótipo contribui com o **ODS 11** (cidades mais seguras e resilientes, com atenção a alagamentos e quedas de árvore), o **ODS 16** (instituições mais eficazes, que respondem e prestam contas) e pode apoiar o **ODS 10** (redução das desigualdades), desde que esse viés seja acompanhado.

## 1. Proteção de dados na prática

| Princípio | Como aparece no código |
| :- | :- |
| **Dados sintéticos** | Todos os nomes, CPFs, telefones e textos foram inventados ([dados/gerar_dados.py](../dados/gerar_dados.py)). O CPF usado é um número de teste conhecido. |
| **Necessidade (minimização)** | O nome do cidadão é lido mas **nunca sai do robô**: vira um pseudônimo (`cid_xxxxxxxxxx`) feito com hash SHA-256 e um "sal" secreto guardado no `.env`. O relatório não tem nome. |
| **Dados no texto livre** | O cidadão às vezes escreve "meu telefone é..." ou "meu CPF é...". Expressões regulares trocam isso por `[TELEFONE]`, `[CPF]` e `[EMAIL]` antes de qualquer outra etapa ([src/validacao.py](../src/validacao.py)). |
| **Nada pessoal sai do computador** | A API de clima recebe só a latitude e a longitude do **centro do bairro**, arredondadas, nunca a coordenada da casa. Não usamos LLM externo, então o texto do cidadão não é enviado a nenhum serviço de terceiros. |
| **Segurança das credenciais** | Usuário e senha do portal e o sal do pseudônimo ficam no `.env`, que está no `.gitignore`. O repositório só tem o `.env.example`, sem valores reais. |
| **Transparência** | O log registra que houve mascaramento ("dados pessoais mascarados: telefone"), sem registrar o dado em si. |

O que faltaria num sistema real: definir por quanto tempo os relatórios ficam guardados, controlar quem acessa a pasta `saida/` e informar o cidadão sobre o uso dos dados no momento da reclamação.

## 2. Ética: decisões automáticas que afetam pessoas

**O robô não pode ser uma caixa-preta.** Uma pessoa que esperou 15 dias para ter o lixo recolhido merece saber por que o pedido dela ficou com prioridade BAIXA. Por isso a prioridade é calculada com regras escritas, e cada pedido tem uma coluna "justificativa", por exemplo: *"categoria drenagem (peso 2); RISCO: pessoas vulneráveis por perto, risco de queda ou acidente, buraco sem proteção; chuva prevista baixa: 0.1 mm em 24h"* (bueiro sem tampa em que um idoso quase caiu).

**O robô sabe quando não sabe.** O limiar de confiança faz o robô passar a decisão para um humano quando não tem certeza. Na nossa medição isso segurou 7 de 8 pedidos que nem eram de zeladoria. Mesmo na revisão humana, se o texto fala de risco, o caso é marcado como URGENTE e vai para o topo.

**Ninguém é descartado.** Um pedido com dado faltando não some: o cidadão recebe uma mensagem dizendo o que faltou ("descrição muito curta... envie de novo com o que, onde e há quanto tempo").

**O servidor não é substituído, é realocado.** O robô tira a parte repetitiva (ler arquivo, digitar no sistema) e deixa a pessoa com o que precisa de julgamento.

### Riscos que identificamos (análise crítica)

| Risco | Por que importa | O que fizemos ou faríamos |
| :- | :- | :- |
| **Viés de participação** | O robô só conhece quem reclama. Bairros com menos internet, menos tempo livre ou menos confiança na prefeitura reclamam menos, e o mapa de pontos críticos (KMeans) pode reforçar a desigualdade, mandando mais equipe para onde já se reclama mais. | Deixamos isso explícito. Para usar de verdade, os pontos críticos deveriam ser comparados com dados de vistoria e com o número de habitantes por bairro, e os canais presenciais (totem) precisam continuar existindo. |
| **Jeito de escrever** | Quem escreve com gíria, erro de digitação ou de forma muito curta tende a ter menor confiança no modelo. | O TF-IDF por pedaços de letras ajuda com erro de digitação, e baixa confiança vai para um humano em vez de virar erro. Mas essas pessoas vão esperar um pouco mais pela revisão, o que precisa ser monitorado. |
| **Regras de urgência ingênuas** | "Posto de saúde" na frase já sobe a prioridade, mesmo quando não há risco. | Preferimos errar para o lado da cautela (recall de 0,93). As regras estão num único lugar e são fáceis de revisar com a equipe da prefeitura. |
| **Confiança excessiva no robô** | Com o tempo, as pessoas podem parar de conferir o que ele faz. | Relatório de cada execução, log detalhado e a aba de revisão separada mantêm um humano no circuito. |
| **Dado de treino artificial** | O modelo aprendeu vícios dos templates (GIGO). | Documentado nas evidências; o próximo passo é retreinar com textos reais anonimizados. |

## 3. Relação com os ODS

| ODS | Meta relacionada | Como o ZelaBot contribui |
| :- | :- | :- |
| **11. Cidades e comunidades sustentáveis** | 11.5 (reduzir mortes e prejuízos causados por desastres, incluindo os ligados à água) | Bueiro entupido e árvore com risco ganham prioridade maior quando há previsão de chuva forte, que é exatamente quando viram emergência. |
| **16. Paz, justiça e instituições eficazes** | 16.6 (instituições eficazes, responsáveis e transparentes) e 16.7 (tomada de decisão responsiva) | Toda reclamação recebe protocolo e resposta, com prazo e órgão responsável, e cada decisão do robô é justificada e registrada. |
| **10. Redução das desigualdades** | 10.2 (inclusão de todos) | Aceitar vários canais, inclusive o totem físico, e não descartar ninguém ajuda. Mas só contribui de verdade se o viés de participação for acompanhado, por isso listamos esse ponto como risco e não como conquista. |
