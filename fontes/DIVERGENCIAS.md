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
