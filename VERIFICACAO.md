# Verificação do acervo (v1.1)

As normas (v1.0) e os julgados (v1.1) foram auditados em separado; a seção [Julgados](#julgados-v11) fica no fim.

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

# Julgados (v1.1)

Auditoria cega por amostragem feita de 2026-11-03 a 2026-11-04 sobre os 14.990 julgados (PAS, decisões do Colegiado, termos de compromisso e acórdãos do CRSFN), em seis blocos: texto, metadados, extração por LLM, citações, dados pessoais e completude. Como nas normas, ela mede se o acervo reproduz a fonte; não mede se a decisão está certa.

## Resultado

Texto (bloco A), última rodada de cada estrato. "Erros" conta itens com pelo menos um erro; a taxa vale para a população do estrato.

| Estrato | População | Rodada | Itens | Erros | O que se pode afirmar |
|---|---|---|---|---|---|
| Colegiado, PDF com texto | 6.601 | 20261108 | 20 | 0 | abaixo de 15% com 95% de confiança |
| PAS, PDF com texto | 1.181 | 20261108 | 20 | 2 | 2 em 20: linha fora de lugar (uma inverte uma negação) |
| TC, PDF com texto | 1.469 | 20261108 | 12 | 0 | abaixo de 25% |
| CRSFN, PDF | 767 | 20261108 | 10 | 0 | abaixo de 30% |
| Colegiado, OCR | 394 | 20261108 | 8 | 3 | ressalva: tabela ou figura que é imagem, dígito de tabela |
| PAS, OCR | 238 | 20261108 | 10 | 0 | abaixo de 30% |
| TC, OCR | 164 | 20261108 | 6 | 1 | 1 em 6: nome de testemunha no carimbo (corrigido) |
| Colegiado, HTML | 3.506 | 20261103 | 13 | 0 | abaixo de 23% |
| CRSFN, HTML | 569 | 20261103 | 6 | 0 | abaixo de 50% |
| TC, extrato HTML do SEI | 81 | 20261103 | 4 | 0 | amostra pequena |
| Decisões antigas (PDF anual) | 24 arquivos | 20261103 | 6 trechos | 0 | amostra pequena |

Demais blocos:

| Bloco | Itens | Erros | O que se pode afirmar |
|---|---|---|---|
| B. Metadados: Colegiado / PAS / TC / CRSFN | 20 / 15 / 15 / 10 | 1 / 0 / 1 / 0 | os 2 erros (classe de audiência pública, data de termo) corrigidos na regra |
| C. Ementa extraída | 40 | 2 | 2 em 40 depois da reextração (meta D1: até 2 em 40) |
| C. Tema | 40 + 40 | 0 | abaixo de 3,75% |
| C. Resultado: Colegiado / TC / PAS / CRSFN | 40 / 20 / 10 / 10 | 2 / 0 / 0 / 0 | 2 em 80; os 2 corrigidos; CRSFN medido de novo depois da regra do recurso de ofício |
| D. Citações (40 trechos) | 30 válidos | 2 | precisão 97,2% (69 de 71 listadas); revocação 65,7% (69 de 105) |
| E. Dados pessoais (qualificação) | 40 | 0 dado que ficou; 1 nome cortado junto | depois de 5 rodadas com correção a cada uma |
| F. CRSFN classificado como não CVM com "CVM" no preâmbulo | 30 | 0 | abaixo de 10% |
| F. Completude | censo | 4 + 4 | 13.658 de 13.662 julgados da CVM e 1.342 de 1.346 acórdãos do CRSFN; os 8 fora estão nas exceções |

A taxa vale para o estrato de onde o item foi sorteado, não para os 14.990 julgados. Zero erro em N itens põe a taxa abaixo de 3/N com 95% de confiança.

## Método

- **Item.** Texto: um trecho sorteado por julgado, transcrito pelo auditor a partir da fonte (até 4 páginas do PDF, recortadas, ou o bloco do HTML). Campo: o auditor preenche resultado, ementa, tema, metadados ou dados pessoais a partir da fonte, sem ver o acervo.
- **Auditor cego.** Lotes de até 10 itens, cada um numa pasta isolada fora do repositório, com `claude -p --tools Read,Write` (Opus no texto, Sonnet nos campos). O log de cada sessão mostra que o auditor não leu nada fora da pasta.
- **Comparação e adjudicação.** Um script compara saída e acervo (`scripts/auditoria_julgados.py comparar`). Toda diferença de texto foi adjudicada por um segundo agente, com a página da fonte aberta como imagem, e classificada como erro do acervo ou ruído; as adjudicações ficaram em arquivo, uma linha por diferença.
- **Erro (C7).** Texto: palavra, número ou sinal que muda o sentido; trecho omitido, duplicado, alheio ou fora de ordem com mudança de sentido; dado pessoal que ficou; trecho que não é dado pessoal cortado como se fosse. Campo: valor diferente do que a fonte diz. Ementa: afirmação contrária ao texto, decisão omitida ou nome de pessoa física. Não conta: caixa, espaço, Markdown, º/o, hifenização, numeração de parágrafo ou de nota solta, tabela linearizada, timbre e rodapé da CVM e do SEI, carimbo de cartório, bloco de assinatura e o corte conservador de endereço, e-mail e número de documento na qualificação (SPEC).
- **Sorteio.** `random.Random(semente)` sobre o universo ordenado; cada amostra foi para o Git antes da auditoria (`fontes/amostra-fase3b*.json`), e nenhuma rodada repete item de outra.
- **Gate.** Estrato com erro foi corrigido por regra no conversor (nunca à mão no texto publicado), reconvertido da fonte e auditado de novo com outra semente.

## Rodadas

| Semente | Escopo | Itens | O que mudou depois |
|---|---|---|---|
| 20261103 | todos os blocos | 411 | recorte da extração pela deliberação; reextração de 10.297 julgados; dados pessoais |
| 20261104 | ementa, tema, resultado, OCR, dados pessoais | 176 | regra do recurso de ofício no CRSFN; linhas repetidas só na borda da página; pii |
| 20261105 | texto PDF e OCR, dados pessoais, resultado do CRSFN | 138 | texto sobreposto; romanos e "§" do OCR; ordem de linhas pelo pypdf; OCR de imagem em PDF nativo; pii |
| 20261106 | dados pessoais | 40 | RG, endereço e CPF lidos pelo OCR |
| 20261107 | texto PDF e OCR, dados pessoais | 128 | linhas soltas e deslocadas; OCR de faixa de imagem; "Vão" por "Não"; nacionalidades |
| 20261108 | texto PDF e OCR, dados pessoais | 128 | nome de testemunha abreviado no bloco e por extenso no carimbo; título espúrio no CRSFN; e, na revisão do diff da reconversão, CPF com ":" do OCR, "Brasil" do texto tomado por timbre e caractere de controle no lugar de glifo |

Itens com erro de texto por rodada, nos sete estratos de PDF e OCR: 10 em 86 (20261103), 11 em 86 (20261105), 9 em 87 (20261107) e 6 em 86 (20261108). Cada rodada traz itens novos; a queda reflete as correções, com a margem de amostras desse tamanho. As correções e as exceções estão em `fontes/RESULTADOS.md`, seção Fase 3b.

## Ressalvas

1. **Julgado lido por OCR** (`nivel_verificacao: ocr`, 813 julgados). Tabela, figura e número lidos por OCR podem sair com dígito trocado, linha faltando ou fora de ordem. Antes de citar número de tabela, confira a `fonte_original`.
2. **Ordem de linha no PDF.** O extrator do macOS desloca às vezes uma linha (número de parágrafo, sobrescrito, itálico). Uma regra confere com o pypdf e devolve a linha ao lugar; os casos que ela não alcança ficaram em 2 de 20 PAS na última rodada. Numa citação literal, confira a fonte.
3. **Ementa e resultado extraídos por LLM.** Ementa com `ementa_fonte: extracao`, tema e resultado do Colegiado e do TC vêm do modelo, a partir do texto; a taxa medida está acima.
4. **Citações.** O índice de citações acha 2 de cada 3 dispositivos citados; não use a ausência no índice como prova de que um julgado não cita uma norma.

## Bateria de perguntas

30 perguntas sobre julgados, com gabarito conferido na página da CVM ou do CRSFN (`testes/bateria-v2.md`), respondidas pelo Claude com e sem os plugins de julgados e julgadas às cegas pelo Claude Opus, que não sabia de qual modo vinha cada resposta, em quatro critérios:

| Critério | Sem os julgados | Com os julgados |
|---|---|---|
| Acha o caso certo | 1 | 25 |
| Conteúdo certo (resultado, valores, fundamento) | 2 | 27 |
| Ressalvas de fonte | 5 | 29 |
| Tudo certo | 1 | 24 |

As 6 falhas com os julgados são de busca: o caso existe no acervo, mas a resposta não o achou (duas estavam nos arquivos anuais de decisões antigas).

### Rodada de ajuste da busca (2026-11-05)

Diagnóstico das 6 falhas pelos transcritos. A causa comum era o limite de leitura: a ferramenta de ler arquivo corta perto de 40 KB sem avisar, e os `indice.md` dos julgados tinham de 73 a 130 KB. As outras causas eram a skill apontar o lugar errado, a falta de índice por processo e os arquivos anuais de decisões antigas sem divisão.

O que mudou:
- `indice.md` com menos de 25 KB;
- sumário no topo dos subíndices longos e "Fim do subíndice." em todos;
- índice por processo nos plugins de PAS e de termos de compromisso e CRSFN;
- índice por decisão nas decisões de 1978 a 2001, com os nomes de pessoa física trocados;
- 5 regras curtas na skill.

Rodada única, sem segunda tentativa, com as 6 perguntas que falhavam e 6 de controle sorteadas entre as 24 certas (semente 20261105). Protocolo da v2: Claude Sonnet com os plugins, só ferramenta de leitura, e juiz Claude Opus cego.

| | Tudo certo | Acha o caso |
|---|---|---|
| As 6 que falhavam | 3 (P09, P23, P25) | 3 |
| 6 de controle | 6 | 6 |

Seguem falhando P10 (acha 1 dos 3 casos), P11 e P24. Em P24, a decisão de 1997 não foi achada nem com o índice por decisão. As outras 18 perguntas da v2 não foram rodadas de novo; o total de 27/30 é projeção, não medida.

Diferença de ambiente em relação à v2:
- os plugins carregam a partir de uma pasta-mãe, porque o Claude Code 2.1.311 não carrega nenhum plugin quando recebe dois ou mais `--plugin-dir`;
- a sessão roda sem as configurações do usuário, para não carregar versões dos mesmos plugins sincronizadas da conta do claude.ai.

Runner: `scripts/bateria.py`.

### Plugin único com fichas (2.0.0, 2026-11-12)

Na 2.0.0, o plugin leva uma ficha por julgado (resultado, ementa, dispositivos e um trecho da decisão de até 1.500 caracteres, ou 4.000 em PAS e acórdãos do CRSFN), e o texto integral fica em `julgados/` na raiz do repositório. As duas baterias foram refeitas só com o plugin, sem web, no protocolo da v2 (Claude Sonnet com leitura de arquivo e juiz Claude Opus cego, semente padrão).

| | r1 | r2 | v1.1, texto integral |
|---|---|---|---|
| Julgados, tudo certo | 18 | 24 | 24 |
| Julgados, acha o caso | 25 | 27 | 25 |
| Normas, conteúdo certo | 27 | 29 | 27 |

Entre as rodadas, uma correção só:
- a skill pede o link do texto integral só quando a ficha não basta;
- trecho de 4.000 caracteres em PAS e CRSFN;
- ementa curta nos índices por tema, ano e processo;
- título no índice das decisões antigas;
- mapas de produto apontando para os julgados.

Ressalvas da r2:
- na r2, o modelo ainda mencionava o link em 25 das 30 respostas de julgados, quase sempre como oferta depois de uma resposta já completa. A skill passou a proibir a oferta como complemento. Na r3 (só julgados, mesmo protocolo), as menções caíram para 6, das quais 4 necessárias, e o placar ficou em 23/30 tudo certo e 27/30 caso certo; a diferença para a r2 está em perguntas sem relação com a mudança (busca por tema e redação de ressalvas), dentro da variação entre rodadas;
- o acórdão `crsfn-14361` junta dois julgamentos (Ac. 48/2018 e 141/2018) no mesmo arquivo, defeito da conversão anterior a esta fase;
- seguem falhando por busca P10 e P24 (decisão de 1997);
- dois gabaritos estão defasados (julgados P17, normas P29) e foram contados como na r1.

Respostas e notas em `dados/fase-6/` (fora do Git).

## Reprodução

```
python3 scripts/auditoria_julgados.py universo
python3 scripts/auditoria_julgados.py sortear --semente 20261103
python3 scripts/auditoria_julgados.py sortear --semente <S> --estratos <bloco/estrato,...> --amostra-anterior <amostras já usadas>
python3 scripts/auditoria_julgados.py insumos --amostra fontes/amostra-fase3b.json --saida <pasta>
python3 scripts/auditoria_julgados.py rodar --lotes <pasta> --paralelo 4
python3 scripts/auditoria_julgados.py comparar --amostra fontes/amostra-fase3b.json --saidas <pasta>
```

As fontes ficam em `dados/fase-2d/cache`, fora do Git.

## Atualização automática

As taxas de erro publicadas acima (normas e julgados) medem a construção do acervo, por amostragem. Elas não medem cada atualização quinzenal. A atualização tem a conferência própria descrita aqui.

**O que é conferido em cada atualização**

Entra sem revisão humana só o item que passa por todas as verificações abaixo:

1. A conversão foi feita por script, a partir de fonte oficial, e há uma segunda leitura independente do mesmo texto que cobre pelo menos 99% dele.
2. Os testes automáticos do repositório passam, inclusive a validação dos arquivos e a conferência dos índices.
3. Nenhum CPF, RG ou caractere de controle aparece nos arquivos alterados.
4. Um revisor por IA, que só vê os insumos do lote, não marca nada.
5. A mudança toca só os arquivos esperados para os itens detectados, e nenhum julgado existente é reescrito.
6. Nas normas alteradas por ato, o texto novo se explica pelo ato: toda linha nova aparece nele.

Se uma verificação falha, a mudança não entra sozinha e fica à espera de uma pessoa, com o motivo anotado.

**O que vai para revisão humana**

- texto lido por OCR;
- revogação de norma;
- vigência diferida (dispositivo com data própria para entrar em vigor);
- norma ou documento novo fora do perímetro do acervo (a decisão de incluir é de uma pessoa);
- ato que altera uma norma com histórico por ato (o histórico é reconstruído por IA e conferido contra o consolidado oficial);
- qualquer item que o revisor por IA marque.

**Período de observação**

Hoje todas as mudanças estão em período de observação: o processo propõe e uma pessoa aprova cada uma, inclusive as que cumpririam o critério acima. O critério só passa a valer sem aprovação depois desse período.

**Entre o ato e o consolidado**

Quando um ato altera uma norma e o texto consolidado oficial ainda não saiu, o arquivo da norma continua com a redação anterior. Ela traz um aviso no campo `incerteza` e aparece na lista "Atos publicados ainda não aplicados" do índice. Confira o ato alterador antes de citar o dispositivo.

**Limites**

- A defasagem esperada é de até cerca de duas semanas entre a publicação na fonte e a entrada no acervo. O índice de cada plugin informa "Fontes conferidas até AAAA-MM-DD".
- A conferência da atualização é por regra e por testes, não por auditoria cega de amostra. Uma nova auditoria por amostragem dará taxas novas, publicadas nesta página com a data.
- Ressalvas de fonte já registradas (OCR, ordem de linha no PDF, Glossário ANBIMA) valem também para itens novos da mesma natureza.
