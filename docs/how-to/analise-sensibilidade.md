# Como executar análise de sensibilidade

A análise de sensibilidade testa a estabilidade do pipeline sob hipóteses pré-especificadas. Ela não deve ser usada como ajuste pós-hoc para obter métricas mais favoráveis.

## Cenários disponíveis

Em `config/base.yaml`, a seção `sensitivity.scenarios` contém cenários de exemplo:

- mudança de semente;
- erro de extração de 10%;
- ausência de 10% em dados observáveis.

Cada cenário cria uma nova configuração temporária e um novo `run_id` derivado.

## Executar todos os cenários

```bash
python scripts/12_run_sensitivity.py \
  --config config/base.yaml \
  --run-id sensibilidade
```

O resumo consolidado é gravado em:

```text
artifacts/sensibilidade/12_sensitivity/sensitivity_modeling_summary.csv
```

## Depuração sem modelagem

Para verificar geração e extração antes de executar modelos:

```bash
python scripts/12_run_sensitivity.py \
  --config config/base.yaml \
  --run-id sensibilidade_debug \
  --skip-modeling
```

## Criar novo cenário

Adicione uma entrada à lista `sensitivity.scenarios`:

```yaml
sensitivity:
  scenarios:
    - name: "ruido_extracao_20pct"
      seed_offset: 4
      extraction_flip_rate: 0.20
      missingness_rate: 0.00
```

Use nomes sem espaços e mantenha uma alteração principal por cenário, sempre que possível.

## Como interpretar

Compare distribuições de métricas entre cenários, não apenas o maior valor. Investigue variações em:

- F1 macro;
- recall de alta e urgente;
- AUPRC de alta e urgente;
- kappa ponderado e erro ordinal;
- Brier score e inclinação de calibração;
- desempenho do extrator;
- distribuição de `prioridade_referencia`.

A diferença entre cenários é uma propriedade do gerador e das hipóteses testadas. Ela não estima robustez clínica em população real.
