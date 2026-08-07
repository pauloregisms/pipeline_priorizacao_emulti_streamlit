# C4 — Diagrama de componentes

```mermaid
flowchart LR
    CFG["config.py\ncarrega YAML"]
    SIM["simulation.py\ndados_estruturados, vulnerabilidade_social, gravidade_latente_auditoria, marcadores_origem e indicadores_psicometricos"]
    QC["quality.py\nfaixas e consistência"]
    NAR["narratives.py\nNarrativeRequest e NarrativeResponse"]
    PRI["priority.py\nprioridade_referencia e regra-base"]
    EXT["extraction.py\nmarcadores_extraidos por ontologia"]
    FEAT["features.py\nconjuntos analíticos"]
    MOD["models.py\nmodelos e pré-processamento"]
    EVA["evaluation.py\nmétricas e bootstrap"]
    UTL["utils.py\nsementes, caminhos e hashes"]

    CFG --> SIM
    CFG --> QC
    CFG --> NAR
    CFG --> PRI
    CFG --> EXT
    CFG --> FEAT
    CFG --> MOD
    CFG --> EVA
    UTL --> SIM
    UTL --> NAR
    UTL --> PRI
    UTL --> EVA
    SIM --> QC
    SIM --> NAR
    SIM --> PRI
    NAR --> EXT
    PRI --> FEAT
    EXT --> FEAT
    FEAT --> MOD
    MOD --> EVA
```

## Interfaces críticas

### Geração narrativa

`narratives.py` recebe `NarrativeRequest` e produz `NarrativeResponse`. Nenhuma outra etapa deve depender de API ou fornecedor específico. O projeto inclui `TemplateNarrativeGenerator` e o adaptador opcional `GeminiNarrativeGenerator`.

### Prioridade

`priority.py` produz `prioridade_referencia` com base em `dados_estruturados`, `indicadores_psicometricos` e `marcadores_origem`. Ele não deve acessar `narrativa_clinica` ou `marcadores_extraidos` para construir a referência.

### Extração

`extraction.py` produz `marcadores_extraidos` apenas a partir de `narrativa_clinica`. A comparação com `marcadores_origem` ocorre na validação, não durante a extração.

### Modelagem

`features.py` remove `gravidade_latente_auditoria` e cria três conjuntos. `models.py` realiza pré-processamento dentro dos folds, e `evaluation.py` produz métricas a partir de previsões.

## Regra de dependência

Dependências devem fluir da configuração e dos módulos de geração para artefatos, e não no sentido contrário. Em particular:

```text
prioridade_referencia não entra no gerador de narrativa
gravidade_latente_auditoria não entra nos classificadores
marcadores_origem não substitui marcadores_extraidos no conjunto operacional
```
