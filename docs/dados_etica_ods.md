# Proteção de dados, ética e ODS

## Resumo

O ZelaBot usa apenas dados sintéticos e uma API pública sem chave, mas trata os dados como reais, seguindo os princípios de finalidade, necessidade e segurança da LGPD (Lei 13.709/2018): o nome vira pseudônimo, CPF, telefone e e-mail no texto são mascarados antes de chegar ao modelo, ao portal ou ao relatório, e só o centro do bairro sai da máquina, para a previsão do tempo. Toda prioridade tem justificativa, baixa confiança vai para uma pessoa e ninguém fica sem resposta. O principal risco é o viés de participação: o robô só vê quem reclama, e bairros com menos acesso digital podem parecer sem problemas. O protótipo contribui com os **ODS 11** (cidades seguras e resilientes), **16** (instituições eficazes e transparentes) e **10** (redução das desigualdades, se o viés for monitorado).

## 1. Proteção de dados

| Princípio | Implementação |
| :- | :- |
| **Dados sintéticos** | Nomes, CPFs, telefones e textos inventados ([dados/gerar_dados.py](../dados/gerar_dados.py)). |
| **Minimização** | O nome é convertido em pseudônimo (`cid_xxxxxxxxxx`, SHA-256 com segredo no `.env`) e não aparece em nenhuma saída. |
| **Texto livre** | CPF, telefone e e-mail viram `[CPF]`, `[TELEFONE]` e `[EMAIL]` antes de qualquer etapa ([src/validacao.py](../src/validacao.py)). |
| **Nada pessoal sai da máquina** | A API de clima recebe só o centro do bairro, arredondado. Sem LLM externo. |
| **Credenciais** | Senha do portal e segredo do pseudônimo no `.env`, fora do Git. |
| **Transparência** | O log registra que houve mascaramento, nunca o dado. |

Num sistema real ainda seria preciso definir a retenção dos relatórios, controlar o acesso a `saida/` e informar o cidadão sobre o uso dos dados.

## 2. Ética

- **Sem caixa-preta:** cada prioridade tem justificativa em texto, por exemplo *"categoria drenagem (peso 2); RISCO: pessoas vulneráveis por perto, risco de queda ou acidente, buraco sem proteção"*.
- **O robô sabe quando não sabe:** baixa confiança vai para revisão humana (7 de 8 pedidos fora do escopo retidos no teste). Casos de risco são marcados como URGENTE mesmo na revisão.
- **Ninguém é descartado:** pedido rejeitado recebe mensagem dizendo o que faltou.
- **O servidor é realocado, não substituído:** sai da digitação e fica com o que exige julgamento.

### Riscos

| Risco | Impacto | Mitigação |
| :- | :- | :- |
| **Viés de participação** | Bairros que reclamam menos parecem ter menos problemas; o KMeans pode reforçar a desigualdade. | Comparar pontos críticos com vistorias e população por bairro; manter canais presenciais. |
| **Jeito de escrever** | Gíria, erro de digitação e textos curtos reduzem a confiança do modelo. | TF-IDF por caracteres tolera erros; baixa confiança vai para revisão, e esse atraso deve ser monitorado. |
| **Regras de urgência ingênuas** | Citar "posto de saúde" já eleva a prioridade. | Preferência pela cautela (recall de 0,93); regras centralizadas e fáceis de revisar. |
| **Confiança excessiva** | Com o tempo, ninguém confere o robô. | Relatório por execução, log detalhado e fila de revisão separada. |
| **Treino artificial** | O modelo aprende vícios dos templates (GIGO). | Retreinar com textos reais anonimizados. |

## 3. ODS

| ODS | Meta | Contribuição |
| :- | :- | :- |
| **11. Cidades sustentáveis** | 11.5: reduzir impactos de desastres, incluindo os ligados à água | Bueiro entupido e árvore com risco sobem de prioridade quando há previsão de chuva forte. |
| **16. Instituições eficazes** | 16.6 e 16.7: instituições transparentes e decisões responsivas | Toda reclamação recebe protocolo, prazo e órgão responsável; cada decisão é justificada e registrada. |
| **10. Redução das desigualdades** | 10.2: inclusão de todos | Vários canais, incluindo o totem físico, e nenhum pedido descartado. Só contribui de fato se o viés de participação for acompanhado. |
