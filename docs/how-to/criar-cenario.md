# Como criar um novo cenário de simulação

Crie um novo cenário quando quiser comparar uma hipótese explícita: outra semente, maior taxa de ausência, maior ruído de extração, nova prevalência ou pesos alternativos de vulnerabilidade.

## 1. Não edite o cenário-base sem necessidade

Mantenha `config/base.yaml` como referência do cenário-base. Crie um novo arquivo, por exemplo:

```text
config/cenario_ausencia_10pct.yaml
```

Comece copiando o base:

```bash
cp config/base.yaml config/cenario_ausencia_10pct.yaml
```

## 2. Altere somente hipóteses explícitas

Exemplo:

```yaml
project:
  run_description: "Cenário de robustez com 10% de ausência em dados observáveis"

simulation:
  missingness_rate: 0.10
  extraction_flip_rate: 0.00
  replicate_index: 1
```

Evite mudanças múltiplas sem justificativa, pois elas tornam o efeito de cada hipótese difícil de interpretar.

## 3. Documente a mudança

Registre no arquivo YAML:

- a hipótese testada;
- a fonte ou justificativa;
- quais parâmetros mudaram;
- o efeito esperado.

Atualize também [Configuração YAML](../reference/configuracao.md) se houver nova chave e `CHANGELOG.md` se a mudança alterar o comportamento disponível para usuários.

## 4. Execute com `run_id` próprio

```bash
python scripts/run_pipeline.py \
  --config config/cenario_ausencia_10pct.yaml \
  --run-id ausencia_10pct \
  --skip-explanations
```

## 5. Compare artefatos

Compare pelo menos:

- `03_quality_control/quality_summary.json`;
- `08_extraction_validation/validation_summary.json`;
- `10_modeling/modeling_summary.csv`;
- distribuições de `prioridade_referencia` e dos escores.

## 6. Cenários em lote

Para executar cenários declarados em `sensitivity.scenarios`, use:

```bash
python scripts/12_run_sensitivity.py --config config/base.yaml --run-id sensibilidade
```

O script cria YAMLs temporários e subexecuções com `run_id` derivados. Consulte [Análise de sensibilidade](analise-sensibilidade.md).

## Checklist

- [ ] O cenário continua inteiramente sintético.
- [ ] Sementes e mudanças estão registradas.
- [ ] Nenhum parâmetro crítico foi alterado sem fonte ou justificativa.
- [ ] O resultado não será interpretado como desempenho clínico.
