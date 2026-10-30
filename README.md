# Normas do mercado de capitais

Acervo em Markdown de normas do mercado de capitais brasileiro (regulação e orientação da CVM, leis e decretos, normas do CMN e do BCB e autorregulação da ANBIMA e da B3), organizado para consulta por pessoas e por assistentes de IA: um arquivo por norma, um título por artigo, metadados de situação e de data-base no cabeçalho e o histórico de alterações preservado em commits, um por ato alterador. O objetivo é dar ao analista de crédito estruturado o texto consolidado e rastreável até a fonte, com a data até a qual cada norma foi atualizada.

## Aviso

Este material não é oficial e não substitui o Diário Oficial da União nem os sites dos órgãos e entidades de origem (CVM, BCB, ANBIMA, B3). O texto pode conter erros de conversão ou estar desatualizado em relação a atos publicados depois da data-base de cada norma. Confira sempre a fonte oficial antes de usar em parecer, contrato ou decisão.

## Status

Em construção (repositório privado). Acervo atual, em camadas declaradas (data-base 2026-10-28 nas camadas 1 a 3 e 2026-10-29 nas camadas 4 e 5):

1. **Regulação da CVM:** as 155 Resoluções CVM vigentes (as 154 do Estoque Regulatório da CVM de 2026-09-08, mais a Res. 249) e as 5 Instruções CVM ainda em vigor (438, 445, 489, 516 e 579, contábeis de fundos). Ficam fora as revogadas, as que só alteram outras e a Res. 26 (prorrogação de prazos de 2021, sem efeito atual [verificar]).
2. **Interpretação da CVM:** os 41 Pareceres de Orientação e os 179 Ofícios-Circulares editados desde 2022-01-01 (8 deles por OCR, porque o PDF da CVM não tem camada de texto). Os 421 anteriores a 2022 aparecem só como verbete no índice, com link. A CVM não publica a vigência de pareceres e ofícios.
3. **Leis e decretos:** 28 leis e 1 decreto no texto compilado do Planalto lido em 2026-10-28, sem histórico (Leis 6.385, 6.404, 4.728, 4.595, 14.430, 11.101, 13.506 e outras; ver `plugins/normas/normas/indices/leis.md`).

4. **CMN e BCB:** 128 normas vigentes que tocam mercado de capitais, fundos, securitização, crédito negociável e instituições do mercado (57 do CMN e 71 do BCB: Resoluções, Resoluções Conjuntas, Circulares, Cartas Circulares e Instruções Normativas), no texto compilado pelo BCB na busca de normas, sem histórico nem conferência contra o DOU. Os atos que só alteram essas normas aparecem como verbete. Ficam fora política monetária, câmbio comercial, crédito rural, pagamentos de varejo, cooperativas e consórcios, prudencial e PLD; o critério de cada norma está em `fontes/perimetro-camada4.json`.
5. **Autorregulação:** 38 documentos vigentes da ANBIMA (códigos, regras e procedimentos, glossário, deliberações, pareceres e perguntas e respostas) e 59 da B3 (regulamentos, manuais de normas, manuais de procedimentos operacionais e glossários), extraídos dos PDFs. Texto de titularidade da ANBIMA e da B3, reproduzido para uso informativo e retirado a pedido; ver `plugins/normas/normas/autorregulacao/README.md`.

Fora do acervo: julgados da CVM.

Cada norma informa o nível de verificação (`nivel_verificacao`): 38 normas têm histórico por ato desde a publicação original, um commit por ato com a data do DOU: 37 Resoluções CVM (o núcleo de fundos e securitização, 17, 21, 30, 50, 60, 80, 160 e 175, e as substantivas 6, 8, 9, 11, 13, 19, 20, 31, 32, 35, 43, 44, 45, 46, 47, 53, 54, 67, 77, 81, 86, 88, 135, 161, 166, 193, 210, 215 e 232) e a Instr. CVM 489; as demais têm o texto vigente convertido por script do consolidado ou do ato publicado pela CVM, ou do compilado do Planalto.

Conferência: `fontes/RESULTADOS.md` (testes por norma) e `fontes/DIVERGENCIAS.md` (onde o histórico e o consolidado da CVM diferem, e por quê).

## Instalação

Para quem for usar com um assistente de IA, ver `COMECE-AQUI.md`. No Claude Code:

```
/plugin marketplace add dmarcheti/normas-mercado-capitais
/plugin install normas@normas-mercado-capitais
```

## Licença

Texto e dados: CC BY 4.0 (`LICENSE`), salvo a pasta `plugins/normas/normas/autorregulacao/` (camada 5), que reproduz texto de titularidade da ANBIMA e da B3, não está sob nenhuma licença deste repositório e sai a pedido delas (ver o README da pasta). Código: MIT (`LICENSE-codigo`).
