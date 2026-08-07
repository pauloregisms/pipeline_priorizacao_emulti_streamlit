# C4 — Diagrama de contexto

```mermaid
flowchart LR
    R["Pesquisador / responsável metodológico"]
    D["Desenvolvedor"]
    P["Pipeline sintético de priorização e-Multi"]
    C["YAML de cenários\nparâmetros, sementes, regras"]
    A["Artefatos experimentais\ntabelas, modelos, relatórios"]
    E["Especialistas\nvalidação de conteúdo e anotação\nquando aplicável"]

    R -->|Define hipóteses e revisa resultados| P
    D -->|Mantém código e integra extensões| P
    C -->|Configura| P
    P -->|Gera| A
    E -->|Revisa matriz e anota narrativas sintéticas| P
```

## Limites

O diagrama não inclui sistemas de prontuário, pacientes, bases clínicas ou integração assistencial. Esses elementos estão fora do escopo da prova de conceito atual.

## Usuários principais

| Ator | Necessidade |
|---|---|
| Pesquisador | executar cenários e interpretar resultados sintéticos |
| Desenvolvedor | manter módulos, scripts, contratos e documentação |
| Especialista | validar conteúdo da matriz ou anotar textos sintéticos, quando a etapa for formalizada |
