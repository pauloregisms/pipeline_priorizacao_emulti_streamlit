# Limites e salvaguardas

## Interpretação obrigatória dos resultados

Resultados deste projeto devem ser descritos como evidências sobre o comportamento de um pipeline em **cenário sintético controlado**. Eles não devem ser descritos como:

- capacidade de identificar risco verdadeiro;
- prioridade clínica validada;
- desempenho em APS ou e-Multi reais;
- recomendação clínica;
- evidência de benefício, redução de espera ou segurança do cuidado.

## Limites do gerador

As relações entre vulnerabilidade, gravidade latente, escalas, marcadores e prioridade foram programadas no próprio estudo. Consequentemente:

- correlações podem ser mais fortes ou mais simples que em dados observacionais;
- a distribuição de classes pode não refletir serviços reais;
- a narrativa pode preservar informação de maneira excessivamente coerente;
- desempenho alto pode refletir a recuperação de regras conhecidas;
- ausência de dados faltantes reais, mudança temporal e heterogeneidade institucional limita a generalização.

## Limites da extração

O extrator de referência é baseado em padrões textuais. Ele é auditável e independente do gerador, mas não cobre toda a complexidade de textos clínicos. Temporalidade, incerteza, severidade e experienciador são tratados por regras simples.

A validação contra `marcadores_origem` demonstra fidelidade ao cenário gerado. Ela não substitui anotação humana independente. O projeto prevê uma amostra estratificada para dupla anotação e cálculo de concordância.

## Limites da matriz de prioridade

A matriz implementada é ilustrativa. Antes de qualquer análise de dissertação, os critérios, pesos, limiares e precedências devem ser documentados, justificados e submetidos a validação de conteúdo por especialistas.

> **Importante:** a implementação atual da regra-base possui limiares duplicados em `src/emulti_pipeline/priority.py`. Antes de calibrar parâmetros, centralize os limiares para que a regra-base e a matriz de referência leiam a mesma fonte versionada. Isso está registrado como dívida técnica na documentação de referência.

## Salvaguardas obrigatórias

- Não inserir dados reais ou identificáveis.
- Não enviar `prioridade_referencia` ou informação equivalente ao gerador de narrativas.
- Não usar `gravidade_latente_auditoria` no treinamento ou avaliação de classificadores.
- Não substituir o extrator independente por um LLM sem manter uma linha de base auditável.
- Não publicar credenciais ou narrativas que possam conter informação real.
- Não integrar resultados a fluxos assistenciais.

## Caminho para pesquisas futuras

Qualquer extensão com dados reais requer projeto independente, avaliação ética e institucional apropriada, governança, autorização do controlador, validação retrospectiva, validação temporal/geográfica, avaliação de equidade e estudo de impacto antes de uso em serviço.
