#!/usr/bin/env python3
"""Conversão de normas para Markdown, só com a biblioteca padrão.

- docx_para_md(path): consolidado da CVM (DOCX) -> Markdown, um parágrafo por
  linha. Texto tachado (redação antiga mantida no consolidado) sai entre `~~`.
  Tabelas viram tabelas Markdown simples. Listas automáticas do Word ganham o
  número do item ("I –", "a)", "1.") lido de word/numbering.xml.
- dou_html_para_md(html): página do DOU (in.gov.br) -> Markdown. Lê o bloco
  `texto-dou`; descarta assinatura e cargo (não são texto normativo).
- planalto_html_para_md(html): lei compilada (planalto.gov.br) -> Markdown.
  Aceita bytes (lê o charset do `<meta>`, em geral windows-1252) ou texto.
  Texto tachado (`<strike>`, `<s>`, `<del>`) sai; as notas "(Redação dada
  pela ...)" e "(Incluído pela ...)" ficam, porque não há histórico que as
  substitua. Ordinal em `<sup>o</sup>` vira `º`.
- normalizar_artigos(md): todo início de artigo vira `## Art. Nº` em linha
  própria; parágrafos, incisos e alíneas ficam como texto.

Limitações conhecidas: numeração de lista só por w:numPr no parágrafo ou no
estilo direto (sem herança entre estilos); imagens, caixas de texto e notas de
rodapé são ignoradas; células de tabela com mais de um parágrafo são unidas
por espaço; no Planalto, tachado por CSS (`line-through`) não é reconhecido.

Uso: python3 scripts/converter.py <arquivo.docx|arquivo.html> [--artigos] [--planalto]
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _espaco(txt):
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip()


# ---------------------------------------------------------------- DOCX

def _tachado(run):
    for nome in ("strike", "dstrike"):
        el = run.find("%srPr/%s%s" % (W, W, nome))
        if el is not None and el.get(W + "val", "true").lower() not in ("0", "false", "off"):
            return True
    return False


def _texto_run(run):
    partes = []
    for el in run:
        if el.tag == W + "t":
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


def _paragrafo(p, numeracao=None):
    """Texto do parágrafo; trechos tachados contíguos viram um `~~...~~`.

    Com `numeracao`, o item de lista automática leva o número na frente. Se o
    parágrafo inteiro é tachado, o número entra dentro da marca (senão a
    normalização deixaria uma linha só com "I –").
    """
    rotulo = numeracao.rotulo(p) if numeracao else None
    saida = []
    tachado = []
    for r in _runs(p):
        t = _texto_run(r)
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


def _tabela(tbl, numeracao=None):
    """Tabela em Markdown. Tabela aninhada numa célula vira tabela própria, depois da
    externa (separada por linha em branco), para a contagem de tabelas bater com a do Word."""
    linhas, aninhadas = [], []
    for tr in tbl.findall(W + "tr"):
        celulas = []
        for tc in tr.findall(W + "tc"):
            ps = []
            for f in _filhos_da_celula(tc):
                if f.tag == W + "p":
                    ps.append(_paragrafo(f, numeracao))
                else:
                    aninhadas.append(_tabela(f, numeracao))
            celulas.append(_espaco(" ".join(x for x in ps if x)).replace("|", "\\|"))
        linhas.append(celulas)
    if not linhas:
        return "\n\n".join(a for a in aninhadas if a)
    larg = max(len(l) for l in linhas)
    linhas = [l + [""] * (larg - len(l)) for l in linhas]
    md = ["| " + " | ".join(linhas[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
    md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n\n".join(["\n".join(md)] + [a for a in aninhadas if a])


def _blocos(el, numeracao=None):
    for filho in el:
        if filho.tag == W + "p":
            yield _paragrafo(filho, numeracao)
        elif filho.tag == W + "tbl":
            yield _tabela(filho, numeracao)
        elif filho.tag in (W + "sdt", W + "sdtContent"):
            yield from _blocos(filho, numeracao)


def docx_para_md(path):
    with zipfile.ZipFile(path) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
        nomes = z.namelist()
        numeracao = _Numeracao(
            z.read("word/numbering.xml") if "word/numbering.xml" in nomes else None,
            z.read("word/styles.xml") if "word/styles.xml" in nomes else None)
    corpo = raiz.find(W + "body")
    blocos = [b for b in _blocos(corpo, numeracao) if b]
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


class _Planalto(HTMLParser):
    BLOCOS = ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "center")
    FORA = ("script", "style", "head", "title")
    TACHADO = ("strike", "s", "del")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocos = []
        self._p = []
        self._fora = 0
        self._tachado = 0
        self._sup = 0
        self._tabela = None
        self._linha = None
        self._celula = None

    def _alvo(self):
        return self._celula if self._celula is not None else self._p

    def _fecha_paragrafo(self):
        txt = _espaco("".join(self._p))
        if txt:
            self.blocos.append(txt)
        self._p = []

    def handle_starttag(self, tag, attrs):
        if tag in self.FORA:
            self._fora += 1
        elif tag in self.TACHADO:
            self._tachado += 1
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
        if self._fora or self._tachado:
            return
        if self._sup and data.strip() in ("o", "O", "º", "°"):
            data = "º"
        elif self._sup and data.strip() in ("a", "ª"):
            data = "ª"
        self._alvo().append(data)

    def fim(self):
        self._fecha_paragrafo()


def planalto_html_para_md(html):
    p = _Planalto()
    p.feed(decodificar_html(html))
    p.close()
    p.fim()
    return "\n\n".join(b for b in p.blocos if b) + "\n"


# ---------------------------------------------------------------- artigos

# Início de artigo: "Art. 1º", "Art. 10.", "Art. 12-A", "Art. 5º-A", "Art. 1.001".
ARTIGO = re.compile(
    r"^Art\.?\s*(?P<num>\d+(?:\.\d{3})*[º°]?(?:-[A-Z]{1,2})?)\s*\.?(?:\s+|$)(?P<resto>.*)$"
)


# Nota de alteração do consolidado que começa com o artigo ("Art. 73-A incluído
# pela Resolução ...", "Art. 9º revogado pela ..."): não é início de artigo.
NOTA_DE_ARTIGO = re.compile(
    r"^(?:com\s+(?:a\s+)?redação\s+dada|incluíd[oa]|revogad[oa]\s+pel[ao]s?|acrescentad[oa]|renumerad[oa])\b"
)


def normalizar_artigos(md):
    saida = []
    for linha in md.split("\n"):
        m = ARTIGO.match(linha)
        if m and not NOTA_DE_ARTIGO.match(m.group("resto")):
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
