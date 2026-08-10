# Tutorial: executar no Google Colab

O Google Colab é útil para testes e demonstrações, mas seu ambiente é temporário. Guarde o arquivo ZIP do projeto e copie os resultados para o Google Drive ao término da execução.

## 1. Enviar o projeto ao Google Drive

Faça upload do arquivo `pipeline_priorizacao_emulti.zip` para uma pasta do Drive. Exemplo de caminho:

```text
MyDrive/Projetos/eMulti/pipeline_priorizacao_emulti.zip
```

## 2. Montar o Drive no notebook

```python
from google.colab import drive

drive.mount('/content/drive')
```

## 3. Descompactar em `/content`

A execução em `/content` costuma ser mais adequada que a execução direta no Drive.

```python
from pathlib import Path
import os
import shutil

zip_path = '/content/drive/MyDrive/Projetos/eMulti/pipeline_priorizacao_emulti.zip'
workdir = '/content'

if not Path(zip_path).exists():
    raise FileNotFoundError(f'Arquivo não encontrado: {zip_path}')

shutil.unpack_archive(zip_path, workdir)
project_dir = Path('/content/pipeline_priorizacao_emulti')
os.chdir(project_dir)
print(os.getcwd())
```

## 4. Instalar dependências

```python
!python -m pip install -q -r requirements.txt
```

## 5. Executar smoke test

```python
!python scripts/run_pipeline.py \
  --config config/base.yaml \
  --run-id colab_smoke \
  --skip-explanations \
  --skip-report \
  --stop-after 03_quality_control_base.py
```

## 6. Executar pipeline completo

```python
!python scripts/run_pipeline.py \
  --config config/base.yaml \
  --run-id colab_baseline
```

O cenário-base usa CPU. Não há necessidade de GPU, porque a geração de narrativa inicial é simulada por templates e os modelos são tabulares.

## 6A. Opcional: testar um provedor LLM

O cenário-base continua usando o simulador local. Para usar um serviço externo,
configure `backend`, `model_id` e `api_key_env` em uma cópia de
`config/llm_smoke.yaml`. Depois informe a chave por entrada oculta com exatamente
o nome declarado em `api_key_env`:

```python
import os
from getpass import getpass

os.environ["LLM_API_KEY"] = getpass("Cole sua chave do provedor: ")
```

```python
!python scripts/run_pipeline.py \
  --config config/llm_smoke.yaml \
  --run-id llm_smoke \
  --skip-explanations \
  --skip-report \
  --stop-after 08_validate_extraction.py
```

Não salve a chave no notebook e não compartilhe a célula preenchida. Depois de
inspecionar `artifacts/llm_smoke/`, a execução completa pode usar uma cópia de
`config/llm.yaml`. Consulte também [Como usar um provedor
LLM](../how-to/usar-provedor-llm.md).

## 7. Persistir resultados no Drive

```python
from pathlib import Path
import shutil

source = Path('/content/pipeline_priorizacao_emulti/artifacts/colab_baseline')
destination = Path('/content/drive/MyDrive/Projetos/eMulti/resultados_colab_baseline')

if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(source, destination)
print(destination)
```

## Cuidados

- Não faça upload de dados reais ao notebook.
- Não insira chaves de API em células que serão compartilhadas.
- Use `run_id` diferentes para cada cenário.
- Baixe ou copie os artefatos antes de encerrar a sessão.
