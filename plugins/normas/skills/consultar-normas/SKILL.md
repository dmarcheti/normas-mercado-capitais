---
name: consultar-normas
description: Consulta o texto das normas do mercado de capitais (Resoluções e Instruções CVM, Pareceres de Orientação, Ofícios-Circulares, leis e decretos, normas do CMN e do BCB, códigos e regulamentos da ANBIMA e da B3) por artigo e com a data-base, e os julgados da CVM e do CRSFN (PAS, decisões do Colegiado, termos de compromisso, acórdãos do CRSFN), com data, relator, resultado e dispositivos citados. Use quando a pergunta depender do que diz uma norma, antes de citar artigo, prazo, quórum ou dever, ou para saber se um dispositivo está vigente ou foi alterado. Use também quando a pergunta for sobre como a CVM ou o CRSFN decidiu: precedente, entendimento do Colegiado, multa ou absolvição em caso concreto, termo de compromisso, ou quais julgados aplicaram um artigo.
---

# Consultar normas e julgados

Acervo em Markdown, em duas pastas ao lado deste `SKILL.md`:

- `normas/`: um arquivo por norma, um título `## Art.` por artigo.
- `julgados/`: índices e fichas dos julgados da CVM e do CRSFN. O texto integral de cada julgado não está nesta pasta; a ficha traz o link dele.

Material não oficial. Não substitui o Diário Oficial da União nem os sites dos órgãos e entidades de origem.

Todos os caminhos abaixo são relativos à pasta que contém este `SKILL.md`. Não use `${CLAUDE_PLUGIN_ROOT}` nem caminho absoluto.

## Como ler os arquivos

Use só a ferramenta de ler arquivo da sua plataforma. Não use comando de shell (`cat`, `ls`, `grep`, `find`) nem execução de código para abrir os arquivos: em algumas plataformas eles não existem, e a leitura direta funciona em todas.

Arquivo grande é cortado em silêncio perto de 40 KB. Todo subíndice tem um sumário no topo e termina na linha "Fim do subíndice.". Se a leitura não terminou nessa linha, continue com `offset` e `limit`, a partir da linha indicada no sumário.

## Qual parte usar

- Pergunta sobre o que diz uma norma: siga "Normas".
- Pergunta sobre como a CVM ou o CRSFN decidiu, precedente ou caso concreto: siga "Julgados".
- Pergunta sobre como a CVM aplicou um artigo: ache o artigo em "Normas", depois os julgados que o citam em "Julgados".

## Normas

### Perímetro

1. Todas as Resoluções CVM vigentes (Estoque Regulatório da CVM, mais as editadas depois dele) e as 5 Instruções CVM ainda em vigor.
2. Os 41 Pareceres de Orientação e os Ofícios-Circulares editados desde 2022-01-01. Os anteriores aparecem só como verbete no índice, sem texto.
3. Leis e decretos do mercado de capitais (Leis 6.385, 6.404, 4.728, 14.430, 11.101 e outras; ver o subíndice).
4. Normas vigentes do CMN e do BCB que tocam mercado de capitais, fundos, securitização, crédito negociável, registro de ativos e recebíveis, investidores institucionais e instituições do mercado (ex.: Res. CMN 4.966, 2.907, 5.118, 4.994, 5.272), no texto compilado pelo BCB.
5. Autorregulação vigente da ANBIMA (códigos, regras e procedimentos, deliberações e orientações) e da B3 (regulamentos e manuais de normas).

Fora do acervo: normas do CMN e do BCB de política monetária, câmbio comercial, crédito rural, pagamentos de varejo, cooperativas, consórcios e prudencial.

### Como navegar

0. Pergunta sobre um produto (CRI, FIDC, FII): leia antes o mapa do produto, `normas/mapas/cri.md`, `fidc.md` ou `fii.md`. Ele lista as normas de cada camada, os dispositivos-chave e o caminho dos arquivos.
1. Leia `normas/indice.md`. É um resumo, com um subíndice por tipo.
2. Leia o subíndice do tipo da pergunta, em `normas/indices/`: `resolucoes.md` (agrupadas por tema; normas contábeis no fim), `instrucoes.md`, `pareceres-orientacao.md`, `oficios-circulares.md` (por superintendência), `leis.md`, `cmn.md` e `bcb.md` (por tipo; ao fim, os atos que só alteram normas do acervo, sem arquivo), `anbima.md`, `b3.md` e `alteradoras.md`. Cada linha traz a ementa e o caminho do arquivo, relativo a `normas/`.
3. Leia o arquivo da norma (ex.: `normas/cvm/resolucoes/0017.md`, `normas/cmn/resolucoes/4966.md`, `normas/bcb/circulares/3553.md`, `normas/autorregulacao/anbima/<slug>.md`). O frontmatter fica no começo do arquivo, entre as duas linhas `---`.
4. Norma em partes (Res. CVM 175 e Lei 6.404): o caminho leva a um `index.md`, com o frontmatter e a lista `## Partes`. Leia o `index.md` e depois a parte do dispositivo (ex.: `normas/cvm/resolucoes/0175/anexo-02.md` para FIDC; os suplementos estão em `suplementos.md`).
5. Resoluções, Instruções e leis: vá ao artigo pelo título `## Art. N`. Parágrafos, incisos e alíneas estão como texto abaixo dele. Leia o artigo inteiro e os que ele cita. Pareceres, Ofícios-Circulares e parte da autorregulação (manuais da B3, perguntas e respostas da ANBIMA) não têm artigos: leia o documento e cite o item, capítulo ou trecho.
6. O texto integral de cada ato alterador está em `normas/cvm/alteradoras/`. Use-o quando a pergunta for sobre o que um ato mudou.
7. Achado o dispositivo, veja quem o interpreta: leia `normas/indices/citacoes.md`, que aponta para o subíndice da norma (`normas/indices/citacoes/<id>.md` ou, nas normas grandes, `normas/indices/citacoes/<id>/index.md` e o arquivo do artigo). Ele lista os Pareceres de Orientação, Ofícios-Circulares e documentos da ANBIMA e da B3 que citam cada dispositivo, com o trecho. Abra os que tratam do ponto da pergunta e leia o documento inteiro antes de responder: o ofício ou a orientação pode mudar a resposta (quem envia, a partir de quando, se uma condição basta).
8. Para os julgados que aplicaram o dispositivo, siga "Julgados". Julgado não é norma.

### Regras

- Nunca responda de memória quando o arquivo existe. Abra o arquivo e cite dele.
- Cite no formato "art. 9º, § 2º, Res. CVM 175", com o dispositivo exato (artigo, parágrafo, inciso, alínea).
- Informe sempre a data-base: o campo `vigente_ate_ato` diz até qual ato alterador o texto foi atualizado (vazio = redação original). Diga, por exemplo, "texto atualizado até a Res. CVM 226/25". Para a data de publicação do ato, use o frontmatter do arquivo do ato (`publicacao_dou`). Norma sem histórico no acervo (lei, decreto e toda norma com `historico_parcial: true`): a data-base é `baixado_em`, a data em que o texto foi lido na fonte. Diga, por exemplo, "texto do Planalto lido em 2026-10-28" ou "consolidado da CVM lido em 2026-10-28".
- Diga o nível de verificação (`nivel_verificacao`):
  - `historico-conferido`: cada ato alterador aplicado e conferido;
  - `consolidado-convertido`: consolidado da CVM convertido por script, sem conferência ato a ato;
  - `ato-convertido`: texto do ato publicado; a norma não foi alterada ou a CVM não publica consolidado;
  - `pdf-extraido`: texto tirado de PDF, sujeito a erro de extração;
  - `ocr`: PDF sem camada de texto, reconhecido por OCR; erros pontuais de leitura são esperados;
  - `compilado-planalto`: lei ou decreto no texto compilado do Planalto.

  Fora de `historico-conferido`, recomende conferir a fonte oficial antes de usar em parecer ou contrato.
- Antes de citar, confira no frontmatter:
  - `situacao`: `revogada` ou `parcialmente-revogada` muda a resposta; dispositivo com a marca `(Revogado)` não está em vigor. `nao-informada` (pareceres e ofícios): a CVM não publica a vigência deles; o documento pode interpretar norma já revogada, então confira se a norma que ele cita está vigente no acervo.
  - `aguarda_consolidado_oficial`: se `true`, há ato aplicado que o consolidado da CVM ainda não reflete; avise.
  - `historico_parcial`: se `true`, o acervo não tem o histórico ato a ato desta norma; o texto vale como o da fonte na data-base e o `incerteza` diz se algum ato alterador não está refletido.
  - `vigencia_inicio`: se existir, há dispositivo com duas redações; a que vem depois de "Vigente a partir de" só vale a partir dessa data. Diga qual vale na data da pergunta.
  - `incerteza`: se não estiver vazio, leia e repasse o que for relevante à pergunta.
- CMN e BCB: o texto é a compilação do próprio BCB (que avisa não substituir o DOU), sem histórico nem conferência contra o DOU no acervo; a data-base é `baixado_em`. Cite como "art. 2º, Res. CMN 4.966" ou "Circular BCB 3.553". Ato só alterador do BCB não tem arquivo: a alteração já está no texto da norma alterada.
- Autorregulação (ANBIMA e B3): não é norma estatal; vincula só as instituições aderentes ao código ou participantes do ambiente da B3. Diga isso quando for relevante. Cite o documento pelo título, com o dispositivo e a data de início de vigência (`data`), ex.: "art. 10 do Código ANBIMA de Ofertas Públicas, vigente desde 2024-07-15". O texto é de titularidade da ANBIMA e da B3, para uso informativo; recomende conferir a versão no site da entidade (`fonte_original`).
- Se a norma ou o dispositivo não está no acervo, diga isso. Não preencha a lacuna com o que lembra e não cite artigo que não abriu.
- Pergunta que depende de norma fora do perímetro (CMN e BCB fora do recorte) ou de Ofício-Circular que só tem verbete: responda só a parte que o acervo cobre e diga o que ficou de fora.
- O texto é conversão do DOU, do consolidado da CVM, do compilado do Planalto, da compilação do BCB ou do PDF da entidade, e pode ter erro. Em parecer, contrato ou decisão, recomende conferir a fonte oficial (`fonte_original` e `fonte_consolidada` no frontmatter).

## Julgados

Julgados da CVM e do CRSFN: processos administrativos sancionadores (PAS) julgados, decisões do Colegiado da CVM desde 1978 (recursos, consultas, dispensas, registros), termos de compromisso aceitos e rejeitados e acórdãos do CRSFN em recursos contra a CVM.

Cada julgado tem duas peças:

- **ficha**, nesta pasta, em `julgados/fichas/`: resumo com id, tipo, processo, data, relator, resultado, ementa, tema, dispositivos citados e um trecho da decisão;
- **texto integral**, fora desta pasta, no GitHub: o link está no campo `texto_integral` da ficha.

### Julgado não é norma

Um julgado diz o que a CVM ou o CRSFN decidiu num caso, com os fatos daquele caso e a redação das normas na época. Ele não vincula como norma e pode ter sido reformado. Ao responder:

- separe o que diz a norma (use "Normas") do que o julgado decidiu;
- diga a data do julgamento e que a norma aplicada pode ter mudado desde então;
- PAS julgado pela CVM pode ter recurso ao CRSFN: procure o acórdão pelo número do processo antes de dizer que a condenação ficou.

### Como navegar

1. Leia `julgados/indice.md`: perímetro, contagens e lista dos subíndices.
2. Escolha o subíndice em `julgados/indices/`:
   - `norma-<id>.md`: julgados que citam cada dispositivo de uma norma (ex.: `norma-lei-6404.md`, `norma-cvm-res-175.md`; norma revogada, como `norma-fora-icvm-358.md`; a norma fora do acervo pouco citada fica no arquivo da família, como `norma-fora-outras-icvm.md`, com uma seção `## icvm-NNN` por norma). `normas-citadas.md` lista as normas citadas. É o caminho para "como a CVM aplicou o art. X";
   - `tema-<tema>.md`: por assunto (ex.: `tema-informacao-privilegiada.md`, `tema-securitizacao.md`);
   - `<tipo>-<ano>.md`: por tipo e ano (ex.: `pas-2024.md`);
   - `processo-AAAA.md`: por número de processo, com o PAS, o termo de compromisso e o acórdão do CRSFN do mesmo processo;
   - `decisao-antiga-AAAA.md` (ou `-s1`/`-s2`, `-t1` a `-t4`, no ano grande): uma linha por decisão de 1978 a 2001, com data e número da ata, processo e título.
3. Na linha do índice, leia a coluna Ficha. Ela traz o caminho relativo a `julgados/` (ex.: `fichas/pas/2023-08.md`). O arquivo tem várias fichas; a do julgado é a seção `## <id>`, com o `Id` da linha. O arquivo de ficha tem até 24 KB: uma leitura basta.
4. Pergunta de listagem ("quais julgados aplicaram o art. X") se responde pelo índice: cite id, processo, data e resultado de cada linha.

### Fluxo de resposta

1. Ache o julgado pelos índices.
2. Leia a ficha e responda por ela. O `resultado` e o `trecho` costumam bastar para dizer como o caso terminou.
3. Se a pergunta pedir o fundamento do voto, os fatos, o raciocínio do relator, a dosimetria da multa ou qualquer coisa que a ficha não traz, tente ler o `texto_integral` com a ferramenta de busca de página (`web_fetch` ou `WebFetch`). No texto integral, leia o Extrato e o Voto antes do Relatório.
4. Se a ferramenta recusar a URL (no claude.ai ela recusa URL que o usuário não colou na conversa), não busque o julgado em outro lugar nem responda de memória. Termine a resposta com o que a ficha permite afirmar e peça, com estas palavras: "Para eu ler o texto integral, cole este link na conversa: <url>". Troque `<url>` pelo `texto_integral` da ficha.
5. Com o link colado, leia o texto integral e complete a resposta.

Nunca responda de memória o que só o texto integral diria. Quando responder só pela ficha, diga que é pela ficha.

### Regras

- Cite assim: "PAS CVM nº 19957.011607/2024-20, j. 2025-05-27, rel. Dir. Fulano"; "Decisão do Colegiado de 2025-12-02, Proc. 19957.xxxxxx/AAAA-DV"; "Acórdão CRSFN nº N, sessão de AAAA-MM-DD". Diga o resultado (`resultado`) e, se houver, a multa como está no texto.
- `resultado` vazio na ficha: o julgado não tem resultado extraído ou a deliberação não o definiu. Não deduza do trecho; leia o texto integral.
- `trecho`: recorte de até 1.500 caracteres da decisão, que pode terminar em "[...]". Não é o julgado inteiro e pode omitir o ponto da pergunta.
- Ementa: a da ficha pode não ser oficial. O campo `ementa_fonte` do texto integral diz a origem: `cvm` ou `crsfn` é oficial; `titulo` foi montada do título; `extracao` foi escrita por modelo de linguagem. Sem ter lido o texto integral, não chame a ementa de oficial e confira no texto antes de usá-la como fundamento.
- `tema` vem de classificação automática. Confirme no texto antes de apoiar a resposta nele.
- `nivel_verificacao`: `html-convertido`, `pdf-extraido` ou `ocr` (este com erros pontuais de leitura). Recomende conferir a fonte oficial (campo `fonte_original` do texto integral) antes de usar em parecer ou peça.
- O índice por norma liga o dispositivo ao texto vigente hoje em `normas/`; o julgado aplicou a redação da época dos fatos. Norma marcada "fora do acervo" (Instruções e Deliberações revogadas) não tem texto no acervo.
- Fato anterior a 2023: a Resolução CVM vigente hoje (175, 160, 80...) não é a norma aplicada. Use a Instrução revogada da época (índice por norma, "fora do acervo") e diga qual regime o julgado aplicou.
- Achou um PAS: procure o termo de compromisso e o acórdão do CRSFN do mesmo processo no `processo-AAAA.md` (o ano é o do número do processo) antes de dizer como o caso terminou.
- FIDC, FII e demais fundos: comece por `julgados/indices/tema-fundos-investimento.md` e pelas normas de fundos do índice por norma, em vez de varrer o ano.
- Pergunta sem data ou sobre fato anterior a 2002: veja também `julgados/indices/decisao-antiga-AAAA.md`. As decisões de 1978 a 2001 não têm ementa nem tema, só o título da pauta.
- Dados pessoais: CPF, documento, endereço e dados bancários foram retirados (`[dado pessoal retirado]`). Não monte perfil, lista ou histórico de pessoa física a partir dos julgados; responda sobre a conduta, a tese e a decisão.
- Se o julgado não está no acervo, diga isso. Não cite processo, data ou resultado que não abriu. A ausência no índice não prova que o julgado não exista.
