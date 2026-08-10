# Referência: configuração YAML

O arquivo `config/base.yaml` contém o cenário-base. Seus valores atuais são ilustrativos e devem ser substituídos por parâmetros justificáveis antes de uma análise definitiva.

## Estrutura geral

| Bloco | Finalidade |
|---|---|
| `project` | identificação e status do cenário |
| `paths` | local de artefatos |
| `simulation` | tamanho, sementes e perturbações controladas |
| `population` | distribuições de atributos sociodemográficos |
| `vulnerability` | pesos do índice de vulnerabilidade |
| `psychometrics` | parâmetros dos instrumentos por item |
| `priority_rules` | limiares da referência simulada |
| `narrative` | identificação e política do gerador textual |
| `extraction` | identificação do extrator e marcadores |
| `annotation` | tamanho da amostra de dupla anotação |
| `modeling` | divisão, validação e bootstrap |
| `sensitivity` | cenários de robustez |

## `project`

| Chave | Tipo | Uso |
|---|---|---|
| `name` | texto | nome lógico do projeto |
| `run_description` | texto | descrição do cenário, preservada em metadados |
| `parameter_status` | texto | aviso de maturidade dos parâmetros |

## `paths`

| Chave | Tipo | Uso |
|---|---|---|
| `artifacts_dir` | caminho relativo ou absoluto | raiz de saída das execuções |

## `simulation`

| Chave | Tipo | Uso |
|---|---|---|
| `n_records` | inteiro | número de indivíduos sintéticos na réplica |
| `base_seed` | inteiro | semente base reprodutível |
| `adult_age_min`, `adult_age_max` | inteiros | faixa de idade simulada |
| `replicate_index` | inteiro | deslocamento explícito da semente por réplica |
| `missingness_rate` | número entre 0 e 1 | ausência aplicada aos conjuntos observáveis em cenários de estresse |
| `narrative_omission_rate` | número entre 0 e 1 | remove menções controladamente antes da extração no cenário textual |
| `extraction_flip_rate` | número entre 0 e 1 | ruído controlado na extração baseada em regras |

## `population`

`gender_probabilities` e `education_probabilities` são mapas categoria → probabilidade. As probabilidades são normalizadas pelo gerador; mesmo assim, devem ser documentadas e preferencialmente somar 1.

| Chave | Uso |
|---|---|
| `gender_probabilities` | categorias de sexo/gênero representadas no cenário |
| `education_probabilities` | categorias de escolaridade |
| `income_lognormal_meanlog`, `income_lognormal_sigma` | parâmetros da renda log-normal simulada |

## `vulnerability`

A seção `weights` contém pesos não negativos que devem somar 1:

- `renda_baixa`;
- `escolaridade_baixa`;
- `inseguranca_alimentar`;
- `moradia_precaria`.

`source_note` deve registrar origem bibliográfica, justificativa ou referência a consenso de especialistas.

## `psychometrics`

Cada instrumento tem:

| Chave | Uso |
|---|---|
| `n_items` | quantidade de itens gerados |
| `n_categories` | número de categorias ordinais por item |
| `thresholds` | limiares do modelo graduado simplificado |
| `discrimination` | intensidade da relação com o sinal latente |

O bloco `state_anxiety` inclui `reverse_scored_items`, com índices 1-baseados dos itens pontuados de forma reversa antes da soma do IDATE-Estado.

## `priority_rules`

| Chave | Uso atual |
|---|---|
| `phq_moderate`, `phq_high` | limiares de PHQ-9 |
| `gad_moderate`, `gad_high` | limiares de GAD-7 |
| `stai_moderate`, `stai_high` | limiares de IDATE-Estado |
| `vulnerability_high` | limiar de alta vulnerabilidade |
| `high_evidence_weight`, `moderate_evidence_weight` | pesos do escore composto |
| `high_priority_cutoff`, `moderate_priority_cutoff` | cortes das classes não urgentes |
| `nonurgent_label_noise` | desvio do ruído aplicado apenas às classes não urgentes |
| `source_note` | justificativa da matriz |

Referência e regra-base chamam a mesma matriz; não existem limiares paralelos no código. Mudanças devem gerar uma nova versão em `priority_rules.version` e permanecer com status de validação explícito.

## `narrative`

| Chave | Uso |
|---|---|
| `provider` | seleciona `template` (local) ou `llm` (API opcional) |
| `generator_id` | identificador do simulador template |
| `prompt_version` | versão lógica do prompt ou contrato textual |
| `max_retries` | tentativas adicionais após a primeira chamada de API |
| `language` | idioma esperado |
| `forbidden_input_keys` | lista adicional de chaves que não podem entrar em geração textual |
| `llm` | bloco unificado com backend, modelo, credencial e opções de chamada |

### `narrative.llm`

| Chave | Uso |
|---|---|
| `generator_id` | identificador estável preservado nos metadados de execução |
| `backend` | prefixo do provedor reconhecido pelo LiteLLM, como `gemini`, `openai` ou `anthropic` |
| `model_id` | identificador do modelo no backend escolhido |
| `api_key_env` | nome da variável de ambiente que contém a credencial |
| `api_base` | endpoint alternativo opcional para serviço compatível |
| `response_format` | `json_schema`, `json_object` ou `prompt_only`, conforme suporte do modelo |
| `temperature` | parâmetro de geração registrado por narrativa |
| `max_output_tokens` | limite de saída JSON curta |
| `retry_backoff_seconds` | espera inicial antes de retentativas exponenciais |
| `send_seed` | envia a semente quando o backend aceitar esse parâmetro |
| `request_options` | parâmetros adicionais aceitos pelo LiteLLM; credenciais e mensagens são proibidas aqui |

O cenário `config/llm.yaml` usa `extends: "base.yaml"` e ativa a camada LLM tanto
na geração quanto na extração. O loader do projeto mescla dicionários de forma
recursiva, permitindo trocar backend e modelo sem duplicar parâmetros científicos.

> **Segurança:** nenhuma chave de API pode ser gravada no YAML. Use somente
> variável de ambiente ou cofre de segredos. O adaptador verifica chaves proibidas
> em toda a estrutura da requisição antes de montar o prompt.

> **Reprodutibilidade:** quando `send_seed` está ativo, a semente é enviada e pode
> ser descartada por backends que não a suportam. O resultado de LLM deve ser
> considerado reproduzível por melhor esforço. Preserve o YAML,
> `model_id`, `prompt_hash`, parâmetros e narrativas efetivamente obtidas.

## `extraction`

| Chave | Uso |
|---|---|
| `provider` | `rules` no teste local ou `llm` no experimento principal |
| `extractor_id` | identificador do extrator |
| `ontology_version` | versão da ontologia de marcadores |
| `prompt_version`, `max_retries` | versão e política de retentativas |
| `bootstrap_repetitions` | reamostragens da validação da extração |
| `stability` | número de casos e repetições da análise de estabilidade |
| `llm` | backend, modelo, chave por variável de ambiente, formato e parâmetros de saída |
| `markers` | lista de marcadores que o cenário pretende usar |

O extrator atual possui uma ontologia codificada no módulo `extraction.py`. Ao acrescentar marcador ao YAML, confirme também suporte no módulo, em contratos, em anotação e em documentação.

## `annotation`

| Chave | Uso |
|---|---|
| `n_per_priority` | quantidade máxima por estrato de `prioridade_referencia` |
| `include_critical_cases` | garante ao menos um caso crítico quando houver candidato disponível |

## `modeling`

| Chave | Uso |
|---|---|
| `final_test_size` | proporção do teste final isolado |
| `outer_splits`, `inner_splits` | folds da validação aninhada |
| `random_state` | semente de modelagem |
| `n_jobs` | paralelismo para modelos compatíveis |
| `bootstrap_repetitions` | número de reamostragens para intervalos percentis |
| `scoring` | métrica do ajuste interno de hiperparâmetros |
| `min_class_count_for_cv` | mínimo de observações por classe para CV |
| `required_models`, `strict_dependencies` | modelos obrigatórios e falha explícita por dependência ausente |
| `calibration_bins` | número de faixas das curvas de calibração |

## `sensitivity`

`scenarios` é uma lista de cenários. Cada item contém `name` e um mapa aninhado `overrides`, aplicado recursivamente à configuração resolvida. Isso permite variar semente, erro de extração, ausência, omissão narrativa e limiares da prioridade sem lógica paralela no script.

| Chave | Uso |
|---|---|
| `name` | nome sem espaço usado no `run_id` derivado |
| `overrides` | alterações YAML aninhadas exclusivas do cenário |

## Boas práticas

- Crie novo YAML para cada hipótese, em vez de alterar silenciosamente o cenário-base.
- Acrescente fonte ou justificativa para todo parâmetro que não seja puramente técnico.
- Preserve um hash ou cópia do YAML junto dos artefatos finais de cada experimento.
