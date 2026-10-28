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

