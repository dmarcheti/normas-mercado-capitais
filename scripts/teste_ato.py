#!/usr/bin/env python3
"""Teste 1 (por ato): o commit de um ato só traz texto que está no ato.

linhas_novas_fora_do_ato(diff, texto_ato) -> linhas adicionadas no diff que
não aparecem no texto do ato (depois de normalizar). Lista vazia = ok.
Ignora headings, frontmatter, linhas só de numeração, a marca de revogação e
a linha "Vigente a partir de ...". Limite conhecido: o teste pega texto
inventado ou alterado, não texto verdadeiro colocado no lugar errado.

Uso: python3 scripts/teste_ato.py <commit>
O commit deve trazer o texto do ato em `alteradoras/` e a alteração em
`resolucoes/`. Saída 0 = ok; 1 = linhas fora do ato; 2 = uso/erro.
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalizar import normalizar_texto  # noqa: E402
from validar import CAMPOS, OPCIONAIS, MARCA_VIGENCIA  # noqa: E402

_CHAVE_FRONTMATTER = re.compile(r"^(?:%s):(?:\s|$)" % "|".join(CAMPOS + OPCIONAIS))
_SO_NUMERACAO = re.compile(
    r"^(?:§+\s*\d+[º°]?(?:-[A-Z])?|Parágrafo único\.?|[IVXLCDM]+(?:-[A-Z]{1,2})?\s*[-–—]?"
    r"|[a-z]\)|\d+\s*[-–—.)]?|Art\.?\s*\d+[º°]?(?:-[A-Z]{1,2})?\.?)$"
)


def _compacto(texto):
    return " ".join(normalizar_texto(texto).split())


def linhas_novas_fora_do_ato(diff, texto_ato):
    ato = _compacto(texto_ato)
    fora = []
    for bruta in diff.split("\n"):
        if not bruta.startswith("+") or bruta.startswith("+++"):
            continue
        linha = bruta[1:]
        if not linha.strip() or linha.strip() == "---" or linha.lstrip().startswith("#"):
            continue
        if _CHAVE_FRONTMATTER.match(linha) or MARCA_VIGENCIA.match(linha):
            continue
        norm = _compacto(linha)
        if not norm or norm == "(Revogado)" or _SO_NUMERACAO.match(norm):
            continue
        if norm.endswith(" (Revogado)") and _SO_NUMERACAO.match(norm[: -len(" (Revogado)")]):
            continue
        if norm not in ato:
            fora.append(linha)
    return fora


def _git(raiz, *args):
    return subprocess.run(
        ["git", "-C", raiz] + list(args), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.decode("utf-8")


def _so_resolucoes(diff):
    blocos = re.split(r"(?m)^(?=diff --git )", diff)
    return "".join(b for b in blocos if re.match(r"diff --git a/\S*/resolucoes/", b))


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    commit = argv[1]
    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    try:
        arquivos = _git(raiz, "show", "--name-only", "--format=", commit).split()
        atos = [a for a in arquivos if "/alteradoras/" in a]
        if not atos:
            print("teste_ato: o commit %s não traz o texto do ato em alteradoras/" % commit)
            return 2
        texto_ato = "\n".join(_git(raiz, "show", "%s:%s" % (commit, a)) for a in atos)
        diff = _so_resolucoes(_git(raiz, "show", "--format=", "--no-color", "-U0", commit))
    except subprocess.CalledProcessError as e:
        print("teste_ato: erro do git: %s" % e.stderr.decode("utf-8").strip())
        return 2
    fora = linhas_novas_fora_do_ato(diff, texto_ato)
    for linha in fora:
        print("fora do ato: %s" % linha)
    print("teste_ato: %d linha(s) fora do ato" % len(fora))
    return 1 if fora else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
