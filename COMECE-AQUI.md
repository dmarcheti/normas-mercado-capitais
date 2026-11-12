# Comece aqui (para a IA que recebeu este link)

Você é um assistente de IA e uma pessoa pediu que instale ou use este acervo: normas do mercado de capitais brasileiro (Resoluções e Instruções CVM vigentes, Pareceres de Orientação, Ofícios-Circulares, leis e decretos, normas do CMN e do BCB e autorregulação da ANBIMA e da B3) em Markdown, com data-base e nível de verificação por norma, e fichas dos julgados da CVM e do CRSFN, com link para o texto integral. Material não oficial; não substitui o Diário Oficial da União nem os sites dos órgãos e entidades de origem. A autorregulação da ANBIMA e da B3 é texto de titularidade delas, para uso informativo (`plugins/normas/skills/consultar-normas/normas/autorregulacao/README.md`).

## Primeiro passo

Pergunte à pessoa qual plataforma ela usa e siga só a seção correspondente:

1. claude.ai (navegador ou aplicativo)
2. Claude Code (terminal)
3. ChatGPT
4. Outra

Repositório: `dmarcheti/normas-mercado-capitais` (hoje privado). Marketplace: `normas-mercado-capitais`. Plugin único: `normas` (normas e julgados), versão 2.0.0.

## claude.ai

1. Customize > Plugins > Add marketplace.
2. Informe `dmarcheti/normas-mercado-capitais`.
3. Instale o plugin `normas`. Quem tinha os plugins `julgados-*` deve removê-los: saíram do marketplace na 2.0.0 e o `normas` já cobre os julgados.
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

Quem tinha os plugins `julgados-*` remova-os, um a um (`/plugin uninstall julgados-pas@normas-mercado-capitais`, por exemplo): saíram do marketplace na 2.0.0. Depois ligue o auto-update do marketplace (`/plugin`, aba Marketplaces, o marketplace `normas-mercado-capitais`, opção de atualização automática). Em repositório privado, o `git` da máquina precisa ter acesso ao GitHub.

## ChatGPT

Não há marketplace nem atualização automática.

1. Peça à pessoa o `.zip` da última release do repositório (página Releases do GitHub; com o repositório privado, ela precisa estar logada).
2. Crie um Projeto e anexe o `.zip` (ou a pasta `plugins/normas/skills/consultar-normas/`, que tem `normas/` e `julgados/`).
3. Cole nas instruções do Projeto o conteúdo de `plugins/normas/skills/consultar-normas/SKILL.md`, a partir da seção "Como ler os arquivos". Os textos integrais dos julgados ficam em `julgados/`, na raiz do repositório; anexe também essa pasta se quiser que a IA leia o texto integral.
4. Avise que, para atualizar, a pessoa deve baixar a release nova e trocar os arquivos.

## Outra plataforma

Os arquivos são Markdown comum. Dê ao assistente a pasta `plugins/normas/skills/consultar-normas/` (com `normas/` e `julgados/`) e, se quiser o texto integral dos julgados, a pasta `julgados/` da raiz do repositório. As regras de uso estão em `plugins/normas/skills/consultar-normas/SKILL.md`.

## Como usar o acervo depois de instalado

- Todos os caminhos abaixo são relativos a `plugins/normas/skills/consultar-normas/`.
- Normas: comece por `normas/indice.md`, que aponta um subíndice por tipo em `normas/indices/`.
- Cada norma é um arquivo; cada artigo é um título `## Art. N` (pareceres, ofícios e parte da autorregulação não têm artigos).
- O frontmatter diz a situação da norma e a data-base (`vigente_ate_ato`). Cite sempre a data-base e o dispositivo exato (ex.: art. 9º, § 2º, Res. CVM 175).
- Julgados: comece por `julgados/indice.md`. Ache o caso nos índices de `julgados/indices/`, leia a ficha (coluna Ficha, seção `## <id>`) e responda por ela. Para o fundamento do voto ou os fatos, leia o `texto_integral` da ficha (link do GitHub, no `julgados/` da raiz do repositório). Se a plataforma recusar o link, peça à pessoa: "Para eu ler o texto integral, cole este link na conversa: <url>". Julgado não é norma.
- Se a norma ou o artigo não estiver no acervo, diga isso. Não responda de memória quando o arquivo existe.
- O acervo é atualizado a cada duas semanas. Veja a linha "Fontes conferidas até AAAA-MM-DD" no índice e informe essa data: ato publicado depois dela, ou até cerca de duas semanas antes, pode ainda não estar no acervo. Norma com aviso no campo `incerteza` tem ato alterador publicado e ainda não aplicado; leia o ato junto.

## Teste de aceitação

Depois de instalar, faça as 5 perguntas de `testes/perguntas-piloto.md` e compare com as respostas esperadas. Anote quantas acertou e se citou a data-base.
