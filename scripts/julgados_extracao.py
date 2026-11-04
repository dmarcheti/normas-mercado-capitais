"""Extração por LLM de ementa, tema, resultado e relator dos julgados convertidos (Task 4 da 2d).

Lê os julgados de plugins/julgados-*/julgados/, recorta cada um (~1.200 tokens: título; o
"## Extrato" ou as ~600 primeiras e ~400 últimas palavras; o "SUMÁRIO" do parecer do comitê),
monta lotes de 25 em dados/fase-2d/extracao/<lote>/lote.json e roda `claude -p` com
scripts/prompts/julgados-extracao.md numa pasta fora do cofre que só tem o lote. Valida o
saida.json e aplica ao frontmatter, marcado como extração:

- ementa (ementa_fonte: extracao) só onde a ementa veio do título e a classe não é rotineira
  (multa cominatória fica com a ementa de modelo, decisão antiga é o arquivo do ano inteiro);
- tema (tema_fonte: extracao) sempre que vazio;
- resultado e relator só se vazios.

A ementa é reprovada se passar de 60 palavras, trouxer dado pessoal ou nome (ou nome e
sobrenome, ou sobrenome composto) de pessoa física do julgado, pela lista positiva de `Pessoas`.
Reprovada, volta uma vez num lote de retentativa com a instrução reforçada (REFORCO); se falhar
de novo, fica a ementa do título e o item é registrado em `ementa_do_titulo` no validacao.json.

    python3 scripts/julgados_extracao.py --ids a,b --model haiku [--simular]
    python3 scripts/julgados_extracao.py --onda 1 --tipo decisao-colegiado --model haiku

Não roda git. O log stream-json e o custo (total_cost_usd) de cada lote ficam na pasta do lote.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import pii  # noqa: E402

PROMPT = os.path.join(jc.AQUI, "prompts", "julgados-extracao.md")
SAIDA = os.path.join(jc.RAIZ, "dados", "fase-2d", "extracao")
COFRE = os.path.realpath(os.path.expanduser("~/cerebro"))
TAMANHO_LOTE = 25
PALAVRAS_INICIO, PALAVRAS_FIM, PALAVRAS_EXTRATO, PALAVRAS_SUMARIO = 600, 400, 900, 250
PALAVRAS_DELIBERACAO, PALAVRAS_FIM_DECISAO = 300, 200
# parágrafo em que o Colegiado delibera ("O Colegiado, por unanimidade, acompanhou...")
_DELIBERACAO = re.compile(r"\bColegiado\b[^.]{0,160}?\b(?:decidiu|deliberou|acompanh|deu\s+provimento|"
                          r"negou|aprovou|rejeitou|deferiu|indeferiu|aceitou|conheceu|determinou|"
                          r"concluiu|entendeu|votou|julgou)", re.I)
MAX_PALAVRAS_EMENTA = 60
SITUACOES = ("decidido", "suspenso", "sem-deliberacao")  # campo `situacao` da saída (3b)
ROTINEIRAS = {"multa-cominatoria"}  # ementa de modelo, a partir do título, sem LLM (C7)
SEM_EMENTA_EXTRAIDA = {"decisao-antiga"}  # um arquivo por ano, com dezenas de decisões
TEMAS = ("divulgacao-informacoes", "informacao-privilegiada", "manipulacao-fraude",
         "deveres-administradores", "assembleia-acionistas", "ofertas-publicas", "opa",
         "fundos-investimento", "securitizacao", "intermediacao", "administracao-carteiras",
         "auditoria-independente", "contabil-demonstracoes", "registro-emissor",
         "infraestrutura-mercado", "analistas-rating", "exercicio-irregular", "criptoativos",
         "crowdfunding", "pld", "multa-cominatoria-taxa", "processual", "normativo",
         "institucional", "outros")

# ---------------------------------------------------------------- arquivos

_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def ler_julgado(caminho):
    """(valores do frontmatter, corpo) de um julgado gravado pelo conversor."""
    with open(caminho, encoding="utf-8") as f:
        texto = f.read()
    m = _FM.match(texto)
    if not m:
        raise ValueError("%s: sem frontmatter" % caminho)
    valores = {}
    for linha in m.group(1).splitlines():
        k, _, v = linha.partition(":")
        valores[k.strip()] = v.strip()
    return valores, texto[m.end():].lstrip("\n")


def gravar(caminho, valores, corpo):
    tmp = caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(jc.frontmatter(valores) + corpo)
    os.replace(tmp, caminho)


def julgados(raiz=jc.RAIZ):
    """[{id, tipo, data, url: caminho}] dos julgados gravados, para jc.selecionar."""
    out = []
    for c in sorted(glob.glob(os.path.join(raiz, "plugins", "julgados-*", "julgados", "**",
                                           "*.md"), recursive=True)):
        if os.sep + "indices" + os.sep in c:
            continue
        try:
            v, _ = ler_julgado(c)
        except ValueError:
            continue
        if v.get("id"):
            out.append({"id": v["id"], "tipo": v.get("tipo", ""), "data": v.get("data", ""),
                        "url": c, "pendente": not v.get("tema") or quer_ementa(v)})
    return out


# ---------------------------------------------------------------- recorte


def _palavras(texto, n, do_fim=False):
    p = texto.split()
    return " ".join(p[-n:] if do_fim else p[:n])


def _secao(corpo, nome):
    m = re.search(r"(?ms)^## %s\s*\n(.*?)(?=^## |\Z)" % re.escape(nome), corpo)
    return m.group(1).strip() if m else ""


def recorte(corpo):
    """Título; o "## Extrato" ou as ~600 primeiras e ~400 últimas palavras; o bloco "SUMÁRIO"
    do parecer, se houver."""
    m = re.search(r"(?m)^# (.+)$", corpo)
    titulo = m.group(1).strip() if m else ""
    texto = re.sub(r"(?m)^# .+\n?", "", corpo, count=1).strip()
    texto = re.sub(r"(?m)^#{2,6}\s+", "", texto)
    extrato = _secao(corpo, "Extrato")
    if extrato:
        miolo = _palavras(extrato, PALAVRAS_EXTRATO)
    elif len(texto.split()) <= PALAVRAS_INICIO + PALAVRAS_FIM:
        miolo = texto
    else:
        miolo = (_palavras(texto, PALAVRAS_INICIO) + "\n[...]\n"
                 + _palavras(texto, PALAVRAS_FIM, do_fim=True))
    partes = [titulo, miolo]
    # Colegiado: a deliberação costuma ficar no meio da "## Decisão", e o fim do documento é o
    # anexo da área técnica; entram os parágrafos de deliberação e o fim da seção
    decisao = re.sub(r"(?m)^#{2,6}\s+", "", _secao(corpo, "Decisão"))
    if not extrato and decisao and decisao.strip() not in miolo:
        delib = [p.strip() for p in re.split(r"\n\s*\n", decisao) if _DELIBERACAO.search(p)]
        delib = [p for p in delib if p not in miolo]
        if delib:
            partes.append("DELIBERAÇÃO: " + _palavras("\n".join(delib), PALAVRAS_DELIBERACAO))
        fim = _palavras(decisao, PALAVRAS_FIM_DECISAO, do_fim=True)
        if fim not in miolo:
            partes.append("FIM DA DECISÃO: " + fim)
    s = re.search(r"(?m)^\W*SUM[ÁA]RIO\b.*$", texto)
    if s and s.group(0).strip() not in miolo:
        partes.append("SUMÁRIO: " + _palavras(texto[s.end():], PALAVRAS_SUMARIO))
    return "\n\n".join(x for x in partes if x)


# ------------------------------------------------ recorte pela deliberação (fase 3b)
#
# Na "## Decisão" do Colegiado e do TC, a deliberação costuma vir no fim de um relato longo da
# área técnica ou do Comitê, e o fim do documento é o anexo da área técnica. O recorte da 3b
# começa pela deliberação, depois o pedido e os fundamentos, e por último a posição da área
# técnica ou do Comitê, rotulada como tal.

PALAVRAS_DELIB_3B, PALAVRAS_POS_DELIB, PALAVRAS_DECISAO_INTEIRA = 450, 150, 900
PALAVRAS_PEDIDO, PALAVRAS_ANTES_DELIB, PALAVRAS_AREA, PALAVRAS_UNIDADE = 300, 350, 200, 250
# "acompanhou o voto ... a seguir transcrito": o dispositivo do voto fica no fim da "## Decisão"
PALAVRAS_CONCLUSAO = 250
_DELIB_3B = re.compile(
    r"\bColegiado\b(?:[^.;]|\.(?=\s*\d)|(?<=\bS)\.|(?<=\bA)\.|(?<=\bSr)\.|(?<=\bSra)\.|"
    r"(?<=\bDr)\.|(?<=\bart)\.|(?<=\barts)\.|(?<=\bProc)\.|(?<=\bn)\.){0,250}?\b(?:deliber|decid|acompanh|acat|acolh|aprov|defer|indefer|"
    r"neg(?:ou|ar)\b|deu\s+provimento|dar\s+provimento|rejeit|aceit|conhec|conclu|determin|"
    r"autoriz|admit|mant(?:eve|er)\b|conced|diverg|entend|fez\s+exig|julg|homolog|referend|"
    r"resolv|reconhec|reform|cancel|dispens)", re.I)
_ACOMPANHADO = re.compile(r"acompanhad[oa]s?\s+pel[oa]s\s+demais\s+(?:membros|diretores)|"
                          r"demais\s+membros\s+do\s+Colegiado\s+acompanh", re.I)
# o julgamento parou: vista, adiamento, retirada de pauta, sobrestamento
_SUSPENSAO = re.compile(
    r"\b(?:pediu|solicitou|solicitad[oa]|pedido|requereu|requerid[oa]|"
    r"concedid[oa])\s+vistas?\b|"
    r"\bpedido\s+de\s+vistas?\s+d[oa]\s+(?:Diretor|Diretora|Presidente|Relator|Relatora)|"
    r"\badiad[ao]s?\s+(?:a\s+|sua\s+)?(?:decis|delibera|aprecia|discuss|julgamento|exame|"
    r"an[áa]lise)|"
    r"\b(?:decis[ãa]o|aprova\w*|delibera\w*|julgamento)\s+(?:\w+\s+){0,3}?adiad|"
    r"\badiar\s+(?:a\s+|o\s+|sua\s+)?(?:decis|delibera|aprecia|discuss|julgamento|exame|"
    r"an[áa]lise)|"
    r"\b(?:fo(?:i|ram)|sido)\s+retirad[oa]s?\s+de\s+pauta|(?-i:\bRetirad[oa]s?\s+de\s+pauta)",
    re.I)
# vista como acesso aos autos (objeto do pedido), não como suspensão do julgamento
_VISTA_ACESSO = re.compile(r"\s*(?:e\s+(?:de\s+)?(?:c[óo]pia|extra)|integral|,\s*c[óo]pia|"
                           r"ter\b|(?:d[oa]s?\s+autos\s+)?d[oa]s?\s+(?:PAS\b|Proc\.|processo\s+"
                           r"(?:administrativo|sancionador|CVM)|inqu[ée]rito|termo|procedimento))",
                           re.I)
_VISTA_ACESSO_ANTES = re.compile(r"(?:deferi\w*|indeferi\w*|negou|nega\w*|negativa\s+de|"
                                 r"futuro|eventual|tenha|tiver)\s+(?:d?o\s+)?$", re.I)
# menção a uma suspensão anterior ("que havia pedido vista", "(PEDIDO DE VISTA DO DLA)",
# "pediu vista em reunião de 04/10")
_RETROSPECTIVA = re.compile(r"havia|haviam|retorn|retomad|\(pedido\s+de\s+vista", re.I)
_RETROSPECTIVA_DEPOIS = re.compile(r"\s*(?:d[oa]s?\s+(?:autos|processo)\s*,?\s*)?"
                                   r"(?:em|na)\s+(?:reuni[ãa]o|sess[ãa]o)\s+(?:de|anterior|"
                                   r"realizada|do\s+dia)", re.I)
_PARTICIPANTE = re.compile(r"^\W*(?:Participantes\b|[•·]|\(\*\))")
_REG = re.compile(r"(?m)^\W*Reg\.?\s*n")
_CONCLUSAO_AREA = re.compile(r"diante\s+do\s+exposto|ante\s+o\s+exposto|em\s+conclus|"
                             r"pelo\s+exposto|isto\s+posto|por\s+todo\s+o\s+exposto|"
                             r"\bconclus[ãa]o\b", re.I)
_ASSINATURA = re.compile(r"\bAtenciosamente\b|\bDe\s+acordo\.\s+Encaminhe", re.I)
_SECAO_AREA = re.compile(r"Manifesta|Parecer|Memorando|Nota\b|Of[íi]cio|Despacho", re.I)


def limpar_decisao(decisao):
    """A "## Decisão" sem a lista de participantes (o que vem antes de "Reg. nº")."""
    texto = re.sub(r"(?m)^#{2,6}\s+", "", decisao)
    m = _REG.search(texto)
    if m and len(texto[:m.start()].split()) <= 150:
        return texto[m.start():].strip()
    return "\n".join(x for x in texto.splitlines() if not _PARTICIPANTE.match(x)).strip()


def _unidades(texto):
    """Parágrafos; o parágrafo de mais de 250 palavras vira frases."""
    out = []
    for p in re.split(r"\n\s*\n", texto):
        p = re.sub(r"\s+", " ", p).strip()
        if not p:
            continue
        if len(p.split()) > PALAVRAS_UNIDADE:
            out.extend(s for s in re.split(r"(?<=[.;])\s+(?=[\"“*(]?[A-ZÀ-Ý])", p) if s)
        else:
            out.append(p)
    return out


def _delibera(u):
    return bool(_DELIB_3B.search(u) or _ACOMPANHADO.search(u) or _SUSPENSAO.search(u))


def _deliberacao(unidades):
    """Índices das unidades da deliberação: a última que delibera e as anteriores próximas
    (até 2 unidades de intervalo), em até 450 palavras."""
    idx = [i for i, u in enumerate(unidades) if _delibera(u)]
    if not idx:
        return []
    escolhidas, palavras, anterior = [], 0, None
    for i in reversed(idx):
        n = len(unidades[i].split())
        if escolhidas and (anterior - i > 3 or palavras + n > PALAVRAS_DELIB_3B):
            break
        escolhidas.insert(0, i)
        palavras += n
        anterior = i
    return escolhidas


def _area_tecnica(corpo, tipo):
    """Posição da área técnica ou do Comitê, fora da "## Decisão" (até 200 palavras)."""
    secoes = re.findall(r"(?ms)^## (.+?)\s*\n(.*?)(?=^## |\Z)", corpo)
    fora = "\n\n".join(t for nome, t in secoes if nome.strip() != "Decisão")
    s = re.search(r"(?m)^\W*SUM[ÁA]RIO\b.*$", fora)
    if s:
        return _palavras(fora[s.end():], PALAVRAS_AREA)
    if tipo == "termo-compromisso":
        return ""
    for nome, t in secoes:
        if nome.strip() != "Decisão" and _SECAO_AREA.search(nome):
            t = re.sub(r"(?m)^#{2,6}\s+", "", t)
            a = _ASSINATURA.search(t)
            t = t[:a.start()] if a else t  # sem o bloco de assinaturas
            ms = [m for m in _CONCLUSAO_AREA.finditer(t) if len(t[m.start():].split()) >= 40]
            return _palavras(t[ms[-1].start():] if ms else t,
                             PALAVRAS_AREA, do_fim=not ms)
    return ""


def recorte_3b(corpo, tipo="decisao-colegiado"):
    """Recorte que começa pela deliberação do Colegiado; sem "## Decisão", o recorte antigo."""
    decisao = _secao(corpo, "Decisão")
    if not decisao or tipo not in ("decisao-colegiado", "termo-compromisso"):
        return recorte(corpo)
    m = re.search(r"(?m)^# (.+)$", corpo)
    titulo = m.group(1).strip() if m else ""
    unidades = _unidades(limpar_decisao(decisao))
    escolhidas = _deliberacao(unidades)
    texto_inteiro = "\n".join(unidades)
    partes = ["TÍTULO: " + titulo]
    if escolhidas:
        delib = [unidades[i] for i in escolhidas]
        seguintes = []
        for u in unidades[escolhidas[-1] + 1:]:
            if len(" ".join(seguintes + [u]).split()) > PALAVRAS_POS_DELIB:
                break
            seguintes.append(u)
        partes.append("DELIBERAÇÃO DO COLEGIADO (o resultado sai daqui):\n"
                      + "\n".join(delib + seguintes))
        depois = unidades[escolhidas[-1] + 1 + len(seguintes):]
        if depois and len(texto_inteiro.split()) > PALAVRAS_DECISAO_INTEIRA:
            partes.append("CONCLUSÃO DA DECISÃO (últimos parágrafos; se o Colegiado acompanhou um "
                          "voto transcrito, a conclusão do voto está aqui e é a decisão):\n"
                          + _palavras("\n".join(depois), PALAVRAS_CONCLUSAO, do_fim=True))
    else:
        partes.append("FIM DA DECISÃO (não se achou parágrafo de deliberação do Colegiado):\n"
                      + _palavras("\n".join(unidades), PALAVRAS_FIM_DECISAO, do_fim=True))
    texto = "\n".join(unidades)
    if len(texto.split()) <= PALAVRAS_DECISAO_INTEIRA:
        partes.append("DECISÃO NA ÍNTEGRA (traz o pedido e pode trazer a posição da área técnica, "
                      "do Comitê ou do relator, que não são a decisão do Colegiado):\n" + texto)
    else:
        antes = "\n".join(unidades[:escolhidas[0]]) if escolhidas else texto
        inicio = _palavras(antes, PALAVRAS_PEDIDO)
        resto = antes.split()[PALAVRAS_PEDIDO:]
        miolo = inicio + ("\n[...]\n" + " ".join(resto[-PALAVRAS_ANTES_DELIB:]) if resto else "")
        partes.append("PEDIDO E FUNDAMENTOS (trechos da decisão antes da deliberação; podem trazer "
                      "a posição da área técnica, do Comitê ou do relator, que não são a decisão "
                      "do Colegiado):\n" + miolo)
    area = _area_tecnica(corpo, tipo)
    if area:
        partes.append("POSIÇÃO DA ÁREA TÉCNICA OU DO COMITÊ (anexo; não é a decisão do "
                      "Colegiado):\n" + area)
    return "\n\n".join(partes)


def situacao_deliberacao(decisao):
    """"suspenso" se o texto termina com o julgamento parado (vista, adiamento, retirada de
    pauta) sem deliberação depois; "decidido" se há deliberação depois da última suspensão;
    "" se não há nem uma nem outra."""
    texto = re.sub(r"\s+", " ", limpar_decisao(decisao))
    ult_susp = -1
    for m in _SUSPENSAO.finditer(texto):
        antes = texto[max(0, m.start() - 60):m.start()]
        if (_VISTA_ACESSO.match(texto, m.end()) or _VISTA_ACESSO_ANTES.search(antes)
                or _RETROSPECTIVA.search(antes + m.group(0))
                or _RETROSPECTIVA_DEPOIS.match(texto, m.end())):
            continue
        ult_susp = m.start()
    fim_delib = max([m.end() for m in _DELIB_3B.finditer(texto)]
                    + [m.end() for m in _ACOMPANHADO.finditer(texto)] + [-1])
    if ult_susp >= 0 and ult_susp > fim_delib - 1:
        return "suspenso"
    return "decidido" if fim_delib >= 0 else ""


def entrada(caminho, novo=False):
    v, corpo = ler_julgado(caminho)
    m = re.search(r"(?m)^# (.+)$", corpo)
    return {"id": v["id"], "tipo": v.get("tipo", ""), "classe": v.get("classe", ""),
            "processo": v.get("processo", ""), "data": v.get("data", ""),
            "titulo": m.group(1).strip() if m else "",
            "recorte": recorte_3b(corpo, v.get("tipo", "")) if novo else recorte(corpo)}


def _gravar_json(caminho, obj):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def montar_lotes(caminhos, pasta, prefixo, tamanho=TAMANHO_LOTE, pessoas=None, motivos=None,
                 novo=False):
    """Grava <pasta>/<prefixo>-NNN/ com lote.json (o que o modelo vê), caminhos.json e
    pessoas.json (lista positiva de pessoas físicas por id, só para a validação); devolve as
    pastas. `motivos` {caminho: motivo}: lote de retentativa (o motivo vai no item); `novo`:
    recorte pela deliberação (fase 3b)."""
    pessoas = pessoas or Pessoas()
    pastas = []
    for i in range(0, len(caminhos), tamanho):
        d = os.path.join(pasta, "%s-%03d" % (prefixo, i // tamanho + 1))
        os.makedirs(d, exist_ok=True)
        lote, nomes = [], {}
        for c in caminhos[i:i + tamanho]:
            e = entrada(c, novo)
            if motivos:
                e["motivo_retentativa"] = motivos.get(c, "")
            lote.append(e)
            v, corpo = ler_julgado(c)
            nomes[e["id"]] = pessoas.do_julgado(v, corpo)
        _gravar_json(os.path.join(d, "lote.json"), lote)
        _gravar_json(os.path.join(d, "caminhos.json"), caminhos[i:i + tamanho])
        _gravar_json(os.path.join(d, "pessoas.json"), nomes)
        pastas.append(d)
    return pastas


# ---------------------------------------------------------------- modelo


def pasta_de_trabalho(trabalho=None):
    """Pasta nova fora do cofre e do repositório (o modelo só vê o lote)."""
    base = os.path.realpath(trabalho or "/private/tmp")
    for proibida in (COFRE, os.path.realpath(jc.RAIZ)):
        if base == proibida or base.startswith(proibida + os.sep):
            raise ValueError("pasta de trabalho dentro do cofre ou do repositório: %s" % base)
    os.makedirs(base, exist_ok=True)
    return tempfile.mkdtemp(prefix="julgados-extracao-", dir=base)


def comando(modelo):
    return ["claude", "-p", "--model", modelo, "--tools", "Read,Write",
            "--allowedTools", "Read,Write", "--permission-mode", "acceptEdits",
            "--strict-mcp-config", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence"]


def custo(log):
    """total_cost_usd do evento result do stream-json (None se não houver)."""
    for linha in reversed(log.splitlines()):
        try:
            ev = json.loads(linha)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("type") == "result":
            return ev.get("total_cost_usd")
    return None


REFORCO = """

## Retentativa

Estes julgados voltaram porque a ementa da primeira rodada foi reprovada; o motivo está em
`motivo_retentativa` de cada item. Regras reforçadas para a `ementa`:

- no máximo 50 palavras (o limite é 60): conte antes de gravar;
- nenhum nome de pessoa física, nem completo, nem nome e sobrenome, nem sobrenome composto:
  escreva "o acusado", "o diretor", "os conselheiros", "a proponente". Nome de empresa, fundo e
  entidade pode ficar.

Os demais campos seguem as regras acima.
"""


def rodar_lote(pasta_lote, modelo, trabalho=None, timeout=900, reforco=""):
    """Roda o modelo numa pasta só com o lote; copia saida.json e grava log e custo."""
    with open(PROMPT, encoding="utf-8") as f:
        prompt = f.read() + reforco
    prompt += ("\n\n## Tarefa\n\nO lote está em `lote.json`, nesta pasta. Grave `saida.json` "
               "nesta pasta, conforme as regras acima, e nada mais.\n")
    work = pasta_de_trabalho(trabalho)
    shutil.copy(os.path.join(pasta_lote, "lote.json"), os.path.join(work, "lote.json"))
    r = subprocess.run(comando(modelo), input=prompt, cwd=work, capture_output=True, text=True,
                       timeout=timeout)
    with open(os.path.join(pasta_lote, "log.jsonl"), "w", encoding="utf-8") as f:
        f.write(r.stdout or "")
    if r.stderr:
        with open(os.path.join(pasta_lote, "stderr.txt"), "w", encoding="utf-8") as f:
            f.write(r.stderr)
    saida = os.path.join(work, "saida.json")
    if os.path.exists(saida):
        shutil.copy(saida, os.path.join(pasta_lote, "saida.json"))
    info = {"modelo": modelo, "codigo": r.returncode, "total_cost_usd": custo(r.stdout or ""),
            "trabalho": work, "saida": os.path.exists(saida)}
    with open(os.path.join(pasta_lote, "execucao.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    return info


# ---------------------------------------------------------------- pessoas físicas do julgado
#
# A ementa é reprovada se trouxer nome ou sobrenome composto de uma pessoa física do próprio
# julgado (lista positiva). A lista sai de dados/ em tempo de execução e só é gravada em
# dados/ (pessoas.json do lote, fora do Git e fora da pasta que o modelo vê):
#   - acusados do CSV de dados abertos (por NUP);
#   - compromitentes e proponentes das tabelas de TC aceitos e rejeitados (por processo);
#   - partes da descrição do inventário (acusados da listagem de PAS; "apresentada por" etc.);
#   - linhas "Acusado(s):" do corpo (extrato da sessão);
#   - o trecho de partes do título ("TIPO – PARTE – PROC.").
# Fica fora o que tiver marca de entidade (S.A., Ltda, Fundo, Banco...).

ACUSADOS_CSV = os.path.join(jc.RAIZ, "dados", "fase-2d", "inventario", "pas",
                            "processo_sancionador_acusado.csv")
LISTAGENS = os.path.join(jc.RAIZ, "dados", "fase-2d", "listagens")
INVENTARIO = os.path.join(jc.RAIZ, "dados", "fase-2d", "julgados-inventario.json")

_LIGACAO = frozenset(("da", "de", "do", "das", "dos", "e", "d", "del", "della", "di", "van",
                      "von", "y"))
# Palavra que marca entidade (em minúsculas e sem acento): o nome inteiro sai da lista.
_ENTIDADE = frozenset("""
s.a s.a. s/a sa ltda ltda. eireli me epp fia fic fidc fii fip fiagro fiim fim fmp fundo fundos
fund banco bank corretora distribuidora dtvm ctvm participacoes participacao securitizadora
administradora gestora investimentos investimento associacao associados companhia cia cia.
auditores auditoria consultoria consultores advogados sociedade simples holding asset capital
gestao trust partners group grupo industrial industria industrias comercio comercial
construtora incorporadora empreendimentos imobiliaria mineracao metalicos metalurgicos
siderurgica energia eletrica petroleo seguros seguradora previdencia agropecuaria agricola
alimentos servicos tecnologia telecomunicacoes textil engenharia transportes logistica
financeira credito cooperativa instituto fundacao clube bolsa mercados valores mobiliarios
inc ltd llc plc gmbh limited corporation corp co. administracao intervencao liquidacao
recuperacao judicial outros outras brasil brasileira nacional internacional importacao
exportacao representacoes comunicacao editora hotel hoteis farmaceutica quimica
""".split())
# Palavra que não é nome de gente (títulos e descrições do inventário).
_NAO_NOME = frozenset("""
recurso recursos contra decisao decisoes processo processos termo compromisso proposta
propostas pedido pedidos credenciamento autorizacao registro dispensa consulta taxa
fiscalizacao multa cominatoria arquivamento administrativo sancionador inquerito
administrador administradores carteira agente autonomo autonomos diretor diretora diretores
presidente conselheiro conselheiros acusado acusados acusada interessado interessados
recorrente recorrentes proponente proponentes sr sra dr dra cvm sep sin sre smi snc sps soi
sfi sge pfe ssr sse sma spc sdm colegiado comissao superintendencia apreciacao revisao
relator relatora rito ordinario sumario simplificado pas proc procs instrucao resolucao
deliberacao lei art nbc ta oferta publica opa reclamacao denuncia
""".split())
_TRATAMENTO = re.compile(r"^(?:(?:Sr|Sra|Srs|Dr|Dra|Sres)\.?\s+)+", re.I)


def _dobrar(texto):
    """Minúsculas sem acento, um caractere por caractere (mantém as posições)."""
    import unicodedata
    return "".join((unicodedata.normalize("NFD", ch)[0] if ch.strip() else ch).lower()
                   for ch in texto)


def _palavras_nome(nome):
    return re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", nome)


def pessoa(nome):
    """O nome limpo, se parece pessoa física (2 a 8 palavras, sem marca de entidade nem palavra
    de título); senão ""."""
    s = re.sub(r"\([^)]*\)?|[\"“”«»]", " ", nome or "")
    s = re.sub(r"\s+", " ", s).strip(" .,;:-–")
    s = _TRATAMENTO.sub("", re.sub(r"(?i)^(?:ou|e|a|o)\s+", "", s))
    if not s or re.search(r"\d|@|/", s):
        return ""
    toks = _palavras_nome(s)
    dobr = [_dobrar(t).strip(".") for t in toks]
    if any(d in _ENTIDADE or d + "." in _ENTIDADE for d in dobr):
        return ""
    if any(d in _NAO_NOME for d in dobr):
        return ""
    plenas = [d for d in dobr if d not in _LIGACAO and len(d) > 1]
    if not 2 <= len(plenas) <= 8:
        return ""
    return " ".join(toks)


def separar_partes(texto):
    """Nomes de uma lista de partes ("A, B e C"; um por linha; "; ")."""
    texto = re.sub(r"(?i)\be\s+outr[oa]s\b", "", texto or "")
    out = []
    for p in re.split(r"\s*(?:[,;\n]|\s+e\s+|\s+E\s+)\s*", texto):
        n = pessoa(p)
        if n and n not in out:
            out.append(n)
    return out


_DESC_PARTES = (
    re.compile(r"apresentad[ao]s?\s+(?:\(i+\)\s*)?(?:[a-zà-ÿ]+\s+){0,3}?por\s+(.{3,600}?)"
               r"(?:\(|\bna qualidade\b|\bem raz[ãa]o\b|\bno [aâ]mbito\b|\bpara\b|[;:]|\.\s|$)"),
    re.compile(r"interpost[oa]s?\s+pel[oa]s?\s+(.{3,300}?)(?:\(|\bcontra\b|\bna qualidade\b|"
               r"[;:]|\.\s|$)"),
    re.compile(r"INTERESSAD[OA]\(?S?\)?\s*:\s*(.{3,300}?)(?:\s{2,}|\b[A-Z]{4,}\s*:|$)"),
    re.compile(r"[Rr]esponsabilidade de\s+(.{3,200}?)(?:\bpor\b|\(|[;:]|\.\s|$)"),
)


def partes_da_descricao(desc, tipo=""):
    desc = re.sub(r"\s+", " ", desc or "")
    out = []
    if tipo == "pas":  # listagem de PAS: acusados em caixa alta antes da ementa
        m = re.match(r"((?:[A-ZÀ-Ý0-9.,&'’/()\-]+\s+)+?)(?=[A-ZÀ-Ý][a-zà-ÿ]|$)", desc + " ")
        if m:
            out += separar_partes(m.group(1))
    for rx in _DESC_PARTES:
        for m in rx.finditer(desc):
            out += [n for n in separar_partes(m.group(1)) if n not in out]
    return out


_ROTULO = re.compile(r"(?im)^\W*(?:acusad[oa]s?|acusado\(s\)|acusada\(s\)|interessad[oa]s?|"
                     r"recorrentes?|proponentes?|compromitentes?)\s*:[ \t]*(.*)$")
_OUTRO_ROTULO = re.compile(r"^\W*[A-ZÀ-Ý][A-Za-zÀ-ÿ()\s]{1,30}:")


def partes_do_corpo(corpo):
    """Nomes das linhas "Acusado(s):" (e afins) do corpo; o valor pode seguir nas linhas de
    baixo, até o próximo rótulo ("Ementa:", "Assunto:") ou linha em branco."""
    out = []
    linhas = corpo.splitlines()
    for i, ln in enumerate(linhas):
        m = _ROTULO.match(ln)
        if not m:
            continue
        valor = [re.sub(r"(?i)^assunto\s*:\s*", "", m.group(1)).strip()]
        for prox in linhas[i + 1:i + 30]:
            if not prox.strip() or prox.startswith("#") or _OUTRO_ROTULO.match(prox):
                break
            valor.append(prox.strip())
        out += [n for n in separar_partes("\n".join(v for v in valor if v)) if n not in out]
    return out


def partes_do_titulo(titulo):
    """O trecho de partes de "TIPO – PARTE – PROC. X" (sem o tipo e sem o processo)."""
    seg = [s.strip() for s in re.split(r"\s+[–—-]\s+", titulo or "")]
    out = []
    for s in seg[1:]:
        if re.match(r"(?i)(procs?\.?|pas|processos?|inqu[ée]rito|rj|sp|\d)", s):
            continue
        out += [n for n in separar_partes(s) if n not in out]
    return out


def _nup_digitos(texto):
    return re.sub(r"\D", "", texto or "")


class Pessoas:
    """Lista positiva de pessoas físicas por julgado; as fontes de dados/ carregam na 1ª consulta
    (ou vêm prontas, nos testes)."""

    def __init__(self, acusados=None, partes_tc=None, descricoes=None, acusados_csv=ACUSADOS_CSV,
                 listagens=LISTAGENS, inventario=INVENTARIO):
        self._acusados, self._partes_tc, self._desc = acusados, partes_tc, descricoes
        self._csv, self._listagens, self._inventario = acusados_csv, listagens, inventario

    @property
    def acusados(self):
        if self._acusados is None:
            self._acusados = {}
            if os.path.exists(self._csv):
                import csv
                with open(self._csv, encoding="latin-1", newline="") as f:
                    for row in csv.DictReader(f, delimiter=";"):
                        n = pessoa(row.get("Nome_Acusado", ""))
                        if n:
                            self._acusados.setdefault(_nup_digitos(row.get("NUP")), []).append(n)
        return self._acusados

    @property
    def partes_tc(self):
        if self._partes_tc is None:
            self._partes_tc = {}
            import julgados_inventario as ji
            for nome, colunas in (("tc_aceitos.html", (0, 4)), ("tc_rejeitados.html", (2,))):
                c = os.path.join(self._listagens, nome)
                if not os.path.exists(c):
                    continue
                with open(c, encoding="utf-8", errors="replace") as f:
                    html = f.read()
                for tds in ji._linhas_tabela(html):
                    proc = jc.normalizar_processo(ji._txt(tds[0]))
                    if not proc:
                        continue
                    for col in colunas:
                        if col >= len(tds):
                            continue
                        txt = ji._txt(tds[col])
                        if col == 0:  # "RJ96/4025 - PARTE"
                            txt = re.split(r"\s+[–-]\s+", txt, maxsplit=1)[1:] or [""]
                            txt = txt[0]
                        self._partes_tc.setdefault(proc, []).extend(separar_partes(txt))
        return self._partes_tc

    @property
    def descricoes(self):
        if self._desc is None:
            self._desc = {}
            if os.path.exists(self._inventario):
                with open(self._inventario, encoding="utf-8") as f:
                    for x in json.load(f).get("julgados", []):
                        if x.get("desc"):
                            self._desc[x["id"]] = (x.get("tipo", ""), x["desc"])
        return self._desc

    def do_julgado(self, valores, corpo):
        out = []

        vistos = set()

        def mais(nomes):
            for n in nomes:
                if _dobrar(n) not in vistos:
                    vistos.add(_dobrar(n))
                    out.append(n)

        mais(self.acusados.get(_nup_digitos(valores.get("nup")), []))
        for p in re.split(r"\s*;\s*", valores.get("processo", "")):
            proc = jc.normalizar_processo(p)
            if proc:
                mais(self.partes_tc.get(proc, []))
                if not valores.get("nup") and jc.nup(p):
                    mais(self.acusados.get(_nup_digitos(jc.nup(p)), []))
        tipo, desc = self.descricoes.get(valores.get("id", ""), ("", ""))
        mais(partes_da_descricao(desc, tipo or valores.get("tipo", "")))
        mais(partes_do_corpo(corpo))
        m = re.search(r"(?m)^# (.+)$", corpo)
        mais(partes_do_titulo(m.group(1) if m else ""))
        return out


def tem_nome(ementa, pessoas_):
    """A ementa traz duas palavras capitalizadas seguidas (com "da", "de"... no meio) que são,
    na mesma ordem, partes do nome de uma pessoa da lista? Pega nome completo, nome e sobrenome
    ("Eike Batista") e sobrenome composto ("Silva Vargas"). Devolve o trecho ou ""."""
    if not ementa or not pessoas_:
        return ""
    toks = [(m.group(0), _dobrar(m.group(0)).strip(".")) for m in
            re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", ementa)]
    listas = []
    for p in pessoas_:
        d = [_dobrar(t).strip(".") for t in _palavras_nome(p)]
        listas.append([x for x in d if x not in _LIGACAO and len(x) > 1])
    for i, (orig, d) in enumerate(toks):
        if not orig[0].isupper() or d in _LIGACAO:
            continue
        j = i + 1
        while j < len(toks) and toks[j][1] in _LIGACAO and not toks[j][0][0].isupper():
            j += 1
        if j >= len(toks) or not toks[j][0][0].isupper():
            continue
        a, b = d, toks[j][1]
        for nome in listas:
            if a in nome and b in nome and nome.index(a) < len(nome) - 1 - nome[::-1].index(b):
                return "%s %s" % (orig, toks[j][0])
    return ""


# ---------------------------------------------------------------- D3 na ementa oficial

PESSOA_OMITIDA = "[pessoa física]"
AVISO_EMENTA = ("nomes de pessoa física omitidos da ementa do frontmatter; ementa integral na "
                "seção Ementa")
_PESSOAS_PADRAO = None


def _trechos_de_nome(ementa, pessoas_):
    """[(ini, fim)] dos trechos da ementa com duas ou mais palavras capitalizadas seguidas que
    são, na ordem, partes do nome de uma pessoa da lista ("da", "de"... e iniciais no meio)."""
    toks = [(m.start(), m.end(), m.group(0), _dobrar(m.group(0)).strip(".")) for m in
            re.finditer(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’.\-]*", ementa or "")]
    nomes = []
    for p in pessoas_ or ():
        d = [x for x in (_dobrar(t).strip(".") for t in _palavras_nome(p))
             if x not in _LIGACAO and len(x) > 1]
        if len(d) >= 2:
            nomes.append(d)
    out, i = [], 0
    while i < len(toks):
        ini, _, orig, d = toks[i]
        melhor = None
        if orig[0].isupper() and d not in _LIGACAO:
            for nome in nomes:
                if d not in nome:
                    continue
                pos, ult, n, k = nome.index(d), i, 1, i + 1
                while k < len(toks) and not ementa[toks[k - 1][1]:toks[k][0]].strip():
                    o2, d2 = toks[k][2], toks[k][3]
                    if d2 in _LIGACAO or (len(d2) == 1 and o2[0].isupper()):
                        k += 1
                        continue
                    if not (o2[0].isupper() and d2 in nome[pos + 1:]):
                        break
                    pos, ult, n, k = nome.index(d2, pos + 1), k, n + 1, k + 1
                if n >= 2 and (melhor is None or ult > melhor):
                    melhor = ult
        if melhor is None:
            i += 1
            continue
        fim, orig_ult = toks[melhor][1], toks[melhor][2]
        if len(toks[melhor][3]) > 1:  # ponto final da frase não é do nome (o da inicial é)
            fim -= len(orig_ult) - len(orig_ult.rstrip("."))
        out.append((ini, fim))
        i = melhor + 1
    return out


def trocar_nomes(ementa, pessoas_):
    """A ementa com cada nome da lista trocado por "[pessoa física]"."""
    for ini, fim in reversed(_trechos_de_nome(ementa, pessoas_)):
        ementa = ementa[:ini] + PESSOA_OMITIDA + ementa[fim:]
    return ementa


def _nomes_em_caixa_alta(ementa):
    """Pessoas da lista de acusados em caixa alta que abre as ementas antigas ("FULANO DE TAL e
    ACME S.A. – Ementa...")."""
    e = re.sub(r"\s+", " ", ementa or "").strip()
    m = re.match(r"^(.{3,400}?)\s+[-–—]\s+(?=\S)", e)
    return separar_partes(m.group(1)) if m and jc._caixa_alta(m.group(1)) else []


def ementa_sem_pessoas(valores, corpo, pessoas_=None, publicada=""):
    """D3 na ementa de qualquer fonte: (valores, corpo, nº de trocas). Os nomes da lista positiva
    do julgado (`pessoas_`, ou a de `Pessoas().do_julgado`) e os da lista em caixa alta antes do
    travessão viram "[pessoa física]" só no frontmatter; o corpo ganha `## Ementa` logo depois do
    `# título` com a ementa como publicada (`publicada`, ou a do frontmatter), se ainda não tem."""
    global _PESSOAS_PADRAO
    ementa = valores.get("ementa") or ""
    if pessoas_ is None:
        if _PESSOAS_PADRAO is None:
            _PESSOAS_PADRAO = Pessoas()
        pessoas_ = _PESSOAS_PADRAO.do_julgado(valores, corpo)
    lista = list(pessoas_) + _nomes_em_caixa_alta(publicada) + _nomes_em_caixa_alta(ementa)
    trechos = _trechos_de_nome(ementa, lista)
    if not trechos:
        return valores, corpo, 0
    inc = [x for x in (valores.get("incerteza") or "").split("; ") if x]
    novos = dict(valores, ementa=trocar_nomes(ementa, lista),
                 incerteza="; ".join(dict.fromkeys(inc + [AVISO_EMENTA])))
    if not re.search(r"(?m)^## Ementa\s*$", corpo):
        texto = re.sub(r"\s+", " ", publicada or ementa).strip()
        m = re.search(r"(?m)^# .*\n", corpo)
        fim = m.end() if m else 0
        resto = corpo[fim:].lstrip("\n")
        corpo = corpo[:fim] + "\n## Ementa\n\n" + texto + "\n\n" + resto
    return novos, corpo, len(trechos)


# ---------------------------------------------------------------- validação


_CITA_RECORTE = re.compile(r"(?i)\brecortes?\b")  # "bloco de controle" é termo legítimo


def validar_saida(lote, saida, pessoas=None, reprovadas=None):
    """(aprovados {id: campos}, erros). Id faltando vai para `reprovadas` (retentativa) e id
    sobrando é ignorado, sem reprovar o resto do lote; campo inválido sai do item (ementa longa ou com nome de pessoa física do julgado, tema ou
    resultado fora da lista). `pessoas`: {id: [nomes]} (pessoas.json do lote); `reprovadas`, se
    dado, recebe {id: motivo} das ementas reprovadas (para a retentativa)."""
    pessoas = pessoas or {}
    reprovadas = {} if reprovadas is None else reprovadas
    erros = []
    if not isinstance(saida, list):
        return {}, ["saida.json não é uma lista"]
    por_id = {}
    for o in saida:
        if isinstance(o, dict) and o.get("id"):
            por_id[o["id"]] = o
    ids = [x["id"] for x in lote]
    faltam, sobram = set(ids) - set(por_id), set(por_id) - set(ids)
    if faltam:
        erros.append("ids faltando: %s" % ", ".join(sorted(faltam)))
    if sobram:
        erros.append("ids a mais: %s" % ", ".join(sorted(sobram)))
    for i in sorted(faltam):
        reprovadas[i] = "id ausente na saída"
    aprovados = {}
    for x in lote:
        if x["id"] in faltam:
            continue
        o, campos = por_id[x["id"]], {}
        ementa = re.sub(r"\s+", " ", str(o.get("ementa") or "")).strip()
        if ementa:
            if len(ementa.split()) > MAX_PALAVRAS_EMENTA:
                motivo = "ementa com mais de %d palavras" % MAX_PALAVRAS_EMENTA
            elif tem_nome(ementa, pessoas.get(x["id"], [])):
                motivo = "ementa com nome de pessoa"
            elif pii.limpar(ementa) != ementa:
                motivo = "ementa com dado pessoal"
            elif _CITA_RECORTE.search(ementa):
                motivo = "ementa cita o recorte"
            else:
                motivo = ""
                campos["ementa"] = ementa
            if motivo:
                erros.append("%s: %s" % (x["id"], motivo))
                reprovadas[x["id"]] = motivo
        tema = str(o.get("tema") or "").strip()
        if tema in TEMAS:
            campos["tema"] = tema
        elif tema:
            erros.append("%s: tema fora da lista (%s)" % (x["id"], tema))
        res = str(o.get("resultado") or "").strip()
        if res in jc.RESULTADOS.get(x["tipo"], ()):
            campos["resultado"] = res
        elif res:
            erros.append("%s: resultado fora da lista do tipo (%s)" % (x["id"], res))
        rel = str(o.get("relator") or "").strip()
        if rel:
            campos["relator"] = pii.limpar(rel)
        sit = str(o.get("situacao") or "").strip()
        if sit in SITUACOES:
            campos["situacao"] = sit
        elif sit:
            erros.append("%s: situação fora da lista (%s)" % (x["id"], sit))
        aprovados[x["id"]] = campos
    return aprovados, erros


# ---------------------------------------------------------------- aplicação


def quer_ementa(v):
    """A ementa extraída substitui a do título? (não na rotineira nem na decisão antiga)"""
    return (v.get("ementa_fonte") == "titulo" and v.get("classe") not in ROTINEIRAS
            and v.get("tipo") not in SEM_EMENTA_EXTRAIDA)


def aplicar(caminho, campos, refazer=False):
    """Grava no frontmatter os campos extraídos, pelas regras da Task 4; devolve os alterados.
    `refazer` (--refazer): a ementa extraída antes e o resultado também são substituídos."""
    v, corpo = ler_julgado(caminho)
    mudou = []
    if refazer and v.get("ementa_fonte") == "extracao":
        v["ementa_fonte"] = "titulo"  # volta a aceitar a ementa extraída (quer_ementa)
    if "ementa" in campos and quer_ementa(v) and campos["ementa"] != v.get("ementa"):
        v["ementa"], v["ementa_fonte"] = campos["ementa"], "extracao"
        mudou.append("ementa")
    if campos.get("tema") and not v.get("tema"):
        v["tema"], v["tema_fonte"] = campos["tema"], "extracao"
        mudou.append("tema")
    for c in ("resultado", "relator"):
        if campos.get(c) and (not v.get(c) or (refazer and c == "resultado"
                                                and campos[c] != v[c])):
            v[c] = campos[c]
            mudou.append(c)
    if refazer and "ementa" not in mudou and v.get("ementa_fonte") == "titulo":
        v["ementa_fonte"] = "extracao"  # a ementa extraída antes fica como estava
    if mudou:
        gravar(caminho, {k: v.get(k, "") for k in jc.CAMPOS}, corpo)
    return mudou


def processar_lote(pasta_lote, refazer=False):
    """Valida saida.json do lote e aplica; grava validacao.json. "retentar" traz {caminho:
    motivo} das ementas reprovadas (longa, com nome, com dado pessoal) que ainda substituiriam a
    do título."""
    with open(os.path.join(pasta_lote, "lote.json"), encoding="utf-8") as f:
        lote = json.load(f)
    with open(os.path.join(pasta_lote, "caminhos.json"), encoding="utf-8") as f:
        caminhos = dict(zip([x["id"] for x in lote], json.load(f)))
    c_pessoas = os.path.join(pasta_lote, "pessoas.json")
    if os.path.exists(c_pessoas):
        with open(c_pessoas, encoding="utf-8") as f:
            pessoas = json.load(f)
    else:
        p = Pessoas()
        pessoas = {i: p.do_julgado(*ler_julgado(c)) for i, c in caminhos.items()}
    reprovadas = {}
    try:
        with open(os.path.join(pasta_lote, "saida.json"), encoding="utf-8") as f:
            saida = json.load(f)
    except (OSError, ValueError) as e:
        saida, aprovados, erros = None, {}, ["saida.json ausente ou inválido (%s)" %
                                             type(e).__name__]
    if saida is not None:
        aprovados, erros = validar_saida(lote, saida, pessoas, reprovadas)
    aplicados = {i: aplicar(caminhos[i], c, refazer) for i, c in aprovados.items()}
    retentar = {caminhos[i]: m for i, m in reprovadas.items()
                if quer_ementa(ler_julgado(caminhos[i])[0])}
    rel = {"erros": erros, "aplicados": aplicados, "retentar": retentar}
    _gravar_json(os.path.join(pasta_lote, "validacao.json"), rel)
    return rel


# ---------------------------------------------------------------- reextração (fase 3b)
#
# A auditoria da 3b achou ementas que trazem a posição da área técnica como se fosse a decisão
# e resultados tirados do voto do relator, da proposta da área técnica ou de julgamento
# suspenso. A reextração refaz, com o recorte pela deliberação (recorte_3b) e o Sonnet:
#   - a ementa de todo julgado com ementa_fonte: extracao;
#   - o resultado de toda decisão do Colegiado e do TC sem resultado da listagem oficial.
# Roda em lotes retomáveis em dados/fase-3b/extracao/ e não toca em plugins/; a aplicação ao
# frontmatter é um passo à parte (--aplicar-reextracao).

SAIDA_3B = os.path.join(jc.RAIZ, "dados", "fase-3b", "extracao")
LISTA_3B = os.path.join(jc.RAIZ, "dados", "fase-3b", "reextracao-lista.json")
FALHAS_SEGUIDAS = 3  # lotes seguidos sem saída: para (cota, rede), para retomar depois


def tc_com_resultado_da_listagem(inventario=INVENTARIO):
    """ids de TC cujo resultado veio da listagem oficial (aceitos/rejeitados)."""
    if not os.path.exists(inventario):
        return set()
    with open(inventario, encoding="utf-8") as f:
        d = json.load(f)
    return {x["id"] for x in d.get("julgados", [])
            if x.get("tipo") == "termo-compromisso" and x.get("resultado")}


def escopo_3b(v, tc_listagem=frozenset()):
    """Campos que a reextração refaz neste julgado (lista vazia: fica fora)."""
    campos = []
    if v.get("ementa_fonte") == "extracao":
        campos.append("ementa")
    if v.get("tipo") == "decisao-colegiado" or (v.get("tipo") == "termo-compromisso"
                                                 and v.get("id") not in tc_listagem):
        campos.append("resultado")
    return campos


def montar_lista(raiz=jc.RAIZ, inventario=INVENTARIO):
    """{gerado_em, criterio, contagens, itens: {id: {tipo, classe, campos}}}."""
    tc = tc_com_resultado_da_listagem(inventario)
    itens, contagens = {}, {}
    for x in julgados(raiz):
        v, _ = ler_julgado(x["url"])
        campos = escopo_3b(v, tc)
        if not campos:
            continue
        itens[x["id"]] = {"tipo": x["tipo"], "classe": v.get("classe", ""), "campos": campos}
        c = contagens.setdefault(x["tipo"], {"itens": 0, "ementa": 0, "resultado": 0,
                                             "ementa_e_resultado": 0})
        c["itens"] += 1
        for k in campos:
            c[k] += 1
        c["ementa_e_resultado"] += len(campos) == 2
    contagens["total"] = {k: sum(c[k] for c in contagens.values())
                          for k in ("itens", "ementa", "resultado", "ementa_e_resultado")}
    return {"gerado_em": jc.hoje_sp(),
            "criterio": "ementa: ementa_fonte extracao; resultado: toda decisao-colegiado e "
                        "termo-compromisso sem resultado da listagem oficial (inventário 2d)",
            "contagens": contagens, "itens": dict(sorted(itens.items()))}


def _ler_json(caminho, padrao=None):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def processar_lote_3b(pasta_lote, escopo):
    """Valida saida.json do lote, sem aplicar; grava validacao.json {erros, aprovados,
    retentar: {id: motivo}} (ementa reprovada onde a ementa está no escopo, ou id ausente)."""
    lote = _ler_json(os.path.join(pasta_lote, "lote.json"), [])
    pessoas = _ler_json(os.path.join(pasta_lote, "pessoas.json"), {})
    saida = _ler_json(os.path.join(pasta_lote, "saida.json"))
    reprovadas = {}
    if saida is None:
        aprovados, erros = {}, ["saida.json ausente ou inválido"]
    else:
        aprovados, erros = validar_saida(lote, saida, pessoas, reprovadas)
    retentar = {i: m for i, m in reprovadas.items()
                if m == "id ausente na saída" or "ementa" in escopo.get(i, ())}
    rel = {"erros": erros, "aprovados": aprovados, "retentar": retentar}
    if "-retentativa-" in os.path.basename(pasta_lote):
        rel["ementa_do_titulo"] = sorted(i for i in retentar if "ementa" in escopo.get(i, ()))
    _gravar_json(os.path.join(pasta_lote, "validacao.json"), rel)
    return rel


def estado_reextracao(saida):
    """O que já rodou em `saida`: {resultados: {id: [campos por lote, em ordem]}, retentar:
    {id: motivo} ainda sem retentativa, ementa_do_titulo: {ids reprovados duas vezes}}."""
    resultados, retentar, retentados, do_titulo = {}, {}, set(), set()
    for val in sorted(glob.glob(os.path.join(saida, "*", "validacao.json")),
                      key=lambda c: (os.path.getmtime(c), c)):
        pasta = os.path.dirname(val)
        rel = _ler_json(val, {})
        for i, campos in rel.get("aprovados", {}).items():
            resultados.setdefault(i, []).append(campos)
        if "-retentativa-" in os.path.basename(pasta):
            retentados.update(x["id"] for x in _ler_json(os.path.join(pasta, "lote.json"), []))
            do_titulo.update(rel.get("ementa_do_titulo", []))
        else:
            retentar.update(rel.get("retentar", {}))
    return {"resultados": resultados, "ementa_do_titulo": do_titulo,
            "retentar": {i: m for i, m in retentar.items() if i not in retentados}}


def _montar_lotes_3b(ids, caminhos, escopo, saida, prefixo, motivos=None):
    cams = [caminhos[i] for i in ids]
    mot = {caminhos[i]: m for i, m in motivos.items() if i in caminhos} if motivos else None
    pastas = montar_lotes(cams, saida, prefixo, motivos=mot, novo=True)
    for p in pastas:
        lote = _ler_json(os.path.join(p, "lote.json"), [])
        _gravar_json(os.path.join(p, "escopo.json"), {x["id"]: escopo[x["id"]] for x in lote})
    return pastas


def reextrair(lista, saida, modelo, raiz=jc.RAIZ, ids=None, limite=None, simular=False,
              trabalho=None):
    """Roda os ids pendentes da lista em lotes de 25 (retomável: pula o que já tem
    validacao.json em `saida`), depois a retentativa das ementas reprovadas. Não aplica."""
    escopo = {i: x["campos"] for i, x in lista["itens"].items()}
    alvo = [i for i in (ids or sorted(escopo)) if i in escopo]
    fora = sorted(set(ids or ()) - set(escopo))
    if fora:
        print("fora da lista: %s" % ", ".join(fora), file=sys.stderr)
    os.makedirs(saida, exist_ok=True)
    estado = estado_reextracao(saida)
    pendentes = [i for i in alvo if i not in estado["resultados"]]
    if limite:
        pendentes = pendentes[:limite]
    caminhos = {x["id"]: x["url"] for x in julgados(raiz)}
    sem = [i for i in pendentes if i not in caminhos]
    if sem:
        print("sem arquivo convertido: %s" % ", ".join(sem), file=sys.stderr)
    pendentes = [i for i in pendentes if i in caminhos]
    prefixo = "%s-%s-%s-%d" % (jc.hoje_sp(), modelo, time.strftime("%H%M%S"), os.getpid())
    n = 1
    while glob.glob(os.path.join(saida, glob.escape(prefixo) + "-*")):  # mesma hora e pid
        n += 1
        prefixo = "%s-%s-%s-%d-%d" % (jc.hoje_sp(), modelo, time.strftime("%H%M%S"),
                                      os.getpid(), n)
    pastas = _montar_lotes_3b(pendentes, caminhos, escopo, saida, prefixo)
    print("%d de %d julgado(s) pendente(s) em %d lote(s) em %s" % (
        len(pendentes), len(alvo), len(pastas), saida), flush=True)
    if simular:
        return 0
    total, seguidas = 0.0, 0

    def rodar(p, reforco=""):
        nonlocal total, seguidas
        try:
            info = rodar_lote(p, modelo, trabalho, reforco=reforco)
        except subprocess.TimeoutExpired:
            info = {"modelo": modelo, "codigo": "timeout", "total_cost_usd": None,
                    "saida": False}
            _gravar_json(os.path.join(p, "execucao.json"), info)
        if not info["saida"]:
            seguidas += 1
            print("%s: sem saida.json (%s)" % (os.path.basename(p), info["codigo"]),
                  file=sys.stderr, flush=True)
            if seguidas >= FALHAS_SEGUIDAS:
                raise RuntimeError("%d lotes seguidos sem saída; retome depois" % seguidas)
            return None
        seguidas = 0
        rel = processar_lote_3b(p, _ler_json(os.path.join(p, "escopo.json"), {}))
        total += info["total_cost_usd"] or 0
        print("%s: US$ %s; %d aprovado(s); %d erro(s); acumulado US$ %.2f" % (
            os.path.basename(p), info["total_cost_usd"], len(rel["aprovados"]),
            len(rel["erros"]), total), flush=True)
        return rel

    try:
        for p in pastas:
            rodar(p)
        retentar = estado_reextracao(saida)["retentar"]
        retentar = {i: m for i, m in retentar.items() if i in caminhos}
        if retentar:  # uma vez, com a instrução reforçada; se falhar, ementa do título
            for p in _montar_lotes_3b(sorted(retentar), caminhos, escopo, saida,
                                      prefixo + "-retentativa", motivos=retentar):
                rodar(p, REFORCO)
            print("retentativa: %d item(ns)" % len(retentar), flush=True)
    except RuntimeError as e:
        print("parado: %s; custo nesta execução US$ %.4f" % (e, total), file=sys.stderr)
        return 1
    print("custo nesta execução: US$ %.4f" % total)
    return 0


def _juntar(entradas):
    """Campos de um id em vários lotes: o valor não vazio mais recente vale."""
    out = {}
    for campos in entradas:
        out.update({k: v for k, v in campos.items() if v})
    return out


def aplicar_reextracao(lista, saida, raiz=jc.RAIZ, simular=False):
    """Aplica ao frontmatter só ementa, ementa_fonte, resultado e tema (tema_fonte), nos campos
    do escopo de cada id; o resto do arquivo fica como está. Grava aplicacao-*.json em `saida`.

    - ementa: a extraída (ementa_fonte: extracao); reprovada duas vezes, a do título (titulo);
    - resultado: vazio se o modelo ou o detector (situacao_deliberacao) acham o julgamento
      suspenso, ou se o modelo não acha deliberação; senão o extraído; sem extraído, fica;
    - tema: o extraído, se o tema atual também veio da extração e mudou."""
    escopo = {i: x["campos"] for i, x in lista["itens"].items()}
    estado = estado_reextracao(saida)
    caminhos = {x["id"]: x["url"] for x in julgados(raiz)}
    rel = {"simulado": simular, "saida": saida, "contagens": {}, "alterados": {},
           "conflitos_situacao": [], "resultado_esvaziado": [], "sem_resultado_extraido": [],
           "ementa_do_titulo": [], "sem_arquivo": [],
           "sem_extracao": sorted(set(escopo) - set(estado["resultados"]))}
    cont = rel["contagens"]
    for i in sorted(estado["resultados"]):
        if i not in escopo:
            continue
        if i not in caminhos:
            rel["sem_arquivo"].append(i)
            continue
        novo, campos = _juntar(estado["resultados"][i]), escopo[i]
        v, corpo = ler_julgado(caminhos[i])
        antes = dict(v)
        if "ementa" in campos:
            if novo.get("ementa"):
                v["ementa"], v["ementa_fonte"] = novo["ementa"], "extracao"
            elif i in estado["ementa_do_titulo"]:
                m = re.search(r"(?m)^# (.+)$", corpo)
                v["ementa"] = jc.ementa_de_titulo(m.group(1) if m else "", v.get("classe"))
                v["ementa_fonte"] = "titulo"
                rel["ementa_do_titulo"].append(i)
        if "resultado" in campos:
            decisao = _secao(corpo, "Decisão")
            det = situacao_deliberacao(decisao) if decisao else ""
            sit = novo.get("situacao", "")
            if sit and (sit == "suspenso") != (det == "suspenso"):
                rel["conflitos_situacao"].append({"id": i, "modelo": sit, "detector": det,
                                                  "resultado_extraido": novo.get("resultado", "")})
            if sit in ("suspenso", "sem-deliberacao") or det == "suspenso":
                v["resultado"] = ""
                if antes.get("resultado"):
                    rel["resultado_esvaziado"].append(
                        {"id": i, "antes": antes["resultado"], "modelo": sit, "detector": det})
            elif novo.get("resultado"):
                v["resultado"] = novo["resultado"]
            else:
                rel["sem_resultado_extraido"].append(i)
        if (novo.get("tema") and v.get("tema_fonte", "") in ("extracao", "")
                and novo["tema"] != v.get("tema")):
            v["tema"], v["tema_fonte"] = novo["tema"], "extracao"
        mudou = [k for k in ("ementa", "ementa_fonte", "resultado", "tema", "tema_fonte")
                 if v.get(k, "") != antes.get(k, "")]
        for k in mudou:
            cont[k] = cont.get(k, 0) + 1
        if mudou:
            rel["alterados"][i] = {k: [antes.get(k, ""), v.get(k, "")] for k in mudou}
            if not simular:
                gravar(caminhos[i], {k: v.get(k, "") for k in jc.CAMPOS}, corpo)
    cont["arquivos"] = len(rel["alterados"])
    nome = "aplicacao-%s-%s%s.json" % (jc.hoje_sp(), time.strftime("%H%M%S"),
                                       "-simulada" if simular else "")
    os.makedirs(saida, exist_ok=True)
    _gravar_json(os.path.join(saida, nome), rel)
    rel["relatorio"] = os.path.join(saida, nome)
    return rel


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--onda", type=int, choices=sorted(jc.ONDAS))
    ap.add_argument("--tipo", choices=jc.TIPOS)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--model", default="sonnet", choices=("haiku", "sonnet"))
    ap.add_argument("--simular", action="store_true", help="só monta os lotes, sem o modelo")
    ap.add_argument("--refazer", action="store_true",
                    help="com --ids: substitui a ementa extraída antes e o resultado")
    ap.add_argument("--trabalho", help="pasta-base de trabalho fora do cofre (padrão /private/tmp)")
    ap.add_argument("--raiz", default=jc.RAIZ)
    ap.add_argument("--saida", help="pasta dos lotes (padrão %s; na 3b, %s)" % (
        os.path.relpath(SAIDA, jc.RAIZ), os.path.relpath(SAIDA_3B, jc.RAIZ)))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--montar-lista", action="store_true",
                   help="3b: grava a lista de reextração (--lista) com as contagens por tipo")
    g.add_argument("--reextrair", action="store_true",
                   help="3b: roda a reextração dos itens da lista, retomável, sem aplicar")
    g.add_argument("--aplicar-reextracao", action="store_true",
                   help="3b: aplica ementa, resultado e tema extraídos em --saida")
    ap.add_argument("--lista", default=LISTA_3B)
    a = ap.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    if a.montar_lista:
        lista = montar_lista(a.raiz)
        os.makedirs(os.path.dirname(a.lista), exist_ok=True)
        _gravar_json(a.lista, lista)
        print(json.dumps(lista["contagens"], ensure_ascii=False))
        return 0
    if a.reextrair or a.aplicar_reextracao:
        lista = _ler_json(a.lista)
        if not lista:
            ap.error("lista ausente: rode --montar-lista antes (%s)" % a.lista)
        saida = a.saida or SAIDA_3B
        if a.reextrair:
            return reextrair(lista, saida, a.model, a.raiz, ids, a.limite, a.simular, a.trabalho)
        rel = aplicar_reextracao(lista, saida, a.raiz, a.simular)
        print(json.dumps(rel["contagens"], ensure_ascii=False))
        print("relatório: %s" % rel["relatorio"])
        return 0
    a.saida = a.saida or SAIDA
    if a.refazer and not a.ids:
        ap.error("--refazer só com --ids")
    itens = jc.selecionar(julgados(a.raiz), ids=ids, tipo=a.tipo, onda=a.onda, limite=a.limite)
    if ids:
        faltam = set(ids) - {x["id"] for x in itens}
        if faltam:
            print("sem arquivo convertido: %s" % ", ".join(sorted(faltam)), file=sys.stderr)
    else:  # retomável: sem --ids, fica de fora o que já tem tema e não quer mais ementa
        itens = [x for x in itens if x["pendente"]]
    # hora e pid no prefixo: filas paralelas que começam juntas não dividem pastas de lote
    prefixo = "%s-%s-%s-%d" % (jc.hoje_sp(), a.model, time.strftime("%H%M%S"), os.getpid())
    pastas = montar_lotes([x["url"] for x in itens], a.saida, prefixo)
    print("%d julgado(s) em %d lote(s) em %s" % (len(itens), len(pastas), a.saida))
    if a.simular:
        return 0
    total, falhas, retentar = 0.0, 0, {}

    def rodar(p, reforco=""):
        nonlocal total, falhas
        info = rodar_lote(p, a.model, a.trabalho, reforco=reforco)
        rel = processar_lote(p, a.refazer)
        total += info["total_cost_usd"] or 0
        falhas += info["codigo"] != 0 or any(e.split(":")[0] not in rel["aplicados"]
                                             for e in rel["erros"])  # erro de lote
        print("%s: US$ %s; %d aplicado(s); %d erro(s)" % (
            os.path.basename(p), info["total_cost_usd"],
            sum(1 for v in rel["aplicados"].values() if v), len(rel["erros"])))
        return rel

    for p in pastas:
        retentar.update(rodar(p)["retentar"])
    if retentar:  # uma vez, com a instrução reforçada; se falhar, fica a ementa do título
        ficaram = {}
        for p in montar_lotes(sorted(retentar), a.saida, os.path.basename(pastas[0])[:-4]
                              + "-retentativa", motivos=retentar):
            rel = rodar(p, REFORCO)
            ficaram.update({c: m for c, m in rel["retentar"].items()})
            rel["ementa_do_titulo"] = sorted(rel["retentar"])
            _gravar_json(os.path.join(p, "validacao.json"), rel)
        print("retentativa: %d item(ns); %d ficaram com a ementa do título" % (
            len(retentar), len(ficaram)))
        for c, m in sorted(ficaram.items()):
            print("  ementa do título: %s (%s)" % (os.path.basename(c), m), file=sys.stderr)
    print("custo total: US$ %.4f" % total)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
