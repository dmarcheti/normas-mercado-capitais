# Comece aqui (para a IA que recebeu este link)

Você é um assistente de IA e uma pessoa pediu que instale ou use este acervo: normas do mercado de capitais brasileiro (8 resoluções da CVM com histórico por ato e 12 leis) em Markdown, com data-base e histórico por ato alterador. Material não oficial; não substitui o Diário Oficial da União nem o site da CVM.

## Primeiro passo

Pergunte à pessoa qual plataforma ela usa e siga só a seção correspondente:

1. claude.ai (navegador ou aplicativo)
2. Claude Code (terminal)
3. ChatGPT
4. Outra

Repositório: `dmarcheti/normas-mercado-capitais` (hoje privado). Marketplace: `normas-mercado-capitais`. Plugin: `normas`.

## claude.ai

1. Customize > Plugins > Add marketplace.
2. Informe `dmarcheti/normas-mercado-capitais`.
3. Instale o plugin `normas`.
4. Ligue "Sync automatically", para receber as atualizações do acervo sem refazer nada.
5. Ligue a skill `consultar-normas` (Customize > Skills, ou dentro do plugin `normas`). Instalar o plugin não liga a skill: sem este passo, a IA responde pela busca na web e ignora o acervo.
6. Confira se a execução de código ("criar e editar arquivos") está ligada nas configurações; as skills dependem dela.
7. Teste: pergunte "o acervo de normas registra alguma divergência na Resolução CVM 17?". Se a resposta não citar o arquivo do acervo, a skill não está ativa.
8. Se o repositório ainda for privado, a conta precisa ter o Claude GitHub App instalado com acesso a ele. Sem isso a adição falha; diga isso à pessoa em vez de insistir.

## Claude Code

```
/plugin marketplace add dmarcheti/normas-mercado-capitais
/plugin install normas@normas-mercado-capitais
```

Depois ligue o auto-update do marketplace (`/plugin`, aba Marketplaces, o marketplace `normas-mercado-capitais`, opção de atualização automática). Em repositório privado, o `git` da máquina precisa ter acesso ao GitHub.

## ChatGPT

Não há marketplace nem atualização automática.

1. Peça à pessoa o `.zip` da última release do repositório (página Releases do GitHub; com o repositório privado, ela precisa estar logada).
2. Crie um Projeto e anexe o `.zip` (ou os arquivos de `plugins/normas/normas/`).
3. Cole nas instruções do Projeto o conteúdo de `plugins/normas/skills/consultar-normas/SKILL.md`, a partir da seção "Como navegar".
4. Avise que, para atualizar, a pessoa deve baixar a release nova e trocar os arquivos.

## Outra plataforma

Os arquivos são Markdown comum. Dê ao assistente a pasta `plugins/normas/normas/` e as regras de `plugins/normas/skills/consultar-normas/SKILL.md`.

## Como usar o acervo depois de instalado

- Comece pelo índice: `plugins/normas/normas/indice.md`.
- Cada norma é um arquivo; cada artigo é um título `## Art. N`.
- O frontmatter diz a situação da norma e a data-base (`vigente_ate_ato`). Cite sempre a data-base e o dispositivo exato (ex.: art. 9º, § 2º, Res. CVM 175).
- Se a norma ou o artigo não estiver no acervo, diga isso. Não responda de memória quando o arquivo existe.

## Teste de aceitação

Depois de instalar, faça as 5 perguntas de `testes/perguntas-piloto.md` e compare com as respostas esperadas. Anote quantas acertou e se citou a data-base.
