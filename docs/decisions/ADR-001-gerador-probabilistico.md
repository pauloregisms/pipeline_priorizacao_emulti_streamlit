# ADR-001 — Usar gerador probabilístico estrutural como mecanismo principal

- **Status:** Aceita
- **Data:** 2026-06-24
- **Decisores:** equipe do projeto

## Contexto

O estudo atual não usa base tabular real autorizada. Modelos como CTGAN ou GAN dependem de dados-fonte para aprender distribuições e relações. O objetivo é testar um pipeline em cenário inteiramente sintético e rastreável.

## Decisão

O mecanismo principal será uma simulação probabilística estrutural parametrizada por YAML, com relações explícitas entre atributos, vulnerabilidade, gravidade latente, escalas, marcadores e prioridade de referência.

## Consequências

### Positivas

- parâmetros e relações ficam auditáveis;
- não requer dados reais;
- sementes e cenários são reproduzíveis;
- análise de sensibilidade pode variar hipóteses de modo controlado.

### Negativas ou custos

- fidelidade depende dos pressupostos do gerador;
- relações artificiais podem inflar métricas;
- não há validade externa ou garantia de representatividade de serviços reais.

## Critérios de reavaliação

A decisão poderá ser revista em pesquisa futura somente se existir base-fonte autorizada, governança e plano explícito de avaliação de fidelidade, utilidade e privacidade.
