#!/usr/bin/env python3
"""Conversão de normas para Markdown, só com a biblioteca padrão.

- docx_para_md(path, caixas=False, notas=False): consolidado da CVM (DOCX) ->
  Markdown, um parágrafo por linha. Texto tachado (redação antiga mantida no
  consolidado) sai entre `~~`. Tabelas viram tabelas Markdown simples. Listas
  automáticas do Word ganham o número do item ("I –", "a)", "1.") lido de
  word/numbering.xml. `caixas=True`: cada caixa de texto (diagrama) vira, depois
  do parágrafo onde está ancorada, um bloco de linhas `> [Diagrama] ...` (um
  parágrafo da caixa por linha; de mc:AlternateContent lê um ramo só).
  `notas=True`: cada referência de nota de rodapé vira ` [k]`, com k na ordem de
  exibição (ordem_das_notas). Os dois ficam desligados no padrão, que é o que o
  teste final do núcleo usa.
- dou_html_para_md(html): página do DOU (in.gov.br) -> Markdown. Lê o bloco
  `texto-dou`; descarta assinatura e cargo (não são texto normativo).
- planalto_html_para_md(html): lei compilada (planalto.gov.br) -> Markdown.
  Aceita bytes (lê o charset do `<meta>`, em geral windows-1252) ou texto.
  Texto tachado (`<strike>`, `<s>`, `<del>`) sai; as notas "(Redação dada
  pela ...)" e "(Incluído pela ...)" ficam, porque não há histórico que as
  substitua. Ordinal em `<sup>o</sup>` vira `º`. Rótulos de margem de vigência
  (links "(Vigência)", "Produção de efeito") saem.
- normalizar_artigos(md): todo início de artigo vira `## Art. Nº` em linha
  própria; parágrafos, incisos e alíneas ficam como texto.

Limitações conhecidas: numeração de lista só por w:numPr no parágrafo ou no
estilo direto (sem herança entre estilos); imagens são ignoradas, e caixas de
texto e notas de rodapé também, salvo `caixas=True` e `notas=True` (da caixa
fica só o texto: setas e posição se perdem); células de tabela com mais de um parágrafo são unidas
por espaço; no Planalto, tachado por CSS (`line-through`) não é reconhecido.

Uso: python3 scripts/converter.py <arquivo.docx|arquivo.html> [--artigos] [--planalto]
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
DIAGRAMA = "> [Diagrama] "


def _espaco(txt):
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip()


# ---------------------------------------------------------------- DOCX

def _tachado(run):
    for nome in ("strike", "dstrike"):
        el = run.find("%srPr/%s%s" % (W, W, nome))
        if el is not None and el.get(W + "val", "true").lower() not in ("0", "false", "off"):
            return True
    return False


def _marca_propria(el):
    return el.get(W + "customMarkFollows", "0").lower() in ("1", "true", "on")


def _texto_run(run, notas=None):
    """Texto do run. Com `notas` ({id: k}), a referência de nota de rodapé vira " [k]"; a
    marca própria do autor (customMarkFollows, o w:t seguinte do run) sai, porque a âncora
    [k] a substitui e casa com a seção final de notas."""
    partes = []
    pular_marca = False
    for el in run:
        if el.tag == W + "footnoteReference" and notas is not None:
            k = notas.get(el.get(W + "id"))
            if k:
                partes.append(" [%d]" % k)
                pular_marca = _marca_propria(el)
            continue
        if el.tag == W + "t":
            if pular_marca:
                pular_marca = False
                continue
            partes.append(el.text or "")
        elif el.tag in (W + "tab", W + "br", W + "cr"):
            partes.append(" ")
        elif el.tag == W + "noBreakHyphen":
            partes.append("-")
    return "".join(partes)


def _runs(el):
    """Runs do elemento em ordem, sem os de texto excluído (w:del)."""
    for filho in el:
        if filho.tag == W + "r":
            yield filho
        elif filho.tag != W + "del":
            yield from _runs(filho)


class _Opcoes:
    """O que docx_para_md lê além do padrão: caixas de texto e âncoras de notas."""

    def __init__(self, caixas=False, notas=None):
        self.caixas, self.notas = caixas, notas


def _ramo(alternativa):
    """De um mc:AlternateContent, o ramo a ler (o Word grava a mesma caixa em mc:Choice,
    DrawingML, e em mc:Fallback, VML): o primeiro com caixa de texto, senão o primeiro."""
    ramos = [r for r in alternativa if r.tag in (MC + "Choice", MC + "Fallback")]
    for r in ramos:
        if r.find(".//" + W + "txbxContent") is not None:
            return r
    return ramos[0] if ramos else None


def _percorrer(el):
    """Descendentes de `el` em ordem de documento, sem w:del e com um ramo só de cada
    mc:AlternateContent."""
    for filho in el:
        if filho.tag == W + "del":
            continue
        yield filho
        if filho.tag == MC + "AlternateContent":
            ramo = _ramo(filho)
            if ramo is not None:
                yield from _percorrer(ramo)
        else:
            yield from _percorrer(filho)


def _caixas_do(el):
    """w:txbxContent dentro de `el` (sem descer em caixa dentro de caixa), em ordem."""
    for filho in el:
        if filho.tag == W + "txbxContent":
            yield filho
        elif filho.tag == MC + "AlternateContent":
            ramo = _ramo(filho)
            if ramo is not None:
                yield from _caixas_do(ramo)
        elif filho.tag != W + "del":
            yield from _caixas_do(filho)


def _raiz(xml):
    return xml if isinstance(xml, ET.Element) else ET.fromstring(xml)


def textos_das_caixas(document_xml):
    """Texto de cada caixa de texto do documento (uma entrada por caixa), lida uma vez só."""
    corpo = _raiz(document_xml).find(W + "body")
    if corpo is None:
        return []
    return [" ".join(t.text or "" for t in _percorrer(tx) if t.tag == W + "t")
            for tx in _caixas_do(corpo)]


def ordem_das_notas(document_xml):
    """ids das notas de rodapé na ordem em que a primeira referência aparece no documento:
    a posição (1, 2, 3...) é o número de exibição, o mesmo de docx_para_md(notas=True)."""
    ids = []
    for el in _percorrer(_raiz(document_xml)):
        if el.tag == W + "footnoteReference":
            k = el.get(W + "id")
            if k not in ids:
                ids.append(k)
    return ids


def _caixa_md(tx, opc):
    """Caixa de texto -> linhas `> [Diagrama] ...`, um parágrafo por linha (sem numeração
    de lista, para não mexer na contagem do corpo)."""
    linhas = []
    for bloco in _blocos(tx, None, opc):
        for linha in (bloco or "").split("\n"):
            if linha.strip():
                linhas.append(linha if linha.startswith(DIAGRAMA) else DIAGRAMA + linha)
    return "\n".join(linhas)


class _Numeracao:
    """Numeração automática do Word (word/numbering.xml e numPr dos estilos).

    rotulo(p) -> "I –", "a)", "1." ou None (sem lista, marcador ou sem número).
    Os contadores são por lista (abstractNum): dois w:num sobre a mesma lista
    continuam a contagem, salvo `startOverride`. Chamar na ordem do documento.
    """

    def __init__(self, numbering_xml=None, styles_xml=None):
        self.niveis = {}   # abstractNumId -> {ilvl: (numFmt, lvlText, start)}
        self.nums = {}     # numId -> (abstractNumId, {ilvl: startOverride})
        self.estilos = {}  # styleId -> (numId, ilvl)
        self.cont = {}     # abstractNumId -> {ilvl: valor atual}
        self.vistos = set()
        if numbering_xml:
            self._ler_numbering(ET.fromstring(numbering_xml))
        if styles_xml:
            self._ler_estilos(ET.fromstring(styles_xml))

    def _ler_numbering(self, raiz):
        for a in raiz.findall(W + "abstractNum"):
            niveis = {}
            for lvl in a.findall(W + "lvl"):
                def val(nome, padrao):
                    el = lvl.find(W + nome)
                    return el.get(W + "val", padrao) if el is not None else padrao
                niveis[int(lvl.get(W + "ilvl", "0"))] = (
                    val("numFmt", "decimal"), val("lvlText", ""), int(val("start", "1")))
            self.niveis[a.get(W + "abstractNumId")] = niveis
        for n in raiz.findall(W + "num"):
            ref = n.find(W + "abstractNumId")
            if ref is None:
                continue
            ajustes = {}
            for o in n.findall(W + "lvlOverride"):
                inicio = o.find(W + "startOverride")
                if inicio is not None:
                    ajustes[int(o.get(W + "ilvl", "0"))] = int(inicio.get(W + "val", "1"))
            self.nums[n.get(W + "numId")] = (ref.get(W + "val"), ajustes)

    def _ler_estilos(self, raiz):
        for st in raiz.findall(W + "style"):
            ref = self._numpr(st.find(W + "pPr"))
            if ref:
                self.estilos[st.get(W + "styleId")] = ref

    @staticmethod
    def _numpr(ppr):
        if ppr is None:
            return None
        num = ppr.find(W + "numPr")
        if num is None or num.find(W + "numId") is None:
            return None
        ilvl = num.find(W + "ilvl")
        return (num.find(W + "numId").get(W + "val"),
                int(ilvl.get(W + "val", "0")) if ilvl is not None else 0)

    def rotulo(self, p):
        ppr = p.find(W + "pPr")
        ref = self._numpr(ppr)
        if ref is None and ppr is not None and ppr.find(W + "pStyle") is not None:
            ref = self.estilos.get(ppr.find(W + "pStyle").get(W + "val"))
        if ref is None or ref[0] not in self.nums:
            return None
        num_id, ilvl = ref
        abstrato, ajustes = self.nums[num_id]
        niveis = self.niveis.get(abstrato, {})
        if ilvl not in niveis:
            return None
        cont = self.cont.setdefault(abstrato, {})
        if num_id not in self.vistos:
            self.vistos.add(num_id)
            for nivel, inicio in ajustes.items():
                cont[nivel] = inicio - 1
        cont[ilvl] = cont[ilvl] + 1 if ilvl in cont else niveis[ilvl][2]
        for fundo in [n for n in cont if n > ilvl]:
            del cont[fundo]
        fmt, texto, _inicio = niveis[ilvl]
        if fmt in ("bullet", "none") or not texto:
            return None

        def nivel_n(m):
            n = int(m.group(1)) - 1
            valor = cont.get(n, niveis.get(n, ("", "", 1))[2])
            return _formatar_numero(valor, niveis.get(n, ("decimal",))[0])
        return re.sub(r"%(\d)", nivel_n, texto).strip() or None


def _romano(n):
    saida = ""
    for valor, letras in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                          (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= valor:
            saida += letras
            n -= valor
    return saida


def _formatar_numero(n, fmt):
    if fmt == "upperRoman":
        return _romano(n)
    if fmt == "lowerRoman":
        return _romano(n).lower()
    if fmt in ("upperLetter", "lowerLetter"):
        letra = chr(ord("a") + (n - 1) % 26) * ((n - 1) // 26 + 1)  # a..z, aa..zz (como o Word)
        return letra.upper() if fmt == "upperLetter" else letra
    if fmt == "decimalZero":
        return "%02d" % n
    if fmt == "ordinal":
        return "%dº" % n
    return str(n)


def _paragrafo(p, numeracao=None, opc=None):
    """Texto do parágrafo; trechos tachados contíguos viram um `~~...~~`.

    Com `numeracao`, o item de lista automática leva o número na frente. Se o
    parágrafo inteiro é tachado, o número entra dentro da marca (senão a
    normalização deixaria uma linha só com "I –").
    """
    rotulo = numeracao.rotulo(p) if numeracao else None
    saida = []
    tachado = []
    notas = opc.notas if opc else None
    for r in _runs(p):
        t = _texto_run(r, notas)
        if _tachado(r):
            tachado.append(t)
        else:
            if tachado:
                saida.append("~~%s~~" % "".join(tachado))
                tachado = []
            saida.append(t)
    if tachado:
        saida.append("~~%s~~" % "".join(tachado))
    txt = "".join(saida)
    # espaço colado à marca: `~~ x ~~` -> ` ~~x~~ `
    txt = re.sub(r"~~(\s+)", r"\1~~", txt)
    txt = re.sub(r"(\s+)~~", r"~~\1", txt)
    txt = _espaco(txt)
    if txt.replace("~", "").strip() == "":
        return ""
    if rotulo:
        if re.fullmatch(r"~~[^~]*~~", txt):
            return "~~%s %s~~" % (rotulo, txt[2:-2])
        return "%s %s" % (rotulo, txt)
    return txt


def _filhos_da_celula(el):
    """Parágrafos e tabelas aninhadas de uma célula, na ordem (entra em sdt)."""
    for filho in el:
        if filho.tag in (W + "p", W + "tbl"):
            yield filho
        elif filho.tag in (W + "sdt", W + "sdtContent"):
            yield from _filhos_da_celula(filho)


def _tabela(tbl, numeracao=None, opc=None):
    """Tabela em Markdown. Tabela aninhada numa célula vira tabela própria, depois da
    externa (separada por linha em branco), para a contagem de tabelas bater com a do Word.
    Caixa de texto numa célula (com `opc.caixas`) também vai depois da tabela."""
    linhas, aninhadas = [], []
    for tr in tbl.findall(W + "tr"):
        celulas = []
        for tc in tr.findall(W + "tc"):
            ps = []
            for f in _filhos_da_celula(tc):
                if f.tag == W + "p":
                    ps.append(_paragrafo(f, numeracao, opc))
                    if opc and opc.caixas:
                        aninhadas += [_caixa_md(tx, opc) for tx in _caixas_do(f)]
                else:
                    aninhadas.append(_tabela(f, numeracao, opc))
            celulas.append(_espaco(" ".join(x for x in ps if x)).replace("|", "\\|"))
        linhas.append(celulas)
    if not linhas:
        return "\n\n".join(a for a in aninhadas if a)
    larg = max(len(l) for l in linhas)
    linhas = [l + [""] * (larg - len(l)) for l in linhas]
    md = ["| " + " | ".join(linhas[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
    md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n\n".join(["\n".join(md)] + [a for a in aninhadas if a])


def _blocos(el, numeracao=None, opc=None):
    for filho in el:
        if filho.tag == W + "p":
            yield _paragrafo(filho, numeracao, opc)
            if opc and opc.caixas:
                for tx in _caixas_do(filho):
                    yield _caixa_md(tx, opc)
        elif filho.tag == W + "tbl":
            yield _tabela(filho, numeracao, opc)
        elif filho.tag in (W + "sdt", W + "sdtContent"):
            yield from _blocos(filho, numeracao, opc)


def docx_para_md(path, caixas=False, notas=False):
    with zipfile.ZipFile(path) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
        nomes = z.namelist()
        numeracao = _Numeracao(
            z.read("word/numbering.xml") if "word/numbering.xml" in nomes else None,
            z.read("word/styles.xml") if "word/styles.xml" in nomes else None)
    opc = None
    if caixas or notas:
        mapa = {k: i for i, k in enumerate(ordem_das_notas(raiz), 1)} if notas else None
        opc = _Opcoes(caixas, mapa)
    corpo = raiz.find(W + "body")
    blocos = [b for b in _blocos(corpo, numeracao, opc) if b]
    return "\n\n".join(blocos) + "\n"


# ---------------------------------------------------------------- DOU

class _Dou(HTMLParser):
    IGNORAR = ("assina", "cargo")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.achou = False
        self._prof_div = 0
        self.blocos = []
        self._p = None
        self._ignora = False
        self._tabela = None  # lista de linhas
        self._linha = None
        self._celula = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "div":
            if self.achou and self._prof_div:
                self._prof_div += 1
            elif "texto-dou" in (a.get("class") or "").split():
                self.achou = True
                self._prof_div = 1
            return
        if not self._prof_div:
            return
        if tag == "table":
            self._tabela = []
        elif tag == "tr" and self._tabela is not None:
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._celula = []
        elif tag == "p" and self._celula is None:
            self._p = []
            classes = (a.get("class") or "").split()
            self._ignora = any(c in self.IGNORAR for c in classes)
        elif tag == "br":
            self._escreve(" ")

    def handle_endtag(self, tag):
        if tag == "div" and self._prof_div:
            self._prof_div -= 1
            return
        if not self._prof_div:
            return
        if tag in ("td", "th") and self._celula is not None:
            self._linha.append(_espaco("".join(self._celula)).replace("|", "\\|"))
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            self._tabela.append(self._linha)
            self._linha = None
        elif tag == "table" and self._tabela is not None:
            self.blocos.append(self._md_tabela(self._tabela))
            self._tabela = None
        elif tag == "p" and self._p is not None:
            txt = _espaco("".join(self._p))
            if txt and not self._ignora:
                self.blocos.append(txt)
            self._p = None
            self._ignora = False

    def handle_data(self, data):
        self._escreve(data)

    def _escreve(self, txt):
        if self._celula is not None:
            self._celula.append(txt)
        elif self._p is not None:
            self._p.append(txt)

    @staticmethod
    def _md_tabela(linhas):
        linhas = [l for l in linhas if l]
        if not linhas:
            return ""
        larg = max(len(l) for l in linhas)
        linhas = [l + [""] * (larg - len(l)) for l in linhas]
        md = ["| " + " | ".join(linhas[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
        md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
        return "\n".join(md)


def dou_html_para_md(html):
    p = _Dou()
    p.feed(html)
    if not p.achou:
        raise ValueError('bloco "texto-dou" não encontrado no HTML')
    return "\n\n".join(b for b in p.blocos if b) + "\n"


# ---------------------------------------------------------------- Planalto

def decodificar_html(dados):
    """bytes -> str pelo charset do `<meta>` (windows-1252 nas páginas do Planalto);
    sem `<meta>`, UTF-8 e, se não decodificar, windows-1252. `str` passa direto."""
    if isinstance(dados, str):
        return dados
    m = re.search(rb"charset\s*=\s*[\"']?\s*([A-Za-z0-9_-]+)", dados[:4096])
    if m:
        try:
            return dados.decode(m.group(1).decode("ascii"), errors="replace")
        except LookupError:
            pass
    try:
        return dados.decode("utf-8")
    except UnicodeDecodeError:
        return dados.decode("cp1252", errors="replace")


# Rótulo de dispositivo que o Planalto risca junto com o texto revogado: "Art. 32.", "§ 2º",
# "Parágrafo único", "I -", "a)". Se o resto do parágrafo é só "(Revogado pela ...)", o
# rótulo volta ao texto, para a marca de revogação não ficar solta no dispositivo anterior.
_ROTULO_RISCADO = re.compile(
    r"^(?:Art\s*\.?\s*\d[\d.]*\s*[º°o]?(?:\s*-\s*[A-Z]{1,2})?\s*\.?"
    r"|§\s*\d+\s*[º°o]?(?:\s*-\s*[A-Z]{1,2})?\s*[-–.]?"
    r"|Parágrafo único\.?"
    r"|[IVXLCDM]+\s*[-–—]"
    r"|[a-z]{1,2}\)|\d+\)|\d+\s*[-–])"
)


def com_rotulo_riscado(visivel, riscado):
    """`visivel`: texto não tachado do parágrafo, sem nada visível antes do tachado;
    `riscado`: o texto tachado que veio antes. Devolve o parágrafo com o rótulo riscado
    na frente quando `visivel` é só a marca "(Revogado ...)"; senão, `visivel`."""
    visivel = " ".join(visivel.split())
    # sobra de pontuação do trecho tachado ("." antes do "(Revogado ...)") não conta
    visivel = re.sub(r"^[.;:,\s]+(?=\(revogad)", "", visivel, flags=re.IGNORECASE)
    if visivel.lower().startswith("(revogad"):
        m = _ROTULO_RISCADO.match(" ".join(riscado.split()))
        if m:
            return m.group(0).strip() + " " + visivel
    return visivel


class _Planalto(HTMLParser):
    BLOCOS = ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "center")
    FORA = ("script", "style", "head", "title")
    TACHADO = ("strike", "s", "del")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocos = []
        self._p = []
        self._riscado = []  # texto tachado do parágrafo antes de qualquer texto visível
        self._fora = 0
        self._tachado = 0
        self._sup = 0
        self._spans = []  # um item por <span> aberto: True se tem text-decoration:line-through
        self._tabela = None
        self._linha = None
        self._celula = None

    def _alvo(self):
        return self._celula if self._celula is not None else self._p

    def _fecha_paragrafo(self):
        txt = _espaco("".join(self._p))
        if txt:
            txt = _espaco(com_rotulo_riscado(txt, "".join(self._riscado)))
            self.blocos.append(txt)
        self._p, self._riscado = [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.FORA:
            self._fora += 1
        elif tag in self.TACHADO:
            self._tachado += 1
        elif tag == "span":
            riscado = "line-through" in (dict(attrs).get("style") or "").lower()
            self._spans.append(riscado)
            self._tachado += riscado
        elif tag == "sup":
            self._sup += 1
        elif tag == "table":
            self._fecha_paragrafo()
            self._tabela = []
        elif tag == "tr" and self._tabela is not None:
            self._linha = []
        elif tag in ("td", "th") and self._linha is not None:
            self._celula = []
        elif tag in self.BLOCOS and self._celula is None:
            self._fecha_paragrafo()
        elif tag == "br":
            self._alvo().append(" ")

    def handle_endtag(self, tag):
        if tag in self.FORA:
            self._fora = max(0, self._fora - 1)
        elif tag in self.TACHADO:
            self._tachado = max(0, self._tachado - 1)
        elif tag == "span":
            if self._spans and self._spans.pop():
                self._tachado = max(0, self._tachado - 1)
        elif tag == "sup":
            self._sup = max(0, self._sup - 1)
        elif tag in ("td", "th") and self._celula is not None:
            self._linha.append(_espaco("".join(self._celula)).replace("|", "\\|"))
            self._celula = None
        elif tag == "tr" and self._linha is not None:
            self._tabela.append(self._linha)
            self._linha = None
        elif tag == "table" and self._tabela is not None:
            self.blocos.append(_Dou._md_tabela(self._tabela))
            self._tabela = None
        elif tag in self.BLOCOS and self._celula is None:
            self._fecha_paragrafo()

    def handle_data(self, data):
        if self._fora:
            return
        if self._sup and data.strip() in ("o", "O", "º", "°"):
            data = "º"
        elif self._sup and data.strip() in ("a", "ª"):
            data = "ª"
        if self._tachado:
            if self._celula is None and not "".join(self._p).strip():
                self._riscado.append(data)
            return
        self._alvo().append(data)

    def fim(self):
        self._fecha_paragrafo()


# Rótulo de margem do Planalto: link cujo texto é só "Vigência", "(Vigência)", "Vigência
# encerrada" ou "Produção de efeito(s)". Remete à data de vigência de uma redação; não é texto
# normativo e, no meio do dispositivo, faz o caput parecer sem efeito. O texto pode vir dentro
# de marcas de formatação (`<a ...><font size="2">(Vigência)</font></a>`, Lei 6.404, art. 136-A)
# e com `&nbsp;` em volta.
_FORMATO = r"(?:<(?:font|span|b|i|u|small|strong|em)\b[^>]*>|</(?:font|span|b|i|u|small|strong|em)\s*>|\s|&nbsp;|&#160;)*"
_ROTULO_VIGENCIA = re.compile(
    r"(?is)<a\b[^>]*>" + _FORMATO + r"\(?" + _FORMATO
    + r"(?:vig[êe]ncia(?:\s+encerrada)?|produ[çc][ãa]o\s+de\s+efeitos?)"
    + _FORMATO + r"\)?" + _FORMATO + r"</a>")


def sem_rotulos_de_vigencia(html):
    """Tira do HTML (já decodificado) os rótulos de margem de vigência do Planalto."""
    return _ROTULO_VIGENCIA.sub("", html)


def planalto_html_para_md(html):
    p = _Planalto()
    p.feed(sem_rotulos_de_vigencia(decodificar_html(html)))
    p.close()
    p.fim()
    return "\n\n".join(b for b in p.blocos if b) + "\n"


# ---------------------------------------------------------------- artigos

# Início de artigo: "Art. 1º", "Art. 10.", "Art. 12-A", "Art. 5º-A", "Art. 1.001".
# Tolera "Art . 3º" (espaço antes do ponto, comum no Planalto) e "Art. 104.A" (sem espaço).
ARTIGO = re.compile(
    r"^Art\s*\.?\s*(?P<num>\d+(?:\.\d{3})*[º°]?(?:-[A-Z]{1,2})?)"
    r"(?:\s*\.?(?:\s+|$)|\.(?=\S))(?P<resto>.*)$"
)


# Nota de alteração do consolidado que começa com o artigo ("Art. 73-A incluído
# pela Resolução ...", "Art. 9º revogado pela ..."): não é início de artigo.
NOTA_DE_ARTIGO = re.compile(
    r"^(?:com\s+(?:a\s+)?redação\s+dada|incluíd[oa]|revogad[oa]\s+pel[ao]s?|acrescentad[oa]|renumerad[oa])\b"
)


_NUMERO_ARTIGO = re.compile(r"^(\d+(?:\.\d{3})*)[º°]?(?:-([A-Z]{1,2}))?$")


def _sucede(anterior, atual):
    """True se o artigo `atual` é o sucessor imediato de `anterior` (9º -> 9º-A -> 9º-B -> 10)."""
    a, b = _NUMERO_ARTIGO.match(anterior), _NUMERO_ARTIGO.match(atual)
    if not a or not b:
        return False
    n1, l1 = int(a.group(1).replace(".", "")), a.group(2) or ""
    n2, l2 = int(b.group(1).replace(".", "")), b.group(2) or ""
    if n2 == n1 + 1 and not l2:
        return True
    if n2 != n1 or not l2:
        return False
    if not l1:
        return l2 == "A"
    return l2 == l1[:-1] + chr(ord(l1[-1]) + 1) if l1[-1] != "Z" else False


def normalizar_artigos(md, ignorar_citacoes=False):
    """Linha que abre artigo vira `## Art. N` + linha em branco + resto.

    `ignorar_citacoes=True` (leis): artigo dentro de citação (texto entre “ e ”, como
    o artigo de uma lei alterada pelo artigo em curso) fica como texto, não vira cabeçalho.
    Aspas retas ("): número ímpar de aspas abre a citação se a linha começa por aspa e a fecha
    se não começa; número par não muda nada. Citação que o Planalto deixou sem fecho não
    engole o resto da lei: o artigo que é o sucessor imediato do último artigo da lei
    (Art. 6º, depois Art. 7º) fecha a citação."""
    saida, aberto, reto, ultimo = [], 0, False, None
    for linha in md.split("\n"):
        m = ARTIGO.match(linha)
        valido = bool(m) and not NOTA_DE_ARTIGO.match(m.group("resto"))
        citado = ignorar_citacoes and (aberto > 0 or reto)
        if citado and valido and ultimo is not None and _sucede(ultimo, m.group("num")):
            citado, aberto, reto = False, 0, False
        if ignorar_citacoes:
            aberto = max(0, aberto + linha.count("“") - linha.count("”"))
            if linha.count('"') % 2:
                if linha.lstrip().startswith('"'):
                    reto = True  # abre (ou reabre) a citação
                elif reto:
                    reto = False  # aspa ímpar no meio ou no fim da linha fecha
        if valido and not citado:
            ultimo = m.group("num")
            saida.append("## Art. " + m.group("num").replace("°", "º"))
            resto = m.group("resto").strip()
            if resto:
                saida.append("")
                saida.append(resto)
        else:
            saida.append(linha)
    return "\n".join(saida)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    caminho = argv[1]
    if caminho.lower().endswith(".docx"):
        md = docx_para_md(caminho)
    elif "--planalto" in argv:
        with open(caminho, "rb") as f:
            md = planalto_html_para_md(f.read())
    else:
        with open(caminho, encoding="utf-8") as f:
            md = dou_html_para_md(f.read())
    if "--artigos" in argv:
        md = normalizar_artigos(md)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
