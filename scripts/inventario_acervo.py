#!/usr/bin/env python3
"""Inventário do perímetro da v1.0 no site da CVM (camadas 1 e 2), só por script.

Lê a busca do site (todas as Resoluções, Instruções, Pareceres de Orientação e
Ofícios-Circulares numa página cada), a planilha do Estoque Regulatório da CVM e
a página de cada Resolução, de cada Instrução não revogada e de cada Parecer.
Grava fontes/acervo.json e imprime o resumo.

Situação de cada Resolução (campo `situacao`):
- revogada: "(Revogada)" no título da busca ou parágrafo "REVOGADA pela..." na página;
- vigente: está no Estoque Regulatório e não está revogada;
- so-alteradora: fora do Estoque, não revogada, ementa só altera ou revoga outros atos;
- verificar: o resto (ex.: editada depois da data do Estoque).

Uso (rede): python3 scripts/inventario_acervo.py [--cache DIR] [--saida ARQUIVO]
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario import BASE, USER_AGENT, _Pagina, _data_cvm, _espaco, extrair_pagina  # noqa: E402

BUSCA = (BASE + "/legislacao/index.html?buscado=true&contCategoriasCheck=1"
         "&vimDaCategoria=/legislacao/%s/&itensPagina=1000&searchPage=1")
CATEGORIAS = ("resolucoes", "instrucoes", "pareceres-orientacao", "oficios-circulares")
ESTOQUE = BASE + "/legislacao/resolucoes/anexos/Estoque_Regulatorio_CVM.xlsx"
SO_ALTERA = re.compile(
    r"^(Altera|Revoga|Acrescenta|Prorroga|Dá nova redação|Inclui|Suspende|Modifica|Adia)\b")
XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def itens_da_busca(html):
    """[{titulo, url, descricao, data}] dos <article> da página de resultados."""
    out = []
    for art in re.findall(r"<article>(.*?)</article>", html, re.S):
        m = re.search(r'<h3><a href="([^"]+)" title="([^"]*)"', art)
        if not m:
            continue
        d = re.search(r'contentDesc">(.*?)</div>', art, re.S)
        dt = re.search(r"<b>Data:</b>\s*(\d{2})/(\d{2})/(\d{4})", art)
        desc = htmllib.unescape(re.sub(r"<[^>]+>", " ", d.group(1))) if d else ""
        out.append({
            "titulo": _espaco(htmllib.unescape(m.group(2))),
            "url": urljoin(BASE, m.group(1)),
            "descricao": _espaco(desc),
            "data": "%s-%s-%s" % (dt.group(3), dt.group(2), dt.group(1)) if dt else None,
        })
    return out


def ler_estoque(path):
    """(data de atualização AAAA-MM-DD, [números das Resoluções do Estoque])."""
    z = zipfile.ZipFile(path)
    ss = ["".join(t.text or "" for t in si.iter(XL + "t"))
          for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(XL + "si")]
    textos = []
    for c in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(XL + "c"):
        v = c.find(XL + "v")
        if v is not None:
            textos.append(ss[int(v.text)] if c.get("t") == "s" else v.text)
    tudo = "\n".join(textos)
    m = re.search(r"atualizado em (\d{2})/(\d{2})/(\d{4})", tudo)
    data = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None
    nums = sorted({int(n) for n in re.findall(r"Resolução CVM\s*(?:nº\s*)?(\d+)", tudo)})
    return data, nums


def detalhes_da_pagina(html):
    """Dados comuns a qualquer ato da CVM: data, DOU, revogação, alterações e arquivos."""
    p = _Pagina()
    p.feed(html)
    revogada, alterada = "", []
    for par in p.paragrafos:
        t = _espaco(par["texto"].replace("\n", " "))
        if re.match(r"REVOGAD", t):
            revogada = t
        if re.search(r"(?m)^\s*ALTERAD", par["texto"]):
            alterada += [txt for _, txt in par["ancoras"] if re.search(r"\d+/\d{2}$", txt)]
    tudo = "\n".join(x["texto"] for x in p.paragrafos)
    dou = re.search(r"Publicad[ao] no DOU de (\d{2})\.(\d{2})\.(\d{2,4})", tudo)
    arquivos = {}
    m = re.search(r"(\d+)\s*$", _espaco(p.titulo))
    proprio = re.compile(r"^[a-z]+0*%s(consolid)?\.\w+$" % m.group(1)) if m else None
    for href, texto in p.ancoras:
        ext = href.rsplit(".", 1)[-1].lower()
        if ext not in ("pdf", "doc", "docx", "htm", "html"):
            continue
        if proprio and not proprio.match(href.rsplit("/", 1)[-1].lower()):
            continue  # link citado na ementa ou no "VIDE", não é arquivo deste ato
        tipo = "consolidado" if "consolid" in href.lower() or "consolidado" in texto.lower() else "ato"
        arquivos.setdefault(tipo, {}).setdefault(ext, urljoin(BASE, href))
    ano = dou and (dou.group(3) if len(dou.group(3)) == 4 else
                   ("19" if int(dou.group(3)) > 50 else "20") + dou.group(3))
    return {
        "data": _data_cvm(p.negrito_data),
        "dou": "%s-%s-%s" % (ano, dou.group(2), dou.group(1)) if dou else None,
        "revogada": revogada,
        "alterada_por": list(dict.fromkeys(alterada)),
        "arquivos": arquivos,
    }


def situacao_resolucao(titulo, revogada, ementa, no_estoque):
    if "(Revogada)" in titulo or revogada:
        return "revogada"
    if no_estoque:
        return "vigente"
    if SO_ALTERA.match(ementa):
        return "so-alteradora"
    return "verificar"


def oficio(item):
    """Superintendência, ano e PDF de um Ofício-Circular da busca."""
    partes = item["url"].split("/legislacao/oficios-circulares/", 1)[1].split("/")
    slug = partes[-1].rsplit(".", 1)[0]
    citadas = re.findall(r"(Instrução|Resolução) CVM n[ºo°]?\s*(\d+)", item["descricao"])
    return {
        "titulo": item["titulo"], "data": item["data"], "superintendencia": partes[0],
        "descricao": item["descricao"], "url_pagina": item["url"],
        "url_pdf": "%s/export/sites/cvm/legislacao/oficios-circulares/%s/anexos/%s.pdf" % (
            BASE, partes[0], slug),
        "cita": ["%s %s" % (t, n) for t, n in citadas],
    }


def _get(url, destino, binario=False):
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        modo = "rb" if binario else "r"
        with open(destino, modo, **({} if binario else {"encoding": "utf-8", "errors": "replace"})) as f:
            return f.read()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    corpo = urllib.request.urlopen(req, timeout=60).read()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(corpo)
    time.sleep(0.7)
    return corpo if binario else corpo.decode("utf-8", errors="replace")


def _numero(titulo):
    m = re.search(r"(\d+)\s*(?:\(|$)", titulo)
    return int(m.group(1)) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default="dados/paginas-cvm")
    ap.add_argument("--saida", default="fontes/acervo.json")
    args = ap.parse_args(argv)
    c = args.cache

    busca = {cat: itens_da_busca(_get(BUSCA % cat, os.path.join(c, "busca-%s.html" % cat)))
             for cat in CATEGORIAS}
    _get(ESTOQUE, os.path.join(c, "estoque.xlsx"), binario=True)
    data_estoque, estoque = ler_estoque(os.path.join(c, "estoque.xlsx"))

    resolucoes = []
    for it in sorted(busca["resolucoes"], key=lambda x: _numero(x["titulo"])):
        n = _numero(it["titulo"])
        html = _get(it["url"], os.path.join(c, "resol%03d.html" % n))
        pag, det = extrair_pagina(html), detalhes_da_pagina(html)
        cons = pag["url_consolidado"]
        resolucoes.append({
            "numero": n, "titulo": it["titulo"], "data": pag["data"], "dou": pag["dou"],
            "ementa": pag["ementa"], "no_estoque": n in estoque,
            "situacao": situacao_resolucao(it["titulo"], det["revogada"], pag["ementa"], n in estoque),
            "revogada": det["revogada"],
            "alteradoras": [a["numero"] for a in pag["alteradoras"]],
            "consolidado": {k: v for k, v in cons.items() if k in ("docx", "pdf", "htm")},
            "consolidado_em_partes": len(cons.get("partes", [])),
            "ato": pag["url_ato"], "url_pagina": it["url"],
        })

    instrucoes = []
    for it in busca["instrucoes"]:
        n = _numero(it["titulo"])
        item = {"numero": n, "titulo": it["titulo"], "data": it["data"],
                "descricao": it["descricao"], "url_pagina": it["url"],
                "revogada": "(Revogada)" in it["titulo"]}
        if not item["revogada"]:
            item.update(detalhes_da_pagina(_get(it["url"], os.path.join(c, "inst%03d.html" % n))))
            item["situacao"] = ("so-alteradora" if SO_ALTERA.match(it["descricao"])
                                else ("revogada" if item["revogada"] else "vigente"))
        else:
            item["situacao"] = "revogada"
        instrucoes.append(item)

    pareceres = []
    for it in busca["pareceres-orientacao"]:
        n = _numero(it["titulo"])
        det = detalhes_da_pagina(_get(it["url"], os.path.join(c, "pare%03d.html" % n)))
        pareceres.append({"numero": n, "titulo": it["titulo"], "data": it["data"],
                          "descricao": it["descricao"], "url_pagina": it["url"], **det})

    oficios = [oficio(it) for it in busca["oficios-circulares"]]

    saida = {
        "lido_em": time.strftime("%Y-%m-%d"),
        "estoque_regulatorio": {"atualizado_em": data_estoque, "resolucoes": estoque},
        "resolucoes": resolucoes, "instrucoes": instrucoes,
        "pareceres": sorted(pareceres, key=lambda x: x["numero"]),
        "oficios_circulares": oficios,
    }
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
        f.write("\n")

    sit = Counter(r["situacao"] for r in resolucoes)
    print("Resoluções: %d %s" % (len(resolucoes), dict(sit)))
    print("Estoque Regulatório (%s): %d" % (data_estoque, len(estoque)))
    print("Instruções: %d %s" % (len(instrucoes), dict(Counter(i["situacao"] for i in instrucoes))))
    print("Pareceres: %d; Ofícios-Circulares: %d" % (len(pareceres), len(oficios)))
    print("-> %s" % args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
