# Extração: ementa, tema e resultado de julgados da CVM

Este é o procedimento para o modelo que preenche os campos que a CVM não publica. O modelo lê um lote de julgados recortados e grava um JSON. Não roda git, não commita e não grava fora da pasta do lote.

## Entrada

`lote.json` é uma lista de `{id, tipo, classe, processo, data, titulo, recorte}`.

Na decisão do Colegiado e no termo de compromisso, o `recorte` vem em blocos rotulados, nesta ordem:

1. `TÍTULO:`
2. `DELIBERAÇÃO DO COLEGIADO (o resultado sai daqui):` traz o parágrafo em que o Colegiado delibera ("O Colegiado, por unanimidade, deliberou...", "acompanhou", "decidiu", "aprovou", "deferiu") e o que vem logo depois. Também traz o parágrafo que registra pedido de vista, adiamento ou retirada de pauta. Se o script não achou a deliberação, o bloco é `FIM DA DECISÃO (...)`.
3. `DECISÃO NA ÍNTEGRA (...)` ou `PEDIDO E FUNDAMENTOS (...)` traz o pedido, o histórico e os fundamentos. Muitas vezes traz o que a área técnica (SEP, SRE, SMI, SIN, SNC, SPS, SSE, PFE), o Comitê de Termo de Compromisso ou o relator propuseram. **Isso não é a decisão do Colegiado.**
4. `POSIÇÃO DA ÁREA TÉCNICA OU DO COMITÊ (anexo; ...)` traz o fim do parecer ou da manifestação anexa, ou o "SUMÁRIO" do parecer do Comitê. **Também não é a decisão do Colegiado.**

Nos demais tipos, o `recorte` traz o título, o extrato ou os primeiros e últimos parágrafos e, se houver, o "SUMÁRIO" do parecer.

## Saída

`saida.json` é uma lista com um objeto por julgado, na ordem da entrada:

```json
{"id": "...", "situacao": "...", "ementa": "...", "tema": "...", "resultado": "...", "relator": "..."}
```

### `situacao`

Leia primeiro o bloco da deliberação e decida a situação do julgamento:

- `decidido`: o Colegiado deliberou sobre o pedido. Isso inclui a retomada de um julgamento que antes teve pedido de vista e que agora terminou com votos e decisão.
- `suspenso`: o julgamento parou sem deliberação final. Os casos são: um diretor pediu vista, a decisão foi adiada ou o item foi retirado de pauta. Vale também quando já havia votos (do relator ou de outros diretores) antes da suspensão. O que conta é a última coisa que aconteceu na reunião: se depois do pedido de vista, do adiamento ou da retirada não há deliberação do Colegiado, é `suspenso`.
- `sem-deliberacao`: o recorte não traz deliberação do Colegiado nem suspensão. Use também para o termo de compromisso sem decisão do Colegiado.

Nos demais tipos (`pas`, `acordao-crsfn`), use `decidido` se o recorte traz o julgamento e `sem-deliberacao` se não traz.

### `ementa`

A ementa tem até 60 palavras, em português, e segue esta ordem:

1. **O que o Colegiado decidiu**, com o objeto do pedido. Por exemplo: "O Colegiado concedeu a dispensa dos arts. 7º e 9º da RCVM 77 para a emissão de debêntures conversíveis da Azul S.A." ou "O Colegiado negou provimento ao recurso contra multa cominatória da SEP por atraso no formulário de referência".
2. **O fundamento** da decisão, como está no texto: a norma citada ou a razão dada.
3. A posição da área técnica, do Comitê ou do relator entra só se ajudar a entender a decisão, e **sempre com rótulo**. Por exemplo: "acompanhando a SEP", "a SRE propôs a rejeição; o Colegiado aceitou a proposta", "contra o parecer do Comitê".

Regras da ementa:

- **Nunca escreva como decisão o que é proposta, parecer ou voto.** "A SEP entende que não há óbice" não é "não há óbice". O voto do relator não é a decisão do Colegiado.
- **Nada que não esteja no recorte.** Se o recorte não traz um valor, data, norma ou condição, não os escreva. Quando a decisão envolve vários processos ou propostas (por exemplo, três propostas aceitas e uma rejeitada), diga quantos foram em cada sentido e os valores como estão no texto. Não some, não arredonde e não escolha um só.
- Se a situação é `suspenso`, descreva o objeto e termine com "Julgamento suspenso por pedido de vista." ou "Decisão adiada." (ou "Retirado de pauta."). Não diga que o Colegiado decidiu, deferiu ou indeferiu.
- **Não escreva nome de pessoa física**, nem mesmo de diretor ou relator, ainda que o texto traga. Use "o acusado", "o diretor relator", "um diretor", "o proponente", "a recorrente". Nome de empresa, fundo e entidade pode ficar.

### `tema`

O tema é exatamente um da lista abaixo: o assunto principal do caso.

### `resultado`

O resultado é um da lista fechada do `tipo`, ou `""`:

- `pas`, `acordao-crsfn`: `condenacao`, `absolvicao`, `parcial`, `extincao`, `arquivamento`, `outro`.
- `termo-compromisso`: `aceito`, `rejeitado`, `outro`.
- `decisao-colegiado`, `decisao-antiga`: `deferido`, `indeferido`, `provido`, `nao-provido`, `parcial`, `conhecimento`, `outro`.

Regras do resultado:

- **O resultado sai da deliberação do Colegiado**, nunca da proposta da área técnica ou do Comitê, nem do voto do relator ou de um diretor.
  - Se o Colegiado acompanhou a área técnica, o resultado é o que a área técnica propôs.
  - Se o Colegiado divergiu, o resultado é o que o Colegiado decidiu.
- Situação `suspenso` ou `sem-deliberacao`: resultado `""`.
- Situação `decidido`: o resultado **nunca** fica vazio. Use `outro` quando nenhum valor da lista descreve a decisão. São exemplos de `outro`: decisão que só fixa entendimento em consulta, aprova norma, determina diligência, toma conhecimento sem decidir pedido ou devolve o processo à área técnica.
- Na decisão do Colegiado, escolha o valor assim:
  - `deferido`/`indeferido`: pedido de dispensa, registro, autorização ou prazo.
  - `provido`/`nao-provido`: recurso. Vale também para o recurso contra o indeferimento de um pedido pela área técnica, ainda que o título fale só em "pedido": o que o Colegiado decide é o recurso.
  - Pedido de reconsideração ou de revisão de decisão do Colegiado: `provido`/`nao-provido` quando o Colegiado reformou ou manteve a decisão. Use `outro` quando ele só admitiu reexaminar ou condicionou a revisão a exigências ainda a cumprir.
  - `parcial`: pedido ou recurso atendido em parte, ou vários pedidos com decisões em sentidos diferentes.
  - `conhecimento`: o Colegiado não conheceu do recurso ou só tomou conhecimento.
- No termo de compromisso:
  - `aceito`/`rejeitado`: a decisão sobre a proposta.
  - Várias propostas com decisões diferentes: `outro`.

### `relator`

O relator vai como está escrito no recorte (nome do diretor ou sigla da área), ou `""` se não houver.

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

1. Cada campo sai só do recorte. Se o recorte não basta, use `""` (ou `outros` no tema).
2. Nenhum campo leva nome de pessoa física, salvo `relator`.
3. Leia cada julgado inteiro antes de escrever. A deliberação manda; os blocos de pedido, fundamentos e área técnica explicam.
4. Grave só `saida.json`, com JSON válido e todos os ids da entrada.
