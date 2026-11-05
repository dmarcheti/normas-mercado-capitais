# Histórico de versões

## Dados de 2026-11-04 (itens da verificação aplicados em 2026-11-05)

- Dados até 2026-11-04: 635 atos, 14991 julgados; Res. BCB 102 (versão 6) e D3649 do Colegiado.
- Versões: `normas` 1.1.3, `julgados-colegiado-2016-2026` 0.5.1.

## Dados de 2026-11-04

- Dados até 2026-11-04: 635 atos, 14990 julgados.
- Versões: `normas` 1.1.2.

## v1.2.0 (não publicada)

- **Atualização automática quinzenal:** a cada duas semanas (quarta-feira), um processo compara as fontes oficiais (CVM, BCB, Planalto, ANBIMA, B3 e CRSFN) com o acervo e aplica o que mudou, pelos mesmos scripts da construção, com testes e um revisor por IA. Execução perdida roda na primeira oportunidade. Entra sem revisão humana só o que tem conferência independente (conversão por script de fonte oficial, cobertura de pelo menos 99% e testes verdes); texto por OCR, revogação, vigência diferida, norma ou documento novo fora do perímetro, ato que altera norma com histórico e item marcado pelo revisor passam por uma pessoa. Por ora tudo está em período de observação: o processo propõe e uma pessoa aprova.
- **Aviso de ato não aplicado:** entre a publicação de um ato alterador e o consolidado oficial, a norma traz aviso no campo `incerteza` e aparece na lista "Atos publicados ainda não aplicados" do índice.
- **Versões e data de conferência:** a versão de cada plugin sobe quando o conteúdo dele muda, e cada índice traz "Fontes conferidas até AAAA-MM-DD". Defasagem esperada: até cerca de duas semanas.
- **Documentação:** seção "Atualização" no `README.md`, seção "Atualização automática" no `VERIFICACAO.md` e nota sobre a data de conferência no `COMECE-AQUI.md`. As taxas de erro publicadas medem a construção, não cada atualização.
- **Código de Negociação de Instrumentos Financeiros da ANBIMA:** a versão vigente desde 2024-11-01 entra no acervo (a ANBIMA passa a 39 documentos). Faltava desde o inventário da camada 5, que só listou as versões anteriores; achado pela primeira verificação da atualização automática.
- **Regras e Procedimentos do Código de Negociação da ANBIMA:** a versão de 2024 (publicada em 08/10/2024) substitui a de 2021, que seguia no acervo; primeira atualização aplicada pela verificação automática. No bloco Nº 01, o antigo Art. 6º virou §2º do Art. 5º e a ANBIMA não renumerou: o bloco passa do Art. 5º ao 7º, como no PDF.
- **Res. BCB 102 (informações ao FGC):** Tabela II com a redação da Res. BCB nº 572/2026, vigente desde 1º/11/2026 (versão 6 do texto compilado pelo BCB). A atualização automática registra a decisão "HTML, sem PDF na API" quando o BCB não publica PDF da norma; antes, a falta da decisão bloqueava o item.
- **Correções:** as da v1.1.1, abaixo, seguem valendo.

## v1.1.1 (2026-11-04)

- **Ofícios SRE com glifo não lido:** 13 Ofícios-Circulares da SRE (2023 e 2024) tinham NUL no lugar de um glifo ("O\x00cios-Circulares", na linha "Referência: Processo nº"), e o grep e o git os tratavam como binários. Reconvertidos da fonte: o glifo, que nem o PDFKit nem o pypdf leem, fica marcado com "�", com aviso no `incerteza`.
- **Pipeline das normas:** a gravação (`texto_vigente.py`, `leis.py`, `fontes_onda.py`, saída do `converter.py`) tira caractere de controle, como nos julgados; o glifo volta quando o pypdf o lê no mesmo trecho. `texto_vigente.py --ids` reconverte só os itens escolhidos.
- **Validador:** reprova caractere de controle em normas, partes, atos alteradores e julgados, com o número de ocorrências.
- **Testemunhas na frase corrida:** o nome das testemunhas em "Na qualidade de testemunhas, assinaram ..." (decisões do Colegiado sobre termo de compromisso) vira `[dado pessoal retirado]`; 186 julgados reconvertidos da fonte, 382 nomes. Novo `scripts/reconverter.py --ids` (ou `--lista`): reconverte por id pelos conversores existentes, separa os ids por conversor, recusa id desconhecido e confere a preservação dos campos extraídos.
- **Versões dos plugins:** `normas` 1.1.1 e `julgados-tc-crsfn` 0.5.1 (julgados reconvertidos sem o nome das testemunhas); os outros quatro `julgados-*` seguem em 0.5.0, sem mudança de conteúdo desde a v1.1.0 (conferido por hash).

## v1.1.0 (2026-11-04)

- **Julgados:** 14.990 julgados em 5 plugins `julgados-*`.
  - 10.501 decisões do Colegiado;
  - 1.714 termos de compromisso;
  - 1.419 PAS;
  - 1.332 acórdãos do CRSFN em recurso de decisão da CVM;
  - 24 arquivos anuais de decisões antigas (1978–2001).
- **Índices:** por ano, por tema e por norma citada, com índice reverso de citações no acervo de normas (`indices/citacoes/`).
- **Extração:** ementa (onde a fonte não traz a sua) e tema por LLM, validados item a item; nome de pessoa fora do frontmatter, dados pessoais retirados do corpo.
- **Varredura do pre-commit:** CPF e RG viram regra fixa; nas pastas de julgados, CNPJ não barra e a lista privada aceita expressões liberadas (linhas com "+").
- **SPEC v0.5.0:** seção Julgados, com frontmatter próprio e listas fechadas de `resultado`.
- **Auditoria dos julgados (Fase 3b):** seis rodadas cegas por amostragem (1.021 itens) com adjudicação contra a fonte; resultado, método e ressalvas em `VERIFICACAO.md`, seção Julgados. Correções no conversor (texto sobreposto, ordem de linha pelo pypdf, OCR de imagem e de faixa, timbre da CVM), no corte de dados pessoais (corte conservador de endereço, e-mail e documento na qualificação; testemunhas) e na regra do resultado do CRSFN; 10 acórdãos duplicados do CRSFN apagados.
- **Bateria v2:** 30 perguntas sobre julgados (`testes/bateria-v2.md`); com os plugins, 24 respostas inteiramente certas, contra 1 sem eles.
- **Resultados e exceções:** `fontes/RESULTADOS.md`, seções Fase 2d e Fase 3b.

## v1.0.0 (2026-10-30)

Primeira versão completa do acervo, ainda em repositório privado.

- **Acervo:** 634 normas em 5 camadas.
  - Camada 1: 155 Resoluções CVM vigentes e 5 Instruções, 38 delas com histórico por ato.
  - Camada 2: 41 Pareceres de Orientação e 179 Ofícios-Circulares desde 2022.
  - Camada 3: 29 leis e decretos.
  - Camada 4: 128 normas do CMN e do BCB.
  - Camada 5: 38 documentos da ANBIMA e 59 da B3.
- **Verificação:** auditoria cega por amostragem nas 5 camadas (`VERIFICACAO.md`).
- **Bateria:** 30 perguntas com gabarito, respondidas com e sem o acervo (`testes/bateria-v1.md`; resultado no README). Foi rodada antes de a skill ganhar a linha dos mapas.
- **Mapas:** CRI, FIDC e FII, em `plugins/normas/normas/mapas/`; a skill os lê nas perguntas por produto.
- **Correções da auditoria:**
  - 26 normas do CMN e do BCB passam a vir do PDF da última versão compilada (antes estavam na redação original);
  - Res. CMN 1.502, alíneas fora de ordem;
  - OC CVM/SMI 2/2023, pela camada de texto do PDF e não por OCR;
  - OC CVM/SIN 6/2023, que estava com o corpo de outro ofício.
- **Ressalvas:** 7 Ofícios-Circulares lidos por OCR; Glossário ANBIMA; Res. CVM 81, art. 45, III (ver `VERIFICACAO.md`).

### Próximo
- A skill acha pior ofícios e documentos da ANBIMA sem artigos (3 erros da bateria). Melhorar a navegação e rodar a bateria de novo.
- Hifenização de fim de linha e cabeçalhos repetidos nos PDFs da ANBIMA e da B3.
- Histórico das leis e de mais resoluções; julgados da CVM.
