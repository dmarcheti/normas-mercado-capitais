#!/usr/bin/env python3
"""Inventário do perímetro da v1.0 no site da CVM (camadas 1 e 2), só por script.

Lê a busca do site (todas as Resoluções, Instruções, Pareceres de Orientação e
Ofícios-Circulares numa página cada), a planilha do Estoque Regulatório da CVM (com o
grupo temático de cada Resolução), a página de cada Resolução, de cada Instrução não
revogada, de cada Parecer e de cada Ofício-Circular (o link do PDF do ofício vem da
página; o nome do PDF nem sempre é o da página). Grava fontes/acervo.json e imprime o
resumo, com as falhas de rede.

Situação de cada Resolução (campo `situacao`):
- revogada: "(Revogada)" no título da busca ou parágrafo "REVOGADA pela..." na página;
- vigente: está no Estoque Regulatório e não está revogada;
- so-alteradora: fora do Estoque, não revogada, ementa só altera ou revoga outros atos;
- verificar: o resto (ex.: 26, prorrogação de prazos de 2021, e 249, editada depois da
  data do Estoque). Quem decide incluir a 249 é scripts/texto_vigente.py.

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


RES_ESTOQUE = re.compile(r"Resolução CVM\s*(?:nº\s*)?(\d+)")


def ler_estoque(path):
    """(data de atualização AAAA-MM-DD, [números das Resoluções do Estoque],
    {número: grupo temático}).

    A planilha tem as colunas "Grupo temático" e "Norma editada"; o grupo vem só na
    primeira linha de cada bloco (células mescladas) e vale para as seguintes, até o próximo.
    """
    z = zipfile.ZipFile(path)
    ss = ["".join(t.text or "" for t in si.iter(XL + "t"))
          for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(XL + "si")]
    textos, linhas = [], []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(XL + "row"):
        celulas = []
        for c in row.iter(XL + "c"):
            v = c.find(XL + "v")
            if v is not None:
                t = ss[int(v.text)] if c.get("t") == "s" else v.text
                textos.append(t)
                celulas.append(_espaco(t or ""))
        linhas.append([t for t in celulas if t])
    tudo = "\n".join(textos)
    m = re.search(r"atualizado em (\d{2})/(\d{2})/(\d{4})", tudo)
    data = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None
    nums = sorted({int(n) for n in RES_ESTOQUE.findall(tudo)})
    grupos, grupo, tabela = {}, None, False
    for celulas in linhas:
        if celulas and celulas[0].lower().startswith("grupo tem"):
            tabela = True
            continue
        if not tabela or not celulas:
            continue
        normas = [c for c in celulas if RES_ESTOQUE.search(c)]
        rotulos = [c for c in celulas if not RES_ESTOQUE.search(c)]
        if rotulos:
            grupo = rotulos[0]
        for c in normas:
            for n in RES_ESTOQUE.findall(c):
                if grupo:
                    grupos.setdefault(int(n), grupo)
    return data, nums, grupos


NOTA_DOU = re.compile(r"\(\s*(?:Publicad|Retificad|Republicad)")


DIV_DEPOIS_DA_DATA = re.compile(r"</b>\s*</p>\s*<div>(.*?)</div>", re.S)


def _ementa(p, html=""):
    """Primeiro parágrafo com texto depois da data, sem as notas "(Publicada no DOU...)".

    Algumas páginas (ex.: Resolução CVM 122) trazem a ementa num <div> logo depois da
    data, sem <p>; nesse caso ela vem desse <div>.
    """
    for par in p.paragrafos:
        t = _espaco(par["texto"].replace("\n", " "))
        if not t or par["texto"].strip() == p.negrito_data.strip():
            continue
        return _espaco(NOTA_DOU.split(t)[0])
    m = DIV_DEPOIS_DA_DATA.search(html)
    if m:
        t = _espaco(htmllib.unescape(re.sub(r"<[^>]+>", " ", m.group(1))))
        return _espaco(NOTA_DOU.split(t)[0])
    return ""


def detalhes_da_pagina(html):
    """Dados comuns a qualquer ato da CVM: data, DOU, ementa, revogação, alterações e arquivos."""
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
    div = DIV_DEPOIS_DA_DATA.search(html)
    if div:
        tudo += "\n" + htmllib.unescape(re.sub(r"<[^>]+>", " ", div.group(1)))
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
        "ementa": _ementa(p, html),
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


def _pasta_slug(url):
    """("sse1", "oc-sse-0326") da URL da página do ofício."""
    partes = url.split("/legislacao/oficios-circulares/", 1)[1].split("/")
    return partes[0], partes[-1].rsplit(".", 1)[0]


def normalizar_slug(slug):
    """Slug da CVM em kebab-case (SPEC v0.3.0: `[a-z0-9]+(-[a-z0-9]+)*`).

    CamelCase ganha hífen antes de cada maiúscula que segue minúscula ou dígito; depois tudo
    em minúsculas, `_`, espaço e qualquer outro sinal viram hífen, e hífens repetidos colapsam.
    Ex.: "OficioCircularCVMSSE0122" -> "oficio-circular-cvmsse0122"; "oc_snc_sep_0124" ->
    "oc-snc-sep-0124".
    """
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", slug).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _pasta_no_slug(oficio, slug):
    """True se toda sigla da pasta (sem dígitos: `sse1` -> `sse`) aparece no slug."""
    siglas = [re.sub(r"\d+", "", x) for x in normalizar_slug(oficio.get("superintendencia") or "").split("-")]
    return all(x in slug.split("-") for x in siglas if x)


def atribuir_slugs(oficios):
    """Grava `slug` (nome do arquivo, único entre os ofícios) e `id` (`cvm-` + slug) em cada
    ofício, a partir de `slug_cvm`. Altera a lista no lugar e a devolve, na mesma ordem.

    Slug normalizado repetido (mesmo slug em pastas diferentes, ou só caixa e separador
    diferentes): o ofício mais antigo fica com o slug base; os seguintes ganham
    `-<pasta normalizada>` e, se ainda colidir, `-2`, `-3`... Antes da data vale a pasta: fica
    com o slug base o ofício cuja pasta tem só siglas presentes no slug (`sin/oc-sin-0623` antes
    de `sse1/oc-sin-0623`, que é o SSE 06/23 com nome trocado; `sse-sin-snc/` antes de
    `old-sse-sin-snc/`). Empate de data: pela pasta.
    """
    base = {id(o): normalizar_slug(o.get("slug_cvm") or o["slug"]) for o in oficios}
    usados = set(base.values())  # nenhum sufixo pode tomar o slug base de outro ofício
    grupos = {}
    for o in oficios:
        grupos.setdefault(base[id(o)], []).append(o)
    for b, grupo in grupos.items():
        grupo.sort(key=lambda o: (not _pasta_no_slug(o, b), o.get("data") or "9999",
                                  o.get("superintendencia") or "", o.get("slug_cvm") or ""))
        grupo[0]["slug"] = b
        for o in grupo[1:]:
            cand = "%s-%s" % (b, normalizar_slug(o.get("superintendencia") or "sem-pasta"))
            n, slug = 2, cand
            while slug in usados:
                slug, n = "%s-%d" % (cand, n), n + 1
            usados.add(slug)
            o["slug"] = slug
    for o in oficios:
        o["id"] = "cvm-" + o["slug"]
    return oficios


def palpite_pdf(url):
    """URL do PDF deduzida do slug da página (reserva, quando a página não traz o link)."""
    pasta, slug = _pasta_slug(url)
    return "%s/export/sites/cvm/legislacao/oficios-circulares/%s/anexos/%s.pdf" % (BASE, pasta, slug)


CITA = re.compile(r"(Instrução|Resolução) CVM n?[ºo°]?\s*(\d+)")


def citadas(texto):
    """["Instrução 555", "Resolução 175"] citadas no texto, sem repetição, na ordem."""
    return list(dict.fromkeys("%s %s" % (t, n) for t, n in CITA.findall(texto or "")))


def oficio(item, pagina=None):
    """Superintendência, slug e PDF de um Ofício-Circular da busca.

    `slug` sai normalizado, mas só fica único depois de `atribuir_slugs` sobre a lista toda.

    `pagina`: HTML da página do ofício. O PDF vem do link dentro do artigo da página
    (o nome do PDF nem sempre é o slug); sem página ou sem link, fica o palpite pelo slug.
    """
    pasta, slug = _pasta_slug(item["url"])
    palpite = palpite_pdf(item["url"])
    det = pdf_do_oficio(pagina) if pagina else {"url_pdf": None, "ementa": ""}
    ementa = det["ementa"] or item["descricao"]
    return {
        "titulo": item["titulo"], "data": item["data"], "superintendencia": pasta,
        "slug": normalizar_slug(slug), "slug_cvm": slug, "id": "cvm-" + normalizar_slug(slug),
        "descricao": item["descricao"], "ementa": ementa,
        "url_pagina": item["url"],
        "url_pdf": det["url_pdf"] or palpite,
        "url_pdf_origem": "pagina" if det["url_pdf"] else "palpite",
        "cita": citadas(ementa),
    }


def pdf_do_oficio(html):
    """{url_pdf, ementa} da página de um Ofício-Circular: o primeiro PDF do artigo cujo
    texto é o título (senão, o primeiro PDF do artigo) e o parágrafo de descrição."""
    p = _Pagina()
    p.feed(html)
    pdfs = [(href, txt) for href, txt in p.ancoras if href.lower().split("?")[0].endswith(".pdf")]
    titulo = _espaco(p.titulo).lower()
    escolhido = next((h for h, t in pdfs if t and t.lower() == titulo), None) or (
        pdfs[0][0] if pdfs else None)
    return {"url_pdf": urljoin(BASE, escolhido) if escolhido else None, "ementa": _ementa(p, html)}


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


def resolucao_do_acervo(n, titulo, url, html, estoque):
    """Entrada de uma resolução no acervo.json, a partir da página dela no site da CVM.

    Usada aqui e pelo atualizar.py (classe A), para a entrada nova ter o mesmo formato."""
    pag, det = extrair_pagina(html), detalhes_da_pagina(html)
    cons = pag["url_consolidado"]
    ementa = pag["ementa"] or det["ementa"]  # Res. 122: ementa num <div>, sem <p>
    return {
        "numero": n, "titulo": titulo, "data": pag["data"], "dou": pag["dou"] or det["dou"],
        "ementa": ementa, "no_estoque": n in estoque,
        "situacao": situacao_resolucao(titulo, det["revogada"], ementa, n in estoque),
        "revogada": det["revogada"],
        "alteradoras": [a["numero"] for a in pag["alteradoras"]],
        "consolidado": {k: v for k, v in cons.items() if k in ("docx", "pdf", "htm")},
        "consolidado_em_partes": len(cons.get("partes", [])),
        "ato": pag["url_ato"], "url_pagina": url,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache", default="dados/paginas-cvm")
    ap.add_argument("--saida", default="fontes/acervo.json")
    args = ap.parse_args(argv)
    c = args.cache

    busca = {cat: itens_da_busca(_get(BUSCA % cat, os.path.join(c, "busca-%s.html" % cat)))
             for cat in CATEGORIAS}
    _get(ESTOQUE, os.path.join(c, "estoque.xlsx"), binario=True)
    data_estoque, estoque, grupos = ler_estoque(os.path.join(c, "estoque.xlsx"))

    resolucoes = []
    for it in sorted(busca["resolucoes"], key=lambda x: _numero(x["titulo"])):
        n = _numero(it["titulo"])
        html = _get(it["url"], os.path.join(c, "resol%03d.html" % n))
        resolucoes.append(resolucao_do_acervo(n, it["titulo"], it["url"], html, estoque))

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

    oficios, falhas = [], []
    for it in busca["oficios-circulares"]:
        cache = os.path.join(c, "oc", "%s-%s.html" % _pasta_slug(it["url"]))
        try:
            pagina = _get(it["url"], cache)
        except Exception as e:  # noqa: BLE001 — rede: fica o palpite e a falha no resumo
            falhas.append("%s: %s" % (it["url"], str(e)[:120]))
            pagina = None
        oficios.append(oficio(it, pagina))
    atribuir_slugs(oficios)

    saida = {
        "lido_em": time.strftime("%Y-%m-%d"),
        "estoque_regulatorio": {"atualizado_em": data_estoque, "resolucoes": estoque,
                                "grupos": {str(n): g for n, g in sorted(grupos.items())}},
        "resolucoes": resolucoes, "instrucoes": instrucoes,
        "pareceres": sorted(pareceres, key=lambda x: x["numero"]),
        "oficios_circulares": oficios,
    }
    tmp = args.saida + ".tmp"  # troca atômica: outro script pode estar lendo o acervo
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, args.saida)

    sit = Counter(r["situacao"] for r in resolucoes)
    print("Resoluções: %d %s" % (len(resolucoes), dict(sit)))
    print("Estoque Regulatório (%s): %d" % (data_estoque, len(estoque)))
    print("Instruções: %d %s" % (len(instrucoes), dict(Counter(i["situacao"] for i in instrucoes))))
    print("Pareceres: %d; Ofícios-Circulares: %d" % (len(pareceres), len(oficios)))
    palpites = [o for o in oficios if o["url_pdf_origem"] == "palpite"]
    diferentes = [o for o in oficios if o["url_pdf_origem"] == "pagina" and
                  o["url_pdf"] != palpite_pdf(o["url_pagina"])]
    print("Ofícios: PDF da página %d (diferente do palpite: %d); palpite %d; falhas de rede %d"
          % (len(oficios) - len(palpites), len(diferentes), len(palpites), len(falhas)))
    for f in falhas:
        print("  falha: %s" % f)
    mudaram = [o for o in oficios if o["slug"] != o["slug_cvm"]]
    print("Ofícios com slug diferente do da CVM: %d" % len(mudaram))
    for o in mudaram:
        print("  %s/%s -> %s" % (o["superintendencia"], o["slug_cvm"], o["slug"]))
    print("-> %s" % args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
