# Divergências registradas

Casos em que o histórico montado e o consolidado da CVM (ou um teste de fidelidade) não coincidem, com a decisão tomada. Mais recente no fim.

## Res. CVM 17, piloto (2026-10-28)

### 1. Teste 1, commit da Res. CVM 162/22: falso positivo de pontuação

- Linha apontada: art. 5º, § 2º (nova redação dada pelo art. 8º da Res. 162).
- Causa: no ato, o parágrafo termina em `...disposição da CVM". (NR)`, com o ponto depois das aspas de fechamento da citação. A norma traz `...disposição da CVM.`, igual ao consolidado da CVM. O teste 1 só tira o `(NR)`, e as aspas fazem a linha não ser trecho literal do ato.
- Conferência: o texto da linha é idêntico ao do ato e ao do consolidado; só a aspa de fechamento foi retirada. Correção tentada: nenhuma alteração fiel do texto passa nos dois testes (manter a aspa suja o texto da norma; tirar o ponto faz o teste 2 falhar).
- Decisão: texto mantido. Sugestão para `scripts/teste_ato.py`: ignorar aspas na comparação (em `_compacto`).

### 2. Teste 2, versão final: art. 9º, caput, "sete" contra "7 (sete)"

- Ato (DOU, DOCX e HTML da CVM): `no prazo de até sete dias úteis`.
- Consolidado da CVM: `no prazo de até 7 (sete) dias úteis`.
- O restante do caput é igual. Parece ajuste editorial do consolidado, não conteúdo do ato.
- Decisão: vale o texto do ato (o commit só pode trazer o que o ato manda). Registrado em `incerteza` do frontmatter. Diferença de 1 linha no teste 2.

### Outras observações

- O ato da Res. 226 diz que a Res. 17 foi "publicada no DOU de 30 de março de 2022"; a publicação foi em 2021-02-10. Erro do ato; o histórico usa a data do DOU de 2021-02-10.
- Vigência diferida: a Res. 162 entrou em vigor em 2023-01-02 (DOU de 2022-07-14) e a 226 em 2025-03-10 (DOU de 2025-03-07). As duas já estão em vigor na data-base do acervo; os commits aplicam a nova redação na data do DOU, sem bloco "Vigente a partir de" e sem `vigencia_inicio`. O histórico mostra a data de publicação, não a de vigor.
- Anexo A: o art. 6º, § 2º da Res. 17 cita "o inciso XI do art. 1º do Anexo A desta Resolução". Nem o HTML do DOU nem o DOCX consolidado da CVM trazem Anexo A, e a página da norma no site da CVM não lista anexo. A referência parece pendente na própria norma; não há texto a transcrever. [verificar]

## Fontes da Fase 2, Task 2 (2026-10-28)

### 1. ctresb/leis contra o piloto (Res. 162 e 226)

- Texto convertido do ctresb (sem o título repetido e a assinatura, `**`, escapes, `<table>` HTML em tabela markdown) contra `alteradoras/0162.md` e `0226.md`: 0 diferenças no corpo. As 2 tabelas achatadas da 226 no ctresb (uma célula por parágrafo) foram restauradas com as tabelas do DOCX da CVM, com o texto do ctresb.
- Conferência token a token ctresb × DOCX da CVM (caixa, pontilhado, marcas de rodapé e assinatura eletrônica descartados): 167, 200, 226 e 240 idênticos; 162 só difere na pontuação "; e)" e em "Art. 10." do DOCX, e no que o ctresb acrescenta (notas); 245 só em erros de digitação das fontes. Diferenças relevantes nos itens 2 a 4.

### 2. Res. 173/22, art. 1º (art. 25 da Res. 80): "§ 5º" no DOU, "§ 6º" no DOCX

- ctresb (HTML do DOU): `§ 5º No caso de oferta pública de distribuição de valores mobiliários destinada exclusivamente a investidores profissionais que utilize o rito de registro automático...`.
- DOCX da CVM do ato e consolidado da 80: `§ 6º No caso de oferta pública ...`, com a nota "§ 6º incluído pela Resolução CVM nº 173". O § 5º do art. 25 já existe, incluído pela Res. 59 ("Para cumprimento do disposto nos incisos XII do § 3º e VIII do § 4º...").
- Decisão: `alteradoras/0173.md` é o texto integral do ato como publicado e não é editado para corrigir o ato: mantém "§ 5º", igual a `dados/fontes/dou-0173.md`. Como aplicar na Res. 80 (inserir como § 6º, já que o § 5º é o da Res. 59) é decisão do replay da 80, não do arquivo do ato. Retificação do DOU não verificada [verificar retificação]; registrado em `incerteza`. O teste 1 do commit da 173 vai acusar a linha "§ 6º" da norma contra o "§ 5º" do ato: divergência esperada, a registrar no `incerteza` da 80.

### 3. Res. 180, 183 e 208: o DOCX da CVM não traz parte do ato

- 180 e 208: as notas (1) a (9) do anexo (tipos de oferta) só existem no ctresb/DOU. 183: os anexos (Anexo A, com o Anexo J da Res. 80) só existem no ctresb/DOU; o DOCX termina no art. 5º. Decisão: vale o ctresb (DOU); `incerteza` registra. A 162 tem o mesmo padrão (notas de rodapé só no DOU), já tratado no piloto.

### 4. Res. 245/26: data e erros de digitação

- ctresb traz `data: 2026-07-03`; o slug, o título e o inventário dizem 1º de julho de 2026 (DOU 2026-07-03). Vale o inventário.
- Erros nas fontes, mantidos: "RESOLUÇÂO CVM nº" (ctresb) e "JUlHO" (DOCX); "Art. 16 ....... § 1º" no ctresb contra "Art. 16. § 1º" no DOCX (pontilhado de trecho omitido). `ementa_do_ato` aceita o "Â".

### 5. Res. 59/21: republicação, data do DOU e remissões

- O arquivo do ctresb é a republicação do DOU de 2022-05-13 (`publicacao: DOU de 13/05/2022, seção 1, p. 86`); o corpo diz "(Publicada no DOU de 23-12-2021, Seção 1, páginas 246 a 255)". O inventário (página da CVM) dá DOU 2021-12-23. O `fonte:` do frontmatter do ctresb traz um `*` no slug (`...-2021-*-399684303`); o nome do arquivo e a URL válida são `resolucao-cvm-n-59-de-22-de-dezembro-de-2021-399684303`.
- Decisão: `publicacao_dou` e `dou` do inventário = 2022-05-13 (primeira publicação do texto que altera a Res. 80); `dou_original` = 2021-12-23. Detalhe e evidências em `fontes/INVENTARIO.md`. A página da CVM dá `normas_na_ementa: [87]` para a 59 (o campo do JSON não foi corrigido; a ementa correta cita as Res. 80 e 81).
- Original da 80 (`dados/fontes/dou-0080.md`, DOU de 2022-03-30): não cita a Res. 59 e traz a redação anterior a ela (sem art. 26-A, art. 41 com os incisos II e III, art. 67 com parágrafo único, art. 25 sem os §§ 5º a 7º); art. 69: vigência em 2022-05-02. Confirma que a 80 nasceu sem o texto da 59 e que a 59 (republicação de 2022-05-13) é commit posterior. Texto do DOU, sem segunda fonte para conferir.
- A 59 também altera a Res. 81 (fora do acervo), o que o texto do ato mostra no art. 6º e 7º.

### 6. Res. 59 e 209: sem DOCX da CVM

- Só PDF no site da CVM. O texto vem do ctresb, sem segunda fonte para conferir; `fonte_consolidada` é o arquivo do ctresb e `sha256_fonte` o hash dele. Tabelas do Anexo A da 59 vêm do HTML do ctresb sem conferência. [verificar]

### 7. Outras

- Atos do DOCX (168, 181, 184, 187, 194, 198, 204, 206, 207, 214, 231): sem slug, `url_dou` vazio, `fonte_original` = URL do DOCX. A assinatura eletrônica do DOCX ("Assinado eletronicamente por ... Presidente") foi retirada do texto.
- Res. 168/22: a ementa do DOCX traz "CVMº 59" (erro de digitação da CVM, mantido).
- Res. 209/24 altera também as Res. 31, 32, 35 e 45 (fora do acervo).
- `scripts/inventario.py` regenera `fontes/inventario.json` a partir do site e apaga `url_dou`, `dou_original` e o `dou` ajustado da 59.

### 8. Textos salvos pelo usuário (HTML do DOU, 2026-10-28)

- Res. 175, 80, 50 (originais) e 179 (ato) vieram de `dados/fontes/manual/*.html` (bloco "texto-dou"), sem segunda fonte para conferir. Datas do DOU nas páginas iguais às do inventário. `url_dou` gravado no inventário para todas as ocorrências.
- Retificação da Res. 175 (DOU de 2023-03-31, `https://www.in.gov.br/web/dou/-/retificacao-474135111`): arquivo `alteradoras/0175-retificacao-2023-03-31.md`, `numero` 175, `id` `cvm-res-175-retificacao-2023-03-31` (fora do padrão `cvm-res-N`), `data` 2022-12-23 (do ato retificado), `ementa` descritiva escrita por nós (o DOU não traz ementa própria) e `incerteza` explicando que é retificação. No índice, o título sai "Resolução CVM nº 175/2022", igual ao do ato original. No JSON: `retificacoes` na norma 175. O replay da 175 decide como aplicar o texto retificado.
- Retificações de 21, 60 e 160: não fornecidas; ficam sem texto. Se o replay acusar divergência nesses atos, registrar aqui. [verificar]

## Fase 2: replay das 8 resoluções (2026-10-28)

Registro de cada cadeia, como gravado no replay. A decisão de cada caso está no item; o resumo vai também no `incerteza` da norma.

### Res. CVM 17

Casos do piloto, acima. Na Fase 2, a data de publicação errada citada no ato da Res. CVM 226/25 entrou no `incerteza`.

### Res. CVM 21

#### Divergências do replay da Res. CVM 21/2021 (2026-10-28)

Cadeia: original (DOU 2021-02-26), Res. CVM 162 (DOU 2022-07-14), 167 (DOU 2022-09-14), 179 (DOU 2023-02-15) e 209 (DOU 2024-08-27; só o art. 1º é da Res. CVM 21). Teste 2 contra `dados/resol021consolid.docx`: 0 diferença não aceita, 380 aceitas (uma por linha divergente; ver o item 4). Os itens 1 a 7 são as diferenças aceitas em `aceitas-propostas.json`; o item 8 reúne observações.

###### 1. Art. 33, inciso I, alínea c

- Ato: Res. CVM 162/22 (art. 9º).
- Causa: o ato traz o marcador de nota (5) e um espaço antes do ponto e vírgula ("valores (5) ;"); o consolidado da CVM não traz marcadores.
- Decisão: vale o texto do ato, sem a nota do anexo do ato; entrada em aceitas-propostas.json e menção no incerteza.

###### 2. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" antes dos anexos; o DOU não traz o bloco como texto normativo.
- Decisão: texto mantido sem o bloco; três entradas e menção no incerteza.

###### 3. Cabeçalhos dos Anexos A a E

- Ato: original (DOU 2021-02-26).
- Causa: o consolidado abre cada anexo com "ANEXO X À RESOLUÇÃO cvm Nº 21, DE 25 DE FEVEREIRO DE 2021" (no Anexo C, o título vem em linha separada); o DOU traz "ANEXO X" (no Anexo C, com o título na mesma linha).
- Decisão: vale o DOU; entradas em aceitas-propostas.json e menção no incerteza.

###### 4. Tabelas dos Anexos C, D e E: marcadores de lista e anotações

- Ato: original e Res. CVM 167/22 (Anexos D e E).
- Causa: o consolidado traz os marcadores de lista (a., b., i., ii.) e as anotações de alteração dentro das células ("Item 3.2 com redação dada pela Resolução CVM nº 167, de 13 de setembro de 2022" e equivalentes); o DOU traz as alíneas sem letra, com marcador "·" nas subalíneas e com o número das notas de rodapé nas células. Onde o ato da Res. CVM 167 reescreve a célula (Anexo E, item 3, alíneas d e e) o marcador do ato coincide com o do consolidado; no Anexo D, o ato escreve "3.2 Indicar" e "3.3 Fornecer", sem o ponto depois do número, que o consolidado tem.
- Decisão: vale o DOU e o ato; uma entrada por linha divergente (linhas de tabela) em aceitas-propostas.json e uma frase no incerteza.

###### 5. Notas de rodapé dos Anexos D e E

- Ato: original (DOU 2021-02-26).
- Causa: o texto das notas de rodapé 1 a 7 consta do DOU e não do consolidado.
- Decisão: texto mantido; sete entradas (norma) e menção no incerteza.

###### 6. Numeração do Anexo E, itens 6.3 a 8

- Ato: original (DOU 2021-02-26).
- Causa: o consolidado numera 6.3 duas vezes, depois 6.4, 6.5, "6. Grupo econômico" e "7. Estrutura operacional e administrativa"; o DOU numera 6.3 a 6.6, "7. Grupo econômico" e "8. Estrutura operacional e administrativa". A sequência do DOU é coerente com as remissões internas (por exemplo, item 6.3.c).
- Decisão: vale o DOU; cinco pares em aceitas-propostas.json e menção no incerteza. [verificar] se as retificações do DOU de 2021-03-04 e 2021-03-09 explicam a diferença.

###### 7. Contagem de tabelas

- Ato: original (DOU 2021-02-26).
- Causa: 3 tabelas na norma e 2 no consolidado; o texto do DOU usado (`dados/fontes/dou-0021.md`) traz uma linha em branco entre o item 7.2 e o item 8 do Anexo E, que parte a tabela em duas.
- Decisão: entrada "tabelas" (norma 3, consolidado 2) em aceitas-propostas.json e menção no incerteza.

###### 8. Observações

- Retificações da Res. CVM 21 no DOU de 2021-03-04 e 2021-03-09 (citadas na Res. CVM 209, art. 1º): não obtidas. O replay parte do DOU de 2021-02-26. [verificar] Constam do incerteza; não geram commit.
- Res. CVM 162/22, art. 9º: o ato reescreve as alíneas c e e do inciso I do art. 33 e não a alínea d; ficam "; e" em d e em e, como no consolidado.
- Res. CVM 167/22 (art. 1º): Anexo A, art. 1º, inciso I; Anexo D, item 3.2 (nova redação) e 3.3 (renumerado); Anexo E, item 3, alíneas d e e. Vigência 2022-10-03.
- Res. CVM 179/23: art. 3º, § 5º e art. 33, § 2º ("assessor de investimento"); vigência 2023-06-01. Os demais artigos do ato são de outras resoluções.
- Res. CVM 209/24: só o art. 1º é da Res. CVM 21 (art. 33, § 3º novo); vigência 2025-07-01, já em vigor em 2026-10-28. Os arts. 2º a 6º são das Res. CVM 31, 32, 35, 45 e 175 e não foram aplicados.

### Res. CVM 30

#### Divergências do replay da Res. CVM 30/2021 (2026-10-28)

Cadeia: original (DOU 2021-05-12), Res. CVM 162 (DOU 2022-07-14) e 179 (DOU 2023-02-15). Teste 2 contra `dados/resol030consolid.docx`: 0 diferença não aceita, 6 aceitas. Os itens 1 a 3 são as diferenças aceitas em `aceitas-propostas.json`; o item 4 reúne observações sem diferença no teste 2.

###### 1. Art. 11, inciso VIII

- Ato: Res. CVM 162/22 (art. 10).
- Causa: o ato traz o marcador de nota (7) depois de "e" no inciso VIII ("VIII - investidores não residentes; e (7)"); o consolidado da CVM não traz marcadores. O marcador (6) do inciso VII desaparece quando a Res. CVM 179/23 reescreve o inciso.
- Decisão: vale o texto do ato, copiado literalmente, sem a nota do anexo do ato; entrada em aceitas-propostas.json e menção no incerteza.

###### 2. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado da CVM termina com "Assinado eletronicamente por / MARCELO BARBOSA / Presidente"; o DOU, origem da norma, não traz o bloco como texto normativo.
- Decisão: texto mantido sem o bloco; três entradas em aceitas-propostas.json e menção no incerteza.

###### 3. Anexos A e B, cabeçalho

- Ato: original (DOU 2021-05-12).
- Causa: o consolidado abre cada anexo com "Anexo X à Resolução CVM nº 30, de 11 de MAIO de 2021"; o DOU traz "ANEXO X". Diferença tipográfica entre as fontes.
- Decisão: vale o DOU; duas entradas em aceitas-propostas.json e menção no incerteza.

###### 4. Observações

- Res. CVM 162/22, art. 10: o dispositivo do ato não fecha as aspas nem traz "(NR)"; a redação foi aplicada normalmente (artigo 11, incisos VII a IX; o inciso IX é novo).
- Vigências: Res. CVM 162/22 em 2023-01-02 e Res. CVM 179/23 em 2023-06-01, ambas já em vigor em 2026-10-28; as redações foram aplicadas na data do DOU de cada ato, e as datas constam do incerteza.

### Res. CVM 50

#### Divergências do replay da Res. CVM 50/2021 (2026-10-28)

Cadeia: original (DOU 2021-09-02), Res. CVM 179 (DOU 2023-02-15) e 245 (DOU 2026-07-03). Teste 2 contra `dados/resol050consolid.docx`: 0 diferença não aceita, 7 aceitas. O título do consolidado lista as Res. CVM 179/23 e 245/26, logo aguarda_consolidado_oficial fica false. Os itens 1 a 3 são as diferenças aceitas em `aceitas-propostas.json`; o item 4 reúne observações.

###### 1. Art. 7º, § 2º

- Ato: Res. CVM 179/23 (art. 10).
- Causa: o ato escreve "2º As regras, procedimentos e controles internos..." sem o símbolo "§"; o consolidado da CVM traz "§ 2º". O restante do parágrafo coincide.
- Decisão: vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 2. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" antes dos anexos; o DOU não traz o bloco como texto normativo.
- Decisão: texto mantido sem o bloco; três entradas e menção no incerteza.

###### 3. Cabeçalhos dos Anexos A, B e C

- Ato: original (DOU 2021-09-02).
- Causa: o consolidado abre cada anexo com "ANEXO X à Resolução CVM nº 50, de 31 de AGOSTO de 2021"; o DOU traz "ANEXO X".
- Decisão: vale o DOU; três entradas e menção no incerteza.

###### 4. Observações

- Res. CVM 179/23 (art. 10 do ato): art. 3º, § 2º; art. 6º, II; art. 7º, I, b), II e § 2º ("agentes autônomos de investimento" para "assessores de investimento"). Vigência 2023-06-01. A ementa do ato cita só a Res. CVM 35 (a mensagem de commit repete a da cadeia da Res. CVM 60, a pedido).
- Res. CVM 245/26: art. 16, § 1º, I (nova redação) e art. 17-A (novo, após o art. 17). Vigência 2026-07-15, já em vigor em 2026-10-28; aplicada direto, sem vigencia_inicio. As datas constam do incerteza.
- Art. 17-A, caput: o ato escreve "devem no limite de suas atribuições, adotar" (sem a vírgula depois de "devem"); mantido literalmente, e o consolidado coincide (sem diferença no teste 2).

### Res. CVM 60

#### Divergências do replay da Res. CVM 60/2021 (2026-10-28)

Cadeia: original (DOU 2021-12-24), Res. CVM 162 (DOU 2022-07-14), 179 (2023-02-15), 194 (2023-11-20) e 226 (2025-03-07). Teste 2 contra `dados/resol060consolid.docx`. Os itens 1 a 27 são as diferenças do teste 2 aceitas em `aceitas-propostas.json`; os itens 28 e 29 são resultados dos testes 1 e 2 que não cabem em aceita.

###### 1. Art. 33, § 4º

- Ato: Res. CVM 194/23 (art. 10, II).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 2. Art. 43-C, caput

- Ato: Res. CVM 194/23 (art. 7º).
- Causa: O ato fecha as aspas depois de Simples ("Renda Fixa - Simples".) e o consolidado da CVM omite o fecho. Vale o texto do ato; diferença editorial do consolidado.
- Decisão: Vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 3. Art. 52, inciso III-A

- Ato: Res. CVM 226/25 (art. 2º).
- Causa: O ato (Res. CVM 226, art. 2º) diz "sete dias úteis"; o consolidado da CVM diz "7 (sete) dias úteis". Vale o texto do ato; mesma diferença editorial da Res. CVM 17, art. 9º.
- Decisão: Vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 4. Art. 63, caput

- Ato: original (DOU 2021-12-24).
- Causa: Trecho omitido do artigo citado da Res. CVM 44: pontilhado longo no DOU e ".." no consolidado da CVM. Diferença tipográfica entre as fontes.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 5. Art. 64, inciso II

- Ato: original (DOU 2021-12-24), possível retificação do DOU de 2023-01-06.
- Causa: O DOU de 2021-12-24 diz "incisos V e VI do Anexo I" e o consolidado da CVM diz "Anexo A". Possível efeito da retificação da Res. CVM 60 no DOU de 2023-01-06, que não foi obtida. Vale o DOU. [verificar]
- Decisão: Vale o DOU original; entrada em aceitas-propostas.json e menção no incerteza. Se a retificação do DOU de 2023-01-06 for obtida, rever este item. [verificar]

###### 6. Art. 66, Anexo A da Res. CVM 47

- Ato: original (DOU 2021-12-24).
- Causa: O DOU junta "; e" e "II" ("; eII"), por falha de espaçamento da fonte; o consolidado da CVM tem o espaço. Diferença tipográfica; vale o DOU.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 7. Assinatura eletrônica

- Ato: consolidado da CVM.
- Causa: Bloco de assinatura eletrônica ao final do consolidado da CVM; o texto do DOU, origem da norma, não o traz como texto normativo.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 8. Anexo Normativo I, art. 2º

- Ato: Res. CVM 194/23 (art. 10, III).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 9. Anexo Normativo I, art. 3º

- Ato: Res. CVM 194/23 (art. 10, III).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 10. Anexo Normativo I, Capítulo III

- Ato: Res. CVM 194/23 (art. 10, IV).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso. No Capítulo III, o histórico mantém o título e acrescenta "(Revogado)"; o consolidado troca o título por "CAPÍTULO III - REVOGADO".
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 11. Anexo Normativo II, art. 3º, § 1º

- Ato: Res. CVM 194/23 (art. 10, V).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 12. Anexo Normativo II, art. 4º, §§ 1º a 4º

- Ato: Res. CVM 194/23 (art. 10, VI).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 13. Anexo Normativo II, art. 5º

- Ato: Res. CVM 194/23 (art. 10, VII).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 14. Anexo Normativo II, Capítulo III, Seção I

- Ato: Res. CVM 194/23 (art. 10, VIII).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso. Na Seção I, o histórico mantém o título e acrescenta "(Revogado)"; o consolidado troca o título por "Seção I - REVOGADA" e traz uma palavra solta ("para").
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 15. Anexo Normativo II, art. 7º, § 4º

- Ato: Res. CVM 194/23 (art. 10, IX).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 16. Suplemento A, art. 2º, incisos XIV e XV

- Ato: Res. CVM 194/23 (art. 5º).
- Causa: O ato (Res. CVM 194, art. 5º) só acrescenta os incisos XVI e XVII e não reescreve o XIV nem o XV; o histórico mantém o "; e" do XIV e o "." do XV do texto original. O consolidado da CVM ajusta os conectores (";" no XIV e no XV). Vale o texto do ato; diferença editorial do consolidado.
- Decisão: Vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 17. Suplemento A, art. 2º, § 4º

- Ato: Res. CVM 194/23 (art. 10, X).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 18. Suplemento C, tabela de experiências profissionais

- Ato: original (DOU 2021-12-24).
- Causa: Marcador de lista: o consolidado da CVM traz "•" nas células; o DOU não tem o marcador. Diferença tipográfica entre as fontes.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 19. Suplemento E, item 1.4-A

- Ato: Res. CVM 194/23 (art. 8º).
- Causa: O ato (Res. CVM 194, art. 8º) escreve "REVOLVÊNCIA" e "[SIM/NÃO]" em caixa alta; o consolidado da CVM escreve "Revolvência" e "[Sim/Não]". Vale o texto do ato; diferença editorial do consolidado.
- Decisão: Vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 20. Suplemento E, itens 1.10.1.1 a 1.10.1.3

- Ato: original (DOU 2021-12-24).
- Causa: O DOU não tem o espaço depois da vírgula (ou o tem em outro lugar) e o consolidado da CVM tem. Diferença tipográfica entre as fontes; vale o texto do DOU (origem da norma).
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 21. Suplemento F, item 1.9

- Ato: original (DOU 2021-12-24).
- Causa: O DOU não tem o espaço depois da vírgula (ou o tem em outro lugar) e o consolidado da CVM tem. Diferença tipográfica entre as fontes; vale o texto do DOU (origem da norma).
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 22. Suplemento F, itens 1.11.1.1 a 1.11.1.3

- Ato: original (DOU 2021-12-24).
- Causa: O DOU não tem o espaço depois da vírgula (ou o tem em outro lugar) e o consolidado da CVM tem. Diferença tipográfica entre as fontes; vale o texto do DOU (origem da norma).
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 23. Suplemento F, item 12.7.4

- Ato: original (DOU 2021-12-24).
- Causa: O DOU junta "contacom" (falta de espaço da fonte); o consolidado da CVM tem "conta com". Diferença tipográfica; vale o DOU.
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 24. Suplemento G, item 1.4-A

- Ato: Res. CVM 194/23 (art. 9º).
- Causa: O ato (Res. CVM 194, art. 9º) escreve "REVOLVÊNCIA" e "[SIM/NÃO]" em caixa alta; o consolidado da CVM escreve "Revolvência" e "[sim/não]". Vale o texto do ato; diferença editorial do consolidado.
- Decisão: Vale o texto do ato, copiado literalmente; entrada em aceitas-propostas.json e menção no incerteza.

###### 25. Suplemento G, item 1.8

- Ato: original (DOU 2021-12-24).
- Causa: O DOU não tem o espaço depois da vírgula (ou o tem em outro lugar) e o consolidado da CVM tem. Diferença tipográfica entre as fontes; vale o texto do DOU (origem da norma).
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 26. Suplemento G, itens 1.10.1.1 a 1.10.1.3

- Ato: original (DOU 2021-12-24).
- Causa: O DOU não tem o espaço depois da vírgula (ou o tem em outro lugar) e o consolidado da CVM tem. Diferença tipográfica entre as fontes; vale o texto do DOU (origem da norma).
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 27. Suplementos H a J

- Ato: Res. CVM 194/23 (art. 10, XI).
- Causa: O ato manda revogar o dispositivo; o histórico mantém a posição com "(Revogado)" (convenção do replay) e o consolidado da CVM escreve "- REVOGADO". Diferença editorial do consolidado; o normalizador (scripts/normalizar.py) só unifica REVOGADO depois de um prefixo de dispositivo com inciso. Nos Suplementos H, I e J, o histórico mantém o cabeçalho "SUPLEMENTO X À RESOLUÇÃO CVM Nº 60..." e acrescenta "(Revogado)"; o consolidado troca o cabeçalho por "SUPLEMENTO X - REVOGADO".
- Decisão: Texto mantido como está; entrada em aceitas-propostas.json e menção no incerteza.

###### 28. Teste 1, Res. CVM 194/23: difflib padrão aponta linhas que não mudaram

- Ato: Res. CVM 194/23.
- Causa: `difflib.unified_diff` (autojunk ligado) alinha mal a remoção do Capítulo III do Anexo Normativo I contra o Anexo Normativo II, e, ao que tudo indica por isso, acusa 76 linhas inalteradas como novas (todas do Anexo Normativo II e do Suplemento A, sem mudança de texto). Com `SequenceMatcher(autojunk=False)`, o mesmo teste 1 dá 0 linhas fora do ato. O teste oficial (`scripts/teste_ato.py`) usa o diff do git (`git show -U0`), que não deve ter esse problema; não pude rodá-lo (sem git neste replay).
- Decisão: texto mantido. Conferir com `scripts/teste_ato.py` no commit da 194. Sugestão: o procedimento do replay deve citar `autojunk=False` quando usar difflib em norma grande.

###### 29. Teste 2: contagem de tabelas (10 na norma, 17 no consolidado)

- Ato: Res. CVM 194/23 (revogação dos Suplementos H, I e J e de itens do Suplemento G) e layout das fontes.
- Causa: o consolidado da CVM mantém, riscadas, as tabelas dos itens revogados (Suplemento G, 1.13 e 1.13.1; formulários antigos; Suplementos H e I); depois da normalização, 8 das 17 tabelas do consolidado ficam sem nenhuma célula. O histórico não tem essas tabelas (o ato revoga e o replay deixa só "(Revogado)"). Das 9 restantes, o consolidado tem 1 a menos que a norma (o DOU parte em duas tabelas o que o DOCX traz em uma, em Suplementos C, E, F ou G).
- Decisão: não há como aceitar em `divergencias-aceitas.json` (a linha "tabelas: N na norma, M no consolidado" não é par de linhas). Fica como a única diferença do teste 2. Sugestão para `scripts/teste_final.py`: não contar tabelas cujas células ficam todas vazias depois da normalização e comparar a contagem só das demais, ou aceitar diferença de contagem por entrada.

###### 30. Retificação da Res. CVM 60 no DOU de 2023-01-06

- Ato: original; citada na Res. CVM 226, art. 2º ("retificada no DOU de 6 de janeiro de 2023").
- Causa: o texto da retificação não foi obtido. A única diferença do teste 2 que parece vir dela é a do item 5 (Art. 64, inciso II: "Anexo I" no DOU, "Anexo A" no consolidado). As demais diferenças têm causa identificada (revogação, tipografia, conectores, caixa alta).
- Decisão: DOU original mantido, retificação registrada no `incerteza` de todas as versões. [verificar]

### Res. CVM 80

#### Divergências do replay da Res. CVM 80/2022

Cada seção é uma ocorrência ou uma classe. Regra: quando o ato e o consolidado da CVM divergem, vale o ato (ou o DOU, no original); a divergência vai para esta lista e para o `incerteza` da norma. Seções 4 a 12 são as classes aceitas em `aceitas-propostas.json`.

##### 1. Item 7.3.j do Anexo C (Res. CVM 168/2022, Art. 4º)

- ato: 168 (DOU 2022-09-21)
- dispositivo: Anexo C, item 7.3.j
- causa: O Art. 4º do ato altera o "item 7.3.j do Anexo A à Resolução CVM nº 59", o texto que a Res. 59 levou ao Anexo C da Res. 80. O ato não cita a Res. 80 nesse artigo. O consolidado da CVM confirma a mudança no item 7.3.j do Anexo C ("Item j com redação dada pela Resolução CVM nº 168").
- decisão: Aplicado ao item 7.3.j do Anexo C: "j. se é membro independente, nos termos da regulamentação específica aplicável à matéria" (sem o ponto final do ato, como as demais linhas da tabela). O primeiro replay da cadeia não tinha aplicado esse artigo; foi corrigido na v3 e propagado até a v11. A linha entra no teste 1 como linha de tabela (seção 13) e, no teste 2, resta só a anotação do consolidado (seção 6).

##### 2. Parágrafo novo do Art. 25 numerado § 5º no ato (Res. CVM 173/2022)

- ato: 173 (DOU 2022-12-01)
- dispositivo: Art. 25, § 5º do ato; § 6º na norma
- causa: O Art. 1º do ato manda dar ao Art. 25 um "§ 5º No caso de oferta pública de distribuição ... prevista no inciso I do § 2º deste artigo", mas o Art. 25 já tinha § 5º ("Para cumprimento do disposto nos incisos XII do § 3º e ..."), de modo que aplicar o número do ato sobrescreveria o parágrafo existente. O consolidado da CVM numera o parágrafo novo como § 6º. A remissão do inciso I do § 2º ("sem prejuízo do disposto no § 5º") vem do ato e é igual no consolidado.
- decisão: O parágrafo entrou como § 6º, numeração do consolidado, sem outra alteração de texto; o inciso I do § 2º ficou como no ato. Único caso em que o número do dispositivo não é o do ato. Entra no teste 1 como linha fora do ato (seção 13) e no incerteza da v4.

##### 3. Contagem de tabelas

- ato: todos (Anexo D)
- dispositivo: tabelas
- causa: A tabela do Anexo D é uma só no consolidado (170 linhas) e duas na norma (97 + 73), porque o DOU deixa uma linha em branco entre "a. informar se o emissor segue as seguintes práticas recomendadas:" e "i. o diretor-presidente deve ser avaliado..." (item 20 do princípio 3.3). O texto das linhas é o mesmo. A norma tem 3 tabelas e o consolidado 2.
- decisão: Vale o DOU. Diferença aceita pela entrada "tabelas" (norma 3, consolidado 2).

##### 4. Títulos de capítulo em caixa alta

- ato: 80 (original)
- dispositivo: títulos de capítulo
- causa: O DOU escreve CAPÍTULO II a XI em caixa alta ("CAPÍTULO II - CATEGORIAS DE EMISSOR..."); o consolidado da CVM usa caixa mista ("Capítulo II - Categorias de Emissor...").
- decisão: Vale o DOU (original da Res. 80). Diferença aceita.

##### 5. Cabeçalho de anexo e bloco de assinatura

- ato: 80 (original)
- dispositivo: cabeçalhos de anexo
- causa: O consolidado abre cada anexo com "Anexo X à Resolução CVM nº 80, de 29 de março de 2022," e traz, depois do Art. 70, o bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente". A norma traz o título do DOU ("ANEXO X") e, por regra do replay, não traz o bloco de assinatura.
- decisão: Vale o DOU. Diferença aceita (um par por anexo A a K; assinatura só no consolidado).

##### 6. Anotações de alteração do consolidado que o normalizador não remove

- ato: 59, 162, 168, 180, 198 (anotações do consolidado)
- dispositivo: anotações de alteração
- causa: O consolidado repete, dentro de células de tabela e em parágrafos próprios, notas do tipo "Item 1.6 com redação dada pela Resolução CVM nº 180...", "Alíneas "b" e "c" com redação dada e alíneas "d" e "e" incluídas pela Resolução CVM nº 59..." e "Incisos X e XI com redação dada ... pela Resolução CVM nº 59" (Art. 25). A regex de nota do normalizador (prefixo de até 40 caracteres) não as pega. No item 8.6 do Anexo C ela apaga no consolidado as linhas "a. órgão" e "b. número total de membros", cujo texto é só o item mais a anotação; a norma as tem. O item 9.3 do Anexo C aparece como "9.3" sem ponto na norma (texto do ato 162) e "9.3." no consolidado.
- decisão: Vale o texto do ato; a anotação não é texto normativo. Diferença aceita.

##### 7. Marcadores de nota de rodapé e notas (1) a (105)

- ato: 80 (original), 198
- dispositivo: marcadores de nota de rodapé
- causa: O DOU traz, nos Anexos C e D, marcadores "(N)" colados ao texto dos itens e, depois do Anexo K, as notas "(1)" a "(105)". O consolidado não traz os marcadores nem as notas e, em alguns itens, deixa um hífen onde estava o marcador ("sobre-:"). Pela mesma razão diferem os marcadores de lista ("- " do DOU contra o item sem marcador) e as aspas simples de "cláusulas pétreas" nas mesmas linhas.
- decisão: Vale o DOU e o ato 198 (que reescreve as notas). Diferença aceita; um par por linha.

##### 8. Marca de revogação dos itens do Anexo B

- ato: 59
- dispositivo: marca de revogação
- causa: Os itens 1.28, 1.29, 5.8 e 5.9 do Anexo B ficam revogados pela Res. 59. O consolidado escreve "1.28 REVOGADO"; a norma, "1.28 (Revogado)", forma do replay.md. A normalização só unifica a marca quando o número vem seguido de ponto ou hífen.
- decisão: Mesma revogação, outra grafia. Diferença aceita.

##### 9. Numeral por extenso nos Arts. 33 e 34, V-A

- ato: 226
- dispositivo: numeral por extenso
- causa: O ato 226 escreve "em até sete dias úteis"; o consolidado traz "em até 7 (sete) dias úteis".
- decisão: Vale o ato. Diferença aceita (mesmo caso da Res. 17).

##### 10. Ponto final do parágrafo único do Art. 46

- ato: 168
- dispositivo: pontuação final
- causa: O ato 168 termina o parágrafo único do Art. 46 em "...regras previstas no Anexo K" seguido de aspas e (NR), sem ponto; o consolidado fecha com ponto.
- decisão: Vale o ato. Diferença aceita.

##### 11. Remissões que o consolidado corrigiu

- ato: 59 e 80 (original)
- dispositivo: remissões
- causa: O item 11.2 do Anexo C remete a "anexo 30-XXXIII" no texto do ato 59 (remissão ao anexo da antiga Instrução CVM 480); o consolidado escreve "anexo F". No § 1º do Anexo K o DOU traz "art. 2º" e o consolidado "art. 2o".
- decisão: Vale o ato (59) e o DOU. Diferença aceita; a remissão certa é a do consolidado e fica registrada aqui, sem alterar o texto.

##### 12. Marcadores de lista e caixa

- ato: 80 (original)
- dispositivo: marcadores de lista
- causa: No Anexo B o DOU numera as alíneas "a)" e "b)" e o consolidado "a." e "b."; no Anexo C o DOU escreve "a. nome" e o consolidado "a. Nome"; nas listas do Anexo C (itens 5.x, 8.1, 8.2, 11.x) o DOU traz o hífen "- " e o consolidado só o texto.
- decisão: Vale o DOU. Diferença aceita.

##### 13. Teste 1: linhas fora do ato por prefixo ou por forma de tabela

- ato: 59, 162, 168, 173, 180, 198
- dispositivo: ver causa
- causa: O teste 1 acusa linhas cujo texto está no ato mas cuja forma não: 59, "1.28 (Revogado)", "1.29 (Revogado)", "5.8 (Revogado)", "5.9 (Revogado)"; 162, as linhas de tabela dos itens 9.3 e 9.4 do Anexo C; 168, a linha de tabela do item 7.3.j; 173, o § 6º (seção 2); 180, as notas "(90) (Revogado)" e "(91) (Revogado)"; 198, quatro linhas de tabela (7.1.d iii e iv, 10.1.a iv e v) e as notas (1) a (9), (11), (14), (15), (17) e (38), cujo texto está no Art. 2º e no Art. 3º do ato e cujo prefixo "(N) " não está.
- decisão: Nenhum texto fora do ato; só o prefixo ou a moldura de tabela. Uma correção por ato não se aplica. Os atos 183, 204, 207, 226 e 231 passam limpos.

### Res. CVM 160

#### Divergências do replay da Res. CVM 160/2022

Cadeia aplicada: original (DOU 2022-07-14) e atos 173/22, 180/23, 183/23, 208/24 e 226/25. Cada seção abaixo vira uma frase no `incerteza` da norma (v5) e as diferenças do teste 2 que ela explica estão em `aceitas-propostas.json` (campo `ref`).

##### 1. Retificação da Res. CVM 160 no DOU de 2022-12-05 não obtida; art. 81, parágrafo único
- Ato: retificação no DOU de 2022-12-05 (citada nos atos 208/24 e 226/25) e republicação da CVM de 2022-12-02.
- Dispositivo: art. 81, parágrafo único.
- Causa: o DOU de 2022-07-14 traz "responsabilidade do , dos coordenadores" (erro material). O consolidado da CVM traz "dos coordenadores". Não há texto da retificação; a republicação do site da CVM não é ato do DOU.
- Decisão: sem commit de retificação. A norma mantém o texto do DOU; o par aparece no teste 2 e foi proposto como aceito; o `incerteza` registra o fato.

##### 2. Notas de rodapé do art. 87 (atos 180/23, 183/23 e 208/24)
- Dispositivo: art. 87, inciso I (marcadores) e bloco de notas ao final do art. 87.
- Causa: os atos trazem um anexo "NOTAS" com as notas (1) a (9), (1) a (7) e (1) a (9), respectivamente, mas não dizem onde elas entram. Os marcadores (1) a (9) estão no texto do inciso I dado pelo ato. As notas (8) e (9) dos atos repetem a numeração das notas (8) e (9) do Anexo B, colisão herdada do DOU. O consolidado da CVM não traz nenhuma nota de rodapé.
- Decisão: a cada ato, as notas do anexo do ato substituem o bloco de notas do art. 87 (da nota (1) até antes das notas do Anexo B), e o inciso I leva os marcadores do ato. O teste 2 acusa 11 linhas (inciso I e "NOTAS:" com as 9 notas); propostas como aceitas.

##### 3. Notas de rodapé e marcadores nos Anexos
- Dispositivo: Anexos (notas (8) a (18) do Anexo B e marcadores no texto dos itens 3, 9, 13, 11.3, 11.4, 12.3 e 12.5 dos Anexos B a E).
- Causa: o DOCX do consolidado não traz as notas de rodapé nem seus marcadores; o DOU traz.
- Decisão: vale o texto do DOU. 22 linhas no teste 2 (11 de notas, 11 de marcadores); propostas como aceitas.

##### 4. Anexos: marcador de seção, [●] e espaçamento
- Dispositivo: Anexos A a J, tabelas e itens com "[...]".
- Causa: o DOU escreve o marcador de seção entre aspas (Seção "#.#"), "[...]" e, em dois casos, junta palavras sem espaço ("ofertaHá", "Seção "#.#"do prospecto"). O consolidado escreve Seção #.# sem aspas, "[●]" e com espaço.
- Decisão: vale o texto do DOU; diferença editorial do consolidado. 248 linhas no teste 2 (algumas idênticas, aceitas por entrada única); propostas como aceitas.

##### 5. Anexo G: b.1.9 rotulado b.2.9 no DOU; b.1.10 e b.2.10 do ato 226
- Dispositivo: Anexo G, Série 1 (b.1.9) e linhas b.1.10 e b.2.10.
- Causa: o DOU rotula b.2.9 o item de título verde da Série 1 (o consolidado rotula b.1.9). O ato 226 escreve Seção '#.#' com aspas simples nas linhas b.1.10 e b.2.10; o consolidado escreve Seção #.#.
- Decisão: o ato vale; propostas como aceitas.

##### 6. Dispositivos revogados
- Dispositivo: art. 26, inciso VIII, alínea c, item 3 (ato 208) e art. 86, § 2º (ato 183).
- Causa: o consolidado escreve "3 - (Revogado)" e "§ 2º - REVOGADO"; a norma segue a convenção do acervo ("3. (Revogado)", "§ 2º (Revogado)").
- Decisão: diferença editorial; propostas como aceitas.

##### 7. Art. 26, inciso IX (ato 173)
- Causa: o ato 173 traz um espaço antes do ponto e vírgula depois de ("debêntures incentivadas emitidas por SPE"); o consolidado não.
- Decisão: vale o texto do ato; proposta como aceita.

##### 8. Art. 89, § 5º, caput (ato 226)
- Causa: o ato diz "sete dias"; o consolidado diz "7 (sete) dias" (mesmo caso do art. 9º da Res. 17).
- Decisão: vale o texto do ato; proposta como aceita.

##### 9. Assinatura eletrônica ao final do consolidado
- Causa: o consolidado termina com "Assinado eletronicamente por / MARCELO BARBOSA / Presidente"; a norma não traz a assinatura.
- Decisão: não é texto normativo; proposta como aceita.

##### 10. Contagem de tabelas (6 na norma, 8 no consolidado): sem aceita possível
- Causa: o consolidado traz, dentro da tabela do Anexo G, linhas de anotação de uma célula ("Alínea b.1.10 incluída pela Resolução CVM nº 226, de 6 de março de 2025." e a equivalente da b.2.10). O normalizador do teste apaga essas linhas e deixa uma linha vazia, que parte a tabela em três (cortes em "b.2) Série 2" e em "C. Outras informações"). A norma tem a tabela inteira.
- Decisão: não alterei a norma (partir a tabela estragaria a renderização). O mecanismo de aceitas não cobre contagem de tabelas; fica como a única diferença do teste 2. Sugestão para quem mantém `scripts/teste_final.py`: descartar a linha de anotação sem deixar linha vazia, ou contar tabelas depois de removê-las.

##### 11. Vigência e lista de atos do consolidado
- Os cinco atos já estavam em vigor em 2026-10-28 (173/22 em 2023-01-02; 180/23 em 2023-04-03; 183/23 em 2023-06-01; 208/24 em 2024-09-02; 226/25 em 2025-03-10). Redações aplicadas direto, na data do DOU de cada ato; datas no `incerteza`.
- O título do consolidado lista 173/22, 180/23, 183/23, 208/24 e 226/25; o sumário do DOCX omite o 226/25, mas o título principal o inclui. Por isso `aguarda_consolidado_oficial: false`.
- O ato 173/22 não teve divergência própria na parte da Res. 160.

### Res. CVM 175

#### Divergências do replay da Res. CVM 175/2022

Base: teste 2 sobre `dados/replay-0175/v9/index.md` contra `dados/resol175consolid.docx`. Regra: vale o texto do ato (DOU); o consolidado da CVM é o gabarito, não a fonte. Cada classe abaixo tem entradas em `aceitas-propostas.json` (campo `ref`) e uma frase no `incerteza` da norma. Resultado: 225 diferenças brutas; 210 cobertas por 114 entradas aceitas; 15 não aceitas (ver "Não aceitas").

##### D01. Campo em branco "[*]" × "[●]" (Suplementos B, C, E, F)
- Ato: o DOU grafa o campo em branco do formulário como "[*]".
- Consolidado: grafa "[●]".
- Decisão: vale o DOU. Diferença só de símbolo; aceita.

##### D02. Notas de rodapé do Suplemento B e numerais soltos
- Ato: o DOU traz as marcas de nota (i a xvii) dentro do texto da lâmina e, ao final do Suplemento B, o bloco "INSTRUÇÕES DE PREENCHIMENTO DA LÂMINA" (30 linhas, com a tabela das espécies de ativos).
- Consolidado: omite o bloco e as marcas, e deixa numerais de nota soltos ("1 2 3 4 5") nos Suplementos B, E e F.
- Decisão: vale o DOU (as instruções fazem parte do ato). Aceita.

##### D03. Espaçamento, pontuação, caixa e divisão de linhas de tabela
- Ocorrências: Anexo Normativo V, Seção IV ("Representação direta" no ato × "Representação Direta" no consolidado); Anexo Normativo VII, art. 11, §§ 1º e 2º ("§1º" × "§ 1º"); Suplemento C ("art.36" × "art. 36", espaço extra, linhas de tabela partidas de outro modo em "Taxa de gestão" e "Despesas totais pagas ao grupo econômico do administrador"); Suplemento E (vírgula em "conforme previsto", caixa alta em "ANTES DE INVESTIR"); Suplemento G (item 3 sem espaço antes de "(a+b+c+d)").
- Decisão: vale o ato; aceita. A contagem de tabelas não muda por causa dessas linhas.

##### D05. Texto do ato difere do consolidado
- Art. 3º, XXXIV e XXXV: o DOU traz taxa de ingresso (XXXIV) antes de taxa de gestão (XXXV); o consolidado inverte.
- Anexo Normativo II, art. 42, § 1º, I: o ato diz "o administrador, o gestor, a entidade registradora e o custodiante"; o consolidado omite "o administrador,".
- Suplemento C: o ato remete ao "art. 2º, inciso IX, do Anexo Normativo I"; o consolidado diz "inciso XI".
- Suplemento G, item h: "Classe de cotas de fundos de Investimento em Direitos Creditórios" no ato; "Classes de Cotas de Fundos de Investimento em Direitos Creditórios" no consolidado.
- Suplemento I, item 4: o ato numera "4. Amortizações de cotas do Mês de Referência"; o consolidado omite o "4.".
- Suplemento O, mesmo item: o consolidado traz uma aspa a mais.
- Decisão: vale o ato; aceita.

##### D06. Linhas e anotações que só existem no consolidado
- Art. 47 (linha solta "I -"), Art. 85 (linha solta "de"), assinatura eletrônica ao fim da parte geral (Art. 141), anotação "Alínea "e" com redação dada pela Resolução CVM nº 240" (Anexo Normativo II, art. 2º, XIII) e anotação "Itens 22, 23, 24 e 25 incluídos pela Resolução CVM nº 200" (Suplemento I).
- Decisão: não são texto dos atos; aceita.

##### D07. Arts. 70-A e 70-B do Anexo Normativo I
- Ato (Res. CVM 184): "Art. 70–A" e "Art. 70–B" com travessão, como parágrafo corrido. A norma grava o título de artigo "## Art. 70-A" (hífen) e o texto em linha própria, como em todo artigo.
- Consolidado: "Art. 70-A. texto" em uma linha só, que o conversor não reconhece como título.
- Decisão: diferença de formato; aceita.

##### D08. Pontuação literal do ato
- Art. 141, XXIII ("XXIII - a Instrução CVM nº 554" no ato; o consolidado traz "XXIII -a"), Anexo Normativo II, art. 4º, § 4º ("§ 4º." no ato) e art. 17, III ("..., ou" no ato; "; ou" no consolidado).
- Decisão: copiado literalmente do ato; aceita.

##### Não aceitas (defeitos conhecidos do teste final)
- Anexo Normativo III, art. 17 (Res. CVM 214): o consolidado marca "- REVOGADO"; a norma grava "(Revogado)". 2 linhas.
- Suplemento D, item 11: o ato traz a tabela em uma só; o consolidado a separa em duas. 13 linhas. A contagem final de tabelas fecha (42 × 42), mas por compensação: o Suplemento D tem 1 tabela na norma e 2 no consolidado, e o Suplemento G tem 3 na norma e 2 no consolidado.
- Total: 15 linhas, que não foram propostas como aceitas.

##### Por ato
- Res. CVM 181 (v1): teste 1 acusa 28 linhas, todas por deslocamento de bloco (taxa de administração e gestão do Art. 48, § 1º, VII, para o § 2º, XIX; §§ 2º a 4º do art. 30 do Anexo Normativo II para o art. 32). Conteúdo conferido contra o consolidado. Falso positivo.
- Retificação de 2023-03-31 (v2): teste 1 acusa 98 linhas porque a retificação cita só o trecho corrigido, com "(...)" no resto da linha. Os três itens sobre sumário não se aplicam, porque a norma não traz sumário. Art. 29, II, d: o "onde se lê" cita o trecho de modo impreciso; aplicado o "leia-se". Anexo Normativo II, art. 33, VI, c: o ato cita "inadimplência;" por "inadimplência; e"; aplicado o "leia-se".
- Res. CVM 184 (v3) e Res. CVM 214 (v8): a única linha acusada pelo teste 1 é a lista `- anexo-NN.md` do index (parte nova); falso positivo.
- Res. CVM 209 (v7): só o art. 6 altera a 175; os arts. 1º a 5º alteram outras resoluções.
- Res. CVM 214 (v8): o art. 5º, II, revoga a Res. CVM 39, que não integra a 175.
- Res. CVM 240 (v9): em vigor desde 2026-03-05 (assinatura), anterior ao DOU de 2026-03-06; aplicada na data do DOU.
- Suplementos C e E: o DOU grafa um caractere de controle (0x95) como marcador; mantido literal.


## Onda 1 do histórico: replay de 29 resoluções (2026-10-29)

Registro de cada cadeia, como gravado no replay. A decisão de cada caso está no item; o resumo vai também no `incerteza` da norma.

### Res. CVM 6

#### Divergências do replay da Res. CVM 6/2020 (2026-10-29)

Cadeia: original (DOU 2020-09-15) e Res. CVM 61 (DOU 2021-12-28; só o art. 8º é da Res. CVM 6). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol006consolid.docx`: 0 diferença não aceita, 19 aceitas em `aceitas-propostas.json` (itens 1 a 4).

###### 1. Títulos dos Capítulos II a XI

- Ato: original.
- Causa: o DOU traz "CAPÍTULO N - TÍTULO" em maiúsculas; o consolidado escreve "Capítulo N" e, nos Capítulos IV e XI, o título em caixa mista.
- Decisão: vale o DOU; dez entradas e menção no incerteza.

###### 2. Art. 22 (alteração da Instrução CVM nº 541)

- Ato: original.
- Causa: o DOU marca com linhas de pontos os trechos mantidos do art. 3º da ICVM 541; o consolidado traz só `"Art. 3º` e `Parágrafo único.`, sem os pontos.
- Decisão: vale o DOU; três entradas. As duas linhas só de pontos são iguais e a mesma entrada cobre as duas (o teste compara as diferenças por igualdade de conteúdo).

###### 3. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o texto do DOU usado não o traz.
- Decisão: três entradas e menção no incerteza.

###### 4. Cabeçalhos dos Anexos A a C

- Causa: `Anexo "X" à Resolução CVM nº 6, de 14 de SETEMBRO DE 2020` no consolidado; `ANEXO "X"` no DOU.
- Decisão: vale o DOU; três entradas e menção no incerteza.

###### 5. Observações

- Res. CVM 61/21, art. 8º: art. 1º, caput ("não está sujeita a registro"), com linha de pontos (parágrafo único mantido); art. 4º reescrito; art. 9º, parágrafo único reescrito.
- Art. 9º, parágrafo único: o ato fecha a citação com uma só aspa depois de "intermediária." e antes do (NR); retirada a aspa de citação, a advertência fica sem aspa de fechamento, igual ao consolidado.
- Vigência da 61/21: 2022-01-03, aplicada na data do DOU.

### Res. CVM 8

#### Divergências do replay da Res. CVM 8/2020 (2026-10-29)

Cadeia: original (DOU 2020-10-15; texto do PDF da CVM), Res. CVM 15 (DOU 2021-01-20), 61 (DOU 2021-12-28; só os arts. 9º a 13 são da Res. CVM 8) e 162 (DOU 2022-07-14; só o art. 7º é da Res. CVM 8). Teste 1: 0 linha fora do ato nos três passos. Teste 2 contra `dados/resol008consolid.docx` (convertido do `.doc` da CVM): 0 diferença não aceita, 8 aceitas em `aceitas-propostas.json` (itens 1 a 3).

###### 1. Títulos dos Capítulos II e III

- Ato: original.
- Causa: o original (PDF) traz os títulos em maiúsculas; o consolidado traz "Capítulo II - OFERTA..." e "CAPÍTULO III - prestação de informações".
- Decisão: vale o original; duas entradas e menção no incerteza.

###### 2. Art. 8º, inciso V

- Ato: original.
- Causa: o texto extraído do PDF quebra a advertência ("LEIA O DOCUMENTO DE INFORMAÇÕES ESSENCIAIS / ANTES DE APLICAR ... / ou [NESTA LETRA IMOBILIÁRIA GARANTIDA]") em três linhas; o consolidado a traz numa linha. É quebra de linha da extração do PDF, não diferença de redação.
- Decisão: v0 fica igual a `dados/fontes/dou-0008.md`; três entradas e menção no incerteza. Correção possível na fonte (`dados/fontes/dou-0008.md`, fora do escopo deste replay). [verificar no DOU]

###### 3. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" antes dos anexos; a redação original usada não traz o bloco.
- Decisão: três entradas e menção no incerteza.

###### 4. Observações

- Res. CVM 61/21, art. 9º: nova ementa. Aplicada no texto (parágrafo da ementa) e no campo `ementa` do frontmatter a partir da v2. O ato cita a Res. CVM 8 como "de 14 de setembro de 2020"; a data é 2020-10-14.
- Res. CVM 61/21, art. 10: reescreve o art. 2º só com o caput, sem linha de pontos; os §§ 1º e 2º (e incisos) saem do texto, como no consolidado. O art. 3º continua citando o § 2º do art. 2º.
- Res. CVM 61/21, arts. 11 a 13: nos Anexos B e C o ato fecha a citação logo depois do inciso (`";"`); a aspa de citação foi retirada.
- Vigências: Res. CVM 15/21 na publicação (2021-01-20); 61/21 em 2022-01-03; 162/22 em 2023-01-02. Todas anteriores à data-base; aplicadas na data do DOU.

### Res. CVM 9

#### Divergências do replay da Res. CVM 9/2020 (2026-10-29)

Cadeia: original (DOU 2020-10-28) e Res. CVM 185 (DOU 2023-07-13; texto do arquivo do ato no site da CVM). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol009consolid.docx` (convertido do `.doc` da CVM; o consolidado já traz a 185): 0 diferença não aceita, 106 aceitas em `aceitas-propostas.json` (itens 1 a 5).

###### 1. Art. 17, inciso VI

- Ato: original.
- Causa: "Cessão de Direitos Creditórios" com iniciais maiúsculas no DOU; minúsculas no consolidado.
- Decisão: vale o DOU; uma entrada e menção no incerteza.

###### 2. Título do Capítulo VI

- Ato: original.
- Causa: "Regras, Procedimentos e Controles Internos" em caixa mista no DOU; maiúsculas no consolidado.
- Decisão: vale o DOU; uma entrada.

###### 3. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o texto do DOU usado não o traz.
- Decisão: três entradas e menção no incerteza.

###### 4. Anexo B (conteúdo do formulário de referência)

- Ato: original.
- Causa: o DOU traz o formulário como tabela de uma coluna, com os marcadores das listas ("a.", "-"); o consolidado convertido do `.doc` traz os itens como parágrafos e, no item 5.1 e nas experiências profissionais (6.2 e 7.4), sem marcador. Contagem de tabelas: 1 na norma, 0 no consolidado.
- Decisão: vale o DOU; 92 entradas linha a linha (107 pares; pares repetidos, como "a. nome", contam uma vez porque o teste remove as diferenças iguais juntas) e uma entrada `tabelas` ("0" e "1"). Menção no incerteza.

###### 5. Cabeçalho e rodapé do consolidado

- Causa: a conversão do `.doc` leva para o corpo o cabeçalho e o rodapé de página (endereços da CVM, "RESOLUÇÃO CVM Nº 9, DE 27 DE OUTUBRO DE 2020", campo PAGE, HYPERLINK). Não é texto da norma.
- Decisão: uma entrada por linha distinta (8 entradas para 13 linhas), lado da norma vazio. Menção no incerteza.

###### 6. Observações

- Res. CVM 185/23, art. 1º: art. 4º reescrito inteiro, sem linha de pontos (caput e §§ 1º a 12; os §§ antigos saem); arts. 7º e 9º com linhas de pontos (só caput e os §§ citados mudam, "SIN" passa a "SSE"); art. 11 caput.
- Vigência: 2023-08-01, aplicada na data do DOU.
- Texto da 185 tirado do DOCX da CVM, não da página do DOU. [verificar no DOU]

### Res. CVM 11

#### Divergências do replay da Res. CVM 11/2020 (2026-10-29)

Cadeia: original (DOU 2020-11-19) e Res. CVM 179 (DOU 2023-02-15; só o art. 1º é da Res. CVM 11). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol011consolid.docx` (convertido do `.doc` da CVM): 0 diferença não aceita, 34 aceitas em `aceitas-propostas.json` (itens 1 a 6).

###### 1. Títulos dos Capítulos II e XII

- Ato: original.
- Causa: "Capítulo" em caixa mista no DOU; "CAPÍTULO" no consolidado.
- Decisão: vale o DOU; duas entradas.

###### 2. Art. 13, inciso XIV

- Ato: original.
- Causa: o consolidado traz "p ara" (espaço no meio da palavra); o DOU, "para".
- Decisão: erro de digitação do consolidado; vale o DOU; uma entrada.

###### 3. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / PRESIDENTE" no consolidado; o texto do DOU usado não o traz.
- Decisão: três entradas.

###### 4. Cabeçalhos dos Anexos A e B

- Causa: "ANEXO X À RESOLUÇÃO CVM Nº 11, DE 18 DE NOVEMBRO DE 2020" no consolidado; "ANEXO X" no DOU.
- Decisão: vale o DOU; duas entradas.

###### 5. Anexo B, tabela de despesas do Clube

- Ato: original.
- Causa: o DOU traz a tabela (8 linhas; "Taxa de administração" e a observação na mesma célula, cabeçalho em caixa mista); o consolidado convertido do `.doc` traz as células como 11 parágrafos, cabeçalho em maiúsculas. Contagem de tabelas: 1 na norma, 0 no consolidado.
- Decisão: vale o DOU; 19 entradas de um lado só e uma entrada `tabelas` ("0" e "1").

###### 6. Cabeçalho e rodapé do consolidado

- Causa: a conversão do `.doc` leva para o corpo o cabeçalho e o rodapé de página (endereços da CVM, título da norma, HYPERLINK).
- Decisão: uma entrada por linha distinta (6 entradas para 11 linhas).

###### 7. Observações

- Res. CVM 179/23, art. 1º: art. 17 reescrito inteiro (caput e parágrafo único; "agentes autônomos de investimento" passa a "assessores de investimento"); art. 20, § 1º, com linhas de pontos.
- Vigência: 2023-06-01, aplicada na data do DOU.

### Res. CVM 13

#### Res. CVM 13/2020: divergências do replay

Cadeia: original (DOU 2020-11-19) -> Res. CVM 64/22 (DOU 2022-02-08) -> Res. CVM 216/24 (DOU 2024-10-31).

Teste 1: 0 linhas fora do ato nos dois passos. Teste 2 (v2 contra resol013consolid.docx): 16 diferenças, todas de forma, propostas em aceitas-propostas.json.

1. Assinatura: o consolidado da CVM termina com "Assinado eletronicamente por / MARCELO BARBOSA / PRESIDENTE"; a página do DOU do original não traz o bloco nesse formato.
2. Títulos dos anexos: o consolidado escreve "ANEXO A À RESOLUÇÃO CVM Nº 13, DE 18 DE NOVEMBRO DE 2020" (idem B e C); o DOU traz só "ANEXO A", "ANEXO B" e "ANEXO C".
3. Cabeçalho e rodapé do .docx: nome da autarquia, endereços das sedes, site e título da resolução, repetidos nas quebras de seção, extraídos como texto pelo conversor.

Observações:
- A retificação da Res. CVM 64 publicada no DOU de 2022-02-09 não foi obtida [verificar]. Nos dispositivos da Res. 13 alterados pela Res. 64 (arts. 2º, 3º, 10, 14, 25 e Anexo A), a redação aplicada coincide com o consolidado da CVM.
- Anexo A, art. 1º, incisos II e III: revogados pela Res. CVM 64; o consolidado traz "– REVOGADO", que a normalização iguala ao "(Revogado)" do histórico. As alíneas a a d do inciso III saem com a revogação.

### Res. CVM 19

#### Divergências do replay da Res. CVM 19/2021 (2026-10-29)

Cadeia: original (DOU 2021-02-26) e Res. CVM 179 (DOU 2023-02-15; só o art. 2º é da Res. CVM 19). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol019consolid.docx`: 0 diferença não aceita, 19 aceitas em `aceitas-propostas.json` (itens 1 a 5). As retificações da Res. CVM 19 (DOU 2021-03-02 e 2021-04-01) não foram obtidas.

###### 1. Art. 3º, inciso II, e art. 26, inciso IV: redação do consolidado diferente do DOU

- Ato: original (provável retificação).
- Causa: o consolidado acrescenta no art. 3º, II "cuja metodologia e conteúdo tenham sido previamente aprovados pela CVM," e cita no art. 26, IV a "Deliberação CVM nº 783, de 17 de novembro de 2017"; o DOU de 2021-02-26 traz o texto sem o trecho e "nº 483". São diferenças de conteúdo, não de formato, e o mais provável é que venham das retificações não obtidas.
- Decisão: vale o DOU até a retificação ser obtida; duas entradas e menção no incerteza. Ao obter as retificações, aplicá-las como passo próprio e retirar estas entradas. [verificar no DOU]

###### 2. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o texto do DOU usado não o traz.
- Decisão: três entradas.

###### 3. Cabeçalhos dos Anexos A a F

- Causa: "ANEXO X à Resolução CVM nº 19, de 25 de FEVEREIRO de 2021" no consolidado; "ANEXO X" no DOU (no Anexo C, o DOU põe o título na mesma linha e o consolidado em linha própria).
- Decisão: vale o DOU; sete entradas.

###### 4. Anexo E, nota de rodapé e marcadores

- Causa: o DOU traz a nota de rodapé 1 (marcador colado em "Recursos humanos1" e o texto da nota depois da tabela) e o marcador "·" nas listas de experiências profissionais; o consolidado não traz nem uma nem outro.
- Decisão: vale o DOU; seis entradas (as listas de experiências aparecem duas vezes e cada entrada cobre as duas).

###### 5. Contagem de tabelas

- Causa: o texto do DOU usado traz uma linha em branco antes do item 8 do Anexo E, que parte a tabela em duas (3 na norma, 2 no consolidado).
- Decisão: uma entrada `tabelas` ("2" e "3").

###### 6. Observações

- Res. CVM 179/23, art. 2º: art. 1º, § 4º; art. 3º, § 2º, IV; art. 4º, § 7º ("agente autônomo de investimento" passa a "assessor de investimento"), todos com linhas de pontos.
- Vigência: 2023-06-01, aplicada na data do DOU.

### Res. CVM 20

#### Divergências do replay da Res. CVM 20/2021 (2026-10-29)

Cadeia: original (DOU 2021-02-26), Res. CVM 179 (DOU 2023-02-15; só o art. 3º é da Res. CVM 20) e 216 (DOU 2024-10-31; só o art. 2º é da Res. CVM 20). Teste 1: 0 linha fora do ato nos dois passos. Teste 2 contra `dados/resol020consolid.docx`: 0 diferença não aceita, 3 aceitas em `aceitas-propostas.json` (itens 1 e 2).

###### 1. Assinatura eletrônica

- Causa: o consolidado traz "Assinado eletronicamente por / Marcelo Barbosa / Presidente"; o DOU traz só "Marcelo Barbosa" (que casa com a linha do consolidado).
- Decisão: duas entradas e menção no incerteza.

###### 2. Cabeçalho do Anexo A

- Causa: "Anexo A à Resolução CVM nº 20, DE 25 de fevereiro de 2021" no consolidado; "ANEXO A" no DOU.
- Decisão: vale o DOU; uma entrada e menção no incerteza.

###### 3. Observações

- Res. CVM 179/23, art. 3º: art. 10 reescrito ("assessor de investimento"); vigência 2023-06-01.
- Res. CVM 216/24, art. 2º: art. 13, inciso V reescrito (alíneas a, com itens 1 e 2, e b); os incisos VI a VIII ficam (linha de pontos). Vigência 2025-07-01, já em vigor na data-base.

### Res. CVM 31

#### Divergências do replay da Res. CVM 31/2021 (2026-10-29)

Cadeia (fontes/INVENTARIO.md): original (DOU 2021-05-20), Res. CVM 174 (DOU 2022-12-06), Res. CVM 209 (DOU 2024-08-27), Res. CVM 220 (DOU 2024-11-12). Teste 1: 0 linha fora do ato em todos os passos. Teste 2 contra `dados/resol031consolid.docx`: 0 diferença não aceita, 2 aceitas em `aceitas-propostas.json`.

###### 1. Assinatura eletrônica

- O consolidado termina com "Assinado eletronicamente por / Presidente"; a fonte original, não. 2 entradas.

###### Observações

- Res. CVM 209/24, art. 2º: o ato dá nova redação ao art. 35 com o caput só, sem linha pontilhada para os parágrafos. Aplicado como nova redação do caput; §§ 1º e 2º mantidos, como no consolidado ("Caput com redação dada pela Resolução CVM nº 209").
- Res. CVM 220/24: texto do DOCX do ato na CVM (inventário sem página do DOU). Art. 15: incisos I e II e § 4º trocados, §§ 1º a 3º mantidos (linha pontilhada), incisos I e II do § 4º e §§ 5º a 7º incluídos. O antigo § 4º virou o § 6º com o mesmo texto.
- Vigência: 174/22 em 2023-01-02; 209/24 em 2025-07-01; 220/24 em 2025-01-02. Todas anteriores à data-base; redações aplicadas na data do DOU, na ordem do DOU.

### Res. CVM 32

#### Divergências do replay da Res. CVM 32/2021 (2026-10-29)

Cadeia (fontes/INVENTARIO.md): original (DOU 2021-05-20), Res. CVM 209 (DOU 2024-08-27). Teste 1: 0 linha fora do ato em todos os passos. Teste 2 contra `dados/resol032consolid.docx`: 0 diferença não aceita, 4 aceitas em `aceitas-propostas.json`.

###### 1. Assinatura eletrônica

- O consolidado termina com "Assinado eletronicamente por / MARCELO BARBOSA / Presidente"; a fonte original, não. 3 entradas.

###### 2. Título do Anexo A

- O consolidado traz "Anexo A à Resolução CVM nº 32, de 19 de maio de 2021"; o DOU, "ANEXO A". Uma entrada.

###### Observações

- Res. CVM 209/24, art. 3º: Art. 11 com linha pontilhada depois do rótulo (caput mantido); §§ 1º a 3º substituídos pelo texto do ato, com os incisos I a III do § 2º e I e II do § 3º.
- Vigência: 209/24 em 2025-07-01, anterior à data-base; redação aplicada na data do DOU.

### Res. CVM 35

#### Divergências do replay da Res. CVM 35/2021 (2026-10-29)

Cadeia: original (DOU 2021-05-27), Res. CVM 134 (DOU 2022-06-13), 179 (DOU 2023-02-15; só o art. 7º é da Res. CVM 35) e 209 (DOU 2024-08-27; só o art. 4º é da Res. CVM 35). Teste 1: 0 linha fora do ato em todos os passos. Teste 2 contra `dados/resol035consolid.docx`: 0 diferença não aceita, 11 aceitas em `aceitas-propostas.json` (itens 1 a 4).

###### 1. Capítulo II, título

- Ato: original.
- Causa: o consolidado traz "Capítulo II - DEFINIÇÕES"; o DOU traz "CAPÍTULO II - DEFINIÇÕES".
- Decisão: vale o DOU; uma entrada e menção no incerteza.

###### 2. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado traz "Assinado eletronicamente por / ... / Presidente" ao fim do texto; o DOU, origem da norma, não o traz.
- Decisão: duas entradas (só consolidado) e menção no incerteza.

###### 3. Anexo Normativo I: título e Capítulos I a VI

- Ato: original.
- Causa: o consolidado traz "Anexo Normativo I - ..." e "CaPÍTULO I" a "CaPÍTULO VI" (caixa mista); o DOU traz tudo em maiúsculas.
- Decisão: vale o DOU; sete entradas e menção no incerteza.

###### 4. Anexo Normativo I, Art. 1º

- Ato: original.
- Causa: o DOU traz "Art. 1oEste anexo", sem espaço; o consolidado traz "Art. 1o Este anexo". A linha não vira `## Art.` (o artigo do anexo fica como texto, como no DOU).
- Decisão: texto do DOU copiado literalmente; uma entrada e menção no incerteza.

###### Observações

- Art. 49 (Res. CVM 179/23): o ato fecha a citação com a aspa antes do ponto final ("e 48\". (NR)"); a aspa saiu com o (NR), como as demais aspas de citação.
- Vigência: 134/22 em 2023-01-02; 179/23 em 2023-06-01 (Seções III e IV do Capítulo VII-A em 2024-01-02); 209/24 em 2025-07-01. Todas anteriores à data-base; redações aplicadas na data do DOU.

### Res. CVM 43

#### Divergências do replay da Res. CVM 43/2021 (2026-10-29)

Cadeia: original (DOU 2021-08-18) e Res. CVM 179 (DOU 2023-02-15; só o art. 8º é da Res. CVM 43). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol043consolid.docx`: 0 diferença não aceita, 6 aceitas em `aceitas-propostas.json` (itens 1 a 3).

###### 1. Títulos dos Capítulos II e III

- Causa: "CAPÍTULO" em maiúsculas no DOU; "Capítulo" no consolidado.
- Decisão: vale o DOU; duas entradas.

###### 2. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o texto do DOU usado não o traz.
- Decisão: três entradas.

###### 3. Cabeçalho do Anexo A

- Causa: "Anexo A à Resolução CVM nº 43, de 17 de AGOSTO de 2021" no consolidado; "ANEXO A" no DOU.
- Decisão: vale o DOU; uma entrada.

###### 4. Observações

- Res. CVM 179/23, art. 8º: art. 2º, § 2º ("agentes autônomos de investimento" passa a "assessores de investimento"), com linhas de pontos.
- Vigência: 2023-06-01, aplicada na data do DOU.

### Res. CVM 44

#### Divergências do replay da Res. CVM 44/2021 (2026-10-29)

Cadeia: original (DOU 2021-08-24, ctresb/leis), Res. CVM 60 (DOU 2021-12-24, art. 63) e 216 (2024-10-31, art. 3º). Teste 1: 0 linhas fora do ato nos dois passos. Teste 2 contra `dados/resol044consolid.docx` (sha256 946d5e0f...): 0 diferenças não aceitas; o item 1 é a diferença aceita em `aceitas-propostas.json` (3 entradas).

###### 1. Assinatura eletrônica

- Ato: original.
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" depois do art. 25; o texto do original não a traz.
- Decisão: 3 entradas (só consolidado).

###### 2. Outras notas

- Res. CVM 60, art. 63: parágrafo único novo no art. 1º, depois do inciso III, como no consolidado.
- Res. CVM 216, art. 3º: repete o caput do art. 9º sem mudança e dá nova redação ao § 1º. Texto do ctresb/leis; a CVM só publica PDF do ato, sem DOCX para conferir.
- Retificação da Res. CVM 60 no DOU de 2023-01-06: não obtida [verificar].

### Res. CVM 45

#### Divergências do replay da Res. CVM 45/2021 (2026-10-29)

Cadeia (fontes/INVENTARIO.md, mais a Res. CVM 209/24 por decisão do coordenador em 2026-10-29): original (DOU 2021-09-02, texto do PDF da CVM), Res. CVM 65 (DOU 2022-02-15), 162 (DOU 2022-07-14; arts. 11 e 18, VIII e IX), 179 (DOU 2023-02-15; art. 9º), 209 (DOU 2024-08-27; art. 5º) e 235 (DOU 2025-11-24). Teste 1: 0 linha fora do ato nos cinco passos. Teste 2 contra `dados/resol045consolid.docx`: 0 diferença não aceita, 84 aceitas em `aceitas-propostas.json` (itens 1 a 7).

###### 1. Art. 14, parágrafo único (extração do PDF)

- Ato: original.
- Causa: o PDF da CVM, convertido, traz "Parágrafo único. do investigado ao Colegiado." e, na linha seguinte, "Da negativa de acesso fundada na hipótese de que trata este artigo, cabe recurso"; o consolidado traz a frase inteira e em ordem.
- Decisão: texto da fonte mantido; duas entradas; conferir no DOU.

###### 2. Prazos por extenso (Res. CVM 235/25)

- Ato: 235.
- Causa: o ato escreve "seis dias", "dez dias", "quinze minutos", "sessenta dias", "cento e vinte dias", "trinta dias", "dois titulares"; o consolidado escreve "6 (seis) dias" etc.
- Dispositivos: Art. 23, § 2º, II; Art. 25, § 4º; Art. 52; Art. 74, caput; Art. 75, caput e § 1º; Art. 86, § 3º; Anexo C, art. 1º, XXIII, a).
- Decisão: vale o ato; oito entradas.

###### 3. Ponto depois do rótulo "§ Nº-A"

- Atos: 65 (Art. 31, § 1º-A; Art. 57, §§ 2º-A e 2º-B) e 235 (Art. 74, § 1º-A, que também tem "quinze dias").
- Causa: o consolidado escreve "§ 1º-A." com ponto; o ato, sem ponto (o § 2º-C da Res. 65 já vem com ponto).
- Decisão: vale o ato; quatro entradas.

###### 4. Assinatura eletrônica

- O consolidado termina com "Assinado eletronicamente por / MARCELO BARBOSA / Presidente"; a fonte original, não. Três entradas.

###### 5. Títulos dos Anexos A a E

- O consolidado traz "ANEXO A à Resolução CVM nº 45, de 31 de agosto de 2021"; o PDF, tudo em maiúsculas. Cinco entradas.

###### 6. Anexo A: tabela achatada no PDF

- Ato: original (e as trocas das Res. 162, 179, 209 e 235 dentro dela).
- Causa: o PDF da CVM achata a tabela "GRUPO | INFRAÇÃO ADMINISTRATIVA | VALOR MÁXIMO" em linhas soltas, com o rótulo do grupo e o valor intercalados entre os incisos ("GRUPO II I – ..." numa linha só). O consolidado traz a tabela (1 tabela; a norma, 0) com as notas de alteração dentro das células.
- Aplicação: cada inciso alterado foi trocado na sua linha; incisos novos (Grupo III, XI; Grupo IV, IX a XI; Grupo V, X) entraram depois do último inciso do grupo.
- Conferência à parte (fora do teste 2): os 43 incisos dos cinco grupos, tirados das células do consolidado sem as notas, são iguais, um a um, às linhas da norma.
- Decisão: uma entrada "tabelas" (1 × 0), seis linhas do consolidado (cabeçalho e cinco grupos) e 53 linhas da norma; incerteza aponta a tabela achatada [verificar no DOU].

###### 7. Anexo C, art. 1º, XVII, d) (extração do PDF)

- A alínea saiu partida em duas linhas ("... fundos mútuos de privatização –" / "FGTS;"). Duas entradas.

###### Observações

- Res. CVM 179/23, art. 9º, Grupo I, V: na célula do ato o ponto final do inciso se funde com a linha de pontos ("mobiliários......"). Mantido o ponto final, como na redação anterior e no consolidado.
- Res. CVM 162/22, art. 18, IX: o ato revoga "o inciso X do art. 1º do Anexo C da Instrução CVM nº 45" (sic). Aplicado ao Anexo C da Res. CVM 45; ficou "X – (Revogado)" e as alíneas a) a c) do inciso saíram com ele, como no consolidado. A alínea c) do inciso IX (art. 18, VIII) ficou "c) (Revogado)".
- Res. CVM 209/24, art. 5º: deu nova redação ao Anexo A, Grupo IV, VII a IX (vigor em 2025-07-01). Passo próprio no histórico (v4, DOU 2024-08-27): VII e VIII trocados, IX incluído. A Res. CVM 235/25 revogou esse art. 5º (art. 4º, II) e reescreveu os mesmos incisos (v5: VII a IX trocados, X e XI incluídos); a redação da 209 vigorou de 2025-07-01 a 2025-12-01. O consolidado da CVM omite a 209 no título ("ALTERAÇÕES INTRODUZIDAS PELAS RESOLUÇÕES CVM Nº 65/22, 162/22, 179/23 e 235/25"), mas a 209 alterou a norma.
- Retificação do DOU de 2021-09-10: texto não obtido; não aplicada.
- Vigência: 65/22 em 2022-03-02; 162/22 em 2023-01-02; 179/23 em 2023-06-01; 209/24 em 2025-07-01; 235/25 em 2025-12-01 (inciso IX do Grupo IV do Anexo A em 2026-01-02). Todas anteriores à data-base; redações aplicadas na data do DOU.

### Res. CVM 46

#### Divergências do replay da Res. CVM 46/2021 (2026-10-29)

Cadeia (fontes/INVENTARIO.md): original (DOU 2021-09-02), Res. CVM 65 (DOU 2022-02-15). Teste 1: 0 linha fora do ato em todos os passos. Teste 2 contra `dados/resol046consolid.docx`: 0 diferença não aceita, 7 aceitas em `aceitas-propostas.json`.

###### 1. Assinatura eletrônica

- O consolidado termina com "Assinado eletronicamente por / MARCELO BARBOSA / Presidente"; a fonte original, não. 3 entradas.

###### 2. Caixa dos títulos e espaço no Art. 9º, I

- Capítulo II, título; Capítulo III, título; Capítulo IV, título: o consolidado usa caixa mista ("Capítulo II - Recursos ao colegiado", "Capítulo III - RELATORIA DE PROCESSOS", "Capítulo IV - Disposições Finais"); o DOU, maiúsculas. Três entradas.
- Art. 9º, I: o consolidado traz "I -ser distribuído" (sem espaço depois do travessão); o DOU, "I - ser distribuído". Uma entrada.

###### Observações

- Res. CVM 65/22, art. 2º: Art. 18-A incluído depois do art. 18, antes do Capítulo IV. Vigência em 2022-03-02, anterior à data-base; redação aplicada na data do DOU.

### Res. CVM 47

#### Divergências do replay da Res. CVM 47/2021 (2026-10-29)

Cadeia: original (DOU 2021-09-02, texto do PDF da CVM), Res. CVM 60 (DOU 2021-12-24, art. 66), 159 (2022-07-11), 207 (2024-08-14) e 236 (2025-12-12). Teste 2 contra `dados/resol047consolid.docx` (sha256 1aefd100...). Os itens 1 a 5 são as diferenças do teste 2 aceitas em `aceitas-propostas.json` (24 entradas); os itens 6 e 7 são resultados do teste 1.

###### 1. Títulos de capítulo e de anexo

- Ato: original.
- Causa: o PDF da CVM traz os títulos dos Capítulos II a VI e dos Anexos A e B em caixa alta; o consolidado, em caixa mista. Diferença editorial do consolidado.
- Decisão: texto mantido; 7 entradas.

###### 2. Art. 18, § 2º

- Ato: Res. CVM 159/22 (art. 2º, nova redação do art. 18 com caput e parágrafo único; art. 3º, III, revoga o § 2º).
- Causa: o histórico mantém o § 2º com "(Revogado)" (convenção do replay); o consolidado omite o parágrafo.
- Decisão: texto mantido; 1 entrada (só norma).

###### 3. Assinatura eletrônica

- Ato: original.
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" entre o art. 25 e o Anexo A; o texto do PDF usado como original não traz a assinatura.
- Decisão: 3 entradas (só consolidado).

###### 4. Anexo A, art. 1º, linha Emissor de valores mobiliários

- Ato: Res. CVM 236/25 (art. 1º).
- Causa: o consolidado traz, dentro da célula, quatro anotações "Alínea "a" com redação dada pela Resolução CVM nº 236, de 9 de dezembro de 2025."; fora delas, o texto é igual. Nota de alteração do consolidado.
- Decisão: texto mantido; 1 entrada.

###### 5. Anexo B, art. 1º, tabela

- Ato: original.
- Causa: a tabela do Anexo B saiu achatada na extração do PDF (cabeçalho e primeira célula na mesma linha, demais células em linhas soltas); o consolidado a traz inteira (3 linhas de tabela), com o mesmo texto. Daí também "tabelas: 1 na norma, 2 no consolidado".
- Decisão: não refazer a tabela (seria texto que não está na fonte); 11 entradas de linha (3 só consolidado, 8 só norma) e 1 entrada "tabelas" (norma 1, consolidado 2). [verificar no DOU]

###### 6. Teste 1, Res. CVM 207/24: caput do Anexo A, art. 1º

- Ato: Res. CVM 207/24 (art. 1º).
- Causa: no original, o caput do art. 1º do Anexo A ("A multa cominatória ordinária será aplicada com o seguinte valor diário:") está na mesma linha que o cabeçalho e a primeira linha da tabela achatada. O ato mantém o caput ("Art. 1º .....") e substitui a tabela; separar o caput gera uma linha nova cujo texto vem da versão anterior, não do ato.
- Decisão: falso positivo (nenhum texto inventado); sem correção possível. A linha de Companhias Securitizadoras que a Res. CVM 60 inserira (v1) saiu com a tabela antiga e voltou na tabela da Res. CVM 207.

###### 7. Teste 1, Res. CVM 236/25: célula da linha Emissor de valores mobiliários

- Ato: Res. CVM 236/25 (art. 1º).
- Causa: o ato troca só as alíneas a) dos incisos I a IV, dentro de uma célula; a célula resultante junta o texto do ato com o resto da célula da Res. CVM 207 (incisos e alíneas b), e o teste 1 compara a célula inteira com o ato.
- Decisão: falso positivo; as quatro alíneas novas foram copiadas do ato (a do inciso III com "– ISEM", como no ato e no consolidado). Mesmo caso das linhas de tabela da seção 13 de `dados/replay-0080/divergencias.md`.

###### 8. Outras notas

- Res. CVM 60, art. 66: a linha de Companhias Securitizadoras entrou como linha de tabela depois de Auditor independente (posição do consolidado), porque a tabela do original está achatada; o ato traz "eII" sem espaço.
- Retificação da Res. CVM 60 no DOU de 2023-01-06: não obtida [verificar].
- Atos 159, 207 e 236: texto do arquivo do ato no site da CVM, não da página do DOU [verificar no DOU].

### Res. CVM 53

#### Divergências do replay da Res. CVM 53/2021 (2026-10-29)

Cadeia: original (DOU 2021-10-18; texto do PDF da CVM) e Res. CVM 239 (DOU 2026-01-12; só o art. 3º, II é da Res. CVM 53). Teste 1: 0 linha fora do ato. Teste 2 contra `dados/resol053consolid.docx` (o consolidado já traz a 239): 0 diferença não aceita, 3 aceitas em `aceitas-propostas.json` (item 1).

###### 1. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o original usado (PDF) não o traz.
- Decisão: três entradas e menção no incerteza.

###### 2. Observações

- Res. CVM 239/26, art. 3º, II: revoga o art. 13, inciso X; o inciso fica como `X – (Revogado)`. Os arts. 1º e 3º, I alteram a Res. CVM 24; o art. 2º é regra de transição de processos internos.
- Vigência para a Res. CVM 53: 2026-01-12 (art. 4º, II), igual à data do DOU.
- A retificação da Res. CVM 239/26 no DOU de 2026-01-16 não foi obtida; não se sabe se toca a Res. CVM 53. [verificar no DOU]

### Res. CVM 54

#### Divergências do replay da Res. CVM 54/2021 (2026-10-29)

Cadeia: original (DOU 2021-10-21; texto do PDF da CVM), Res. CVM 61 (DOU 2021-12-28; só o art. 14 é da Res. CVM 54) e 171 (DOU 2022-10-31). Teste 1: 0 linha fora do ato nos dois passos. Teste 2 contra `dados/resol054consolid.docx`: 0 diferença não aceita, 8 aceitas em `aceitas-propostas.json` (itens 1 a 4).

###### 1. Art. 4º, cabeçalho

- Ato: original.
- Causa: o consolidado escreve "Art. 4o" (letra o), que a normalização não reconhece como cabeçalho de artigo; a linha do consolidado fica inteira e o original tem `## Art. 4º` e o caput.
- Decisão: vale o original; duas entradas e menção no incerteza.

###### 2. Art. 9º, inciso I

- Ato: original.
- Causa: o texto extraído do PDF quebra o inciso antes da citação "NOTIFICAÇÃO DE LANÇAMENTO NÚMERO XXXX/LOTE XXXX"; o consolidado o traz numa linha.
- Decisão: v0 fica igual a `dados/fontes/dou-0054.md`; duas entradas e menção no incerteza. Correção possível na fonte, fora do escopo deste replay. [verificar no DOU]

###### 3. Título do Capítulo IV

- Ato: original.
- Causa: maiúsculas no original; "Capítulo IV" no consolidado.
- Decisão: vale o original; uma entrada.

###### 4. Assinatura eletrônica

- Causa: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" no consolidado; o original usado não o traz.
- Decisão: três entradas e menção no incerteza.

###### 5. Observações

- Res. CVM 61/21, art. 14: só o § 1º do art. 13 (linha de pontos depois dele).
- Res. CVM 171/22, art. 1º: art. 13-A novo, inserido depois do art. 13, antes do Capítulo IV. O art. 2º do ato (regra transitória) não altera a norma.
- Vigências: 61/21 em 2022-01-03; 171/22 em 2022-12-01. Aplicadas na data do DOU.

### Res. CVM 67

#### Divergências do replay da Res. CVM 67/2022 (2026-10-29)

Cadeia: original (DOU 2022-03-11, ctresb/leis) e Res. CVM 248 (DOU 2026-10-14, art. 1º). Teste 1: 0 linhas fora do ato. Teste 2 contra `dados/resol067consolid.docx` (sha256 47d4aa38...): 0 diferenças não aceitas; os itens 1 e 2 são as diferenças aceitas em `aceitas-propostas.json` (7 entradas).

###### 1. Títulos de capítulo

- Ato: original.
- Causa: o original traz os títulos dos Capítulos II a VI em caixa alta; o consolidado, em caixa mista ("Capítulo II - ...", e o IV também no nome). Diferença editorial do consolidado.
- Decisão: texto mantido; 5 entradas.

###### 2. Assinatura eletrônica

- Ato: original.
- Causa: depois do art. 47, o original traz só "Marcelo Barbosa"; o consolidado traz "Assinado eletronicamente por / Marcelo Barbosa / Presidente".
- Decisão: 2 entradas (só consolidado).

###### 3. Outras notas

- Res. CVM 248, art. 1º: nova redação do inciso VI do art. 2º sem as alíneas a e b do original, que saem com o inciso, como no consolidado; nova redação do caput e dos incisos I e II do art. 3º, inciso III novo e § 5º novo.
- Res. CVM 248: texto do arquivo do ato no site da CVM, não da página do DOU [verificar no DOU]. As notas do consolidado datam o ato de "9 de outubro de 2026"; o ato diz 13 de outubro de 2026 (notas não entram na comparação).

### Res. CVM 77

#### Res. CVM 77/2022: divergências do replay

Cadeia: original (DOU 2022-03-30) -> Res. CVM 216/24 (DOU 2024-10-31; art. 4º altera o art. 8º, III).

Teste 1: 0 linhas fora do ato. Teste 2 (v1 contra resol077consolid.docx): 15 diferenças, todas de forma, propostas em aceitas-propostas.json.

1. Espaços a mais no consolidado: Art. 18, § 1º ("notas comerciais .") e Art. 19, § 8º ("16 ( dezesseis)"). Mesmo texto.
2. Assinatura: bloco "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" só no consolidado.
3. Título do Anexo A: "Anexo A à Resolução CVM nº 77, de 29 de março de 2022" no consolidado; "ANEXO A" no DOU.
4. Anexo A, tabela do formulário: a página do DOU traz os campos de marcação como texto ("Sim ( ); ouNão ( )" e a coluna "( )" nos itens I e II); no .docx são caixas de seleção que o conversor não extrai. Mesmo número de tabelas (1).

Observação: a Res. CVM 216/24 entrou em vigor em 2025-07-01; aplicada na data do DOU (2024-10-31).

### Res. CVM 81

#### Divergências do replay da Res. CVM 81/2022 (2026-10-29)

Cadeia: original (DOU 2022-03-30; texto do PDF do ato no site da CVM), Res. CVM 59/21 (republicação no DOU em 2022-05-13) e Res. CVM 204/24 (DOU 2024-06-05; texto do DOCX da CVM). Teste 1: 59 com 6 linhas acusadas (item 1); 204 com 3 linhas acusadas (itens 2 e 3). Teste 2 contra `dados/resol081consolid.docx`: 0 diferença não aceita, 570 aceitas em `aceitas-propostas.json` (itens 4 a 10).

###### 1. Teste 1 da Res. CVM 59/21: revogações dentro de linhas achatadas dos Anexos C, H e I

- Ato: Res. CVM 59/21 (art. 8º, IV e V; art. 7º).
- Causa: no PDF do original, os Anexos C e H vêm achatados (vários itens numa linha). A revogação dos itens 5.l e 8.e do Anexo C e do item 11 do Anexo H foi aplicada dentro dessas linhas: o item fica "l. (Revogado)", "e. (Revogado)" ou "11. (Revogado)" e saem os subitens dele. O teste 1 acusa as linhas editadas (5, m, 8.a-d, f, 10-11 do Anexo H) e a linha da nota de rodapé 3 do Anexo I, que saiu da linha achatada do campo 12 para linha própria.
- Verificação: em cada linha acusada o único texto inserido é "(Revogado)"; o resto é texto do original (conferido por diff contra v0).
- Decisão: nenhum texto novo fora do ato; mantido como historico-conferido (precedente: replay-0080, item 13); menção no incerteza.

###### 2. Teste 1 da Res. CVM 204/24: Art. 34, § 1º e Art. 81, caput

- Ato: Res. CVM 204/24 (art. 2º).
- Art. 34: o DOCX do ato traz só o rótulo "§ 1º" (sem texto) onde o original tinha "Parágrafo único. O boletim de voto a distância deve dar ao acionista a possibilidade de alocar seus votos..."; o replay mantém o texto anterior sob o número novo, como no consolidado. O teste 1 acusa a linha, porque o texto não está no ato, só o número.
- Art. 81: no PDF do original o caput e o inciso I vêm numa linha só; o ato dá nova redação ao inciso I, e o caput passa a linha própria ("Constitui infração grave, para os efeitos da Lei 6.385, de 7 de dezembro de 1976:"), com o texto do original.
- Decisão: só rótulo ou separação de linha; mantido; menção no incerteza.

###### 3. Teste 1 da Res. CVM 204/24: título do Anexo O

- Ato: Res. CVM 204/24 (art. 4º).
- Causa: o ato dá nova redação ao Anexo O com a tabela só; no PDF do original o título "Inclusão de propostas no boletim de voto a distância" vinha na mesma linha da tabela achatada. O replay mantém o título em linha própria antes da nova tabela, como no consolidado.
- Decisão: texto do original; mantido; menção no incerteza.

###### 4. Numerais e títulos de capítulo

- Ato: Res. CVM 204/24 e original.
- Causa: o consolidado escreve "20 (vinte)", "4 (quatro)", "48 (quarenta e oito)" etc. onde o DOCX do ato traz só o extenso (Arts. 5º, 26, 27, 30, 30-A, 37, 43, 44, 45, 46-B e 49); os títulos de capítulo vêm em maiúsculas no PDF do original e em caixa mista no consolidado.
- Decisão: vale o texto da fonte; um par por linha (19 de numerais, 5 de títulos).

###### 5. Art. 44, II, a), item 2, e Art. 45, I, b): "; e"

- Ato: Res. CVM 204/24.
- Causa: o ato termina as duas linhas com "; e"; o consolidado, com ponto final.
- Decisão: vale o ato; dois pares.

###### 6. Art. 44, II, b): linha partida no PDF

- Ato: original (alínea não alterada pela 204).
- Causa: no PDF do original a alínea vem partida em "...Cadastro Nacional de Pessoas Jurídicas" e "– CNPJ."; o consolidado traz uma linha só.
- Decisão: mantido o texto da fonte; duas entradas.

###### 7. Art. 45, III, e Subseção VII (redação da 204 sem linhas pontilhadas)

- Ato: Res. CVM 204/24.
- Causa: o DOCX do ato não traz as linhas pontilhadas de remissão. O ato dá nova redação ao caput, aos incisos I e II e ao § 1º do Art. 45 e não menciona o inciso III; o consolidado o mantém ("48 (quarenta e oito) horas"). O replay mantém o inciso III com a redação anterior ("48 horas"). O ato insere a "Subseção VII – Cômputo dos Votos na Assembleia" antes do novo Art. 46-C; o consolidado mantém também o título antigo "Subseção VII – Cômputo dos Votos na Assembleia Geral" antes do Art. 47, e o replay segue o consolidado.
- Decisão: estrutura do consolidado, texto da fonte; um par (inciso III); menção no incerteza [verificar no DOU].

###### 8. Assinatura eletrônica

- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" antes dos anexos.
- Decisão: três entradas e menção no incerteza.

###### 9. Anexos A a Q: texto achatado no PDF do original

- Ato: original (e, nos Anexos C, H, I, M e O, as alterações aplicadas sobre ele).
- Causa: no PDF do original os anexos vêm achatados (vários itens numa linha, chamadas e textos das notas de rodapé no meio do texto, tabelas do Anexo N sem estrutura); o consolidado traz um item por linha. Os itens alterados conferem com o consolidado: Anexo M, itens 11 e 20, e Anexo O (tabela), da Res. CVM 204/24; Anexo I, campos 12 e 13, e Anexo C, item 5.l, e Anexo H, item 11, da Res. CVM 59/21.
- Anexo M, itens 11 e 20: a nova redação não traz as chamadas das notas de rodapé 7 e 18 do original; os textos dessas notas ficam no anexo [verificar no DOU].
- Decisão: uma entrada por linha divergente (cerca de 540) e a entrada "tabelas" (norma 1, consolidado 2); menção no incerteza [verificar no DOU].

###### 10. Anexo C, item 8: revogação parcial (ato) × total (consolidado)

- Ato: Res. CVM 59/21 (art. 8º, IV: "os itens 5.l e 8.e do Anexo C").
- Causa: o consolidado da CVM risca o item 8 inteiro (caput e alíneas a a f) e traz "8. REVOGADO" com a nota "Item 8 revogado pela Resolução CVM nº 59"; o texto do ato (republicação no DOU) revoga só a alínea 8.e.
- Decisão: vale o texto do ato (só 8.e revogada); três entradas e menção no incerteza [verificar no DOU].

###### 11. Observações

- Vigência: Res. CVM 59/21 em vigor em 2023-01-02; Res. CVM 204/24 em 2025-01-02. Aplicadas na data do DOU (59 na republicação de 2022-05-13).
- Retificação da Res. CVM 204/24 no DOU de 2024-06-19: texto não obtido [verificar no DOU].
- Art. 5º da Res. CVM 204/24: revogados art. 10, VI; art. 11, III; art. 26, § 2º; art. 28, § 5º; art. 31, § 2º; art. 45, § 2º (antigo); art. 48, I e § 3º.

### Res. CVM 86

#### Res. CVM 86/2022: divergências do replay

Cadeia: original (DOU 2022-04-01) -> Res. CVM 221/24 (DOU 2024-12-11).

Teste 1: 0 linhas fora do ato. Teste 2 (v1 contra resol086consolid.docx): 33 diferenças, todas de forma, propostas em aceitas-propostas.json.

1. Notas de alteração: "§§ 1º, 2º e 3º incluídos pela Resolução CVM nº 221..." (Art. 1º) e "§§ 6º, 7º e 8º com redação dada pela..." (Art. 9º) ficam no texto normalizado do consolidado porque começam com "§§".
2. Título do Capítulo II: "Capítulo II – DISTRIBUIÇÃO PÚBLICA" no consolidado; "CAPÍTULO II -DISTRIBUIÇÃO PÚBLICA" no DOU.
3. Art. 7º: a página do DOU quebra o caput em dois parágrafos ("...deferido se" / "não houver manifestação da SRE neste prazo."). Mesmo texto; mantida a forma da fonte.
4. Títulos do Capítulo III e das Seções I e II: o art. 2º da Res. CVM 221/24 revoga só os arts. 29 e 30 e o Anexo H. O consolidado tacha também os títulos do Capítulo III ("Ofertas sujeitas a regimes diferenciados") e das duas seções; o histórico os mantém, porque o ato não os revoga expressamente.
5. Art. 40, I, b: o ato escreve "art. 1º, §1º, inciso I" (sem espaço); o histórico copia o ato e o consolidado escreve "§ 1º".
6. Assinatura: bloco "Assinado eletronicamente / MARCELO BARBOSA / Presidente" só no consolidado.
7. Títulos dos anexos: o consolidado escreve "Anexo A à Resolução CVM nº 86, DE 31 DE MARÇO DE 2022" (idem B a G), separa o subtítulo do Anexo C e marca "ANEXO H - REVOGADO"; o histórico tem "ANEXO A" etc. e "ANEXO H" seguido de "(Revogado)".

Observações:
- A retificação do original publicada no DOU de 2022-07-08 não foi obtida [verificar]. O teste 2 não mostra diferença de conteúdo entre o histórico e o consolidado.
- A Res. CVM 221/24 entrou em vigor em 2024-12-16; aplicada na data do DOU (2024-12-11).
- O art. 2º da Res. CVM 221/24 cita "Resolução CVM nº 86, de 31 de março de 2021" (ano errado no ato; a norma é de 2022). Sem efeito no texto.

### Res. CVM 88

#### Divergências do replay da Res. CVM 88/2022 (2026-10-29)

Cadeia: original (DOU 2022-04-28; texto do PDF do ato no site da CVM), Res. CVM 158 (DOU 2022-06-29) e 226 (DOU 2025-03-07; só o art. 4º é da Res. CVM 88). Teste 1: 0 linha fora do ato nos dois passos. Teste 2 contra `dados/resol088consolid.docx`: 0 diferença não aceita, 102 aceitas (uma por linha divergente distinta, mais a contagem de tabelas). Todas são de forma, vindas da extração do PDF da redação original; nenhuma toca dispositivo alterado pelos atos.

###### 1. Quebras de parágrafo do PDF (Art. 8º, § 2º, e Art. 11, inciso II)

- Ato: original.
- Causa: a heurística de parágrafos do PDF parte o § 2º do art. 8º dentro de "PACOTE DE / DOCUMENTOS RELEVANTES" / ", antes do início da oferta" e separa a frase entre aspas do inciso II do art. 11; o consolidado traz cada dispositivo em um parágrafo. Mesmo texto.
- Decisão: texto do PDF mantido; entradas em aceitas-propostas.json e menção no incerteza.

###### 2. Assinatura

- Ato: não se aplica.
- Causa: o consolidado traz "MARCELO BARBOSA / Presidente" depois do art. 57; o texto do PDF sai sem a assinatura.
- Decisão: texto mantido sem o bloco; entradas e menção no incerteza.

###### 3. Anexos A a H: parágrafos e tabelas achatados

- Ato: original (o Anexo E, Seção 3, alínea c, alterada pela Res. CVM 158, coincide com o consolidado).
- Causa: no PDF, os termos de ciência (Anexos A a C) saem com os parágrafos e a linha de assinatura juntos; as tabelas dos Anexos D, G e H saem como texto corrido (tabelas: 0 na norma, 3 no consolidado); no Anexo E, a palavra "subsequentes." do item 2 da Seção 1 sai uma linha acima e títulos de seção ("Seção 5", "Seção 7", "Seção 11") colam no parágrafo anterior; as 3 notas de rodapé dos Anexos D e H ("1 As informações devem ser prestadas...", "2 ...", "3 ...") ficam no texto, com o número colado ao título, e o consolidado as tem como notas do Word, fora do texto convertido. Comparação palavra a palavra das linhas divergentes: fora as notas, a assinatura e a posição de "subsequentes.", as mesmas palavras na mesma ordem.
- Decisão: vale o texto do PDF (o DOU não foi obtido); uma entrada por linha divergente distinta e a de tabelas em aceitas-propostas.json; menção no incerteza ("Anexos", "tabelas").

###### 4. Observações

- Retificação da Res. CVM 88 no DOU de 2022-05-04: texto não obtido; o teste 2 não acusou diferença de conteúdo que ela explicaria.
- Res. CVM 158: o art. 2º põe a vigência em 2022-06-28, um dia antes do DOU (2022-06-29). Res. CVM 226: vigência em 2025-03-10.
- Res. CVM 158, art. 1º, inciso V do art. 16: o ato escreve "V -" (hífen) e o original do PDF tem "V –" (travessão); vale o texto do ato.

### Res. CVM 135

#### Divergências do replay da Res. CVM 135/2022 (2026-10-29)

Cadeia: original (DOU 2022-06-13; texto do PDF do ato no site da CVM), Res. CVM 170/22 (DOU 2022-10-14) e Res. CVM 220/24 (DOU 2024-11-12). Teste 1: 170 limpo; 220 com uma linha acusada por rótulo (item 7). Teste 2 contra `dados/resol135consolid.docx`: 0 diferença não aceita, 118 aceitas em `aceitas-propostas.json` (itens 1 a 6).

###### 1. Art. 39, § 3º, inciso II

- Ato: Res. CVM 220/24 (art. 1º).
- Causa: o ato termina o inciso II com "; e" e não toca o inciso III, que segue em vigor; o consolidado da CVM termina o inciso II com ponto final.
- Decisão: vale o texto do ato; um par em aceitas-propostas.json e menção no incerteza.

###### 2. Art. 126, § 1º: nota de alteração

- Ato: Res. CVM 220/24.
- Causa: o consolidado traz "Incisos III, IV e V com redação dada pela Resolução CVM nº 220, de 11 de novembro de 2024.", que a normalização não remove (o prefixo "Incisos III, IV e V" tem vírgula, que o padrão de nota do normalizador não aceita).
- Decisão: não é texto normativo; uma entrada (consolidado) e menção no incerteza.

###### 3. Assinatura eletrônica

- Ato: não se aplica (final do consolidado).
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" antes dos anexos.
- Decisão: texto mantido sem o bloco; três entradas e menção no incerteza.

###### 4. Cabeçalhos dos Anexos A, B e C

- Ato: original.
- Causa: o PDF do ato traz "ANEXO X À RESOLUÇÃO CVM Nº 135, DE 10 DE JUNHO DE 2022"; o consolidado, "ANEXO X À Resolução CVM nº 135, ..." (caixa mista).
- Decisão: vale o ato; três pares e menção no incerteza.

###### 5. Anexo B: tabela achatada no PDF

- Ato: original.
- Causa: o consolidado traz o Anexo B como tabela (uma linha por item; contagem de tabelas 1). O PDF do ato, origem do texto, vem achatado: várias alíneas numa linha, os números das notas de rodapé 1 a 9 colados ao texto ("art. 411 Nome da entidade:", "2. Auditores 4") e o texto das notas de rodapé no meio dos itens. O conteúdo normativo é o mesmo.
- Decisão: vale o texto do ato até conferência no DOU [verificar no DOU]; uma entrada por linha divergente (102 linhas) e a entrada "tabelas" (norma 0, consolidado 1); menção no incerteza.

###### 6. Anexo C: alíneas numa linha

- Ato: original.
- Causa: no PDF do ato, título e alíneas a a e vêm numa linha só; no consolidado, uma por linha.
- Decisão: vale o ato; sete entradas e menção no incerteza.

###### 7. Teste 1 da Res. CVM 220/24: rótulo do § 1º do Art. 152

- Ato: Res. CVM 220/24.
- Dispositivo: Art. 152, § 1º.
- Causa: o ato escreve "§ 1º ....." (só o número, com linha de pontos) onde o original tinha "Parágrafo único. A dispensa a que se refere o inciso I do caput depende:"; o replay mantém o texto anterior sob o número novo, como no consolidado da CVM. O teste 1 acusa "§ 1º A dispensa a que se refere o inciso I do caput depende:", porque o texto não está no ato, só o número.
- Decisão: nenhum texto novo fora do ato, só o rótulo (precedente: replay-0080, item 13). Mantido; menção no incerteza; nivel_verificacao historico-conferido.

###### 8. Observações

- Vigência: Res. CVM 170/22 em vigor em 2022-11-01; Res. CVM 220/24 em 2025-01-02. Aplicadas na data do DOU.
- Art. 95, § 3º (Res. CVM 170/22): a nova redação não traz os incisos I e II do original, que saem com o parágrafo, como no consolidado.
- Art. 132 (Res. CVM 220/24): o ato substitui o artigo e o título da Subseção III ("Recurso à CVM" passa a "Supervisão"); Arts. 133 a 135 revogados.

### Res. CVM 161

#### Divergências do replay da Res. CVM 161/2022 (2026-10-29)

Cadeia: original (DOU 2022-07-14, ctresb/leis), Res. CVM 173 (DOU 2022-12-01, art. 3º), 207 (2024-08-14, art. 3º) e 222 (2024-12-11, art. 1º). Teste 1: 0 linhas fora do ato nos três passos. Teste 2 contra `dados/resol161consolid.docx` (sha256 0212bdd3...): 0 diferenças não aceitas; os itens 1 a 4 são as diferenças aceitas em `aceitas-propostas.json` (10 entradas).

###### 1. Título do Capítulo II

- Ato: original.
- Causa: o original traz "CAPÍTULO II - REGISTRO DE COORDENADOR DE OFERTAS PÚBLICAS" em caixa alta; o consolidado, "REGISTRO de coordenador de ofertas públicas". Diferença editorial do consolidado.
- Decisão: texto mantido; 1 entrada.

###### 2. Assinatura eletrônica

- Ato: original.
- Causa: o consolidado traz "Assinado eletronicamente por / MARCELO BARBOSA / Presidente" entre o art. 24 e o Anexo A; o texto do original não a traz.
- Decisão: 3 entradas (só consolidado).

###### 3. Títulos dos Anexos A e B

- Ato: original.
- Causa: o consolidado acrescenta "À RESOLUÇÃO CVM Nº 161, DE 13 DE JULHO DE 2022" a "ANEXO A" e "ANEXO B".
- Decisão: texto mantido; 2 entradas.

###### 4. Anexo B, itens 5.4.1 e 5.5.1

- Ato: original.
- Causa: nas duas listas de experiências profissionais, o original traz "- " antes de nome da instituição, cargo, atividade principal e datas de entrada e saída, dentro da célula; o consolidado não traz o marcador. O texto é o mesmo.
- Decisão: texto mantido; 4 entradas (cada entrada cobre as duas ocorrências da mesma linha).

###### 5. Outras notas

- Retificação da Res. CVM 173 no DOU de 2023-01-06: não obtida [verificar].
- Res. CVM 207: texto do arquivo do ato no site da CVM, não da página do DOU [verificar no DOU].
- Art. 22-A (Res. CVM 207) entrou depois do art. 22, antes do Capítulo IX, como no consolidado.

### Res. CVM 166

#### Divergências do replay da Res. CVM 166/2022 (2026-10-29)

Cadeia: original (DOU 2022-09-02, ctresb/leis) e Res. CVM 231 (DOU 2025-07-04, art. 2º). Teste 1: 0 linhas fora do ato. Teste 2 contra `dados/resol166consolid.docx` (sha256 06d1bc0a...): 0 diferenças não aceitas; os itens 1 e 2 são as diferenças aceitas em `aceitas-propostas.json` (4 entradas).

###### 1. Art. 1º, parágrafo único

- Ato: Res. CVM 231/25 (art. 2º).
- Causa: o ato inclui o § 2º no art. 1º ("Art. 1º ....", linha de pontos, "§ 2º ...") sem citar nem renumerar o parágrafo único do original. O consolidado renumera o parágrafo único para § 1º.
- Decisão: texto do ato aplicado literalmente; o parágrafo único fica com o rótulo do original, ao lado do § 2º novo. Renumeração do consolidado aceita como diferença de numeração (1 entrada). Se a regra do projeto for renumerar implicitamente, trocar "Parágrafo único." por "§ 1º" em v1 (o teste 1 então acusaria a linha, só pelo rótulo, como no item 7 de `dados/replay-0135/divergencias.md`).

###### 2. Assinatura eletrônica

- Ato: original.
- Causa: o consolidado traz "Assinado eletronicamente por / JOÃO PEDRO BARROSO DO NASCIMENTO / Presidente" depois do art. 6º; o texto do original não a traz.
- Decisão: 3 entradas (só consolidado).

###### 3. Outras notas

- Res. CVM 231: texto do arquivo do ato no site da CVM, não da página do DOU [verificar no DOU]. Vigor em 2026-01-02, já passado na data-base.

### Res. CVM 193

#### Divergências do replay da Res. CVM 193/2023 (2026-10-29)

Cadeia: original (DOU 2023-10-23; texto do PDF do ato no site da CVM), Res. CVM 219 (DOU 2024-10-31), 227 (DOU 2025-04-01) e 244 (DOU 2026-06-01). Teste 1: 0 linha fora do ato nos três passos. Teste 2 contra `dados/resol193consolid.docx`: 0 diferença não aceita, 6 aceitas.

###### 1. Dispositivos revogados (Art. 2º e Art. 5º, inciso III)

- Ato: Res. CVM 244/26, art. 1º.
- Causa: o histórico mantém o dispositivo com "(Revogado)" (convenção do replay); o consolidado da CVM só traz a redação antiga tachada e a nota "• Art. 2º revogado pela Resolução CVM nº 244..." / "•Inciso III revogado pela...", que a normalização apaga. No art. 2º, por isso, também o heading `## Art. 2º` sobra só na norma.
- Decisão: vale a convenção; três entradas em aceitas-propostas.json e menção no incerteza.

###### 2. Assinatura

- Ato: não se aplica.
- Causa: o consolidado traz "Assinado eletronicamente por / JOÃO PEDRO BARROSO DO NASCIMENTO / Presidente"; o texto do PDF sai sem a assinatura.
- Decisão: texto mantido sem o bloco; três entradas e menção no incerteza.

###### 3. Observações

- Res. CVM 219, art. 1º: a citação termina em `primeiro".` sem "(NR)"; aplicada como substituição dos incisos I e II e inclusão do III do art. 5º, como no consolidado.
- Res. CVM 244, art. 2º: dá nova redação ao caput e aos incisos I e II do art. 5º sem linha de pontos; o inciso III, revogado pelo art. 1º do mesmo ato, fica com "(Revogado)". O art. 3º do ato não altera o texto da Res. CVM 193 (regra autônoma).
- Res. CVM 244: o preâmbulo cita reunião do Colegiado "em 27 de maio de 2025" num ato de 29 de maio de 2026 [verificar]; não afeta o texto da Res. CVM 193.

### Res. CVM 210

#### Divergências do replay da Res. CVM 210/2024 (2026-10-29)

Cadeia: original (DOU 2024-08-27; texto do ctresb/leis) e Res. CVM 229/25 (DOU 2025-05-23). Teste 1: limpo. Teste 2 contra `dados/resol210consolid.docx`: 0 diferença não aceita, 18 aceitas em `aceitas-propostas.json`.

###### 1. Art. 15, parágrafo único: "auxiliar no investidor"

- Ato: original.
- Causa: o texto do DOU diz "atuar como auxiliar no investidor"; o consolidado da CVM, "auxiliar do investidor". A Res. CVM 210/24 tem retificação no DOU de 2025-06-23, cujo texto não foi obtido; pode ser a origem da diferença.
- Decisão: vale o texto do DOU até a conferência; um par e menção no incerteza [verificar no DOU].

###### 2. Assinatura eletrônica

- Causa: o consolidado traz "Assinado eletronicamente por / JOÃO PEDRO BARROSO DO NASCIMENTO / Presidente".
- Decisão: três entradas e menção no incerteza.

###### 3. Anexo (Suplementos A e B)

- Ato: original.
- Causa: no texto do DOU (ctresb/leis), células com quebra de linha vêm juntas sem espaço ("DateDD/MM/AAAA", "APLICACAORESGATE_PARCIAL...") e a célula de TIPO DA MOVIMENTACAO do Suplemento B ocupa duas linhas da tabela; o consolidado traz espaço e uma linha só. O título "ANEXO" do DOU não está no consolidado.
- Decisão: vale o texto da fonte; 14 entradas e menção no incerteza. Contagem de tabelas igual (3 e 3).

###### 4. Observações

- Vigência: Res. CVM 229/25 em vigor em 2025-06-02, aplicada na data do DOU. O Art. 23 original (vigor em 2025-07-01) passou a 2026-01-02 antes de a redação original entrar em vigor; as duas datas são anteriores à data-base (2026-10-29), sem vigência diferida.

### Res. CVM 215

#### Divergências do replay da Res. CVM 215/2024 (2026-10-29)

Cadeia: original (DOU 2024-10-31; texto do ctresb/leis) e Res. CVM 230/25 (DOU 2025-06-23), que só muda o Art. 75. Teste 1: limpo. Teste 2 contra `dados/resol215consolid.docx`: 0 diferença não aceita, 40 aceitas em `aceitas-propostas.json`. Nenhuma diferença de texto normativo.

###### 1. Títulos de capítulo em maiúsculas

- Causa: o DOU traz os títulos dos Capítulos II a IX e dos Capítulos I a VI do Anexo C em maiúsculas; o consolidado da CVM, em caixa mista. Mesmo texto.
- Decisão: vale o texto do DOU; 28 entradas (um par por título) e menção no incerteza.

###### 2. Assinatura eletrônica

- Causa: o consolidado traz "Assinado eletronicamente por / JOÃO PEDRO BARROSO DO NASCIMENTO / Presidente".
- Decisão: três entradas e menção no incerteza.

###### 3. Títulos dos Anexos A a D

- Causa: o consolidado acrescenta a cada título a nota "à Resolução CVM nº 215, de 29 de outubro de 2024, COM A ALTERAÇÃO INTRODUZIDA PELA RESOLUÇÃO CVM Nº 230/25" e põe o subtítulo "Laudo de avaliação" do Anexo C em linha própria; o DOU traz "ANEXO A", "ANEXO B", "ANEXO C - Laudo de avaliação" e "ANEXO D À RESOLUÇÃO CVM Nº 215, DE 29 DE OUTUBRO DE 2024".
- Decisão: vale o título do DOU; nove entradas e menção no incerteza.

###### 4. Observações

- Vigência: a Res. CVM 230/25 entrou em vigor em 2025-06-18, antes do DOU (2025-06-23); aplicada na data do DOU. O Art. 75 original (vigor em 2025-07-01) passou a 2025-10-01 antes de a redação original entrar em vigor; as duas datas são anteriores à data-base (2026-10-29).

### Res. CVM 232

#### Divergências do replay da Res. CVM 232/2025 (2026-10-29)

Cadeia: original (DOU 2025-07-04; texto do PDF da CVM) e Res. CVM 236/25 (DOU 2025-12-12; texto do DOCX da CVM). A 236 muda o Art. 33, parágrafo único, I (com alíneas a e b), inclui o Art. 66-A e muda o caput do Art. 68. Teste 1: limpo. Teste 2 contra `dados/resol232consolid.docx`: 0 diferença não aceita, 111 aceitas em `aceitas-propostas.json`. Nenhuma diferença de texto normativo.

###### 1. Títulos de capítulo em maiúsculas

- Causa: a fonte traz os títulos dos Capítulos II a VI em maiúsculas; o consolidado da CVM, em caixa mista.
- Decisão: vale o texto da fonte; 10 entradas e menção no incerteza.

###### 2. Assinatura eletrônica

- Causa: o consolidado traz "Assinado eletronicamente por / JOÃO PEDRO BARROSO DO NASCIMENTO / Presidente"; a extração do PDF a descarta.
- Decisão: três entradas e menção no incerteza.

###### 3. Títulos dos Anexos A a C

- Causa: o consolidado acrescenta a cada título a nota "com as alterações introduzidas pela resolução cvm nº 236/25".
- Decisão: vale o título da fonte; seis entradas e menção no incerteza.

###### 4. Artefatos da extração do PDF no corpo

- Dispositivos: Art. 12, IV e Art. 28, § 2º (espaço antes do ponto após "º"); Art. 22, § 10 e Art. 46, I (linha quebrada no meio do dispositivo).
- Decisão: mesmo texto do consolidado; o texto da fonte não foi mexido; 10 entradas e menção no incerteza.

###### 5. Anexos B e C achatados

- Causa: a extração do PDF junta itens na mesma linha, gruda as chamadas de nota de rodapé no texto ("Advertências1", "Oferta3"), põe as notas de rodapé 1 a 12 no corpo e achata a tabela de dados finais de colocação do Anexo C. O consolidado (convertido sem notas) traz um item por linha e a tabela.
- Decisão: vale o texto da fonte até a conferência no DOU; 81 entradas de linha e uma de contagem de tabelas (0 na fonte, 1 no consolidado) [verificar no DOU].

###### 6. Observações

- Art. 33, parágrafo único, I, b: termina em "; e" sem alínea c, no ato e no consolidado; copiado literalmente.
- Vigência: a Res. CVM 236/25 entrou em vigor na publicação (2025-12-12). O Art. 68 original (vigor em 2026-01-02) passou a 2026-03-16 antes de a redação original entrar em vigor; as duas datas são anteriores à data-base (2026-10-29).
- Fonte do ato: só o DOCX da CVM (sem arquivo no ctresb) [verificar no DOU].

### Tabelas restauradas do consolidado (2026-10-29)

- Res. CVM 47, Anexo B; Res. CVM 81, Anexo N; Res. CVM 88, Anexo D: a tabela achatada pelo PDF do original foi trocada pela tabela do consolidado, com as mesmas palavras. As aceitas que cobriam o texto achatado saíram; o `incerteza` de cada norma registra a troca.
- Res. CVM 88, Anexo D: a nota (1) está no PDF do original e não no consolidado; mantida depois da tabela, como aceita (só na norma).

## Retificações do DOU aplicadas (2026-10-29)

Fontes: páginas do DOU salvas pelo navegador em 2026-10-29 (`dados/fontes/manual/`, resumo em `dados/fontes/manual/retificacoes-dou-2026-10-29.md`). Cada retificação que muda texto entra como passo próprio na cadeia da norma, na data do DOU, com o ato em `plugins/normas/normas/cvm/alteradoras/NNNN-retificacao-AAAA-MM-DD.md` (mesmo método da retificação da Res. CVM 175 na Fase 2). O `montar_historico.py` passa a separar retificações do mesmo ato por data (chave ato, tipo, data do DOU).

| Norma | DOU | O que muda | Aceitas (antes → depois) |
|---|---|---|---|
| Res. CVM 19 | 2021-03-02 | art. 3º, II: acrescenta ", cuja metodologia e conteúdo tenham sido previamente aprovados pela CVM," | 19 → 17 (com a linha abaixo) |
| Res. CVM 19 | 2021-04-01 | art. 26, IV: "nº 483" → "nº 783" | idem |
| Res. CVM 210 | 2025-06-23 | art. 15, parágrafo único: "auxiliar no investidor" → "auxiliar do investidor" | 18 → 17 |
| Res. CVM 160 | 2022-12-05 | art. 81, parágrafo único: "a responsabilidade do , dos coordenadores" → "a responsabilidade dos coordenadores" | 188 → 187 |
| Res. CVM 60 | 2023-01-06 | art. 64 (nova redação do art. 2º, II, da Res. CVM 51): "incisos V e VI do Anexo I" → "do Anexo A" | 35 → 34 |
| Res. CVM 86 | 2022-07-08 | Anexo A, item I: "site [●]." → "site [-]." (o DOU de 2022-04-01 grafa "[G]") | 33 → 34 |
| Res. CVM 21 | 2021-03-04 | republicação dos Anexos D e E inteiros "por terem saído no DOU de 26-2-2021 com incorreções" | 380 → 63 |

- Teste 1: nos passos de 19, 21 e 167 sobre os anexos republicados, 0 linha fora do ato. Nos de 210, 160, 60 e 86, 1 linha fora do ato em cada um, porque a retificação cita só o trecho corrigido e a linha inteira não está no texto dela (mesmo caso da retificação da Res. CVM 175); a linha nova difere da anterior só pelo trecho do "leia-se". Os passos seguintes de cada cadeia têm o mesmo resultado de antes.
- Teste 2: 0 diferença não aceita nas seis normas.
- Res. CVM 86: a única aceita nova. O consolidado da CVM mantém "[●]" e a retificação manda "[-]"; os dois marcam campo a preencher pelo ofertante. Diferença de forma; vale o DOU.
- Res. CVM 21: os anexos seguem a republicação, com os cabeçalhos "ANEXO D/E À RESOLUÇÃO cvm Nº 21, DE 25 DE FEVEREIRO DE 2021" sem a chamada "(*)" e sem a nota "N. da Coejo". A republicação traz as letras das alíneas (a., b., i.) e um espaço depois do número dos itens, e não parte a tabela do Anexo E. Por isso saíram as aceitas de marcadores de lista dessas alíneas, de cabeçalho do Anexo E e de contagem de tabelas (agora 2 e 2). Ficam as aceitas de notas de rodapé, do marcador "·" das subalíneas, das anotações da Res. CVM 167 no consolidado e da numeração do Anexo E (6.3 a 6.6, 7 e 8), que a republicação mantém. Os atos 162, 179 e 209 não tocam os Anexos D e E; o 167 foi reaplicado sobre o texto republicado.

Retificações que não mudam o texto do acervo (sem passo novo):
- Res. CVM 21, DOU de 2021-03-09: só corrige a data no título da republicação ("Março" por "FEVEREIRO"); registrada no `incerteza`.
- Res. CVM 45, DOU de 2021-09-10: o "GCP" já está no acervo.
- Res. CVM 88, DOU de 2022-05-04.
- Res. CVM 64, DOU de 2022-02-09.
- Res. CVM 173, DOU de 2023-01-06: o "§ 6º" já está no acervo; explica a exceção do teste 1 da Fase 2.
- Res. CVM 204, DOU de 2024-06-19.
- Res. CVM 239, DOU de 2026-01-16: não toca a Res. CVM 53.
- Res. CVM 81, Anexo C, item 8: o DOU de 2022-05-13 (republicação da Res. CVM 59) diz "5.l e 8.e". O acervo está certo; o consolidado da CVM, não.
