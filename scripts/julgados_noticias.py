"""PAS julgados fora da listagem da CVM: notícias do resultado (gov.br/cvm) e extratos de sessão
de julgamento publicados no SEI (série 919).

A listagem de PAS (conteudo.cvm.gov.br) parou em 2025-05-27 e deixa de fora parte dos julgados de
2022 a 2025. As duas fontes que cobrem esses casos:
- a notícia do resultado, publicada no dia do julgamento ou no seguinte, com os PDFs das peças
  (relatório, voto, manifestações de voto) em /assuntos/noticias/anexos/AAAA/; o nome do PDF não
  segue padrão, então vale o href da notícia;
- o extrato da sessão de julgamento no SEI (HTML, com ementa, acusados, relator e decisão), que
  sai uma a duas semanas depois do julgamento.

Cache (dados/, fora do Git): `listagens/noticias/busca-NNNN.html` (páginas da busca por
"julgamento", 30 itens cada), `listagens/noticias/artigo-<md5[:8]>.html` (a notícia; o nome vem do
MD5 da URL) e `listagens/sei-extratos/*.html` (páginas da pesquisa do SEI, 20 linhas cada).
O inventário lê só o cache; `baixar` completa o que falta (1 requisição por segundo).

Uso:
  python3 scripts/julgados_noticias.py --baixar --de 01/01/2022 --ate 30/10/2026 --maximo 80
  python3 scripts/julgados_noticias.py          # resumo do que está no cache
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402

PASTA = os.path.join(jc.RAIZ, "dados", "fase-2d", "listagens", "noticias")
PASTA_SEI = os.path.join(jc.RAIZ, "dados", "fase-2d", "listagens", "sei-extratos")
URL_BUSCA = "https://www.gov.br/cvm/pt-br/assuntos/noticias"
URL_SEI = ("https://sei.cvm.gov.br/sei/publicacoes/controlador_publicacoes.php?"
           "acao=publicacao_pesquisar&acao_origem=publicacao_pesquisar&id_orgao_publicacao=0")
URL_EXTRATO = ("https://sei.cvm.gov.br/sei/publicacoes/controlador_publicacoes.php?"
               "acao=publicacao_visualizar&id_documento=%s&id_orgao_publicacao=0")
SERIE_EXTRATO = "919"
POR_PAGINA, POR_PAGINA_SEI = 30, 20

SUBTITULOS_RESULTADO = {"ATIVIDADE SANCIONADORA", "JULGAMENTO"}
# notícias sancionadoras que não são resultado de julgamento de PAS
_NAO_RESULTADO = re.compile(r"termo de compromisso|inicia julgamento|of[íi]cios? de alerta|"
                            r"relat[óo]rio de atividade|multas aplicadas|total de multas|"
                            r"stop orders?", re.I)
_RESUMO_SESSAO = re.compile(r"sess[ãa]o de julgamento", re.I)
_NUP = re.compile(r"19957\.\d{6}/\d{4}-\s*\d{2}")
_NUP_PDF = re.compile(r"19957[_.\-]?(\d{5,6})[_.\-/](\d{4})[_.\-]?(\d{2})(?!\d)")
_TAG = re.compile(r"<[^>]+>")


def _txt(html):
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html or ""))).strip()


def nome_artigo(url):
    return "artigo-%s.html" % hashlib.md5(url.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------- leitura


def ler_busca(html):
    """[{sub, url, titulo, data}] de uma página da busca de notícias."""
    out = []
    for li in re.findall(r"<li>\s*<div class=\"conteudo\">(.*?)</li>", html, re.S):
        a = re.search(r"<h2 class=\"titulo\">\s*<a href=\"([^\"]+)\">(.*?)</a>", li, re.S)
        if not a:
            continue
        sub = re.search(r"subtitulo-noticia\">(.*?)<", li, re.S)
        d = re.search(r"class=\"data\">\s*([\d/]+)", li)
        out.append({"sub": _txt(sub.group(1)) if sub else "", "url": unescape(a.group(1)).strip(),
                    "titulo": _txt(a.group(2)), "data": jc.data_br(d.group(1)) if d else None})
    return out


def proximo_inicio(html, inicio):
    """Deslocamento da próxima página da busca, ou None na última."""
    nums = [int(x) for x in re.findall(r"b_start:int=(\d+)", html)]
    return inicio + POR_PAGINA if any(n > inicio for n in nums) else None


def e_resultado(item):
    return item["sub"].upper() in SUBTITULOS_RESULTADO and not _NAO_RESULTADO.search(item["titulo"])


def _nups(texto):
    vistos = []
    for n in _NUP.findall(texto):
        n = re.sub(r"\s", "", n)
        if n not in vistos:
            vistos.append(n)
    return vistos


def ler_artigo(html):
    """{url, sub, titulo, data, nups, pecas: [(url do PDF, rótulo)]} da página da notícia.
    NUPs e PDFs só do corpo (o rodapé tem links de outras notícias)."""
    url = re.search(r"<meta property=\"og:url\" content=\"([^\"]+)\"", html)
    sub = re.search(r"class=\"nitfSubtitle\">(.*?)</p>", html, re.S)
    tit = re.search(r"class=\"documentFirstHeading\">(.*?)</h1>", html, re.S)
    pub = re.search(r"documentPublished\">.*?class=\"value\">\s*([\d/]+)", html, re.S)
    i = html.find('id="parent-fieldname-text"')
    corpo = html[i:] if i >= 0 else html
    j = corpo.find('id="viewlet-below-content"')
    corpo = corpo[:j] if j >= 0 else corpo
    pecas, vistos = [], set()
    for href, rot in re.findall(r"<a\b[^>]*?href=\"([^\"]+)\"[^>]*>(.*?)</a>", corpo, re.S):
        u = jc.absoluta(unescape(href).strip())
        if "/noticias/anexos/" not in u or not u.split("?")[0].lower().endswith(".pdf"):
            continue
        if u not in vistos:
            vistos.add(u)
            pecas.append((u, _txt(rot)))
    return {"url": unescape(url.group(1)) if url else "", "sub": _txt(sub.group(1)) if sub else "",
            "titulo": _txt(tit.group(1)) if tit else "",
            "data": jc.data_br(pub.group(1)) if pub else None,
            "nups": _nups(_txt(corpo)), "pecas": pecas}


def _chave_nup(nup):
    m = re.match(r"19957\.(\d+)/(\d{4})-(\d{2})", nup)
    return (int(m.group(1)), m.group(2), m.group(3)) if m else None


def pecas_por_nup(art):
    """{nup: [(url, rótulo)]}: o PDF vai para o NUP que está no nome do arquivo; sem NUP no
    nome, vai para todos os NUPs da notícia."""
    chaves = {_chave_nup(n): n for n in art["nups"]}
    out = {n: [] for n in art["nups"]}
    for u, rot in art["pecas"]:
        nome = os.path.basename(u.split("?")[0])
        achados = {chaves.get((int(a), b, c)) for a, b, c in _NUP_PDF.findall(nome)} - {None}
        for n in (achados or art["nups"]):
            out[n].append((u, rot))
    return out


def ler_busca_sei(html):
    """[{protocolo, id_documento, serie, data_pub, resumo, nups, url}] de uma página da pesquisa
    de publicações do SEI."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        ids = re.findall(r"id_documento=(\d+)", tr)
        if not ids:
            continue
        cel = [_txt(c).replace("\xa0", " ").strip()
               for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cel) < 8:
            continue
        resumo = cel[7]
        out.append({"protocolo": cel[1], "id_documento": ids[0], "serie": cel[2],
                    "data_pub": jc.data_br(cel[4]), "resumo": resumo, "nups": _nups(resumo),
                    "url": URL_EXTRATO % ids[0]})
    return out


def _ler(caminho):
    with open(caminho, "rb") as f:
        return jc.decodificar(f.read())


def carregar(pasta=PASTA, pasta_sei=PASTA_SEI):
    """{"noticias": [artigos de resultado], "faltam": [URLs de resultado sem artigo no cache],
    "extratos": [linhas do SEI, uma por documento]} do cache."""
    resultado, vistos = [], set()
    for p in sorted(glob.glob(os.path.join(pasta, "busca-*.html"))):
        for it in ler_busca(_ler(p)):
            if e_resultado(it) and it["url"] not in vistos:
                vistos.add(it["url"])
                resultado.append(it)
    noticias, faltam = [], []
    for it in resultado:
        p = os.path.join(pasta, nome_artigo(it["url"]))
        if not os.path.exists(p):
            faltam.append(it["url"])
            continue
        art = ler_artigo(_ler(p))
        art["url"] = art["url"] or it["url"]
        art["data"] = it["data"] or art["data"]  # a data da busca é a da publicação
        art["titulo"] = art["titulo"] or it["titulo"]
        noticias.append(art)
    extratos = {}
    for p in sorted(glob.glob(os.path.join(pasta_sei, "*.html"))):
        for r in ler_busca_sei(_ler(p)):
            if r["serie"].startswith("Extrato de Sess"):
                extratos[r["id_documento"]] = r
    return {"noticias": noticias, "faltam": faltam,
            "extratos": sorted(extratos.values(), key=lambda r: (r["data_pub"] or "",
                                                                 r["id_documento"]))}


def indice(fonte):
    """{nup: {nup, noticia, titulo, data, data_fonte, pecas, outras_noticias, extratos}}. As peças
    juntam as de todas as notícias do NUP (o resumo da sessão às vezes traz o relatório e a
    notícia do caso, o voto). Notícia principal: a com mais peças desse NUP; no empate, a que
    não é resumo de sessão e, depois, a mais antiga. Sem notícia, a data é a da primeira
    publicação do extrato (aproximada: o extrato sai depois do julgamento)."""
    por_nup = {}
    for art in fonte["noticias"]:
        for n, pecas in pecas_por_nup(art).items():
            por_nup.setdefault(n, []).append((art, pecas))
    out = {}
    for n, lista in por_nup.items():
        lista.sort(key=lambda x: (-len(x[1]), bool(_RESUMO_SESSAO.match(x[0]["titulo"])),
                                  x[0]["data"] or "9999"))
        art = lista[0][0]
        pecas, vistos = [], set()
        for _a, ps in lista:
            for u, rot in ps:
                if u not in vistos:
                    vistos.add(u)
                    pecas.append((u, rot))
        out[n] = {"nup": n, "noticia": art["url"], "titulo": art["titulo"], "data": art["data"],
                  "data_fonte": "noticia", "pecas": pecas,
                  "outras_noticias": [a["url"] for a, _ in lista[1:]], "extratos": []}
    for r in fonte["extratos"]:
        for n in r["nups"]:
            if n not in out:
                out[n] = {"nup": n, "noticia": "", "titulo": "", "data": r["data_pub"],
                          "data_fonte": "extrato", "pecas": [], "outras_noticias": [],
                          "extratos": []}
            out[n]["extratos"].append({k: r[k] for k in ("id_documento", "protocolo", "serie",
                                                         "data_pub", "resumo", "url")})
    return out


# ---------------------------------------------------------------- download


class Limite(Exception):
    pass


def _gravar(caminho, dados):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho + ".parcial", "wb") as f:
        f.write(dados)
    os.replace(caminho + ".parcial", caminho)


def baixar(pasta, pasta_sei, cliente, de, ate, maximo=80, refazer_busca=True, log=print):
    """Completa o cache: páginas da busca de notícias (de/ate em dd/mm/aaaa), artigos de
    resultado que faltam e páginas da pesquisa do SEI (série 919; `hdnInicio` é deslocamento em
    registros, passo 20). Para em `maximo` requisições. Com `refazer_busca` falso, página de busca
    que já está no cache não é pedida de novo."""
    import urllib.parse
    feitas = [0]

    def contar():
        if feitas[0] >= maximo:
            raise Limite("limite de %d requisições" % maximo)
        feitas[0] += 1

    try:
        inicio = 0
        while inicio is not None:
            p = os.path.join(pasta, "busca-%04d.html" % inicio)
            if refazer_busca or not os.path.exists(p):
                q = {"form.submitted": "1", "texto": "julgamento", "dt_inicio": de, "dt_fim": ate}
                if inicio:
                    q["b_start:int"] = str(inicio)
                contar()
                dados, _cab, _u = cliente.get(URL_BUSCA + "?" + urllib.parse.urlencode(q))
                _gravar(p, dados)
            html = _ler(p)
            inicio = proximo_inicio(html, inicio) if ler_busca(html) else None
        for u in carregar(pasta, pasta_sei)["faltam"]:
            contar()
            dados, _cab, _u = cliente.get(u)
            _gravar(os.path.join(pasta, nome_artigo(u)), dados)
        off = 0
        while True:
            p = os.path.join(pasta_sei, "o%d.html" % off)
            if refazer_busca or not os.path.exists(p):
                campos = {"hdnInfraTipoPagina": "1", "hdnInicio": str(off),
                          "hdnInfraPrefixoCookie": "CVM_SEI_", "selOrgao[]": "0",
                          "txtInteiroTeor": "", "txtResumo": "", "selUnidadeResponsavel": "",
                          "selSerie": SERIE_EXTRATO, "txtNumero": "", "txtProtocoloPesquisa": "",
                          "selVeiculoPublicacao": "", "txtDataDocumento": "",
                          "rdoDataPublicacao": "E", "txtDataInicio": de, "txtDataFim": ate}
                contar()
                dados, _cab, _u = cliente.post(URL_SEI, campos)
                _gravar(p, dados)
            if len(ler_busca_sei(_ler(p))) < POR_PAGINA_SEI:
                break
            off += POR_PAGINA_SEI
    except Limite as e:
        log("parou: %s" % e)
    return feitas[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baixar", action="store_true")
    ap.add_argument("--de", default="01/01/2022")
    ap.add_argument("--ate", default=None, help="dd/mm/aaaa; padrão: hoje")
    ap.add_argument("--maximo", type=int, default=80)
    ap.add_argument("--so-o-que-falta", action="store_true",
                    help="não pede de novo as páginas de busca que já estão no cache")
    a = ap.parse_args(argv)
    if a.baixar:
        h = jc.hoje_sp()
        ate = a.ate or "%s/%s/%s" % (h[8:], h[5:7], h[:4])
        n = baixar(PASTA, PASTA_SEI, jc.Cliente(), a.de, ate, a.maximo,
                   refazer_busca=not a.so_o_que_falta)
        print("requisições: %d" % n)
    fonte = carregar()
    idx = indice(fonte)
    print(json.dumps({"noticias_de_resultado": len(fonte["noticias"]),
                      "artigos_faltando": len(fonte["faltam"]),
                      "extratos": len(fonte["extratos"]), "nups": len(idx)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
