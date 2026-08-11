# Referência: camada LLM unificada

## Componentes

| Componente | Responsabilidade |
|---|---|
| `src/emulti_pipeline/llm.py` | normalizar chamadas e respostas estruturadas |
| `LLMNarrativeGenerator` | produzir os campos SOAP `subjective` e `assessment` |
| `LLMClinicalExtractor` | extrair a ontologia fechada usando somente a narrativa |
| `create_narrative_generator()` | selecionar `template` ou `llm` |
| `create_clinical_extractor()` | selecionar `rules` ou `llm` |

## Seleção de backend

`StructuredLLMClient` forma o identificador de chamada como
`<backend>/<model_id>`. Se `model_id` já contiver uma barra, ele é usado sem
alteração. Assim, a troca de fornecedor ocorre no YAML.

## Configuração

| Chave | Obrigatória | Descrição |
|---|---:|---|
| `backend` | sim | backend ou formato de API reconhecido pelo LiteLLM |
| `model_id` | sim | identificador solicitado ao fornecedor |
| `api_key_env` | sim em chamada real | variável de ambiente que contém o segredo |
| `api_base` | não | URL alternativa do endpoint |
| `response_format` | sim | `json_schema`, `json_object` ou `prompt_only` |
| `send_seed` | não | tenta enviar a semente ao backend |
| `request_options` | não | opções adicionais não sensíveis |

## Metadados

Os artefatos registram `backend`, `model_id`, modelo informado na resposta quando
disponível, motivo de término, temperatura, limite de saída, versão e hash do
prompt, número de retentativas, timestamp e uso. A chave da API não é registrada.

## Acompanhamento no console

Cada chamada real registra a etapa, a fase, o `patient_id` sintético, a posição da
operação, a tentativa atual e o modelo. O campo `planned_remaining` informa quantas
operações lógicas faltam se as próximas respostas forem concluídas na primeira
tentativa. `max_attempts_remaining` representa o limite superior de chamadas ainda
possíveis, considerando todas as retentativas configuradas. Falhas e retentativas
registram apenas o tipo do erro, sem expor a chave ou o conteúdo clínico.

O cliente também verifica o motivo de término antes de interpretar o JSON. Respostas
encerradas por limite de tokens são identificadas como truncadas e seguem a política
normal de retentativas.

## Limites

- O LiteLLM normaliza a interface, mas os recursos variam entre modelos.
- `drop_params` permite retirar parâmetros que o backend não aceita.
- Saída estruturada deve ser confirmada no modelo escolhido.
- A reprodutibilidade é de melhor esforço mesmo quando a semente é aceita.
- Respostas são validadas localmente antes de entrarem no pipeline.
- O gerador textual recebe manifestações qualitativas, não nomes, itens ou escores
  de instrumentos psicométricos. Uma referência explícita a instrumento ou
  pontuação na resposta provoca retentativa.
