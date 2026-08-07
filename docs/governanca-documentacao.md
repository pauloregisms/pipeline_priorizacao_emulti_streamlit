# Governança da documentação

## Objetivo

Manter uma única fonte rastreável para a relação entre metodologia, parâmetros, código, artefatos e decisões de arquitetura.

## Regra de atualização conjunta

Uma mudança deve atualizar o documento correspondente no mesmo commit ou pull request.

| Alteração | Documentos que normalmente precisam ser revisados |
|---|---|
| Novo parâmetro no YAML | `reference/configuracao.md`, `reference/dicionario-de-dados.md`, `CHANGELOG.md` |
| Nova coluna ou formato de arquivo | `reference/contratos-de-dados.md`, `reference/artefatos.md` |
| Nova etapa de script | `reference/scripts.md`, `MAPA_DE_ETAPAS.md`, diagramas C4 |
| Nova regra de prioridade | `reference/matriz-de-prioridade.md`, ADR quando estrutural, documentação metodológica |
| Novo marcador clínico | `reference/ontologia-de-marcadores.md`, dicionário, contrato de dados e anotação humana |
| Novo modelo preditivo | `reference/scripts.md`, `architecture/arc42.md`, `CHANGELOG.md` |
| Integração com LLM | `how-to/adicionar-provedor-llm.md`, contratos, `SECURITY.md`, ADR |

## Hierarquia de fontes

Quando houver conflito entre arquivos, use esta ordem de interpretação:

1. código executável e testes/verificações atuais;
2. contratos de dados e configuração versionados;
3. ADRs aceitos;
4. documentação de arquitetura e referência;
5. explicações e tutoriais.

Se o código divergir do contrato ou do ADR, a divergência deve ser tratada como defeito ou como decisão pendente; não deve ser resolvida silenciosamente em documentação narrativa.

## Revisão periódica

Antes de cada rodada formal de experimento:

- confirmar que `config/base.yaml` ainda registra valores e fontes corretas;
- congelar hash/versão do código, YAML e prompts;
- revisar a matriz de prioridade e a ontologia;
- confirmar que `artifacts/` não contém dados não permitidos;
- registrar alterações no changelog.

## Publicação

A documentação pode ser revisada diretamente no GitHub. Quando o site MkDocs for usado, gere-o localmente com:

```bash
python -m pip install -r requirements-docs.txt
mkdocs serve
```

A publicação externa deve ocorrer somente a partir da documentação já revisada no repositório principal.
