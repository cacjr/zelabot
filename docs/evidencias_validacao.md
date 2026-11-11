# Evidências de validação

Todos os resultados são reproduzíveis pelos comandos indicados. Arquivos de apoio em [evidencias/](evidencias/).

## 1. Execução de ponta a ponta

**Comando:** `python main.py reset` e `python main.py`

**Entrada:** 5 arquivos sintéticos ([dados/gerar_dados.py](../dados/gerar_dados.py)) com problemas inseridos de propósito.

| Arquivo | Formato | Registros | Problemas inseridos |
| :- | :- | :- | :- |
| `app156_2026-11-03.csv` | CSV, UTF-8, vírgula | 12 | linha duplicada; bairro e coordenada inválidos; telefone no texto |
| `totem_legado.csv` | CSV, CP1252, ponto e vírgula | 7 | data no futuro; descrição "oi" |
| `subprefeitura_lote.xlsx` | Excel | 7 | 2 pedidos fora do escopo |
| `formulario_site.json` | JSON | 5 | CPF no texto; caso urgente |
| `exportacao_interrompida.json` | JSON | ilegível | arquivo cortado no meio |

**Resultado** ([log](evidencias/log_execucao_limpa.txt), [relatório JSON](evidencias/execucao_exemplo.json), [planilha](evidencias/relatorio_exemplo.xlsx)):

| Indicador | Valor |
| :- | :- |
| Registros lidos | 31 |
| Registrados no portal | 23 |
| Revisão humana | 4 |
| Rejeitados | 3 (localização inválida, data no futuro, descrição curta) |
| Duplicata ignorada | 1 |
| Quarentena | 1 |
| Pendentes | 0 |
| Dados pessoais mascarados | 2 (telefone, CPF) |
| Tempo | 32,9 s |

**Comparação com gabarito.** Os 30 registros únicos foram rotulados em [gabarito_entrada.csv](../dados/teste/gabarito_entrada.csv) com a decisão esperada, a categoria e a urgência. O `python main.py avaliar` compara automaticamente ([detalhe por registro](evidencias/avaliacao_lote_entrada.csv)):

| Medida | Resultado |
| :- | :- |
| Automatizadas na categoria certa | **23/23** (IC 95%: 85,7% a 100%) |
| Rejeições corretas | 3/3 |
| Fora do escopo enviados à revisão | 2/2 |
| Erros silenciosos | 0 |
| Pedidos do escopo enviados à revisão | 2 (sugestão correta, confiança baixa) |
| Urgentes detectados | 8/10 |

O "fio soltando faísca" foi para revisão por confiança baixa (34%), mas marcado como **URGENTE** no topo da fila. Os intervalos usam o método de Wilson, adequado a amostras pequenas e taxas próximas de 100%.

| Formulário preenchido | Protocolo gerado | Registros no portal |
| :-: | :-: | :-: |
| ![formulário](evidencias/print_formulario_preenchido.png) | ![protocolo](evidencias/print_protocolo_gerado.png) | ![registros](evidencias/print_portal_registros.png) |

## 2. Modelo em conjunto de teste rotulado

**Comando:** `python main.py avaliar` · **Amostra:** [teste_rotulado.csv](../dados/teste/teste_rotulado.csv), 59 frases escritas à mão, com vocabulário diferente do treino (51 no escopo, 8 fora).

Rótulos revisados por Gustavo Duarte em 10/11/2026.

Na validação cruzada do treino o F1 é 1,00, sinal de que as frases sintéticas são parecidas demais entre si. Por isso o teste é separado e escrito de outra forma.

### 2.1 Classificador (51 frases do escopo)

| | Acurácia | F1 macro |
| :- | :-: | :-: |
| **TF-IDF + Regressão Logística** | **86,3%** (IC 95%: 74,3% a 93,2%) | **0,861** |
| Regra por palavra-chave | 70,6% | 0,795 |

A regra não respondeu 13 frases ("buracão", "luminárias", "colchão", "sarjeta", "tronco"); o modelo acertou 12 delas.

| Categoria | Precisão | Recall | F1 | n |
| :- | :-: | :-: | :-: | :-: |
| pavimentação | 0,92 | 1,00 | 0,96 | 11 |
| iluminação | 0,89 | 0,80 | 0,84 | 10 |
| limpeza | 0,70 | 0,70 | 0,70 | 10 |
| drenagem | 0,82 | 0,90 | 0,86 | 10 |
| árvores | 1,00 | 0,90 | 0,95 | 10 |

![Matriz de confusão](evidencias/matriz_confusao.png)

### 2.2 Robô com limiar de confiança (59 frases)

Erro silencioso é quando o robô decide sozinho e erra, o pior caso, porque ninguém revisa.

| Limiar | Automatiza | Acerto no automatizado | Erros silenciosos | Fora do escopo retidos |
| :-: | :-: | :-: | :-: | :-: |
| 0,30 | 96,6% | 77,2% | 13 | 2/8 |
| 0,40 | 89,8% | 81,1% | 10 | 4/8 |
| 0,50 | 79,7% | 85,1% | 7 | 5/8 |
| **0,55** | **71,2%** | **92,9%** | **3** | **7/8** |
| 0,65 | 64,4% | 100% | 0 | 8/8 |
| 0,70 | 55,9% | 100% | 0 | 8/8 |

**Regra de escolha:** o limiar com maior acerto no automatizado, mantendo pelo menos 65% de automação. Com todos os dados, a regra escolhe 0,55: os erros silenciosos caem de 7 para 3 e 7 de 8 pedidos fora do escopo são retidos. Subir para 0,65 zera os erros, mas derruba a automação para 64%.

**Estimativa sem viés de seleção.** Escolher o limiar e medir o resultado nos mesmos dados infla o número. Por isso o teste foi dividido em 5 partes: em cada rodada, a regra escolhe o limiar em 4 partes e o resultado é medido só na parte que ficou de fora.

| Validação cruzada aninhada | Resultado |
| :- | :- |
| Limiar escolhido em cada rodada | 0,55; 0,55; 0,65; 0,55; 0,65 |
| Automatizadas | 69,5% |
| Acerto no automatizado | **95,1%** (IC 95%: 83,9% a 98,7%) |
| Erros silenciosos | 2 |

A estimativa honesta fica no mesmo patamar da medição direta (92,9%), o que indica que o 0,55 não foi um ajuste de sorte.

### 2.3 Regra de urgência

Recall de 0,93 (13/14) e precisão de 0,81 (13/16). A prioridade é o recall: perder um caso de risco custa mais que um alarme a mais. O único urgente perdido foi um pedido fora do escopo, que foi para revisão de qualquer forma.

## 3. Falhas tratadas

**Comando:** `python main.py falhas` ([resultado](evidencias/demo_falhas.md))

| Cenário | Falha simulada | Resultado |
| :- | :- | :- |
| API de clima fora do ar | host inexistente | 11/11 casos seguem sem o critério de chuva, com justificativa; disjuntor abre após 2 falhas |
| Portal fora do ar | portal desligado | 23 solicitações na fila de pendentes |
| Portal instável | erro 503 a cada 4 cadastros | 23/23 registradas após 7 novas tentativas automáticas |
| Senha errada | `PORTAL_SENHA` inválida | 2 pendentes; registradas após corrigir a senha |
| Arquivo corrompido | JSON cortado | quarentena com motivo; demais arquivos lidos |
| Arquivo ausente | caminho inexistente | registrado no log; execução concluída |
| Dados inválidos | data futura, "oi", bairro inexistente, duplicata | 3 rejeições com motivo e mensagem; duplicata ignorada |
| Execução repetida | mesmos arquivos | nenhum cadastro em dobro |
| Reenvio corrigido | pedido rejeitado volta com descrição completa | reenvio processado e registrado |

Todos os 9 cenários passaram. Os 20 testes automatizados (`python -m pytest`) cobrem validação, mascaramento, leitura em CP1252, JSON corrompido, retry, chuva forte, API fora do ar, arquivo de estado bloqueado pelo sistema e reenvio corrigido. Eles também rodam no GitHub Actions a cada push.

## 4. Análise dos erros

Erros em [avaliacao_erros.csv](evidencias/avaliacao_erros.csv). As palavras de maior peso no modelo explicam a maioria:

| Frase | Esperado | Previsto | Causa |
| :- | :- | :- | :- |
| "Praça sem iluminação, virou ponto de assalto" | iluminação | limpeza | "virou ponto" pesa para limpeza ("virou ponto de lixo" no treino) |
| "Ponto de ônibus sem luz nenhuma" | iluminação | limpeza | mesma causa: "ponto" |
| "Terreno baldio cheio de lixo" | limpeza | drenagem | "cheio de lixo" aparece em "bueiro cheio de lixo" |
| "Papeleira transbordando" | limpeza | drenagem | "transbordando" só aparece com bueiro e córrego |
| "Árvore tampando a iluminação do poste" | árvores | iluminação | frase ambígua |
| "Gostaria de elogiar o atendimento" | fora do escopo | pavimentação (62%) | o modelo não tem a classe "nenhuma" |

Palavras vazias como "um" e "uma" também estão entre as de maior peso: os templates de treino repetem construções e o modelo aprende o vício, um caso de GIGO no próprio treino.

Na urgência, a regra perdeu "galhos encostando na fiação" (procura "fio solto", não "fiação") e deu alarme a mais em "poda em frente ao posto de saúde" e "raiz levantou a calçada". Regras por palavra-chave só detectam o que foi previsto.

## 5. Limites

1. **Amostras pequenas** (59 frases de teste, 30 registros de entrada): os intervalos de confiança são largos.
2. **Rotulagem pela mesma equipe:** teste e gabarito foram rotulados por quem construiu o modelo; um rotulador independente reduziria esse viés.
3. **Treino sintético:** F1 de 1,00 no treino contra 0,86 no teste.
4. **Sem classe "fora do escopo":** o modelo depende do limiar para não decidir.
5. **Regras de urgência por palavra-chave:** explicáveis, mas limitadas.
6. **Critério de chuva** não foi acionado na execução real (previsão de 0 a 0,2 mm); está coberto por teste automatizado com 25 mm.
7. **Portal simulado:** seletores e tempos mudariam num sistema real. A execução completa foi validada com Chrome e com Edge, e num clone limpo do repositório.
