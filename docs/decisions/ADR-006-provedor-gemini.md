# ADR-006 — Adotar adaptador opcional para Gemini API

- **Status:** Aceita
- **Data:** 2026-06-25
- **Decisores:** equipe do projeto

## Contexto

O pipeline precisava de uma implementação concreta de LLM que preservasse a
arquitetura desacoplada já definida em `ADR-002`. A integração deveria funcionar
com credencial do próprio pesquisador, sem inserir segredos no código, no YAML
ou nos artefatos, e sem modificar a semântica da prioridade simulada.

## Decisão

Foi adicionado `GeminiNarrativeGenerator`, baseado no SDK oficial
`google-genai` e selecionado por `narrative.provider: gemini`. A configuração
executável `config/gemini.yaml` herda `config/base.yaml`, evitando duplicação de
parâmetros científicos.

O adaptador:

- recebe somente `NarrativeRequest`;
- bloqueia recursivamente chaves de prioridade e rótulo;
- envia somente `dados_estruturados`, `indicadores_psicometricos` e
  `marcadores_origem` ao conteúdo do prompt;
- solicita JSON estruturado com `subjective` e `assessment`;
- registra metadados sem credenciais;
- usa semente, hash do prompt, retentativas e artefatos de saída para
  rastreabilidade;
- mantém `TemplateNarrativeGenerator` como padrão local e sem custo.

## Consequências

### Positivas

- permite testar narrativas mais variadas sem mudar as etapas posteriores;
- fornece um caminho documentado para Google Colab e ambiente local;
- melhora a auditabilidade por meio de metadados padronizados;
- mantém o modo template para testes rápidos, sem dependência externa.

### Negativas ou custos

- a execução pode consumir cota e gerar custo conforme o modelo selecionado;
- saídas de LLM podem variar entre execuções e atualizações do provedor;
- filtros de segurança, limites de taxa e indisponibilidade podem interromper a
  geração de alguns perfis;
- o adaptador não transforma resultados sintéticos em evidência clínica.

## Critérios de reavaliação

Revisar esta decisão quando houver mudança incompatível no SDK/API, necessidade
de processamento em lote, adoção de outro provedor ou resultado de auditoria que
mostre inconsistências relevantes nas narrativas geradas.
