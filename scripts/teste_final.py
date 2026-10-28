#!/usr/bin/env python3
"""Teste 2 (final): a norma montada pelo histórico == o consolidado da CVM.

diferencas_final(md_norma, md_consolidado) -> lista de diferenças (vazia = ok).
Compara linha a linha, depois de normalizar artigos e texto (ver normalizar.py)
e a partir do primeiro `## Art.`; título, ementa e considerandos ficam de fora
(a ementa vai no frontmatter e o título do consolidado traz a lista de atos).

Uso: python3 scripts/teste_final.py <id> [--norma ARQ.md] [--consolidado ARQ.docx]
Sem --consolidado, usa dados/resolNNNconsolid.docx (baixa se faltar, com a URL do
inventário). Saída 0 = ok; 1 = diferenças; 2 = uso/erro.
"""
import difflib
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import docx_para_md, normalizar_artigos  # noqa: E402
from normalizar import normalizar_texto  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_HEADING = re.compile(r"^## Art\. (.+)$")


def _sem_assinatura(linhas):
    """Tira o bloco final "Original assinado por / NOME / Cargo" do consolidado
    (o DOU, de onde vem a norma, não o traz como texto normativo)."""
    for i in range(max(0, len(linhas) - 5), len(linhas)):
        if linhas[i].strip().lower() == "original assinado por":
            return linhas[:i]
    return linhas


def _linhas(md):
    md = _FRONTMATTER.sub("", md, count=1)
    texto = normalizar_texto(normalizar_artigos(md))
    linhas = _sem_assinatura([l for l in texto.split("\n") if l.strip()])
    for i, l in enumerate(linhas):
        if _HEADING.match(l):
            return linhas[i:]
    return []


def _contexto(linhas, i):
    while i >= 0:
        m = _HEADING.match(linhas[i])
        if m:
            return "Art. " + m.group(1)
        i -= 1
    return "?"


def diferencas_final(md_norma, md_consolidado):
    norma, cons = _linhas(md_norma), _linhas(md_consolidado)
    if not norma:
        return ["norma sem nenhum artigo (## Art.)"]
    if not cons:
        return ["consolidado sem nenhum artigo"]
    dif = []
    ops = difflib.SequenceMatcher(None, cons, norma, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        for i in range(i1, i2):
            dif.append("[%s] só no consolidado: %s" % (_contexto(cons, i), cons[i]))
        for j in range(j1, j2):
            dif.append("[%s] só na norma: %s" % (_contexto(norma, j), norma[j]))
    return dif


def _numero(id_norma):
    m = re.fullmatch(r"cvm-res-(\d+)", id_norma)
    return int(m.group(1)) if m else None


def _baixar(url, destino):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
        f.write(r.read())


def main(argv):
    args = argv[1:]
    opcoes = {}
    for chave in ("--norma", "--consolidado"):
        if chave in args:
            i = args.index(chave)
            opcoes[chave] = args[i + 1] if i + 1 < len(args) else None
            del args[i:i + 2]
    if len(args) != 1 or None in opcoes.values():
        print(__doc__)
        return 2
    numero = _numero(args[0])
    if numero is None:
        print("teste_final: id inválido %r (esperado cvm-res-N)" % args[0])
        return 2
    norma = opcoes.get("--norma") or os.path.join(
        RAIZ, "plugins", "normas", "normas", "cvm", "resolucoes", "%04d.md" % numero)
    consolidado = opcoes.get("--consolidado") or os.path.join(RAIZ, "dados", "resol%03dconsolid.docx" % numero)
    if not os.path.exists(norma):
        print("teste_final: norma não encontrada: %s" % norma)
        return 2
    if not os.path.exists(consolidado):
        from inventario import carregar_inventario
        item = next((x for x in carregar_inventario(os.path.join(RAIZ, "fontes", "inventario.json"))
                     if x["id"] == args[0]), None)
        url = (item or {}).get("url_consolidado", {}).get("docx")
        if not url:
            print("teste_final: sem consolidado DOCX no inventário para %s" % args[0])
            return 2
        _baixar(url, consolidado)
    with open(norma, encoding="utf-8") as f:
        md_norma = f.read()
    dif = diferencas_final(md_norma, docx_para_md(consolidado))
    for d in dif:
        print(d)
    print("teste_final: %s, %d diferença(s)" % (args[0], len(dif)))
    return 1 if dif else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
