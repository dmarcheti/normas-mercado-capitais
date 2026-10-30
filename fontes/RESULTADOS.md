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
