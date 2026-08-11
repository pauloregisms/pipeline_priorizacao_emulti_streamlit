# Relatório automático do pipeline sintético e-Multi

**Execução:** `experimento_gemini31flash_lite`
**Status dos parâmetros:** ILUSTRATIVO - CALIBRAR ANTES DA ANÁLISE DEFINITIVA

## Delimitação
Este relatório descreve uma prova de conceito inteiramente sintética. As métricas representam recuperação de uma prioridade de referência simulada, não validade clínica ou desempenho em pacientes reais.

## Controle de qualidade
- Falhas estruturais: 0
- Falhas psicométricas: 0
- Alfa de Cronbach (inspeção sintética): {'phq9': 0.8481569218478208, 'gad7': 0.7245970155851862, 'idate_estado': 0.8498921386443928}

## Prioridade de referência simulada
- Distribuição: {'alta': 247, 'baixa': 64, 'moderada': 147, 'urgente': 42}

## Extração
- F1 macro de presença contra a referência do gerador: 0.9134763452595142
- F1 micro de presença: 0.9106796116504854
- Taxa de omissão: 0.062
- Taxa de alucinação: 0.0305
- A validação com anotadores humanos deve ser reportada separadamente quando os arquivos de dupla anotação estiverem disponíveis.

## Modelagem
| dataset                              | model         |   development_f1_macro |   final_test_f1_macro | final_best_params                                                                       |
|:-------------------------------------|:--------------|-----------------------:|----------------------:|:----------------------------------------------------------------------------------------|
| 01_estruturados_escores              | rule_baseline |               0.308223 |              0.322281 | nan                                                                                     |
| 01_estruturados_escores              | ordinal_logit |               0.476783 |              0.548137 | {'model__alpha': 1.0}                                                                   |
| 01_estruturados_escores              | random_forest |               0.52878  |              0.586283 | {'model__max_depth': None, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 5} |
| 01_estruturados_escores              | xgboost       |               0.51093  |              0.351528 | {'model__max_depth': 3, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |
| 02_limite_superior_marcadores_origem | rule_baseline |               1        |              1        | nan                                                                                     |
| 02_limite_superior_marcadores_origem | ordinal_logit |               0.818887 |              0.879753 | {'model__alpha': 0.5}                                                                   |
| 02_limite_superior_marcadores_origem | random_forest |               0.844202 |              0.867416 | {'model__max_depth': 12, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 1}   |
| 02_limite_superior_marcadores_origem | xgboost       |               0.803132 |              0.893533 | {'model__max_depth': 3, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |
| 03_operacional_marcadores_extraidos  | rule_baseline |               0.775524 |              0.826754 | nan                                                                                     |
| 03_operacional_marcadores_extraidos  | ordinal_logit |               0.798074 |              0.756797 | {'model__alpha': 0.5}                                                                   |
| 03_operacional_marcadores_extraidos  | random_forest |               0.754084 |              0.819054 | {'model__max_depth': None, 'model__max_features': 'sqrt', 'model__min_samples_leaf': 1} |
| 03_operacional_marcadores_extraidos  | xgboost       |               0.737492 |              0.860751 | {'model__max_depth': 3, 'model__min_child_weight': 1, 'model__subsample': 0.85}         |

## Tabela simplificada de classificação
- Modelo selecionado: ordinal_logit (maior F1 macro na validação cruzada aninhada (desenvolvimento)).
- Artefato: `14_priority_view/classification_queue.csv`.
- A tabela contém apenas perfis sintéticos e não deve ser interpretada como fila clínica.

## Interpretação e limites
Resultados elevados podem decorrer de relações estruturais programadas no próprio gerador. Antes de qualquer uso assistencial seriam necessários dados reais autorizados, validação externa, avaliação de equidade, governança e estudo de impacto.