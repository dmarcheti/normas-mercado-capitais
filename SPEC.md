# SPEC: formato do acervo (v0.5.0)

Versão semântica. Campos novos opcionais = menor; campo obrigatório novo ou mudança de significado = maior.

## Estrutura

- Cada norma é um arquivo Markdown sob `plugins/normas/normas/`, na pasta do seu tipo (tabela abaixo). Nomes sem acento, em minúsculas.

| `tipo` | `orgao` | `id` | Arquivo (sob `plugins/normas/normas/`) |
|---|---|---|---|
| `resolucao` | `cvm` | `cvm-res-N` | `cvm/resolucoes/NNNN.md` (ex.: `0017.md`) |
| `instrucao` (v0.3.0) | `cvm` | `cvm-instr-N` | `cvm/instrucoes/NNNN.md` |
| `parecer-orientacao` (v0.3.0) | `cvm` | `cvm-po-N` | `cvm/pareceres-orientacao/NNNN.md` |
| `oficio-circular` (v0.3.0) | `cvm` | `cvm-<slug>` | `cvm/oficios-circulares/<pasta>/<slug>.md` |
| `lei` | `federal` | `lei-N` | `leis/lei-NNNNN.md` (5 dígitos) |
| `decreto` (v0.3.0) | `federal` | `decreto-N` | `leis/decreto-NNNNN.md` (5 dígitos) |
| `lei-complementar` (v0.3.0) | `federal` | `lcp-N` | `leis/lcp-NNN.md` (3 dígitos) |
| `resolucao-cmn` (v0.4.0) | `cmn` | `cmn-res-N` | `cmn/resolucoes/NNNN.md` |
| `resolucao-bcb` (v0.4.0) | `bcb` | `bcb-res-N` | `bcb/resolucoes/NNNN.md` |
| `resolucao-conjunta` (v0.4.0) | `bcb` | `bcb-resc-N` | `bcb/resolucoes-conjuntas/NNNN.md` |
| `circular` (v0.4.0) | `bcb` | `bcb-circ-N` | `bcb/circulares/NNNN.md` |
| `carta-circular` (v0.4.0) | `bcb` | `bcb-cc-N` | `bcb/cartas-circulares/NNNN.md` |
| `instrucao-normativa-bcb` (v0.4.0) | `bcb` | `bcb-in-N` | `bcb/instrucoes-normativas/NNNN.md` |
| `codigo-autorregulacao`, `regras-procedimentos`, `regulamento`, `manual`, `glossario`, `orientacao-autorregulacao` (v0.4.0) | `anbima` ou `b3` | `<orgao>-<slug>` | `autorregulacao/<orgao>/<slug>.md` |

- Ofício-circular: `<slug>` é o nome da página do ofício no site da CVM, sem `.html` (ex.: `oc-sse-0326`, `occ-sin-sse-0125`, `oc-anual-2026-sre`), só minúsculas, dígitos e hífen; o id é `cvm-` + slug (`cvm-oc-sse-0326`). `<pasta>` é a pasta do ofício no site da CVM (`sin`, `sep`, `sse1`, `smi-sin`...). O `numero` é o número do ofício (inteiro), sem regra de coerência com o id, porque se repete entre superintendências e anos.
- CMN e BCB (camada 4, v0.4.0): NNNN é o número com 4 dígitos. `resolucao-cmn` inclui as resoluções do CMN até a 4.838, publicadas só como "Resolução". A Resolução Conjunta fica em `bcb`, com os órgãos signatários no `incerteza`.
- Autorregulação (camada 5, v0.4.0): `<slug>` só com minúsculas, dígitos e hífen, sem acento, até 80 caracteres; o id é `<orgao>-` + nome do arquivo sem `.md` (`anbima-codigo-administracao-gestao`). Não há número. O `autorregulacao/README.md` (fonte e data-base de cada documento, uso informativo, direitos da ANBIMA e da B3) não é norma.
- Norma em partes (norma longa, como a Res. CVM 175): uma pasta `<número com 4 dígitos>/` com `index.md` e as partes. O `index.md` tem o frontmatter completo e uma seção `## Partes` com uma lista `- arquivo.md`, na ordem do texto. Cada parte não tem frontmatter e abre com `# título` (ex.: `# Anexo Normativo I`); os artigos continuam como `## Art.`. O mesmo número de artigo pode se repetir em partes diferentes.
- Leis (v0.2.0), decretos e leis complementares (v0.3.0) ficam em `plugins/normas/normas/leis/` (sem nível de órgão), em arquivo único ou, em partes, na pasta com o mesmo nome (`lei-NNNNN/index.md`, `decreto-NNNNN/index.md`). Código Civil: só os artigos do recorte (`lei-10406.md`, arts. 1.368-C a 1.368-F), descrito em `incerteza`.
- Atos que alteram normas ficam em `plugins/normas/normas/<órgão>/alteradoras/<número com 4 dígitos>.md`, com o texto do ato.
- Os atos só alteradores do CMN e do BCB (v0.4.0) não têm arquivo nem histórico: o texto compilado pelo BCB já reflete a alteração, e o ato entra como verbete no subíndice da norma alterada.
- Cada artigo começa em linha própria com um heading de nível 2: `## Art. 1º`, `## Art. 10`, `## Art. 12-A`. Parágrafos, incisos e alíneas ficam como texto abaixo do artigo.
- O validador não exige `## Art.`: pareceres de orientação e ofícios-circulares não têm artigos. Quando a norma tem artigos, a regra acima vale.
- Dispositivo revogado permanece com a marca `(Revogado)` (ou `(Revogado pela Resolução CVM nº X)`).
- Cada ato alterador é um commit; autor e data do commit são a identidade de replay e a data de publicação no DOU.

## Frontmatter

Campos obrigatórios, nesta ordem:

| Campo | Conteúdo |
|---|---|
| `id` | identificador estável, ex.: `cvm-res-17`, `lei-6404` |
| `orgao` | `cvm`, `federal`, `cmn`, `bcb`, `anbima` ou `b3`, conforme o tipo (tabela da Estrutura) |
| `tipo` | um dos tipos da tabela da Estrutura |
| `numero` | número do ato (inteiro); vazio na autorregulação |
| `data` | data do ato, AAAA-MM-DD; na autorregulação, a data de início de vigência ou a data da versão |
| `publicacao_dou` | data de publicação no DOU, AAAA-MM-DD; vazio na autorregulação |
| `ementa` | ementa oficial |
| `situacao` | `vigente`, `revogada`, `parcialmente-revogada` ou `nao-informada` (só parecer e ofício) |
| `versao_texto` | `consolidado` ou `original` |
| `vigente_ate_ato` | número do último ato alterador aplicado (data-base do texto); vazio em lei, decreto, lei complementar, CMN, BCB e autorregulação |
| `aguarda_consolidado_oficial` | `true` se há ato aplicado ainda não refletido no consolidado da CVM |
| `historico_parcial` | `true` se o histórico de atos não está completo |
| `fonte_original` | URL da redação original |
| `fonte_consolidada` | URL do texto consolidado usado na conferência |
| `sha256_fonte` | hash do arquivo da fonte consolidada |
| `baixado_em` | AAAA-MM-DD do download da fonte (data-base do texto); em lei é a data-base do texto |
| `verificado_em` | AAAA-MM-DD da última conferência contra o consolidado (nos textos por script, a data da geração) |
| `incerteza` | texto livre; vazio quando não há |

Opcionais, depois de `incerteza`, nesta ordem:

- `vigencia_inicio` (AAAA-MM-DD), obrigatório quando o texto tem bloco "vigente a partir de" (vigência diferida: o dispositivo traz as duas redações, a atual e a futura, esta com a data).
- `nivel_verificacao` (v0.3.0): como o texto foi obtido e conferido. Valores:
  - `historico-conferido`: texto montado pelo replay dos atos (um commit por ato) e conferido contra o consolidado da CVM pelo teste final;
  - `consolidado-convertido`: conversão do consolidado da CVM (DOCX, DOC ou HTM), sem histórico de atos; a conferência é só da conversão;
  - `ato-convertido`: conversão do texto do ato (DOCX, DOC ou HTM), para norma nunca alterada ou sem consolidado;
  - `pdf-extraido`: texto extraído do PDF da CVM (só há PDF); sujeito a erro de extração, descrito em `incerteza`;
  - `ocr` (v0.3.1): texto reconhecido por OCR (Vision, macOS) de PDF sem camada de texto; erros pontuais de reconhecimento são esperados; a confiança média e a mínima por página ficam em `incerteza`;
  - `compilado-planalto`: texto compilado do Planalto (leis, decretos e leis complementares), conferido pelo `scripts/teste_lei.py`.
  - `html-convertido` (v0.5.0): conversão de página HTML da fonte; nesta versão, só em julgados (seção Julgados).

Regras de valor (verificadas por `scripts/validar.py`):

- Chaves na ordem da tabela, sem campo repetido nem desconhecido; um valor por linha (`chave: valor`), sem listas.
- `numero` inteiro (vazio só na autorregulação). `orgao`, `id` e nome do arquivo conforme o tipo (tabela da Estrutura); `tipo` fora da tabela é erro, e a mensagem lista os aceitos. Em ofício-circular, o `id` é `cvm-` + nome do arquivo sem `.md`. Em norma em partes o arquivo é `index.md`, dentro da pasta com o nome acima (sem `.md`).
- Em lei, decreto e lei complementar, `vigente_ate_ato` fica vazio (não há atos aplicados em sequência); `historico_parcial: true`; `aguarda_consolidado_oficial: false`.
- CMN e BCB (v0.4.0): `situacao: vigente`; `versao_texto: consolidado` (texto compilado pelo BCB) ou `original` (só o PDF do ato); `vigente_ate_ato` vazio; `historico_parcial: true`; `aguarda_consolidado_oficial: false`; `publicacao_dou` do campo DOU da API do BCB (sem DOU informado, repete `data`, com aviso no `incerteza`). O arquivo fica na pasta do órgão e do tipo (a pasta `resolucoes/` é dividida com a CVM: `cmn/resolucoes/`, `bcb/resolucoes/`).
- Autorregulação (v0.4.0, `anbima` e `b3`): `numero` e `publicacao_dou` vazios (só nela); `data` é a data de início de vigência ou a data da versão; `situacao: vigente`; `versao_texto: original`; `vigente_ate_ato` vazio; `historico_parcial: true`; `aguarda_consolidado_oficial: false`; `nivel_verificacao: pdf-extraido` (obrigatório). O arquivo fica em `autorregulacao/<orgao>/`. A `ementa` é o título do documento na página da entidade (sem número, é ela que nomeia o documento no índice).
- Datas em AAAA-MM-DD válidas (`publicacao_dou` vazio só na autorregulação); `aguarda_consolidado_oficial` e `historico_parcial` são `true` ou `false`.
- `situacao` ∈ `vigente`, `revogada`, `parcialmente-revogada`, `nao-informada`; `versao_texto` ∈ `consolidado`, `original`. `nao-informada` só em `parecer-orientacao` e `oficio-circular`: a CVM não publica a vigência deles.
- `vigente_ate_ato`, nos tipos da CVM: número do último ato aplicado (inteiro, ex.: `226`) ou vazio quando só a redação original foi aplicada.
- `nivel_verificacao`, quando presente, é um dos seis primeiros valores acima (`html-convertido` é só dos julgados).
- `sha256_fonte`: 64 caracteres hexadecimais. `ementa`, `fonte_original` e `fonte_consolidada` não ficam vazios.

## Pastas validadas e índices

- O validador (`scripts/validar.py <raiz>`) lê as normas de `resolucoes/`, `instrucoes/`, `pareceres-orientacao/`, `oficios-circulares/<pasta>/` e `leis/` e, desde a v0.4.0, de `cmn/resolucoes/`, `bcb/{resolucoes,resolucoes-conjuntas,circulares,cartas-circulares,instrucoes-normativas}/` e `autorregulacao/{anbima,b3}/`. Os atos alteradores (`alteradoras/`), os índices e o `autorregulacao/README.md` não seguem o schema.
- O índice (`scripts/indice.py`) gera, na raiz `plugins/normas/normas/`: `indice.md` (resumo: aviso, perímetro, contagem por tipo e link para cada subíndice), `normas.json` (todas as normas, com `tipo` e, na resolução do Estoque Regulatório, `grupo`) e os subíndices em `indices/`: `resolucoes.md` (por grupo temático do Estoque Regulatório da CVM, lido de `fontes/acervo.json`, chave `estoque_regulatorio.grupos`; normas contábeis por último), `instrucoes.md`, `pareceres-orientacao.md`, `oficios-circulares.md` (por pasta, data decrescente; os ofícios de `fontes/acervo.json` sem arquivo no acervo entram como verbete, com link e sem texto), `leis.md` (leis, leis complementares e decretos), `cmn.md` e `bcb.md` (v0.4.0; uma seção por tipo e, ao fim, "Atos só alteradores, sem arquivo": os atos de `fontes/perimetro-camada4.json` com `decisao: alteradora` cujo `altera` aponta para norma com arquivo no acervo, com a ementa e o link `url_pagina` de `fontes/acervo-bcb.json`; sem esses arquivos, a seção não sai), `anbima.md` e `b3.md` (v0.4.0; uma seção por tipo) e `alteradoras.md`. O `indice.md` descreve o perímetro em 5 camadas: CVM (1 e 2), leis federais (3), CMN e BCB no texto compilado pelo BCB (4) e autorregulação da ANBIMA e da B3, de titularidade delas e de uso informativo (5). Subíndice vazio não é gerado. A saída não tem data de geração; `--verificar` falha se algum arquivo estiver defasado ou se sobrar em `indices/` subíndice que não é mais gerado.
- Citações (v0.5.0): o índice também gera `indices/citacoes/<id>.md`, o índice reverso de cada norma do acervo citada por um documento de interpretação do acervo (parecer de orientação, ofício-circular e autorregulação): uma seção por artigo (`## art. 90`, `## Anexo II, art. 2º`, a parte geral primeiro) e, em cada linha, o dispositivo completo, o título curto do documento, o tipo, a data, o caminho relativo a `normas/` e um trecho de até 160 caracteres, cortado em palavra. Se o subíndice de uma norma passar de 40 KB, ele vira a pasta `indices/citacoes/<id>/`, com `index.md` (parte, artigo, número de citações e arquivo de cada artigo) e um arquivo por artigo, de nome estável e ordenável (`art-0155.md`, `anexo-ii-art-0002.md`, `art-1368-c.md`); `indices/citacoes.md` aponta para o arquivo ou para o `index.md` da pasta. A extração é por script (`scripts/citacoes.py`, regex), sem conferência manual; norma fora do acervo e autocitação não entram, e o par (documento, dispositivo) não se repete. `indices/citacoes.md` lista as normas citadas com o número de documentos e de citações. Sem citação, nada é gerado. O `indice.md` aponta o `indices/citacoes.md` e avisa que os julgados ficam nos plugins `julgados-*`. `--verificar` cobre `indices/citacoes/` e as subpastas (defasado ou sobra = falha).

## Norma em partes: regras do validador

- O `index.md` tem exatamente uma seção `## Partes`; cada item da lista é um arquivo existente na pasta; todo `.md` da pasta (fora o `index.md`) está na lista.
- Parte sem frontmatter e com `# título` na primeira linha não vazia.
- A checagem de vigência diferida olha o texto do `index.md` mais o de todas as partes.
- O texto da norma, para os testes, é o `index.md` seguido das partes na ordem da lista.

## Leis

Texto do compilado do Planalto, na data-base `baixado_em`. As notas do Planalto ("(Redação dada pela Lei nº ...)", "(Incluído pela ...)") ficam no texto, porque não há histórico de commits que as substitua; o texto tachado (revogado ou substituído) sai. Não há gabarito independente: o teste (`scripts/teste_lei.py`) confere a conversão, com os artigos em ordem crescente e sem lacuna e o texto da norma igual ao texto visível não tachado do HTML. Num recorte (Código Civil), o HTML é comparado só no trecho da norma.

## Divergências aceitas

Quando o consolidado da CVM difere do ato por ajuste editorial dele (ex.: "sete" no ato, "7 (sete)" no consolidado), a diferença do teste final pode ser aceita em `fontes/divergencias-aceitas.json`, uma entrada por diferença: `{"id", "dispositivo", "consolidado", "norma", "motivo", "ref"}`. A entrada tira do diff o par de linhas que casa exatamente (`consolidado` e `norma` são as linhas normalizadas; vazio = só um lado). Regras:

- entrada sem par no diff é erro ("aceita não usada");
- o dispositivo (ex.: `Art. 9º, caput`) tem de aparecer no `incerteza` da norma;
- o teste imprime quantas diferenças foram aceitas.

## Teste final: tabelas

O teste final compara o número de tabelas da norma com o do consolidado (diferença é erro) e as células não vazias de cada tabela; células vazias e linhas só de separador não contam. Anotação de alteração do consolidado dentro de uma tabela ("Alínea b.1.10 incluída pela...") não parte a tabela, e tabela sem nenhuma célula com texto depois da normalização (toda riscada ou revogada) não conta.

## Teste por ato

O teste por ato (`scripts/teste_ato.py`) lê o diff do commit com `git show --diff-algorithm=histogram` (o Myers padrão realinha mal blocos inalterados) e ignora os itens `- arquivo.md` da lista `## Partes` de um `index.md`.

## Vigência diferida

O dispositivo traz a redação atual e, depois dela, a futura, aberta por uma linha que começa com `Vigente a partir de` (pode vir em citação `>` ou em negrito), seguida da data. O frontmatter ganha `vigencia_inicio` com essa data. O validador rejeita o bloco sem `vigencia_inicio` válido. Se houver mais de um bloco com datas diferentes, use a data do primeiro e descreva os demais em `incerteza` (limite até a v0.3.0).

## Marcas no texto

- Revogado: `(Revogado)` ou `(Revogado pela Resolução CVM nº X)`. O consolidado da CVM usa `REVOGADO`, também com travessão depois do dispositivo (`§ 4º - REVOGADO`, `Seção I - REVOGADA`, `CAPÍTULO III - REVOGADO`, `SUPLEMENTO H - REVOGADO`, `Art. 17 - REVOGADO`); os testes tratam as formas como iguais.
- Notas de alteração do consolidado ("Caput com redação dada pela...", "(NR)") não entram no texto da norma; o histórico de commits as substitui.
- Redação antiga tachada no consolidado é descartada na comparação.

## Julgados

Desde a v0.5.0 o acervo tem julgados: decisões da CVM (PAS, termos de compromisso, itens do Colegiado e decisões antigas) e acórdãos do CRSFN em recursos contra decisões da CVM. **Julgado não é norma**: diz o que se decidiu num caso concreto, com a redação das normas da época, e não vincula como norma. Os julgados ficam fora de `plugins/normas/`, em plugins próprios, e não entram no `normas.json` nem nos índices das normas.

### Plugins e pastas

Cada julgado mora no plugin do seu tipo e período, escolhido por uma função única, `plugin_do_julgado(tipo, ano)`, em `scripts/julgados_comum.py` (cinco plugins, `PLUGINS_JULGADOS`; o corte saiu do tamanho medido no piloto):

| Plugin | Conteúdo |
|---|---|
| `plugins/julgados-pas/` | PAS julgados pela CVM |
| `plugins/julgados-tc-crsfn/` | termos de compromisso (aceitos e rejeitados) e acórdãos do CRSFN |
| `plugins/julgados-colegiado-2002-2008/` | demais itens do Colegiado de 2002 a 2008 e as decisões antigas (1978 a 2001) |
| `plugins/julgados-colegiado-2009-2015/` | idem, 2009 a 2015 |
| `plugins/julgados-colegiado-2016-2026/` | idem, 2016 em diante |

Em cada plugin: `.claude-plugin/plugin.json`, `skills/consultar-julgados/SKILL.md` (cópia idêntica nos cinco; um teste confere) e a entrada no `.claude-plugin/marketplace.json` da raiz, `julgados/indice.md`, `julgados/indices/` e os julgados, um arquivo por julgado:

| `tipo` | `orgao` | `id` | Arquivo (sob `julgados/`) |
|---|---|---|---|
| `pas` | `cvm` | `cvm-pas-<proc>` | `cvm/pas/AAAA/<proc>.md` |
| `termo-compromisso` | `cvm` | `cvm-col-AAAAMMDD-dNNNN` (ou `cvm-tc-<proc>-AAAAMMDD`, sem item do Colegiado) | `cvm/colegiado/AAAA/<id sem cvm->.md` |
| `decisao-colegiado` | `cvm` | `cvm-col-AAAAMMDD-dNNNN` | `cvm/colegiado/AAAA/col-AAAAMMDD-dNNNN.md` |
| `decisao-antiga` | `cvm` | `cvm-dec-AAAA[-NNN]` | `cvm/decisoes-antigas/AAAA[-NNN].md` |
| `acordao-crsfn` | `crsfn` | `crsfn-<recurso ou proc>` | `crsfn/AAAA/<slug>.md` |

- `<proc>`: número do processo em minúsculas, só dígitos, letras e hífen (`19957-011607-2024-20`, `rj2015-1234`, `sp2010-0077`). Repetição do mesmo processo no mesmo tipo: sufixo `-2`, `-3`.
- `AAAA` é o ano da sessão ou da decisão, igual ao ano de `data`.
- Nenhum nome de pessoa física em `id`, nome de arquivo, `ementa` (de qualquer `ementa_fonte`) ou linha de índice. Na `ementa` oficial (`cvm`, `crsfn`), o nome da lista positiva do julgado (acusados dos dados abertos, compromitentes e proponentes, "Acusado(s):" do corpo, partes do título, lista em caixa alta antes do travessão) vira `[pessoa física]` só no frontmatter; o corpo guarda a ementa como publicada em `## Ementa`, logo depois do `# título`, e o `incerteza` registra "nomes de pessoa física omitidos da ementa do frontmatter; ementa integral na seção Ementa".

### Frontmatter dos julgados

Campos, todos obrigatórios, nesta ordem; um valor por linha (`chave: valor`), sem listas YAML:

| Campo | Conteúdo |
|---|---|
| `id` | conforme o tipo (tabela acima) |
| `orgao` | `cvm`; `crsfn` no `acordao-crsfn` |
| `tipo` | `pas`, `termo-compromisso`, `decisao-colegiado`, `decisao-antiga` ou `acordao-crsfn` |
| `classe` | só no Colegiado: `recurso`, `consulta`, `dispensa`, `registro`, `normativo`, `reconsideracao`, `incidente-pas`, `multa-cominatoria`, `institucional` ou `outros` (pelo título); obrigatória em `decisao-colegiado` |
| `processo` | número(s) do processo como publicado(s), separados por `; `, sem nome de parte; vazio só em `decisao-antiga` e no item do Colegiado (`decisao-colegiado` ou `termo-compromisso` com id `cvm-col-`) sem processo publicado (agenda regulatória, plano de auditoria, apresentação, alteração de termo); nos TCs de 2004–2006 o número do PAS vem do título ("PAS CVM Nº 27/99" → `27/99`) |
| `nup` | NUP normalizado (`19957-011607-2024-20`) ou vazio |
| `rito` | `ordinario`, `simplificado` ou vazio |
| `data` | data da sessão, reunião ou decisão, AAAA-MM-DD |
| `relator` | nome ou sigla, como publicado, ou vazio |
| `resultado` | lista fechada por tipo (abaixo) ou vazio |
| `ementa` | ementa da fonte ou montada (ver `ementa_fonte`) |
| `ementa_fonte` | `cvm` (publicada pela CVM), `crsfn` (publicada pelo CRSFN), `extracao` (extraída por LLM, não oficial) ou `titulo` (montada por script a partir do título da CVM, sem o trecho das partes) |
| `tema` | tema da lista fechada ou vazio (até a extração) |
| `tema_fonte` | `script` ou `extracao`; vazio só quando `tema` é vazio |
| `normas_citadas` | ids do acervo ou `fora:<rotulo>`, separados por `; `, ou vazio |
| `dispositivos_citados` | `<id ou fora:rotulo> [<parte> ]art. N[, § N \| , parágrafo único][, inciso X][, alínea y]`, separados por `; `, ou vazio (ex.: `cvm-res-175 Anexo II art. 2º, inciso XII, alínea d; lei-6404 art. 155, § 1º`) |
| `fonte_original` | URL da fonte |
| `sha256_fonte` | hash do arquivo da fonte (64 caracteres hexadecimais) |
| `baixado_em` | AAAA-MM-DD do download |
| `nivel_verificacao` | `html-convertido`, `pdf-extraido` ou `ocr` |
| `incerteza` | texto livre; vazio quando não há (ex.: "recurso ao CRSFN") |

`resultado`, lista fechada:

- `pas` e `acordao-crsfn`: `condenacao`, `absolvicao`, `parcial` (condenação e absolvição no mesmo processo), `extincao`, `arquivamento`, `outro`;
- `termo-compromisso`: `aceito`, `rejeitado`, `outro`;
- `decisao-colegiado` e `decisao-antiga`: `deferido`, `indeferido`, `provido`, `nao-provido`, `parcial`, `conhecimento`, `outro`.

Como o valor é escolhido (v1.1.0):

- O resultado sai da deliberação do Colegiado, nunca da proposta da área técnica ou do Comitê, nem do voto do relator; julgamento suspenso (vista, adiamento, retirada de pauta) ou sem deliberação fica com `resultado` vazio.
- Decisão do Colegiado: `deferido`/`indeferido` para pedido (dispensa, registro, autorização, prazo); `provido`/`nao-provido` para recurso, inclusive o recurso contra indeferimento da área técnica, e para pedido de reconsideração em que o Colegiado reformou ou manteve a decisão; `parcial` para pedido ou recurso atendido em parte; `conhecimento` quando não conheceu do recurso ou só tomou conhecimento; `outro` para o que não cabe na lista (consulta que fixa entendimento, norma aprovada, diligência).
- Acórdão do CRSFN: o que fica valendo depois do acórdão. Recurso de ofício negado mantém a absolvição da CVM; com recurso voluntário negado no mesmo acórdão, o resultado é `parcial`.

Citações (`normas_citadas` e `dispositivos_citados`): o id é o do `plugins/normas/normas/normas.json`; norma fora do acervo usa `fora:<rotulo>`, com o rótulo do `scripts/citacoes.py` (`icvm-358`, `res-cvm-35`, `deliberacao-cvm-538`, `lei-7940`, `lcp-105`, `res-cmn-2689` etc.). `fora:` com rótulo de norma que está no acervo é erro. A parte da norma em partes vai antes do artigo (`Anexo II`, `Suplemento A`); na parte geral, nada.

### Corpo

`# <título da fonte>` na primeira linha não vazia e, depois, uma seção `## ` por peça, na ordem da fonte: `## Ementa` (a ementa publicada, quando a do frontmatter omite nomes; no `acordao-crsfn`, a do acórdão), `## Extrato`, `## Relatório`, `## Voto`, `## Declaração de voto`, `## Manifestação da área técnica`, `## Parecer do Comitê de Termo de Compromisso`, `## Termo de compromisso`, `## Decisão`; a peça sem cabeçalho reconhecível fica em `## Texto`. No PDF anual de decisões antigas sem divisão possível, uma seção `## ` por decisão. Texto como a fonte publica, sem reescrita; dado pessoal cortado (CPF, RG, endereço, e-mail, telefone, data de nascimento, dados bancários e a qualificação pessoal do termo de compromisso) fica marcado `[dado pessoal retirado]`. O corte é conservador: na qualificação de uma parte, o endereço (inclusive o comercial e o da sede, quando vem junto do da pessoa), o e-mail e o número de documento saem sempre, mesmo quando a pessoa é jurídica ou o dado é institucional. Isso evita deixar escapar o endereço de uma pessoa física que aparece perto de um CNPJ. Na auditoria, esse corte a mais não conta como erro. Nome, cargo, CNPJ e o endereço de sede citado fora da qualificação ficam.

### Validação e índices dos julgados

- `python3 scripts/validar.py plugins/julgados-<plugin>/julgados` (raiz chamada `julgados`, ou `--julgados`) valida cada `.md` sob a raiz, fora `indice.md` e `indices/`: ordem e conjunto de chaves, vazios, coerência entre `tipo`, `orgao`, `id`, `data` e caminho, datas, listas fechadas, formato e existência das citações (contra o `normas.json`; `--normas-json` muda o caminho; sem o arquivo, só o formato), `sha256_fonte` e o corpo (`# ` e ao menos um `## `). A CI valida cada `plugins/julgados-*/julgados` que existir.
- `python3 scripts/indice.py` gera, em cada `plugins/julgados-*/julgados/`: `indice.md` (aviso de que julgado não é norma, perímetro do plugin, contagem por tipo e ano, links), `indices/<tipo>-<ano>.md`, `indices/tema-<tema>.md` (tema sem acento, em kebab-case) e `indices/norma-<id>.md` (`norma-fora-<rotulo>.md` fora do acervo; a norma fora do acervo citada por menos de 10 julgados fica em `norma-fora-outras-<família>.md`, uma seção `## <rotulo>` por norma, para o plugin não passar de 5.000 arquivos): o índice reverso, uma seção por artigo, com link relativo para a norma no plugin `normas` e a nota "texto vigente hoje; o julgado aplicou a redação da época" (fora do acervo: "fora do acervo"); a norma citada sem dispositivo fica numa seção própria. A linha do índice traz tipo, processo, data, resultado, tema, ementa e arquivo, nunca o título (que pode ter nome de pessoa). Sem julgados, nada é gerado e o `--verificar` passa; com eles, defasado ou sobra = falha.

## Histórico de versões

- v0.5.0: julgados (seção Julgados): plugins `julgados-*`, tipos `pas`, `termo-compromisso`, `decisao-colegiado`, `decisao-antiga` e `acordao-crsfn`, órgão `crsfn`, frontmatter próprio, listas fechadas de `resultado`, `ementa_fonte` (com `titulo`) e `tema_fonte`, citações por id do acervo ou `fora:<rotulo>`, corpo com seções `##` e a marca `[dado pessoal retirado]`; valor `html-convertido` em `nivel_verificacao` (só julgados); validador e índices dos julgados; índice reverso de citações no acervo de normas (`indices/citacoes/`). Julgado não é norma.
- v0.4.0: camada 4 (CMN e BCB: tipos `resolucao-cmn`, `resolucao-bcb`, `resolucao-conjunta`, `circular`, `carta-circular` e `instrucao-normativa-bcb`; órgãos `cmn` e `bcb`) e camada 5 (autorregulação: tipos `codigo-autorregulacao`, `regras-procedimentos`, `regulamento`, `manual`, `glossario` e `orientacao-autorregulacao`; órgãos `anbima` e `b3`; `numero` e `publicacao_dou` vazios; id pelo slug); pastas novas no validador; subíndices `cmn.md`, `bcb.md` (com os atos só alteradores, sem arquivo), `anbima.md` e `b3.md`; perímetro do índice em 5 camadas; aviso generalizado.
- v0.3.1: valor `ocr` em `nivel_verificacao`; `baixado_em` é a data do download da fonte e `verificado_em` a da geração.
- v0.3.0: tipos `instrucao`, `parecer-orientacao`, `oficio-circular`, `decreto` e `lei-complementar`; `situacao: nao-informada` (só parecer e ofício); campo opcional `nivel_verificacao`; `## Art.` não é exigido; índice dividido em resumo e subíndices (`indices/`), com resoluções por grupo do Estoque Regulatório e verbetes de ofícios sem texto.
- v0.2.0: norma em partes; leis (`tipo: lei`, `orgao: federal`); divergências aceitas; contagem de tabelas no teste final; numeração de listas do Word (incisos e alíneas numerados pelo Word) na conversão do consolidado.
- v0.1.0: piloto com a Res. CVM 17.

## Aviso

Material não oficial. Não substitui o Diário Oficial da União nem os sites dos órgãos e entidades de origem.
