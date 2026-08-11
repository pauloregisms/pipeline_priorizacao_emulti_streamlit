# ADR-007 — Adotar camada LLM unificada orientada por YAML

## Status

Aceita.

## Contexto

A primeira integração externa possuía classes, funções, modos e configurações
associados diretamente a um fornecedor. Esse desenho exigia alterações no código
para comparar modelos de Google AI, OpenAI, Anthropic ou outro serviço.

## Decisão

Adotar `StructuredLLMClient` como interface única para respostas JSON estruturadas,
com transporte normalizado pelo LiteLLM. As fábricas reconhecem apenas os tipos
metodológicos `template` ou `llm` para narrativas e `rules` ou `llm` para extração.

Backend, modelo, variável de credencial, URL alternativa, formato de resposta,
semente e opções adicionais pertencem ao YAML. Modos curtos recebem os nomes
genéricos `smoke` e `llm_smoke`. O executor recebe explicitamente o caminho do
arquivo YAML em `execute_selected_mode`.

## Consequências

- trocar fornecedor ou modelo não exige alterar código;
- geração e extração podem usar backends diferentes;
- credenciais permanecem fora do YAML e dos artefatos;
- os testes simulam a função de conclusão e não realizam chamadas de rede;
- diferenças de recursos entre modelos continuam exigindo ajuste de
  `response_format` e validação por teste curto;
- o LiteLLM passa a ser dependência opcional da execução com API.

## Restrições preservadas

O gerador não recebe prioridade de referência nem pistas equivalentes. Também não
recebe nomes de instrumentos, números de itens, respostas ordinais, faixas ou
escores psicométricos. Esses dados são traduzidos localmente em
`manifestacoes_psicologicas` qualitativas. O extrator mantém o identificador
sintético apenas para associação local e envia ao modelo somente a narrativa.
Todos os dados permanecem inteiramente sintéticos e sem uso assistencial.
