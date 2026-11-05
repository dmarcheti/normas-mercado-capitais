#!/usr/bin/env python3
"""Índice por decisão das decisões antigas do Colegiado (1978 a 2001).

Cada ano é um arquivo só (`cvm/decisoes-antigas/AAAA.md`, até 1,7 MB): "ATA DA REUNIÃO DO
COLEGIADO Nº N DE dd.mm.aaaa" (`## `) e, dentro dela, uma decisão por título em caixa alta
(`### `). Este módulo lê esses arquivos e devolve, por decisão, a data e o número da ata, o
processo (se houver), o título e `arquivo:linha`. Quem monta as tabelas e grava é `indice.py`.

O título vem do próprio arquivo e passa por duas limpezas:
- ruído: o conversor abriu decisão em toda linha em caixa alta, então listas de participantes,
  cabeçalhos de voto ("DO RECURSO"), assinaturas e quadros viram "decisão". Esses títulos saem
  (contados em `Contagem.ruido`);
- pessoa física: nome de investidor, reclamante ou recorrente sai do título e entra
  "[pessoa física]" (`julgados_extracao.PESSOA_OMITIDA`). A lista de nomes vem só do conteúdo
  dos próprios arquivos (rótulos "Interessado:", "Reclamante:"...) e da posição do nome no título
  ("RECURSO DE <NOME> CONTRA", "<TIPO> – <NOME>"), sem `dados/`: o índice tem de sair igual em
  qualquer máquina.

Só biblioteca padrão.
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import julgados_comum as jc  # noqa: E402
import julgados_converter as conv  # noqa: E402
import julgados_extracao as je  # noqa: E402

TITULO_MAX = 100
ANO_MIN, ANO_MAX = 1976, 2001
SEM_TITULO = "(sem título identificado)"

# Ata fora do padrão de `conv._ATA`: "1°.07.1986", "ATA DE REUNIÃO DO COLEGIADO DE 17.06.1986".
_ATA_ABRE = re.compile(r"^#{2,3}\s+(ATA\s+D[AE]\s+REUNI[ÃA]O\b.*)$")
_DATA_TOLERANTE = re.compile(r"(\d{1,2})\s*[°º]?\s*\.\s*(\d{1,2})\s*\.\s*(\d{2,4})")
_NUMERO_ATA = re.compile(r"\bN[º°o]\.?\s*(\d+\s*[A-Z]?)\b")

_CAUDA = re.compile(r"(?i)\s*[-–—(]?\s*PROC(?:ESSOS?)?\.?\s*(?:CVM\s*)?(?:N[º°o]\.?\s*)?"
                    r"(?:(?:RJ|SP)\s*[-/]?\s*\d{2,4}\s*/\s*\d+|[\d./\-]+)?\s*\)?\s*$")
_RELATOR_COLADO = re.compile(r"^.{0,90}?DIRETOR(?:A)?[- ]RELATOR(?:A)?[\"”]?\s*(.*)$")
_CONECTIVO_FINAL = re.compile(r"(?i)(?:\b(?:DE|DA|DO|DAS|DOS|E|EM|PARA|COM|POR|A|AO|AOS|AS|NO|NA|SOBRE)|[-–—,])$")
_REG = re.compile(r"(?im)^\s*Reg(?:istro)?\.?\s*(?:Col\.?\s*)?(?:n[º°o]\.?\s*)?(\d{1,5}\s*/\s*\d{2,4})")
_ASSUNTO = re.compile(r"(?im)^\W*ASSUNTO\s*:\s*(.+)$")

_RUIDO_INICIO = re.compile(
    r"^\W*(?:PARTICIPANTES|PRESENTES|COMUNICADOS?\b|ASSUNTOS?\s+GERAIS|PROCESSO\b[\s:]*(?:CVM|N|RJ|SP|RC)|"
    r"PROC\b|REGISTRO\b|DO\s|DA\s|DOS\s|DAS\s|DE\s|[IVX]{1,4}\s*[-–.)]|\d+\s*[-–.)]|ANEXO\b|"
    r"ATA\s+D[AE]\b|AUSENTES?\b|RELAT[ÓO]RIO\s*$|VOTO\s*$|CONCLUS[ÃA]O\s*$|SENHORES\b|"
    r"(?:DIRETOR|DIRETORA|PRESIDENTE|SUPERINTENDENTE)\b|NOTA\s*:|OBS\b|"
    r"(?:INTERESSAD[OA]S?|RECORRENTES?|RECLAMANTES?|PROPONENTES?|ASSUNTO|RELATORA?|EMENTA|OBJETO|"
    r"REFER[ÊE]NCIA|DATA|PROCESSO|DECIS[ÃA]O|VOTO)\s*:|"
    r"DISPOSI[ÇC][ÕO]ES?\s+(?:FINAIS?|TRANSIT[ÓO]RIAS?|GERAIS|PRELIMINARES)|CAP[ÍI]TULO\b|"
    r"SE[ÇC][ÃA]O\b|T[ÍI]TULO\s+[IVX]|ART(?:IGO)?\.?\s*\d|JUSTIFICATIVA\b|CONSIDERANDO\b|"
    r"DESCRI[ÇC][ÃA]O\b|TOTAL\b)", re.I)
_CARGO = re.compile(r"[-–—]\s*(?:Presidente|Diretora?|Superintendente|Procurador|Substitut|PTE\b|DES\b|DIRETOR)",
                    re.I)
_SIGLA_PARTICIPANTE = re.compile(r"\s[-–—]\s*[A-Z]{2,5}\b")
_PARTICIPANTE = re.compile(r"^\W*([A-ZÀ-Ý][A-ZÀ-Ý .'\-]{5,60}?)\s+[–—-]\s*(?:Presidente|Diretora?|Superintendente|"
                           r"Procurador|PTE|DES|DAM|DGH)", re.I)

# Palavras que, mesmo parecendo nome, não são de pessoa nos títulos.
_NAO_PESSOA = frozenset("""
pessoa pessoas fisica fisicas juridica juridicas aberta abertas fechada fechadas geral gerais
estadual federal municipal bolsa bolsas fundo fundos clube clubes carteira carteiras mercado
mercados titulos valores mobiliarios acoes debentures cotas quotas opcao opcoes futuro futuros
termo operacao operacoes instrucao instrucoes deliberacao deliberacoes parecer pareceres
auditor auditores independente independentes contratacao nomeacao exclusao inclusao
autorizacao autonomo autonomos escritural escriturais custodia banco bancos financeira
financeiras sociedade sociedades administrador administradores cancelamento suspensao
alteracao reforma estatuto estatutos controle transferencia aquisicao alienacao fusao cisao
incorporacao liquidacao intervencao inquerito processo processos sancionador administrativo
publica publico oferta ofertas distribuicao registro credenciamento credenciada habilitacao
""".split())


class Contagem:
    """Números da leitura de um conjunto de arquivos anuais."""

    def __init__(self):
        self.decisoes = 0
        self.ruido = 0           # títulos descartados como ruído
        self.vazios = 0          # decisões mantidas sem título aproveitável
        self.nomes_trocados = 0  # títulos em que entrou "[pessoa física]"
        self.por_ano = collections.defaultdict(lambda: collections.Counter())
        self.duplicadas = 0

    def somar(self, ano, chave, n=1):
        self.por_ano[ano][chave] += n


def _dobrar(txt):
    return je._dobrar(txt or "")


def _tokens(txt):
    return [t for t in (_dobrar(x).strip(".") for x in je._palavras_nome(txt or "")) if t]


def _letras(txt):
    return re.sub(r"[^A-Za-zÀ-ÿ]", "", txt or "")


def _data_da_ata(cabecalho):
    m = conv._ATA.search(cabecalho)
    if m:
        d, mes, a = m.group(1), m.group(2), m.group(3)
    else:
        m = _DATA_TOLERANTE.search(cabecalho)
        if not m:
            return ""
        d, mes, a = m.groups()
    try:
        ano, mes, dia = conv._ano4(a), int(mes), int(d)
    except ValueError:
        return ""
    if not (ANO_MIN <= ano <= ANO_MAX and 1 <= mes <= 12 and 1 <= dia <= 31):
        return ""
    return "%04d-%02d-%02d" % (ano, mes, dia)


def _numero_da_ata(cabecalho):
    m = _NUMERO_ATA.search(cabecalho)
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def _janela(linhas, i, max_nao_vazias=12):
    """Linhas não vazias depois do título `i`, até o próximo `#`."""
    out, j = [], i + 1
    while j < len(linhas) and not linhas[j].startswith("#") and len(out) < max_nao_vazias:
        if linhas[j].strip():
            out.append(linhas[j].strip())
        j += 1
    return out


def _processo(texto):
    """Processo da decisão: NUP ou RJ/SP normalizado (a numeração curta "NN/AAAA" fica de fora:
    "Reg. 25/1999" não é PAS); sem ele, o registro do Colegiado ("Reg. 3045/00")."""
    nums = [n for n in jc.processos(texto) if not re.fullmatch(r"\d{2,3}-\d{4}", n)]
    if nums:
        return "; ".join(nums[:2])
    m = _REG.search(texto)
    return "Reg. %s" % re.sub(r"\s+", "", m.group(1)) if m else ""


def _nomes_dos_participantes(linhas):
    """Nomes em caixa alta das listas de participantes ("NOME – Diretor"): título que é só um
    deles é assinatura, não decisão."""
    nomes = set()
    for ln in linhas:
        m = _PARTICIPANTE.match(ln)
        if m:
            nomes.add(" ".join(_tokens(m.group(1))))
    return nomes


def _e_ruido(titulo, participantes):
    if not titulo:
        return True
    letras = _letras(titulo)
    if len(letras) < 8 or len(titulo.split()) < 2:
        return True
    if titulo[:1] == '"' or _RUIDO_INICIO.match(titulo):
        return True
    if _CARGO.search(titulo) or len(_SIGLA_PARTICIPANTE.findall(titulo)) >= 2:
        return True
    if len(re.findall(r"\d+,\d+", titulo)) >= 2 or (len(re.findall(r"\d[\d.,]*", titulo)) >= 3
                                                   and len(letras) < 40):
        return True
    toks = " ".join(_tokens(titulo))
    return any(n and (toks == n or toks.startswith(n + " ") or toks.endswith(" " + n))
               for n in participantes)


def _limpar_titulo(bruto, janela):
    """(título, processo) de um `### ` do arquivo. Título vazio: sem aproveitamento."""
    t = re.sub(r"\s+", " ", bruto).strip(' "“”')
    m = _RELATOR_COLADO.match(t)
    if m:  # assinatura do voto anterior colada no título seguinte
        t = m.group(1).strip(' "“”')
    t = re.sub(r"(?i)^ASSUNTO\s*:\s*", "", t)
    if t and _CONECTIVO_FINAL.search(t) and janela:
        prox = janela[0]
        if (len(prox) <= 60 and _letras(prox).upper() == _letras(prox) and len(_letras(prox)) >= 3
                and not _REG.match(prox) and not re.match(r"(?i)relator", prox)):
            t = t + " " + prox
    proc = _processo(t + "\n" + "\n".join(janela[:8]))
    t = _CAUDA.sub("", t).strip(' "“”-–—,;:')
    if not t:
        m = next((a for a in (_ASSUNTO.search(x) for x in janela[:8]) if a), None)
        t = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    return t, proc


def vocabulario(textos, minimo=5):
    """Palavras que aparecem em minúsculas ao menos `minimo` vezes no texto: vocabulário comum,
    não nome próprio (nome de gente vem sempre capitalizado)."""
    cont = collections.Counter()
    rx = re.compile(r"(?<![A-Za-zÀ-ÿ])[a-zà-ÿ]{3,}(?![A-Za-zÀ-ÿ])")
    for t in textos:
        cont.update(_dobrar(w) for w in rx.findall(t))
    return {p for p, n in cont.items() if n >= minimo}


_PALAVRA = re.compile(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'’]*(?:-[A-Za-zÀ-ÿ]+)*\.?")
# Marca de empresa: o trecho que a contém, ou que vem logo antes dela, não é nome de pessoa.
_MARCA_ENTIDADE = frozenset((
    "s.a.", "s.a", "sa", "ltda", "ltd", "cia", "me", "epp", "eireli", "and", "inc", "trust", "corp",
    "limited", "partners", "bank", "fund", "funds", "company", "co", "asset", "management", "investment",
    "investments", "group", "associates", "holding", "holdings", "securities", "capital", "brasil",
    "participacoes", "participações", "banco", "companhia", "estado", "estadual", "federal", "nacional"))
# Palavra que, logo depois do trecho, mostra que ele é razão social ("X HOTEL", "X CORRETORA").
_SEGUE_EMPRESA = frozenset((
    "hotel", "hoteis", "mecanica", "industria", "industrias", "industrial", "comercio", "engenharia", "leasing",
    "arrendamento", "distribuidora", "corretora", "corretoras", "investimentos", "seguros", "seguradora",
    "financeira", "mineracao", "siderurgica", "metalurgica", "petroquimica", "construtora", "empreendimentos",
    "imoveis", "agricola", "textil", "alimentos", "energia", "eletrica", "telecomunicacoes", "bolsa",
    "ccvm", "ctvm", "dtvm", "cvmc", "cctvm", "tcvm", "cvm", "sccvm", "sctvm", "auditores", "auditoria",
    "consultoria", "servicos", "transportes", "participacoes", "empreendimento", "fundo", "clube", "banco",
    "bancos", "bank", "cooperativa", "associacao", "sociedade", "grupo", "holding", "motors"))
# O que pode vir antes do nome de pessoa: início, travessão, dois-pontos, aspas, ou um desses rótulos.
_ANTES_PESSOA = re.compile(
    r"(?:^|[–—:-]|\b(?:INVESTIDORA?|SRS?\.?|SRAS?\.?|A[ÇC][ÃA]O(?:\s+ORDIN[ÁA]RIA)?(?:\s+(?:QUE|MOVIDA\s+POR))?|RECLAMA[ÇC][ÃA]O|RECLAMA[ÇC][ÕO]ES|RECURSOS?|PEDIDO|"
    r"SOLICITA[ÇC][ÃA]O|CREDENCIAMENTO|INTERMEDIA[ÇC][ÃA]O|CANCELAMENTO|REGISTRO|PLEITO|CONSULTA|"
    r"INDICA[ÇC][ÃA]O|ENTRE)(?:\s+(?:D[AEO]S?))?)\s*$", re.I)


def trechos_de_nome(titulo, vocab):
    """[(ini, fim)] dos trechos do título que são nome de pessoa física: duas ou mais palavras
    pronunciáveis (vogal, 3 letras ou mais) que não são vocabulário comum, sigla, lugar nem marca
    de entidade, seguidas, com "de/da/do/e" e iniciais no meio; o trecho não pode ser seguido de
    "S.A.", "Ltda." etc. (nome de empresa)."""
    toks = [(m.start(), m.end(), m.group(0), _dobrar(m.group(0)).strip(".")) for m in _PALAVRA.finditer(titulo)]

    def pleno(k):
        orig, d = toks[k][2], toks[k][3]
        return (len(d) >= 3 and re.search(r"[aeiouy]", d) is not None and d not in vocab
                and d not in _NAO_PESSOA and d not in je._ENTIDADE and d not in je._NAO_NOME
                and d not in je._LIGACAO)

    def inicial(k):
        return len(toks[k][3]) == 1 and toks[k][2].endswith(".")

    out, i = [], 0
    while i < len(toks):
        if inicial(i) and i + 1 < len(toks) and pleno(i + 1):
            pass  # o nome começa por inicial ("M. MARCELLO LEITE BARBOSA")
        elif not pleno(i):
            i += 1
            continue
        ini_k, fim_k, k, plenos = i, i, i, 0
        traco = bool(re.search(r"[–-]\s*$", titulo[:toks[i][0]]))
        while k < len(toks):
            if k > ini_k and titulo[toks[k - 1][1]:toks[k][0]].strip():
                break
            if pleno(k):
                plenos += 1
                fim_k = k
                k += 1
            elif inicial(k):
                k += 1
            elif (traco and plenos == 1 and k + 1 < len(toks) and pleno(k + 1) and len(toks[k][3]) <= 5
                  and toks[k][2].isupper() and toks[k][3] not in je._LIGACAO
                  and toks[k][3] not in _NAO_PESSOA and toks[k][3] not in je._ENTIDADE
                  and toks[k][3] not in je._NAO_NOME and not titulo[toks[k][1]:toks[k + 1][0]].strip()):
                k += 1  # sobrenome que também é palavra comum ("DIAS") entre dois nomes, depois de travessão
            elif toks[k][3] in je._LIGACAO and k + 1 < len(toks) and (pleno(k + 1) or inicial(k + 1)) \
                    and not titulo[toks[k][1]:toks[k + 1][0]].strip():
                k += 1
            else:
                break
        seguinte = toks[fim_k + 1][3] if fim_k + 1 < len(toks) else ""
        resto = titulo[toks[fim_k][1]:toks[fim_k][1] + 2]
        entidade = (seguinte in _MARCA_ENTIDADE or seguinte in _SEGUE_EMPRESA
                    or re.match(r"\s*(?:S\s*[./]\s*[AC]\b|&)", titulo[toks[fim_k][1]:], re.I)
                    or any(t[3] in _MARCA_ENTIDADE for t in toks[ini_k:fim_k + 1]))
        ante = titulo[:toks[ini_k][0]].rstrip()
        contexto = bool(_ANTES_PESSOA.search(ante)) and (
            ante != "" or re.match(r"\s*(?:[–—:-]|$)", titulo[toks[fim_k][1]:]) is not None)
        if plenos >= 2 and not entidade and contexto and not resto.startswith("/"):
            out.append((toks[ini_k][0], toks[fim_k][1]))
        i = max(k, i + 1)
    return out


_CONTRA = re.compile(r"[–-]\s+([A-ZÀ-Ý][A-ZÀ-Ý.'’ ]+?)\s+X\s+[A-ZÀ-Ý]")


def sem_pessoas(titulo, vocab):
    """(título com "[pessoa física]" no lugar de cada nome, houve troca)."""
    original = novo = titulo
    # "– FULANO DE TAL X EMPRESA S/A": o lado esquerdo do "X" (contra) é parte, sem vocabulário a conferir
    m = _CONTRA.search(novo)
    if m and not re.search(r"\d|S\s*/\s*[AC]|LTDA|BANCO|CIA|COMPANHIA|FUNDO|CCVM|CTVM|DTVM|CVMC",
                           m.group(1), re.I) and len(m.group(1).split()) >= 2:
        novo = novo[:m.start(1)] + je.PESSOA_OMITIDA + novo[m.end(1):]
    titulo = novo
    for ini, fim in reversed(trechos_de_nome(titulo, vocab)):
        novo = novo[:ini] + je.PESSOA_OMITIDA + novo[fim:]
    return novo, novo != original


def nomes_dos_rotulos(linhas):
    """Nomes das linhas "Interessado:", "Reclamante:", "Recorrente:"... do arquivo."""
    return je.partes_do_corpo("\n".join(linhas))


class ListaDeNomes:
    """Lista positiva com índice por palavra: `trocar` só olha os nomes que dividem alguma
    palavra com o título (a lista passa de mil nomes e os títulos de sete mil)."""

    def __init__(self):
        self.nomes = {}
        self.por_palavra = collections.defaultdict(set)

    def adicionar(self, nome):
        chave = " ".join(_tokens(nome))
        if not chave or chave in self.nomes:
            return
        self.nomes[chave] = nome
        for t in set(_tokens(nome)):
            if t not in je._LIGACAO and len(t) > 1:
                self.por_palavra[t].add(chave)

    def trocar(self, titulo):
        """(título com "[pessoa física]", houve troca)."""
        cand = set()
        for t in set(_tokens(titulo)):
            cand |= self.por_palavra.get(t, set())
        if not cand:
            return titulo, False
        novo = je.trocar_nomes(titulo, [self.nomes[c] for c in sorted(cand)])
        return novo, novo != titulo


def _curto(titulo, n=TITULO_MAX):
    if len(titulo) <= n:
        return titulo
    corte = titulo[:n].rsplit(" ", 1)[0].rstrip(" ,;:-–—")
    return corte + "…"


def _ler_linhas(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read().split("\n")


def _decisoes_do_arquivo(linhas, participantes):
    """[{ata, data, titulo_bruto, janela, linha}] do arquivo anual (todas as `### `, atas
    incluídas as que o conversor deixou como `### ATA...`)."""
    ata, data, out = "", "", []
    for i, ln in enumerate(linhas):
        m = _ATA_ABRE.match(ln)
        if m:
            ata, data = _numero_da_ata(m.group(1)), _data_da_ata(m.group(1))
            if not data:  # o conversor quebrou o cabeçalho: a data está na linha seguinte
                seguinte = next((x for x in linhas[i + 1:i + 4] if x.strip()), "")
                data = _data_da_ata(m.group(1) + " " + seguinte) if not seguinte.startswith("#") else ""
            continue
        if ln.startswith("### "):
            out.append({"ata": ata, "data": data, "bruto": ln[4:], "janela": _janela(linhas, i),
                        "linha": i + 1})
    return out


def ler_decisoes(arquivos):
    """([decisão], Contagem) dos arquivos anuais `{ano: caminho}`. Cada decisão: dict com data
    (da ata), ata, processo, titulo (já sem nome de pessoa), ano (do arquivo), linha, arquivo
    (`cvm/decisoes-antigas/AAAA.md`)."""
    cont = Contagem()
    lidos, rotulos = {}, []
    todos_participantes = set()
    for ano, caminho in sorted(arquivos.items()):
        linhas = _ler_linhas(caminho)
        lidos[ano] = linhas
        todos_participantes |= _nomes_dos_participantes(linhas)
        rotulos += nomes_dos_rotulos(linhas)
    brutas = {ano: _decisoes_do_arquivo(linhas, todos_participantes) for ano, linhas in lidos.items()}
    vocab = vocabulario("\n".join(linhas) for linhas in lidos.values())
    lista = ListaDeNomes()
    for n in rotulos:
        lista.adicionar(n)
    limpas = []
    for ano, ds in sorted(brutas.items()):
        anterior = None
        for d in ds:
            bruto = re.sub(r"\s+", " ", d["bruto"]).strip(' "“”')
            if _e_ruido(bruto, todos_participantes) and not _RELATOR_COLADO.match(bruto):
                cont.ruido += 1
                cont.somar(ano, "ruido")
                continue
            titulo, proc = _limpar_titulo(d["bruto"], d["janela"])
            if re.match(r"(?i)^ASSUNTO\b", d["bruto"].strip(' "“”')) and anterior == d["data"] + d["ata"]:
                cont.ruido += 1  # "ASSUNTO:" do voto da decisão que acabou de abrir
                cont.somar(ano, "ruido")
                continue
            if not titulo or _e_ruido(titulo, todos_participantes):
                if not (proc and not titulo):
                    cont.ruido += 1
                    cont.somar(ano, "ruido")
                    continue
                titulo = ""
            anterior = d["data"] + d["ata"]
            limpas.append((ano, d, titulo, proc))
    # 2ª passada: o nome visto em contexto de pessoa num título vale para os demais títulos
    for _ano, _d, titulo, _proc in limpas:
        for ini, fim in trechos_de_nome(titulo, vocab):
            lista.adicionar(titulo[ini:fim])
    out = []
    for ano, d, titulo, proc in limpas:
        titulo, trocou = lista.trocar(titulo)
        titulo, trocou2 = sem_pessoas(titulo, vocab)
        if trocou or trocou2:
            cont.nomes_trocados += 1
            cont.somar(ano, "nomes")
        if not titulo:
            cont.vazios += 1
            cont.somar(ano, "vazios")
            titulo = SEM_TITULO
        out.append({"data": d["data"], "ata": d["ata"], "processo": proc, "titulo": _curto(titulo),
                    "ano": ano, "linha": d["linha"],
                    "arquivo": "cvm/decisoes-antigas/%s.md" % ano})
    # a mesma decisão em dois arquivos anuais (ata de dezembro repetida no ano seguinte): fica a
    # do arquivo cujo ano é o da ata
    vistos, finais = {}, []
    for d in out:
        chave = (d["data"], d["ata"], d["titulo"], d["processo"])
        if d["data"] and chave in vistos and vistos[chave]["ano"] != d["ano"]:
            anterior = vistos[chave]
            if str(d["ano"]) == d["data"][:4] and str(anterior["ano"]) != d["data"][:4]:
                finais[finais.index(anterior)] = d
                vistos[chave] = d
            cont.duplicadas += 1
            continue
        vistos[chave] = d
        finais.append(d)
    cont.decisoes = len(finais)
    return finais, cont
