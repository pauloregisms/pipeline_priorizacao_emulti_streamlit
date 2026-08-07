# ADR-004 — Usar validação cruzada aninhada e teste final isolado

- **Status:** Aceita
- **Data:** 2026-06-24
- **Decisores:** equipe do projeto

## Contexto

Ajustar hiperparâmetros e estimar desempenho no mesmo conjunto superestima resultados. O pipeline compara múltiplos modelos e estratégias de pré-processamento em dados simulados com classes ordinais.

## Decisão

Usar validação cruzada estratificada aninhada no conjunto de desenvolvimento e manter um conjunto final de teste isolado. Imputação, padronização e seleção de hiperparâmetros devem ocorrer apenas dentro dos folds de treinamento.

## Consequências

### Positivas

- reduz vazamento de informação entre treinamento e avaliação;
- separa escolha de modelo de estimativa final;
- preserva a prevalência original no teste.

### Negativas ou custos

- aumenta tempo de execução;
- exige número suficiente de registros em cada classe;
- ainda é validação interna em cenário sintético.

## Critérios de reavaliação

Revisar apenas se o protocolo de avaliação for substituído por esquema temporal, externo ou prospectivo em uma pesquisa distinta.
