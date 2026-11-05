---
name: consultar-julgados
description: Consulta julgados da CVM e do CRSFN (processos administrativos sancionadores julgados, decisões do Colegiado da CVM desde 1978 em recursos, consultas, dispensas e registros, termos de compromisso aceitos e rejeitados, acórdãos do CRSFN em recursos contra a CVM), com data, relator, resultado e os dispositivos citados. Use quando a pergunta for sobre como a CVM ou o CRSFN decidiu, precedente, entendimento do Colegiado, multa ou absolvição em caso concreto, termo de compromisso, ou sobre quais julgados aplicaram um artigo de norma.
---

# Consultar julgados

Acervo de julgados da CVM e do CRSFN em Markdown: um arquivo por julgado, com o texto como o órgão publica. Material não oficial; não substitui os sites da CVM e do CRSFN.

## Julgado não é norma

Um julgado diz o que a CVM ou o CRSFN decidiu num caso, com os fatos daquele caso e a redação das normas na época. Ele não vincula como norma e pode ter sido reformado. Ao responder:

- separe o que diz a norma (use a skill `consultar-normas`, se instalada) do que o julgado decidiu;
- diga a data do julgamento e que a norma aplicada pode ter mudado desde então;
- PAS julgado pela CVM pode ter recurso ao CRSFN: procure o acórdão pelo número do processo antes de dizer que a condenação ficou.

## Onde está cada coisa

Os julgados ficam em cinco plugins, por tipo e período; cada um tem a pasta `julgados/` e esta skill. Um caso pode estar em mais de um: o PAS em `julgados-pas`, o recurso dele ao CRSFN e um termo de compromisso no mesmo processo em `julgados-tc-crsfn`.

| Plugin | Conteúdo |
|---|---|
| `julgados-pas` | PAS julgados pela CVM (`julgados/cvm/pas/AAAA/`) |
| `julgados-tc-crsfn` | termos de compromisso aceitos e rejeitados (`julgados/cvm/colegiado/AAAA/`, `tipo: termo-compromisso`) e acórdãos do CRSFN em recursos contra a CVM (`julgados/crsfn/AAAA/`) |
| `julgados-colegiado-2002-2008`, `-2009-2015`, `-2016-2026` | demais decisões do Colegiado do período (`julgados/cvm/colegiado/AAAA/`); o de 2002 a 2008 inclui também as decisões de 1978 a 2001, um arquivo por ano (`julgados/cvm/decisoes-antigas/AAAA.md`) |

Use só a ferramenta de ler arquivo da sua plataforma; não use shell nem execução de código.

1. Leia `julgados/indice.md` do plugin: perímetro, contagens e subíndices.
2. Escolha o subíndice em `julgados/indices/`:
   - `norma-<id>.md`: julgados que citam cada dispositivo de uma norma (ex.: `norma-lei-6404.md`, `norma-cvm-res-175.md`; norma revogada, como `norma-fora-icvm-358.md`; a norma fora do acervo pouco citada fica no arquivo da família, como `norma-fora-outras-icvm.md`, com uma seção `## icvm-NNN` por norma). É o caminho para "como a CVM aplicou o art. X";
   - `tema-<tema>.md`: por assunto (ex.: `tema-informacao-privilegiada.md`, `tema-securitizacao.md`);
   - `<tipo>-<ano>.md`: por tipo e ano (ex.: `pas-2024.md`);
   - `processo-AAAA.md` (só em `julgados-pas` e `julgados-tc-crsfn`): por número de processo, com o PAS, o termo de compromisso e o acórdão do CRSFN do mesmo processo;
   - `decisao-antiga-AAAA.md` (ou `-s1`/`-s2`, `-t1` a `-t4`, no ano grande; só em `julgados-colegiado-2002-2008`): uma linha por decisão de 1978 a 2001, com data e número da ata, processo, título e `arquivo:linha`; leia o arquivo anual a partir dessa linha, com `offset`.
   Cada linha traz data, processo, resultado, tema, ementa e caminho.
3. Abra o arquivo do julgado. O frontmatter vem entre as duas linhas `---`; o texto tem uma seção `##` por peça (Extrato, Relatório, Voto, Declaração de voto, Manifestação da área técnica, Parecer do Comitê de Termo de Compromisso, Termo de compromisso, Decisão). Num PAS longo, leia o Extrato e o Voto antes do Relatório.

## Regras

- Cite assim: "PAS CVM nº 19957.011607/2024-20, j. 2025-05-27, rel. Dir. Fulano"; "Decisão do Colegiado de 2025-12-02, Proc. 19957.xxxxxx/AAAA-DV"; "Acórdão CRSFN nº N, sessão de AAAA-MM-DD". Diga o resultado (`resultado`) e, se houver, a multa como está no texto.
- `ementa_fonte`: `cvm` ou `crsfn` é a ementa oficial; `titulo` foi montada do título; `extracao` foi escrita por modelo de linguagem. Nos dois últimos casos, diga que a ementa não é oficial e confira no texto antes de usá-la.
- `tema_fonte: extracao` e `resultado` vazio: o campo veio de extração ou falta; confirme no texto.
- `nivel_verificacao`: `html-convertido`, `pdf-extraido` ou `ocr` (este com erros pontuais de leitura). Recomende conferir a fonte oficial (`fonte_original`) antes de usar em parecer ou peça.
- `incerteza`: leia e repasse o que for relevante (peça não segmentada, página por OCR, link de decisão suspeito).
- O índice por norma liga o dispositivo ao texto vigente hoje no plugin `normas`; o julgado aplicou a redação da época dos fatos. Norma marcada "fora do acervo" (Instruções e Deliberações revogadas) não tem texto no acervo.
- Dados pessoais: CPF, documento, endereço e dados bancários foram retirados (`[dado pessoal retirado]`). Não monte perfil, lista ou histórico de pessoa física a partir dos julgados; responda sobre a conduta, a tese e a decisão.
- FIDC, FII e demais fundos: comece por `indices/tema-fundos-investimento.md` do plugin do período (e pelas normas de fundos do índice por norma), em vez de varrer o ano.
- Fato anterior a 2023: a Resolução CVM vigente hoje (175, 160, 80...) não é a norma aplicada. Use a Instrução revogada da época (índice por norma, "fora do acervo") e diga qual regime o julgado aplicou.
- Achou um PAS: procure o termo de compromisso e o acórdão do CRSFN do mesmo processo no `processo-AAAA.md` de `julgados-pas` e de `julgados-tc-crsfn` (o ano é o do número do processo) antes de dizer como o caso terminou.
- Subíndice e arquivo grandes: a leitura única é cortada em silêncio perto de 40 KB. Todo subíndice termina em "Fim do subíndice."; se a leitura não terminou nessa linha, continue com `offset` a partir da linha do sumário no topo do arquivo.
- Pergunta sem data ou sobre fato anterior a 2002: veja também o índice das decisões antigas (`julgados-colegiado-2002-2008`, `indices/decisao-antiga-AAAA.md`); as decisões de 1978 a 2001 não têm ementa nem tema, só o título da pauta.
- Se o julgado não está no acervo, diga isso. Não cite processo, data ou resultado que não abriu.
