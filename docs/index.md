# Documentação do pipeline

Esta documentação descreve como compreender, executar, manter e estender o pipeline sintético de priorização para e-Multi. Ela é versionada junto com o código para que decisões metodológicas e implementações evoluam de forma rastreável.

## Como navegar

A organização segue quatro tipos de necessidade:

| Se você precisa... | Consulte... |
|---|---|
| Entender conceitos, limites e escolhas de desenho | [Explicações](explanation/visao-geral.md) |
| Aprender por meio de uma execução guiada | [Tutoriais](tutorials/primeira-execucao.md) |
| Apresentar a execução sintética pré-carregada | [Demonstração Streamlit](tutorials/demonstracao-streamlit.md) |
| Resolver uma tarefa específica | [Guias práticos](how-to/criar-cenario.md) |
| Visualizar resultados de classificação | [Tabela ordenada da classificação](how-to/visualizar-classificacao-final.md) |
| Gerar narrativas por API Gemini | [Usar o provedor Gemini](how-to/usar-provedor-gemini.md) |
| Consultar contratos, parâmetros, scripts e artefatos | [Referência](reference/configuracao.md) |

## Conteúdo essencial para novos desenvolvedores

1. [Visão geral](explanation/visao-geral.md) — objetivo, limites e vocabulário do projeto.
2. [Metodologia e fluxo de dados](explanation/metodologia-e-fluxo.md) — relação entre `dados_estruturados`, `indicadores_psicometricos`, `marcadores_origem`, `narrativa_clinica`, `marcadores_extraidos`, `prioridade_referencia` e `prioridade_prevista`.
3. [Primeira execução local](tutorials/primeira-execucao.md) — instalação e smoke test.
4. [Nomenclatura do pipeline](reference/nomenclatura.md) — nomes padronizados das estruturas centrais.
5. [Contratos de dados](reference/contratos-de-dados.md) — entradas e saídas formais.
6. [Arquitetura C4](architecture/c4-componentes.md) — componentes e fronteiras.
7. [ADRs](decisions/README.md) — decisões que não devem ser alteradas sem revisão.
8. [Tabela ordenada da classificação](how-to/visualizar-classificacao-final.md) — inspeção dos perfis sintéticos classificados.
9. [Provedor Gemini](how-to/usar-provedor-gemini.md) — integração externa opcional, sem mudar os contratos do pipeline.

## Regras de leitura obrigatória

Antes de editar o código, tenha clareza sobre estas três restrições:

- **Não há dados reais de pacientes.**
- **`prioridade_referencia` não é prioridade clínica real; é uma referência simulada.**
- **O gerador de narrativas não pode receber prioridade, códigos, limiares ou pista equivalente.**

## Uso no GitHub

Todos os arquivos são Markdown e podem ser lidos diretamente no GitHub. O arquivo `mkdocs.yml` oferece uma navegação opcional caso o repositório publique a documentação como site estático.

## Manutenção

Consulte [Governança da documentação](governanca-documentacao.md) para saber quando atualizar cada documento e como registrar mudanças de arquitetura.
