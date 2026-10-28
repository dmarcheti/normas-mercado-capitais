---
name: consultar-normas
description: Consulta o texto das normas do acervo (todas as Resoluções CVM vigentes, Instruções CVM em vigor, Pareceres de Orientação, Ofícios-Circulares da CVM e leis e decretos do mercado de capitais) por artigo, com a data-base de cada norma. Use quando a pergunta depender do que diz uma norma ou orientação da CVM ou uma dessas leis, antes de citar artigo, prazo, quórum ou dever, ou quando for preciso saber se um dispositivo está vigente ou foi alterado.
---

# Consultar normas

Acervo de normas do mercado de capitais em Markdown: um arquivo por norma, um título `## Art.` por artigo. Material não oficial; não substitui o Diário Oficial da União nem o site da CVM.

## Quando usar

Perguntas sobre o mercado de capitais que dependam do texto de uma norma ou orientação da CVM, ou de uma lei ou decreto do recorte. Perímetro, em camadas:

1. Todas as Resoluções CVM vigentes (Estoque Regulatório da CVM, mais as editadas depois dele) e as 5 Instruções CVM ainda em vigor.
2. Os 41 Pareceres de Orientação e os Ofícios-Circulares editados desde 2022-01-01; os anteriores aparecem só como verbete no índice, sem texto.
3. Leis e decretos do mercado de capitais (Leis 6.385, 6.404, 4.728, 14.430, 11.101 e outras; ver o subíndice).

Fora do acervo: resoluções do CMN e do BCB, autorregulação (ANBIMA, B3) e julgados da CVM.

## Como navegar

Use só a ferramenta de ler arquivo da sua plataforma. Não use comando de shell (`cat`, `ls`, `grep`, `find`) nem execução de código para abrir os arquivos: em algumas plataformas eles não existem, e a leitura direta funciona em todas.

1. Leia `normas/indice.md`. O caminho é relativo à pasta do plugin, a que contém `skills/` e `normas/`; em Claude Code, `${CLAUDE_PLUGIN_ROOT}/normas/indice.md`. Ele é um resumo, com um subíndice por tipo.
2. Leia o subíndice do tipo da pergunta, em `normas/indices/`: `resolucoes.md` (agrupadas por tema; normas contábeis no fim), `instrucoes.md`, `pareceres-orientacao.md`, `oficios-circulares.md` (por superintendência), `leis.md` e `alteradoras.md`. Cada linha traz a ementa e o caminho do arquivo, relativo a `normas/`.
3. Leia o arquivo da norma (ex.: `normas/cvm/resolucoes/0017.md`). O frontmatter fica no começo do arquivo, entre as duas linhas `---`.
4. Norma em partes (Res. CVM 175 e Lei 6.404): o caminho leva a um `index.md`, com o frontmatter e a lista `## Partes`. Leia o `index.md` e depois a parte do dispositivo (ex.: `normas/cvm/resolucoes/0175/anexo-02.md` para FIDC; os suplementos estão em `suplementos.md`).
5. Resoluções, Instruções e leis: vá ao artigo pelo título `## Art. N`. Parágrafos, incisos e alíneas estão como texto abaixo dele. Leia o artigo inteiro e os que ele cita. Pareceres e Ofícios-Circulares não têm artigos: leia o documento e cite o item ou o trecho.
6. O texto integral de cada ato alterador está em `normas/cvm/alteradoras/`. Use-o quando a pergunta for sobre o que um ato mudou.

## Regras

- Nunca responda de memória quando o arquivo existe. Abra o arquivo e cite dele.
- Cite no formato "art. 9º, § 2º, Res. CVM 175", com o dispositivo exato (artigo, parágrafo, inciso, alínea).
- Informe sempre a data-base: o campo `vigente_ate_ato` diz até qual ato alterador o texto foi atualizado (vazio = redação original). Diga, por exemplo, "texto atualizado até a Res. CVM 226/25". Para a data de publicação do ato, o frontmatter do arquivo do ato (`publicacao_dou`). Norma sem histórico no acervo (lei, decreto e toda norma com `historico_parcial: true`): a data-base é `baixado_em`, a data em que o texto foi lido na fonte; diga, por exemplo, "texto do Planalto lido em 2026-10-28" ou "consolidado da CVM lido em 2026-10-28".
- Diga o nível de verificação (`nivel_verificacao`): `historico-conferido` (cada ato alterador aplicado e conferido), `consolidado-convertido` (consolidado da CVM convertido por script, sem conferência ato a ato), `ato-convertido` (texto do ato publicado; a norma não foi alterada ou a CVM não publica consolidado), `pdf-extraido` (texto tirado de PDF, sujeito a erro de extração), `compilado-planalto` (lei ou decreto no texto compilado do Planalto). Fora de `historico-conferido`, recomende conferir a fonte oficial antes de usar em parecer ou contrato.
- Antes de citar, confira no frontmatter:
  - `situacao`: `revogada` ou `parcialmente-revogada` muda a resposta; dispositivo com a marca `(Revogado)` não está em vigor. `nao-informada` (pareceres e ofícios): a CVM não publica a vigência deles; o documento pode interpretar norma já revogada, então confira se a norma que ele cita está vigente no acervo.
  - `aguarda_consolidado_oficial`: se `true`, há ato aplicado que o consolidado da CVM ainda não reflete; avise.
  - `historico_parcial`: se `true`, o acervo não tem o histórico ato a ato desta norma; o texto vale como o da fonte na data-base e o `incerteza` diz se algum ato alterador não está refletido.
  - `vigencia_inicio`: se existir, há dispositivo com duas redações; a que vem depois de "Vigente a partir de" só vale a partir dessa data. Diga qual vale na data da pergunta.
  - `incerteza`: se não estiver vazio, leia e repasse o que for relevante à pergunta.
- Se a norma ou o dispositivo não está no acervo, diga isso. Não preencha a lacuna com o que lembra e não cite artigo que não abriu.
- Pergunta que depende de norma fora do perímetro (CMN, BCB, ANBIMA, B3, julgados) ou de Ofício-Circular que só tem verbete: responda só a parte que o acervo cobre e diga o que ficou de fora.
- O texto é conversão do DOU e do consolidado da CVM e pode ter erro. Em parecer, contrato ou decisão, recomende conferir a fonte oficial (`fonte_original` e `fonte_consolidada` no frontmatter).
