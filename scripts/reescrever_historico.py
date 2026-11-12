#!/usr/bin/env python3
"""Reescreve o histórico de um ESPELHO bare do repositório: troca, nos blobs dos julgados, os trechos
que o varredor (`varrer_historico.py`) marcou como dado pessoal e troca o e-mail pessoal dos commits
e tags pelo noreply (mailmap). Não toca o repositório do cofre nem o repo aninhado de trabalho.

Uso:
    reescrever_historico.py --repo ESPELHO.git --achados dados/fase-5/historico/achados.jsonl \\
        --mailmap ARQ --saida DIR

Recusa (saída 2) se o --repo não for bare, se o caminho real não contiver /dados/fase-5/espelho/,
se tiver remote configurado, ou se tiver ref fora de refs/heads/main e refs/tags/*.

O mapa {sha do blob: bytes novos} vem só dos achados `pii-*` cujos caminhos estão todos em
plugins/julgados-*/ ou julgados/ (normas, termo, cnpj, controle, msg-*, email-metadado e os "-direto" são
ignorados). Cada blob é partido em linhas como o varredor (`split("\\n")`); os blocos são aplicados do
fim para o começo, com `linhas` (1-based) e `original`/`limpo`: o bloco tem de bater com o texto
(`"\\n".join(linhas[i1:i2]) == original`), senão falha ruidosa. Bloco com o mesmo número de linhas no
original e no limpo troca só as linhas de `linhas_fora_da_base`; com número diferente troca o bloco
inteiro pelo `limpo`.

Saída em --saida (só contagens e shas, nenhum valor):
- reescrita.json: blobs no mapa, trocados, nunca vistos, sem troca efetiva, commits reescritos,
  primeiro commit cujo sha mudou;
- commit-map e ref-map do filter-repo.

Saída do processo: 0 ok; 2 recusa ou erro. Erro nunca vira 0.
"""
import argparse
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

ESPELHO = "/dados/fase-5/espelho/"
# o histórico guarda os julgados em plugins/julgados-*/ (até a Fase 6) e em julgados/ (depois)
JULGADOS = re.compile(r"^(?:plugins/julgados-[^/]+/|julgados/)")
REFS_OK = "refs/heads/main"


class ErroReescrita(Exception):
    pass


# ---------------------------------------------------------------- git

def _git(repo, *args, entrada=None):
    r = subprocess.run(["git", "-C", repo] + list(args), input=entrada, capture_output=True)
    if r.returncode != 0:
        raise ErroReescrita("git %s falhou (código %d)" % (args[0], r.returncode))
    return r.stdout


def _texto(repo, *args):
    return _git(repo, *args).decode("utf-8", "replace").strip()


# ---------------------------------------------------------------- recusas

def validar_espelho(repo):
    """Devolve o caminho real do espelho ou levanta ErroReescrita se alguma recusa valer."""
    if not os.path.isdir(repo):
        raise ErroReescrita("o --repo não existe")
    real = os.path.realpath(repo)
    if ESPELHO not in real.rstrip(os.sep) + os.sep:
        raise ErroReescrita("recusado: o caminho do --repo não contém %s" % ESPELHO)
    if _texto(real, "rev-parse", "--is-bare-repository") != "true":
        raise ErroReescrita("recusado: o --repo não é bare")
    if _texto(real, "remote"):
        raise ErroReescrita("recusado: o espelho tem remote configurado")
    refs = [r for r in _texto(real, "for-each-ref", "--format=%(refname)").split("\n") if r]
    fora = [r for r in refs if r != REFS_OK and not r.startswith("refs/tags/")]
    if fora:
        raise ErroReescrita("recusado: %d ref(s) fora de refs/heads/main e refs/tags/*" % len(fora))
    if REFS_OK not in refs:
        raise ErroReescrita("recusado: o espelho não tem refs/heads/main")
    return real


# ---------------------------------------------------------------- mapa de blobs

def ler_achados(caminho):
    if not os.path.isfile(caminho):
        raise ErroReescrita("o --achados não existe")
    registros = []
    with open(caminho, encoding="utf-8") as f:
        for n, linha in enumerate(f, 1):
            if linha.strip():
                try:
                    registros.append(json.loads(linha))
                except ValueError:
                    raise ErroReescrita("achados.jsonl: linha %d não é JSON" % n)
    return registros


def selecionar(achados):
    """({blob: [achados]}, contagens por motivo). Só `pii-*` de blob com TODOS os caminhos em
    plugins/julgados-*/ ou julgados/. Blob misto (julgados e outro lugar) é erro: trocá-lo mexeria fora dos julgados."""
    por_blob, ignorados, mistos = {}, {}, set()
    for a in achados:
        regra = a.get("regra", "")
        if a.get("tipo") != "blob" or not regra.startswith("pii-"):
            chave = regra if a.get("tipo") == "blob" else "metadado"
            ignorados[chave] = ignorados.get(chave, 0) + 1
            continue
        caminhos = a.get("caminhos") or []
        em = [bool(JULGADOS.match(c)) for c in caminhos]
        if not any(em):
            ignorados["pii-fora-dos-julgados"] = ignorados.get("pii-fora-dos-julgados", 0) + 1
            continue
        if not all(em):
            mistos.add(a["blob"])
            continue
        por_blob.setdefault(a["blob"], []).append(a)
    if mistos:
        raise ErroReescrita("%d blob(s) com achado pii estão em julgados e fora deles: %s"
                            % (len(mistos), ", ".join(sorted(mistos)[:10])))
    return por_blob, ignorados


def aplicar_blocos(texto, achados):
    """Texto novo a partir dos blocos dos achados de um blob. Falha ruidosa se um bloco não bater."""
    linhas = texto.split("\n")
    blocos = []
    for a in achados:
        ls = a.get("linhas") or []
        if not ls or ls != list(range(ls[0], ls[-1] + 1)):
            raise ErroReescrita("bloco com linhas não contíguas")
        i1, i2 = ls[0] - 1, ls[-1]
        if i1 < 0 or i2 > len(linhas) or "\n".join(linhas[i1:i2]) != a.get("original"):
            raise ErroReescrita("o bloco não bate com o texto do blob %s" % a.get("blob", "?"))
        blocos.append((i1, i2, a))
    blocos.sort(key=lambda b: (b[0], b[1]))
    for (_, fim, _a), (ini, _b, _c) in zip(blocos, blocos[1:]):
        if ini < fim:
            raise ErroReescrita("blocos sobrepostos")
    for i1, i2, a in reversed(blocos):
        lim = a["limpo"].split("\n")
        if len(lim) == i2 - i1:
            for n in a.get("linhas_fora_da_base", a["linhas"]):
                k = n - 1
                if not (i1 <= k < i2):
                    raise ErroReescrita("linha fora do bloco")
                linhas[k] = lim[k - i1]
        else:
            linhas[i1:i2] = lim
    return "\n".join(linhas)


def ler_blobs(repo, shas):
    """{sha: bytes} dos blobs presentes no repo; os ausentes ficam de fora."""
    if not shas:
        return {}
    r = subprocess.run(["git", "-C", repo, "cat-file", "--batch"], input=("\n".join(shas) + "\n").encode(),
                       capture_output=True)
    if r.returncode != 0:
        raise ErroReescrita("git cat-file falhou")
    saida, dados, pos = {}, r.stdout, 0
    while pos < len(dados):
        fim = dados.index(b"\n", pos)
        cab = dados[pos:fim].decode("ascii", "replace").split(" ")
        pos = fim + 1
        if len(cab) == 2 and cab[1] == "missing":
            continue
        if len(cab) != 3 or cab[1] != "blob":
            raise ErroReescrita("resposta inesperada do git cat-file")
        tam = int(cab[2])
        saida[cab[0]] = dados[pos:pos + tam]
        pos += tam + 1
    return saida


def montar_mapa(repo, achados):
    """(mapa {sha: bytes novos}, info). Info só com contagens e shas."""
    por_blob, ignorados = selecionar(achados)
    originais = ler_blobs(repo, sorted(por_blob))
    mapa, sem_troca = {}, []
    for sha in sorted(por_blob):
        if sha not in originais:
            continue
        try:
            texto = originais[sha].decode("utf-8")
        except UnicodeDecodeError:
            raise ErroReescrita("o blob %s não é UTF-8" % sha)
        novo = aplicar_blocos(texto, por_blob[sha]).encode("utf-8")
        if novo == originais[sha]:
            sem_troca.append(sha)
        else:
            mapa[sha] = novo
    info = {"achados_lidos": len(achados), "achados_ignorados": ignorados,
            "blobs_com_achado": len(por_blob),
            "blobs_ausentes_no_espelho": len(por_blob) - len(originais),
            "blobs_sem_troca_efetiva": sem_troca}
    return mapa, info


# ---------------------------------------------------------------- filter-repo

def rodar_filter_repo(repo, mapa, mailmap):
    """Roda o git-filter-repo no próprio repo (bare). Devolve (vistos, trocados) como conjuntos de sha.

    API usada: `FilteringOptions.parse_args([...], error_on_empty=False)` e
    `RepoFilter(args, blob_callback=cb).run()`; `blob.original_id` é bytes com o sha em hex.
    `--prune-empty never` e `--prune-degenerate never`: o padrão apagaria o commit que só limpava um
    julgado (a árvore dele fica igual à do pai depois da troca), e o gate quer um commit para cada
    commit."""
    try:
        import git_filter_repo as fr
    except ImportError:
        raise ErroReescrita("git_filter_repo não está instalado")
    vistos, trocados = set(), set()

    def cb(blob, _metadata):
        oid = blob.original_id
        if not oid:
            return
        oid = oid.decode("ascii")
        novo = mapa.get(oid)
        if novo is None:
            return
        vistos.add(oid)
        if blob.data != novo:
            blob.data = novo
            trocados.add(oid)

    antes = os.getcwd()
    os.chdir(repo)
    try:
        args = fr.FilteringOptions.parse_args(
            ["--force", "--quiet", "--replace-refs", "delete-no-add", "--prune-empty", "never",
             "--prune-degenerate", "never", "--mailmap", mailmap],
            error_on_empty=False)
        with contextlib.redirect_stdout(io.StringIO()):
            fr.RepoFilter(args, blob_callback=cb).run()
    except SystemExit as e:
        raise ErroReescrita("o git-filter-repo terminou com erro (%s)" % (e.code,))
    finally:
        os.chdir(antes)
    return vistos, trocados


def ler_commit_map(caminho):
    mapa = {}
    with open(caminho, encoding="ascii") as f:
        next(f, None)  # cabeçalho "old new"
        for linha in f:
            p = linha.split()
            if len(p) == 2:
                mapa[p[0]] = p[1]
    return mapa


# ---------------------------------------------------------------- execução

def executar(args):
    repo = validar_espelho(args.repo)
    if not os.path.isfile(args.mailmap):
        raise ErroReescrita("o --mailmap não existe")
    mailmap = os.path.abspath(args.mailmap)
    saida = os.path.abspath(args.saida)

    achados = ler_achados(args.achados)
    mapa, info = montar_mapa(repo, achados)
    ordem = [s for s in _texto(repo, "rev-list", "--topo-order", "--reverse", "--all").split("\n") if s]

    vistos, trocados = rodar_filter_repo(repo, mapa, mailmap)

    meta = os.path.join(repo, "filter-repo")
    for nome in ("commit-map", "ref-map"):
        if not os.path.isfile(os.path.join(meta, nome)):
            raise ErroReescrita("o filter-repo não gravou o %s" % nome)
    os.makedirs(saida, exist_ok=True)
    for nome in ("commit-map", "ref-map"):
        shutil.copyfile(os.path.join(meta, nome), os.path.join(saida, nome))
    renomes = ler_commit_map(os.path.join(meta, "commit-map"))
    mudados = {o for o, n in renomes.items() if o != n}
    primeiro = next((s for s in ordem if s in mudados), None)

    rel = {"blobs_com_achado": info["blobs_com_achado"],
           "blobs_no_mapa": len(mapa),
           "blobs_ausentes_no_espelho": info["blobs_ausentes_no_espelho"],
           "blobs_sem_troca_efetiva": info["blobs_sem_troca_efetiva"],
           "blobs_trocados": len(trocados),
           "blobs_do_mapa_nunca_vistos": sorted(set(mapa) - vistos),
           "achados_lidos": info["achados_lidos"],
           "achados_ignorados": info["achados_ignorados"],
           "commits_total": len(renomes),
           "commits_reescritos": len(mudados),
           "primeiro_commit_alterado": ({"antigo": primeiro, "novo": renomes[primeiro]} if primeiro else None)}
    with open(os.path.join(saida, "reescrita.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("blobs no mapa: %d | trocados: %d | nunca vistos: %d | sem troca efetiva: %d | ausentes: %d"
          % (rel["blobs_no_mapa"], rel["blobs_trocados"], len(rel["blobs_do_mapa_nunca_vistos"]),
             len(rel["blobs_sem_troca_efetiva"]), rel["blobs_ausentes_no_espelho"]))
    print("commits: %d de %d reescritos | primeiro alterado: %s"
          % (rel["commits_reescritos"], rel["commits_total"],
             rel["primeiro_commit_alterado"]["antigo"] if primeiro else "nenhum"))
    return 0


def _parser():
    p = argparse.ArgumentParser(description="Reescreve o histórico de um espelho bare (sem imprimir valores).")
    p.add_argument("--repo", required=True, help="espelho bare, em .../dados/fase-5/espelho/")
    p.add_argument("--achados", required=True, help="achados.jsonl do varrer_historico.py")
    p.add_argument("--mailmap", required=True, help="arquivo mailmap para o filter-repo")
    p.add_argument("--saida", required=True, help="diretório para reescrita.json, commit-map e ref-map")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        return executar(args)
    except ErroReescrita as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
