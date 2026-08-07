# Pipeline Sintético de Priorização para e-Multi

> **Status:** prova de conceito de pesquisa. Este projeto gera e analisa dados inteiramente sintéticos; não usa prontuários, não recebe dados pessoais, não produz diagnóstico e não deve ser usado para priorização assistencial real.

Este repositório implementa uma simulação computacional para testar, em ambiente controlado, um fluxo de geração de perfis sintéticos, escalas psicométricas, narrativas clínicas SOAP, extração de marcadores e classificação de uma **prioridade de referência simulada** para encaminhamentos em saúde mental à e-Multi.

A finalidade é metodológica: avaliar plausibilidade, rastreabilidade, consistência interna e robustez do pipeline. Métricas elevadas neste repositório indicam apenas capacidade de recuperar relações e regras programadas no próprio cenário de simulação.

## Vinculação acadêmica

Este projeto é resultado da pesquisa de mestrado de **Renata Alves dos Santos**,
formanda do Curso de Mestrado Profissional em Saúde da Família (MPSF), vinculado
ao Programa de Pós-Graduação em Saúde da Família (PPGSF), da Universidade
Estadual Vale do Acaraú (UVA), em pesquisa orientada pelo Professor Dr. Paulo Regis Menezes Sousa.

O repositório reúne os artefatos computacionais desenvolvidos para a dissertação,
incluindo a simulação de dados, a geração de narrativas clínicas sintéticas, a
extração de marcadores e a classificação de prioridade de referência simulada
para encaminhamentos em saúde mental no contexto da Atenção Primária à Saúde
e da equipe e-Multi.

## Comece aqui

| Perfil | Próxima leitura |
|---|---|
| Banca ou avaliador acadêmico | [Demonstração Streamlit](docs/tutorials/demonstracao-streamlit.md) |
| Novo desenvolvedor | [Visão geral do projeto](docs/explanation/visao-geral.md) e [Primeira execução](docs/tutorials/primeira-execucao.md) |
| Pesquisador que vai alterar o cenário | [Como criar um cenário](docs/how-to/criar-cenario.md) e [Configuração YAML](docs/reference/configuracao.md) |
| Desenvolvedor que vai gerar narrativas com Gemini | [Usar o provedor Gemini](docs/how-to/usar-provedor-gemini.md) e [Contratos de dados](docs/reference/contratos-de-dados.md) |
| Desenvolvedor que vai integrar outro LLM | [Como adicionar um provedor de LLM](docs/how-to/adicionar-provedor-llm.md) e [Contratos de dados](docs/reference/contratos-de-dados.md) |
| Pessoa responsável por regras de prioridade | [Matriz de prioridade](docs/reference/matriz-de-prioridade.md) e [ADR-003](docs/decisions/ADR-003-prioridade-simulada-ordinal.md) |
| Revisor de arquitetura | [arc42 resumido](docs/architecture/arc42.md) e diagramas [C4](docs/architecture/c4-contexto.md) |

A documentação completa está organizada no diretório [`docs/`](docs/index.md), seguindo uma combinação de **Docs-as-Code**, **Diátaxis**, **arc42/C4** e **Architecture Decision Records (ADRs)**.

## O que o pipeline faz

1. gera atributos sociodemográficos, psicossociais, clínicos e de utilização de serviços;
2. cria uma gravidade latente `gravidade_latente_auditoria` para o gerador, preservada apenas para auditoria;
3. simula respostas por item e totais de PHQ-9, GAD-7 e IDATE-Estado;
4. verifica faixas e regras de consistência da base;
5. produz narrativa SOAP com provedor configurável (`template` para teste local ou Gemini para o experimento principal);
6. constrói `prioridade_referencia`, uma prioridade de referência simulada, **após** gerar a narrativa;
7. extrai marcadores qualificados por provedor independente; Gemini é comparado a uma linha de base por regras;
8. compara três conjuntos analíticos: `dados_estruturados + indicadores_psicometricos`, `dados_estruturados + indicadores_psicometricos + marcadores_origem` e `dados_estruturados + indicadores_psicometricos + marcadores_extraidos`;
9. avalia regra-base, regressão logística ordinal, Random Forest e XGBoost;
10. produz métricas de classificação, ordinalidade, calibração, robustez e explicabilidade;
11. consolida uma tabela ordenada de classificação para inspeção dos perfis sintéticos.

O mapa detalhado entre cada passo metodológico e os scripts está em [MAPA_DE_ETAPAS.md](MAPA_DE_ETAPAS.md) e na [referência de scripts](docs/reference/scripts.md).

## Garantias metodológicas essenciais

- `prioridade_referencia` não é uma variável clínica real; é a saída da matriz de prioridade simulada.
- O gerador de narrativas recebe somente `dados_estruturados`, `indicadores_psicometricos` e `marcadores_origem`; não recebe `prioridade_referencia`, códigos, nomes de prioridade ou limiares que revelem o rótulo.
- A geração textual ocorre antes da criação de `prioridade_referencia`.
- A gravidade latente `gravidade_latente_auditoria` não entra nos conjuntos analíticos usados pelos classificadores.
- O extrator por regras é mantido como referência independente, inclusive quando uma futura versão usar LLM para extração.
- Parâmetros em `config/base.yaml` são **ilustrativos** e devem ser calibrados antes de qualquer análise acadêmica definitiva.

## Estrutura do repositório

```text
pipeline_priorizacao_emulti/
├── config/                    # parâmetros dos cenários de simulação
├── src/emulti_pipeline/       # módulos reutilizáveis do pipeline
├── scripts/                   # etapas executáveis 00–14 e orquestrador
├── artifacts/                 # saídas de execução (ignoradas pelo Git)
├── demo_artifacts/            # execução sintética congelada para a demonstração
├── docs/                      # documentação versionada
├── .streamlit/config.toml     # tema e salvaguardas da interface
├── streamlit_app.py           # aplicação somente leitura para a banca
├── .github/                   # modelos de colaboração no GitHub
├── README.md                  # entrada rápida para o projeto
├── CONTRIBUTING.md            # fluxo de contribuição
├── SECURITY.md                # dados, chaves e comunicação de vulnerabilidades
└── mkdocs.yml                 # navegação opcional para site de documentação
```

## Instalação local

Requisitos mínimos: Python 3.10 ou superior e `pip` atualizado.

```bash
python -m venv .venv
source .venv/bin/activate            # Linux/macOS
# .venv\Scripts\Activate.ps1         # Windows PowerShell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Para uma instalação reproduzível com o arquivo de lock e as dependências de teste:

```bash
uv sync --extra dev --extra gemini --locked
```

Para a execução detalhada, consulte o [tutorial de primeira execução](docs/tutorials/primeira-execucao.md). Para uso em notebook, consulte [Google Colab](docs/tutorials/google-colab.md).

## Demonstração Streamlit para avaliação

O projeto inclui uma interface somente de leitura com uma execução sintética já
carregada. Ela permite inspecionar perfis, narrativas, marcadores, métricas,
explicações e metadados sem reexecutar o pipeline e sem configurar uma chave de API.

```bash
uv sync --extra demo --locked
uv run streamlit run streamlit_app.py
```

A execução demonstrativa fica em
`demo_artifacts/demonstracao_precarregada/`. A aplicação não possui upload,
entrada de dados reais ou botão de nova execução. Consulte o
[tutorial de implantação e apresentação](docs/tutorials/demonstracao-streamlit.md).

## Execução rápida

```bash
python scripts/run_pipeline.py --config config/base.yaml --run-id baseline
```

Para uma verificação rápida sem modelagem, explicabilidade ou relatório final:

```bash
python scripts/run_pipeline.py \
  --config config/base.yaml \
  --run-id smoke_test \
  --skip-explanations \
  --skip-report \
  --stop-after 03_quality_control_base.py
```

A análise de sensibilidade é executada separadamente, pois gera novas réplicas do pipeline:

```bash
python scripts/12_run_sensitivity.py --config config/base.yaml --run-id baseline
```

## Resultado esperado

Cada execução é gravada em `artifacts/<run_id>/`. Os principais produtos são descritos em [Artefatos gerados](docs/reference/artefatos.md):

- `01_profiles/profiles.csv` — atributos estruturados, `marcadores_origem` e coluna de auditoria do gerador;
- `02_psychometrics/psychometrics.csv` — itens e totais das escalas;
- `04_narratives/narratives.jsonl` — narrativas SOAP e metadados;
- `05_priority/prioridade_referencia.csv` — `prioridade_referencia` e evidências da matriz;
- `06_extraction/marcadores_extraidos.csv` — marcadores extraídos `marcadores_extraidos`;
- `08_extraction_validation/` — métricas macro/micro, qualificadores, bootstrap, estabilidade e concordância;
- `09_analytical_sets/` — os três conjuntos analíticos;
- `10_modeling/` — previsões, métricas, modelos e intervalos;
- `11_explanations/` — coeficientes e/ou saídas SHAP;
- `13_report/report.md` — síntese automática da execução;
- `14_priority_view/classification_queue.csv` — tabela ordenada da classificação final para inspeção de perfis sintéticos.
- `14_priority_view/prediction_traceability.csv` — ligação por perfil entre geração, extração, regra e modelo.

Consulte também [Como visualizar a classificação final](docs/how-to/visualizar-classificacao-final.md).

## Geração de narrativas com Gemini (opcional)

A geração narrativa permanece desacoplada em `src/emulti_pipeline/narratives.py`. Além do simulador local `TemplateNarrativeGenerator`, o projeto inclui `GeminiNarrativeGenerator`, selecionado por `config/gemini.yaml`.

A integração Gemini:

- lê a chave somente da variável de ambiente `GEMINI_API_KEY`;
- solicita saída JSON estruturada com os campos SOAP `subjective` e `assessment`;
- registra provedor, modelo, timestamp, versão do prompt, parâmetros, semente, hash do prompt e retentativas;
- bloqueia recursivamente campos de prioridade antes da chamada;
- nunca recebe ou deve receber dados reais de pacientes.

Faça primeiro o teste curto:

```bash
export GEMINI_API_KEY='cole-a-chave-somente-no-terminal'
python scripts/run_pipeline.py \
  --config config/gemini_smoke.yaml \
  --run-id gemini_smoke \
  --skip-explanations \
  --skip-report \
  --stop-after 04_generate_narratives.py
```

Consulte [Usar o provedor Gemini](docs/how-to/usar-provedor-gemini.md). Para criar outro adaptador, consulte [Como adicionar um provedor de LLM](docs/how-to/adicionar-provedor-llm.md).

## Contribuição e documentação

Antes de contribuir, leia [CONTRIBUTING.md](CONTRIBUTING.md). Mudanças em scripts, parâmetros, contratos de dados ou regras de prioridade devem atualizar a documentação e, quando aplicável, um ADR ou o changelog.

> **Licença:** ainda não definida. Não reutilize ou redistribua o código fora do contexto autorizado pelo responsável pelo repositório até que uma licença seja escolhida.
