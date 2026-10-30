# Extração: ementa, tema e resultado de julgados da CVM

Procedimento para o modelo que preenche os campos que a CVM não publica. Ele lê um lote de julgados recortados e grava um JSON. Não roda git, não commita e não grava fora da pasta do lote.

## Entrada

`lote.json`: lista de `{id, tipo, classe, processo, data, titulo, recorte}`. O `recorte` traz o título, o extrato ou os primeiros e últimos parágrafos da decisão e, se houver, o "SUMÁRIO" do parecer, em até ~1.200 tokens.

## Saída

`saida.json`: lista com um objeto por julgado, na ordem da entrada:

```json
{"id": "...", "ementa": "...", "tema": "...", "resultado": "...", "relator": "..."}
```

- `ementa`: até 60 palavras, em português, no estilo de ementa: objeto, fundamento normativo citado no texto e resultado. **Não escreva nome de pessoa física**, mesmo que o texto traga: use "o acusado", "os diretores", "o proponente", "a recorrente". Nome de empresa, fundo e entidade pode ficar. Não invente norma, valor ou resultado que não esteja no recorte.
- `tema`: exatamente um da lista abaixo, o assunto principal do caso.
- `resultado`: um da lista fechada do `tipo`, ou `""` se o recorte não disser.
  - `pas`, `acordao-crsfn`: `condenacao`, `absolvicao`, `parcial`, `extincao`, `arquivamento`, `outro`;
  - `termo-compromisso`: `aceito`, `rejeitado`, `outro`;
  - `decisao-colegiado`, `decisao-antiga`: `deferido`, `indeferido`, `provido`, `nao-provido`, `parcial`, `conhecimento`, `outro`.
- `relator`: como escrito no recorte (nome do diretor ou sigla da área); `""` se não houver.

## Temas

| Tema | Abrange |
|---|---|
| `divulgacao-informacoes` | informações periódicas e eventuais, fato relevante, comunicação ao mercado, formulário de referência |
| `informacao-privilegiada` | uso de informação privilegiada, dever de sigilo |
| `manipulacao-fraude` | manipulação de preços, operação fraudulenta, condições artificiais, práticas não equitativas |
| `deveres-administradores` | dever de diligência e de lealdade, conflito de interesses, abuso de poder de controle, deveres do conselho fiscal |
| `assembleia-acionistas` | assembleia, direito de voto, dividendos, direito de recesso, acordo de acionistas |
| `ofertas-publicas` | oferta de distribuição, registro e dispensa de oferta, oferta irregular, prospecto, coordenador |
| `opa` | oferta pública de aquisição de ações |
| `fundos-investimento` | administração, gestão e regras de fundos (FIDC, FII, FIP, Fiagro e outros) |
| `securitizacao` | companhia securitizadora, CRI, CRA, patrimônio separado, agente fiduciário |
| `intermediacao` | corretoras, distribuidoras, assessores de investimento, adequação ao perfil, ordens |
| `administracao-carteiras` | gestor, administrador fiduciário, consultor de valores mobiliários |
| `auditoria-independente` | auditor independente e seus deveres |
| `contabil-demonstracoes` | demonstrações financeiras, normas contábeis, parecer de auditoria como objeto |
| `registro-emissor` | registro, categoria, suspensão e cancelamento de emissor |
| `infraestrutura-mercado` | bolsa, balcão, depósito, custódia, escrituração, registro de ativos |
| `analistas-rating` | analista de valores mobiliários, agência de classificação de risco |
| `exercicio-irregular` | atividade sem registro, captação irregular, esquemas fraudulentos ao público |
| `criptoativos` | criptoativos, tokens e tokenização como valor mobiliário |
| `crowdfunding` | plataformas de investimento participativo |
| `pld` | prevenção à lavagem de dinheiro e cadastro |
| `multa-cominatoria-taxa` | multa cominatória, taxa de fiscalização, recolhimentos |
| `processual` | prescrição, nulidade, efeito suspensivo, provas, prazos, impedimento, reconsideração sem mérito |
| `normativo` | edição de norma, audiência pública, interpretação geral |
| `institucional` | convênios, organização interna, assuntos administrativos da CVM |
| `outros` | o que não cabe acima |

## Regras

1. Cada campo sai só do recorte. Se o recorte não basta, `""` (ou `outros` no tema).
2. Nada de nome de pessoa física em nenhum campo, salvo em `relator`.
3. Grave só `saida.json`, válido e com todos os ids da entrada.
