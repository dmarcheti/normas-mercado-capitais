# Replay: aplicar um ato alterador a uma norma

Procedimento para o agente que reconstrói o histórico de uma norma, ato por ato. Um ato = uma versão do arquivo da norma. O agente só escreve arquivos; commit é de quem dispara o agente.

## Entrada

- `norma_atual`: o arquivo da norma na versão anterior (a primeira é a redação original, vinda do DOU, já convertida com `dou_html_para_md` e `normalizar_artigos`).
- `texto_ato`: o texto integral do ato alterador, também do DOU, convertido da mesma forma.
- `numero_ato`, `data_dou`: do `fontes/inventario.json`.

## Saída

1. A norma alterada: o mesmo arquivo, com só o que o ato manda mudar.
2. O texto do ato em `alteradoras/<NNNN>.md`, integral (inclusive o que ele altera em outras normas), com o frontmatter da SPEC e `versao_texto: original`. Só os artigos do próprio ato viram `## Art.`; artigos citados dentro das redações novas ficam como texto.

## Regras de aplicação

1. Leia o ato inteiro e liste, por norma-alvo, os dispositivos tocados. Aplique só os que dizem respeito à norma em processamento; as demais normas do ato ficam para quando elas forem processadas.
2. Convenções dos atos da CVM:
   - Redação entre aspas, terminada em `(NR)`: substitui o dispositivo citado. Aspas e `(NR)` não vão para a norma.
   - Linha de pontos (`.....`) ou `Art. 5º ......`: o resto do dispositivo fica como está. Só troque o que o ato escreve por extenso.
   - Dispositivo novo (`Art. 7º-A`, `§ 3º-A`, `III-A`): insira na posição da numeração. Artigo novo vira `## Art. 7º-A`.
   - "Ficam revogados": o dispositivo permanece com a marca `(Revogado)` (ou `(Revogado pela Resolução CVM nº X)`), nunca some do texto.
   - Anexos e tabelas: troque só a linha ou o item que o ato cita.
3. Copie o texto do ato literalmente. Não reescreva, não corrija erro do ato, não complete, não modernize pontuação (exceto retirar as aspas de citação e o `(NR)`). Se o ato está ambíguo ou contradiz a norma (por exemplo, cita uma data de publicação errada), aplique o que está escrito e anote em `incerteza`.
4. Vigência diferida: se a vigência do ato é posterior à data-base do acervo (`baixado_em`), o dispositivo fica com as duas redações: a atual e, depois dela, a futura, aberta por uma linha `Vigente a partir de AAAA-MM-DD`, e o frontmatter ganha `vigencia_inicio`. Se a vigência já passou na data-base, aplique direto a nova redação e registre as datas de vigor em `incerteza`.
5. Não invente texto. Nenhuma frase na norma que não esteja na versão anterior ou no ato.

## Frontmatter a cada ato

Mude só o necessário, mantendo as chaves e a ordem da SPEC:

- `versao_texto`: `consolidado` depois do primeiro ato; `original` só na redação original.
- `vigente_ate_ato`: número do ato aplicado.
- `incerteza`: o que o agente não conseguiu resolver (vazio se nada).
- `aguarda_consolidado_oficial`: `true` se o ato ainda não consta no consolidado da CVM.
- `historico_parcial`: `true` se faltar algum ato da lista de alteradoras do inventário.

## Verificações (rodam a cada ato, em ordem)

1. `validar_norma(<arquivo>)` devolve lista vazia.
2. Teste 1: `diff` unificado (difflib) entre a versão anterior e a nova; `linhas_novas_fora_do_ato(diff, texto_ato)` devolve lista vazia. Uma correção por ato.
3. Falhou de novo: pare, registre em `fontes/DIVERGENCIAS.md` (linha afetada, causa, decisão) e siga para o ato seguinte.
4. Depois do último ato: teste 2, `diferencas_final(norma_final, consolidado_docx_convertido)`. Diferenças vão para `fontes/DIVERGENCIAS.md`, com a causa quando conhecida.

## Limites

- Sem git: o agente não faz add, commit nem checkout. O commit usa a identidade de replay e a data do DOU e é feito por quem dispara o agente.
- Cada ato é lido do DOU (`url_dou` no inventário); a página do ato no site da CVM (DOCX) serve só de conferência do texto.
- Se o ato não couber na tarefa (muitas normas-alvo, ou dispositivo que o procedimento não cobre), pare e diga o que falta.
