# Como gerar narrativas com o provedor Gemini

O projeto contém um adaptador opcional, `GeminiNarrativeGenerator`, para gerar
narrativas SOAP e extrair marcadores **inteiramente sintéticos** pela Gemini API. A geração continua usando
o contrato `NarrativeRequest` → `NarrativeResponse`; por isso, as etapas de
modelagem e avaliação não dependem da API escolhida. A extração recebe apenas a narrativa e possui contrato próprio.

> **Limite obrigatório:** use somente os perfis sintéticos produzidos por este
> repositório. Não envie prontuários, nomes, dados de pacientes, registros de
> profissionais ou qualquer dado pessoal à API.

## O que foi implementado

- `src/emulti_pipeline/narrative_providers/gemini.py` — adaptador da Gemini API;
- `src/emulti_pipeline/extraction_providers/gemini.py` — extrator independente com JSON estruturado;
- `config/gemini.yaml` — cenário executável que herda `config/base.yaml` e troca
  os provedores de narrativa e extração;
- `config/gemini_smoke.yaml` — teste curto de 20 perfis, destinado às etapas 00 a 08;
- saída JSON estruturada com os campos `subjective` e `assessment`;
- retentativas exponenciais configuráveis;
- metadados de modelo, parâmetros, semente, hash do prompt e uso de tokens,
  quando disponíveis no SDK;
- bloqueio recursivo de campos de prioridade antes da montagem do prompt.

O adaptador usa o SDK oficial `google-genai` e a operação `generate_content`.
A documentação oficial informa que o SDK pode ler `GEMINI_API_KEY` diretamente
do ambiente e que a geração pode retornar saída estruturada em JSON.

## 1. Instalar dependências

Na raiz do repositório, instale ou atualize as dependências:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

O arquivo `requirements.txt` inclui `google-genai`. O modo `template` não faz
chamadas externas e permanece disponível quando não houver chave configurada.

## 2. Definir a chave sem colocá-la no código

Crie ou gerencie uma chave no Google AI Studio/Google Cloud e mantenha-a fora
do repositório. Use uma chave autorizada ou com as restrições adequadas ao seu
projeto Google Cloud.

No macOS ou Linux, defina a chave apenas para a sessão atual do terminal:

```bash
export GEMINI_API_KEY='cole-a-chave-apenas-no-seu-terminal'
```

No Windows PowerShell:

```powershell
$env:GEMINI_API_KEY = 'cole-a-chave-apenas-no-seu-terminal'
```

Não inclua a chave em `config/gemini.yaml`, `.env.example`, notebooks
compartilhados, logs, commits, issues ou artefatos. O projeto ignora `.env`, mas
não carrega esse arquivo automaticamente.

### Google Colab

Em um notebook pessoal, use entrada oculta e execute a célula antes do pipeline:

```python
import os
from getpass import getpass

os.environ["GEMINI_API_KEY"] = getpass("Cole sua chave Gemini: ")
```

Não deixe essa célula preenchida ao compartilhar o notebook.

## 3. Fazer um teste curto e controlado

O primeiro teste deve gerar apenas 20 narrativas. Ele consome chamadas da API,
mas não executa modelagem nem relatório:

```bash
python scripts/run_pipeline.py \
  --config config/gemini_smoke.yaml \
  --run-id gemini_smoke \
  --skip-explanations \
  --skip-report \
  --stop-after 08_validate_extraction.py
```

Inspecione os arquivos produzidos:

```text
artifacts/gemini_smoke/04_narratives/narratives.jsonl
artifacts/gemini_smoke/04_narratives/narratives_index.csv
artifacts/gemini_smoke/04_narratives/narrative_generation_manifest.json
artifacts/gemini_smoke/06_extraction/extraction_manifest.json
artifacts/gemini_smoke/08_extraction_validation/validation_summary.json
```

O manifest deve registrar `provider: gemini`, `api_called: true`, o
`model_id`, a versão lógica do prompt e os parâmetros de geração. Ele não deve
conter a chave de API.

## 4. Executar um cenário completo

Depois da inspeção manual das narrativas do teste curto, execute o cenário
configurado para Gemini:

```bash
python scripts/run_pipeline.py \
  --config config/gemini.yaml \
  --run-id gemini_baseline
```

`config/gemini.yaml` herda todos os parâmetros científicos de `base.yaml`. Para
alterar quantidade de perfis, modelo ou parâmetros de geração, crie um novo YAML
que use `extends`, em vez de alterar silenciosamente o cenário-base.

Exemplo:

```yaml
extends: "gemini.yaml"

simulation:
  n_records: 100

narrative:
  gemini:
    model_id: "gemini-3.5-flash"
    temperature: 1.0
```

## 5. Parâmetros do adaptador

| Chave | Papel |
|---|---|
| `narrative.provider` | deve ser `gemini` para ativar o adaptador |
| `narrative.prompt_version` | identificador lógico do prompt versionado |
| `narrative.max_retries` | tentativas adicionais após a primeira chamada |
| `narrative.gemini.generator_id` | identificador preservado nos artefatos |
| `narrative.gemini.model_id` | nome do modelo Gemini solicitado pelo SDK |
| `narrative.gemini.api_key_env` | nome da variável de ambiente que armazena a chave |
| `narrative.gemini.temperature` | parâmetro de geração registrado por narrativa |
| `narrative.gemini.max_output_tokens` | limite da resposta JSON curta |
| `narrative.gemini.retry_backoff_seconds` | espera inicial para retentativas exponenciais |
| `extraction.provider` | deve ser `gemini` no experimento principal |
| `extraction.prompt_version` | versão lógica do prompt de extração |
| `extraction.stability` | tamanho da amostra e número de repetições |
| `extraction.gemini.*` | modelo, chave, temperatura, tokens e retentativas do extrator |

O `seed` do perfil sintético é enviado como parâmetro de geração para melhorar a
repetibilidade. A API trata repetição com a mesma semente como melhor esforço;
portanto, o experimento deve registrar modelo, data, prompt, parâmetros e
respostas efetivamente obtidas.

## 6. Garantias contra vazamento de rótulo

Antes de chamar a API, o adaptador verifica, inclusive em estruturas aninhadas,
se o payload contém `prioridade_referencia`, `prioridade_prevista`, códigos de
prioridade, `Yref`, `Yhat`, `target` ou equivalentes. Em caso positivo, a etapa
falha antes de realizar qualquer chamada.

O prompt recebe exclusivamente:

- `dados_estruturados`;
- `indicadores_psicometricos`;
- `marcadores_origem`.

A prioridade de referência é criada apenas na etapa 05, depois da geração
textual. O adaptador não lê arquivos de prioridade e não recebe
`gravidade_latente_auditoria`.

## 7. Saída estruturada e falhas esperadas

A API é instruída a devolver um objeto JSON com `subjective` e `assessment`. O
adaptador valida esses dois campos e monta `narrativa_clinica` no formato SOAP.
Se houver resposta vazia, saída não JSON, bloqueio de segurança, problema de
cota ou erro de rede, ele realiza as retentativas configuradas e encerra com uma
mensagem que não expõe credenciais.

Uma falha em casos com marcadores críticos não deve ser contornada reduzindo
salvaguardas do provedor. Registre a taxa de falhas e avalie seu efeito como
parte das limitações do experimento.

## 8. Validação antes do experimento principal

1. Leia uma amostra estratificada de `narratives.jsonl`.
2. Compare as narrativas com `marcadores_origem` e os indicadores psicométricos.
3. Procure invenção de eventos, inconsistências e termos de priorização.
4. Execute as etapas 06–08, compare Gemini com a regra independente e verifique falhas, qualificadores e estabilidade.
5. Guarde o YAML, o hash do prompt, o modelo e os artefatos da execução.
6. Execute a etapa completa somente após documentar a inspeção piloto.

Consulte também [Contratos de dados](../reference/contratos-de-dados.md),
[Configuração YAML](../reference/configuracao.md) e
[ADR-006](../decisions/ADR-006-provedor-gemini.md).
