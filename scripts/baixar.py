#!/usr/bin/env python3
"""Baixa as fontes da Fase 2 para dados/ (cache; nada é baixado duas vezes).

Sem argumentos livres: as URLs saem de fontes/inventario.json e fontes/leis.json.
Só fala com os domínios de DOMINIOS, uma requisição a cada PAUSA segundos, e
não altera nenhum arquivo do repositório fora de dados/.

O que baixa:
- consolidado DOCX das 8 resoluções -> dados/resolNNNconsolid.docx
- DOCX/HTM de cada ato no site da CVM (reserva) -> dados/fontes/cvm-NNNN.{docx,htm}
- lista do ctresb/leis (slug do in.gov.br) -> dados/fontes/ctresb.json
- busca no in.gov.br para o ato sem slug e para as retificações -> dados/fontes/busca-NNNN.html
- página do DOU de cada original e alteradora -> dados/fontes/dou-NNNN.html
- retificações achadas na busca -> dados/fontes/dou-NNNN-retificacao-<slug>.html
- compilado do Planalto de cada lei -> dados/fontes/lei-NNNNN.html (decreto-NNNNN.html,
  lcp-NNN.html), tentando as URLs de `planalto` na ordem (compilado primeiro, original de reserva)
No fim grava dados/fontes/relatorio.json (o que deu certo, de onde, e o que falhou).

Uso: python3 scripts/baixar.py [--leis]
--leis: só as normas de fontes/leis.json; as entradas já baixadas (ok no relatório e
arquivo no cache) ficam como estão, e o resto do relatório é preservado.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario import USER_AGENT, carregar_inventario  # noqa: E402
from teste_lei import nome_do_arquivo  # noqa: E402

RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DADOS = os.path.join(RAIZ, "dados")
FONTES = os.path.join(DADOS, "fontes")
DOMINIOS = ("www.in.gov.br", "www.planalto.gov.br", "conteudo.cvm.gov.br", "api.github.com")
PAUSA = 2.0
DOU = "https://www.in.gov.br/web/dou/-/"
BUSCA = "https://www.in.gov.br/consulta/-/buscar/dou?q=%s&s=todos&exactDate=all&sortType=0"
CTRESB = "https://api.github.com/repos/ctresb/leis/contents/reguladores/cvm/resolucoes/%d"
PLANALTO = "https://www.planalto.gov.br/"
COM_RETIFICACAO = (21, 60, 160, 175)  # fontes/INVENTARIO.md, "Pontos de atenção"

_ultima = [0.0]


def permitido(url):
    p = urllib.parse.urlparse(url)
    return p.scheme == "https" and p.hostname in DOMINIOS


def baixar(url, destino):
    """Baixa url para destino, se ainda não existir. Devolve o caminho."""
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return destino
    if not permitido(url):
        raise ValueError("domínio fora da lista: %s" % url)
    espera = PAUSA - (time.time() - _ultima[0])
    if espera > 0:
        time.sleep(espera)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            corpo = r.read()
    finally:
        _ultima[0] = time.time()
    if not corpo:
        raise ValueError("resposta vazia: %s" % url)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(corpo)
    return destino


def slug_ctresb(nomes, numero):
    """Slug do in.gov.br do ato `numero`, a partir dos nomes de arquivo do ctresb/leis."""
    pre = re.compile(r"^resolucao-(?:cvm-)?n-%d-de-" % numero)
    for n in nomes:
        if pre.match(n):
            return n[:-3] if n.endswith(".md") else n
    return None


def slugs_da_busca(html, numero):
    """(slug do ato, [slugs de retificação]) achados na página de busca do in.gov.br."""
    slugs = list(dict.fromkeys(re.findall(r'"urlTitle"\s*:\s*"([^"]+)"', html)))
    pre = re.compile(r"^resolucao-(?:cvm-)?n-%d-de-" % numero)
    ato = next((s for s in slugs if pre.match(s)), None)
    retif = [s for s in slugs if s.startswith("retificacao")]
    return ato, retif


def _atos(inv):
    """{numero: dou} das 8 resoluções e de todas as alteradoras."""
    atos = {}
    for norma in inv:
        atos[norma["numero"]] = norma["dou"]
        for a in norma["alteradoras"]:
            atos[a["numero"]] = a["dou"]
    return dict(sorted(atos.items()))


def _tenta(rel, chave, url, destino):
    try:
        baixar(url, destino)
        rel[chave] = {"ok": True, "url": url, "arquivo": os.path.relpath(destino, RAIZ)}
        return True
    except Exception as e:  # noqa: BLE001 — registra e segue
        rel[chave] = {"ok": False, "url": url, "erro": str(e)[:200]}
        return False


def baixar_leis(leis, rel, so_novas=False):
    """Página do Planalto de cada norma de `leis` em dados/fontes/<nome>.html (lei-NNNNN,
    decreto-NNNNN, lcp-NNN); a primeira URL de `planalto` que responder vale.
    `so_novas`: pula a norma que já tem download ok em `rel` e o arquivo no cache."""
    for lei in leis:
        nome = nome_do_arquivo(lei["id"])
        if nome is None:
            rel[lei["id"]] = {"ok": False, "erro": "id fora de lei-N, decreto-N, lcp-N"}
            continue
        destino = os.path.join(FONTES, nome + ".html")
        if so_novas and rel.get(lei["id"], {}).get("ok") and os.path.exists(destino):
            continue
        for caminho in lei["planalto"]:
            if _tenta(rel, lei["id"], PLANALTO + caminho, destino):
                break


def _gravar_relatorio(rel):
    with open(os.path.join(FONTES, "relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    so_leis = argv[1:] == ["--leis"]
    if len(argv) != 1 and not so_leis:
        print(__doc__)
        return 2
    with open(os.path.join(RAIZ, "fontes", "leis.json"), encoding="utf-8") as f:
        leis = json.load(f)
    if so_leis:
        caminho = os.path.join(FONTES, "relatorio.json")
        rel = {}
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                rel = json.load(f)
        baixar_leis(leis, rel, so_novas=True)
        _gravar_relatorio(rel)
        falhas = sorted(l["id"] for l in leis if not rel.get(l["id"], {}).get("ok"))
        print("baixar --leis: %d ok, %d falha(s)" % (len(leis) - len(falhas), len(falhas)))
        for k in falhas:
            print("  falhou %s: %s" % (k, rel[k].get("erro")))
        return 1 if falhas else 0
    inv = carregar_inventario(os.path.join(RAIZ, "fontes", "inventario.json"))
    atos = _atos(inv)
    rel = {}

    for norma in inv:
        n = norma["numero"]
        _tenta(rel, "consolidado-%d" % n, norma["url_consolidado"]["docx"],
               os.path.join(DADOS, "resol%03dconsolid.docx" % n))
        for a in norma["alteradoras"]:
            for ext, url in a.get("url_ato", {}).items():
                if ext in ("docx", "htm"):
                    _tenta(rel, "cvm-%d-%s" % (a["numero"], ext), url,
                           os.path.join(FONTES, "cvm-%04d.%s" % (a["numero"], ext)))

    nomes = []
    for ano in sorted({int(d[:4]) for d in atos.values()}):
        arq = os.path.join(FONTES, "ctresb-%d.json" % ano)
        if _tenta(rel, "ctresb-%d" % ano, CTRESB % ano, arq):
            with open(arq, encoding="utf-8") as f:
                nomes += [x["name"] for x in json.load(f)]

    for n in atos:
        slug = slug_ctresb(nomes, n)
        origem = "ctresb" if slug else None
        retif = []
        if not slug or n in COM_RETIFICACAO:
            q = urllib.parse.quote_plus('"Resolução CVM nº %d"' % n)
            busca = os.path.join(FONTES, "busca-%04d.html" % n)
            if _tenta(rel, "busca-%d" % n, BUSCA % q, busca):
                with open(busca, encoding="utf-8", errors="replace") as f:
                    achado, retif = slugs_da_busca(f.read(), n)
                if not slug and achado:
                    slug, origem = achado, "busca"
        if not slug:
            rel["dou-%d" % n] = {"ok": False, "erro": "slug não achado (ctresb nem busca)"}
            continue
        if _tenta(rel, "dou-%d" % n, DOU + slug, os.path.join(FONTES, "dou-%04d.html" % n)):
            rel["dou-%d" % n].update(slug=slug, origem=origem, dou=atos[n])
        for s in retif[:5]:
            _tenta(rel, "retif-%d-%s" % (n, s), DOU + s,
                   os.path.join(FONTES, "dou-%04d-retificacao-%s.html" % (n, s)))

    baixar_leis(leis, rel)

    _gravar_relatorio(rel)
    falhas = sorted(k for k, v in rel.items() if not v["ok"])
    print("baixar: %d ok, %d falha(s)" % (len(rel) - len(falhas), len(falhas)))
    for k in falhas:
        print("  falhou %s: %s" % (k, rel[k].get("erro")))
    print("relatório: dados/fontes/relatorio.json")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
