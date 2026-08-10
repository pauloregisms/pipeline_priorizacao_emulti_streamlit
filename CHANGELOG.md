# Changelog

## Não publicado

- Substituição dos adaptadores vinculados ao Gemini por `LLMNarrativeGenerator`, `LLMClinicalExtractor` e `StructuredLLMClient`.
- Seleção de Google AI, OpenAI, Anthropic ou outro backend compatível por `backend`, `model_id` e `api_key_env` no YAML.
- Novas configurações `config/llm.yaml` e `config/llm_smoke.yaml`; remoção dos modos e arquivos executáveis associados a um fornecedor.
- Executor do Colab com modos `smoke` e `llm_smoke`, função `require_llm_api_keys()` e caminho YAML explícito em `execute_selected_mode()`.

Este arquivo registra mudanças relevantes para quem executa, estende, revisa ou reproduz o pipeline.

O formato segue a convenção **Keep a Changelog** de forma simplificada. Versões futuras devem separar mudanças em `Adicionado`, `Alterado`, `Corrigido`, `Removido` e `Segurança` quando aplicável.

## [Não lançado]

### Alterado

- **Mudança incompatível de nomenclatura:** as colunas, contratos, conjuntos analíticos, previsões e documentação passaram a usar `marcadores_origem`, `marcadores_extraidos`, `prioridade_referencia` e `prioridade_prevista`. Execuções anteriores devem ser regeneradas; artefatos produzidos antes desta mudança não são compatíveis com os scripts atuais.
- O contrato de geração de narrativa passou a expor `dados_estruturados`, `indicadores_psicometricos`, `marcadores_origem` e `narrativa_clinica`.
- Origem e extração passaram a compartilhar um contrato qualificado com presença, negação, antecedente remoto, temporalidade, severidade, certeza e experienciador.
- A matriz de prioridade e a regra-base passaram a usar a mesma função e os mesmos parâmetros YAML.
- Os conjuntos de limite superior e operacional passaram a ter esquema canônico idêntico; a semente foi removida dos preditores.
- A regra-base deixou de receber probabilidades artificiais; calibração multiclasse e curvas são geradas somente para modelos probabilísticos.

### Adicionado

- Adaptador opcional `GeminiNarrativeGenerator`, baseado no SDK `google-genai`, para geração de narrativas SOAP sintéticas em JSON estruturado.
- Configurações herdáveis `config/gemini.yaml` e `config/gemini_smoke.yaml`, sem duplicação dos parâmetros científicos do cenário-base.
- Fábrica `create_narrative_generator()` para seleção explícita entre `template` e `gemini`.
- Validação recursiva de chaves proibidas na entrada de provedores de narrativa.
- Guia de uso local e no Google Colab para Gemini, referência técnica do provedor e ADR-006.
- Extrator Gemini independente, auditoria, comparador por regras, validação por dimensão, bootstrap e estabilidade.
- Configuração resolvida, hash da árvore de código, arquivo `uv.lock`, empacotamento, testes e integração contínua.
- Tabela de rastreabilidade por previsão ligando geração, extração, regra e modelo.

- Estrutura de documentação Docs-as-Code em `docs/`.
- Organização por Diátaxis: explicações, tutoriais, guias práticos e referências.
- Documentação de arquitetura arc42 e diagramas C4 em Mermaid.
- Registros de decisões arquiteturais (ADRs).
- Guia de contribuição, política de segurança e modelo de pull request.
- Configuração opcional de navegação para MkDocs.
- Etapa 14 para consolidar uma tabela ordenada de classificação final de perfis sintéticos em CSV e HTML.
- Funções reutilizáveis de visualização em `emulti_pipeline.visualization`.
- Guia de uso da tabela no terminal e no Google Colab.

## [0.1.0] — 2026-06-24

### Adicionado

- Pipeline inicial de simulação probabilística estrutural.
- Simulação de perfis sintéticos e escalas PHQ-9, GAD-7 e IDATE-Estado.
- Gerador de narrativas SOAP simuladas e desacopladas de APIs de LLM.
- Regra de prioridade de referência simulada em quatro categorias.
- Extrator de marcadores baseado em dicionário e regras de negação.
- Conjuntos analíticos `dados_estruturados + indicadores_psicometricos`, `dados_estruturados + indicadores_psicometricos + marcadores_origem` e `dados_estruturados + indicadores_psicometricos + marcadores_extraidos`.
- Modelagem com regra-base, regressão logística ordinal, Random Forest e XGBoost.
- Métricas de classificação, calibração, robustez e explicabilidade.
