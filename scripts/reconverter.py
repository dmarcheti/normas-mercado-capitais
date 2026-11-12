#!/usr/bin/env python3
"""Reconverte julgados por id, da fonte em cache, pelos conversores existentes.

Uso: python3 scripts/reconverter.py --ids a,b,c
     python3 scripts/reconverter.py --lista arquivo   (um id por linha ou separados por vírgula;
                                                       "#" começa comentário)

- O id é o do frontmatter (`cvm-col-20220222-d2485`, `cvm-pas-...`, `crsfn-...`). Id que não
  está no inventário dos julgados nem na classificação do CRSFN (órgão CVM) é recusado: nada é
  convertido e a saída é 2.
- A lista é separada por tipo antes de chamar cada conversor: os ids do CRSFN vão para
  `crsfn.py converter`, os demais para `julgados_converter.py`. Conversor sem id na lista não é
  chamado (`crsfn.py converter` sem `--ids` reconverte todos).
- Os campos extraídos por LLM (ementa com `ementa_fonte: extracao`, `tema` e `tema_fonte`,
  `resultado`, `relator`) ficam: os dois conversores os preservam ao gravar
  (`julgados_converter._preservar_extracao`). Depois da conversão, este script confere cada
  julgado contra o frontmatter anterior; se a reconversão gravou em outro caminho (a data mudou
  de ano), a preservação é refeita a partir do arquivo antigo, que não é apagado e sai no
  relatório como órfão.
- Nunca aplica o pii.py sobre o texto publicado: a reconversão parte sempre da fonte.
- Julgado que já tinha arquivo e não foi regravado (o conversor pulou o id sem erro, como faz o
  CRSFN com duplicata) é erro: o arquivo é comparado (inode e mtime) antes e depois.
- `--so-cache`: não toca a rede. Antes de converter, confere que a fonte de cada id está no cache
  (`registro.json` e os arquivos dele, para a CVM; `<id>.json` e o arquivo dele, para o CRSFN); se
  faltar alguma, nada é convertido e a saída é 1. O `julgados_converter.py` já só lê o cache; o
  `crsfn.py converter` baixaria o que falta, e com `--so-cache` recebe um cliente que recusa
  qualquer requisição.

Saída: 0 sem erro; 1 com erro de conversão, julgado ausente ou não regravado, caminho mudado,
frontmatter ilegível, campo extraído perdido ou fonte fora do cache (`--so-cache`); 2 com id
desconhecido ou lista vazia.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402

TIPOS_PRESERVAM_RESULTADO = ("decisao-colegiado", "termo-compromisso", "decisao-antiga")


def ler_ids(ids=None, lista=None):
    """Ids na ordem dada, sem repetição."""
    brutos = []
    if ids:
        brutos += ids.split(",")
    if lista:
        with open(lista, encoding="utf-8") as f:
            for linha in f:
                brutos += linha.split("#", 1)[0].replace(",", " ").split()
    out = []
    for i in (x.strip() for x in brutos):
        if i and i not in out:
            out.append(i)
    return out


def conhecidos(raiz=jc.RAIZ):
    """(ids do inventário dos julgados da CVM, ids do CRSFN classificados como da CVM)."""
    import crsfn
    import julgados_baixar as jb
    inv = os.path.join(raiz, os.path.relpath(jb.INVENTARIO, jc.RAIZ))
    cvm = {it["id"] for it in jb.carregar_inventario(inv)} if os.path.exists(inv) else set()
    cam = crsfn.caminhos(raiz)["classificacao"]
    cls = {}
    if os.path.exists(cam):
        with open(cam, encoding="utf-8") as f:
            cls = json.load(f).get("itens", {})
    return cvm, {i for i, r in cls.items() if r.get("orgao") == "CVM"}


def _sob_raiz(caminho, raiz):
    return os.path.join(raiz, os.path.relpath(caminho, jc.RAIZ))


def fora_do_cache(cvm_ids, crsfn_ids, raiz=jc.RAIZ, itens_cvm=None):
    """Ids cuja fonte não está inteira no cache (sem tocar a rede)."""
    import crsfn
    import julgados_baixar as jb
    falta = []
    if cvm_ids:
        if itens_cvm is None:
            inv = _sob_raiz(jb.INVENTARIO, raiz)
            itens_cvm = jb.carregar_inventario(inv) if os.path.exists(inv) else []
        por_id = {it["id"]: it for it in itens_cvm}
        cache = _sob_raiz(jb.CACHE, raiz)
        for i in cvm_ids:
            it = por_id.get(i)
            pasta = jb.pasta_do_item(it, cache) if it else None
            try:
                reg = jb.ler_registro(pasta) if pasta else None
            except ValueError:
                reg = None
            arqs = (reg or {}).get("arquivos") or []
            if not arqs or not all(os.path.exists(os.path.join(pasta, a.get("arquivo", "")))
                                   and a.get("arquivo") for a in arqs):
                falta.append(i)
    cache = crsfn.caminhos(raiz)["cache"]
    for i in crsfn_ids:
        try:
            with open(os.path.join(cache, i + ".json"), encoding="utf-8") as f:
                arq = json.load(f).get("arquivo")
        except (OSError, ValueError):
            arq = None
        if not arq or not os.path.exists(os.path.join(cache, arq)):
            falta.append(i)
    return falta


class ClienteSemRede:
    """Cliente do crsfn.py para `--so-cache`: qualquer requisição é erro."""
    n = 0

    def _recusa(self, url, *a, **kw):
        raise RuntimeError("--so-cache: requisição recusada (%s)" % url)

    get = post = head = _recusa


def separar(ids, cvm, crsfn_ids):
    """(ids para o julgados_converter, ids para o crsfn converter, desconhecidos)."""
    a, b, x = [], [], []
    for i in ids:
        (b if i in crsfn_ids else a if i in cvm else x).append(i)
    return a, b, x


def localizar(ids, raiz=jc.RAIZ):
    """{id: caminho} dos julgados gravados, pelo nome do arquivo e pela linha `id:`."""
    stems = {}
    for i in ids:
        for pref in sorted(set(jc._PREFIXO_ARQ.values()), key=len, reverse=True):
            if i.startswith(pref):
                stems.setdefault(i[len(pref):] + ".md", []).append(i)
                break
    out = {}
    for c in glob.glob(os.path.join(raiz, "julgados", "**", "*.md"), recursive=True):
        cands = stems.get(os.path.basename(c))
        if not cands:
            continue
        with open(c, encoding="utf-8") as f:
            cab = f.read(400)
        for i in cands:
            if "\nid: %s\n" % i in cab:
                out.setdefault(i, []).append(c)
    return out


def _ler(caminho):
    try:
        return je.ler_julgado(caminho)[0]
    except (OSError, ValueError):
        return None


def _marca(caminho):
    """Identidade da gravação: os conversores gravam por os.replace (inode novo)."""
    try:
        st = os.stat(caminho)
    except OSError:
        return None
    return (st.st_ino, st.st_mtime_ns, st.st_size)


def conferir_extracao(antigo, novo):
    """Problemas de preservação dos campos extraídos entre o frontmatter antigo e o novo."""
    p = []
    if antigo.get("ementa_fonte") == "extracao":
        if novo.get("ementa_fonte") not in ("extracao", "cvm", "crsfn"):
            p.append("ementa extraída perdida (ementa_fonte %r)" % novo.get("ementa_fonte"))
        elif novo.get("ementa_fonte") == "extracao" and novo.get("ementa") != antigo.get("ementa"):
            p.append("ementa extraída mudou")
    if antigo.get("tema_fonte") == "extracao" and (
            novo.get("tema_fonte") != "extracao" or novo.get("tema") != antigo.get("tema")):
        p.append("tema extraído perdido ou mudado (%r -> %r)" % (antigo.get("tema"),
                                                                  novo.get("tema")))
    if ((antigo.get("resultado") or antigo.get("ementa_fonte") == "extracao"
         or antigo.get("tipo") in TIPOS_PRESERVAM_RESULTADO)
            and novo.get("resultado", "") != antigo.get("resultado", "")):
        p.append("resultado mudou (%r -> %r)" % (antigo.get("resultado"), novo.get("resultado")))
    if antigo.get("relator") and not novo.get("relator"):
        p.append("relator perdido (%r)" % antigo.get("relator"))
    return p


def _represervar(novo_caminho, antigo_caminho):
    """Caminho mudou: refaz a preservação a partir do arquivo antigo, que fica onde está."""
    import julgados_converter as jconv
    valores, corpo = je.ler_julgado(novo_caminho)
    valores = jconv._preservar_extracao(valores, antigo_caminho)
    tmp = novo_caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(jc.sem_controle(jc.frontmatter(valores) + corpo))
    os.replace(tmp, novo_caminho)


def _converter_cvm(ids, raiz):
    import julgados_converter as jconv
    return jconv.main(["--ids", ",".join(ids), "--raiz", raiz])


def _converter_crsfn(ids, raiz, so_cache=False):
    import crsfn
    return crsfn.main(["converter", "--ids", ",".join(ids)], raiz=raiz,
                      cliente=ClienteSemRede() if so_cache else None)


def reconverter(ids, raiz=jc.RAIZ, converter_cvm=_converter_cvm, converter_crsfn=_converter_crsfn,
                conhecidos_=None, so_cache=False, fora_do_cache_=fora_do_cache):
    """Relatório {cvm, crsfn, desconhecidos, sem_cache, conversor_rc, ausentes, nao_regravados,
    orfaos, problemas, rc}."""
    cvm, crs = conhecidos_ if conhecidos_ is not None else conhecidos(raiz)
    a, b, x = separar(ids, cvm, crs)
    rel = {"cvm": a, "crsfn": b, "desconhecidos": x, "sem_cache": [], "conversor_rc": {},
           "ausentes": [], "nao_regravados": [], "orfaos": {}, "problemas": {}, "rc": 0}
    if not ids or x:
        rel["rc"] = 2
        return rel
    if so_cache:
        rel["sem_cache"] = fora_do_cache_(a, b, raiz)
        if rel["sem_cache"]:
            rel["rc"] = 1
            return rel
    antes = localizar(ids, raiz)
    antigos = {i: _ler(c[0]) for i, c in antes.items()}
    marcas = {c: _marca(c) for cs in antes.values() for c in cs}
    if a:
        rel["conversor_rc"]["cvm"] = converter_cvm(a, raiz)
    if b:
        rel["conversor_rc"]["crsfn"] = (converter_crsfn(b, raiz, so_cache=True) if so_cache
                                        else converter_crsfn(b, raiz))
    depois = localizar(ids, raiz)
    for i in ids:
        novos = depois.get(i, [])
        if not novos:
            rel["ausentes"].append(i)
            continue
        velhos = antes.get(i, [])
        atual = [c for c in novos if c not in velhos] or novos
        if velhos and set(novos) != set(velhos):
            # gravou em outro caminho: o novo é o que não existia antes
            _represervar(atual[0], velhos[0])
            rel["orfaos"][i] = sorted(set(velhos) - set(atual))
        elif _marca(atual[0]) == marcas.get(atual[0]):
            rel["nao_regravados"].append(i)
            continue
        prob = []
        if velhos and antigos.get(i) is None:
            prob.append("frontmatter anterior ilegível (%s): extração não conferida" % velhos[0])
        novo_v = _ler(atual[0])
        if novo_v is None:
            prob.append("frontmatter novo ilegível (%s)" % atual[0])
        if antigos.get(i) and novo_v is not None:
            prob += conferir_extracao(antigos[i], novo_v)
        if prob:
            rel["problemas"][i] = prob
    falhou = (any(rel["conversor_rc"].values()) or rel["ausentes"] or rel["nao_regravados"]
              or rel["orfaos"] or rel["problemas"])
    rel["rc"] = 1 if falhou else 0
    return rel


def main(argv=None, **kw):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--lista", help="arquivo com os ids")
    ap.add_argument("--raiz", default=jc.RAIZ, help="raiz do repositório")
    ap.add_argument("--so-cache", action="store_true",
                    help="não toca a rede; falha se a fonte de algum id não estiver no cache")
    a = ap.parse_args(argv)
    ids = ler_ids(a.ids, a.lista)
    rel = reconverter(ids, a.raiz, so_cache=a.so_cache, **kw)
    if not ids:
        print("reconverter: nenhum id", file=sys.stderr)
    for i in rel["desconhecidos"]:
        print("reconverter: id desconhecido: %s (nada foi convertido)" % i, file=sys.stderr)
    for i in rel["sem_cache"]:
        print("reconverter: --so-cache: fonte fora do cache: %s (nada foi convertido)" % i,
              file=sys.stderr)
    for k, v in rel["conversor_rc"].items():
        if v:
            print("reconverter: conversor %s saiu com %s" % (k, v), file=sys.stderr)
    for i in rel["nao_regravados"]:
        print("reconverter: %s não foi regravado pelo conversor" % i, file=sys.stderr)
    for i in rel["ausentes"]:
        print("reconverter: %s sem arquivo depois da conversão" % i, file=sys.stderr)
    for i, v in rel["orfaos"].items():
        print("reconverter: %s gravado em outro caminho; arquivo antigo fica: %s"
              % (i, ", ".join(v)), file=sys.stderr)
    for i, v in rel["problemas"].items():
        print("reconverter: %s: %s" % (i, "; ".join(v)), file=sys.stderr)
    if rel["rc"] != 2 and not rel["sem_cache"]:
        print("reconverter: %d da CVM, %d do CRSFN; %d ausente(s), %d não regravado(s), "
              "%d órfão(s), %d com problema no frontmatter" % (
                  len(rel["cvm"]), len(rel["crsfn"]), len(rel["ausentes"]),
                  len(rel["nao_regravados"]), len(rel["orfaos"]), len(rel["problemas"])))
    return rel["rc"]


if __name__ == "__main__":
    sys.exit(main())
