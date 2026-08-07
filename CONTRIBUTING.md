# Como contribuir

Obrigado por contribuir com o pipeline sintético de priorização para e-Multi. Este repositório é simultaneamente um artefato de software e parte de uma pesquisa metodológica. Portanto, uma alteração pode afetar o código, os resultados, a documentação e a interpretação científica.

## Princípios de contribuição

1. **Não introduzir dados reais.** O repositório e seus artefatos devem permanecer inteiramente sintéticos.
2. **Não ocultar decisões metodológicas.** Mudanças em regras, parâmetros, modelos, métricas ou contratos precisam ser rastreáveis.
3. **Não criar vazamento de rótulo.** `prioridade_referencia`, códigos de prioridade, limiares de decisão ou campos equivalentes não podem chegar à geração textual nem a etapas que os usem como pistas indevidas.
4. **Preservar a separação entre `marcadores_origem` e `marcadores_extraidos`.** Marcadores verdadeiros do gerador e marcadores extraídos do texto não são intercambiáveis.
5. **Atualizar a documentação no mesmo pull request.** Código e documentação devem evoluir juntos.

## Antes de começar

1. Leia [README.md](README.md) e [docs/index.md](docs/index.md).
2. Consulte os [ADRs](docs/decisions/README.md) para decisões já aceitas.
3. Verifique as [limitações conhecidas](docs/explanation/limites-e-salvaguardas.md).
4. Abra ou associe uma issue para mudanças relevantes.

## Ambiente local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Execute a verificação mínima antes de enviar alterações:

```bash
python -m compileall src scripts
python scripts/run_pipeline.py \
  --config config/base.yaml \
  --run-id contributer_smoke_test \
  --skip-explanations \
  --skip-report \
  --stop-after 03_quality_control_base.py
```

> O identificador `contributer_smoke_test` pode ser substituído por outro. Os artefatos em `artifacts/` não devem ser versionados, exceto arquivos explicitamente selecionados como exemplos sintéticos e revisados.

## Fluxo sugerido de trabalho

1. Crie uma branch com nome descritivo, por exemplo `docs/contratos-llm` ou `feat/novo-cenario-ruido`.
2. Faça alterações pequenas e coerentes em cada commit.
3. Atualize os testes ou a checagem de execução quando necessário.
4. Atualize os documentos afetados em `docs/`.
5. Atualize `CHANGELOG.md` quando a mudança for relevante para usuários do projeto.
6. Abra um pull request usando o modelo fornecido em `.github/pull_request_template.md`.

## Quando criar um ADR

Crie um novo documento em `docs/decisions/` quando a alteração for difícil de reverter, alterar uma restrição metodológica ou tiver impacto transversal. Exemplos:

- troca do gerador probabilístico por outro mecanismo;
- inclusão de um provedor de LLM;
- mudança na semântica ou nas classes de `prioridade_referencia`;
- alteração no conjunto de modelos comparados;
- mudança em como são preservados os artefatos;
- alteração de política para dados, credenciais ou publicação de resultados.

Use o modelo presente em `docs/decisions/ADR-TEMPLATE.md`.

## Padrões mínimos de código

- Use tipagem quando ela melhorar a clareza do contrato.
- Preserve docstrings em módulos, classes e funções públicas.
- Não deixe parâmetros científicos escondidos no código. Parâmetros devem ficar no YAML ou ter justificativa explícita.
- Use sementes explícitas e não substitua geradores determinísticos por chamadas aleatórias sem rastreabilidade.
- Mantenha caminhos de leitura e escrita encapsulados pelas funções de `utils.py` quando possível.
- Prefira mensagens de erro que indiquem a etapa, a coluna ou o arquivo necessário.

## Mudanças na geração de narrativas

O adaptador Gemini já implementado deve obedecer ao [guia de uso](docs/how-to/usar-provedor-gemini.md). Toda nova integração de LLM deve obedecer à [política de integração](docs/how-to/adicionar-provedor-llm.md):

- implementar `BaseNarrativeGenerator`;
- aceitar apenas `NarrativeRequest`;
- retornar `NarrativeResponse`;
- registrar metadados de execução;
- bloquear prioridade e informações que revelem o rótulo;
- não incluir chave de API, URL privada ou dado real em commits, logs ou artefatos públicos.

## Mudanças nos parâmetros de simulação

Antes de alterar `config/base.yaml` ou adicionar um cenário:

1. registre a fonte, a justificativa ou o consenso de especialistas;
2. documente a alteração em [Configuração YAML](docs/reference/configuracao.md);
3. avalie a necessidade de atualizar a [matriz de prioridade](docs/reference/matriz-de-prioridade.md);
4. execute cenário-base e análise de sensibilidade;
5. registre impactos esperados e observados no pull request.

## Revisão de pull request

Um pull request só deve ser considerado pronto quando:

- [ ] não introduz dados reais, identificáveis ou credenciais;
- [ ] preserva a prevenção de vazamento de rótulo;
- [ ] executa pelo menos a checagem de compilação e um smoke test;
- [ ] documenta efeitos em contratos, parâmetros ou artefatos;
- [ ] inclui ADR quando a decisão for arquitetural ou metodológica;
- [ ] não apresenta resultados sintéticos como evidência clínica.
