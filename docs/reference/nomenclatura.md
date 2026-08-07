# Referência: nomenclatura do pipeline

Esta referência define os nomes padronizados das estruturas centrais. Os nomes usam `snake_case`, não usam caracteres especiais e descrevem o papel de cada informação no fluxo de dados.

## Estruturas principais

| Nome padronizado | Definição | Pode entrar no classificador? |
|---|---|---|
| `dados_estruturados` | atributos sociodemográficos, psicossociais, clínicos e de utilização de serviços disponíveis antes do encaminhamento conceitual | Sim |
| `vulnerabilidade_social` | índice sintético derivado de componentes dos dados estruturados | Sim |
| `gravidade_latente_auditoria` | construto interno do gerador, preservado somente para auditoria | Não |
| `indicadores_psicometricos` | respostas por item e totais simulados de PHQ-9, GAD-7 e IDATE-Estado | Sim; o cenário-base usa os totais |
| `marcadores_origem` | marcadores clínicos definidos pelo gerador para compor o cenário sintético | Somente no conjunto de limite superior |
| `narrativa_clinica` | texto SOAP sintético gerado a partir das informações permitidas | Não diretamente |
| `marcadores_extraidos` | marcadores recuperados de `narrativa_clinica` pelo processo de PLN | Sim, no conjunto operacional |
| `prioridade_referencia` | rótulo ordinal simulado produzido pela matriz de prioridade | Não; é o alvo de comparação |
| `prioridade_prevista` | classe estimada pela regra-base ou pelo classificador | É a saída da modelagem |

## Convenções de colunas

| Família | Convenção | Exemplo |
|---|---|---|
| Marcadores de origem | `marcadores_origem_<codigo>` | `marcadores_origem_ideacao_suicida` |
| Marcadores extraídos | `marcadores_extraidos_<codigo>_<atributo>` | `marcadores_extraidos_ideacao_suicida_present` |
| Referência simulada | `prioridade_referencia` e `prioridade_referencia_codigo` | `alta`, `2` |
| Resultado do modelo | `prioridade_prevista` e `prioridade_prevista_codigo` | `moderada`, `1` |

## Artefatos relacionados

- `01_profiles/profiles.csv` contém `dados_estruturados`, `vulnerabilidade_social`, `gravidade_latente_auditoria` e `marcadores_origem`.
- `02_psychometrics/psychometrics.csv` contém `indicadores_psicometricos`.
- `04_narratives/narratives.jsonl` contém `narrativa_clinica` e os metadados do gerador.
- `05_priority/prioridade_referencia.csv` contém `prioridade_referencia`.
- `06_extraction/marcadores_extraidos.csv` contém `marcadores_extraidos`.
- `10_modeling/*/final_test_predictions.csv` contém `prioridade_referencia`, `prioridade_prevista` e as probabilidades por classe.

## Regras de segurança metodológica

1. `prioridade_referencia` e `prioridade_referencia_codigo` não podem ser fornecidas ao gerador de narrativas nem ao extrator.
2. `gravidade_latente_auditoria` não pode entrar nos conjuntos analíticos nem no treinamento dos classificadores.
3. `marcadores_origem` e `marcadores_extraidos` não são intercambiáveis; a diferença entre eles mede a perda introduzida pela etapa textual.
4. `prioridade_prevista` deve ser interpretada apenas como saída experimental de uma prova de conceito com dados sintéticos.
