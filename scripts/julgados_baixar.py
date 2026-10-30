"""Baixa as fontes dos julgados do inventário (página, PDFs, anexos e termos) para o cache local.

Cache: dados/fase-2d/cache/<tipo>/<ano>/<id>/, com um registro.json por julgado que guarda,
para cada arquivo, papel, rótulo, URL, nome local, tamanho, sha256, data e content-type.
No máximo 1 requisição por segundo. Retomável: arquivo já no cache é reaproveitado se um HEAD
confirmar que a URL ainda responde com o mesmo tamanho (sem Content-Length, vale o cache).

Uso:
  python3 scripts/julgados_baixar.py --ids cvm-pas-rj2015-1234,cvm-col-20251202-d3228
  python3 scripts/julgados_baixar.py --onda 1 --tipo pas --limite 20
"""
import argparse
import hashlib
import json
import os
import re
import sys
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402

CACHE = os.path.join(jc.RAIZ, "dados", "fase-2d", "cache")
INVENTARIO = os.path.join(jc.RAIZ, "dados", "fase-2d", "julgados-inventario.json")

_ARTIGO = re.compile(r"<article\b[^>]*contentTextoGeral[^>]*>(.*?)</article>", re.S | re.I)
_LINK = re.compile(r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_EXT = re.compile(r"\.(pdf|docx?|xlsx?|zip|rtf|html?)$", re.I)


def pasta_do_item(item, raiz=CACHE):
    return os.path.join(raiz, item["tipo"], str(jc.ano_do_item(item) or "sem-ano"), item["id"])


def links_da_pagina(html):
    """[(url absoluta, rótulo)] dos documentos ligados no corpo da página da CVM: PDFs, arquivos
    em /anexos/ e documentos do SEI. Uma entrada por URL, com o rótulo mais longo."""
    m = _ARTIGO.search(html)
    corpo = m.group(1) if m else html
    vistos = {}
    for href, rot in _LINK.findall(corpo):
        url = jc.reparar_url(unescape(href).strip())
        caminho = url.split("?")[0].split("#")[0]
        doc = (caminho.lower().endswith(".pdf") or ("/anexos/" in caminho and _EXT.search(caminho))
               or "sei.cvm.gov.br" in url and "publicacoes" in url)
        if not doc:
            continue
        url = jc.absoluta(url)
        rot = re.sub(r"\s+", " ", unescape(_TAG.sub(" ", rot))).strip()
        if url not in vistos or len(rot) > len(vistos[url]):
            vistos[url] = rot
    return list(vistos.items())


def _nome_local(papel, n, url, content_type=""):
    base = os.path.basename(url.split("?")[0].split("#")[0]) or "documento"
    ext = os.path.splitext(base)[1].lower()
    if not ext or len(ext) > 6 or "sei.cvm.gov.br" in url:
        ext = ".pdf" if "pdf" in (content_type or "") else ".html"
    return "%02d-%s%s" % (n, papel, ext)


def _sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_registro(pasta):
    p = os.path.join(pasta, "registro.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _gravar_registro(pasta, reg):
    os.makedirs(pasta, exist_ok=True)
    tmp = os.path.join(pasta, "registro.json.parcial")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, os.path.join(pasta, "registro.json"))


def _cache_valido(cliente, pasta, anterior, verificar=True):
    """True se o arquivo do registro anterior existe, confere com o sha256 e (com `verificar`)
    um HEAD na URL devolve o mesmo tamanho ou não informa tamanho."""
    if not anterior:
        return False, ""
    caminho = os.path.join(pasta, anterior["arquivo"])
    if not os.path.exists(caminho) or os.path.getsize(caminho) != anterior["tamanho"]:
        return False, ""
    if _sha256(caminho) != anterior["sha256"]:
        return False, "sha256 do cache não confere"
    if not verificar:
        return True, ""
    try:
        cab = cliente.head(anterior["url"])
    except Exception as e:  # rede fora: fica o cache, com aviso
        return True, "HEAD falhou (%s); cache mantido" % type(e).__name__
    tam = cab.get("content-length")
    if tam and tam.isdigit() and int(tam) != anterior["tamanho"]:
        return False, "tamanho mudou na origem (%s -> %s)" % (anterior["tamanho"], tam)
    return True, ""


def _baixar_arquivo(cliente, pasta, papel, rotulo, url, n, anterior, verificar, avisos):
    ok, aviso = _cache_valido(cliente, pasta, anterior, verificar)
    if aviso:
        avisos.append("%s: %s" % (url, aviso))
    if ok:
        return dict(anterior, papel=papel, rotulo=rotulo), False
    dados, cab, final = cliente.get(url)
    ct = cab.get("content-type", "")
    nome = _nome_local(papel, n, url, ct)
    os.makedirs(pasta, exist_ok=True)
    tmp = os.path.join(pasta, nome + ".parcial")
    with open(tmp, "wb") as f:
        f.write(dados)
    os.replace(tmp, os.path.join(pasta, nome))
    return {"papel": papel, "rotulo": rotulo, "url": url, "url_final": final, "arquivo": nome,
            "tamanho": len(dados), "sha256": hashlib.sha256(dados).hexdigest(),
            "baixado_em": jc.hoje_sp(), "content_type": ct}, True


def _papel_principal(item):
    u = item["url"].split("?")[0].lower()
    if u.endswith(".pdf"):
        return "documento"
    if "sei.cvm.gov.br" in item["url"]:
        return "sei"
    return "pagina"


def baixar_item(item, cliente, raiz=CACHE, verificar=True, log=print):
    """Baixa um julgado; devolve o registro gravado. Erro de rede num arquivo fica em `erros`
    e o item volta como incompleto (a próxima execução tenta de novo)."""
    pasta = pasta_do_item(item, raiz)
    antes = ler_registro(pasta) or {}
    por_url = {a["url"]: a for a in antes.get("arquivos", [])}
    reg = {"id": item["id"], "tipo": item["tipo"], "url": item["url"], "arquivos": [],
           "ignorados": [], "erros": [], "avisos": []}
    fila = [(_papel_principal(item), item.get("titulo", ""), item["url"])] if item["url"] else []
    feitos, novos = set(), 0
    while fila:
        papel, rotulo, url = fila.pop(0)
        if url in feitos:
            continue
        feitos.add(url)
        try:
            arq, novo = _baixar_arquivo(cliente, pasta, papel, rotulo, url,
                                        len(reg["arquivos"]) + 1, por_url.get(url), verificar,
                                        reg["avisos"])
        except Exception as e:
            reg["erros"].append({"url": url, "papel": papel, "erro": "%s: %s" % (
                type(e).__name__, str(e)[:200])})
            continue
        novos += novo
        reg["arquivos"].append(arq)
        _gravar_registro(pasta, dict(reg, completo=False))
        if papel == "pagina":
            with open(os.path.join(pasta, arq["arquivo"]), "rb") as f:
                html = jc.decodificar(f.read(), {"content-type": arq.get("content_type", "")})
            for u, rot in links_da_pagina(html):
                if jc.anexo_alheio(rot):
                    reg["ignorados"].append({"url": u, "rotulo": rot, "motivo": "anexo alheio"})
                    continue
                fila.append(("pdf" if item["tipo"] == "pas" else "anexo", rot, u))
        if papel in ("pagina", "documento", "sei") and url == item["url"]:
            for u in item.get("termo_urls", []):
                fila.append(("termo", "termo de compromisso", jc.absoluta(u)))
    reg["completo"] = not reg["erros"] and bool(reg["arquivos"])
    reg["baixado_em"] = jc.hoje_sp()
    _gravar_registro(pasta, reg)
    log("%s: %d arquivo(s), %d novo(s)%s" % (item["id"], len(reg["arquivos"]), novos,
                                            ", %d erro(s)" % len(reg["erros"]) if reg["erros"]
                                            else ""))
    return reg


def carregar_inventario(caminho=INVENTARIO):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)["julgados"]


def main(argv=None, cliente=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--ano", type=int)
    ap.add_argument("--tipo", choices=jc.TIPOS)
    ap.add_argument("--onda", type=int, choices=sorted(jc.ONDAS))
    ap.add_argument("--limite", type=int)
    ap.add_argument("--inventario", default=INVENTARIO)
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--sem-head", action="store_true",
                    help="reaproveita o cache sem conferir o tamanho na origem")
    a = ap.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    itens = jc.selecionar(carregar_inventario(a.inventario), ids=ids, ano=a.ano, tipo=a.tipo,
                          onda=a.onda, limite=a.limite)
    if ids:
        faltam = set(ids) - {i["id"] for i in itens}
        if faltam:
            print("ids fora do inventário: %s" % ", ".join(sorted(faltam)), file=sys.stderr)
    cliente = cliente or jc.Cliente()
    resumo = {"itens": 0, "completos": 0, "sem_url": [], "com_erro": []}
    for it in itens:
        resumo["itens"] += 1
        if not it.get("url"):
            resumo["sem_url"].append(it["id"])
            print("%s: fonte pendente (sem URL)" % it["id"])
            continue
        reg = baixar_item(it, cliente, a.cache, verificar=not a.sem_head)
        if reg["completo"]:
            resumo["completos"] += 1
        else:
            resumo["com_erro"].append(it["id"])
    print(json.dumps(dict(resumo, requisicoes=getattr(cliente, "n", None)), ensure_ascii=False))
    return 0 if not resumo["com_erro"] else 1


if __name__ == "__main__":
    sys.exit(main())
