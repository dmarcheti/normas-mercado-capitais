#!/usr/bin/env python3
"""Pre-push: recusa o push de qualquer ref que contenha, como ancestral, um commit do histórico antigo.

Protege contra um `git push origin <branch antigo>` por engano depois da reescrita do histórico
(Fase 5): os commits antigos têm e-mail e dados que não podem chegar ao repo público.

Entrada (stdin, protocolo do hook pre-push): uma linha por ref,
`<local ref> <local sha> <remote ref> <remote sha>`. Ref de deleção (sha local zerado) passa.

A lista de commits proibidos é um arquivo, um sha completo por linha, `#` comenta (linha inteira ou
no fim da linha). O caminho vem de `git config normas.historicoAntigo` (aceita `~`).
- Config ausente: só avisa e deixa passar (o repo pode ser clonado por terceiros).
- Config apontando para arquivo inexistente ou ilegível, ou com linha que não é sha: recusa.
- Sha da lista que não existe no repo é ignorado (clone novo nunca teve o histórico antigo).
- Qualquer erro do git ao conferir um ancestral conta como recusa.

Saída 0 = push liberado; 1 = push recusado.
"""
import os
import re
import subprocess
import sys

NULO = re.compile(r"^0+$")
SHA = re.compile(r"^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")


def git(args, cwd):
    p = subprocess.run(["git", "-C", cwd] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def ler_lista(caminho):
    """Shas do arquivo. OSError ou ValueError (linha que não é sha) sobem ao chamador."""
    shas = []
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            linha = linha.split("#", 1)[0].strip()
            if not linha:
                continue
            if not SHA.match(linha):
                raise ValueError("linha %d não é um sha completo" % n)
            shas.append(linha.lower())
    return shas


def refs_do_stdin(texto):
    """[(ref local, sha local)] das linhas do protocolo, sem as deleções."""
    refs = []
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) < 2:
            continue
        if NULO.match(partes[1]):
            continue
        refs.append((partes[0], partes[1]))
    return refs


def main(stdin_texto, cwd=None, err=sys.stderr):
    cwd = cwd or os.getcwd()
    refs = refs_do_stdin(stdin_texto)
    rc, caminho, _ = git(["config", "--get", "--type=path", "normas.historicoAntigo"], cwd)
    if rc != 0 or not caminho:
        err.write("pre-push: normas.historicoAntigo não configurado; não conferi o histórico antigo.\n"
                  "  Para ativar: git config normas.historicoAntigo /caminho/para/historico-antigo.txt\n")
        return 0
    try:
        lista = ler_lista(caminho)
    except OSError as x:
        err.write("pre-push: RECUSADO. Não consegui ler a lista do histórico antigo (%s): %s\n" % (caminho, x))
        return 1
    except ValueError as x:
        err.write("pre-push: RECUSADO. Lista do histórico antigo inválida (%s): %s\n" % (caminho, x))
        return 1
    existentes = [s for s in lista if git(["cat-file", "-e", s + "^{commit}"], cwd)[0] == 0]
    if not existentes:
        return 0
    for ref, sha in refs:
        for antigo in existentes:
            rc, _, e = git(["merge-base", "--is-ancestor", antigo, sha], cwd)
            if rc == 0:
                err.write("pre-push: RECUSADO. %s (%s) contém o commit %s do histórico antigo.\n"
                          "  Não envie esse branch. Confira o que está empurrando (git push <remoto> <branch>).\n"
                          % (ref, sha[:12], antigo[:12]))
                return 1
            if rc != 1:
                err.write("pre-push: RECUSADO. Erro ao conferir %s (%s) contra %s: %s\n"
                          % (ref, sha[:12], antigo[:12], e or "git rc %d" % rc))
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.stdin.read()))
