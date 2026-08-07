# Demonstração Streamlit com execução pré-carregada

Esta aplicação foi preparada para permitir que uma banca acadêmica inspecione os
artefatos de uma execução sintética já concluída. Ela funciona em modo somente
leitura: não recebe arquivos, não executa novamente o pipeline e não chama APIs
externas.

> **Escopo:** todos os perfis, narrativas, escores, marcadores e rótulos exibidos
> são sintéticos. A aplicação não é uma ferramenta assistencial e não deve ser
> apresentada como validação clínica.

## Conteúdo da execução congelada

A execução `demonstracao_precarregada` fica em
`demo_artifacts/demonstracao_precarregada/` e contém:

- 800 perfis inteiramente sintéticos;
- narrativas produzidas pelo gerador local por templates;
- marcadores extraídos pelo comparador determinístico por regras;
- três conjuntos analíticos e quatro comparadores de modelagem;
- 160 perfis no conjunto final reservado;
- métricas, matrizes de confusão, calibração e explicações;
- metadados, configuração resolvida e relatório automático.

## Executar localmente

Com `uv`:

```bash
uv sync --extra demo --locked
uv run streamlit run streamlit_app.py
```

Com `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

A interface estará disponível, por padrão, em `http://localhost:8501`.

## Implantar em Streamlit Community Cloud

1. publique o repositório em um serviço Git compatível;
2. confirme que `demo_artifacts/demonstracao_precarregada/` foi incluído no repositório;
3. no Streamlit Community Cloud, escolha `streamlit_app.py` como arquivo principal;
4. use uma versão de Python compatível com `pyproject.toml`;
5. implante sem cadastrar segredos: esta demonstração não usa chaves de API.

O arquivo `requirements.txt` já inclui o Streamlit. A aplicação adiciona o
diretório `src/` ao caminho de importação, portanto não depende de uma instalação
editável do pacote no ambiente de hospedagem.

## Implantar em contêiner

```bash
docker build -t pipeline-emulti-demo .
docker run --rm -p 8501:8501 pipeline-emulti-demo
```

O `Dockerfile` respeita a variável `PORT` quando ela é definida pela plataforma.

## Atualizar deliberadamente a execução demonstrativa

Somente o mantenedor deve regenerar os artefatos:

```bash
python scripts/run_pipeline.py \
  --config config/demo.yaml \
  --run-id demonstracao_precarregada
```

Antes de publicar a nova versão, execute os testes e revise os manifestos, as
métricas e o relatório. Não habilite upload ou entrada livre de dados sem uma
nova avaliação ética, de segurança e de finalidade.

## Roteiro sugerido para a banca

1. **Visão geral:** apresentar o fluxo completo e comparar os conjuntos analíticos.
2. **Perfis sintéticos:** abrir um perfil e percorrer dados, narrativa, previsão e
   auditoria dos marcadores.
3. **Qualidade e extração:** mostrar o contrato que impede vazamento de entradas.
4. **Modelagem:** comparar desenvolvimento, teste final e matriz de confusão.
5. **Interpretabilidade:** destacar que SHAP e coeficientes não indicam causalidade.
6. **Rastreabilidade:** abrir metadados e baixar os artefatos legíveis da execução.
