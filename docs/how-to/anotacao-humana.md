# Como executar a anotação humana de narrativas

A anotação humana complementa a validação contra `marcadores_origem`. Ela não deve ser feita com acesso à prioridade de referência, para evitar viés de confirmação.

## 1. Criar amostra estratificada

Após gerar narrativas e prioridade:

```bash
python scripts/07_create_annotation_sample.py \
  --config config/base.yaml \
  --run-id baseline
```

A etapa produz:

```text
artifacts/baseline/07_annotation/annotation_template.csv
artifacts/baseline/07_annotation/annotation_sampling_audit.csv
artifacts/baseline/07_annotation/annotation_instructions.json
```

O arquivo `annotation_template.csv` contém `patient_id`, texto e colunas vazias de anotação. O arquivo de auditoria contém `prioridade_referencia` e deve permanecer separado dos anotadores.

## 2. Preparar dois arquivos independentes

Faça duas cópias do template, uma para cada anotador:

```text
annotation_annotator_a.csv
annotation_annotator_b.csv
```

Cada anotador preenche, para cada marcador:

- presença;
- negação;
- temporalidade;
- severidade;
- incerteza;
- experienciador;
- observações opcionais.

## 3. Regras de preenchimento

- Use `1` para presença e `0` para ausência quando a informação estiver clara.
- Não deduza informação não explicitada no texto.
- Diferencie manifestação atual de evento remoto.
- Diferencie relato do paciente de relato sobre familiar ou terceiro.
- Registre dúvida em `notes`, em vez de converter incerteza em afirmação.

A ontologia operacional está em [Ontologia de marcadores](../reference/ontologia-de-marcadores.md).

## 4. Avaliar concordância

```bash
python scripts/08_validate_extraction.py \
  --config config/base.yaml \
  --run-id baseline \
  --annotator-a caminho/annotation_annotator_a.csv \
  --annotator-b caminho/annotation_annotator_b.csv
```

O script produz concordância de Cohen para presença de cada marcador e também mantém métricas do extrator contra `marcadores_origem`.

## 5. Adjudicar divergências

Depois da avaliação independente:

1. identifique divergências;
2. faça discussão por um protocolo de adjudicação;
3. registre a decisão e o motivo;
4. gere uma versão de referência adjudicada, mantendo os arquivos originais imutáveis;
5. use a referência adjudicada para análise complementar, sem substituir silenciosamente os resultados dos anotadores independentes.

## Cuidados éticos

Mesmo com textos sintéticos, trate os arquivos como material de pesquisa. Não introduza exemplos reais, nomes ou descrições de casos assistenciais durante a anotação.
