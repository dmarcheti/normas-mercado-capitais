# Normas do mercado de capitais

Acervo em Markdown de normas do mercado de capitais brasileiro (regulação e orientação da CVM, leis e decretos), organizado para consulta por pessoas e por assistentes de IA: um arquivo por norma, um título por artigo, metadados de situação e de data-base no cabeçalho e o histórico de alterações preservado em commits, um por ato alterador. O objetivo é dar ao analista de crédito estruturado o texto consolidado e rastreável até a fonte, com a data até a qual cada norma foi atualizada.

## Aviso

Este material não é oficial e não substitui o Diário Oficial da União nem o site da CVM. O texto pode conter erros de conversão ou estar desatualizado em relação a atos publicados depois da data-base de cada norma. Confira sempre a fonte oficial antes de usar em parecer, contrato ou decisão.

## Status

Em construção (repositório privado). Acervo atual, em camadas declaradas (data-base 2026-10-28):

1. **Regulação da CVM:** as 155 Resoluções CVM vigentes (as 154 do Estoque Regulatório da CVM de 2026-09-08, mais a Res. 249) e as 5 Instruções CVM ainda em vigor (438, 445, 489, 516 e 579, contábeis de fundos). Ficam fora as revogadas, as que só alteram outras e a Res. 26 (prorrogação de prazos de 2021, sem efeito atual [verificar]).
2. **Interpretação da CVM:** os 41 Pareceres de Orientação e os 179 Ofícios-Circulares editados desde 2022-01-01 (8 deles por OCR, porque o PDF da CVM não tem camada de texto). Os 421 anteriores a 2022 aparecem só como verbete no índice, com link. A CVM não publica a vigência de pareceres e ofícios.
3. **Leis e decretos:** 28 leis e 1 decreto no texto compilado do Planalto lido em 2026-10-28, sem histórico (Leis 6.385, 6.404, 4.728, 4.595, 14.430, 11.101, 13.506 e outras; ver `plugins/normas/normas/indices/leis.md`).

Fora do acervo: resoluções do CMN e do BCB, autorregulação (ANBIMA, B3) e julgados da CVM.

Cada norma informa o nível de verificação (`nivel_verificacao`): 9 normas têm histórico por ato desde a publicação original, um commit por ato com a data do DOU (Res. CVM 175, 160, 60, 17, 30, 21, 80 e 50, e Instr. CVM 489); as demais têm o texto vigente convertido por script do consolidado ou do ato publicado pela CVM, ou do compilado do Planalto.

Conferência: `fontes/RESULTADOS.md` (testes por norma) e `fontes/DIVERGENCIAS.md` (onde o histórico e o consolidado da CVM diferem, e por quê).

## Instalação

Para quem for usar com um assistente de IA, ver `COMECE-AQUI.md`. No Claude Code:

```
/plugin marketplace add dmarcheti/normas-mercado-capitais
/plugin install normas@normas-mercado-capitais
```

## Licença

Texto e dados: CC BY 4.0 (`LICENSE`). Código: MIT (`LICENSE-codigo`).
