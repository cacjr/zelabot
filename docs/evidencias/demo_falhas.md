# Demonstração de falhas tratadas

Gerado automaticamente por `python main.py falhas` em 04/11/2026 21:34.

| Cenário | Falha simulada | Esperado | Obtido | Passou? |
| :- | :- | :- | :- | :-: |
| API de clima fora do ar | URL da API apontando para um host inexistente | robô segue sem o critério de chuva e explica isso na justificativa | 11 de 11 casos de bueiro/arvore com 'previsão indisponível'; disjuntor aberto após 2 falhas | sim |
| Portal da prefeitura fora do ar | portal desligado | nada se perde: tudo vai para a fila de pendentes | 0 registradas, 23 na fila de pendentes | sim |
| Arquivo corrompido | JSON cortado no meio (exportacao_interrompida.json) | arquivo vai para quarentena com o motivo e os outros 4 são lidos | 1 em quarentena (JSONDecodeError), 31 registros dos outros arquivos lidos | sim |
| Dados inválidos | data no futuro, texto 'oi', bairro inexistente e linha duplicada | rejeita com motivo e mensagem ao cidadão; duplicata ignorada | 3 rejeitadas, cada uma com motivo (APP-0099, TOT-0002, TOT-0007), 1 duplicata ignorada | sim |
| Portal instável (erro 503) | portal responde 503 a cada 4 cadastros | retry com espera recupera e a fila de pendentes zera | 23/23 registradas, 7 novas tentativas automáticas, fila de pendentes = 0 | sim |
| Execução repetida | rodar o robô de novo com os mesmos arquivos | nada é cadastrado em dobro no portal | 31 já processadas ignoradas; portal continuou com 23 registros | sim |
| Senha do portal errada | PORTAL_SENHA inválida no .env | não insiste no login, guarda na fila e registra quando a senha é corrigida | 1ª execução: 2 pendentes (CredenciaisInvalidas); após corrigir: 2 registradas | sim |
| Arquivo ausente | caminho de arquivo que não existe | registra no log e termina a execução normalmente | status do arquivo: ausente; relatório gerado normalmente | sim |
