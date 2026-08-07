# ADR-002 — Desacoplar geração de narrativas de fornecedores de LLM

- **Status:** Aceita
- **Data:** 2026-06-24
- **Decisores:** equipe do projeto

## Contexto

A metodologia exige narrativa SOAP sintética, mas não deve depender de plano comercial, API ou fornecedor específico. Além disso, o pipeline precisa executar localmente para testes, depuração e reprodutibilidade básica.

## Decisão

A geração textual será definida por `BaseNarrativeGenerator`. Implementações devem receber `NarrativeRequest` e devolver `NarrativeResponse`. A implementação padrão é `TemplateNarrativeGenerator`, um simulador local determinístico por semente.

## Consequências

### Positivas

- execução sem API e sem credenciais;
- troca de provedor isolada do restante do pipeline;
- contrato de entrada/saída explícito;
- metadados de execução podem ser padronizados.

### Negativas ou custos

- cada novo adaptador exige testes de contrato e de qualidade textual;
- resultados podem variar quando um LLM real for introduzido;
- prompts e parâmetros precisam ser versionados.

## Critérios de reavaliação

Revisar se o projeto adotar outro tipo de gerador que não possa obedecer aos contratos atuais.
