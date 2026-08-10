# Mapa entre metodologia e scripts

| Etapa metodológica | Script | Entrada principal | Saída principal |
|---|---|---|---|
| Reprodutibilidade e ambiente | `00_prepare_workspace.py` | YAML de configuração | metadados da execução, versão de bibliotecas |
| Geração de dados_estruturados, vulnerabilidade_social, gravidade_latente_auditoria e marcadores_origem | `01_generate_profiles.py` | parâmetros estruturais | `profiles.csv` |
| Itens e totais psicométricos | `02_simulate_psychometrics.py` | perfis, parâmetros de escalas | `psychometrics.csv` |
| Plausibilidade e consistência | `03_quality_control_base.py` | perfis e escalas | checagens e sumário de qualidade |
| Narrativa SOAP sintética | `04_generate_narratives.py` | dados_estruturados, indicadores_psicometricos e marcadores_origem; nunca prioridade_referencia; provedor `template` ou `llm` | `narratives.jsonl` e manifest com metadados do provedor |
| Matriz de prioridade simulada | `05_assign_reference_priority.py` | dados_estruturados, indicadores_psicometricos, marcadores_origem e regras protocoladas | `prioridade_referencia.csv` |
| PLN independente | `06_extract_markers.py` | somente narrativas | `marcadores_extraidos.csv`, auditoria, comparador por regras e repetições de estabilidade |
| Anotação humana | `07_create_annotation_sample.py` | narrativas e estratos | formulário de dupla anotação |
| Validação da extração | `08_validate_extraction.py` | marcadores_origem qualificados, marcadores_extraidos e anotações opcionais | macro/micro, dimensões, omissão, alucinação, bootstrap, estabilidade e concordância |
| Conjuntos analíticos | `09_build_analytical_datasets.py` | dados_estruturados, indicadores_psicometricos, marcadores_origem, marcadores_extraidos e prioridade_referencia | três conjuntos comparáveis |
| Validação interna | `10_train_evaluate_models.py` | conjuntos analíticos | métricas, previsões, modelos e ICs |
| Interpretabilidade | `11_explain_models.py` | modelos e teste final | coeficientes/SHAP no conjunto-teste |
| Robustez | `12_run_sensitivity.py` | cenários do YAML | desempenho entre cenários |
| Relatório | `13_generate_report.py` | artefatos das etapas anteriores | `report.md` |
| Visualização simplificada | `14_export_priority_table.py` | previsões finais + dados_estruturados, indicadores_psicometricos e marcadores_extraidos | tabela CSV/HTML ordenada para inspeção de perfis sintéticos |

## Garantia contra vazamento de rótulo

A geração de narrativas é executada antes do script que cria `prioridade_referencia`. O contrato da classe `NarrativeRequest`, em `src/emulti_pipeline/narratives.py`, não possui campo de prioridade. Além disso, `04_generate_narratives.py` interrompe a execução se detectar colunas com nomes que sugiram rótulo de prioridade.

## Camada unificada para modelos de linguagem

`TemplateNarrativeGenerator` é o simulador local. `LLMNarrativeGenerator` é o adaptador externo selecionado por `narrative.provider: llm`. Ambos recebem `NarrativeRequest` e devolvem `NarrativeResponse`.

`StructuredLLMClient` lê backend, modelo, nome da variável de credencial e opções de chamada no YAML, solicita JSON estruturado, registra metadados sem credenciais e bloqueia recursivamente rótulos de prioridade antes da geração. A troca entre serviços compatíveis ocorre pela configuração, sem novas condições nos scripts ou nas fábricas.
