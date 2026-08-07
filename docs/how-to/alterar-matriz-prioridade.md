# Como alterar a matriz de prioridade simulada

A matriz de prioridade define `prioridade_referencia`, o alvo de referência da simulação. Alterá-la muda a pergunta computacional do experimento e exige cautela metodológica.

## Antes de editar

1. Defina se a mudança afeta regra urgente, critérios de alta/moderada prioridade, limiares, pesos ou ruído não urgente.
2. Documente fonte, consenso de especialistas ou justificativa do cenário.
3. Avalie a necessidade de validação de conteúdo por especialistas.
4. Crie ou atualize um ADR caso a alteração mude a semântica do desfecho.

## Onde a matriz está implementada

- Parâmetros configuráveis: `config/base.yaml`, seção `priority_rules`.
- Regras e precedências: `src/emulti_pipeline/priority.py`, função `assign_reference_priority`.
- Regra-base operacional: `src/emulti_pipeline/priority.py`, função `rule_baseline_from_available_features`.
- Descrição de referência: [Matriz de prioridade](../reference/matriz-de-prioridade.md).

## Procedimento seguro

1. Crie um novo YAML de cenário.
2. Altere os valores configuráveis de `priority_rules`.
3. Se a regra depender de novo marcador, atualize simultaneamente:
   - gerador em `simulation.py`;
   - narrativa em `narratives.py`;
   - ontologia e extrator em `extraction.py`;
   - conjunto analítico em `features.py`;
   - documentação de ontologia, contratos e matriz.
4. Atualize a regra-base para manter o mesmo conjunto de critérios observáveis.
5. Execute cenário-base e sensibilidade.

## Dívida técnica atual

A regra de referência lê `priority_rules` do YAML, mas a regra-base operacional possui alguns limiares codificados diretamente. Antes de calibrar valores para uma análise definitiva, refatore `priority.py` para que ambas usem uma fonte comum de limiares e precedências.

Essa refatoração deve ser acompanhada por teste que confirme que mudanças no YAML afetam a regra-base quando aplicável.

## Não faça

- Não envie `prioridade_referencia`, nomes de prioridade ou códigos ao gerador textual.
- Não substitua `prioridade_referencia` por uma afirmação de necessidade clínica real.
- Não ajuste limiares após observar o desempenho de classificadores sem registrar a decisão como nova hipótese experimental.
