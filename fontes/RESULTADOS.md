# Resultados dos testes de fidelidade (Fase 2)

Data: 2026-10-28. Teste 1: todo texto novo de um commit de ato aparece no texto do ato (`scripts/teste_ato.py <commit>`). Teste 2: a norma final é igual ao consolidado DOCX da CVM, descontadas as divergências aceitas de `fontes/divergencias-aceitas.json` (`scripts/teste_final.py <id>`). Leis: teste de conversão contra a página do Planalto (`scripts/teste_lei.py <id>`). Cada divergência está descrita em `fontes/DIVERGENCIAS.md` e no campo `incerteza` da norma.

## Teste 1, por commit de ato

| DOU | Ato | Tipo | Linhas fora do ato | Observação |
|---|---|---|---|---|
| 2022-05-13 | 59 | alteracao | 0 |  |
| 2022-07-14 | 162 | alteracao | 0 |  |
| 2022-09-14 | 167 | alteracao | 0 |  |
| 2022-09-21 | 168 | alteracao | 0 |  |
| 2022-12-01 | 173 | alteracao | 1 | § 6º no lugar do § 5º do ato (o § 5º já fora incluído pela Res. CVM 59); divergência registrada |
| 2023-02-15 | 179 | alteracao | 0 |  |
| 2023-03-23 | 180 | alteracao | 0 |  |
| 2023-03-30 | 181 | alteracao | 0 |  |
| 2023-03-31 | 175 | retificacao | 96 | a retificação usa "(...)" no lugar do resto da linha; o teste não confere esse formato; divergência registrada |
| 2023-05-12 | 183 | alteracao | 0 |  |
| 2023-06-02 | 184 | alteracao | 0 |  |
| 2023-09-28 | 187 | alteracao | 0 |  |
| 2023-11-20 | 194 | alteracao | 0 |  |
| 2024-02-02 | 198 | alteracao | 0 |  |
| 2024-03-13 | 200 | alteracao | 0 |  |
| 2024-06-05 | 204 | alteracao | 0 |  |
| 2024-07-08 | 206 | alteracao | 0 |  |
| 2024-08-14 | 207 | alteracao | 0 |  |
| 2024-08-14 | 208 | alteracao | 0 |  |
| 2024-08-27 | 209 | alteracao | 0 |  |
| 2024-10-01 | 214 | alteracao | 0 |  |
| 2025-03-07 | 226 | alteracao | 0 |  |
| 2025-07-04 | 231 | alteracao | 0 |  |
| 2026-03-06 | 240 | alteracao | 0 |  |
| 2026-07-03 | 245 | alteracao | 0 |  |

## Teste 2, por resolução

| Norma | Atos aplicados | Diferenças não aceitas | Divergências aceitas |
|---|---|---|---|
| Res. CVM 17 | 2 | 0 | 1 |
| Res. CVM 21 | 4 | 0 | 380 |
| Res. CVM 30 | 2 | 0 | 6 |
| Res. CVM 50 | 2 | 0 | 7 |
| Res. CVM 60 | 4 | 0 | 35 |
| Res. CVM 80 | 11 | 0 | 264 |
| Res. CVM 160 | 5 | 0 | 188 |
| Res. CVM 175 | 9 | 0 | 128 |

## Leis (teste de conversão)

| Lei | Diferenças |
|---|---|
| lei-6385 | 0 |
| lei-6404 | 0 |
| lei-14430 | 0 |
| lei-9514 | 0 |
| lei-10931 | 0 |
| lei-8668 | 0 |
| lei-11076 | 0 |
| lei-13986 | 0 |
| lei-14711 | 0 |
| lei-14754 | 0 |
| lei-12431 | 0 |
| lei-10406 | 0 |

## Fase 2b: texto vigente por script (2026-10-28; correções em 2026-10-29)

Inventário: `scripts/inventario_acervo.py` → `fontes/acervo.json` (site da CVM e Estoque Regulatório de 2026-09-08). Conversão: `scripts/texto_vigente.py`, sem LLM. Fontes baixadas em 2026-10-28 (`baixado_em`); conferência em 2026-10-29 (`verificado_em`). Cobertura = fração das palavras da fonte, lidas por um extrator independente, presentes no Markdown (palavras = letras e dígitos; "_" separa). Extrator independente: `textutil` do macOS para DOCX, DOC e HTM; pypdf para PDF, cujo texto da norma vem do PDFKit do macOS.

| Camada | Itens | Com texto | Nível de verificação | Cobertura ≥ 99% |
|---|---|---|---|---|
| 1: Resoluções e Instruções | 152 | 152 | 33 consolidado-convertido, 116 ato-convertido, 3 pdf-extraido | 149 de 152 |
| 2: Pareceres e Ofícios-Circulares desde 2022 | 220 | 220 | 40 ato-convertido, 172 pdf-extraido, 8 ocr | 174 de 212 conferidos |
| 3: leis e decretos | 29 | 29 | compilado-planalto | `teste_lei` com 0 diferença nas 29 |

- Instr. CVM 489: histórico por ato (Instr. 502/11 e 576/16), teste 1 com 0 linha fora do ato nos dois commits; sem teste 2, porque a CVM não publica consolidado.
- Camada 1 abaixo de 99%: Res. CVM 100 (98,1%), 103 (98,1%) e 122 (97,1%). Não falta texto: o `textutil` lê duas vezes cada diagrama (o Word grava a caixa de texto em duas cópias) e o conversor lê uma; descontada a cópia, as três passam de 99,8%.
- Camada 2 abaixo de 99% (38 ofícios, mínima 94,5% no SIN 06/24): o pypdf, lado da conferência, parte palavras ("op eracionalização", "Ins titucionais"); conferido por amostra nas 5 mais baixas, sem perda no texto da norma. Por esse defeito o pypdf deixou de ser o extrator.
- Diagramas: 10 normas trazem o texto das caixas em blocos "> [Diagrama]", sem o desenho.
- Notas de rodapé: 40 normas, com âncora `[n]` no texto e a seção final "Notas de rodapé".
- OCR (Vision, macOS) nos 8 ofícios sem camada de texto (PDF escaneado ou fonte Type3): confiança média de 0,86 (SMI 02/23, tabela de tickers e ISINs) a 0,996; aceito com confiança média ≥ 0,85. Erros pontuais de leitura são esperados e estão avisados no `incerteza`.
- Ligaduras ("ﬁ") e espaços especiais dos PDFs normalizados (Unicode NFKC, preservando º e ª).
- Parecer de Orientação 34: o DOC da CVM é um RTF com a página escaneada como imagem; o texto veio do PDF.
- Leis: os rótulos de margem do Planalto ("(Vigência)", "Produção de efeito", "Vigência encerrada") saem do texto e do gabarito do teste; cada lei afetada diz isso no `incerteza`.

## Onda 1 do histórico: 29 resoluções (2026-10-29)

Plano da Fase 2b, seção 7. Fontes em `fontes/INVENTARIO.md` (seção "Onda 1"); divergências em `fontes/DIVERGENCIAS.md` (seção "Onda 1 do histórico"). A `main` foi remontada com as cadeias do núcleo, da Instr. 489 e da onda 1 em ordem de DOU: 89 commits de ato (38 originais, entre eles o da Res. 60, que também altera a 44 e a 47; 50 alterações; 1 retificação), seguidos dos commits de código e texto vigente. Backup local da `main` anterior: branch `backup/main-fase-2b`.

### Teste 1, por commit de ato

52 commits: as 50 alterações, o original da Res. 60 e a retificação da 175. Limpos: 45. Com linhas fora do ato, todas conferidas e registradas:

- Res. CVM 59/21 (altera a 81): 6 linhas dos Anexos C e H achatados pelo PDF em que entrou "(Revogado)", e a nota 3 partida; o único texto inserido é "(Revogado)".
- Res. CVM 204/24 (altera a 81): 3 linhas de estrutura (rótulo do Art. 34, § 1º; caput do Art. 81 separado do inciso I; título do Anexo O); o DOCX do ato não tem linha pontilhada.
- Res. CVM 207/24 e 236/25 (alteram a 47): 1 linha cada, falso positivo de tabela achatada no PDF (precedente da Res. 80).
- Res. CVM 220/24 (altera a 135): 1 linha, rótulo do Art. 152, § 1º.
- Res. CVM 173/22 e retificação da 175: casos da Fase 2, acima.
- Res. CVM 60/21 (original da 60, que altera a 44 e a 47): o texto do ato é a própria norma, fora de `alteradoras/`; conferido à parte, 0 linha fora do ato nas 44 e 47.

### Teste 2, por resolução

| Norma | Atos aplicados | Diferenças não aceitas | Divergências aceitas |
|---|---|---|---|
| Res. CVM 6 | 1 | 0 | 19 |
| Res. CVM 8 | 3 | 0 | 8 |
| Res. CVM 9 | 1 | 0 | 106 |
| Res. CVM 11 | 1 | 0 | 34 |
| Res. CVM 13 | 2 | 0 | 16 |
| Res. CVM 19 | 1 | 0 | 19 |
| Res. CVM 20 | 2 | 0 | 3 |
| Res. CVM 31 | 3 | 0 | 2 |
| Res. CVM 32 | 1 | 0 | 4 |
| Res. CVM 35 | 3 | 0 | 11 |
| Res. CVM 43 | 1 | 0 | 6 |
| Res. CVM 44 | 2 | 0 | 3 |
| Res. CVM 45 | 5 | 0 | 84 |
| Res. CVM 46 | 1 | 0 | 7 |
| Res. CVM 47 | 4 | 0 | 12 |
| Res. CVM 53 | 1 | 0 | 3 |
| Res. CVM 54 | 2 | 0 | 8 |
| Res. CVM 67 | 1 | 0 | 7 |
| Res. CVM 77 | 1 | 0 | 15 |
| Res. CVM 81 | 2 | 0 | 449 |
| Res. CVM 86 | 1 | 0 | 33 |
| Res. CVM 88 | 2 | 0 | 94 |
| Res. CVM 135 | 2 | 0 | 118 |
| Res. CVM 161 | 3 | 0 | 10 |
| Res. CVM 166 | 1 | 0 | 4 |
| Res. CVM 193 | 3 | 0 | 6 |
| Res. CVM 210 | 1 | 0 | 18 |
| Res. CVM 215 | 1 | 0 | 40 |
| Res. CVM 232 | 1 | 0 | 111 |

Divergências aceitas: 1.250 entradas novas, quase todas de forma (títulos em caixa alta, assinatura eletrônica, numerais por extenso, tabelas dos anexos achatadas no PDF da redação original). As de conteúdo, com [verificar no DOU]: Res. 19, art. 3º, II, e art. 26, IV (retificações de 2021 não obtidas); Res. 81, Anexo C, item 8 (o ato 59 revoga só a alínea e; o consolidado risca o item inteiro); Res. 210, art. 15, parágrafo único ("no" × "do" investidor; retificação de 2025-06-23 não obtida). Res. 166: vale a aplicação literal do ato ("Parágrafo único" e "§ 2º"); o consolidado renumera.

`teste_final` passou a aceitar cópia idêntica de uma entrada (a mesma divergência em dois dispositivos tem duas entradas iguais; a segunda não acusa "aceita não usada" quando a primeira já cobriu as linhas do mesmo contexto).


### Tabelas restauradas do consolidado (2026-10-29)

Nas normas com original tirado do PDF da CVM, três tabelas viraram uma linha corrida ilegível: Res. 47, Anexo B; Res. 81, Anexo N; Res. 88, Anexo D. Um commit de forma, depois do histórico, devolveu a tabela do consolidado da CVM, com as mesmas palavras do trecho achatado (conferido palavra a palavra). Na Res. 88, a nota (1) do Anexo D, que está no PDF e não no consolidado, ficou depois da tabela. Ficam em linhas, por decisão: a Res. 45, Anexo A (o consolidado põe os incisos de cada grupo numa célula; em linhas, cada inciso é o que os atos alteram), e os formulários da Res. 88, Anexos G e H, e da Res. 135, Anexo B. Teste 2 refeito nas três: 0 diferença não aceita.

## Retificações do DOU (2026-10-29)

Lidas no in.gov.br pelo navegador; HTML salvo em `dados/fontes/manual/` (fora do Git), resumo e endereços no DOU em `dados/fontes/manual/retificacoes-dou-2026-10-29.md`. Sete mudam texto e viraram commits na data do DOU (um commit por retificação, arquivo em `alteradoras/NNNN-retificacao-AAAA-MM-DD.md`): Res. 19 (2021-03-02 e 2021-04-01), Res. 21 (2021-03-04, republicação dos Anexos D e E), Res. 60 (2023-01-06), Res. 86 (2022-07-08), Res. 160 (2022-12-05) e Res. 210 (2025-06-23). As de 19 e 210 eram as diferenças de conteúdo aceitas com [verificar]; o consolidado da CVM estava certo. A republicação da Res. 21 tirou 317 das 380 divergências aceitas da norma.

Teste 1 dos commits de retificação: 19 e 21 limpos; 60, 86, 160 e 210 com 1 linha cada, a linha corrigida, porque a retificação cita só o trecho (mesmo caso da retificação da 175). Teste 2: 0 diferença não aceita nas seis.

Sem mudança de texto: Res. 45 (2021-09-10), 64 (2022-02-09), 88 (2022-05-04), 173 (2023-01-06; o acervo já tinha o "§ 6º", o que explica a exceção do teste 1 da Fase 2), 204 (2024-06-19), 239 (2026-01-16) e 21 (2021-03-09, data no título da republicação). Res. 81, Anexo C, item 8: a republicação da Res. 59 no DOU de 2022-05-13 diz "5.l e 8.e"; o acervo está certo.

## Fase 2c: camadas 4 (CMN e BCB) e 5 (ANBIMA e B3) (2026-10-29)

Inventário por script: `scripts/inventario_bcb.py` (API da busca de normas do BCB: 2.128 normas vigentes), `scripts/inventario_b3.py` (páginas de regulamentos e manuais da B3), `scripts/inventario_anbima.py` (páginas de código da ANBIMA, lidas no navegador, porque parte da lista é montada por JavaScript). Perímetro da camada 4: `scripts/perimetro_camada4.py` (regra por assunto mais a revisão das ementas, com o motivo de cada decisão em `fontes/perimetro-camada4.json`). Conversão: `scripts/texto_vigente.py --camada 4|5`, sem LLM. Cobertura como na Fase 2b; extrator independente: `textutil` do macOS para o HTML do BCB (convertido por `scripts/html_bcb.py`, só biblioteca padrão) e pypdf para PDF (texto da norma pelo PDFKit).

| Camada | Itens | Nível de verificação | Conferidos | Cobertura ≥ 99% |
|---|---|---|---|---|
| 4: CMN (57) e BCB (71) | 128 | 123 consolidado-convertido (HTML compilado pelo BCB), 4 pdf-extraido, 1 ocr | 127 | 124 de 127 |
| 5: ANBIMA (38) e B3 (59) | 97 | 97 pdf-extraido | 97 | 80 de 97 |

- Atos do BCB que só alteram normas do perímetro: sem arquivo (a compilação do BCB já traz a alteração); 77 verbetes nos subíndices `cmn.md` e `bcb.md`.
- Normas da camada 4 sem HTML na busca do BCB, tiradas do PDF da última versão: CC 3.934, Circ. 3.902, Res. CMN 2.843 e 3.042 (pdf-extraido) e Res. CMN 3.621 (PDF sem camada de texto, por OCR, sem conferência independente).
- Redação antiga tachada no HTML do BCB: 15.189 palavras retiradas nas 128 normas; 15 tabelas preservadas em Markdown (as de diagramação, de uma célula, viram parágrafos). O `textutil` descartava as tabelas do HTML do BCB, por isso o conversor próprio.
- Abaixo de 99% (3 na camada 4, mínima 92,9% na Res. CMN 2.843; 17 na camada 5, mínima 87,5% no Comunicado de Supervisão de Ofertas da ANBIMA): conferido item a item, nenhum perde texto. As palavras que faltam são pedaços que o pypdf, lado da conferência, parte ("resolu" "ção", "informaçã o de ve") ou símbolos de fórmula; no Código dos Processos da ANBIMA, a diferença está só no sumário com linhas pontilhadas (página 2).
- Camada 5: em 10 PDFs assinados da ANBIMA, a página final de registro das assinaturas eletrônicas (nomes, e-mails, IP e localização dos signatários) foi retirada do texto e da conferência, com aviso no `incerteza`. O Regulamento do FILCB e o Manual de Normas de Direito de Acesso da B3 citam CNPJ de empresa (FILCB, Banco B3, Laqus, SL Tools); por decisão do Diogo, o texto fica como está e esses 4 CNPJs entram na lista `CNPJS_PUBLICOS` de `scripts/varrer_termos.py`, que continua barrando qualquer outro. Tabelas dos PDFs ficam como texto; numeração e quebras podem estar deslocadas. Data: início de vigência informado pela entidade ou data no nome do arquivo; nos demais, a data do arquivo no servidor (Last-Modified) ou da leitura, com [verificar] no `incerteza`.
- Docling (conversor de PDF com modelos de layout) testado contra o DOU nos 10 originais da CVM tirados de PDF: texto igual ao do PDFKit (cobertura de 99,0% a 100%), tabelas recuperadas em parte (51% a 100% das células) mas partidas por página; 3 a 43 s por PDF e 1,8 GB de memória. Não adotado no lote.

## Fase 3: auditoria cega por amostragem (2026-10-30)

Método, amostra e resultado em `VERIFICACAO.md`. Scripts: `scripts/auditoria.py` (universo, sorteio, insumos, comparação), `auditoria_universo.py` e `auditoria_texto.py`. Amostras: `fontes/amostra-fase3.json` (semente 20261030; camada 4 sorteada de novo depois da correção) e `fontes/amostra-fase3-reauditoria.json` (semente 20261031). Exceções de vigência: `fontes/vigencia-excecoes.json`.

- Camada 4: as 26 normas do CMN e do BCB alteradas cujo texto na busca de normas do BCB é a redação original passam a vir do PDF `_vN_L` da última versão (`scripts/bcb_versoes.py`). Ficam com `nivel_verificacao: pdf-extraido`. A conferência pelo pypdf fica abaixo de 99% em 24 das 31 normas da camada tiradas de PDF, porque o pypdf parte palavras. A ordem das palavras foi medida contra o pypdf: só a Res. CMN 1.502 tinha desvio relevante, e ela foi corrigida à mão.
- Legibilidade de PDF: tickers e ISINs contam como texto legível, e números puros saem da fração. O OC CVM/SMI 2/2023 deixa o OCR. Os outros 7 ofícios por OCR não têm camada de texto.

## Fase 2d: julgados da CVM e do CRSFN (2026-10-31)

15.000 julgados em 5 plugins: 10.501 decisões do Colegiado, 1.714 termos de compromisso, 1.419 PAS, 1.342 acórdãos do CRSFN em recurso de decisão da CVM e 24 arquivos anuais de decisões antigas (1978–2001). Por data: 3.448 de 2019 em diante, 6.531 de 2010 a 2018 e 5.021 até 2009. Scripts: `scripts/julgados_inventario.py`, `julgados_baixar.py`, `julgados_converter.py`, `crsfn.py`, `julgados_extracao.py`, `pii.py` e `indice.py`; regras na SPEC v0.5.0.

| Plugin | Julgados | Arquivos | Tamanho |
|---|---|---|---|
| `julgados-colegiado-2002-2008` (com as decisões antigas) | 2.983 | 3.208 | 45,1 MB |
| `julgados-colegiado-2009-2015` | 4.161 | 4.363 | 59,3 MB |
| `julgados-colegiado-2016-2026` | 3.381 | 3.734 | 77,5 MB |
| `julgados-pas` | 1.419 | 1.726 | 113,4 MB |
| `julgados-tc-crsfn` | 3.056 | 3.367 | 121,4 MB |

Limite do claude.ai: 200 MB e 5.000 arquivos por plugin. Normas fora do acervo citadas por menos de 10 julgados ficam num arquivo por família (`indices/norma-fora-outras-<família>.md`).

- **Conversão e conferência.** Nível de verificação: 4.156 `html-convertido`, 10.539 `pdf-extraido` e 305 `ocr`. Depois das correções da Fase 3b (texto de imagem em PDF nativo e faixa de imagem passaram pelo OCR), em 2026-11-04: 4.152 `html-convertido`, 10.025 `pdf-extraido` e 813 `ocr`. A conferência independente (pypdf ou texto do HTML) fica abaixo do limite em 4 decisões do Colegiado, marcadas no `incerteza`; nos casos abertos, a diferença é artefato (menu do HTML, palavras partidas pelo pypdf), não texto perdido.
  - Fase 3b: tabelas e cartas que vinham só como imagem dentro do PDF passaram a entrar por OCR, no ponto da página onde a imagem está (o julgado fica `ocr`, com "N página(s) por OCR" no `incerteza`). Em tabela lida por OCR, número pode sair trocado (dígito, vírgula, nota de rodapé lida como algarismo) e linhas de organograma saem fora de ordem; não há regra segura para corrigir. Número de tabela em julgado `ocr` deve ser conferido na `fonte_original` antes de ser citado.
- **Citações.** Amostra de 40 julgados conferida contra o texto: 39 certas (97,5%). No erro, a fonte escreve "Deliberação CVM nº 480/09" para outra norma. Correções no lote: ponto de milhar em intervalo de artigos ("1.009"), "Lei das Estatais" como Lei 13.303, conectivo colado ao número ("4ºe 5º", "132 e133").
- **Extração por LLM** (Haiku, `claude -p`, lotes de 25, validação item a item): tema em todos os julgados, exceto as 24 decisões antigas (um arquivo por ano, com dezenas de decisões); ementa onde a fonte não traz a sua (7.830 extraídas; 1.405 PAS com a ementa da CVM e 1.339 acórdãos com a do CRSFN). Custo equivalente na API: US$ 31,90.
  - 172 julgados ficam com a ementa montada do título: a ementa extraída foi reprovada pelo validador (nome de pessoa, dado pessoal ou tamanho) duas vezes.
  - Recorte da extração: nas decisões do Colegiado, a deliberação fica no meio da seção "Decisão" e o fim do documento é o anexo da área técnica. O recorte passou a levar os parágrafos de deliberação e o fim da seção; as 559 decisões cuja ementa dizia "sem decisão no recorte" foram reextraídas. Ficam 144 ementas que mencionam o recorte, a maioria de atas de pauta normativa em que a fonte não traz o texto da minuta.
  - 1.228 decisões do Colegiado, 81 termos de compromisso e 30 PAS ficam sem `resultado` (matéria sem deliberação de mérito ou texto sem o dispositivo).
- **Dados pessoais (D3).** Nome de pessoa só no corpo; CPF, RG, endereço residencial, telefone, e-mail pessoal, data de nascimento e conta bancária viram `[dado pessoal retirado]`. A varredura final achou CPF e RG que escapavam (hífen antes do número, "CPFMF", "RG n.º", "identidade nº", "RG/SSP/SP") e endereços residenciais (parêntese no meio do endereço, "nesta cidade", "reside na Rua", endereço depois do CPF, logradouro com apartamento); `pii.py` foi corrigido e 79 julgados reconvertidos. Varredura final: 0 CPF, 0 RG; e-mails só `@cvm.gov.br`. CNPJ fica no texto dos julgados (decisão C do plano).
- **Decisões antigas.** Os PDFs anuais trazem atas de anos anteriores; a `data` é a da primeira reunião do ano do arquivo. Atas com complemento antes da data ("COM O SUPERINTENDENTE GERAL", 1979) eram descartadas com a capa; corrigido, cobertura de 0,9926 a 1,0 nos 24 arquivos.
- **Termos de compromisso de 2004–2006** sem processo na listagem: o número do PAS vem do título ("PAS CVM Nº 27/99" → `27/99`). Três itens do Colegiado sem número publicado ficam com `processo` vazio (SPEC).
- **Teste de fumaça:** 5 perguntas via `claude -p` com a skill de cada plugin (PAS com FIDC em 2023, CRSFN e insider trading, dispensa em oferta de CRI, atas de 1979, TC e art. 11, § 5º, da Lei 6.385). As 5 respostas citam processo e data e trazem as ressalvas de fonte; a terceira apontou a ementa errada que levou à correção do recorte.

Exceções:

- `cvm-col-20250408-d3248`: a página responde HTTP 410; fica fora.
- CRSFN: 20 acórdãos sem fonte disponível (19 em `sei.economia.gov.br`, um deles da CVM, processo 19957.100008/2019-12, e `crsfn-14303`); 4 sem data da sessão (`crsfn-5440`, `crsfn-8252`, `crsfn-9248`, `crsfn-8542`). `crsfn-5991` (sem processo de origem no texto) e `crsfn-edcl-14324` (preâmbulo com codificação quebrada) são da CVM, mas a classificação automática não os pega.
- Três acórdãos do CRSFN (`crsfn-2959`, `crsfn-2912`, `crsfn-2824`) julgam PAS de 1993, 1996 e 1997 que não estão na lista de PAS da CVM.
- 19 julgados e 30 índices citam fundos e empresas cujo nome contém um termo da lista privada do pre-commit. Por decisão do Diogo (2026-10-31), entram na base: a lista privada passou a aceitar expressões liberadas (linhas com "+"), que valem só nas pastas de julgados; o mesmo termo fora dessas expressões continua barrando.

## Fase 3b: auditoria dos julgados (2026-11-03 a 2026-11-04)

Método e taxas em `VERIFICACAO.md`, seção Julgados. Aqui ficam as correções feitas por causa da auditoria e as exceções que não contam como erro.

Correções (todas com reconversão a partir da fonte, nunca sobre o texto publicado):

- **Recorte da extração.** A deliberação que acompanha um voto "a seguir transcrito" deixava o dispositivo fora do recorte, e 473 ementas falavam "do recorte". O recorte passou a levar a conclusão do voto; o validador reprova a ementa que cita o recorte; 10.297 julgados com ementa, tema ou resultado reextraídos.
- **Resultado do CRSFN.** Recurso de ofício negado mantém a absolvição; com recursos voluntários negados no mesmo acórdão, o resultado é `parcial` (110 acórdãos corrigidos; regra na SPEC).
- **Texto perdido no PDF.** A regra das linhas repetidas apagava qualquer linha que aparecesse em 3 ou mais páginas, com os dígitos normalizados, inclusive texto de mérito e notas "Doc. nº". Passou a valer só na borda da página (1.995 julgados).
- **Texto sobreposto.** PDFs que desenham o texto em camadas saíam com linhas repetidas e picadas (`cvm-pas-rj2014-3616`: 1.580 linhas duplicadas). As camadas viram uma linha (38 julgados).
- **Ordem das linhas.** Trecho deslocado pelo PDFKit (número de parágrafo, sobrescrito, itálico) volta ao lugar quando o pypdf confirma (1.221 PDFs).
- **Imagem em PDF nativo.** Tabelas e cartas que vinham só como imagem passam pelo OCR (448 julgados passaram a `ocr`).
- **OCR.** "§" lido como "8" ou "$", romanos de incisos ("Il", "VIll"), siglas ("PAiS", "CVMi"), CNPJ/ME antes de 2019.
- **Dados pessoais.** Passaporte; RG com órgão expedidor antes do número; regime de bens e profissão; nacionalidade antes de "com escritório"; endereço com ponto do OCR no meio; linha "CPF:" deformada pelo OCR; nome da testemunha no carimbo. "Residentes no Brasil", "no exterior" e "no país" deixaram de ser cortados como endereço (orações e citações restauradas). Política do corte conservador na SPEC.
- **Ementa sem nome.** Ente público ("Estado de São Paulo", "União Federal") e frase do voto lida como parte deixaram de virar `[pessoa física]` (25 ementas).
- **Metadados.** Termo de compromisso avulso usa a data de aprovação do texto, não a do nome do PDF (4); audiência pública sobre rito sumário é `normativo` (3); resultado de julgamento suspenso fica vazio na reconversão.
- **Depois da última rodada (20261108).** Nome de testemunha abreviado no bloco e por extenso no carimbo, e sem acento no carimbo, sai também; "Declaração de voto" em minúscula no meio da frase deixou de virar seção no CRSFN (26 acórdãos); CPF lido pelo OCR com ":" entre os grupos ("CPF: 008: ...") sai (1 julgado); linha "Brasil;" ou "– Brasil," do texto (fim de item, "B3 S.A. – Brasil, Bolsa, Balcão") deixou de ser tomada por timbre (11 linhas em 14 julgados); o NUL que a extração deixa no lugar de um glifo não lido vira "�", e o STX do hífen do SEI vira "-" (42 julgados; antes o grep tratava esses arquivos como binários).
- **Normas: ofícios SRE com NUL (v1.1.1, 2026-11-04).** A mesma limpeza passou para o pipeline das normas, e o validador reprova caractere de controle. 13 Ofícios-Circulares da SRE (2023 e 2024) reconvertidos da fonte com `texto_vigente.py --ids`: a fonte Calibri embutida mapeia um glifo (provavelmente a ligadura "fí" de "Ofícios") para U+0000, nem o PDFKit nem o pypdf o leem, e ele fica "�", com aviso no `incerteza`. Arquivos com caractere de controle em `plugins/`: 13 → 0.

Exceções (não contam como erro):

- Quatro julgados do inventário sem endereço de fonte publicado: `cvm-pas-19957-001275-2016-65`, `cvm-tc-19957-004515-2018-45-20190326`, `cvm-tc-19957-009525-2018-17-20190910` e `cvm-tc-19957-010505-2018-49-20191023`.
- CRSFN: 10 duplicatas (mesmo sha256 e mesmo corpo) apagadas. Grupos de PAS com o mesmo PDF e processos diferentes (julgamento conjunto) ficam, um arquivo por processo.
- `crsfn-14361`: o documento traz dois acórdãos (Ac. 48/2018, de 2018-02-20, e Ac. 141/2018, de 2018-06-26), registrado no `incerteza`.
- `crsfn-8543`: o PDF da fonte repete o texto do acórdão três vezes; o acervo reproduz e registra no `incerteza`.
- `cvm-pas-19957-016206-2023-85` cita "art. 545 da RCVM nº 160/2022", artigo que não existe; o índice reproduz a citação como está no texto.
- Decisões antigas (PDF anual de 1978 a 2001): um arquivo por ano, sem `tema` nem `resultado` por decisão.
- Taxonomia: `classe: multa-cominatoria` agrupa recurso de multa cominatória, taxa de fiscalização, mecanismo de ressarcimento de prejuízos e fundo de garantia; no resultado do Colegiado, recurso contra indeferimento da área técnica é `provido`/`nao-provido` (SPEC).
