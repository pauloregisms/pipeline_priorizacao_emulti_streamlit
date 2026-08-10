# Como configurar outro provedor de LLM

Na maioria dos casos, um novo fornecedor não exige uma classe Python. A camada
`StructuredLLMClient` delega a comunicação ao LiteLLM e recebe toda a seleção pelo
YAML.

## Endpoint já reconhecido pelo LiteLLM

Crie um cenário que herde `llm.yaml` e altere:

```yaml
narrative:
  provider: "llm"
  llm:
    backend: "IDENTIFICADOR_DO_BACKEND"
    model_id: "IDENTIFICADOR_DO_MODELO"
    api_key_env: "NOME_DA_VARIAVEL_SECRETA"
    response_format: "json_schema"
    request_options: {}
```

Repita o bloco em `extraction.llm` quando o fornecedor também for usado para
extração. Não adicione uma condição na fábrica e não coloque o nome do serviço em
funções, classes ou modos de execução.

## Endpoint compatível com outra base de URL

Se o serviço aceitar um protocolo já suportado, configure `api_base` e, quando
necessário, opções não sensíveis em `request_options`. Credenciais, `model`,
`messages` e `response_format` são reservados e não podem aparecer em
`request_options`.

## Quando alterar código

Uma modificação em `StructuredLLMClient` só é justificável quando o endpoint não
pode ser expresso pelo LiteLLM nem pelos parâmetros YAML. Nesse caso:

- preserve `LLMNarrativeGenerator` e `LLMClinicalExtractor`;
- mantenha a seleção por `backend`, sem funções específicas do fornecedor;
- normalize a saída no contrato `StructuredLLMResponse`;
- não registre segredos nem payload clínico em metadados;
- acrescente testes sem rede com uma função de conclusão simulada;
- documente a decisão arquitetural.

O contrato metodológico não pode mudar. O gerador recebe somente os grupos
autorizados e o extrator recebe somente a narrativa sintética.
