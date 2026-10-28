# SPEC: formato do acervo (v0.2.0)

Versão semântica. Campos novos opcionais = menor; campo obrigatório novo ou mudança de significado = maior.

## Estrutura

- Cada resolução é um arquivo Markdown em `plugins/normas/normas/<órgão>/<tipo>/<número com 4 dígitos>.md` (ex.: `cvm/resolucoes/0017.md`). Nomes sem acento, em minúsculas.
- Norma em partes (norma longa, como a Res. CVM 175): uma pasta `<número com 4 dígitos>/` com `index.md` e as partes. O `index.md` tem o frontmatter completo e uma seção `## Partes` com uma lista `- arquivo.md`, na ordem do texto. Cada parte não tem frontmatter e abre com `# título` (ex.: `# Anexo Normativo I`); os artigos continuam como `## Art.`. O mesmo número de artigo pode se repetir em partes diferentes.
- Leis (v0.2.0) ficam em `plugins/normas/normas/leis/` (sem nível de órgão): `lei-NNNNN.md` (5 dígitos) ou, em partes, `lei-NNNNN/index.md`. Código Civil: só os artigos do recorte (`lei-10406.md`, arts. 1.368-C a 1.368-F), descrito em `incerteza`.
- Atos que alteram normas ficam em `plugins/normas/normas/<órgão>/alteradoras/<número com 4 dígitos>.md`, com o texto do ato.
- Cada artigo começa em linha própria com um heading de nível 2: `## Art. 1º`, `## Art. 10`, `## Art. 12-A`. Parágrafos, incisos e alíneas ficam como texto abaixo do artigo.
- Dispositivo revogado permanece com a marca `(Revogado)` (ou `(Revogado pela Resolução CVM nº X)`).
- Cada ato alterador é um commit; autor e data do commit são a identidade de replay e a data de publicação no DOU.

## Frontmatter

Campos obrigatórios, nesta ordem:

| Campo | Conteúdo |
|---|---|
| `id` | identificador estável, ex.: `cvm-res-17`, `lei-6404` |
| `orgao` | `cvm` (resolução) ou `federal` (lei) |
| `tipo` | `resolucao` ou `lei` |
| `numero` | número do ato (inteiro) |
| `data` | data do ato, AAAA-MM-DD |
| `publicacao_dou` | data de publicação no DOU, AAAA-MM-DD |
| `ementa` | ementa oficial |
| `situacao` | `vigente`, `revogada` ou `parcialmente-revogada` |
| `versao_texto` | `consolidado` ou `original` |
| `vigente_ate_ato` | número do último ato alterador aplicado (data-base do texto); vazio em lei |
| `aguarda_consolidado_oficial` | `true` se há ato aplicado ainda não refletido no consolidado da CVM |
| `historico_parcial` | `true` se o histórico de atos não está completo |
| `fonte_original` | URL da redação original |
| `fonte_consolidada` | URL do texto consolidado usado na conferência |
| `sha256_fonte` | hash do arquivo da fonte consolidada |
| `baixado_em` | AAAA-MM-DD; em lei é a data-base do texto |
| `verificado_em` | AAAA-MM-DD da última conferência contra o consolidado |
| `incerteza` | texto livre; vazio quando não há |

Opcional: `vigencia_inicio` (AAAA-MM-DD), obrigatório quando o texto tem bloco "vigente a partir de" (vigência diferida: o dispositivo traz as duas redações, a atual e a futura, esta com a data). Vem depois de `incerteza`.

Regras de valor (verificadas por `scripts/validar.py`):

- Chaves na ordem da tabela, sem campo repetido nem desconhecido; um valor por linha (`chave: valor`), sem listas.
- `numero` inteiro. Resolução: `orgao: cvm`, `id` = `cvm-res-<numero>`, arquivo `<numero com 4 dígitos>.md`. Lei: `orgao: federal`, `id` = `lei-<numero>`, arquivo `lei-<numero com 5 dígitos>.md`. Em norma em partes o arquivo é `index.md`, dentro da pasta com o nome acima (sem `.md`).
- Em lei, `vigente_ate_ato` fica vazio (não há atos aplicados em sequência); `historico_parcial: true`; `aguarda_consolidado_oficial: false`.
- Datas em AAAA-MM-DD válidas; `aguarda_consolidado_oficial` e `historico_parcial` são `true` ou `false`.
- `situacao` ∈ `vigente`, `revogada`, `parcialmente-revogada`; `versao_texto` ∈ `consolidado`, `original`.
- `vigente_ate_ato`: número do último ato aplicado (inteiro, ex.: `226`) ou vazio quando só a redação original foi aplicada.
- `sha256_fonte`: 64 caracteres hexadecimais. `ementa`, `fonte_original` e `fonte_consolidada` não ficam vazios.

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

O teste final compara o número de tabelas da norma com o do consolidado (diferença é erro) e as células não vazias de cada tabela; células vazias e linhas só de separador não contam.

## Vigência diferida

O dispositivo traz a redação atual e, depois dela, a futura, aberta por uma linha que começa com `Vigente a partir de` (pode vir em citação `>` ou em negrito), seguida da data. O frontmatter ganha `vigencia_inicio` com essa data. O validador rejeita o bloco sem `vigencia_inicio` válido. Se houver mais de um bloco com datas diferentes, use a data do primeiro e descreva os demais em `incerteza` (limite da v0.1.0 e da v0.2.0).

## Marcas no texto

- Revogado: `(Revogado)` ou `(Revogado pela Resolução CVM nº X)`. O consolidado da CVM usa `REVOGADO`; os testes tratam as três formas como iguais.
- Notas de alteração do consolidado ("Caput com redação dada pela...", "(NR)") não entram no texto da norma; o histórico de commits as substitui.
- Redação antiga tachada no consolidado é descartada na comparação.

## Histórico de versões

- v0.2.0: norma em partes; leis (`tipo: lei`, `orgao: federal`); divergências aceitas; contagem de tabelas no teste final; numeração de listas do Word (incisos e alíneas numerados pelo Word) na conversão do consolidado.
- v0.1.0: piloto com a Res. CVM 17.

## Aviso

Material não oficial. Não substitui o Diário Oficial da União nem o site da CVM.
