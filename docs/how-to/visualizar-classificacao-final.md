# Como visualizar a classificação final em uma tabela ordenada

## Finalidade

A etapa `14_export_priority_table.py` reúne as previsões do teste final, os dados estruturados, os escores psicométricos e os marcadores extraídos em uma tabela de inspeção rápida. Ela é útil para revisar se o modelo classificou os **perfis sintéticos** de maneira coerente com as informações que recebeu.

> **Limite de uso:** a tabela não é uma fila clínica, não representa pacientes reais e não fornece recomendação assistencial. A prioridade exibida é a previsão de um modelo treinado em uma prova de conceito inteiramente sintética.

## Pré-requisito

Execute as etapas 00 a 10. O orquestrador completo já executa a etapa 14 automaticamente após a modelagem:

```bash
python scripts/run_pipeline.py --config config/base.yaml --run-id baseline
```

Para gerar ou atualizar somente a tabela:

```bash
python scripts/14_export_priority_table.py \
  --config config/base.yaml \
  --run-id baseline
```

Por padrão, o script usa o conjunto `03_operacional_marcadores_extraidos`, que corresponde ao cenário operacional: atributos estruturados, escores e marcadores extraídos das narrativas.

## Seleção do modelo

A opção padrão é `--model best`. Nesse caso, o script escolhe o modelo com maior `development_f1_macro` no conjunto de desenvolvimento, calculado pela validação cruzada aninhada. A seleção não usa o desempenho do teste final, evitando escolher o modelo retrospectivamente pelo mesmo conjunto que será visualizado.

Para selecionar um modelo de forma explícita:

```bash
python scripts/14_export_priority_table.py \
  --config config/base.yaml \
  --run-id baseline \
  --dataset 03_operacional_marcadores_extraidos \
  --model xgboost
```

Modelos aceitos dependem do resultado da etapa 10 e normalmente incluem `rule_baseline`, `ordinal_logit`, `random_forest` e `xgboost`.

## Arquivos gerados

Os arquivos ficam em:

```text
artifacts/<run_id>/14_priority_view/
```

| Arquivo | Conteúdo |
|---|---|
| `classification_queue.csv` | tabela ordenada, pronta para abrir no Colab, Excel ou LibreOffice Calc |
| `classification_queue.html` | a mesma tabela em página HTML autocontida para abrir no navegador |
| `priority_view_manifest.json` | modelo selecionado, critério de seleção, origem das previsões e aviso de escopo |

A ordenação é: **urgente → alta → moderada → baixa**. Dentro de cada categoria, os registros são ordenados pela probabilidade estimada de `alta/urgente`, seguida da probabilidade de `urgente`.

## Colunas da tabela

| Coluna | Significado |
|---|---|
| `Posição` | posição de inspeção após a ordenação; não é fila clínica |
| `ID do perfil sintético` | identificador do caso sintético |
| `Prioridade prevista` | classe prevista pelo modelo selecionado |
| `Probabilidade alta/urgente` | soma das probabilidades previstas para as classes alta e urgente |
| `Probabilidade urgente` | probabilidade prevista especificamente para a classe urgente |
| `Idade`, `Categoria de gênero`, `Vulnerabilidade social` | atributos estruturados usados para contextualizar o perfil sintético |
| `PHQ-9`, `GAD-7`, `IDATE-Estado` | escores simulados derivados dos itens psicométricos |
| `Comprometimento funcional extraído` | severidade recuperada da narrativa pelo extrator de marcadores |
| `Sinais de atenção extraídos` | resumo dos marcadores encontrados na narrativa; não substitui leitura da narrativa ou auditoria de erros do extrator |

## Exibir no Google Colab

Depois de executar o pipeline, carregue o CSV:

```python
import pandas as pd
from pathlib import Path

run_id = "baseline_colab"
path = Path(f"artifacts/{run_id}/14_priority_view/classification_queue.csv")

fila = pd.read_csv(path)
display(fila.head(30))
```

Para recriar a tabela diretamente em uma célula do notebook, sem executar o script 14, use a função do pacote:

```python
import sys
from pathlib import Path
import pandas as pd

# Execute na raiz do projeto.
sys.path.insert(0, str(Path.cwd() / "src"))

from emulti_pipeline.visualization import (
    build_simplified_classification_table,
    display_simplified_classification_table,
)

run_id = "baseline_colab"
root = Path("artifacts") / run_id

profiles = pd.read_csv(root / "01_profiles" / "profiles.csv")
psychometrics = pd.read_csv(root / "02_psychometrics" / "psychometrics.csv")
extracted = pd.read_csv(root / "06_extraction" / "marcadores_extraidos.csv")
predictions = pd.read_csv(
    root / "10_modeling" / "03_operacional_marcadores_extraidos" / "xgboost" / "final_test_predictions.csv"
)

tabela = build_simplified_classification_table(
    profiles,
    psychometrics,
    extracted,
    predictions,
)

display(display_simplified_classification_table(tabela, n_rows=30))
```

## Exibir a referência simulada para auditoria

Por padrão, a tabela não mostra `prioridade_referencia`, pois esse rótulo existe apenas para avaliação experimental e não estaria disponível em um cenário operacional hipotético. Para auditoria da classificação, use:

```bash
python scripts/14_export_priority_table.py \
  --config config/base.yaml \
  --run-id baseline \
  --include-reference
```

A tabela incluirá a coluna `Prioridade de referência simulada` e uma coluna de concordância. Não use essa opção para representar uma tela operacional, pois ela expõe o rótulo construído pelo próprio gerador.
