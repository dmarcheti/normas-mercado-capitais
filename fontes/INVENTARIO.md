# Inventário de atos alteradores (8 resoluções CVM)

Fonte: páginas das resoluções em `conteudo.cvm.gov.br/legislacao/resolucoes/resolNNN.html`, lidas em 2026-10-28 por `scripts/inventario.py`. Dados completos em `fontes/inventario.json`. Datas de ato e de DOU vêm da página de cada ato. A lista "ALTERADA pela(s) Resolução(ões)" é a da própria CVM; não foi conferida contra o texto dos atos.

## Alteradoras por norma

| Norma | Ato | DOU | Alteradoras | Consolidado |
|---|---|---|---|---|
| Res. CVM 175 | 2022-12-23 | 2022-12-28 | 8: 181/23, 184/23, 187/23, 200/24, 206/24, 209/24, 214/24, 240/26 | DOCX e PDF |
| Res. CVM 160 | 2022-07-13 | 2022-07-14 | 5: 173/22, 180/23, 183/23, 208/24, 226/25 | DOCX e PDF |
| Res. CVM 60 | 2021-12-23 | 2021-12-24 | 4: 162/22, 179/23, 194/23, 226/25 | DOCX e PDF |
| Res. CVM 17 | 2021-02-09 | 2021-02-10 | 2: 162/22, 226/25 | DOCX e PDF |
| Res. CVM 30 | 2021-05-11 | 2021-05-12 | 2: 162/22, 179/23 | DOCX e PDF |
| Res. CVM 21 | 2021-02-25 | 2021-02-26 | 4: 162/22, 167/22, 179/23, 209/24 | DOCX e PDF |
| Res. CVM 80 | 2022-03-29 | 2022-03-30 | 11: 59/21, 162/22, 168/22, 173/22, 180/23, 183/23, 198/24, 204/24, 207/24, 226/25, 231/25 | DOCX e PDF |
| Res. CVM 50 | 2021-08-31 | 2021-09-02 | 2: 179/23, 245/26 | DOCX e PDF |

Total: 38 pares norma-alteradora, 24 atos distintos. Nenhuma das 8 normas está sem consolidado: as 8 páginas oferecem o texto consolidado em DOCX e em PDF (16 links, todos respondem com arquivo do tipo certo, conferido por requisição parcial). A Res. 175 também publica o consolidado em partes (Parte Geral e Anexos Normativos I a XI) em PDF. A redação original de cada norma está só em PDF no site da CVM.

## Piloto

Res. CVM 17 (agente fiduciário): regra do plano (menos alteradoras entre 17 e 60, com ao menos 2): 17 tem 2, 60 tem 4. Alteradoras do piloto: 162/22 (DOU 2022-07-14; no site só PDF e DOCX) e 226/25 (DOU 2025-03-07; também HTML). A 162/22 altera outras 4 das 8 normas (60, 30, 21, 80) e a 226/25 altera outras 3 (60, 80, 160): bom caso para o commit único de ato que altera mais de uma norma.

## Atos que alteram mais de uma das 8 normas

- 162/22: 17, 21, 30, 60, 80
- 179/23: 21, 30, 50, 60 (a ementa só cita a Res. 35; o ato "atualiza a denominação dos assessores de investimento em diversas resoluções")
- 226/25: 17, 60, 80, 160
- 173/22, 180/23, 183/23: 80 e 160
- 209/24: 21 e 175

## Pontos de atenção

- Res. 59/21 (DOU 2021-12-23) consta como alteradora da Res. 80, que só foi publicada em 2022-03-30. A ementa da 59 altera as Instruções CVM 480 e 481, não a Res. 80. Provável alteração prévia, em vigor junto com a 80; decidir o tratamento antes de rodar o histórico da 80. [verificar]
- A ementa nem sempre lista as normas alteradas (179/23); o campo `normas_na_ementa` do JSON é só pista. A lista da CVM, por norma, é a referência do inventário.
- Retificações no DOU existem para 21, 60, 160 e 175 (campo `retificada_dou` na página; fora do JSON). Republicação no site em 2022-12-02 para a 160 (erro material no art. 81, parágrafo único).
- Texto original das normas: só PDF no site da CVM; a biblioteca padrão do Python não lê PDF. Para a Task 6 será preciso o HTML do DOU, ou aceitar uma dependência para PDF (há `pypdf` instalado no Python do usuário; fora do projeto).
