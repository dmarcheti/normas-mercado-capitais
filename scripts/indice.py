#!/usr/bin/env python3
"""Índice das normas do acervo.

gerar_indice(raiz) -> (md, itens): `raiz` é `plugins/normas/normas`. `itens` é a
lista, ordenada por órgão, tipo e número, de {id, titulo, ementa, situacao,
vigente_ate_ato, caminho}; `caminho` é relativo à raiz (ex.: cvm/resolucoes/0017.md).
`md` é o índice legível (indice.md), com as normas e os atos alteradores.

Uso: python3 scripts/indice.py [raiz]            grava indice.md e normas.json em raiz
     python3 scripts/indice.py [raiz] --verificar  falha (saída 1) se estiverem desatualizados
A raiz padrão é plugins/normas/normas. Sem data de geração: a saída só muda
quando o acervo muda.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validar import ler_frontmatter  # noqa: E402

RAIZ_PADRAO = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "plugins", "normas", "normas"))
ARQUIVOS_DO_INDICE = ("indice.md", "normas.json")


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        pares, _corpo, erro = ler_frontmatter(f.read())
    if erro:
        raise ValueError("%s: %s" % (caminho, erro))
    return dict((c, v) for c, v in pares if c is not None)


def _arquivos(raiz, pasta):
    achados = []
    for dirpath, _dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) == pasta:
            achados += [os.path.join(dirpath, n) for n in nomes if n.endswith(".md")]
    return achados


def _titulo(v):
    return "Resolução %s nº %s/%s" % (v["orgao"].upper(), v["numero"], v["data"][:4])


def _item(raiz, caminho):
    v = _ler(caminho)
    return {
        "id": v["id"],
        "titulo": _titulo(v),
        "ementa": v["ementa"],
        "situacao": v["situacao"],
        "vigente_ate_ato": v["vigente_ate_ato"],
        "caminho": os.path.relpath(caminho, raiz).replace(os.sep, "/"),
    }


def _chave(item):
    orgao, tipo, arq = item["caminho"].split("/")[:3]
    return (orgao, tipo, arq)


def _celula(txt):
    return txt.replace("|", "\\|")


def gerar_indice(raiz):
    itens = sorted((_item(raiz, c) for c in _arquivos(raiz, "resolucoes")), key=_chave)
    atos = sorted((_item(raiz, c) for c in _arquivos(raiz, "alteradoras")), key=_chave)
    md = [
        "# Índice das normas",
        "",
        "Material não oficial. Não substitui o Diário Oficial da União nem o site da CVM.",
        "Gerado por `scripts/indice.py`; não edite à mão.",
        "",
        "## Normas",
        "",
        "| Norma | Ementa | Situação | Vigente até o ato | Arquivo |",
        "|---|---|---|---|---|",
    ]
    for i in itens:
        md.append("| %s | %s | %s | %s | %s |" % (
            i["titulo"], _celula(i["ementa"]), i["situacao"],
            i["vigente_ate_ato"] or "redação original", i["caminho"]))
    md += ["", "## Atos alteradores (texto integral do ato)", "",
           "| Ato | Ementa | Arquivo |", "|---|---|---|"]
    for i in atos:
        md.append("| %s | %s | %s |" % (i["titulo"], _celula(i["ementa"]), i["caminho"]))
    return "\n".join(md) + "\n", itens


def _json(itens):
    return json.dumps(itens, ensure_ascii=False, indent=2) + "\n"


def main(argv):
    args = [a for a in argv[1:] if a != "--verificar"]
    verificar = "--verificar" in argv[1:]
    if len(args) > 1:
        print(__doc__)
        return 2
    raiz = args[0] if args else RAIZ_PADRAO
    if not os.path.isdir(raiz):
        print("indice: %s não existe" % raiz)
        return 2
    md, itens = gerar_indice(raiz)
    esperado = {"indice.md": md, "normas.json": _json(itens)}
    if verificar:
        defasados = []
        for nome, conteudo in esperado.items():
            caminho = os.path.join(raiz, nome)
            atual = open(caminho, encoding="utf-8").read() if os.path.exists(caminho) else None
            if atual != conteudo:
                defasados.append(nome)
        if defasados:
            print("indice: desatualizado (%s); rode python3 scripts/indice.py" % ", ".join(defasados))
            return 1
        print("indice: em dia (%d norma(s))" % len(itens))
        return 0
    for nome, conteudo in esperado.items():
        with open(os.path.join(raiz, nome), "w", encoding="utf-8") as f:
            f.write(conteudo)
    print("indice: %d norma(s) gravada(s) em %s" % (len(itens), raiz))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
