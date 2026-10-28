---
name: consultar-normas
description: Consulta o texto das normas do acervo (resoluções da CVM sobre fundos, ofertas públicas, securitização, agente fiduciário, emissores, e leis do mercado de capitais) por artigo, com a data-base de cada norma. Use quando a pergunta depender do que diz uma resolução da CVM ou uma dessas leis, antes de citar artigo, prazo, quórum ou dever, ou quando for preciso saber se um dispositivo está vigente ou foi alterado.
---

# Consultar normas

Acervo de normas do mercado de capitais em Markdown: um arquivo por norma, um título `## Art.` por artigo. Material não oficial; não substitui o Diário Oficial da União nem o site da CVM.

## Quando usar

Perguntas sobre regulação de fundos, ofertas públicas de valores mobiliários, securitização, agente fiduciário, emissores, PLD e administração de carteiras que dependam do texto de uma resolução da CVM ou de uma lei do recorte (Lei 6.385, Lei 6.404, Lei 14.430, Código Civil arts. 1.368-C a 1.368-F e outras). O índice mostra o que existe.

## Como navegar

Use só a ferramenta de ler arquivo da sua plataforma. Não use comando de shell (`cat`, `ls`, `grep`, `find`) nem execução de código para abrir os arquivos: em algumas plataformas eles não existem, e a leitura direta funciona em todas.

1. Leia o arquivo `normas/indice.md`. O caminho é relativo à pasta do plugin, a que contém `skills/` e `normas/`; em Claude Code, `${CLAUDE_PLUGIN_ROOT}/normas/indice.md`. O índice lista as resoluções, as leis e os atos alteradores, com o caminho de cada arquivo.
2. Leia o arquivo da norma pelo caminho do índice (ex.: `normas/cvm/resolucoes/0017.md`). O frontmatter fica no começo do arquivo, entre as duas linhas `---`.
3. Norma em partes (Res. CVM 175 e Lei 6.404): o caminho do índice leva a um `index.md`, com o frontmatter e a lista `## Partes`. Leia o `index.md` e depois a parte do dispositivo (ex.: `normas/cvm/resolucoes/0175/anexo-02.md` para FIDC; os suplementos estão em `suplementos.md`).
4. Vá ao artigo pelo título `## Art. N`. Parágrafos, incisos e alíneas estão como texto abaixo dele. Leia o artigo inteiro e os que ele cita.
5. O texto integral de cada ato alterador está em `normas/cvm/alteradoras/NNNN.md`. Use-o quando a pergunta for sobre o que um ato mudou.

## Regras

- Nunca responda de memória quando o arquivo existe. Abra o arquivo e cite dele.
- Cite no formato "art. 9º, § 2º, Res. CVM 175", com o dispositivo exato (artigo, parágrafo, inciso, alínea).
- Informe sempre a data-base: o campo `vigente_ate_ato` diz até qual ato alterador o texto foi atualizado (vazio = redação original). Diga, por exemplo, "texto atualizado até a Res. CVM 226/25". Para a data de publicação do ato, o frontmatter do arquivo do ato (`publicacao_dou`). Lei (`tipo: lei`) não tem histórico no acervo: a data-base é `baixado_em`, a data em que o texto foi lido no Planalto; diga, por exemplo, "texto do Planalto lido em 2026-10-28".
- Antes de citar, confira no frontmatter:
  - `situacao`: `revogada` ou `parcialmente-revogada` muda a resposta; dispositivo com a marca `(Revogado)` não está em vigor.
  - `aguarda_consolidado_oficial`: se `true`, há ato aplicado que o consolidado da CVM ainda não reflete; avise.
  - `historico_parcial`: se `true`, pode faltar ato alterador; avise.
  - `vigencia_inicio`: se existir, há dispositivo com duas redações; a que vem depois de "Vigente a partir de" só vale a partir dessa data. Diga qual vale na data da pergunta.
  - `incerteza`: se não estiver vazio, leia e repasse o que for relevante à pergunta.
- Se a norma ou o dispositivo não está no acervo, diga isso. Não preencha a lacuna com o que lembra e não cite artigo que não abriu.
- Pergunta que depende de outra norma (lei, instrução, resolução fora do índice): responda só a parte que o acervo cobre e diga o que ficou de fora.
- O texto é conversão do DOU e do consolidado da CVM e pode ter erro. Em parecer, contrato ou decisão, recomende conferir a fonte oficial (`fonte_original` e `fonte_consolidada` no frontmatter).
