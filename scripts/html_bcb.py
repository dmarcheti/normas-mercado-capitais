#!/usr/bin/env python3
"""HTML do texto compilado do BCB (campo Texto da API da busca de normas) para Markdown, só com a
biblioteca padrão (html.parser).

- Parágrafos (p, div, h1-h6, blockquote, li) separados por linha em branco; <br> quebra a linha.
- <strong>/<b> -> **; <em>/<i> -> *; style font-weight/font-style também contam (o BCB marca
  `font-weight:normal` dentro de <strong> nas notas em vermelho).
- Tachado (<s>, <strike>, <del> ou text-decoration line-through) -> ~~...~~, fechado e reaberto
  a cada linha (o texto_vigente tira o tachado do consolidado linha a linha); dentro do tachado não
  há ** nem *, para a retirada não deixar marcadores soltos.
- <table> com mais de uma célula em alguma linha -> tabela Markdown em pipe (primeira linha como
  cabeçalho, | escapado, colspan expandido em células vazias, linhas vazias fora); tabela de
  diagramação (todas as linhas com uma célula só) -> o conteúdo como blocos, com as tabelas de
  dentro convertidas normalmente; tabela aninhada numa célula de tabela de dados -> texto achatado
  na célula.
- Links ficam só com o texto; listas viram "- "; imagens, <style>, <script> e <title> saem.
- <pre> (normas antigas em texto de largura fixa): parágrafos separados por linha em branco, com
  as linhas unidas; parágrafo de 3 linhas ou mais com régua (linha só de -, = ou _) fica em bloco
  de código, para não desmontar a tabela desenhada em texto; em parágrafo menor (título
  sublinhado), a régua sai.
- U+200B e U+FEFF saem, &nbsp; vira espaço e os espaços são colapsados.

Uso: python3 scripts/html_bcb.py <arquivo.html | dados/fase-2c/bcb/<tipo>-NNNNN.json>
"""
import json
import re
import sys
from html.parser import HTMLParser

VAZIOS = {"br", "img", "hr", "meta", "link", "input", "col", "wbr", "area", "base", "param", "source"}
PULAR = {"style", "script", "title", "head", "noscript", "template"}
BLOCOS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "ul", "ol", "dl", "dt", "dd",
          "center", "section", "article", "header", "footer", "address", "figure", "figcaption",
          "form", "fieldset", "body", "html", "main", "nav", "aside", "caption"}
TABELA = {"table", "tbody", "thead", "tfoot", "tr", "td", "th"}
NEGRITO, ITALICO, TACHADO = {"b", "strong"}, {"i", "em"}, {"s", "strike", "del"}
INVISIVEIS = re.compile("[​﻿]")
REGUA = re.compile(r"^\s*[-=_]{10,}\s*$")


class No:
    __slots__ = ("tag", "attrs", "filhos")

    def __init__(self, tag, attrs=None):
        self.tag, self.attrs, self.filhos = tag, dict(attrs or {}), []


class _Arvore(HTMLParser):
    """Árvore tolerante: fecha <p> aberto quando começa um bloco, <td>/<tr>/<li> implícitos, e
    ignora tag de fechamento sem par (sem atravessar célula ou tabela)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.raiz = No("#raiz")
        self.pilha = [self.raiz]

    def _abrir(self, tag, attrs):
        no = No(tag, attrs)
        self.pilha[-1].filhos.append(no)
        if tag not in VAZIOS:
            self.pilha.append(no)

    def _fechar_ate(self, tag, limites):
        for k in range(len(self.pilha) - 1, 0, -1):
            t = self.pilha[k].tag
            if t == tag:
                del self.pilha[k:]
                return True
            if t in limites:
                return False
        return False

    def handle_starttag(self, tag, attrs):
        if tag in BLOCOS or tag in TABELA or tag in ("li", "pre"):
            # <p> aberto (só com inline por cima) fecha antes de um bloco
            for k in range(len(self.pilha) - 1, 0, -1):
                t = self.pilha[k].tag
                if t == "p":
                    del self.pilha[k:]
                    break
                if t in BLOCOS or t in TABELA or t in ("li", "pre"):
                    break
        if tag in ("td", "th"):
            self._fechar_ate("td", {"tr", "table"}) or self._fechar_ate("th", {"tr", "table"})
        elif tag == "tr":
            self._fechar_ate("tr", {"table"})
        elif tag == "li":
            self._fechar_ate("li", {"ul", "ol", "table", "td", "th"})
        self._abrir(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self.pilha[-1].filhos.append(No(tag, attrs))

    def handle_endtag(self, tag):
        if tag in VAZIOS:
            if tag == "br":  # </br> solto vale como <br>
                self.pilha[-1].filhos.append(No("br"))
            return
        if tag == "table":
            limites = set()
        elif tag in TABELA:
            limites = {"table"}
        else:
            limites = {"td", "th", "table"}
        self._fechar_ate(tag, limites)

    def handle_data(self, data):
        self.pilha[-1].filhos.append(data)


def arvore(html):
    p = _Arvore()
    p.feed(html or "")
    p.close()
    return p.raiz


# ---------------------------------------------------------------- formatação

def _estilo(attrs):
    out = {}
    for parte in (attrs.get("style") or "").split(";"):
        if ":" in parte:
            k, v = parte.split(":", 1)
            out[k.strip().lower()] = v.strip().lower()
    return out


def _fmt(no, fmt):
    """fmt = (tachado, negrito, itálico) depois de entrar em `no`."""
    s, b, i = fmt
    if no.tag in TACHADO:
        s = True
    if no.tag in NEGRITO:
        b = True
    if no.tag in ITALICO:
        i = True
    st = _estilo(no.attrs)
    if "line-through" in st.get("text-decoration", "") + st.get("text-decoration-line", ""):
        s = True
    peso = st.get("font-weight")
    if peso:
        if peso in ("bold", "bolder") or re.fullmatch(r"[6-9]00", peso):
            b = True
        elif peso in ("normal", "lighter") or re.fullmatch(r"[1-5]00", peso):
            b = False
    estilo = st.get("font-style")
    if estilo:
        i = estilo in ("italic", "oblique")
    return s, b, i


_MARCA = ("~~", "**", "*")


def _linha(grupos):
    """[(texto, fmt)] de uma linha -> Markdown, com os marcadores colados no texto."""
    buf, atual = "", (False, False, False)

    def efetivo(f):
        return (True, False, False) if f[0] else f

    def transitar(novo):
        nonlocal buf, atual
        k = next((j for j in range(3) if atual[j] != novo[j]), None)
        if k is None:
            return
        fecha = "".join(_MARCA[j] for j in range(2, k - 1, -1) if atual[j])
        if fecha:
            corpo = buf.rstrip()
            buf = corpo + fecha + buf[len(corpo):]
        buf += "".join(_MARCA[j] for j in range(k, 3) if novo[j])
        atual = novo

    for texto, f in grupos:
        if not texto.strip():
            buf += texto
            continue
        f = efetivo(f)
        nucleo = texto.strip()
        inicio = texto[:len(texto) - len(texto.lstrip())]
        fim = texto[len(texto.rstrip()):]
        if f != atual:
            buf += inicio
            transitar(f)
            buf += nucleo + fim
        else:
            buf += texto
    transitar((False, False, False))
    return buf.strip()


def _paragrafo(tokens):
    """Tokens inline (("t", texto, fmt) e ("br",)) -> texto do parágrafo, uma linha por <br>."""
    linhas, atual = [], []
    for tk in tokens + [("br",)]:
        if tk[0] == "br":
            grupos, anterior_espaco = [], True
            for _, txt, f in atual:
                txt = re.sub(r"\s+", " ", INVISIVEIS.sub("", txt).replace("\xa0", " "))
                if anterior_espaco:
                    txt = txt.lstrip(" ")
                if not txt:
                    continue
                anterior_espaco = txt.endswith(" ")
                if grupos and grupos[-1][1] == f:
                    grupos[-1] = (grupos[-1][0] + txt, f)
                else:
                    grupos.append((txt, f))
            linha = _linha(grupos)
            if linha:
                linhas.append(linha)
            atual = []
        else:
            atual.append(tk)
    return "\n".join(linhas)


# ---------------------------------------------------------------- blocos

def _celulas(tr):
    return [c for c in tr.filhos if isinstance(c, No) and c.tag in ("td", "th")]


def _linhas(tabela):
    """<tr> da tabela (diretos ou em tbody/thead/tfoot), sem entrar em tabela aninhada."""
    out = []
    for c in tabela.filhos:
        if not isinstance(c, No):
            continue
        if c.tag == "tr":
            out.append(c)
        elif c.tag in ("tbody", "thead", "tfoot"):
            out += _linhas(c)
    return out


def _texto_simples(no):
    if isinstance(no, str):
        return no
    if no.tag in PULAR:
        return ""
    if no.tag == "br":
        return "\n"
    return "".join(_texto_simples(c) for c in no.filhos)


class _Render:
    def __init__(self, achatar=False):
        self.achatar = achatar  # dentro de célula de tabela de dados

    def tokens(self, no, fmt):
        """Tokens de `no`: ("t", texto, fmt), ("br",) e ("blocos", [str])."""
        out = []
        for c in no.filhos:
            if isinstance(c, str):
                out.append(("t", c, fmt))
                continue
            if c.tag in PULAR or c.tag in ("img", "hr", "input"):
                continue
            if c.tag == "br":
                out.append(("br",))
                continue
            f = _fmt(c, fmt)
            if c.tag == "table":
                out.append(("blocos", self.tabela(c, f)))
            elif c.tag == "pre":
                out.append(("blocos", _pre(c)))
            elif c.tag == "li":
                bl = self.blocos(c, f)
                if bl:
                    bl[0] = "- " + bl[0]
                out.append(("blocos", bl))
            elif c.tag in BLOCOS or c.tag in TABELA:
                out.append(("blocos", self.blocos(c, f)))
            else:
                out += self.tokens(c, f)
        return out

    def blocos(self, no, fmt):
        out, run = [], []
        for tk in self.tokens(no, fmt) + [("blocos", [])]:
            if tk[0] == "blocos":
                p = _paragrafo(run)
                if p:
                    out.append(p)
                out += [b for b in tk[1] if b]
                run = []
            else:
                run.append(tk)
        return out

    def celula(self, td, fmt):
        txt = " ".join(_Render(achatar=True).blocos(td, _fmt(td, fmt)))
        txt = re.sub(r"\s+", " ", txt).strip()
        return re.sub(r"(?<!\\)\|", r"\\|", txt)

    def tabela(self, tabela, fmt):
        linhas = _linhas(tabela)
        if self.achatar:
            return [" ".join(self.celula(td, fmt) for tr in linhas for td in _celulas(tr)).strip()]
        if all(len(_celulas(tr)) <= 1 for tr in linhas):  # diagramação
            out = []
            for tr in linhas:
                for td in _celulas(tr):
                    out += self.blocos(td, _fmt(td, fmt))
            return out
        matriz = []
        for tr in linhas:
            cel = []
            for td in _celulas(tr):
                cel.append(self.celula(td, fmt))
                try:
                    extra = int(td.attrs.get("colspan") or 1) - 1
                except ValueError:
                    extra = 0
                cel += [""] * max(0, min(extra, 50))
            if any(cel):
                matriz.append(cel)
        if not matriz:
            return []
        larg = max(len(c) for c in matriz)
        matriz = [c + [""] * (larg - len(c)) for c in matriz]
        md = ["| " + " | ".join(matriz[0]) + " |", "| " + " | ".join(["---"] * larg) + " |"]
        md += ["| " + " | ".join(c) + " |" for c in matriz[1:]]
        return ["\n".join(md)]


def _pre(no):
    txt = INVISIVEIS.sub("", _texto_simples(no)).replace("\xa0", " ").replace("\r", "")
    out = []
    for par in re.split(r"\n[ \t]*\n", txt):
        linhas = [x.rstrip() for x in par.split("\n")]
        linhas = [x for x in linhas if x.strip()]
        if not linhas:
            continue
        reguas = [x for x in linhas if REGUA.match(x)]
        if reguas and len(linhas) >= 3:  # tabela desenhada em texto
            out.append("```\n" + "\n".join(linhas) + "\n```")
        else:  # régua de sublinhado de título sai
            juntas = " ".join(x.strip() for x in linhas if not REGUA.match(x))
            if juntas.strip():
                out.append(re.sub(r"\s+", " ", juntas).strip())
    return out


def html_para_md(html):
    """Markdown do HTML do campo Texto da API do BCB (tachado entre ~~, a retirar no consolidado)."""
    blocos = _Render().blocos(arvore(html), (False, False, False))
    return "\n\n".join(blocos).strip() + "\n" if blocos else ""


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        dados = f.read()
    if argv[1].endswith(".json"):
        dados = (json.loads(dados).get("conteudo") or [{}])[0].get("Texto") or ""
    sys.stdout.write(html_para_md(dados))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
