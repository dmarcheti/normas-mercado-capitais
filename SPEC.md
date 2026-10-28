# SPEC: formato do acervo (v0.1.0)

Versão semântica. Campos novos opcionais = menor; campo obrigatório novo ou mudança de significado = maior.

## Estrutura

- Cada norma é um arquivo Markdown em `plugins/normas/normas/<órgão>/<tipo>/<número com 4 dígitos>.md` (ex.: `cvm/resolucoes/0017.md`). Nomes sem acento, em minúsculas.
- Atos que alteram normas ficam em `plugins/normas/normas/<órgão>/alteradoras/<número com 4 dígitos>.md`, com o texto do ato.
- Cada artigo começa em linha própria com um heading de nível 2: `## Art. 1º`, `## Art. 10`, `## Art. 12-A`. Parágrafos, incisos e alíneas ficam como texto abaixo do artigo.
- Dispositivo revogado permanece com a marca `(Revogado)` (ou `(Revogado pela Resolução CVM nº X)`).
- Cada ato alterador é um commit; autor e data do commit são a identidade de replay e a data de publicação no DOU.

## Frontmatter

Campos obrigatórios, nesta ordem:

| Campo | Conteúdo |
|---|---|
| `id` | identificador estável, ex.: `cvm-res-17` |
| `orgao` | `cvm` |
| `tipo` | `resolucao` |
| `numero` | número do ato (inteiro) |
| `data` | data do ato, AAAA-MM-DD |
| `publicacao_dou` | data de publicação no DOU, AAAA-MM-DD |
| `ementa` | ementa oficial |
| `situacao` | `vigente`, `revogada` ou `parcialmente-revogada` |
| `versao_texto` | `consolidado` ou `original` |
| `vigente_ate_ato` | número do último ato alterador aplicado (data-base do texto) |
| `aguarda_consolidado_oficial` | `true` se há ato aplicado ainda não refletido no consolidado da CVM |
| `historico_parcial` | `true` se o histórico de atos não está completo |
| `fonte_original` | URL da redação original |
| `fonte_consolidada` | URL do texto consolidado usado na conferência |
| `sha256_fonte` | hash do arquivo da fonte consolidada |
| `baixado_em` | AAAA-MM-DD |
| `verificado_em` | AAAA-MM-DD da última conferência contra o consolidado |
| `incerteza` | texto livre; vazio quando não há |

Opcional: `vigencia_inicio` (AAAA-MM-DD), obrigatório quando o texto tem bloco "vigente a partir de" (vigência diferida: o dispositivo traz as duas redações, a atual e a futura, esta com a data). Vem depois de `incerteza`.

Regras de valor (verificadas por `scripts/validar.py`):

- Chaves na ordem da tabela, sem campo repetido nem desconhecido; um valor por linha (`chave: valor`), sem listas.
- `numero` inteiro; `id` = `cvm-res-<numero>`; o arquivo se chama `<numero com 4 dígitos>.md`.
- Datas em AAAA-MM-DD válidas; `aguarda_consolidado_oficial` e `historico_parcial` são `true` ou `false`.
- `situacao` ∈ `vigente`, `revogada`, `parcialmente-revogada`; `versao_texto` ∈ `consolidado`, `original`.
- `vigente_ate_ato`: número do último ato aplicado (inteiro, ex.: `226`) ou vazio quando só a redação original foi aplicada.
- `sha256_fonte`: 64 caracteres hexadecimais. `ementa`, `fonte_original` e `fonte_consolidada` não ficam vazios.

## Vigência diferida

O dispositivo traz a redação atual e, depois dela, a futura, aberta por uma linha que começa com `Vigente a partir de` (pode vir em citação `>` ou em negrito), seguida da data. O frontmatter ganha `vigencia_inicio` com essa data. O validador rejeita o bloco sem `vigencia_inicio` válido. Se houver mais de um bloco com datas diferentes, use a data do primeiro e descreva os demais em `incerteza` (limite da v0.1.0).

## Marcas no texto

- Revogado: `(Revogado)` ou `(Revogado pela Resolução CVM nº X)`. O consolidado da CVM usa `REVOGADO`; os testes tratam as três formas como iguais.
- Notas de alteração do consolidado ("Caput com redação dada pela...", "(NR)") não entram no texto da norma; o histórico de commits as substitui.
- Redação antiga tachada no consolidado é descartada na comparação.

## Aviso

Material não oficial. Não substitui o Diário Oficial da União nem o site da CVM.
