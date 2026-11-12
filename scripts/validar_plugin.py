#!/usr/bin/env python3
"""Validador do plugin `normas`: tamanho, fichas e índices dos julgados.

Uso: python3 scripts/validar_plugin.py [--repo RAIZ]
Saída 0 = ok; 1 = alguma violação (uma por linha); 2 = uso incorreto. Pasta ausente é violação:
sem as fichas, sem os índices ou sem o `julgados/` da raiz não há o que validar, e isso é falha.

Confere:
1. `plugins/normas/` com no máximo LIMITE_MB (soma dos bytes dos arquivos) e LIMITE_ARQUIVOS arquivos;
2. nenhum arquivo de `julgados/fichas/` da skill acima de LIMITE_FICHA bytes e `julgados/indice.md`
   com no máximo LIMITE_INDICE_MD bytes;
3. o `texto_integral` de toda ficha aponta (URL do GitHub -> caminho) para um arquivo que existe em
   `julgados/` da raiz;
4. todo par (Ficha, Id) das tabelas dos índices existe: o arquivo da ficha existe e traz `## <Id>`;
5. todo julgado de `julgados/` da raiz tem ficha (algum `texto_integral` aponta para ele).
"""
import argparse
import os
import re
import sys
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fichas as fch  # noqa: E402
import validar as val  # noqa: E402

LIMITE_MB = 170
LIMITE_ARQUIVOS = 4500
LIMITE_FICHA = 24000
LIMITE_INDICE_MD = 25 * 1024
PLUGIN = os.path.join("plugins", "normas")
SKILL_JULGADOS = os.path.join(PLUGIN, "skills", "consultar-normas", "julgados")

RE_ID = re.compile(r"(?m)^## (.+?)[ \t]*$")
RE_TEXTO = re.compile(r"(?m)^- texto_integral: (\S+)[ \t]*$")


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def _arquivos(pasta):
    for dirpath, _dirs, nomes in os.walk(pasta):
        for n in sorted(nomes):
            yield os.path.join(dirpath, n)


def erros_tamanho(repo, limite_mb=LIMITE_MB, limite_arquivos=LIMITE_ARQUIVOS):
    pasta = os.path.join(repo, PLUGIN)
    if not os.path.isdir(pasta):
        return ["%s: pasta não existe" % PLUGIN]
    total = n = 0
    for c in _arquivos(pasta):
        total += os.path.getsize(c)
        n += 1
    out = []
    if total > limite_mb * 1024 * 1024:
        out.append("%s: %.2f MB, acima de %s MB" % (PLUGIN, total / 1024 / 1024, limite_mb))
    if n > limite_arquivos:
        out.append("%s: %d arquivos, acima de %d" % (PLUGIN, n, limite_arquivos))
    return out


def erros_limites_skill(repo, limite_ficha=LIMITE_FICHA, limite_indice=LIMITE_INDICE_MD):
    base = os.path.join(repo, SKILL_JULGADOS)
    out = []
    pasta = os.path.join(base, fch.PASTA_FICHAS)
    if not os.path.isdir(pasta) or not any(True for _ in _arquivos(pasta)):
        out.append("%s: sem fichas" % os.path.join(SKILL_JULGADOS, fch.PASTA_FICHAS))
    else:
        for c in _arquivos(pasta):
            t = os.path.getsize(c)
            if t > limite_ficha:
                out.append("%s: %d bytes, acima de %d" % (os.path.relpath(c, repo), t, limite_ficha))
    indice = os.path.join(base, "indice.md")
    if not os.path.isfile(indice):
        out.append("%s: não existe" % os.path.relpath(indice, repo))
    elif os.path.getsize(indice) > limite_indice:
        out.append("%s: %d bytes, acima de %d" % (os.path.relpath(indice, repo),
                                                  os.path.getsize(indice), limite_indice))
    return out


def alvo_do_texto(url):
    """Caminho relativo a `julgados/` da raiz que a URL `texto_integral` nomeia; None se a URL não é
    da base do acervo."""
    if not url.startswith(fch.BASE_URL):
        return None
    return unquote(url[len(fch.BASE_URL):])


def erros_textos_integrais(repo):
    """([erros], {caminhos relativos a julgados/ citados por alguma ficha})."""
    pasta = os.path.join(repo, SKILL_JULGADOS, fch.PASTA_FICHAS)
    raiz = os.path.join(repo, "julgados")
    out, citados = [], set()
    if not os.path.isdir(raiz):
        return ["julgados: pasta não existe"], citados
    if not os.path.isdir(pasta):
        return [], citados  # a falta das fichas já é acusada em erros_limites_skill
    for c in _arquivos(pasta):
        if not c.endswith(".md"):
            continue
        rel = os.path.relpath(c, repo)
        for url in RE_TEXTO.findall(_ler(c)):
            alvo = alvo_do_texto(url)
            if alvo is None:
                out.append("%s: texto_integral fora da base do acervo: %s" % (rel, url))
            elif not os.path.isfile(os.path.join(raiz, *alvo.split("/"))):
                out.append("%s: texto_integral aponta para arquivo que não existe: %s" % (rel, alvo))
            else:
                citados.add(alvo)
    return out, citados


def pares_dos_indices(texto):
    """[(Ficha, Id)] das linhas das tabelas cujo cabeçalho termina em `| Id | Ficha |`."""
    out, ativa = [], False
    for linha in texto.split("\n"):
        if not linha.startswith("|"):
            ativa = False
            continue
        celulas = [x.strip() for x in linha.strip().strip("|").split("|")]
        if len(celulas) >= 2 and celulas[-2:] == ["Id", "Ficha"]:
            ativa = True
        elif ativa and len(celulas) >= 2 and not set(linha) <= set("|-: "):
            out.append((celulas[-1], celulas[-2]))
    return out


def erros_indices(repo):
    base = os.path.join(repo, SKILL_JULGADOS)
    if not os.path.isdir(base):
        return ["%s: pasta não existe" % SKILL_JULGADOS]
    ids_por_ficha = {}
    out, vistos = [], set()
    for c in _arquivos(base):
        rel_c = os.path.relpath(c, base).replace(os.sep, "/")
        if not c.endswith(".md") or rel_c.startswith(fch.PASTA_FICHAS + "/"):
            continue
        for ficha, ident in pares_dos_indices(_ler(c)):
            if (ficha, ident) in vistos:
                continue
            vistos.add((ficha, ident))
            if ficha not in ids_por_ficha:
                caminho = os.path.join(base, *ficha.split("/"))
                ids_por_ficha[ficha] = set(RE_ID.findall(_ler(caminho))) if os.path.isfile(caminho) else None
            if ids_por_ficha[ficha] is None:
                out.append("%s: ficha não existe: %s (Id %s)" % (rel_c, ficha, ident))
            elif ident not in ids_por_ficha[ficha]:
                out.append("%s: %s não tem `## %s`" % (rel_c, ficha, ident))
    if not vistos:
        out.append("%s: nenhuma linha com Id e Ficha nos índices" % SKILL_JULGADOS)
    return out


def erros_julgados_sem_ficha(repo, citados):
    raiz = os.path.join(repo, "julgados")
    if not os.path.isdir(raiz):
        return []  # já acusado em erros_textos_integrais
    out = []
    for c in val.arquivos_de_julgados(raiz):
        rel = os.path.relpath(c, raiz).replace(os.sep, "/")
        if rel not in citados:
            out.append("julgados/%s: sem ficha" % rel)
    return out


def validar(repo):
    erros = erros_tamanho(repo) + erros_limites_skill(repo)
    e_textos, citados = erros_textos_integrais(repo)
    erros += e_textos + erros_indices(repo) + erros_julgados_sem_ficha(repo, citados)
    return erros


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=fch.REPO)
    args = ap.parse_args(argv)
    erros = validar(os.path.abspath(args.repo))
    for e in erros:
        print(e)
    print("validar_plugin: %d violação(ões)" % len(erros))
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
