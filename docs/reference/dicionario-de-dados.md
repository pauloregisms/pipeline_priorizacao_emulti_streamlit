# Referência: dicionário de dados

Este dicionário descreve as variáveis implementadas no cenário-base. Valores e distribuições são ilustrativos até calibração formal.

## Atributos estruturados (`dados_estruturados`)

| Variável | Tipo | Faixa / categorias | Papel |
|---|---|---|---|
| `patient_id` | texto | `SYN-<seed>-<índice>` | chave sintética de junção |
| `seed` | inteiro | semente da réplica | rastreabilidade |
| `age_years` | inteiro | 18 a 80 | atributo sociodemográfico |
| `gender_category` | categórica | categorias do YAML | atributo sociodemográfico |
| `education` | categórica | `fundamental_ou_menos`, `medio`, `superior` | componente contextual |
| `income_brl` | numérica positiva | log-normal simulada | componente contextual |
| `income_normalized` | numérica | 0 a 1 | componente do índice de vulnerabilidade |
| `food_insecurity` | binária | 0/1 | componente do índice de vulnerabilidade |
| `poor_housing` | binária | 0/1 | componente do índice de vulnerabilidade |
| `social_vulnerability` | numérica | 0 a 1 | índice sintético observável |
| `mental_health_history` | binária | 0/1 | histórico clínico |
| `chronic_condition` | binária | 0/1 | comorbidade simulada |
| `recent_service_contact` | binária | 0/1 | uso recente de serviço |

## Variável de auditoria

| Variável | Tipo | Uso permitido |
|---|---|---|
| `gravidade_latente_auditoria` | numérica | apenas auditoria do gerador, nunca modelagem |

## Marcadores de origem (`marcadores_origem`)

| Variável | Tipo | Codificação |
|---|---|---|
| `marcadores_origem_ideacao_suicida` | binária | 0 ausente; 1 presente no cenário |
| `marcadores_origem_planejamento_suicida` | binária | 0/1; requer ideação no cenário-base |
| `marcadores_origem_autoagressao_iminente` | binária | 0/1; requer planejamento no cenário-base |
| `marcadores_origem_risco_violencia` | binária | 0/1 |
| `marcadores_origem_sintomas_psicoticos` | binária | 0/1 |
| `marcadores_origem_uso_problematico_substancias` | binária | 0/1 |
| `marcadores_origem_internacao_previa` | binária | 0/1 |
| `marcadores_origem_agravamento_recente` | binária | 0/1 |
| `marcadores_origem_suporte_social_baixo` | binária | 0/1 |
| `marcadores_origem_comprometimento_funcional` | ordinal | 0 ausente; 1 leve; 2 moderado; 3 importante |

## Instrumentos psicométricos (`indicadores_psicometricos`)

| Instrumento | Itens | Escala por item | Total |
|---|---:|---:|---:|
| PHQ-9 | 9 | 0 a 3 | 0 a 27 |
| GAD-7 | 7 | 0 a 3 | 0 a 21 |
| IDATE-Estado | 20 | 1 a 4 após reversão quando prevista | 20 a 80 |

Os itens são gerados primeiro. O total é sempre calculado pela soma posterior.

## Prioridade de referência (`prioridade_referencia`)

| Rótulo | Código | Papel |
|---|---:|---|
| `baixa` | 0 | prioridade de referência simulada |
| `moderada` | 1 | prioridade de referência simulada |
| `alta` | 2 | prioridade de referência simulada |
| `urgente` | 3 | categoria simulada de segurança |

`prioridade_referencia` não é diagnóstico, prognóstico ou decisão clínica observada.

## Marcadores extraídos (`marcadores_extraidos`)

Veja [Ontologia de marcadores](ontologia-de-marcadores.md) e [Contratos de dados](contratos-de-dados.md). `marcadores_extraidos` é derivado de texto e pode divergir de `marcadores_origem` por erro de extração ou cenário de ruído.
