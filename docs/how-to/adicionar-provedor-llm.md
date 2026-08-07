# Como adicionar um provedor de LLM

A arquitetura já possui dois provedores:

- `template` — `TemplateNarrativeGenerator`, local e determinístico por semente;
- `gemini` — `GeminiNarrativeGenerator`, opcional e configurado por
  `config/gemini.yaml`.

Para usar o Gemini, consulte [Como gerar narrativas com o provedor
Gemini](usar-provedor-gemini.md). Este documento explica como adicionar outro
fornecedor sem alterar o restante do pipeline.

## Contrato obrigatório

O módulo `src/emulti_pipeline/narratives.py` define:

- `NarrativeRequest`: entrada permitida;
- `NarrativeResponse`: saída obrigatória;
- `BaseNarrativeGenerator`: interface a implementar;
- `create_narrative_generator`: fábrica selecionada pelo YAML.

`NarrativeRequest` contém apenas:

- `patient_id` sintético;
- `seed`;
- `dados_estruturados`;
- `indicadores_psicometricos`;
- `marcadores_origem`;
- `prompt_version`.

Ele **não** contém `prioridade_referencia`, `prioridade_prevista`, códigos de
prioridade, limiares, `Yref`, `Yhat` ou informação equivalente.

## 1. Criar adaptador

Crie, por exemplo, `src/emulti_pipeline/narrative_providers/meu_provedor.py`:

```python
from emulti_pipeline.narratives import (
    BaseNarrativeGenerator,
    NarrativeRequest,
    NarrativeResponse,
    narrative_input_payload,
    validate_narrative_request,
)
from emulti_pipeline.utils import json_hash


class MeuProvedorNarrativeGenerator(BaseNarrativeGenerator):
    def __init__(self, model_id: str, api_key: str) -> None:
        self.model_id = model_id
        self.api_key = api_key
        self.generator_id = f"meu-provedor-{model_id}"

    def generate(self, request: NarrativeRequest) -> NarrativeResponse:
        validate_narrative_request(request)
        payload = narrative_input_payload(request)
        input_hash = json_hash(payload)

        # 1. montar prompt somente com dados autorizados;
        # 2. chamar a API com tratamento de erros e retentativas;
        # 3. validar formato e coerência da resposta;
        # 4. retornar NarrativeResponse com metadados completos.
        raise NotImplementedError
```

Não use esse esqueleto como implementação final sem acrescentar validação de
formato, tratamento de falhas, retentativas, testes e documentação.

## 2. Construir prompt de forma auditável

O prompt deve:

- pedir formato SOAP limitado aos campos necessários;
- proibir nomes, endereços, documentos e dados identificáveis;
- proibir criação de sintomas, diagnósticos ou eventos não presentes na entrada;
- solicitar linguagem clínica objetiva e concisa;
- ser versionado e ter hash registrado;
- não conter `prioridade_referencia`, `prioridade_prevista` ou pistas do rótulo.

## 3. Armazenar segredo com segurança

Use variável de ambiente ou cofre de segredos:

```bash
export MEU_PROVEDOR_API_KEY='valor-local-nao-versionado'
```

Não versione a chave em YAML, código, notebook, log ou artefato. Veja
[SECURITY.md](../../SECURITY.md).

## 4. Registrar metadados mínimos

O campo `generation_metadata` deve registrar, no mínimo:

```json
{
  "mode": "api",
  "provider": "identificador_do_provedor",
  "model_id": "identificador_exato_do_modelo",
  "model_version": "quando_disponivel",
  "request_timestamp_utc": "...",
  "temperature": 0.0,
  "max_output_tokens": 0,
  "prompt_hash": "...",
  "retry_count": 0,
  "forbidden_label_check": "passed"
}
```

Evite registrar cabeçalhos, credenciais, prompt bruto ou payloads que não sejam
necessários à auditoria.

## 5. Registrar o provedor na fábrica

Adicione uma condição explícita em `create_narrative_generator()`:

```python
if provider == "meu_provedor":
    from .narrative_providers.meu_provedor import MeuProvedorNarrativeGenerator
    return MeuProvedorNarrativeGenerator(...)
```

Não espalhe condicionais de fornecedor pelos scripts. Preserve
`TemplateNarrativeGenerator` como modo local para testes reprodutíveis.

## 6. Validar antes do experimento

- Compare amostra de narrativas com os atributos de origem.
- Verifique ausência de vazamento de prioridade.
- Verifique se o extrator independente continua funcional.
- Registre modelo, parâmetros, versão do prompt e data.
- Execute uma réplica isolada antes de usar o adaptador em todos os cenários.

## Requisito de arquitetura

A implementação de um LLM não deve alterar a semântica de
`prioridade_referencia`, não deve acessar arquivos da etapa `05_priority` e não
deve usar `gravidade_latente_auditoria` como entrada textual.
