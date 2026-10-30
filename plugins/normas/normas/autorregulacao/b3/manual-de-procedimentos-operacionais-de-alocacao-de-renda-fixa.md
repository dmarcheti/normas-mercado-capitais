---
id: b3-manual-de-procedimentos-operacionais-de-alocacao-de-renda-fixa
orgao: b3
tipo: manual
numero:
data: 2026-05-25
publicacao_dou:
ementa: Manual de Procedimentos Operacionais de Alocação de Renda Fixa
situacao: vigente
versao_texto: original
vigente_ate_ato:
aguarda_consolidado_oficial: false
historico_parcial: true
fonte_original: https://www.b3.com.br/data/files/D3/12/3E/75/8205E91064BF82E9AC094EA8/MPO%20de%20Alocacao%20de%20Renda%20Fixa%20-%2025052026%20-%20Sem%20marca.pdf
fonte_consolidada: https://www.b3.com.br/data/files/D3/12/3E/75/8205E91064BF82E9AC094EA8/MPO%20de%20Alocacao%20de%20Renda%20Fixa%20-%2025052026%20-%20Sem%20marca.pdf
sha256_fonte: 5b3c842df6d0ba1e662ab085904b01aa6a910b0c61247d70746546d381bbd6f3
baixado_em: 2026-10-29
verificado_em: 2026-10-29
incerteza: Documento de autorregulação da B3 (versão de 2026-05-25), extraído por script do PDF, data-base 2026-10-29. Vincula só as instituições aderentes ou participantes. Texto de titularidade da B3, reproduzido para uso informativo; retirado a pedido (ver autorregulacao/README.md). Extraído de PDF: quebras de linha, tabelas e numeração podem estar deslocadas [verificar].
nivel_verificacao: pdf-extraido
---

MANUAL DE

PROCEDIMENTOS

OPERACIONAIS

DE ALOCAÇÃO

DO MERCADO DE

BALCÃO DE

RENDA FIXA

VERSÃO – 25/maio/2026

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

ÍNDICE

REGISTRO DE ALTERAÇÕES ................................................................................................ 3

1. INTRODUÇÃO ......................................................................................................................... 4

2. PARTICIPANTES E CONTAS .................................................................................................. 4

2.1. Participantes ............................................................................................................ 5

2.2. Conta ........................................................................................................................ 5

2.2.1. Tipos de Contas ...................................................................................................... 5

2.2.2. Vínculo entre Contas e Participantes .................................................................. 6

3. MODALIDADES DE OPERAÇÕES ........................................................................................... 7

4. CAPTURA E ALOCAÇÃO ........................................................................................................ 7

4.1. Captura de negócios .............................................................................................. 7

4.1.1. Validações na captura de negócios ..................................................................... 7

4.1.2. Cancelamento de negócio fechado na Plataforma de Negociação do Balcão

B3 9

4.2. Alocação de negócios ............................................................................................ 9

4.2.1. Inclusão de alocação ........................................................................................... 10

4.2.2. Alteração de alocação ......................................................................................... 11

4.2.3. Cancelamento de alocação ................................................................................ 12

4.2.4. Alocação de operação de intermediação ......................................................... 12

4.2.5. Confirmação da alocação .................................................................................... 14

4.2.6. Geração de número de comando Selic............................................................. 15

4.2.7. Geração de número de controle para negócios alocados que envolvam

Ativos Depositados ............................................................................................................... 16

4.2.8. Confirmação de Posição para Ativos Depositados ......................................... 16

4.2.9. Rejeição da Alocação de negócios que envolvam Ativos Depositados ...... 16

4.2.10. Grades de alocação de negócios envolvendo Títulos Selic .......................... 17

4.2.11. Grades de alocação de negócios envolvendo Ativos Depositados .............. 18

4.2.12. Grades de confirmação de Posição de Ativos Depositados .......................... 18

4.2.13. Disposições Gerais .............................................................................................. 19

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

REGISTRO DE ALTERAÇÕES

Número da

alteração

Data de entrada em

vigor do normativo

Ofício Circular que divulgou a

alteração normativa*

1 14/12/2020 173/2020-PRE

2 04/05/2022 047/2022-PRE

3 11/03/2024 028/2024-PRE

4 01/04/2024 045/2024-PRE

5 02/05/2024 063/2024-PRE

6 05/08/2024 103/2024-PRE (Revogado)

substituído por 116/2024-PRE

7 07/08/2025 015/2025-VPE

8 25/05/2026 012/2026-VPE

*Ofício Circular por meio do qual a alteração foi divulgada.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

1. INTRODUÇÃO

O presente Manual de Procedimentos Operacionais tem por objetivo, observado o

disposto nas Normas do Balcão B3 e, em especial, o disposto no Regulamento do

Balcão B3 e no Manual de Normas da Plataforma de Negociação do Balcão B3, definir

as disposições específicas aplicáveis aos procedimentos de alocação de negócios que

tenham por objeto Título Selic e Ativos Depositados cadastrados na Plataforma de

Negociação do Balcão B3 ou em Sistema Externo que atue como mercado

regulamentado de valores mobiliários autorizado pela CVM, no Sistema de Alocação.

No caso de Sistema Externo, os procedimentos de alocação contemplarão as etapas e

os Ativos estabelecidos no contrato de prestação de serviço entre a B3 e o respectivo

Sistema Externo.

O presente manual está organizado com a finalidade de permitir maior clareza para os

Participantes no entendimento dos fluxos aplicáveis, critérios de validação e

funcionalidades presentes no Sistema de Alocação. Os capítulos apresentam os

principais temas relacionados ao fluxo de alocação disponibilizado aos Participantes

que utilizam o Sistema de Alocação para alocação dos seus negócios.

Às definições dos termos com iniciais em maiúscula, em suas formas no singular e no

plural, utilizadas neste manual aplicam-se as definições e os significados constantes do

Glossário das Normas do Balcão B3.

Os termos usuais dos mercados financeiro e de capitais, os de natureza jurídica,

econômica e contábil e os termos técnicos de qualquer outra natureza empregados

neste manual, e não constantes do Glossário das Normas do Balcão B3 têm os

significados geralmente aceitos no Brasil.

2. PARTICIPANTES E CONTAS

O Sistema de Alocação de negócios utiliza a estrutura de Participantes e Contas

previstas nas Normas do Balcão B3.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

2.1. Participantes

Os Participantes que poderão optar pela utilização das funções de alocação e

confirmação de alocação, disponibilizadas pelo Sistema de Alocação, são aqueles

detentores dos seguintes Direitos de Acesso:

1. à Plataforma de Negociação do Balcão B3; e

2. à Plataforma de Negociação do Balcão B3 para Gestor.

A classificação de Família de Front, nos termos do Glossário das Normas do Balcão B3,

é aplicada aos Participantes que realizam a negociação na Plataforma de Negociação

do Balcão B3 ou, no Sistema Externo que atue como mercado regulamentado de valores

mobiliários autorizados pela CVM, que podem realizar as devidas alocações e

confirmações no Sistema de Alocação, conforme definido neste Manual de

Procedimentos Operacionais.

Os Participantes elegíveis ao recebimento das informações de alocação de negócios

para posterior Registro no Selic, no Subsistema de Registro ou no Subsistema de

Depósito Centralizado do Balcão B3 são aqueles detentores do Direito de Acesso ao

Subsistema de Registro, ao Subsistema de Depósito Centralizado e ao Subsistema de

Compensação e Liquidação. Esses Participantes são classificados como Família de

Back.

2.2. Conta

As Contas passíveis de utilização no processo de alocação de negócios realizados na

Plataforma de Negociação do Balcão B3 ou em Sistema Externo e que tenham por

objeto Títulos Selic ou Ativos Depositados são aquelas pertencentes à estrutura

cadastral do SELIC ou do Balcão B3 cadastradas pelo Participante no Sistema do

Balcão B3 e com situação válida.

2.2.1. Tipos de Contas

As Contas passíveis de alocação são as seguintes:

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

I. Contas Selic:

a. SI - Conta de Intermediação Selic; e

b. SL – Conta Própria Selic

II. Contas do Balcão B3, cujas definições constam no Glossário de Normas do

Balcão B3:

a. PO – Conta Própria;

b. IN – Conta Intermediação;

c. C1/C2 – Conta de Cliente;

d. EM – Conta de Agente de Registro ou Conta de Agente de Depósito

e. (Conta Emissora); e

RT – Conta Reserva Técnica

2.2.2. Vínculo entre Contas e Participantes

Para uma Conta estar habilitada ao processo de alocação, ela deve estar ativa e

vinculada a pelo menos um Participante ativo na Plataforma de Negociação do Balcão

B3 ou no Sistema Externo e a somente um Participante ativo no Subsistema de Depósito

Centralizado.

A vinculação de uma Conta a um Sistema Externo está condicionada à autorização

prévia do Participante responsável pela conta junto ao Balcão B3, nos termos do

Regulamento do Balcão B3 e, quando aplicável, ao previsto no contrato entre a B3 e o

respectivo Sistema Externo.

O vínculo entre a Conta e o Participante da Plataforma de Negociação do Balcão B3

carrega a identificação do Ofertante dentro do Participante, e que pode originar negócios

para serem alocados naquela Conta. Esta informação é utilizada no processo de captura

e alocação.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

3. MODALIDADES DE OPERAÇÕES

A negociação realizada na Plataforma de Negociação do Balcão B3, a Compra e a

Venda previamente realizada cujas condições sejam informadas no Módulo Voice, que

tenham por objeto Títulos Selic, Ativos Depositados, habilitados na Plataforma de

Negociação do Balcão B3 e a negociação em Sistema Externo são aceitas no Sistema

de Alocação.

A B3 não é contraparte central garantidora das operações realizadas na Plataforma de

Negociação do Balcão B3 ou em Sistema Externo, de forma que, no desempenho das

suas atividades:

I - não é responsável, direta ou indiretamente, pelo adimplemento ou satisfação

dos direitos referentes a tais operações, assim como pelas Liquidações das

operações; e

II – em decorrência do disposto no inciso I, incumbe aos Participantes manter

estruturas e processos próprios para gerenciar adequadamente os riscos de

crédito e de liquidez das operações que realizem em seu nome e em nome de

seus clientes.

4. CAPTURA E ALOCAÇÃO

4.1. Captura de negócios

Os negócios realizados na Plataforma de Negociação do Balcão B3 ou em Sistema

Externo são capturados automaticamente pelo Sistema de Alocação.

4.1.1. Validações na captura de negócios

Dentre os requisitos a serem verificados no processo de captura, consideram-se:

1. a situação e a habilitação das Contas dos Participantes ou dos participantes

do Sistema Externo envolvidos na operação.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

2. neste momento, é validado se os Participantes envolvidos no negócio

enviado à Plataforma de Negociação do Balcão B3 ou dos participantes

envolvidos no negócio realizado no Sistema Externo estão devidamente

cadastrados junto ao Sistema do Balcão B3;

3. a data e o horário do negócio;

4. o ativo objeto da operação. O Sistema de Alocação valida se o negócio

envolve Título Selic e Ativos Depositados, e se os Participantes e Contas

estão habilitados para alocação deste tipo de ativo;

5. A identificação do Ofertante e vínculo de Conta informada pelo Participante;

e

6. o Título Selic ou Ativo Depositado objeto do negócio deve ser compatível

com os mercados habilitados para os Participantes e para as Contas.

Se a mensagem recebida da Plataforma de Negociação do Balcão B3 ou de Sistema

Externo tiver o indicativo de “auto-alocação” em algum dos lados do negócio, o Sistema

de Alocação irá efetuar automaticamente a alocação total do negócio para a Conta

própria Selic ou Conta Própria previamente indicada pelo participante do negócio. Caso

a informação de Conta previamente indicada não estiver estabelecida no Sistema de

Alocação no momento da captura do negócio, o sistema não efetuará a alocação

automática e o negócio permanecerá não alocado.

Se a mensagem recebida da Plataforma de Negociação do Balcão B3 ou de Sistema

Externo indicar que algum dos lados do negócio pertence a uma operação de

intermediação, o Sistema de Alocação irá efetuar automaticamente a alocação total do

negócio para a Conta de Intermediação Selic ou Conta de Intermediação previamente

indicada pelo participante parte do negócio. Caso a informação de Conta de

Intermediação previamente indicada não estiver estabelecida no Sistema de Alocação

no momento da captura do negócio, o sistema não efetuará a alocação automática e o

negócio permanecerá não alocado. Além disso, neste momento também é validado se

a operação de intermediação não possui mais do que três negócios e se o número da

intermediação recebido da Plataforma de Negociação do Balcão B3 ou de Sistema

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

Externo já não foi utilizado. Em qualquer um dos casos, o sistema não efetuará a

alocação automática e o negócio permanecerá como não alocado.

Caso o mesmo lado de um negócio tenha indicativo de “auto-alocação” e de

intermediação, o Sistema de Alocação não efetuará a alocação automática e o negócio

permanecerá não alocado.

Os negócios que atenderem aos requisitos estabelecidos e que forem alocados terão

seus detalhes informados aos Participantes envolvidos, por meio de tela do Sistema de

Alocação, ou de mensagens e arquivos eletrônicos, conforme formatos estabelecidos

no catálogo de mensagens e arquivos da B3.

4.1.2. Cancelamento de negócio fechado na Plataforma de Negociação do

Balcão B3 ou em Sistema Externo

O Cancelamento de negócio somente pode ser efetuado se observadas as seguintes

condições:

1. a solicitação de cancelamento somente pode ser tratada se for recebida antes

do encerramento da grade de alocação;

2. se a alocação do negócio não tiver sido confirmada por alguma das partes, o

Cancelamento é efetivado pelo Sistema de Alocação, onde o status do negócio

é alterado para cancelado e os Participantes ou Sistema Externo envolvidos são

informados por meio de tela e/ou mensagem, conforme o caso; e

3. se a alocação do negócio tiver sido confirmada por ambas as partes, o

Cancelamento não é efetivado pelo Sistema de Alocação, onde o status do

negócio é alterado para “cancelado somente no sistema de negociação” e os

Participantes ou Sistema Externo envolvidos são informados por meio de

mensagem e/ou outro meio específico, conforme o caso.

4.2. Alocação de negócios

A alocação é o procedimento por meio do qual os Participantes responsáveis pela

negociação realizam a identificação das Contas mencionadas no item 2.2.1 para cada

negócio.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

4.2.1. Inclusão de alocação

A inclusão de alocação é realizada negócio a negócio de forma total, dentro das grades

de alocação, sendo composta de três etapas:

1. Fornecimento de informações pelo Participante ao Sistema de Alocação, com

destaque para:

a. código das Contas previamente cadastradas no sistema de cadastro

do Sistema do Balcão B3 até o dia útil anterior;

b. número do negócio;

c. quantidade de cada alocação; e

d. identificação de Cliente quando a conta alocada for C1 ou C2,

observado que tal identificação é opcional e que não é validada pelo

Sistema de Alocação

2. Fornecimento pelo Participante que atue como vendedor ao Sistema de

Alocação para procedimentos de alocação de Ativos Depositados das

seguintes informações:

a. Identificação quando o negócio for alocado para uma posição de

Bloqueio Judicial;

b. Identificação quando o negócio for desvinculado de uma posição de

Reserva Técnica;

3. O sistema de Alocação não valida o saldo de ativos disponível nas posições

referidas no item 2 acima.

4. Validação das informações recebidas. Nesta etapa, o Sistema de Alocação

efetua a validação das informações recebidas observado que:

a. a Conta alocada deve estar habilitada no Selic para Título Selic e

cadastrada no Sistema do Balcão B3 para o Título Selic e para o Ativo

Depositado objeto do negócio;

b. a soma das quantidades de cada alocação deve ser igual à quantidade

total do negócio;

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

5. c. d. e. o vínculo entre a Conta e o Participante da Plataforma de Negociação

do Balcão B3 ou do Sistema Externo deve ter as informações

cadastrais iguais às que foram validadas na captura do negócio;

a alocação do negócio não pode ter sido previamente confirmada pelo

Participante, conforme descrito no item 4.2.5 deste manual;

não é permitida que a mesma Conta seja informada em ambos os lados

do negócio;

i. Regra não aplicada quando as contas alocadas forem C1 ou

C2;

f. se a alocação for realizada para uma Conta de Intermediação, a

quantidade alocada deve ser igual à quantidade total do negócio; e

g. não é permitido que o mesmo Cliente final seja informado em ambos

os lados do negócio.

Resposta da alocação. Após a validação das informações recebidas, o sistema

fornece para o Participante o resultado da alocação e a ocorrência de erros,

se aplicável.

A partir do momento em que o Sistema de Alocação conhece as Contas alocadas em

cada negócio, o Participante responsável pelo Registro da operação (Família de Back),

que envolva Título Selic ou Ativo Depositado, passa a receber informações sobre a

evolução do processo de alocação.

A inclusão da alocação deve ser realizada pelos Participantes dentro das grades de

alocação. Caso o Participante não realize a inclusão da alocação, deve realizar o

cancelamento do negócio fechado na Plataforma de Negociação do Balcão B3

observando o disposto no item 4.1.2.

O Participante que não realizar a inclusão da alocação e/ou não realizar o cancelamento

do negócio fechado na Plataforma de Negociação do Balcão B3 será considerado

inadimplente e estará sujeito às penalidades previstas no Regulamento do Balcão B3.

4.2.2. Alteração de alocação

Para alterar a alocação de um negócio, o Participante pode realizar uma nova inclusão

de alocação, conforme descrito no item 4.2.1 deste manual. Caso a nova inclusão de

alocação seja realizada com sucesso, as alocações anteriores são removidas.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

A alteração da alocação não pode ser efetuada de forma parcial e somente pode ser

solicitada se a alocação não tiver sido previamente confirmada pelo Participante,

conforme descrito no item 4.2.5 deste manual.

Se o negócio que terá a alocação alterada pertencer a uma intermediação registrada no

sistema, a alteração da alocação não é permitida. O Participante deve primeiramente

realizar a exclusão da intermediação, conforme descrito no item 4.2.4 deste manual, e

depois realizar a inclusão da alocação.

4.2.3. Cancelamento de alocação

O cancelamento de alocação de uma operação é o processo pelo qual o Participante

solicita a exclusão do negócio anteriormente alocado das respectivas Contas.

Para realizar o cancelamento da alocação de um negócio, o Participante deve informar,

por meio de tela ou mensagem, o número do negócio que deve ter a alocação

cancelada.

O Cancelamento da alocação não pode ser efetuado de forma parcial e somente pode

ser solicitado se a alocação não tiver sido previamente confirmada pelo Participante,

conforme descrito no item 4.2.5 deste manual.

Se o negócio cujo Cancelamento da alocação foi solicitado pertencer a uma

intermediação registrada no sistema, o cancelamento da alocação não é permitido. O

Participante deve primeiramente realizar a exclusão da intermediação, conforme

descrito no item 4.2.4.

Para Ativos Depositados, o cancelamento da alocação pode ser efetuado somente se o

procedimento de confirmação de posição de ativos entre as partes envolvidas do

negócio, não tiver sido iniciado.

4.2.4. Alocação de operação de intermediação

A operação de intermediação de Títulos Selic ou Ativo Depositado pode ser recebida

diretamente da Plataforma de Negociação do Balcão B3 ou do Sistema Externo no

processo de captura de negócios, conforme descrito no item 4.1.1 deste manual, ou

pode ser inserida pelo Participante diretamente no Sistema de Alocação.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

No caso de operação de intermediação recebida diretamente da Plataforma de

Negociação do Balcão B3 ou do Sistema Externo, as validações das informações da

operação de intermediação são efetuadas no momento da captura dos negócios,

conforme descrito no item 4.1.1 deste manual.

O Participante pode realizar a inserção da operação de intermediação diretamente no

Sistema de Alocação, dentro da grade de alocação, através das seguintes etapas:

1. Fornecimento de informações ao Sistema de Alocação, contendo:

a. o código da Conta de Intermediação Selic deve estar previamente

cadastrado no Sistema do Balcão B3 até o dia útil anterior; e

b. a indicação de número dos negócios envolvidos na intermediação,

sendo no máximo dois negócios por intermediação. Em caso de

intermediação parcial, no qual apenas um dos negócios será alocado

integralmente no Sistema de Alocação, o Participante pode informar

apenas um número de negócio.

2. Validação das informações recebidas. Nesta etapa, o Sistema de Alocação

efetua a validação das informações recebidas observado que:

a. a Conta de Intermediação alocada deve estar habilitada no Selic e

cadastrada no Sistema do Balcão B3 para o Título Selic objeto dos

negócios. Para Ativo Depositado, a Conta Intermediação deve estar

habilitada e cadastrada no Sistema do Balcão B3;

b. c. d. pode haver, no máximo, dois negócios envolvidos na intermediação;

o vínculo entre a Conta e o Participante deve ter as informações iguais

às que foram validadas na captura do negócio;

os negócios informados devem ser alocados para a mesma Conta, ter

o mesmo ativo, ter a mesma data de Liquidação, ter a mesma data de

negociação, ter a mesma quantidade e terem natureza de operação

diferente;

e. as operações de intermediação não podem ter sido previamente

utilizadas em outras intermediações ou não podem envolver mais do

que três negócios, mesmo que em outro Participante;

f. as alocações dos negócios envolvidos na intermediação não podem ter

sido previamente confirmadas pelo Participante, conforme descrito no

item 4.2.5 deste manual; e

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

g. os negócios informados na intermediação não podem ter a alocação

de ambos os lados do negócio para a mesma Conta.

3. Resposta da inclusão da operação de intermediação. Após a validação da

inclusão da operação de intermediação, o sistema fornece para o Participante

o resultado da inclusão e a ocorrência de erros, se aplicável.

Se os negócios informados na intermediação já tiverem sido alocados para outras

Contas, caso a inclusão da operação de intermediação seja validada com sucesso, as

alocações anteriores são removidas e os negócios permanecerão alocados na Conta

de Intermediação.

Para operações de intermediação capturadas diretamente da Plataforma de Negociação

do Balcão B3, do Sistema Externo ou incluídas no Sistema de Alocação, o Participante

deve efetuar a confirmação da operação de intermediação, podendo ser:

1. 2. parcial: quando a intermediação envolve apenas um negócio; e

total: quando a intermediação envolve dois negócios.

O Participante pode efetuar a confirmação da operação de intermediação diretamente

no processo de inclusão da intermediação em um passo único.

O Participante também pode realizar a exclusão da operação de intermediação no

Sistema de Alocação, caso o processo de alocação de todas as operações envolvidas

na intermediação não tiver sido finalizado. Após a exclusão da intermediação, as

alocações são removidas da Conta de Intermediação e os negócios permanecem não

alocados.

4.2.5. Confirmação da alocação

Após a realização da alocação, o Participante deve efetuar a sua confirmação.

No próprio processo de inclusão da alocação, o Participante já pode efetuar a

confirmação da alocação em um passo único.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

O Participante pode informar no Sistema de Alocação se a Conta própria previamente

indicada, a ser utilizada no processo de “auto-alocação”

, pode ter confirmação

automática na captura da operação. Esta funcionalidade não é aplicável para Contas de

Intermediação, que obrigatoriamente necessitam de confirmação da alocação pelo

Participante através do processo de intermediação, conforme descrito no item 4.2.4.

Para negócios que tenham por objeto Ativos Depositados, a confirmação da alocação é

obrigatória para que ocorra o envio do registro de negócio para o Subsistema de

Depósito Centralizado.

A confirmação da alocação deve ser realizada pelos Participantes dentro das grades de

alocação. Caso o Participante não confirme a alocação, deve realizar o cancelamento

do negócio fechado na Plataforma de Negociação do Balcão B3 observando o disposto

no item 4.1.2.

O Participante que não confirmar a alocação e/ou não realizar o cancelamento do

negócio fechado na Plataforma de Negociação do Balcão B3 será considerado

inadimplente e estará sujeito às penalidades previstas no Regulamento do Balcão B3.

4.2.6. Geração de número de comando Selic

Após a confirmação da alocação em ambos os lados do negócio, o Sistema de Alocação

efetua automaticamente a quebra das alocações em pares de compradores e

vendedores. Para cada par de comprador e vendedor, o Sistema de Alocação atribui

um número de comando Selic da faixa exclusiva da B3 para atendimento do processo

de alocação dos negócios realizados na Plataforma de Negociação do Balcão B3.

Para negócios não alocados ou não confirmados em ambos os lados do negócio, o

Sistema de Alocação não atribui número de comando Selic.

Para negócios pertencentes a uma operação de intermediação, a geração do número

de comando somente ocorre quando todos os negócios estão alocados e confirmados

por todos os Participantes envolvidos. O Sistema de Alocação leva em consideração os

compradores e vendedores finais da operação de intermediação para determinar os

pares de compradores e vendedores.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

4.2.7. Geração de número de controle para negócios alocados que envolvam

Ativos Depositados

Após a confirmação da alocação por ambos os lados do negócio, o Sistema de Alocação

efetua automaticamente a quebra das alocações em pares de compradores e

vendedores.

Para cada par de comprador e vendedor, o Sistema de Alocação cria um número de

controle de operação de compra e venda, utilizando o mesmo padrão do Sistema do

Balcão B3, para atendimento do processo de alocação dos negócios que tenham

condições informadas no Módulo Voice ou que sejam realizados na Plataforma de

Negociação de Balcão B3 ou em Sistema Externo e posterior Registro e liquidação.

Para negócios pertencentes a uma operação de intermediação, a geração do número

de controle somente ocorre quando todos os negócios estão alocados e confirmados

por todos os Participantes envolvidos. O Sistema de Alocação leva em consideração os

compradores e vendedores finais da operação de intermediação para determinar os

pares de compradores e vendedores.

4.2.8. Confirmação de Posição para Ativos Depositados

Após a alocação e a geração do número controle de operação, o Sistema de Alocação

envia o negócio para confirmação de posição pelos Participantes envolvidos no negócio

que podem realizar a confirmação da seguinte forma:

• ambas as partes do negócio confirmando no Sistema de Alocação;

• ambas as partes do negócio confirmando no Subsistema de Depósito

Centralizado; ou

• uma das partes confirma a posição no Sistema de Alocação e a outra confirma

a posição no Subsistema de Depósito Centralizado.

O Sistema Externo não atua no processo de confirmação de posição para Ativos

Depositados.

4.2.9. Rejeição da Alocação de negócios que envolvam Ativos Depositados

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

Caso qualquer dos Participantes envolvidos no processo de confirmação de posição do

ativo do negócio objeto de alocação:

(i) (ii) rejeite a alocação realizada no Sistema de Alocação, o número controle da

operação será cancelado e o Sistema de Alocação enviará a mensagem de

cancelamento para o Subsistema de Depósito Centralizado.

rejeite a alocação no Subsistema de Depósito Centralizado, este enviará

uma mensagem de integração para o Sistema de Alocação cancelando o

número de controle gerado.

Caso os Participantes queiram reenviar a operação para o Subsistema de Depósito

Centralizado, será necessário realizar uma nova alocação, gerando um novo número de

controle de operação que irá novamente para aprovação dos Participantes.

O Sistema Externo não atua no processo de rejeição de alocação.

4.2.10. Grades de alocação de negócios envolvendo Títulos Selic

Para negócios com Liquidação em D+0 e negócios com Liquidação em data futura

envolvendo Títulos Selic os processos de alocação e confirmação de alocação devem

ser efetuados respeitando os seguintes horários:

Modalidade de Operação Horário Limite

Operações com Liquidação em D+0 até as 18h00 do dia da realização da

operação.

Operações com Liquidação em data futura até as 20h00 do dia da realização da

operação.

Após o encerramento da grade de alocação de negócios com Liquidação futura, o

Sistema de Alocação remove todas as informações de negócios e alocações, gerando

o arquivo com o resultado da final da alocação.

Os Participantes podem realizar a inclusão, alteração, cancelamento e confirmação de

alocação ou de operação de intermediação, assim como acompanhar a evolução de

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

cada processo, por meio de tela ou do envio de mensagens eletrônicas ao sistema,

conforme formato estabelecido no catálogo de mensagens e arquivos da B3.

4.2.11. Grades de alocação de negócios envolvendo Ativos Depositados

Para negócios com Liquidação em D+0 e negócios com Liquidação em data futura

envolvendo Ativos Depositados, os processos de alocação e confirmação de alocação

devem ser efetuados respeitando os seguintes horários:

Modalidade de Operação Horário Limite

Operações com Liquidação em D+0 e com

Bancos Liquidantes diferentes para as

Contas alocadas entre a compra e venda

até as 17h40 do dia da realização da

operação.

Operações com Liquidação em D+0 e com

Bancos Liquidantes iguais para as Contas

alocadas entre a compra e venda

até as 20h00 do dia da realização da

operação.

Operações com Liquidação em data futura até as 20h00 do dia da realização da

operação.

O Participante que (i) não incluir a alocação, (ii) não confirmar a alocação, e/ou (iii) não

realizar o cancelamento do negócio fechado na Plataforma de Negociação do Balcão

B3 observando o disposto no item 4.1.2., até o horário limite estipulado acima será

considerado inadimplente e estará sujeito às penalidades previstas no Regulamento do

Balcão B3.

Após o encerramento da grade de alocação de negócios com Liquidação em data futura,

o Sistema de Alocação remove todas as informações de negócios e alocações, gerando

o arquivo com o resultado da alocação.

Os Participantes podem realizar a inclusão, alteração, cancelamento e confirmação de

alocação ou de operação de intermediação, assim como acompanhar a evolução de

cada processo, por meio de tela ou do envio de mensagens ao sistema, conforme

formato estabelecido no catálogo de mensagens e arquivos da B3.

4.2.12. Grades de confirmação de Posição de Ativos Depositados

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

Os processos de confirmação de posição de Ativos Depositados objeto de negócios com

Liquidação em D+0 e negócios com Liquidação em data futura que tenham sido

alocados devem ser efetuados respeitando os seguintes horários:

Modalidade de Operação Horário Limite

Operações com Liquidação em D+0 e com

Bancos Liquidantes diferentes para as

Contas alocadas entre a compra e venda

até as 17h40 do dia da realização da

operação.

Operações com Liquidação em D+0 e com

Bancos Liquidantes iguais para as Contas

alocadas entre a compra e venda

até as 20h00 do dia da realização da

operação.

Operações com Liquidação em data futura até as 20h00 do dia da realização da

operação.

O Participante que não realizar a confirmação de posição de Ativos Depositados e

Valores Mobiliários Registrados, até o horário limite estipulado acima, será considerado

inadimplente e estará sujeito às penalidades previstas no Regulamento do Balcão B3.

Após o encerramento da grade de confirmação de posição de negócios com Liquidação

futura, o Sistema de Alocação remove todas as informações de negócios e alocações,

gerando o arquivo com o resultado da final da alocação.

Os Participantes podem realizar a inclusão, alteração, cancelamento e confirmação de

alocação ou de operação de intermediação, assim como acompanhar a evolução de

cada processo, por meio de tela ou do envio de mensagens ao sistema, conforme

formato estabelecido no catálogo de mensagens e arquivos da B3.

4.2.13. Disposições Gerais

A B3 poderá solicitar aos Participantes envolvidos no processo de alocação, a qualquer

tempo, o envio de informações adicionais para a execução da alocação.

Poderá ocorrer a interrupção do procedimento de alocação, caso a B3 verifique a

suspeita ou a ocorrência de quaisquer irregularidades, mantendo suspenso o

procedimento de alocação, impreterivelmente, até a correção desta irregularidade ou

até o seu cancelamento por encerramento da grade de alocação.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION

Ainda, poderá ocorrer o cancelamento do procedimento de alocação por razões

administrativas e prudenciais, caso não haja o envio de informações adicionais ou o

saneamento da irregularidade identificada.

Na hipótese de ambiguidade entre as disposições contidas neste Manual de Normas e

nas demais Normas do Balcão B3 relacionada às disposições específicas aplicáveis aos

Ativos, às Atividades de Registro, de Depósito Centralizado, de Compensação e

Liquidação e ao Mercado de Balcão Organizado, deve prevalecer o normativo mais

específico, considerando a matéria do objeto da ambiguidade. Caso os normativos e a

matéria não estejam relacionados às disposições específicas aplicáveis aos Ativos, às

Atividades de Registro, de Depósito Centralizado, de Compensação e Liquidação e ao

Mercado de Balcão Organizado, deve prevalecer o Regulamento do Balcão B3.

O presente manual de procedimentos operacionais é aprovado pela Diretoria Colegiada

da B3 e, conforme aplicável, pelos órgãos reguladores competentes, nos termos da

regulamentação editada por estes.

Este Manual de Procedimentos Operacionais entra em vigor na data de 25 de maio de

2026.

INFORMAÇÃO PÚBLICA – PUBLIC INFORMATION
