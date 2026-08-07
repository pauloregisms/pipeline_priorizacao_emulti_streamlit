# ADR-005 — Preservar a distinção entre marcadores de origem e extraídos

- **Status:** Aceita
- **Data:** 2026-06-24
- **Decisores:** equipe do projeto

## Contexto

A simulação define marcadores de origem `marcadores_origem`, enquanto a narrativa é processada para recuperar marcadores `marcadores_extraidos`. Confundir ambos ocultaria a perda de informação introduzida pela etapa textual e inviabilizaria avaliação da extração.

## Decisão

Manter nomes, arquivos, contratos e conjuntos analíticos separados para `marcadores_origem` e `marcadores_extraidos`. O conjunto com `marcadores_origem` é tratado como limite superior de informação; o conjunto com `marcadores_extraidos` representa cenário operacional.

## Consequências

### Positivas

- permite medir erro de extração;
- evita vazamento de informação geradora para o modelo operacional;
- preserva rastreabilidade entre cenário, texto e extração.

### Negativas ou custos

- aumenta número de artefatos e documentação;
- exige cuidados ao selecionar colunas para modelagem.

## Critérios de reavaliação

A decisão só deve ser revista se a metodologia deixar de incluir narrativa e extração, hipótese que alteraria o escopo central do projeto.
