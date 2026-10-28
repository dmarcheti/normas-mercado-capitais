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

- Res. 59/21 (DOU 2021-12-23) consta como alteradora da Res. 80, que só foi publicada em 2022-03-30. A ementa da 59 altera as Instruções CVM 480 e 481, não a Res. 80. Provável alteração prévia, em vigor junto com a 80; decidir o tratamento antes de rodar o histórico da 80. [verificar] Decidido na Fase 2 (seção "Fontes da Fase 2" ao final).
- A ementa nem sempre lista as normas alteradas (179/23); o campo `normas_na_ementa` do JSON é só pista. A lista da CVM, por norma, é a referência do inventário.
- Retificações no DOU existem para 21, 60, 160 e 175 (campo `retificada_dou` na página; fora do JSON). Republicação no site em 2022-12-02 para a 160 (erro material no art. 81, parágrafo único).
- Texto original das normas: só PDF no site da CVM; a biblioteca padrão do Python não lê PDF. Para a Task 6 será preciso o HTML do DOU, ou aceitar uma dependência para PDF (há `pypdf` instalado no Python do usuário; fora do projeto).

## Fontes da Fase 2 (2026-10-28)

O in.gov.br responde 403 a script e não foi acessado. O texto de cada ato vem de uma de três fontes: o ctresb/leis (GitHub, conversão fiel do HTML do DOU; o nome do arquivo é o slug do in.gov.br, que vira `url_dou`), o DOCX da CVM (`dados/fontes/cvm-NNNN.docx`, para os 11 atos sem arquivo no ctresb; `url_dou` vazio) ou foi salvo pelo usuário no navegador (HTML do DOU, `dados/fontes/manual/`, para as Res. 175, 80, 50 e 179 e a retificação da 175). Textos gravados em `dados/fontes/dou-NNNN.md` (33) e, para os atos alteradores, em `plugins/normas/normas/cvm/alteradoras/NNNN.md` (22 novos, com a 179 e a retificação da 175; 162 e 226 do piloto mantidos, o corpo do ctresb é idêntico ao deles). Código: `scripts/alteradoras.py`.

Colunas: texto do ato (originais e alteradoras) | DOU | `url_dou` no JSON | fonte do texto | normas do inventário tocadas.

| Ato | DOU | url_dou | Fonte do texto | Normas tocadas |
|---|---|---|---|---|
| 17 | 2021-02-10 | sim | ctresb/leis (original) | 17 |
| 21 | 2021-02-26 | sim | ctresb/leis (original) | 21 |
| 30 | 2021-05-12 | sim | ctresb/leis (original) | 30 |
| 50 | 2021-09-02 | sim | DOU, salvo pelo usuário no navegador em 2026-10-28 | 50 |
| 60 | 2021-12-24 | sim | ctresb/leis (original) | 60 |
| 80 | 2022-03-30 | sim | DOU, salvo pelo usuário no navegador em 2026-10-28 | 80 |
| 160 | 2022-07-14 | sim | ctresb/leis (original) | 160 |
| 175 | 2022-12-28 | sim | DOU, salvo pelo usuário no navegador em 2026-10-28 | 175 |
| 59 | 2022-05-13 | sim | ctresb/leis (sem DOCX; só PDF na CVM) | 80 |
| 162 | 2022-07-14 | sim | ctresb/leis + DOCX da CVM | 17, 21, 30, 60, 80 |
| 167 | 2022-09-14 | sim | ctresb/leis + DOCX da CVM | 21 |
| 168 | 2022-09-21 | não | DOCX da CVM | 80 |
| 173 | 2022-12-01 | sim | ctresb/leis + DOCX da CVM | 80, 160 |
| 179 | 2023-02-15 | sim | DOU, salvo pelo usuário no navegador em 2026-10-28 | 21, 30, 50, 60 |
| 180 | 2023-03-23 | sim | ctresb/leis + DOCX da CVM | 80, 160 |
| 181 | 2023-03-30 | não | DOCX da CVM | 175 |
| 183 | 2023-05-12 | sim | ctresb/leis + DOCX da CVM | 80, 160 |
| 184 | 2023-06-02 | não | DOCX da CVM | 175 |
| 187 | 2023-09-28 | não | DOCX da CVM | 175 |
| 194 | 2023-11-20 | não | DOCX da CVM | 60 |
| 198 | 2024-02-02 | não | DOCX da CVM | 80 |
| 200 | 2024-03-13 | sim | ctresb/leis + DOCX da CVM | 175 |
| 204 | 2024-06-05 | não | DOCX da CVM | 80 |
| 206 | 2024-07-08 | não | DOCX da CVM | 175 |
| 207 | 2024-08-14 | não | DOCX da CVM | 80 |
| 208 | 2024-08-14 | sim | ctresb/leis + DOCX da CVM | 160 |
| 209 | 2024-08-27 | sim | ctresb/leis (sem DOCX; só PDF na CVM) | 21, 175 |
| 214 | 2024-10-01 | não | DOCX da CVM | 175 |
| 226 | 2025-03-07 | sim | ctresb/leis + DOCX da CVM | 17, 60, 80, 160 |
| 231 | 2025-07-04 | não | DOCX da CVM | 80 |
| 240 | 2026-03-06 | sim | ctresb/leis + DOCX da CVM | 175 |
| 245 | 2026-07-03 | sim | ctresb/leis + DOCX da CVM | 50 |
| 175 retificação | 2023-03-31 | sim | DOU, salvo pelo usuário no navegador em 2026-10-28 | 175 |

Totais: 17 do ctresb (5 originais, 12 alteradoras; 10 com DOCX da CVM para conferência, 59 e 209 sem), 11 do DOCX, 4 do DOU salvo pelo usuário (originais 175, 80, 50 e ato 179), mais a retificação da 175. Nenhum texto pendente. HTML salvo em `dados/fontes/manual/`; DOU conferido na própria página (`publicado-dou-data`): 175 em 28/12/2022, 80 em 30/03/2022, 50 em 02/09/2021, 179 em 15/02/2023, retificação em 31/03/2023, iguais ao inventário.

### Retificações

- Res. 175: retificação do DOU de 2023-03-31 (`https://www.in.gov.br/web/dou/-/retificacao-474135111`; corrige o texto publicado no DOU de 2022-12-28, seção 1, p. 57 a 84). Texto em `dados/fontes/dou-0175-retificacao-2023-03-31.md` e `plugins/normas/normas/cvm/alteradoras/0175-retificacao-2023-03-31.md` (`numero` 175, `id` `cvm-res-175-retificacao-2023-03-31`, `data` = 2022-12-23 do ato retificado, `publicacao_dou` = 2023-03-31). No JSON: `retificacoes` na norma 175.
- Retificações de 21, 60 e 160: texto não obtido; a registrar como divergência no replay, se o teste acusar.

### Res. CVM 59/21: decisão (Task 2, Decisão 4 do plano)

Conclusão: a 59 entra na cadeia da Res. 80 como commit, depois da 80, com data do DOU de 2022-05-13 (não 2021-12-23). Não gera `alteradora_anterior`.

- O texto do ctresb é a republicação do DOU de 2022-05-13 (seção 1, p. 86), cuja ementa diz "Altera as Resoluções CVM nº 80 e nº 81, ambas de 29 de março de 2022" e cujo art. 1º diz "A Resolução CVM nº 80, de 29 de março de 2022, passa a vigorar com a seguinte redação". A publicação de 2021-12-23 é anterior à Res. 80 e alterava as Instruções CVM 480 e 481; o texto dela não foi obtido.
- O consolidado da 80 (`resol080consolid.docx`) cita a 59 em 29 notas, com a mesma redação do ato: por exemplo "Art. 26-A incluído pela Resolução CVM nº 59, de 22 de dezembro de 2021", "§ 5º incluído pela Resolução CVM nº 59..." (art. 25) e "Inciso II revogado pela Resolução CVM nº 59...". O texto do art. 26-A é igual ao do ato.
- A Res. 168/22 (art. 4º) altera "o item 7.3.j do Anexo A à Resolução CVM nº 59" e o consolidado da 80 mostra o item j do Anexo C "com redação dada pela Resolução CVM nº 168": a 59 tem de estar na cadeia antes da 168.
- Vigência da 59: 2023-01-02 (art. 9º). Como nos commits do piloto, o commit usa a data do DOU, sem `vigencia_inicio`.
- No JSON: `dou` da 59 passa a 2022-05-13 e `dou_original` guarda 2021-12-23. Ordem dos atos da 80 por DOU: 59 (2022-05-13), 162 (2022-07-14), 168 (2022-09-21), 173 (2022-12-01)...
- O original da 80 (`dou-0080.md`, DOU de 2022-03-30) não cita a Res. 59 e traz o texto anterior a ela: sem o art. 26-A, art. 41 com os incisos II e III, art. 67 com parágrafo único, art. 25 sem os §§ 5º a 7º. O art. 69 diz "Esta Resolução entra em vigor em 2 de maio de 2022" (vigência diferida da 80 em relação ao DOU de 2022-03-30). A republicação da 59 (2022-05-13) é posterior ao DOU e à vigência da 80, e à revogação da Instrução CVM 480 pelo art. 70, II: é a hipótese que explica a troca das remissões de ICVM 480/481 para Res. 80/81.
- Atenção: `scripts/inventario.py` regenera o JSON a partir do site da CVM e apaga `url_dou`, `dou_original`, `retificacoes` e o ajuste do `dou` da 59.
