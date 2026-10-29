#!/usr/bin/env python3
"""Texto e OCR de PDF pelas bibliotecas nativas do macOS (PDFKit e Vision), via
scripts/pdf_macos.swift. Sem dependência fora da biblioteca padrão; só funciona no macOS.

O .swift é compilado uma vez com `swiftc -O` para dados/bin/pdf_macos e recompilado quando
o fonte muda; sem swiftc, cai para `swift scripts/pdf_macos.swift` (mais lento).

  texto_pdfkit(path) -> str                 páginas separadas por form feed
  ocr(path) -> (str, [confiança média por página])

Uso:
  python3 scripts/pdf_macos.py texto|ocr <pdf>
  python3 scripts/pdf_macos.py ocr-sem-texto [--relatorio dados/texto-vigente-camada-2.json]
      [--fontes dados/texto-vigente-fontes] [--saida dados/ocr]
    OCR dos itens com resultado "sem-texto" no relatório do texto_vigente: grava <saida>/<id>.txt
    e <saida>/relatorio.json (páginas, confiança média e mínima, palavras, legibilidade, segundos).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "pdf_macos.swift")
BINARIO = os.path.join(AQUI, "..", "dados", "bin", "pdf_macos")
TIMEOUT_TEXTO = 120
TIMEOUT_OCR = 1800


class ErroPdfMacos(RuntimeError):
    pass


def _exigir_macos():
    if sys.platform != "darwin":
        raise ErroPdfMacos("pdf_macos só funciona no macOS (PDFKit e Vision); plataforma atual: %s"
                           % sys.platform)


def _comando():
    """Prefixo do comando: o binário compilado (compila se faltar ou estiver velho) ou o swift."""
    _exigir_macos()
    velho = (not os.path.exists(BINARIO)
             or os.path.getmtime(BINARIO) < os.path.getmtime(FONTE))
    if velho and shutil.which("swiftc"):
        os.makedirs(os.path.dirname(BINARIO), exist_ok=True)
        r = subprocess.run(["swiftc", "-O", FONTE, "-o", BINARIO],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise ErroPdfMacos("swiftc falhou ao compilar %s:\n%s" % (FONTE, r.stderr.strip()))
        velho = False
    if not velho:
        return [BINARIO]
    if shutil.which("swift"):
        return ["swift", FONTE]
    raise ErroPdfMacos("swift/swiftc não encontrados; instale as Command Line Tools do Xcode")


def _rodar(args, timeout):
    cmd = _comando() + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ErroPdfMacos("pdf_macos %s: tempo esgotado (%d s)" % (" ".join(args), timeout))
    if r.returncode != 0:
        raise ErroPdfMacos("pdf_macos %s: código %d: %s"
                           % (" ".join(args), r.returncode, (r.stderr or "").strip()))
    return r


def _saida(stdout):
    # o swift termina a saída com uma quebra de linha do print
    return stdout[:-1] if stdout.endswith("\n") else stdout


def texto_pdfkit(path, timeout=TIMEOUT_TEXTO):
    """Texto do PDF pelo PDFKit, páginas separadas por form feed (\\f)."""
    return _saida(_rodar(["texto", os.path.abspath(path)], timeout).stdout)


def paginas_ocr(stderr):
    """[(confiança média, trechos .accurate, trechos extras)] por página, das linhas
    'CONF<TAB>página<TAB>média<TAB>trechos<TAB>extras' do stderr do swift."""
    res = []
    for linha in (stderr or "").splitlines():
        partes = linha.split("\t")
        if len(partes) >= 4 and partes[0] == "CONF":
            res.append((float(partes[2]), int(partes[3]), int(partes[4]) if len(partes) > 4 else 0))
    return res


def confiancas(stderr):
    """Confiança média por página (passada .accurate)."""
    return [p[0] for p in paginas_ocr(stderr)]


def ocr(path, timeout=TIMEOUT_OCR, dpi=300, detalhe=False):
    """(texto por OCR, páginas separadas por \\f; [confiança média por página]).
    Com detalhe=True, a lista traz (confiança, trechos .accurate, trechos extras) por página."""
    r = _rodar(["ocr", os.path.abspath(path), str(dpi)], timeout)
    return _saida(r.stdout), (paginas_ocr(r.stderr) if detalhe else confiancas(r.stderr))


def pdf_teste(saida, txt, timeout=TIMEOUT_TEXTO):
    """Gera um PDF simples com o texto de `txt` (form feed separa páginas); para os testes."""
    _rodar(["pdf-teste", os.path.abspath(saida), os.path.abspath(txt)], timeout)
    return saida


def ocr_sem_texto(relatorio, fontes, saida, extrair=None):
    """OCR dos itens "sem-texto" de um relatório do texto_vigente; devolve o relatório do OCR."""
    from texto_vigente import legibilidade  # só aqui: pdf_macos não depende do texto_vigente
    extrair = extrair or ocr
    with open(relatorio, encoding="utf-8") as f:
        ids = [i["id"] for i in json.load(f) if i.get("resultado") == "sem-texto"]
    os.makedirs(saida, exist_ok=True)
    res = []
    for id_ in ids:
        pdf = os.path.join(fontes, id_ + ".pdf")
        item = {"id": id_}
        if not os.path.exists(pdf):
            item["erro"] = "fonte ausente: %s" % pdf
            res.append(item)
            continue
        t0 = time.time()
        txt, pags = extrair(pdf, detalhe=True)
        seg = time.time() - t0
        conf = [p[0] for p in pags]
        with open(os.path.join(saida, id_ + ".txt"), "w", encoding="utf-8") as f:
            f.write(txt)
        frac, n = legibilidade(txt)
        item.update(paginas=len(conf),
                    confianca_media=round(sum(conf) / len(conf), 4) if conf else None,
                    confianca_minima=round(min(conf), 4) if conf else None,
                    confianca_por_pagina=[round(c, 4) for c in conf],
                    trechos_extras=sum(p[2] for p in pags),
                    palavras=n, legibilidade=frac, segundos=round(seg, 1),
                    segundos_por_pagina=round(seg / len(conf), 2) if conf else None)
        res.append(item)
    with open(os.path.join(saida, "relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    return res


def _main_lote(argv):
    raiz = os.path.join(AQUI, "..")
    ap = argparse.ArgumentParser(prog="pdf_macos.py ocr-sem-texto")
    ap.add_argument("--relatorio", default=os.path.join(raiz, "dados", "texto-vigente-camada-2.json"))
    ap.add_argument("--fontes", default=os.path.join(raiz, "dados", "texto-vigente-fontes"))
    ap.add_argument("--saida", default=os.path.join(raiz, "dados", "ocr"))
    a = ap.parse_args(argv)
    for i in ocr_sem_texto(a.relatorio, a.fontes, a.saida):
        if "erro" in i:
            print("%s: %s" % (i["id"], i["erro"]))
        else:
            print("%s: %d pág., confiança média %.3f (mín. %.3f), %d palavras, legibilidade %.2f, "
                  "%.1f s" % (i["id"], i["paginas"], i["confianca_media"] or 0,
                              i["confianca_minima"] or 0, i["palavras"], i["legibilidade"],
                              i["segundos"]))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["ocr-sem-texto"]:
        return _main_lote(argv[1:])
    if len(argv) != 2 or argv[0] not in ("texto", "ocr"):
        print(__doc__, file=sys.stderr)
        return 64
    if argv[0] == "texto":
        print(texto_pdfkit(argv[1]))
    else:
        txt, conf = ocr(argv[1])
        print(txt)
        print("confiança por página: %s" % ", ".join("%.3f" % c for c in conf), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
