# Referência: ontologia de marcadores clínicos

A ontologia operacional está implementada em `src/emulti_pipeline/extraction.py` como `MARKER_ONTOLOGY`. Ela permite que o extrator por regras identifique padrões positivos, negativos e atributos simples de contexto.

## Marcadores atuais

| Código | Significado no cenário | Saída extraída principal |
|---|---|---|
| `ideacao_suicida` | pensamentos de morte/ideação atual ou negada | `marcadores_extraidos_ideacao_suicida_*` |
| `planejamento_suicida` | planejamento de autoagressão | `marcadores_extraidos_planejamento_suicida_*` |
| `autoagressao_iminente` | risco iminente de autoagressão | `marcadores_extraidos_autoagressao_iminente_*` |
| `risco_violencia` | risco de comportamento agressivo/violência | `marcadores_extraidos_risco_violencia_*` |
| `sintomas_psicoticos` | percepção alterada, ideias de referência ou sintoma psicótico | `marcadores_extraidos_sintomas_psicoticos_*` |
| `uso_problematico_substancias` | uso de álcool ou substâncias com prejuízo | `marcadores_extraidos_uso_problematico_substancias_*` |
| `internacao_previa` | internação anterior relacionada a sofrimento psíquico | `marcadores_extraidos_internacao_previa_*` |
| `agravamento_recente` | piora recente de sintomas | `marcadores_extraidos_agravamento_recente_*` |
| `suporte_social_baixo` | rede de apoio limitada | `marcadores_extraidos_suporte_social_baixo_*` |
| `comprometimento_funcional` | dificuldade leve, moderada ou importante em atividades | `marcadores_extraidos_comprometimento_funcional_*` |

## Atributos por marcador

| Sufixo | Tipo | Valores esperados |
|---|---|---|
| `_present` | binário | 0 ou 1 |
| `_negated` | binário | 0 ou 1 |
| `_remote_present` | binário | 0 ou 1; antecedente remoto que pode coexistir com negação atual |
| `_temporality` | categórico | `atual`, `remoto`, `nao_especificado` |
| `_severity` | categórico | `ausente`, `leve`, `moderado`, `alto`, `importante`, `nao_especificado` |
| `_severity_code` | ordinal | 0 a 3 |
| `_certainty` | categórico | `afirmado`, `incerto` |
| `_experiencer` | categórico | `paciente`, `terceiro` |
| `_evidence` | texto | sentença usada como evidência |

## Regras de interpretação

- Presença atual, negação atual e antecedente remoto são representados separadamente.
- Negação explícita atual tem prioridade sobre correspondência positiva genérica atual encontrada na mesma narrativa.
- Temporalidade remota não deve ser interpretada como marcador atual sem regra adicional.
- O extrator atual é uma linha de base simples; os valores de severidade e certeza não devem ser tratados como validação clínica.
- O texto de evidência não deve ser incluído em modelos, porque representa linguagem livre e pode introduzir atalho não controlado.

## Como adicionar um marcador

1. Defina código, semântica, exemplos positivos e negativos.
2. Acrescente padrões em `MARKER_ONTOLOGY`.
3. Gere o marcador verdadeiro correspondente `marcadores_origem_<codigo>` no simulador, quando aplicável.
4. Atualize o gerador de narrativa para expressar o marcador de forma coerente.
5. Atualize a referência de extração, os conjuntos analíticos e os formulários de anotação.
6. Atualize a matriz de prioridade se o marcador influenciar `prioridade_referencia`.
7. Atualize contratos, dicionário, ontologia e ADR se a mudança for estrutural.

## Limite de cobertura

A ontologia atual não é terminologia clínica completa. Ela foi desenhada para um cenário sintético controlado e deve ser expandida e validada antes de qualquer tentativa de uso com narrativas reais.
