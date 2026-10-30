# Histórico de versões

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
