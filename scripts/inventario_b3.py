#!/usr/bin/env python3
"""Inventário dos regulamentos e manuais da B3 (camada 5), só por script.

Percorre as páginas de categoria de b3.com.br/pt_br/regulacao/estrutura-normativa/regulamentos-e-manuais/
e as subpáginas "Acessar documentos" (estrutura-normativa/estrutura-normativa/<segmento>/), junta os
links de arquivo (.pdf, .doc, .docx), normaliza a URL (a B3 grava caminhos relativos com "../" a
mais; o arquivo está sempre em https://www.b3.com.br/data/files/...), separa a versão "com marcas"
(alterações destacadas) da "sem marcas" (texto limpo) e lê, por HEAD, o tamanho e a data do arquivo.
A data da versão vem do nome do arquivo quando ele a traz (ex.: "- 21092026", "_31.01.2022").

Uso (rede): python3 scripts/inventario_b3.py [--cache DIR] [--saida ARQUIVO]
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

RAIZ = "https://www.b3.com.br/pt_br/regulacao/estrutura-normativa/"
CATEGORIAS = RAIZ + "regulamentos-e-manuais/%s.htm"
NOMES = ("acesso", "cau-controle-de-acesso-unificado", "central-depositaria",
         "compensacao-liquidacao-e-gerenciamento-de-riscos", "distribuicao", "escrituracao",
         "garantias-bilaterais", "infraestrutura-para-financiamento", "listagem", "negociacao",
         "registro-e-liquidacao", "sro-operacoes-de-seguros", "tesouro-direto",
         "unidade-de-financiamento")
ARQ = re.compile(r"\.(pdf|docx?|zip)$", re.I)


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def _head(url):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, int(r.headers.get("Content-Length") or 0), r.headers.get("Last-Modified")
    except urllib.error.HTTPError as e:
        return e.code, 0, None


def url_arquivo(href):
    """URL absoluta do arquivo: tudo a partir de 'data/files/' vai para www.b3.com.br."""
    href = htmllib.unescape(href).strip()
    i = href.find("data/files/")
    if i >= 0:
        return "https://www.b3.com.br/" + href[i:]
    return urllib.parse.urljoin(RAIZ, href)


def data_do_nome(nome):
    nome = urllib.parse.unquote(nome)
    m = re.search(r"(\d{2})[.]?(\d{2})[.]?(20\d{2})(?!\d)", nome)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(1)) <= 31:
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
    m = re.search(r"(20\d{2})(\d{2})(\d{2})(?!\d)", nome)
    if m and 1 <= int(m.group(2)) <= 12:
        return "%s-%s-%s" % m.groups()
    return None


NORMATIVO = re.compile(r"regulamento|manual de normas|^mn |\bmpo\b|procedimentos operacionais|"
                       r"administra[çc][ãa]o de risco|gerenciamento de risco|manual do emissor|"
                       r"gloss[áa]rio|crit[ée]rios para cria|opera[çc][õo]es da c[âa]mara de c[âa]mbio", re.I)


def chave_versao(nome):
    """Nome do documento sem data, marcas e sufixos, para juntar as versões do mesmo documento."""
    n = urllib.parse.unquote(nome).rsplit(".", 1)[0].lower()
    n = re.sub(r"\.doc$|\.vfinal|\.final\d*|\.comparado", "", n)
    n = re.sub(r"[-_ ]*(com|sem)\s*marcas?", "", n)
    n = re.sub(r"\d{2}[.]?\d{2}[.]?20\d{2}|20\d{6}|_?sancoes 20\d{2}_?|\s\d$", "", n)
    return re.sub(r"[\s_.-]+", " ", n).strip()


# Mesma norma com nomes diferentes (conferido pela data no texto, 2026-10-29): arquivo -> motivo
SUBSTITUIDOS = {
    "Regulamento Central Depositaria RV B3 - 20230130.doc.pdf":
        "versão de 30/01/2023; vigente: Regulamento da CSD de RV B3.pdf (versão de 23/02/2026)",
    "Regulamento_Tesouro_Direto.pdf":
        "versão de julho de 2017; vigente: Regulamento TD Publicado no Site .11.07.2023.pdf",
}


def perimetro(d):
    """(entra?, motivo) do documento na camada 5."""
    if d["arquivo"] in SUBSTITUIDOS:
        return False, SUBSTITUIDOS[d["arquivo"]]
    txt = " ".join(d["rotulos"]) + " " + d["arquivo"]
    if d["marcas"] == "com":
        return False, "versão com marcas (há a sem marcas)"
    if any("manuais-de-operacoes" in p for p in d["paginas"]) and not NORMATIVO.search(d["arquivo"]):
        return False, "manual de operação de sistema"
    if re.search(r"manual de opera[çc][õo]es -|usu[áa]rio|guia de cadastro|plataforma integrada|"
                 r"especifica[çc][ãa]o t[ée]cnica|portal do cau|layout", txt, re.I):
        return False, "manual de sistema, guia ou especificação técnica"
    if d["formato"] not in ("pdf", "doc", "docx"):
        return False, "formato %s" % d["formato"]
    if NORMATIVO.search(txt):
        return True, "regulamento, manual de normas ou procedimento"
    return False, "não normativo"


def links(html):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    for href, rotulo in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        rot = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", rotulo))).strip()
        yield href, rot


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", default="fontes/acervo-b3.json")
    args = ap.parse_args(argv[1:])
    paginas = {CATEGORIAS % n: n for n in NOMES}
    vistos, docs = set(), {}
    fila = list(paginas)
    while fila:
        url = fila.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        try:
            h = _get(url)
        except Exception as e:  # noqa: BLE001
            print("falha %s: %s" % (url, e))
            continue
        cat = paginas.get(url)
        for href, rot in links(h):
            if "estrutura-normativa/estrutura-normativa/" in href and not ARQ.search(href):
                sub = urllib.parse.urljoin(url, href)
                sub = RAIZ + "estrutura-normativa/" + sub.split("estrutura-normativa/estrutura-normativa/", 1)[1]
                if sub not in vistos:
                    paginas.setdefault(sub, cat)
                    fila.append(sub)
                continue
            if not ARQ.search(href.split("?", 1)[0]):
                continue
            u = url_arquivo(href)
            nome = urllib.parse.unquote(u.rsplit("/", 1)[-1])
            d = docs.setdefault(u, {"url": u, "arquivo": nome, "rotulos": [], "paginas": []})
            if rot and rot not in d["rotulos"]:
                d["rotulos"].append(rot)
            if url not in d["paginas"]:
                d["paginas"].append(url)
        time.sleep(0.5)
    for d in docs.values():
        st, tam, lm = _head(d["url"])
        txt = " ".join(d["rotulos"]) + " " + d["arquivo"]
        d.update({
            "http": st, "bytes": tam, "last_modified": lm,
            "marcas": "com" if re.search(r"com\s*marca", txt, re.I) else (
                "sem" if re.search(r"sem\s*marca", txt, re.I) else "n/a"),
            "data_nome": data_do_nome(d["arquivo"]),
            "formato": d["arquivo"].rsplit(".", 1)[-1].lower(),
            "categoria": paginas.get(d["paginas"][0]),
        })
        time.sleep(0.3)
    # perímetro e versão vigente: entre as versões do mesmo documento, a de data mais recente no nome
    for d in docs.values():
        d["entra"], d["motivo"] = perimetro(d)
        d["chave"] = chave_versao(d["arquivo"])
    grupos = {}
    for d in docs.values():
        if d["entra"]:
            grupos.setdefault(d["chave"], []).append(d)
    for g in grupos.values():
        g.sort(key=lambda d: (d["data_nome"] or "0000", d["last_modified"] or ""), reverse=True)
        for d in g[1:]:
            d["entra"], d["motivo"] = False, "versão anterior ou cópia de %s" % g[0]["arquivo"]
    out = {"fonte": RAIZ + "regulamentos-e-manuais/", "lido_em": time.strftime("%Y-%m-%d"),
           "paginas": sorted(vistos), "documentos": sorted(docs.values(), key=lambda d: (d["categoria"] or "", d["arquivo"]))}
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    entram = [d for d in out["documentos"] if d["entra"]]
    print("páginas: %d, documentos: %d, no perímetro: %d" % (len(vistos), len(docs), len(entram)))
    for d in entram:
        print("%-34s %s | %s" % (d["categoria"], d["data_nome"] or "-", d["arquivo"][:90]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
