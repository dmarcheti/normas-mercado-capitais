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

## Fase 2b: texto vigente por script (2026-10-28)

Inventário: `scripts/inventario_acervo.py` → `fontes/acervo.json` (site da CVM e Estoque Regulatório de 2026-09-08). Conversão: `scripts/texto_vigente.py`, sem LLM. Cobertura = fração das palavras da fonte, extraídas pelo `textutil` do macOS (conversor independente), presentes no Markdown antes de tirar o texto tachado do consolidado.

| Camada | Itens | Com texto | Nível de verificação |
|---|---|---|---|
| 1: Resoluções e Instruções | 152 | 152 | 33 consolidado-convertido, 116 ato-convertido, 3 pdf-extraido (Res. 1, 10 e 12) |
| 2: Pareceres e Ofícios-Circulares desde 2022 | 220 | 212 | 40 ato-convertido, 172 pdf-extraido |
| 3: leis e decretos | 29 | 29 | compilado-planalto; `teste_lei` com 0 diferença nas 29 |

- Instr. CVM 489: histórico por ato (Instr. 502/11 e 576/16), teste 1 com 0 linha fora do ato nos dois commits; sem teste 2, porque a CVM não publica consolidado.
- Cobertura com conferência independente: 189 normas, 184 com 99% ou mais. Abaixo: Res. CVM 89 (98,6%), 94 (98,5%), 100 (96,2%), 103 (96,1%) e 122 (94,0%), todas pela mesma causa: diagramas em caixa de texto (74 a 612 palavras), que o conversor não lê. Está no `incerteza` de cada uma.
- Notas de rodapé: 40 normas trazem a seção final "Notas de rodapé" (sem a âncora no texto).
- PDF sem conferência independente (175 normas, quase todas Ofícios-Circulares): só a regra de legibilidade (fração de palavras alfabéticas ≥ 0,5 e ao menos 50 palavras).
- Sem texto (8 Ofícios-Circulares, ficam como verbete no índice): SSE 03/26 e 02/26 (fonte Type3 sem mapa Unicode), SMI 02/23 (codificação de fonte), SEP 06/26, SSE 06/25, SSE 04/25, SNC/SSE/SIN 02/25 conjunto e SSE/SNC 02/25 (PDF escaneado). Só OCR resolve.
- Parecer de Orientação 34: o DOC da CVM é um RTF com a página escaneada como imagem; o texto veio do PDF.
- Leis: os rótulos de margem do Planalto ("(Vigência)", "Produção de efeito", "Vigência encerrada") saem do texto e do gabarito do teste; cada lei afetada diz isso no `incerteza`. Resíduo: 5 ocorrências no art. 136-A da Lei 6.404, coladas à nota "(Incluído pela Lei nº 13.129, de 2015)".
