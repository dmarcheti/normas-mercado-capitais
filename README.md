# Normas do mercado de capitais

Acervo em Markdown de normas do mercado de capitais brasileiro (inicialmente resoluções da CVM sobre fundos, ofertas públicas e securitização), organizado para consulta por pessoas e por assistentes de IA: um arquivo por norma, um título por artigo, metadados de situação e de data-base no cabeçalho e o histórico de alterações preservado em commits, um por ato alterador. O objetivo é dar ao analista de crédito estruturado o texto consolidado e rastreável até a fonte, com a data até a qual cada norma foi atualizada.

## Aviso

Este material não é oficial e não substitui o Diário Oficial da União nem o site da CVM. O texto pode conter erros de conversão ou estar desatualizado em relação a atos publicados depois da data-base de cada norma. Confira sempre a fonte oficial antes de usar em parecer, contrato ou decisão.

## Status

Em construção (repositório privado). Acervo atual:

- 8 resoluções da CVM com histórico por ato desde a publicação original no DOU: Res. CVM 175 (fundos), 160 (ofertas públicas), 60 (securitizadoras), 17 (agente fiduciário), 30 (suitability), 21 (administração de carteiras), 80 (emissores) e 50 (PLD/FTP). Um commit por ato alterador, com a data do DOU (33 atos, de 2021-02-10 a 2026-07-03).
- 12 leis com o texto da página do Planalto lida em 2026-10-28, sem histórico: Leis 6.385, 6.404, 14.430, 9.514, 10.931, 8.668, 11.076, 13.986, 14.711, 14.754, 12.431 e Código Civil (arts. 1.368-C a 1.368-F).

Conferência: `fontes/RESULTADOS.md` (testes por norma) e `fontes/DIVERGENCIAS.md` (onde o histórico e o consolidado da CVM diferem, e por quê).

## Instalação

Para quem for usar com um assistente de IA, ver `COMECE-AQUI.md`. No Claude Code:

```
/plugin marketplace add dmarcheti/normas-mercado-capitais
/plugin install normas@normas-mercado-capitais
```

## Licença

Texto e dados: CC BY 4.0 (`LICENSE`). Código: MIT (`LICENSE-codigo`).
