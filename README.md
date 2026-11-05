# Normas do mercado de capitais

Acervo em Markdown de normas do mercado de capitais brasileiro (regulação e orientação da CVM, leis e decretos, normas do CMN e do BCB e autorregulação da ANBIMA e da B3), organizado para consulta por pessoas e por assistentes de IA: um arquivo por norma, um título por artigo, metadados de situação e de data-base no cabeçalho e o histórico de alterações preservado em commits, um por ato alterador. O objetivo é dar ao analista de crédito estruturado o texto consolidado e rastreável até a fonte, com a data até a qual cada norma foi atualizada.

## Aviso

Este material não é oficial e não substitui o Diário Oficial da União nem os sites dos órgãos e entidades de origem (CVM, BCB, ANBIMA, B3). O texto pode conter erros de conversão ou estar desatualizado em relação a atos publicados depois da data-base de cada norma. Confira sempre a fonte oficial antes de usar em parecer, contrato ou decisão.

## Status

Em construção (repositório privado). Acervo atual, em camadas declaradas (data-base 2026-10-28 nas camadas 1 a 3, 2026-10-29 na camada 5 e 2026-10-30 na camada 4):

1. **Regulação da CVM:** as 155 Resoluções CVM vigentes (as 154 do Estoque Regulatório da CVM de 2026-09-08, mais a Res. 249) e as 5 Instruções CVM ainda em vigor (438, 445, 489, 516 e 579, contábeis de fundos). Ficam fora as revogadas, as que só alteram outras e a Res. 26 (prorrogação de prazos de 2021, sem efeito atual [verificar]).
2. **Interpretação da CVM:** os 41 Pareceres de Orientação e os 179 Ofícios-Circulares editados desde 2022-01-01 (7 deles por OCR, porque o PDF da CVM não tem camada de texto). Os 421 anteriores a 2022 aparecem só como verbete no índice, com link. A CVM não publica a vigência de pareceres e ofícios.
3. **Leis e decretos:** 28 leis e 1 decreto no texto compilado do Planalto lido em 2026-10-28, sem histórico (Leis 6.385, 6.404, 4.728, 4.595, 14.430, 11.101, 13.506 e outras; ver `plugins/normas/normas/indices/leis.md`).

4. **CMN e BCB:** 128 normas vigentes que tocam mercado de capitais, fundos, securitização, crédito negociável e instituições do mercado (57 do CMN e 71 do BCB: Resoluções, Resoluções Conjuntas, Circulares, Cartas Circulares e Instruções Normativas), no texto compilado pelo BCB, sem histórico nem conferência contra o DOU: o da busca de normas, ou, nas 26 normas alteradas cujo texto na busca é a redação original, o PDF da última versão compilada (relido em 2026-10-30). Os atos que só alteram essas normas aparecem como verbete. Ficam fora política monetária, câmbio comercial, crédito rural, pagamentos de varejo, cooperativas e consórcios, prudencial e PLD; o critério de cada norma está em `fontes/perimetro-camada4.json`.
5. **Autorregulação:** 39 documentos vigentes da ANBIMA (códigos, regras e procedimentos, glossário, deliberações, pareceres e perguntas e respostas) e 59 da B3 (regulamentos, manuais de normas, manuais de procedimentos operacionais e glossários), extraídos dos PDFs. Texto de titularidade da ANBIMA e da B3, reproduzido para uso informativo e retirado a pedido; ver `plugins/normas/normas/autorregulacao/README.md`.

6. **Julgados (v1.1):** 14.990 julgados em 5 plugins `julgados-*`: 1.419 PAS julgados pela CVM, 10.501 decisões do Colegiado (2002 em diante), 1.714 termos de compromisso, 1.332 acórdãos do CRSFN em recurso de decisão da CVM e 24 arquivos anuais de decisões antigas (1978–2001). Cada julgado traz o texto da fonte, processo, data, relator, resultado, ementa (a da CVM ou do CRSFN, ou extraída por LLM e marcada `ementa_fonte: extracao`), tema e as normas citadas, com índices por ano, por tema e por norma, e o índice reverso de citações no plugin `normas`. Dados pessoais (CPF, RG, endereço, qualificação, testemunhas) saem do texto; o nome da parte fica. Julgado não é norma: diz o que a CVM ou o CRSFN decidiu num caso, com a redação das normas da época.

   **PAS de 2022 em diante.** A listagem de PAS julgados da CVM para em 2025-05 e não traz parte dos julgados de 2022 a 2025. Esse período entra também pelas notícias de resultado e pelos extratos de sessão do SEI (`scripts/julgados_noticias.py`): a base tem 264 PAS julgados de 2022 a 2025 e 25 de 2026 (data-base 2026-11-05). A ausência de um julgado na base não prova que ele não exista.

Cada norma informa o nível de verificação (`nivel_verificacao`): 38 normas têm histórico por ato desde a publicação original, um commit por ato com a data do DOU: 37 Resoluções CVM (o núcleo de fundos e securitização, 17, 21, 30, 50, 60, 80, 160 e 175, e as substantivas 6, 8, 9, 11, 13, 19, 20, 31, 32, 35, 43, 44, 45, 46, 47, 53, 54, 67, 77, 81, 86, 88, 135, 161, 166, 193, 210, 215 e 232) e a Instr. CVM 489; as demais têm o texto vigente convertido por script do consolidado ou do ato publicado pela CVM, ou do compilado do Planalto.

Conferência: `fontes/RESULTADOS.md` (testes por norma) e `fontes/DIVERGENCIAS.md` (onde o histórico e o consolidado da CVM diferem, e por quê).

As datas-base acima são as da construção do acervo. Daqui em diante elas avançam com a atualização quinzenal (seção seguinte).

## Atualização

A cada duas semanas, às quartas-feiras, um processo compara as fontes oficiais (CVM, BCB, Planalto, ANBIMA, B3 e CRSFN) com o acervo e aplica o que mudou. Ele usa os mesmos scripts da construção, com testes e um revisor por IA. A primeira execução agendada é a de 2026-11-18.

Se uma execução não acontece no dia (máquina desligada, feriado), ela roda na primeira oportunidade. Nada se perde, porque a comparação é com o acervo, e não com a execução anterior.

- **Entra sem revisão humana** só o que tem conferência independente: texto convertido por script de fonte oficial, com cobertura de pelo menos 99% e testes verdes.
- **Passa por revisão humana:** texto lido por OCR, revogação, vigência diferida, norma ou documento novo fora do perímetro, ato que altera uma norma com histórico por ato e qualquer item que o revisor por IA marque.
- **Hoje, tudo está em período de observação:** o processo propõe e uma pessoa aprova cada mudança.
- **Ato publicado, consolidado ainda não:** entre a publicação de um ato que altera uma norma e a chegada do texto consolidado oficial, a norma traz um aviso no campo `incerteza` e aparece na lista "Atos publicados ainda não aplicados" do índice (`plugins/normas/normas/indice.md`). Nesse intervalo, leia o ato alterador junto com a norma.
- **Versões:** a versão de cada plugin sobe quando o conteúdo dele muda. O claude.ai só baixa o conteúdo novo quando a versão sobe.
- **Até quando vale:** cada índice traz a linha "Fontes conferidas até AAAA-MM-DD". Espere uma defasagem de até cerca de duas semanas entre a publicação na fonte e a entrada no acervo.

As taxas de erro da seção Verificação medem a construção, não cada atualização. O que se confere em cada atualização está em `VERIFICACAO.md`, seção "Atualização automática".

## Verificação

Auditoria cega por amostragem da construção, em 2026-10-30, nas 5 camadas: 297 itens sorteados (263 na amostra e 34 na re-auditoria) (semente registrada), refeitos ou transcritos por um modelo que só via a fonte, e comparados com o acervo por script. Resultado por camada, método, erros achados e ressalvas em `VERIFICACAO.md`. Em resumo:

- Camada 1: zero erro de texto em 114 itens (taxa abaixo de 2,6% com 95% de confiança).
- Camada 2: zero erro em 22 itens fora do OCR (abaixo de 13,6%). Os 7 ofícios lidos por OCR têm erros pontuais de leitura: confira o PDF da CVM.
- Camada 3: zero erro em 28 itens (abaixo de 10,7%).
- Camada 4: 1 erro, corrigido. Depois da correção, zero erro em 50 itens (abaixo de 6%).
- Camada 5: 1 erro, sem correção. Ressalva: no Glossário ANBIMA, verbetes e definições podem estar desalinhados.

### Julgados

Auditoria cega por amostragem de 2026-11-03 a 2026-11-04, em seis rodadas (1.021 itens), com adjudicação de cada diferença contra a página da fonte. Na última rodada:

- Texto em PDF: zero erro em 20 decisões do Colegiado, 12 termos e 10 acórdãos do CRSFN; 2 erros em 20 PAS (linha fora de lugar).
- Texto por OCR (813 julgados, `nivel_verificacao: ocr`): 4 erros em 24 (tabela ou figura que é imagem, dígito de tabela, nome de testemunha num carimbo, este já corrigido). Ressalva: confira número de tabela na fonte.
- Dados pessoais: nenhum dado que ficou em 40 qualificações.
- Extração por LLM: ementa 2 erros em 40; resultado 2 em 80, corrigidos; tema zero em 80.

Método, todas as rodadas e ressalvas em `VERIFICACAO.md`, seção Julgados.

## Bateria de perguntas

30 perguntas com gabarito, cobrindo as 5 camadas, mais 2 fora do perímetro (`testes/bateria-v1.md`). Cada gabarito foi conferido na fonte oficial. As perguntas foram respondidas pelo Claude Sonnet 5.5, sem web, em dois modos:

- **com o acervo:** só lendo os arquivos do plugin;
- **sem o acervo:** sem nenhuma ferramenta.

Um Claude Opus 5.5 corrigiu as 60 respostas sem saber de que modo vinha cada uma. Em 2026-10-30:

| Camada | Perguntas | Conteúdo certo, com acervo | Conteúdo certo, sem acervo |
|---|---|---|---|
| 1. CVM | 9 | 9 | 1 |
| 2. Pareceres e ofícios | 5 | 3 | 2 |
| 3. Leis | 5 | 5 | 1 |
| 4. CMN e BCB | 5 | 5 | 0 |
| 5. ANBIMA e B3 | 4 | 3 | 0 |
| Fora do perímetro | 2 | 2 | 1 |
| **Total** | **30** | **27** | **5** |

Com o acervo, 26 respostas citaram o dispositivo certo e 29 informaram a data-base; sem ele, 4 e 0. As 3 respostas erradas com o acervo têm a mesma causa: ofício ou documento da ANBIMA sem artigos que o modelo não abriu, porque procurou na norma de base. É o ponto fraco da consulta.

### Julgados

30 perguntas sobre julgados (`testes/bateria-v2.md`), com gabarito conferido na página da CVM ou do CRSFN, respondidas com e sem os plugins de julgados e corrigidas às cegas pelo Claude Opus:

| Critério | Com os julgados | Sem os julgados |
|---|---|---|
| Acha o caso certo | 25 | 1 |
| Conteúdo certo | 27 | 2 |
| Ressalvas de fonte | 29 | 5 |
| Tudo certo | 24 | 1 |

As 6 falhas com os julgados são de busca: o caso está no acervo, mas a resposta não o achou.

## Mapas por produto

`plugins/normas/normas/mapas/` tem um mapa para CRI, um para FIDC e um para FII: que normas do acervo regem cada produto, por camada, com os dispositivos-chave e o caminho do arquivo. São mapas de navegação, não parecer.

## Instalação

Para quem for usar com um assistente de IA, ver `COMECE-AQUI.md`. No Claude Code:

```
/plugin marketplace add dmarcheti/normas-mercado-capitais
/plugin install normas@normas-mercado-capitais
/plugin install julgados-pas@normas-mercado-capitais
/plugin install julgados-tc-crsfn@normas-mercado-capitais
/plugin install julgados-colegiado-2016-2026@normas-mercado-capitais
```

Os plugins de julgados são independentes: instale só os períodos e tipos que usar (`julgados-colegiado-2002-2008` e `julgados-colegiado-2009-2015` para decisões mais antigas).

## Licenças, dados pessoais e retirada

**Atos oficiais.** Os textos de leis, decretos, resoluções, pareceres, ofícios e decisões da CVM, do CRSFN, do CMN e do BCB não são objeto de direito autoral (Lei 9.610/98, art. 8º, IV: "os textos de tratados ou convenções, leis, decretos, regulamentos, decisões judiciais e demais atos oficiais"). O que este repositório acrescenta a eles tem licença própria.

**O trabalho do repositório: CC BY 4.0** (`LICENSE`). Seleção, estrutura, frontmatter, índices, mapas, histórico por ato, notas e divergências. Pode copiar e adaptar, com atribuição.

**Código: MIT** (`LICENSE-codigo`). Os scripts em `scripts/`.

**Autorregulação (camada 5).** A pasta `plugins/normas/normas/autorregulacao/` não está sob nenhuma licença deste repositório: reproduz texto de titularidade da ANBIMA e da B3, para uso informativo e não comercial, e sai a pedido delas. O pedido segue o formulário abaixo; mais detalhes no README da pasta.

**Julgados.** São atos oficiais da CVM e do CRSFN, com o texto da fonte. O dado pessoal (CPF, RG, endereço, e-mail, telefone, data de nascimento, dados bancários, qualificação pessoal e nome de testemunha) é cortado e marcado `[dado pessoal retirado]`, pela política do `SPEC.md` (seção Julgados, subseção Corpo). Nome de parte, relator e demais agentes do processo ficam, nos termos do `SPEC.md`. O titular que queira a retirada de dado seu pede pelo formulário.

**Retirada.** O pedido é só pelo [formulário `retirada`](https://github.com/dmarcheti/normas-mercado-capitais/issues/new?template=retirada.yml) das issues do repositório. O projeto não tem e-mail de contato.
- **Não escreva o dado pessoal na issue**, que é pública. Informe o id ou o caminho do documento e o tipo de dado (por exemplo, "CPF" ou "endereço").
- O mantenedor atende o pedido e apaga a issue depois.
- A retirada vale da versão corrente em diante. Versões anteriores do histórico do Git e cópias de terceiros podem conter o texto.

**Aviso.** Este material não é aconselhamento jurídico. A fonte oficial prevalece, e cada norma traz o link para ela no frontmatter (`fonte_original` e `fonte_consolidada`). Veja também a seção Aviso, no início.
