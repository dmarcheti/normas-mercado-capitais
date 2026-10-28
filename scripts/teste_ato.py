#!/usr/bin/env python3
"""Teste 1 (por ato): o commit de um ato só traz texto que está no ato.

linhas_novas_fora_do_ato(diff, texto_ato) -> linhas adicionadas no diff que
não aparecem no texto do ato (depois de normalizar). Lista vazia = ok.
Ignora headings, frontmatter, linhas só de numeração, a marca de revogação, a
linha "Vigente a partir de ..." e os itens da lista `- arquivo.md` de `## Partes`
num index.md de norma em partes. O diff do git usa o algoritmo histogram (o Myers
padrão realinha mal blocos inalterados e acusa linhas que não mudaram). Limite conhecido: o teste pega texto
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
_ITEM_DE_PARTES = re.compile(r"^- [\w.-]+\.md$")
_SO_NUMERACAO = re.compile(
    r"^(?:§+\s*\d+[º°]?(?:-[A-Z])?|Parágrafo único\.?|[IVXLCDM]+(?:-[A-Z]{1,2})?\s*[-–—]?"
    r"|[a-z]\)|\d+\s*[-–—.)]?|\d+(?:\.\d+)+\.?|\(\d+\)|Art\.?\s*\d+[º°]?(?:-[A-Z]{1,2})?\.?)$"
)
_NOTA_DE_RODAPE = re.compile(r"^\(\d+\)\s+")


def _no_ato(norm, ato):
    """Linha de tabela: cada célula com texto tem de estar no ato (a moldura e as
    células vazias não). Nota de rodapé "(N) texto": basta o texto."""
    if norm.startswith("|"):
        celulas = [c.strip() for c in norm.strip("|").split("|") if c.strip()]
        return all(c in ato for c in celulas)
    if norm in ato:
        return True
    m = _NOTA_DE_RODAPE.match(norm)
    return bool(m) and norm[m.end():] in ato


def _compacto(texto):
    # Aspas saem dos dois lados: o ato cita a nova redação entre aspas
    # ('... CVM". (NR)'), e a norma alterada traz o texto sem elas.
    return " ".join(normalizar_texto(texto).replace('"', "").split())


def linhas_novas_fora_do_ato(diff, texto_ato):
    ato = _compacto(texto_ato)
    fora = []
    arquivo = ""
    for bruta in diff.split("\n"):
        if bruta.startswith("+++"):
            arquivo = bruta[4:].strip()
            continue
        if not bruta.startswith("+"):
            continue
        linha = bruta[1:]
        if _ITEM_DE_PARTES.match(linha.strip()) and os.path.basename(arquivo) == "index.md":
            continue
        if not linha.strip() or linha.strip() == "---" or linha.lstrip().startswith("#"):
            continue
        if _CHAVE_FRONTMATTER.match(linha) or MARCA_VIGENCIA.match(linha):
            continue
        norm = _compacto(linha)
        if not norm or norm == "(Revogado)" or _SO_NUMERACAO.match(norm):
            continue
        if norm.endswith(" (Revogado)") and _SO_NUMERACAO.match(norm[: -len(" (Revogado)")]):
            continue
        if not _no_ato(norm, ato):
            fora.append(linha)
    return fora


def argumentos_diff(commit):
    return ["show", "--diff-algorithm=histogram", "--format=", "--no-color", "-U0", commit]


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
        diff = _so_resolucoes(_git(raiz, *argumentos_diff(commit)))
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
