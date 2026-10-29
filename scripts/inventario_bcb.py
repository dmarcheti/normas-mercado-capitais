#!/usr/bin/env python3
"""Inventário da camada 4 (CMN e BCB) pela API da busca de normas do BCB, só por script.

Duas chamadas públicas, sem chave (as mesmas da página bcb.gov.br/estabilidadefinanceira/buscanormas):
- busca: /api/search/app/normativos/buscanormativos (SharePoint; 500 linhas por página),
  com tipo, número, data, assunto, responsável e os indicadores Revogado e Cancelado;
- norma: /api/conteudo/app/normativos/exibenormativo?p1=<tipo>&p2=<número>, com o texto
  compilado em HTML (redação antiga em <s>, notas "Redação dada pela..."), DOU, versão,
  atualizações, referências e documentos anexos.

Tipos: as Resoluções do CMN aparecem como "Resolução" até a 4.838 e "Resolução CMN" depois;
o script junta as duas como `resolucao-cmn`. Situação: `revogada` (Revogado), `cancelada`
(Cancelado) ou `vigente` (nenhum dos dois; o BCB não marca revogação parcial).

Uso (rede): python3 scripts/inventario_bcb.py [--cache DIR] [--saida ARQUIVO] [--sem-texto]
  Baixa a busca de todos os tipos e a norma de cada não revogada (cache em
  dados/fase-2c/bcb/); grava o inventário completo em dados/fase-2c/acervo-bcb-completo.json e,
  em fontes/acervo-bcb.json, só as vigentes com os campos de identificação (contagem por tipo e
  situação no topo); imprime o resumo.
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
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inventario import USER_AGENT  # noqa: E402

BUSCA = "https://www.bcb.gov.br/api/search/app/normativos/buscanormativos?"
NORMA = "https://www.bcb.gov.br/api/conteudo/app/normativos/exibenormativo?"
PAGINA = "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?"
# tipo do BCB -> tipo do acervo
TIPOS = {
    "Resolução": "resolucao-cmn",
    "Resolução CMN": "resolucao-cmn",
    "Resolução BCB": "resolucao-bcb",
    "Resolução Conjunta": "resolucao-conjunta",
    "Circular": "circular",
    "Carta Circular": "carta-circular",
    "Instrução Normativa BCB": "instrucao-normativa-bcb",
}
LINHAS = 500
CAMPOS_SO_NO_COMPLETO = ("atualizacoes", "referencias", "dou_texto", "responsavel")


def _get(url, tentativas=3):
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception:  # noqa: BLE001 — rede: tenta de novo
            if i == tentativas - 1:
                raise
            time.sleep(3 * (i + 1))


def busca(tipo_bcb, inicio):
    p = {"querytext": "ContentType:normativo AND contentSource:normativos",
         "rowlimit": LINHAS, "startrow": inicio, "sortlist": "Data1OWSDATE:descending",
         "refinementfilters": 'TipodoNormativoOWSCHCS:equals("%s")' % tipo_bcb}
    return _get(BUSCA + urllib.parse.urlencode(p))


def todos(tipo_bcb):
    """Linhas da busca de um tipo, todas as páginas."""
    out, inicio = [], 0
    while True:
        r = busca(tipo_bcb, inicio)
        out += r["Rows"]
        inicio += r["RowCount"]
        if not r["RowCount"] or inicio >= r["TotalRows"]:
            return out
        time.sleep(0.5)


def _bool(x):
    return str(x).strip().lower() in ("1", "true")


def item_da_busca(row):
    tipo_bcb = row["TipodoNormativoOWSCHCS"]
    n = int(float(row["NumeroOWSNMBR"]))
    sit = "cancelada" if _bool(row.get("CanceladoOWSBOOL")) else (
        "revogada" if _bool(row.get("RevogadoOWSBOOL")) else "vigente")
    return {
        "tipo": TIPOS[tipo_bcb], "tipo_bcb": tipo_bcb, "numero": n,
        "data": (row.get("data") or "")[:10] or None,
        "assunto": re.sub(r"\s+", " ", row.get("AssuntoNormativoOWSMTXT") or "").strip(),
        "responsavel": row.get("ResponsavelOWSText"), "situacao": sit,
        "url_pagina": PAGINA + urllib.parse.urlencode({"tipo": tipo_bcb, "numero": n}),
    }


def data_dou(txt):
    m = re.search(r"DOU de (\d{1,2})/(\d{1,2})/(\d{4})", txt or "")
    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else None


def palavras_html(h):
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", h or ""))
    return len(re.findall(r"\w+", t))


def detalhar(item, cache):
    """Acrescenta ao item os campos da norma (exibenormativo), com cache em disco."""
    destino = os.path.join(cache, "%s-%05d.json" % (item["tipo_bcb"].replace(" ", "_"), item["numero"]))
    if os.path.exists(destino) and os.path.getsize(destino):
        with open(destino, encoding="utf-8") as f:
            d = json.load(f)
    else:
        d = _get(NORMA + urllib.parse.urlencode({"p1": item["tipo_bcb"], "p2": item["numero"]}))
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        time.sleep(0.4)
    c = (d.get("conteudo") or [{}])[0]
    texto = c.get("Texto") or ""
    docs = c.get("Documentos") or ""
    item.update({
        "dou": data_dou(c.get("DOU")), "dou_texto": c.get("DOU"),
        "versao": c.get("VersaoNormativo"),
        "formato": ("html" if palavras_html(texto) >= 30 else "sem-texto")
                   + ("+anexos" if docs else ""),
        "palavras": palavras_html(texto), "bytes_html": len(texto.encode("utf-8")),
        "tachado": len(re.findall(r"<(?:s|strike)\b", texto)),
        "tabelas": texto.count("<table"),
        "documentos": docs if isinstance(docs, str) else json.dumps(docs, ensure_ascii=False),
        "atualizacoes": [a.strip() for a in (c.get("Atualizacoes") or "").split(";#") if a.strip()],
        "referencias": [a.strip() for a in (c.get("Referencias") or "").split(";#") if a.strip()],
    })
    return item


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default="dados/fase-2c/bcb")
    ap.add_argument("--saida", default="fontes/acervo-bcb.json")
    ap.add_argument("--completo", default="dados/fase-2c/acervo-bcb-completo.json")
    ap.add_argument("--sem-texto", action="store_true", help="só a busca, sem a norma de cada uma")
    args = ap.parse_args(argv[1:])
    os.makedirs(args.cache, exist_ok=True)
    itens, falhas = [], []
    for tipo_bcb in TIPOS:
        linhas = todos(tipo_bcb)
        print("%s: %d" % (tipo_bcb, len(linhas)), flush=True)
        itens += [item_da_busca(r) for r in linhas]
    itens.sort(key=lambda i: (i["tipo"], i["numero"]))
    if not args.sem_texto:
        vig = [i for i in itens if i["situacao"] == "vigente"]
        for k, i in enumerate(vig, 1):
            try:
                detalhar(i, args.cache)
            except Exception as e:  # noqa: BLE001 — registra e segue
                falhas.append("%s %d: %s" % (i["tipo_bcb"], i["numero"], e))
            if k % 100 == 0:
                print("  normas: %d/%d" % (k, len(vig)), flush=True)
    acervo = {"fonte": "API da busca de normas do BCB (bcb.gov.br/estabilidadefinanceira/buscanormas)",
              "lido_em": time.strftime("%Y-%m-%d"), "normas": itens, "falhas": falhas}
    with open(args.completo, "w", encoding="utf-8") as f:
        json.dump(acervo, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # no Git: só as vigentes, sem atualizações e referências (o completo fica em dados/)
    contagem = Counter((i["tipo"], i["situacao"]) for i in itens)
    enxuto = dict(acervo, contagem=["%s %s %d" % (t, s, n) for (t, s), n in sorted(contagem.items())],
                  normas=[{k: v for k, v in i.items() if k not in CAMPOS_SO_NO_COMPLETO}
                          for i in itens if i["situacao"] == "vigente"])
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(enxuto, f, ensure_ascii=False, indent=1)
        f.write("\n")
    cont = Counter((i["tipo"], i["situacao"]) for i in itens)
    for (t, s), n in sorted(cont.items()):
        print("%-26s %-10s %5d" % (t, s, n))
    print("falhas: %d" % len(falhas))
    for x in falhas[:20]:
        print("  " + x)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
