# Tutorial: primeira execução local

Este tutorial conduz uma nova pessoa desenvolvedora desde a cópia do repositório até um smoke test controlado. Ele usa exclusivamente o simulador local de narrativas e não requer chave de API.

## 1. Preparar o ambiente

No diretório do projeto:

```bash
python -m venv .venv
source .venv/bin/activate            # Linux/macOS
# .venv\Scripts\Activate.ps1         # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verifique o interpretador:

```bash
python --version
```

Use Python 3.10 ou superior.

## 2. Verificar a estrutura

```bash
python -m compileall src scripts
```

O comando deve concluir sem erro. Ele não executa experimentos; apenas verifica se os módulos podem ser compilados.

## 3. Executar a etapa inicial do fluxo

Use um identificador exclusivo para não substituir artefatos existentes:

```bash
python scripts/run_pipeline.py \
  --config config/base.yaml \
  --run-id tutorial_smoke \
  --skip-explanations \
  --skip-report \
  --stop-after 03_quality_control_base.py
```

Essa execução cria:

- metadados do ambiente;
- perfis sintéticos;
- escalas psicométricas simuladas;
- checagens de qualidade.

## 4. Inspecionar as saídas

```bash
find artifacts/tutorial_smoke -maxdepth 2 -type f | sort
```

Arquivos importantes:

```text
artifacts/tutorial_smoke/01_profiles/profiles.csv
artifacts/tutorial_smoke/02_psychometrics/psychometrics.csv
artifacts/tutorial_smoke/03_quality_control/quality_summary.json
```

Abra `quality_summary.json` e confirme que a quantidade de falhas estruturais e psicométricas é zero no cenário-base.

## 5. Executar o fluxo completo

Depois do smoke test, execute:

```bash
python scripts/run_pipeline.py --config config/base.yaml --run-id tutorial_completo
```

A execução completa pode levar mais tempo por causa da validação aninhada, XGBoost e SHAP.

## 6. Ler o relatório automático

```bash
cat artifacts/tutorial_completo/13_report/report.md
```

O relatório resume qualidade, distribuição de `prioridade_referencia`, desempenho de extração e modelagem. Ele não substitui uma análise crítica dos arquivos detalhados.

## 7. Limpar artefatos locais, se necessário

```bash
rm -rf artifacts/tutorial_smoke artifacts/tutorial_completo
```

Não remova `artifacts/.gitkeep`, pois ele preserva o diretório no Git.

## Próximo passo

Para modificar suposições do cenário, siga [Como criar um cenário de simulação](../how-to/criar-cenario.md).
