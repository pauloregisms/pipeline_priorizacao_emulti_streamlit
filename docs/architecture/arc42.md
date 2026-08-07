# Arquitetura — arc42 resumido

## 1. Objetivos e requisitos de qualidade

O sistema deve ser:

- reproduzível por semente, configuração e artefatos;
- modular por etapa metodológica;
- auditável quanto a entradas e saídas;
- seguro quanto à ausência de dados reais e credenciais;
- explícito sobre limites de interpretação;
- extensível para diferentes geradores de narrativa sem acoplamento ao restante do pipeline.

## 2. Restrições de arquitetura

- Python é a linguagem de implementação.
- Dados e narrativas são inteiramente sintéticos.
- Parâmetros devem ser configuráveis e documentados.
- `prioridade_referencia` não pode entrar na geração textual.
- `gravidade_latente_auditoria` não pode entrar na modelagem.
- A saída do gerador textual deve obedecer a contratos estáveis.
- A validação é interna e orientada a simulação; não é validação clínica.

## 3. Contexto e fronteiras

O sistema é usado por pesquisador e desenvolvedor para executar cenários. Ele recebe YAML e código versionado e produz artefatos de simulação. Não se conecta ao PEC, a bases clínicas ou a fluxos assistenciais.

Veja [C4 — Contexto](c4-contexto.md).

## 4. Estratégia de solução

A solução é uma pipeline orientada a arquivos e scripts:

- módulos em `src/emulti_pipeline` encapsulam regras reutilizáveis;
- scripts em `scripts/` compõem etapas explícitas;
- YAML controla parâmetros;
- artefatos intermediários permitem auditoria;
- o gerador de narrativa usa uma interface abstrata;
- o extrator por regras funciona como linha de base independente;
- a modelagem usa conjuntos comparáveis e validação aninhada.

## 5. Blocos de construção

| Bloco | Responsabilidade |
|---|---|
| Configuração | carregar YAML e validar contexto básico |
| Simulação | gerar perfis, `gravidade_latente_auditoria`, `marcadores_origem` e escalas |
| Qualidade | verificar invariantes e propriedades psicométricas |
| Narrativas | criar `narrativa_clinica` por contrato desacoplado |
| Prioridade | gerar `prioridade_referencia` pela matriz simulada |
| Extração | transformar texto em `marcadores_extraidos` |
| Conjuntos analíticos | construir `dados_estruturados + indicadores_psicometricos`, `dados_estruturados + indicadores_psicometricos + marcadores_origem`, `dados_estruturados + indicadores_psicometricos + marcadores_extraidos` |
| Modelagem | comparar linha de base e classificadores |
| Avaliação | métricas, calibração, bootstrap |
| Explicabilidade | coeficientes e SHAP no teste |
| Relatório | consolidar saída para inspeção |

Veja [C4 — Componentes](c4-componentes.md).

## 6. Fluxo de execução

O fluxo principal é descrito em [Metodologia e fluxo](../explanation/metodologia-e-fluxo.md). Cada script é uma fronteira de etapa e grava arquivos intermediários para facilitar depuração.

## 7. Conceitos transversais

- **Reprodutibilidade:** sementes, YAML, manifests, metadados de ambiente e hashes.
- **Segurança:** dados sintéticos, segredos fora do repositório, bloqueio de rótulos na narrativa.
- **Rastreabilidade:** `run_id`, `patient_id` sintético e arquivos por etapa.
- **Interpretabilidade:** métricas por classe, ordinalidade, calibração, coeficientes e SHAP.
- **Documentação:** Docs-as-Code e ADRs.

## 8. Decisões relevantes

Consulte [ADRs](../decisions/README.md).

## 9. Riscos técnicos

| Risco | Mitigação atual |
|---|---|
| Vazamento de rótulo | ordem do fluxo, contrato restrito e checagem de chaves proibidas |
| Divergência entre YAML e regras hardcoded | documentada como dívida técnica; requer refatoração antes de calibração final |
| Dependência de LLM | interface desacoplada e simulador local |
| Métrica inflada por cenário sintético | documentação de limites, múltiplos cenários e avaliação de extração |
| Artefatos grandes | `.gitignore` e preservação seletiva |

## 10. Glossário

Veja [Visão geral](../explanation/visao-geral.md) e [Contratos de dados](../reference/contratos-de-dados.md).
