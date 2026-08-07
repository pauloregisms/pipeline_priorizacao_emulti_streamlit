# ADR-003 — Representar a prioridade como referência simulada ordinal de quatro classes

- **Status:** Aceita
- **Data:** 2026-06-24
- **Decisores:** equipe do projeto

## Contexto

O projeto não possui decisões clínicas reais ou desfechos independentes de pacientes. É necessário um alvo explícito para avaliar a recuperação de regras no cenário de simulação.

## Decisão

`prioridade_referencia` terá quatro categorias ordenadas: baixa, moderada, alta e urgente. A classe urgente será tratada como categoria simulada de segurança e receberá precedência por regras explícitas. `prioridade_referencia` será criado por `dados_estruturados`, `indicadores_psicometricos`, `marcadores_origem` e matriz protocolada, após a geração de narrativa.

## Consequências

### Positivas

- torna o alvo e sua origem transparentes;
- permite métricas multiclasse, ordinais e análises operacionais;
- evita alegar que se trata de necessidade clínica real.

### Negativas ou custos

- desempenho mede reprodução de uma regra simulada;
- limiares e precedências exigem documentação e validação de conteúdo;
- não há descoberta de relações clínicas novas.

## Critérios de reavaliação

Revisar apenas se um projeto futuro usar decisões reais ou outro desfecho independente e autorizado.
