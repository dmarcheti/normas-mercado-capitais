# SPEC: formato do acervo (v0.3.1)

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

- Ofício-circular: `<slug>` é o nome da página do ofício no site da CVM, sem `.html` (ex.: `oc-sse-0326`, `occ-sin-sse-0125`, `oc-anual-2026-sre`), só minúsculas, dígitos e hífen; o id é `cvm-` + slug (`cvm-oc-sse-0326`). `<pasta>` é a pasta do ofício no site da CVM (`sin`, `sep`, `sse1`, `smi-sin`...). O `numero` é o número do ofício (inteiro), sem regra de coerência com o id, porque se repete entre superintendências e anos.
- Norma em partes (norma longa, como a Res. CVM 175): uma pasta `<número com 4 dígitos>/` com `index.md` e as partes. O `index.md` tem o frontmatter completo e uma seção `## Partes` com uma lista `- arquivo.md`, na ordem do texto. Cada parte não tem frontmatter e abre com `# título` (ex.: `# Anexo Normativo I`); os artigos continuam como `## Art.`. O mesmo número de artigo pode se repetir em partes diferentes.
- Leis (v0.2.0), decretos e leis complementares (v0.3.0) ficam em `plugins/normas/normas/leis/` (sem nível de órgão), em arquivo único ou, em partes, na pasta com o mesmo nome (`lei-NNNNN/index.md`, `decreto-NNNNN/index.md`). Código Civil: só os artigos do recorte (`lei-10406.md`, arts. 1.368-C a 1.368-F), descrito em `incerteza`.
- Atos que alteram normas ficam em `plugins/normas/normas/<órgão>/alteradoras/<número com 4 dígitos>.md`, com o texto do ato.
- Cada artigo começa em linha própria com um heading de nível 2: `## Art. 1º`, `## Art. 10`, `## Art. 12-A`. Parágrafos, incisos e alíneas ficam como texto abaixo do artigo.
- O validador não exige `## Art.`: pareceres de orientação e ofícios-circulares não têm artigos. Quando a norma tem artigos, a regra acima vale.
- Dispositivo revogado permanece com a marca `(Revogado)` (ou `(Revogado pela Resolução CVM nº X)`).
- Cada ato alterador é um commit; autor e data do commit são a identidade de replay e a data de publicação no DOU.

## Frontmatter

Campos obrigatórios, nesta ordem:

| Campo | Conteúdo |
|---|---|
| `id` | identificador estável, ex.: `cvm-res-17`, `lei-6404` |
| `orgao` | `cvm` ou `federal`, conforme o tipo (tabela da Estrutura) |
| `tipo` | `resolucao`, `instrucao`, `parecer-orientacao`, `oficio-circular`, `lei`, `decreto` ou `lei-complementar` |
| `numero` | número do ato (inteiro) |
| `data` | data do ato, AAAA-MM-DD |
| `publicacao_dou` | data de publicação no DOU, AAAA-MM-DD |
| `ementa` | ementa oficial |
| `situacao` | `vigente`, `revogada`, `parcialmente-revogada` ou `nao-informada` (só parecer e ofício) |
| `versao_texto` | `consolidado` ou `original` |
| `vigente_ate_ato` | número do último ato alterador aplicado (data-base do texto); vazio em lei, decreto e lei complementar |
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

Regras de valor (verificadas por `scripts/validar.py`):

- Chaves na ordem da tabela, sem campo repetido nem desconhecido; um valor por linha (`chave: valor`), sem listas.
- `numero` inteiro. `orgao`, `id` e nome do arquivo conforme o tipo (tabela da Estrutura); `tipo` fora da tabela é erro, e a mensagem lista os aceitos. Em ofício-circular, o `id` é `cvm-` + nome do arquivo sem `.md`. Em norma em partes o arquivo é `index.md`, dentro da pasta com o nome acima (sem `.md`).
- Em lei, decreto e lei complementar, `vigente_ate_ato` fica vazio (não há atos aplicados em sequência); `historico_parcial: true`; `aguarda_consolidado_oficial: false`.
- Datas em AAAA-MM-DD válidas; `aguarda_consolidado_oficial` e `historico_parcial` são `true` ou `false`.
- `situacao` ∈ `vigente`, `revogada`, `parcialmente-revogada`, `nao-informada`; `versao_texto` ∈ `consolidado`, `original`. `nao-informada` só em `parecer-orientacao` e `oficio-circular`: a CVM não publica a vigência deles.
- `vigente_ate_ato`, nos tipos da CVM: número do último ato aplicado (inteiro, ex.: `226`) ou vazio quando só a redação original foi aplicada.
- `nivel_verificacao`, quando presente, é um dos seis valores acima.
- `sha256_fonte`: 64 caracteres hexadecimais. `ementa`, `fonte_original` e `fonte_consolidada` não ficam vazios.

## Pastas validadas e índices

- O validador (`scripts/validar.py <raiz>`) lê as normas de `resolucoes/`, `instrucoes/`, `pareceres-orientacao/`, `oficios-circulares/<pasta>/` e `leis/`. Os atos alteradores (`alteradoras/`) e os índices não seguem o schema.
- O índice (`scripts/indice.py`) gera, na raiz `plugins/normas/normas/`: `indice.md` (resumo: aviso, perímetro, contagem por tipo e link para cada subíndice), `normas.json` (todas as normas, com `tipo` e, na resolução do Estoque Regulatório, `grupo`) e os subíndices em `indices/`: `resolucoes.md` (por grupo temático do Estoque Regulatório da CVM, lido de `fontes/acervo.json`, chave `estoque_regulatorio.grupos`; normas contábeis por último), `instrucoes.md`, `pareceres-orientacao.md`, `oficios-circulares.md` (por pasta, data decrescente; os ofícios de `fontes/acervo.json` sem arquivo no acervo entram como verbete, com link e sem texto), `leis.md` (leis, leis complementares e decretos) e `alteradoras.md`. Subíndice vazio não é gerado. A saída não tem data de geração; `--verificar` falha se algum arquivo estiver defasado ou se sobrar em `indices/` subíndice que não é mais gerado.

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

## Histórico de versões

- v0.3.1: valor `ocr` em `nivel_verificacao`; `baixado_em` é a data do download da fonte e `verificado_em` a da geração.
- v0.3.0: tipos `instrucao`, `parecer-orientacao`, `oficio-circular`, `decreto` e `lei-complementar`; `situacao: nao-informada` (só parecer e ofício); campo opcional `nivel_verificacao`; `## Art.` não é exigido; índice dividido em resumo e subíndices (`indices/`), com resoluções por grupo do Estoque Regulatório e verbetes de ofícios sem texto.
- v0.2.0: norma em partes; leis (`tipo: lei`, `orgao: federal`); divergências aceitas; contagem de tabelas no teste final; numeração de listas do Word (incisos e alíneas numerados pelo Word) na conversão do consolidado.
- v0.1.0: piloto com a Res. CVM 17.

## Aviso

Material não oficial. Não substitui o Diário Oficial da União nem o site da CVM.
