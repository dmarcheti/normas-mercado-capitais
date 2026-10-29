#!/usr/bin/env python3
"""Fase 2c: Docling só como conversor de PDF, contra o extrator atual (PDFKit) e o pypdf.

Gabarito: o texto da página do DOU salva no navegador (dados/fontes/manual/dou-<n>-*.html, div
"texto-dou"), quando existe. Métricas por norma e extrator:
- cobertura: fração das palavras do gabarito presentes no texto (multiconjunto, como no texto_vigente);
- precisão: fração das palavras do texto presentes no gabarito (pega lixo, cabeçalho repetido e
  palavra partida, que vira duas palavras inexistentes);
- partidas: palavras do texto que não existem no gabarito mas, coladas à seguinte, existem;
- tabelas: número de tabelas no gabarito (<table>) e no Markdown do Docling (blocos de linhas "|");
  células: fração das células não vazias do gabarito que aparecem como célula numa tabela do Docling.
Sem gabarito, só o tamanho e as tabelas.

O Docling roda no venv isolado (dados/fase-2c/docling-venv), sem OCR (os PDFs têm camada de texto);
a saída Markdown fica em dados/fase-2c/docling/<nome>.md.

Uso: python3 scripts/comparar_docling.py <pdf>... [--gabarito-dir dados/fontes/manual]
     [--saida dados/fase-2c/docling] [--relatorio dados/fase-2c/docling/comparacao.json]
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texto_vigente as tv  # noqa: E402
import pdf_macos  # noqa: E402

VENV_PY = "dados/fase-2c/docling-venv/bin/python"
DOCLING = r'''
import sys, time
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
o = PdfPipelineOptions(); o.do_ocr = False; o.do_table_structure = True
c = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=o)})
for pdf, md in zip(sys.argv[1::2], sys.argv[2::2]):
    t = time.time()
    r = c.convert(pdf)
    open(md, "w", encoding="utf-8").write(r.document.export_to_markdown())
    print("%s %.1f" % (md, time.time() - t), flush=True)
'''


class _Dou(HTMLParser):
    """Texto e tabelas da div texto-dou."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.prof, self.dentro, self.partes = 0, False, []
        self.tabelas, self.celula, self.na_celula = [], [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.dentro and tag == "div" and "texto-dou" in (a.get("class") or ""):
            self.dentro, self.prof = True, 0
        if self.dentro:
            if tag == "div":
                self.prof += 1
            if tag in ("p", "br", "tr"):
                self.partes.append("\n")
            if tag == "table":
                self.tabelas.append([])
            if tag in ("td", "th"):
                self.na_celula, self.celula = True, []

    def handle_endtag(self, tag):
        if not self.dentro:
            return
        if tag in ("td", "th") and self.na_celula:
            self.na_celula = False
            txt = re.sub(r"\s+", " ", "".join(self.celula)).strip()
            if txt and self.tabelas:
                self.tabelas[-1].append(txt)
            self.partes.append(" ")
        if tag == "div":
            self.prof -= 1
            if self.prof == 0:
                self.dentro = False

    def handle_data(self, d):
        if self.dentro:
            self.partes.append(d)
            if self.na_celula:
                self.celula.append(d)


def gabarito(numero, pasta):
    arqs = sorted(glob.glob(os.path.join(pasta, "dou-%d-*.html" % numero)))
    arqs = [a for a in arqs if "retificacao" not in a and "republicacao" not in a]
    if not arqs:
        return None
    p = _Dou()
    with open(arqs[0], encoding="utf-8", errors="replace") as f:
        p.feed(f.read())
    return {"arquivo": arqs[0], "texto": "".join(p.partes), "tabelas": [t for t in p.tabelas if t]}


def _norm(txt):
    return tv.palavras(tv.normalizar_pdf(txt))


def metricas(gab, txt):
    a, b = Counter(_norm(gab)), Counter(_norm(txt))
    ta, tb = sum(a.values()), sum(b.values())
    cob = sum(min(n, b[w]) for w, n in a.items()) / ta if ta else 0
    prec = sum(min(n, a[w]) for w, n in b.items()) / tb if tb else 0
    lista = _norm(txt)
    partidas = sum(1 for x, y in zip(lista, lista[1:]) if x not in a and (x + y) in a)
    return {"cobertura": round(cob, 4), "precisao": round(prec, 4), "partidas": partidas, "palavras": tb}


def tabelas_md(md):
    """Lista de tabelas (cada uma, lista de células não vazias) do Markdown."""
    out, atual = [], None
    for linha in md.split("\n"):
        if linha.strip().startswith("|"):
            if atual is None:
                atual = []
                out.append(atual)
            if re.match(r"^\s*\|[\s:|-]+\|\s*$", linha):
                continue
            atual += [c.strip() for c in linha.strip().strip("|").split("|") if c.strip()]
        else:
            atual = None
    return out


def celulas_achadas(tab_gab, tab_md):
    norm = lambda s: " ".join(_norm(s))  # noqa: E731
    gab = [norm(c) for t in tab_gab for c in t if norm(c)]
    md = Counter(norm(c) for t in tab_md for c in t)
    if not gab:
        return None
    ach = 0
    for c in gab:
        if md[c] > 0:
            md[c] -= 1
            ach += 1
    return round(ach / len(gab), 4)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--gabarito-dir", default="dados/fontes/manual")
    ap.add_argument("--saida", default="dados/fase-2c/docling")
    ap.add_argument("--relatorio", default="dados/fase-2c/docling/comparacao.json")
    args = ap.parse_args(argv[1:])
    os.makedirs(args.saida, exist_ok=True)
    pares = []
    for pdf in args.pdfs:
        md = os.path.join(args.saida, os.path.basename(pdf).rsplit(".", 1)[0] + ".md")
        if not os.path.exists(md):
            pares += [pdf, md]
    tempos = {}
    if pares:
        t0 = time.time()
        r = subprocess.run([VENV_PY, "-c", DOCLING] + pares, capture_output=True, text=True)
        if r.returncode:
            print(r.stderr[-3000:])
            return 1
        for linha in r.stdout.split("\n"):
            if linha.strip():
                md, s = linha.rsplit(" ", 1)
                tempos[md] = float(s)
        print("docling: %d PDFs em %.0f s" % (len(pares) // 2, time.time() - t0))
    rel = []
    for pdf in args.pdfs:
        nome = os.path.basename(pdf).rsplit(".", 1)[0]
        mdp = os.path.join(args.saida, nome + ".md")
        with open(mdp, encoding="utf-8") as f:
            doc = f.read()
        kit = tv.normalizar_pdf(pdf_macos.texto_pdfkit(pdf))
        pyp = tv.normalizar_pdf(tv._pdf_txt(pdf))
        m = re.search(r"cvm-0*(\d+)", nome)
        gab = gabarito(int(m.group(1)), args.gabarito_dir) if m else None
        tmd = tabelas_md(doc)
        linha = {"pdf": pdf, "docling_segundos": tempos.get(mdp), "tabelas_docling": len(tmd),
                 "palavras": {"pdfkit": len(_norm(kit)), "pypdf": len(_norm(pyp)), "docling": len(_norm(doc))}}
        if gab:
            linha.update({
                "gabarito": gab["arquivo"], "tabelas_gabarito": len(gab["tabelas"]),
                "pdfkit": metricas(gab["texto"], kit), "pypdf": metricas(gab["texto"], pyp),
                "docling": metricas(gab["texto"], doc),
                "celulas_docling": celulas_achadas(gab["tabelas"], tmd),
            })
        rel.append(linha)
    with open(args.relatorio, "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
    print("%-26s %-17s %-17s %-17s %-9s %s" % ("pdf", "pdfkit cob/prec/part", "pypdf", "docling",
                                              "tab g/d", "células"))
    for r in rel:
        f = lambda k: "%.3f/%.3f/%d" % (r[k]["cobertura"], r[k]["precisao"], r[k]["partidas"]) if k in r else "-"  # noqa: E731
        print("%-26s %-17s %-17s %-17s %-9s %s" % (os.path.basename(r["pdf"])[:26], f("pdfkit"), f("pypdf"),
                                                  f("docling"), "%s/%s" % (r.get("tabelas_gabarito", "-"),
                                                                           r["tabelas_docling"]),
                                                  r.get("celulas_docling", "-")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
