# Relatório automático do pipeline sintético e-Multi

**Execução:** `demonstracao_precarregada`
**Status dos parâmetros:** DEMONSTRAÇÃO — PARÂMETROS ILUSTRATIVOS, SEM VALIDADE CLÍNICA

## Delimitação
Este relatório descreve uma prova de conceito inteiramente sintética. As métricas representam recuperação de uma prioridade de referência simulada, não validade clínica ou desempenho em pacientes reais.

## Controle de qualidade
- Falhas estruturais: 0
- Falhas psicométricas: 0
- Alfa de Cronbach (inspeção sintética): {'phq9': 0.8411883819164261, 'gad7': 0.7165190989465214, 'idate_estado': 0.8414318034987662}

## Prioridade de referência simulada
- Distribuição: {'alta': 361, 'baixa': 147, 'moderada': 249, 'urgente': 43}

## Extração
- F1 macro de presença contra a referência do gerador: 1.0
- F1 micro de presença: 1.0
- Taxa de omissão: 0.0
- Taxa de alucinação: 0.0
- A validação com anotadores humanos deve ser reportada separadamente quando os arquivos de dupla anotação estiverem disponíveis.

## Modelagem
| dataset                              | model         |   development_f1_macro |   final_test_f1_macro | final_best_params                                                                       |
|:-------------------------------------|:--------------|-----------------------:|----------------------:|:----------------------------------------------------------------------------------------|
| 01_estruturados_escores              | rule_baseline |               0.3423   |              0.345466 | nan                                                                                     |
| 01_estruturados_escores              | ordinal_logit |               0.495053 |              0.473851 | {'model__alpha': 1.0}                                                                   |
| 01_estruturados_escores              | random_forest |               0.503652 |              0.569028 | {'model__max_depth': None, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 5} |
| 01_estruturados_escores              | xgboost       |               0.496342 |              0.518176 | {'model__max_depth': 5, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |
| 02_limite_superior_marcadores_origem | rule_baseline |               1        |              1        | nan                                                                                     |
| 02_limite_superior_marcadores_origem | ordinal_logit |               0.844199 |              0.854671 | {'model__alpha': 0.5}                                                                   |
| 02_limite_superior_marcadores_origem | random_forest |               0.878464 |              0.846114 | {'model__max_depth': None, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 1} |
| 02_limite_superior_marcadores_origem | xgboost       |               0.900106 |              0.857613 | {'model__max_depth': 5, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |
| 03_operacional_marcadores_extraidos  | rule_baseline |               0.851173 |              0.800532 | nan                                                                                     |
| 03_operacional_marcadores_extraidos  | ordinal_logit |               0.826964 |              0.845483 | {'model__alpha': 0.5}                                                                   |
| 03_operacional_marcadores_extraidos  | random_forest |               0.876156 |              0.83914  | {'model__max_depth': 12, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 1}   |
| 03_operacional_marcadores_extraidos  | xgboost       |               0.888806 |              0.854901 | {'model__max_depth': 5, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |

## Tabela simplificada de classificação
- Modelo selecionado: xgboost (maior F1 macro na validação cruzada aninhada (desenvolvimento)).
- Artefato: `14_priority_view/classification_queue.csv`.
- A tabela contém apenas perfis sintéticos e não deve ser interpretada como fila clínica.

## Interpretação e limites
Resultados elevados podem decorrer de relações estruturais programadas no próprio gerador. Antes de qualquer uso assistencial seriam necessários dados reais autorizados, validação externa, avaliação de equidade, governança e estudo de impacto.