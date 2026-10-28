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
