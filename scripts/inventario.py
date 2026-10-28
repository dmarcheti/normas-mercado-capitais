#!/usr/bin/env python3
"""Inventário de atos alteradores das resoluções CVM.

extrair_pagina(html): lê a página de uma resolução no site da CVM.
montar_inventario(numeros, paginas): junta a página de cada resolução com a
página de cada alteradora (data do ato e do DOU).
Uso (rede): python3 scripts/inventario.py [--cache DIR] [--saida ARQUIVO]
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

BASE = "https://conteudo.cvm.gov.br"
URL_PAGINA = BASE + "/legislacao/resolucoes/resol%03d.html"
NORMAS = [175, 160, 60, 17, 30, 21, 80, 50]
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
MESES = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def _espaco(txt):
    return re.sub(r"\s+", " ", txt.replace("\xa0", " ")).strip()


class _Pagina(HTMLParser):
    """Coleta, dentro do <article>, os parágrafos, as âncoras e o título."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.em_artigo = False
        self.titulo = ""
        self._em_h2 = False
        self.paragrafos = []  # [{"texto": str, "ancoras": [(href, texto)]}]
        self.ancoras = []  # todas as âncoras do artigo: (href, texto)
        self.negrito_data = ""
        self._p = None
        self._a = None
        self._em_b = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "article" and "contentTextoGeral" in (a.get("class") or ""):
            self.em_artigo = True
        if not self.em_artigo:
            return
        if tag == "h2":
            self._em_h2 = True
        elif tag == "p":
            self._p = {"texto": "", "ancoras": []}
        elif tag == "br" and self._p is not None:
            self._p["texto"] += "\n"
        elif tag == "b":
            self._em_b = True
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], ""]

    def handle_endtag(self, tag):
        if not self.em_artigo:
            return
        if tag == "article":
            self.em_artigo = False
        elif tag == "h2":
            self._em_h2 = False
        elif tag == "b":
            self._em_b = False
        elif tag == "p" and self._p is not None:
            self.paragrafos.append(self._p)
            self._p = None
        elif tag == "a" and self._a is not None:
            anc = (self._a[0], _espaco(self._a[1]))
            self.ancoras.append(anc)
            if self._p is not None:
                self._p["ancoras"].append(anc)
            self._a = None

    def handle_data(self, data):
        if not self.em_artigo:
            return
        if self._em_h2:
            self.titulo += data
        if self._em_b and not self.negrito_data:
            self.negrito_data = data
        if self._p is not None:
            self._p["texto"] += data
        if self._a is not None:
            self._a[1] += data


def _data_cvm(txt):
    """'Tue Feb 09 19:00:00 BRST 2021' -> '2021-02-09'."""
    m = re.search(r"([A-Z][a-z]{2}) (\d{1,2}) \d\d:\d\d:\d\d \w+ (\d{4})", txt)
    if not m or m.group(1) not in MESES:
        return None
    return "%s-%02d-%02d" % (m.group(3), MESES[m.group(1)], int(m.group(2)))


def _datas_dou(txt):
    """Todas as datas dd.mm.aaaa do trecho, em AAAA-MM-DD."""
    return ["%s-%s-%s" % (a, m, d)
            for d, m, a in re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", txt)]


def _numero_da_resolucao(href):
    m = re.search(r"/resolucoes/resol(\d+)\.html?$", href)
    return int(m.group(1)) if m else None


def extrair_pagina(html):
    """Lê a página de uma resolução da CVM e devolve um dict com:
    numero, titulo, data, dou, retificada_dou, ementa, normas_na_ementa
    (resoluções citadas com link na ementa), url_original,
    url_consolidado ({docx, pdf, partes}), url_ato ({htm, pdf, docx}) e
    alteradoras ([{numero, ano}], na ordem da página).
    """
    p = _Pagina()
    p.feed(html)
    titulo = _espaco(p.titulo)
    m = re.search(r"(\d+)\s*$", titulo)
    numero = int(m.group(1)) if m else None
    textos = [_espaco(x["texto"].replace("\n", " ")) for x in p.paragrafos]
    tudo = "\n".join(x["texto"] for x in p.paragrafos)

    # Ementa: primeiro parágrafo com texto depois da data, sem as notas "(Publicada ...)".
    ementa, par_ementa = "", None
    for par in p.paragrafos:
        t = _espaco(par["texto"].replace("\n", " "))
        if not t or par["texto"].strip() == p.negrito_data.strip():
            continue
        par_ementa = par
        ementa = _espaco(re.split(r"\(\s*(?:Publicada|Retificada|Republicada)", t)[0])
        break

    dou = None
    m = re.search(r"Publicada no DOU de (\d{2}\.\d{2}\.\d{4})", tudo)
    if m:
        dou = _datas_dou(m.group(1))[0]
    retificada = []
    for m in re.finditer(r"Retificada no DOU de ([^)]*)\)", tudo):
        retificada += _datas_dou(m.group(1))

    # Resoluções citadas (com link) na ementa. É só uma pista de quais normas o ato
    # mexe: ementas como "atualiza a denominação ... em diversas resoluções" não listam todas.
    citadas = []
    if par_ementa is not None:
        for href, _ in par_ementa["ancoras"]:
            n = _numero_da_resolucao(href)
            if n is not None and n not in citadas:
                citadas.append(n)

    original, consolidado, ato = [], {}, {}
    for href, texto in p.ancoras:
        url = urljoin(BASE, href)
        baixo = texto.lower()
        arquivo = href.rsplit("/", 1)[-1].lower()
        if "redação original" in baixo:
            original.append(url)
        elif "texto consolidado" in baixo and "[doc]" in baixo:
            consolidado.setdefault("docx", url)
        elif "texto consolidado" in baixo:
            consolidado.setdefault("pdf", url)
        elif "consolid_" in href:
            consolidado.setdefault("partes", []).append(url)
        elif re.fullmatch(r"resol0*%s\.(htm|pdf|docx)" % numero, arquivo):
            # arquivo do próprio ato (texto publicado), qualquer que seja o rótulo do link
            ato.setdefault(arquivo.rsplit(".", 1)[1], url)
        elif re.fullmatch(r"resol0*%sconsolid\.htm" % numero, arquivo):
            consolidado.setdefault("htm", url)

    alteradoras = []
    for par in p.paragrafos:
        # "ALTERADA pelas Resoluções 162/22 e 226/25." (pode vir depois de um "VIDE ..." no mesmo parágrafo)
        if not re.search(r"(?m)^\s*ALTERAD", par["texto"]):
            continue
        for href, texto in par["ancoras"]:
            n = _numero_da_resolucao(href)
            ano = re.search(r"/(\d{2})$", texto)
            if n is not None and ano:
                alteradoras.append({"numero": n, "ano": 2000 + int(ano.group(1))})

    return {
        "numero": numero,
        "titulo": titulo,
        "data": _data_cvm(p.negrito_data),
        "dou": dou,
        "retificada_dou": retificada,
        "ementa": ementa,
        "normas_na_ementa": citadas,
        "url_original": original,
        "url_consolidado": consolidado,
        "url_ato": ato,
        "alteradoras": alteradoras,
    }


def montar_inventario(numeros, paginas):
    """paginas: {numero: dict de extrair_pagina (+ "url_pagina")}. Devolve a lista do inventário."""
    saida = []
    for n in numeros:
        pag = paginas[n]
        alts = []
        for a in pag["alteradoras"]:
            ap = paginas[a["numero"]]
            alts.append({
                "numero": a["numero"],
                "data": ap["data"],
                "dou": ap["dou"],
                "url_pagina": ap.get("url_pagina") or URL_PAGINA % a["numero"],
                "normas_na_ementa": ap.get("normas_na_ementa", []),
                "url_ato": ap.get("url_ato", {}),
            })
        cons = {k: v for k, v in pag["url_consolidado"].items() if k in ("docx", "pdf", "htm")}
        saida.append({
            "id": "cvm-res-%d" % n,
            "numero": n,
            "data": pag["data"],
            "dou": pag["dou"],
            "url_pagina": pag.get("url_pagina") or URL_PAGINA % n,
            "url_original": pag["url_original"],
            "url_consolidado": cons,
            "alteradoras": alts,
        })
    return saida


def carregar_inventario(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _baixar(numero, cache):
    arq = os.path.join(cache, "resol%03d.html" % numero) if cache else None
    if arq and os.path.exists(arq):
        with open(arq, encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(URL_PAGINA % numero, headers={"User-Agent": USER_AGENT})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    if arq:
        os.makedirs(cache, exist_ok=True)
        with open(arq, "w", encoding="utf-8") as f:
            f.write(html)
    time.sleep(0.7)
    return html


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default="dados/paginas-cvm", help="pasta de cache das páginas (ignorada pelo Git)")
    ap.add_argument("--saida", default="fontes/inventario.json")
    args = ap.parse_args(argv)

    paginas = {}
    for n in NORMAS:
        paginas[n] = extrair_pagina(_baixar(n, args.cache))
        paginas[n]["url_pagina"] = URL_PAGINA % n
    for n in NORMAS:
        for a in paginas[n]["alteradoras"]:
            if a["numero"] not in paginas:
                paginas[a["numero"]] = extrair_pagina(_baixar(a["numero"], args.cache))
                paginas[a["numero"]]["url_pagina"] = URL_PAGINA % a["numero"]
    inv = montar_inventario(NORMAS, paginas)
    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(inv, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("%d normas, %d alteradoras distintas -> %s" % (
        len(inv), len(paginas) - len(NORMAS), args.saida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
