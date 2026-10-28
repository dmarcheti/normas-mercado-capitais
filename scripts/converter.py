#!/usr/bin/env python3
"""Conversão de normas para Markdown, só com a biblioteca padrão.

- docx_para_md(path): consolidado da CVM (DOCX) -> Markdown, um parágrafo por
  linha. Texto tachado (redação antiga mantida no consolidado) sai entre `~~`.
  Tabelas viram tabelas Markdown simples.
- dou_html_para_md(html): página do DOU (in.gov.br) -> Markdown. Lê o bloco
  `texto-dou`; descarta assinatura e cargo (não são texto normativo).
- normalizar_artigos(md): todo início de artigo vira `## Art. Nº` em linha
  própria; parágrafos, incisos e alíneas ficam como texto.

Limitações conhecidas: listas numeradas automáticas do Word (w:numPr) não têm
o número no XML e saem sem ele; imagens, caixas de texto e notas de rodapé são
ignoradas; células de tabela com mais de um parágrafo são unidas por espaço.

Uso: python3 scripts/converter.py <arquivo.docx|arquivo.html> [--artigos]
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


def _paragrafo(p):
    """Texto do parágrafo; trechos tachados contíguos viram um `~~...~~`."""
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
    return "" if txt.replace("~", "").strip() == "" else txt


def _tabela(tbl):
    linhas = []
    for tr in tbl.findall(W + "tr"):
        celulas = []
        for tc in tr.findall(W + "tc"):
            ps = [_paragrafo(p) for p in tc.iter(W + "p")]
            celulas.append(_espaco(" ".join(x for x in ps if x)).replace("|", "\\|"))
        linhas.append(celulas)
    if not linhas:
        return ""
    larg = max(len(l) for l in linhas)
    linhas = [l + [""] * (larg - len(l)) for l in linhas]
    md = ["| " + " | ".join(linhas[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
    md += ["| " + " | ".join(l) + " |" for l in linhas[1:]]
    return "\n".join(md)


def _blocos(el):
    for filho in el:
        if filho.tag == W + "p":
            yield _paragrafo(filho)
        elif filho.tag == W + "tbl":
            yield _tabela(filho)
        elif filho.tag in (W + "sdt", W + "sdtContent"):
            yield from _blocos(filho)


def docx_para_md(path):
    with zipfile.ZipFile(path) as z:
        raiz = ET.fromstring(z.read("word/document.xml"))
    corpo = raiz.find(W + "body")
    blocos = [b for b in _blocos(corpo) if b]
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
    else:
        with open(caminho, encoding="utf-8") as f:
            md = dou_html_para_md(f.read())
    if "--artigos" in argv:
        md = normalizar_artigos(md)
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
