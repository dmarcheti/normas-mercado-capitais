#!/usr/bin/env python3
"""Piloto da Fase 2c: 10 normas das camadas 4 (CMN e BCB) e 5 (ANBIMA e B3) pelo texto_vigente.py,
sem LLM, saída fora do acervo (dados/fase-2c/piloto/).

- CMN e BCB: o texto compilado vem da API do BCB (campo Texto, HTML; cache do inventario_bcb.py),
  gravado como .htm e convertido como consolidado HTM (textutil -> DOCX -> Markdown; a redação
  antiga em <s> sai como tachado). A conferência independente NÃO usa o textutil, que já é o
  conversor: é o texto do HTML lido pelo html.parser da biblioteca padrão.
- ANBIMA e B3: PDF (PDFKit no texto, pypdf na conferência, como na Fase 2b).

O frontmatter ainda é o da SPEC v0.3.1 (orgao cvm); o validador vai acusar tipo e órgão, que são
os campos novos da SPEC v0.4.0 do plano. O piloto mede conversão, cobertura e tamanho.

Uso: python3 scripts/piloto_2c.py [--saida dados/fase-2c/piloto]
"""
import argparse
import html as htmllib
import json
import os
import re
import sys
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texto_vigente as tv  # noqa: E402

CACHE_BCB = "dados/fase-2c/bcb"
PILOTO_BCB = [("Resolução CMN", 4966), ("Resolução", 2907), ("Resolução CMN", 5118),
              ("Resolução BCB", None), ("Circular", None), ("Carta Circular", None)]


class _Texto(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes = []

    def handle_data(self, d):
        self.partes.append(d)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br", "div", "tr", "td", "th", "li"):
            self.partes.append("\n")


def texto_html(path):
    p = _Texto()
    with open(path, encoding="utf-8") as f:
        p.feed(f.read())
    return "".join(p.partes)


_conf_original = tv.texto_conferencia


def texto_conferencia(path, ext):
    return texto_html(path) if ext == "htm" else _conf_original(path, ext)


tv.texto_conferencia = texto_conferencia


def _bcb(tipo_bcb, numero):
    arq = os.path.join(CACHE_BCB, "%s-%05d.json" % (tipo_bcb.replace(" ", "_"), numero))
    with open(arq, encoding="utf-8") as f:
        return arq, json.load(f)["conteudo"][0]


def escolher_bcb(acervo):
    """Completa os None de PILOTO_BCB: a norma vigente do tipo com mais tabelas e tachado (formato difícil)."""
    escolhidos = []
    vig = [n for n in acervo["normas"] if n["situacao"] == "vigente" and n.get("formato", "").startswith("html")]
    for tipo_bcb, numero in PILOTO_BCB:
        if numero is None:
            cand = [n for n in vig if n["tipo_bcb"] == tipo_bcb]
            cand.sort(key=lambda n: (n.get("tabelas", 0) > 0, n.get("tachado", 0) > 0, n.get("palavras", 0)), reverse=True)
            numero = cand[0]["numero"]
        escolhidos.append((tipo_bcb, numero))
    return escolhidos


def item_bcb(tipo_bcb, numero, pasta_fontes):
    arq, c = _bcb(tipo_bcb, numero)
    tipo = {"Resolução": "resolucao-cmn", "Resolução CMN": "resolucao-cmn", "Resolução BCB": "resolucao-bcb",
            "Circular": "circular", "Carta Circular": "carta-circular"}[tipo_bcb]
    org = "cmn" if tipo == "resolucao-cmn" else "bcb"
    pasta = {"resolucao-cmn": "resolucoes", "resolucao-bcb": "resolucoes", "circular": "circulares",
             "carta-circular": "cartas-circulares"}[tipo]
    iid = "%s-%s-%d" % (org, {"resolucao-cmn": "res", "resolucao-bcb": "res", "circular": "circ",
                              "carta-circular": "cc"}[tipo], numero)
    htm = os.path.join(pasta_fontes, "%s.htm" % iid)
    with open(htm, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'></head><body>%s</body></html>" % (c.get("Texto") or ""))
    os.utime(htm, (os.path.getmtime(arq), os.path.getmtime(arq)))
    url = "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=%s&numero=%d" % (
        tipo_bcb.replace(" ", "%20"), numero)
    return {"id": iid, "tipo": tipo, "numero": numero, "data": (c.get("Data") or "")[:10],
            "dou": None, "ementa": re.sub(r"\s+", " ", c.get("Assunto") or "").strip(), "situacao": "vigente",
            "url_pagina": url, "fontes": {"consolidado": {"htm": url}}, "alteradoras": [],
            "vigente_ate_ato": "", "arquivo": "%s/%s/%04d.md" % (org, pasta, numero), "notas": []}


def item_pdf(org, doc, pasta_fontes, slug):
    dest = os.path.join(pasta_fontes, "%s-%s.pdf" % (org, slug))
    if not os.path.exists(dest):
        os.link(doc["cache"], dest)
    return {"id": "%s-%s" % (org, slug), "tipo": "autorregulacao", "numero": None,
            "data": doc.get("vigente_desde") or doc.get("data_nome") or "2026-10-29", "dou": None,
            "ementa": doc.get("titulo") or (doc.get("rotulos") or [doc["arquivo"]])[0],
            "situacao": "vigente", "url_pagina": doc["url"], "fontes": {"ato": {"pdf": doc["url"]}},
            "alteradoras": [], "vigente_ate_ato": "", "arquivo": "%s/%s.md" % (org, slug), "notas": []}


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", default="dados/fase-2c/piloto")
    args = ap.parse_args(argv[1:])
    fontes = os.path.join(args.saida, "fontes")
    os.makedirs(fontes, exist_ok=True)
    with open("fontes/acervo-bcb.json", encoding="utf-8") as f:
        bcb = json.load(f)
    itens = [item_bcb(t, n, fontes) for t, n in escolher_bcb(bcb)]
    with open("dados/fase-2c/anbima/acervo-com-cache.json", encoding="utf-8") as f:
        anb = {d["arquivo"]: d for d in json.load(f)["documentos"] if d.get("cache")}
    with open("dados/fase-2c/b3-com-cache.json", encoding="utf-8") as f:
        b3 = {d["arquivo"]: d for d in json.load(f)["documentos"] if d.get("cache")}
    escolha = [
        ("anbima", anb, "4. Codigo de Ofertas_08_07_2024 _publicar_ _1_.PDF", "codigo-ofertas-publicas"),
        ("anbima", anb, "Regras e Procedimentos_ AGRT_v_23.03.2026 - assinado.pdf", "rp-agrt"),
        ("b3", b3, "Regulamento de Emissores - 12.03.2026.pdf", "regulamento-emissores"),
        ("b3", b3, "Manual de Normas Colocacao CRA CRI Deb e Nota Comercial - 10112025 - Sem marca.pdf",
         "mn-colocacao-cra-cri-debenture-nota-comercial"),
    ]
    for org, base, arq, slug in escolha:
        itens.append(item_pdf(org, base[arq], fontes, slug))
    rel = tv.processar(itens, args.saida, fontes)
    with open(os.path.join(args.saida, "relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
    for r in rel:
        print("%-46s %-16s %-22s art=%-4s tab=%-3s cob=%-7s tach=%-6s bytes=%s" % (
            r["id"], r.get("fonte"), r.get("nivel_verificacao") or r.get("resultado"), r.get("artigos"),
            r.get("tabelas"), r.get("cobertura"), r.get("palavras_tachadas"), r.get("caracteres")))
    print(tv.resumo(rel))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
