# Camada 5: autorregulação (ANBIMA e B3)

Esta pasta reúne, em texto integral, os códigos, regras e procedimentos, regulamentos e manuais de autorregulação vigentes da ANBIMA e da B3, extraídos por script dos PDFs publicados por elas.

## Titularidade e uso

- Os textos desta pasta são de titularidade da ANBIMA (Associação Brasileira das Entidades dos Mercados Financeiro e de Capitais) e da B3 S.A. – Brasil, Bolsa, Balcão. Estão aqui só para consulta informativa, sem fim comercial.
- Esta pasta **não** está sob a licença CC BY 4.0 do restante do acervo, nem sob a licença MIT do código. Nenhum direito sobre estes textos é concedido por este repositório.
- O repositório não tem vínculo com a ANBIMA nem com a B3, e elas não revisaram nem endossam esta reprodução.
- Autorregulação não é norma estatal: vincula as instituições aderentes aos códigos da ANBIMA ou participantes dos ambientes da B3, nos termos de cada documento.

## Retirada a pedido

Se a ANBIMA ou a B3 pedirem, o texto sai do acervo. Para pedir a retirada, abra uma issue com o rótulo `retirada` em https://github.com/dmarcheti/normas-mercado-capitais/issues, indicando o documento.

A retirada vale para a versão corrente do repositório. O texto continua nas versões anteriores do histórico do Git e nas cópias que terceiros já tenham feito.

## Fonte e data-base

| Entidade | Onde está a versão vigente | Lido em |
|---|---|---|
| ANBIMA | páginas de cada código em https://www.anbima.com.br/pt_br/autorregular/codigos.htm e a página de Ética (https://www.anbima.com.br/pt_br/institucional/a-anbima/etica-e-integridade.htm) | 2026-10-29 |
| B3 | https://www.b3.com.br/pt_br/regulacao/estrutura-normativa/regulamentos-e-manuais/ e subpáginas (versão sem marcas de cada documento) | 2026-10-29 |

O frontmatter de cada arquivo traz o link do PDF de origem (`fonte_original`), o hash do arquivo baixado (`sha256_fonte`), a data de início de vigência ou da versão (`data`) e a data da leitura (`baixado_em`). A lista dos documentos e o critério de inclusão estão em `../indices/anbima.md`, `../indices/b3.md` e, no repositório, em `fontes/acervo-anbima.json` e `fontes/acervo-b3.json`.

## Limites

- O texto vem de PDF (`nivel_verificacao: pdf-extraido`): tabelas, numeração e quebras de linha podem estar deslocadas. A versão publicada pela entidade prevalece.
- Ficam fora: questionários de due diligence, checklists, modelos, manuais de sistema e de envio de dados, layouts, metodologias e versões anteriores ou com marcas de alteração.
