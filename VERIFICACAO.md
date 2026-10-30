# Verificação do acervo (v1.0)

Auditoria cega por amostragem feita em 2026-10-30, sobre as 5 camadas do acervo (634 normas). Ela mede uma coisa: se o texto do acervo é igual ao da fonte oficial. Não mede se a norma é a certa para um caso nem se a interpretação está correta.

## Resultado

| Camada | Itens auditados | Erros de texto | O que se pode afirmar |
|---|---|---|---|
| 1. Resoluções e Instruções CVM | 114 | 0 | zero erro em 114 itens: taxa de erro abaixo de 2,6% com 95% de confiança |
| 2. Pareceres e Ofícios-Circulares, sem OCR | 22 | 0 | zero erro em 22 itens: taxa de erro abaixo de 13,6% com 95% de confiança |
| 2. Ofícios-Circulares lidos por OCR (7) | 8 + 8 | 2 + 2 | ressalva: o OCR erra; use o PDF da CVM (ver Ressalvas) |
| 3. Leis e decretos | 28 | 0 | zero erro em 28 itens: taxa de erro abaixo de 10,7% com 95% de confiança |
| 4. CMN e BCB | 55 + 25 | 1, corrigido | depois da correção, zero erro em 50 itens: taxa de erro abaixo de 6% com 95% de confiança |
| 5. ANBIMA e B3 | 30 | 1 | ressalva: o Glossário ANBIMA tem verbetes separados das definições (ver Ressalvas) |

A taxa vale para a população de onde a amostra saiu (a camada ou categoria da linha), não para o acervo inteiro. É a regra de três: zero erro em N itens sorteados põe a taxa abaixo de 3/N com 95% de confiança. Nas categorias auditadas por inteiro (censo), não há taxa: todos os itens foram conferidos.

## Método

- **Item.** Na camada 1, com histórico por ato, o item é um artigo alterado por um ato, na versão do commit daquele ato. Nas demais, o item é um artigo, uma página de PDF ou um bloco de texto.
- **Auditor cego.** Para cada lote de até 10 itens, um modelo Claude Opus 5.5 roda numa pasta isolada, fora do repositório, que contém só os insumos do lote (`claude -p --tools Read,Write`). O log de cada sessão (stream-json) mostra que o auditor não leu nada fora da pasta.
  - Camada 1, replay: o auditor recebe o artigo como estava antes do ato e o texto integral do ato, e escreve o artigo como fica depois do ato.
  - Demais camadas: o auditor recebe a fonte e transcreve o trecho. A fonte é a página do PDF recortada, lida como imagem, ou o recorte do HTML do Planalto e do BCB, com as marcas de tachado. É um canal independente do extrator que gerou o acervo.
- **Comparação.** Um script compara a saída do auditor com o acervo, palavra a palavra (`scripts/auditoria.py comparar`). Toda diferença foi triada à mão, com a fonte aberta, e classificada como erro do acervo, erro do auditor, divergência já registrada ou forma.
- **Erro de texto.** Conta como erro: palavra, número ou sinal que muda o sentido; dispositivo trocado, omitido ou duplicado; redação revogada apresentada como vigente; dado pessoal que deveria ter saído. Não conta: caixa, espaço, Markdown, º/o, aspas, e divergência já decidida em `fontes/DIVERGENCIAS.md`.
- **Sorteio.**
  - Semente 20261030, com `random.Random` sobre o universo ordenado. A lista ficou no Git antes de qualquer resultado (`fontes/amostra-fase3.json`).
  - A camada 4 foi sorteada de novo, com a mesma semente, depois da correção descrita abaixo. Os 30 itens do primeiro sorteio dela, anteriores à correção, saíram sem auditoria.
  - A re-auditoria usou a semente 20261031, sem repetir itens (`fontes/amostra-fase3-reauditoria.json`).
- **Gate.** Um erro de texto reprova a categoria. A categoria reprovada é corrigida, refeita nas normas afetadas e re-auditada uma vez. Se o erro persistir, a ressalva é publicada aqui.

## Amostra por categoria

Universo em unidades (artigos, páginas ou trechos). "Censo": todas as unidades auditadas.

| Camada | Categoria | Universo | Amostra | Resultado |
|---|---|---|---|---|
| 1 | Revogação | 56 | censo | sem erro |
| 1 | Vigência diferida (dispositivos com data própria em 10 atos) | 12 | censo | sem erro |
| 1 | Inclusão | 72 | 12 | sem erro |
| 1 | Nova redação (8 entre trechos que um ato posterior sobrescreveu) | 234 | 15 | sem erro |
| 1 | Tabela e anexo | 460 | 12 (1 sem região comparável) | sem erro |
| 1 | Texto sem histórico (DOCX, DOC; 5 com lista numerada) | 1.074 | 10 | sem erro |
| 2 | Ofício por OCR | 39 páginas | 8 + 8 | ressalva |
| 2 | Ofício em PDF | 2.282 páginas | 12 | sem erro |
| 2 | Parecer de Orientação (DOC, DOCX) | 304 | 5 | sem erro |
| 2 | Nota de rodapé e diagrama | 551 | 5 | sem erro |
| 3 | "Redação dada" e "Incluído" | 451 | 14 | sem erro |
| 3 | Revogado | 131 | 10 | sem erro |
| 3 | Rótulo de margem retirado | 193 | 5 | sem erro |
| 3 | Tabela | 1 | censo | sem erro |
| 4 | Redação tachada retirada | 199 | 10 | sem erro |
| 4 | Nota "Redação dada" | 171 | 7 | sem erro |
| 4 | Tabela | 8 | censo | sem erro |
| 4 | Norma só pelo PDF ou OCR (1 página por norma) | 120 páginas, 31 normas | 31 + 26 | 1 erro, corrigido; re-auditoria sem erro |
| 5 | Página de assinaturas retirada | 10 | censo | sem dado pessoal; ressalva do Glossário |
| 5 | Quebra de página | 4.143 pares | 8 | sem erro |
| 5 | Sumário | 119 | 6 | sem erro |
| 5 | Tabela de PDF | 78 | 6 | sem erro |

Da contagem saem 6 itens que não tiveram auditoria cega válida, todos conferidos à mão contra a fonte, sem erro do acervo:

- Res. CVM 175, Anexos VIII e XII (ato 184/23): o ato cria anexos inteiros, cada um com seu art. 1º e art. 6º. O auditor aplicou o artigo de outro anexo.
- Lei 13.506, arts. 43 e 62: o recorte do HTML caiu em outro artigo, e o auditor não teve o que transcrever.
- Também ficaram fora, porque o script não achou a região do acervo a comparar: 1 item de tabela e anexo e 2 páginas de norma só pelo PDF.

## Erros encontrados e correções

| Onde | Erro | Correção |
|---|---|---|
| Res. CMN 1.502 (camada 4) | alíneas a) e b) do item VI lidas fora de ordem pelo extrator de PDF, dentro do item VIII | ordem refeita pelo PDF; medida a ordem das palavras nas 31 normas da camada 4 tiradas de PDF, só esta tinha desvio relevante |
| OC CVM/SMI 2/2023 (camada 2) | lido por OCR, embora o PDF tenha texto; ticker "D10W34" no lugar de "D1OW34" e valores da tabela perdidos | regra de legibilidade passa a aceitar tickers e ISINs; texto refeito pela camada de texto do PDF |
| OCs CVM/SSE 4/2025 e Conjunto 2/2025 (OCR) | pontuação trocada, "capítulo V1" no lugar de "VI", ruído do carimbo no meio do texto | sem correção possível por script: ressalva |
| Glossário ANBIMA (camada 5) | o PDF em duas colunas separa os verbetes das definições, e a definição de "Usuários" aparece depois de "Exterior" | sem correção por script: ressalva |

## Achados fora da amostra

- **Camada 4, normas do CMN e do BCB alteradas.** O campo de texto da busca de normas do BCB traz a redação original. O texto compilado vigente está só no PDF da última versão (`_vN_L`). Por isso, 26 normas estavam na redação original; entre elas, as Res. CMN 2.907 (FIDC), 4.734 e 4.593 (recebíveis). As 26 foram refeitas pelo PDF da última versão, e a camada 4 foi auditada depois disso. Quem achou foi o redator da bateria de perguntas, ao não encontrar na 2.907 a marca da alteração de 2018.
- **OC CVM/SIN 6/2023.** O arquivo trazia o corpo do OC CVM/SSE 6/2023: um PDF antigo no cache local tinha o nome do outro ofício. Corrigido. Os 369 arquivos de fonte da CVM no cache foram conferidos contra o tamanho publicado no site, e nenhum outro diverge.
- **Duplicatas.** O OC Conjunto SIN/SSE 1/2022 e o OC Conjunto SNC/SSE/SIN 1/2025 aparecem duas vezes cada no acervo, porque a CVM os publica em duas pastas. O texto é o mesmo.

## Ressalvas

1. **Ofícios-Circulares lidos por OCR** (7: OCs CVM/SEP 6/2026, Conjunto SNC/SSE/SIN 2/2025, SSE/SNC 2/2025, SSE 2/2026, 3/2026, 4/2025 e 6/2025; `nivel_verificacao: ocr`). O PDF da CVM não tem camada de texto. O OCR erra em pontuação, em algarismos romanos e no carimbo de assinatura. Para citar, confira o PDF da CVM (`fonte_original`).
2. **Glossário ANBIMA.** Verbetes e definições podem estar desalinhados. Confira o PDF da ANBIMA.
3. **Res. CVM 81, art. 45, inciso III.** A Res. CVM 204/24 reescreve o art. 45 com caput, incisos I e II e § 1º, sem linha pontilhada, e revoga expressamente só o § 2º. O novo inciso II repete o conteúdo do antigo III. O acervo mantém o inciso III, como o consolidado da CVM. O auditor, lendo o ato ao pé da letra, o tirou. Registrado em `fontes/DIVERGENCIAS.md` [verificar no DOU].

## Limitações de forma (não contam como erro)

- PDFs da ANBIMA e da B3 (camada 5): hifenização de fim de linha preservada ("obriga- ções"); cabeçalho e rodapé repetidos no meio do texto (ex.: "INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION"); numeração de listas e células de tabela deslocadas; pontilhado do sumário.
- PDFs da CVM (camada 2): número de nota de rodapé colado à palavra ("11.04.200648" é a data 11.04.2006 com a nota 48); texto de gráficos não extraído; palavra partida no timbre ("V alores").
- PDFs do BCB (camada 4): palavra partida pelo extrator ("disp osição"); fórmula sem marcação.
- Res. CVM 30 (1 linha), Res. CVM 160 (5) e o texto da Res. CVM 162 em `alteradoras/` (8): âncora de nota de rodapé solta, como "(7)", copiada do texto do ato.

## Reprodução

```
python3 scripts/auditoria.py universo
python3 scripts/auditoria.py sortear --semente 20261030
python3 scripts/auditoria.py insumos --amostra fontes/amostra-fase3.json --saida <pasta>
# um lote por pasta: claude -p "Siga as instruções de PROMPT.md, nesta pasta." --model opus --tools Read,Write
python3 scripts/auditoria.py comparar --amostra fontes/amostra-fase3.json --saidas <pasta>
```

As fontes ficam em `dados/`, fora do Git. O universo depende delas e do histórico da `main` em 2026-10-30.
