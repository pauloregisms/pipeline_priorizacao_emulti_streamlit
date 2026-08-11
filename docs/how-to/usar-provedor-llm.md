# Como usar um provedor LLM

O pipeline possui uma única camada para serviços de modelos de linguagem. O código
não seleciona diretamente Google AI, OpenAI ou Anthropic. Essa escolha ocorre nos
blocos `narrative.llm` e `extraction.llm` do YAML.

## 1. Escolher backend, modelo e variável de credencial

Copie `config/llm_smoke.yaml` para um novo cenário ou edite uma cópia. Os valores
`CONFIGURE_BACKEND` e `CONFIGURE_MODEL_ID` são marcadores intencionais e precisam
ser substituídos antes da chamada. Para usar o mesmo serviço nas duas etapas:

```yaml
extends: "llm_smoke.yaml"

narrative:
  provider: "llm"
  llm:
    backend: "openai"
    model_id: "IDENTIFICADOR_DO_MODELO"
    api_key_env: "OPENAI_API_KEY"

extraction:
  provider: "llm"
  llm:
    backend: "openai"
    model_id: "IDENTIFICADOR_DO_MODELO"
    api_key_env: "OPENAI_API_KEY"
```

Para Anthropic, troque apenas os três valores por `anthropic`, o identificador do
modelo e `ANTHROPIC_API_KEY`. Para Google AI, use `gemini`, o identificador do
modelo e `GEMINI_API_KEY`. Geração e extração também podem usar backends ou modelos
diferentes.

## 2. Definir o formato de resposta

Use o formato mais forte aceito pelo modelo escolhido:

| Valor | Quando usar |
|---|---|
| `json_schema` | o modelo aceita saída estruturada estrita por esquema |
| `json_object` | o modelo garante JSON, mas não aceita o esquema estrito |
| `prompt_only` | o endpoint não aceita parâmetro de formato; o esquema é incluído no prompt |

O pipeline sempre interpreta e valida o objeto retornado. Uma resposta inválida
aciona a política de retentativas registrada no YAML.

## 3. Definir o segredo fora do arquivo

No terminal:

```bash
export OPENAI_API_KEY='valor-nao-versionado'
```

No Google Colab, cadastre o mesmo nome no painel Secrets. O executor tenta carregar
essa variável e, se ela não existir, solicita o valor por entrada oculta. Nunca
grave a credencial no YAML, no notebook ou nos artefatos.

## 4. Executar o teste curto

```bash
python scripts/run_pipeline.py \
  --config config/llm_smoke.yaml \
  --run-id llm_smoke \
  --stop-after 08_validate_extraction.py \
  --skip-explanations \
  --skip-report
```

Examine:

- `04_narratives/narrative_generation_manifest.json`;
- `06_extraction/extraction_manifest.json`;
- `08_extraction_validation/validation_summary.json`;
- os registros de auditoria e as respostas inválidas, se houver.

## 5. Executar o experimento

Depois de validar a amostra, use uma cópia de `config/llm.yaml`, defina um novo
`run_id` e preserve o YAML resolvido. Registre o backend, o identificador exato do
modelo, a variável de credencial, a temperatura, o formato de resposta e a data.

Todos os dados devem permanecer sintéticos. O gerador não recebe a prioridade de
referência nem dados psicométricos brutos. A etapa 04 converte localmente as
respostas simuladas em manifestações psicológicas qualitativas, sem nomes de
instrumentos, itens, totais, faixas ou escores. O extrator mantém `patient_id`
apenas para associação local e envia ao modelo somente `narrativa_clinica`.
