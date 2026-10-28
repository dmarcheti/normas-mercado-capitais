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
