# Segurança, dados e comunicação responsável

## Escopo de dados permitido

Este repositório foi projetado para trabalhar exclusivamente com **dados sintéticos**. É proibido inserir, anexar, versionar, registrar em log ou enviar a um provedor externo:

- prontuários ou trechos de prontuários;
- nomes, endereços, telefones, documentos, identificadores de pacientes ou profissionais;
- qualquer informação pessoal, sensível ou potencialmente identificável;
- chaves de API, tokens, senhas, certificados ou arquivos `.env` reais.

## Credenciais de APIs futuras

O projeto inclui o adaptador opcional `GeminiNarrativeGenerator`, mas o modo padrão continua sendo local (`template`). Ao usar Gemini ou outro adaptador externo:

- armazene credenciais apenas em variáveis de ambiente, cofre de segredos ou configuração local ignorada pelo Git;
- nunca grave credenciais em YAML, notebooks compartilhados, artefatos ou logs;
- use privilégios mínimos e rotação de chaves quando o serviço permitir;
- registre metadados do modelo e da execução, mas não conteúdo sensível;
- confirme que as políticas do provedor são compatíveis com o uso exclusivamente sintético do projeto;
- não tente desativar filtros de segurança do provedor para contornar falhas de geração; registre e avalie as falhas.

Um arquivo `.env.example` pode documentar nomes de variáveis sem conter valores reais.

## Relato de vulnerabilidades

Não publique detalhes de vulnerabilidades, exposição de credenciais ou inclusão acidental de dados no rastreador público de issues. Entre em contato com o responsável pelo repositório por canal privado e inclua:

- descrição do problema;
- arquivos ou componentes envolvidos;
- impacto potencial;
- passos mínimos para reprodução;
- evidências de que nenhum dado sensível foi compartilhado na comunicação.

## Salvaguarda metodológica

Uma falha de segurança também pode ser metodológica. São consideradas críticas as alterações que:

- enviem `prioridade_referencia` ou pistas equivalentes ao gerador de narrativas;
- misturem `marcadores_origem` e `marcadores_extraidos` sem declaração explícita;
- introduzam variáveis de auditoria, como `gravidade_latente_auditoria`, nos classificadores;
- permitam execução com dados reais sem uma avaliação ética e institucional independente.
