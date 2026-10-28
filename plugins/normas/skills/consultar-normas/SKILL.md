---
name: consultar-normas
description: Consulta o texto das normas da CVM do acervo (regulação de fundos, ofertas públicas, securitização, agente fiduciário) por artigo, com a data-base de cada norma. Use quando a pergunta depender do que diz uma resolução da CVM, antes de citar artigo, prazo, quórum ou dever, ou quando for preciso saber se um dispositivo está vigente ou foi alterado.
---

# Consultar normas

Acervo de normas do mercado de capitais em Markdown: um arquivo por norma, um título `## Art.` por artigo. Material não oficial; não substitui o Diário Oficial da União nem o site da CVM.

## Quando usar

Perguntas sobre regulação de fundos, ofertas públicas de valores mobiliários, securitização e agente fiduciário que dependam do texto de uma resolução da CVM. No piloto, o acervo tem só a Res. CVM 17 (agente fiduciário); o índice mostra o que existe.

## Como navegar

1. Abra `normas/indice.md` (nesta pasta do plugin, ao lado de `skills/`; em Claude Code, `${CLAUDE_PLUGIN_ROOT}/normas/indice.md`). `normas/normas.json` traz a mesma lista em JSON.
2. Pegue o caminho da norma no índice (ex.: `cvm/resolucoes/0017.md`) e abra o arquivo. Leia o frontmatter primeiro.
3. Vá ao artigo pelo título `## Art. N`. Parágrafos, incisos e alíneas estão como texto abaixo dele. O arquivo é pequeno o bastante para ler o artigo inteiro e os que ele cita.
4. O texto integral de cada ato alterador está em `normas/<órgão>/alteradoras/NNNN.md`. Use-o quando a pergunta for sobre o que um ato mudou.

## Regras

- Nunca responda de memória quando o arquivo existe. Abra o arquivo e cite dele.
- Cite no formato "art. 9º, § 2º, Res. CVM 175", com o dispositivo exato (artigo, parágrafo, inciso, alínea).
- Informe sempre a data-base: o campo `vigente_ate_ato` diz até qual ato alterador o texto foi atualizado (vazio = redação original). Diga, por exemplo, "texto atualizado até a Res. CVM 226/25". Para a data de publicação do ato, o frontmatter do arquivo do ato (`publicacao_dou`).
- Antes de citar, confira no frontmatter:
  - `situacao`: `revogada` ou `parcialmente-revogada` muda a resposta; dispositivo com a marca `(Revogado)` não está em vigor.
  - `aguarda_consolidado_oficial`: se `true`, há ato aplicado que o consolidado da CVM ainda não reflete; avise.
  - `historico_parcial`: se `true`, pode faltar ato alterador; avise.
  - `vigencia_inicio`: se existir, há dispositivo com duas redações; a que vem depois de "Vigente a partir de" só vale a partir dessa data. Diga qual vale na data da pergunta.
  - `incerteza`: se não estiver vazio, leia e repasse o que for relevante à pergunta.
- Se a norma ou o dispositivo não está no acervo, diga isso. Não preencha a lacuna com o que lembra e não cite artigo que não abriu.
- Pergunta que depende de outra norma (lei, instrução, resolução fora do índice): responda só a parte que o acervo cobre e diga o que ficou de fora.
- O texto é conversão do DOU e do consolidado da CVM e pode ter erro. Em parecer, contrato ou decisão, recomende conferir a fonte oficial (`fonte_original` e `fonte_consolidada` no frontmatter).
