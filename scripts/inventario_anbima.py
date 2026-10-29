#!/usr/bin/env python3
"""Inventário da autorregulação da ANBIMA (camada 5), sem LLM.

A lista de documentos das páginas de código (anbima.com.br/pt_br/autorregular/codigos/...) é
montada em parte por JavaScript: a versão vigente de alguns códigos e as versões anteriores não
estão no HTML que o servidor entrega. Por isso a entrada é o JSON lido no navegador (Claude in
Chrome, 2026-10-29): {página: [[rótulo, caminho depois de data/files/], ...]}. A página de Ética
(institucional/a-anbima/etica-e-integridade.htm) é estática e lida aqui por HTTP.

Classificação (por regra sobre o rótulo; sem rótulo conhecido, `fora`):
- `vigente`: "vigente a partir de", "(vigente)", "vigente - consolidado", Glossário, e os atos
  de interpretação listados sem data de fim (deliberação, parecer, alinhamento ACT,
  perguntas e respostas, comunicado de supervisão);
- `anterior`: "vigente de X a Y" (versão encerrada) e "versão anterior";
- `fora`: questionários (QDD), checklists, modelos, manuais de registro e de envio de dados,
  metodologias, guias e formulários: material operacional, não norma.
Documento repetido em várias páginas (Glossário, Deveres Básicos) vira um item, com as páginas.

Uso: python3 scripts/inventario_anbima.py [--paginas dados/fase-2c/anbima/paginas.json]
     [--saida fontes/acervo-anbima.json]
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario import USER_AGENT  # noqa: E402

BASE = "https://www.anbima.com.br/"
ETICA = BASE + "pt_br/institucional/a-anbima/etica-e-integridade.htm"
CODIGOS = BASE + "pt_br/autorregular/codigos/%s.htm"
FORA = re.compile(r"^(Para |De |Checklist|Modelo|Manual|Guia|FIP - |PAF|Relat[óo]rio de troca|"
                  r"Minutas|C[óo]digo de [ée]tica e conduta profissional|C[óo]digo de fornecedores|MANUAL)", re.I)
INTERPRETACAO = re.compile(r"Delibera|Parecer|PARECER|Alinhamento ACT|Perguntas e [Rr]espostas|Q&A|"
                           r"Comunicado|Diretrizes", re.I)
DATA = r"(\d{2})[./](\d{2})[./](\d{2,4})"


def _data(m):
    d, mth, a = m.groups()
    return "%s-%s-%s" % (a if len(a) == 4 else "20" + a, mth, d)


def classificar(rotulo):
    r = re.sub(r"^\d{2}/\d{2}/\d{2,4}", "", rotulo).strip()  # data de publicação colada ao rótulo
    m = re.search(r"vigente a partir de " + DATA, r, re.I)
    if m:
        return "vigente", _data(m), r
    if re.search(r"vigente de .* (?:a|até) ", r, re.I) or "versão anterior" in r.lower():
        return "anterior", None, r
    if re.search(r"\(vigente\)|vigente - consolidado", r, re.I) or r.startswith("Glossário"):
        return "vigente", None, r
    if FORA.search(r):
        return "fora", None, r
    if INTERPRETACAO.search(r) or re.match(r"C[óo]digo de [ÉE]tica para Associados|Regras e procedimentos para ades", r, re.I):
        return "vigente", None, r
    return "fora", None, r


def tipo_doc(rotulo):
    r = rotulo.lower()
    if r.startswith("código") or r.startswith("codigo"):
        return "codigo"
    if r.startswith("regras e procedimentos"):
        return "regras-procedimentos"
    if r.startswith("glossário"):
        return "glossario"
    if "delibera" in r:
        return "deliberacao"
    if "parecer" in r:
        return "parecer"
    if "diretrizes" in r:
        return "diretrizes"
    return "orientacao"


def etica():
    req = urllib.request.Request(ETICA, headers={"User-Agent": USER_AGENT})
    h = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    out = []
    for href, x in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', h, re.S):
        if "data/files/" in href:
            rot = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
            if rot and not re.match(r"^\d{2}/\d{2}/\d{4}$", rot):
                out.append([rot, htmllib.unescape(href).split("data/files/", 1)[1]])
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paginas", default="dados/fase-2c/anbima/paginas.json")
    ap.add_argument("--saida", default="fontes/acervo-anbima.json")
    args = ap.parse_args(argv[1:])
    with open(args.paginas, encoding="utf-8") as f:
        paginas = json.load(f)
    paginas["etica"] = etica()
    docs = {}
    for pag, itens in paginas.items():
        url_pag = ETICA if pag == "etica" else CODIGOS % pag
        for rot, caminho in itens:
            url = BASE + "data/files/" + caminho
            sit, desde, limpo = classificar(rot)
            d = docs.setdefault(url, {"titulo": limpo, "url": url,
                                      "arquivo": urllib.parse.unquote(caminho.rsplit("/", 1)[-1]),
                                      "situacao": sit, "vigente_desde": desde, "paginas": []})
            if url_pag not in d["paginas"]:
                d["paginas"].append(url_pag)
            ordem = {"vigente": 0, "anterior": 1, "fora": 2}
            if ordem[sit] < ordem[d["situacao"]]:
                d.update(titulo=limpo, situacao=sit, vigente_desde=desde)
    for d in docs.values():
        d["tipo"] = tipo_doc(d["titulo"])
        d["formato"] = d["arquivo"].rsplit(".", 1)[-1].lower()
    out = {"fonte": "páginas de código da ANBIMA (lidas no navegador) e página de Ética",
           "lido_em": time.strftime("%Y-%m-%d"),
           "documentos": sorted(docs.values(), key=lambda d: (d["situacao"], d["tipo"], d["titulo"]))}
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    from collections import Counter
    print(Counter(d["situacao"] for d in docs.values()))
    for d in out["documentos"]:
        if d["situacao"] == "vigente":
            print("%-22s %-10s %-4s %s" % (d["tipo"], d["vigente_desde"] or "-", d["formato"], d["titulo"][:95]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
