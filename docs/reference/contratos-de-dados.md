# Referência: contratos de dados

Este documento define formatos e fronteiras de dados que novos componentes devem respeitar.

## Estruturas principais

| Nome padronizado | Papel |
|---|---|
| `dados_estruturados` | atributos estruturados observáveis antes do encaminhamento conceitual |
| `indicadores_psicometricos` | escalas psicométricas simuladas |
| `marcadores_origem` | marcadores de origem definidos pelo gerador |
| `narrativa_clinica` | narrativa SOAP sintética produzida pelo gerador |
| `marcadores_extraidos` | marcadores recuperados de `narrativa_clinica` |
| `prioridade_referencia` | prioridade de referência simulada |
| `prioridade_prevista` | previsão de regra ou classificador |

## `NarrativeRequest`

Definido em `src/emulti_pipeline/narratives.py`.

```python
@dataclass(frozen=True)
class NarrativeRequest:
    patient_id: str
    seed: int
    dados_estruturados: dict[str, Any]
    indicadores_psicometricos: dict[str, Any]
    marcadores_origem: dict[str, Any]
    prompt_version: str
```

### Invariantes

- `patient_id` deve ser sintético.
- `seed` deve permitir reprodução da geração textual simulada.
- `dados_estruturados`, `indicadores_psicometricos` e `marcadores_origem` podem conter apenas informação permitida no cenário.
- Não pode conter `prioridade_referencia`, `priority`, `prioridade`, `priority_code` ou equivalente.
- A implementação do gerador deve falhar explicitamente se detectar chave proibida.

## `NarrativeResponse`

```python
@dataclass(frozen=True)
class NarrativeResponse:
    patient_id: str
    narrative_id: str
    subjective: str
    assessment: str
    narrativa_clinica: str
    generator_id: str
    prompt_version: str
    input_hash: str
    generation_metadata: dict[str, Any]
```

### Requisitos

- `narrativa_clinica` deve ser resultado coerente com `subjective` e `assessment`.
- `input_hash` deve ser calculado a partir do payload permitido.
- `generation_metadata` deve permitir auditoria sem expor credenciais.
- Um provedor de API deve registrar modelo, versão quando disponível, parâmetros, timestamp, hash do prompt e política de retentativa.
- `generation_metadata` não pode conter chave de API, cabeçalhos HTTP, prompt bruto ou outros segredos.
- O adaptador Gemini solicita JSON estruturado com `subjective` e `assessment`, depois constrói `narrativa_clinica`.

## Perfil sintético (`profiles.csv`)

Campos centrais:

| Grupo | Campos principais |
|---|---|
| Identificação | `patient_id`, `seed` |
| Sociodemográficos | `age_years`, `gender_category`, `education`, `income_brl`, `income_normalized` |
| Psicossociais | `food_insecurity`, `poor_housing`, `social_vulnerability` |
| Clínicos/uso de serviço | `mental_health_history`, `chronic_condition`, `recent_service_contact` |
| Auditoria | `gravidade_latente_auditoria` — proibido nos classificadores |
| `marcadores_origem` | campos iniciados em `marcadores_origem_` |

## Escalas psicométricas (`psychometrics.csv`)

- `patient_id` é a chave de junção.
- Itens PHQ-9 e GAD-7 variam de 0 a 3.
- Itens pontuados de IDATE-Estado variam de 1 a 4.
- Totais esperados: `phq9_total` de 0 a 27; `gad7_total` de 0 a 21; `idate_estado_total` de 20 a 80.
- Os totais devem ser derivados dos itens, não gerados independentemente.

## Prioridade (`prioridade_referencia.csv`)

| Campo | Descrição |
|---|---|
| `patient_id` | chave de junção |
| `prioridade_referencia` | rótulo ordinal: baixa, moderada, alta, urgente |
| `prioridade_referencia_codigo` | codificação: 0, 1, 2, 3 |
| `urgent_rule_triggered` | indicador de regra determinística de segurança |
| `priority_high_evidence` | soma de evidências de alta prioridade |
| `priority_moderate_evidence` | soma de evidências de prioridade moderada |
| `priority_score` | escore composto não urgente antes da precedência de segurança |

## Marcadores extraídos (`marcadores_extraidos.csv`)

Para cada marcador da ontologia, o extrator produz:

```text
marcadores_extraidos_<marcador>_present
marcadores_extraidos_<marcador>_negated
marcadores_extraidos_<marcador>_remote_present
marcadores_extraidos_<marcador>_temporality
marcadores_extraidos_<marcador>_severity
marcadores_extraidos_<marcador>_severity_code
marcadores_extraidos_<marcador>_certainty
marcadores_extraidos_<marcador>_experiencer
marcadores_extraidos_<marcador>_evidence
```

O campo `_evidence` é textual e não entra nos conjuntos analíticos. Os demais campos podem entrar no conjunto operacional quando forem adequados ao cenário.

## Conjuntos analíticos

Todos possuem as colunas de identificação e alvo:

```text
patient_id, prioridade_referencia, prioridade_referencia_codigo, urgent_rule_triggered
```

A seguir, incluem:

- `01_estruturados_escores`: atributos estruturados e totais psicométricos;
- `02_limite_superior_marcadores_origem`: conjunto anterior + contrato canônico `marker_*` preenchido pela origem;
- `03_operacional_marcadores_extraidos`: conjunto estruturado + o mesmo contrato canônico `marker_*` preenchido pela extração.

Os dois conjuntos com marcadores têm nomes, tipos e dimensões idênticos; diferem apenas nos valores. Evidência textual, identificadores de extrator e semente de simulação não entram como preditores.

## Contrato de extensões

Ao adicionar um novo marcador, escala, variável ou modelo:

1. defina seu tipo, faixa, codificação e disponibilidade temporal;
2. atualize geração e validação;
3. atualize os contratos deste documento;
4. atualize a ontologia e os formulários de anotação, quando aplicável;
5. confirme que a informação não viola as fronteiras de `prioridade_referencia` ou de `gravidade_latente_auditoria`.
