#!/usr/bin/env python3
"""Conferência independente das normas `nivel_verificacao: pdf-extraido`: o texto da fonte PDF
extraído pelo PDFKit do macOS (conversor diferente do pypdf que gerou a norma) contra o corpo
da norma. Só lê as normas; não altera nada em plugins/.

cobertura = texto_vigente.cobertura(texto PDFKit, corpo da norma): fração das palavras da
fonte presentes no corpo (multiconjunto).
cobertura_ajustada = a mesma conta depois de normalizar os dois lados (NFKC, que desfaz as
ligaduras ﬁ/ﬂ, e "_" como separador, porque o PDFKit quebra as URLs do rodapé do SEI no "_"):
separa o artefato de extração da perda real de texto.

Uso:
  python3 scripts/conferir_pdf.py [--normas plugins/normas/normas]
      [--fontes dados/texto-vigente-fontes] [--saida dados/conferencia-pdf.json] [--limite N]
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, "..")
sys.path.insert(0, AQUI)

import pdf_macos  # noqa: E402
from texto_vigente import cobertura, palavras  # noqa: E402

LIMIAR = 0.99


def separar(md):
    """(dicionário do frontmatter, corpo) de uma norma; frontmatter só com chave: valor simples."""
    m = re.match(r"---\n(.*?)\n---\n?", md, re.S)
    if not m:
        return {}, md
    campos = {}
    for linha in m.group(1).splitlines():
        if ":" in linha and not linha.startswith((" ", "-")):
            k, v = linha.split(":", 1)
            campos[k.strip()] = v.strip()
    return campos, md[m.end():]


def normas_pdf(pasta):
    """[(id, caminho relativo, corpo)] das normas com nivel_verificacao: pdf-extraido."""
    res = []
    for raiz, _, arqs in os.walk(pasta):
        for a in sorted(arqs):
            if not a.endswith(".md"):
                continue
            p = os.path.join(raiz, a)
            with open(p, encoding="utf-8") as f:
                campos, corpo = separar(f.read())
            if campos.get("nivel_verificacao") == "pdf-extraido" and campos.get("id"):
                res.append((campos["id"], os.path.relpath(p, pasta), corpo))
    return sorted(res)


def ajustar(txt):
    return unicodedata.normalize("NFKC", txt).replace("_", " ")


def faltam(fonte_txt, corpo):
    """Counter das palavras da fonte ausentes do corpo (multiconjunto)."""
    return Counter(palavras(fonte_txt)) - Counter(palavras(corpo))


def conferir(normas, fontes, extrair=None):
    extrair = extrair or pdf_macos.texto_pdfkit
    itens = []
    for id_, arq, corpo in normas:
        pdf = os.path.join(fontes, id_ + ".pdf")
        item = {"id": id_, "arquivo": arq}
        if not os.path.exists(pdf):
            item.update(resultado="fonte-ausente", cobertura=None)
            itens.append(item)
            continue
        try:
            txt = extrair(pdf)
        except pdf_macos.ErroPdfMacos as e:
            item.update(resultado="erro", erro=str(e), cobertura=None)
            itens.append(item)
            continue
        cob = cobertura(txt, corpo)
        item.update(resultado="ok", cobertura=cob,
                    cobertura_ajustada=cobertura(ajustar(txt), ajustar(corpo)),
                    palavras_pdfkit=len(palavras(txt)), palavras_norma=len(palavras(corpo)))
        if cob < LIMIAR:
            falta = faltam(ajustar(txt), ajustar(corpo))
            item["palavras_faltando"] = sum(falta.values())
            item["faltam_amostra"] = [[w, n] for w, n in falta.most_common(20)]
        itens.append(item)
    return itens


def resumo(itens):
    ok = [i for i in itens if i["resultado"] == "ok"]
    altas = [i for i in ok if i["cobertura"] >= LIMIAR]
    baixas = sorted((i for i in ok if i["cobertura"] < LIMIAR), key=lambda i: i["cobertura"])
    ajust = [i for i in ok if i["cobertura_ajustada"] >= LIMIAR]
    linhas = ["normas pdf-extraido: %d; conferidas: %d; cobertura >= %d%%: %d; abaixo: %d; "
              "cobertura ajustada >= %d%%: %d"
              % (len(itens), len(ok), LIMIAR * 100, len(altas), len(baixas), LIMIAR * 100,
                 len(ajust))]
    for i in itens:
        if i["resultado"] != "ok":
            linhas.append("  %s: %s %s" % (i["id"], i["resultado"], i.get("erro", "")))
    for i in baixas:
        linhas.append("  %s  %.2f%%  ajustada %.2f%%  (faltam %d de %d após ajuste; ex.: %s)" % (
            i["id"], i["cobertura"] * 100, i["cobertura_ajustada"] * 100,
            i["palavras_faltando"], i["palavras_pdfkit"],
            ", ".join("%s×%d" % (w, n) for w, n in i["faltam_amostra"][:8])))
    return "\n".join(linhas)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--normas", default=os.path.join(RAIZ, "plugins", "normas", "normas"))
    ap.add_argument("--fontes", default=os.path.join(RAIZ, "dados", "texto-vigente-fontes"))
    ap.add_argument("--saida", default=os.path.join(RAIZ, "dados", "conferencia-pdf.json"))
    ap.add_argument("--limite", type=int)
    a = ap.parse_args(argv)
    normas = normas_pdf(a.normas)[:a.limite]
    itens = conferir(normas, a.fontes)
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    with open(a.saida, "w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False, indent=1)
    print(resumo(itens))
    print("relatório: %s" % a.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
