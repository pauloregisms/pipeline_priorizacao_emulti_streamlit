# C4 — Diagrama de contêineres

Neste repositório, “contêiner” é usado no sentido de grandes unidades executáveis e de armazenamento. Não implica necessariamente uso de Docker.

```mermaid
flowchart TB
    YAML["Configuração YAML\nconfig/*.yaml"]
    SCRIPTS["Scripts executáveis\nscripts/00–13"]
    CORE["Biblioteca Python\nsrc/emulti_pipeline"]
    ART["Artefatos por execução\nartifacts/<run_id>/"]
    DOCS["Documentação\nREADME, docs, ADRs"]
    LLM["Adaptador de narrativa\nTemplate local / Gemini opcional / APIs futuras"]

    YAML --> SCRIPTS
    SCRIPTS --> CORE
    CORE --> LLM
    SCRIPTS --> ART
    DOCS -.descreve.-> YAML
    DOCS -.descreve.-> SCRIPTS
    DOCS -.descreve.-> CORE
    DOCS -.descreve.-> ART
```

## Responsabilidades

| Unidade | Responsabilidade |
|---|---|
| `config/` | declarar hipóteses e parâmetros |
| `scripts/` | executar etapas e preservar a ordem metodológica |
| `src/emulti_pipeline/` | manter lógica reutilizável e contratos |
| `artifacts/` | armazenar saídas intermediárias e finais |
| `docs/` | registrar uso, arquitetura, contratos e decisões |
| adaptador de narrativa | converter `NarrativeRequest` em `NarrativeResponse` sem acessar `prioridade_referencia`; `template` local ou `gemini` opcional |
