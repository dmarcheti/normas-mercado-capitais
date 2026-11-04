#!/usr/bin/env python3
"""Varredura dos arquivos de um PR no CI (Fase 4, C19): CPF, RG e caractere de controle.

Uso: python3 scripts/varrer_pr.py ARQUIVO...
Sem a lista privada de termos (ela fica no pre-commit local). Só .md e .json; arquivo apagado
ou binário fica de fora. O achado mostra só arquivo, regra e linha, nunca o número, porque a
saída do CI é pública. Saída 0 = ok; 1 = achados.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pii  # noqa: E402
from controle import CONTROLE  # noqa: E402


def _linha(texto, pos):
    return texto.count("\n", 0, pos) + 1


def varrer_texto(rotulo, texto):
    achados = []
    for nome, achar in (("CPF", pii.achar_cpfs), ("RG", pii.achar_rgs)):
        for a, _ in achar(texto):
            achados.append("%s: %s na linha %d" % (rotulo, nome, _linha(texto, a)))
    for m in CONTROLE.finditer(texto):
        achados.append("%s: caractere de controle U+%04X na linha %d" % (rotulo, ord(m.group(0)), _linha(texto, m.start())))
    return achados


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield k
            yield from _strings(x)
    elif isinstance(v, list):
        for x in v:
            yield from _strings(x)


def varrer_arquivos(caminhos):
    achados = []
    for c in caminhos:
        if not c.endswith((".md", ".json")) or not os.path.isfile(c):
            continue
        with open(c, "rb") as f:
            dados = f.read()
        try:
            texto = dados.decode("utf-8")
        except UnicodeDecodeError:
            achados.append("%s: não é UTF-8" % c)
            continue
        if c.endswith(".json"):
            try:
                texto += "\n" + "\n".join(_strings(json.loads(texto)))  # \u0000 escapado também conta
            except ValueError:
                achados.append("%s: JSON ilegível" % c)
        achados += varrer_texto(c, texto)
    return achados


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    achados = varrer_arquivos(argv)
    for a in achados:
        print(a)
    print("varrer_pr: %d arquivo(s), %d achado(s)" % (len(argv), len(achados)))
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main())
