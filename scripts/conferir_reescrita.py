#!/usr/bin/env python3
"""Gate da reescrita do histórico: compara o repositório original com o espelho reescrito.

Uso:
    conferir_reescrita.py --antes REPO_ORIGINAL --ref-antes fase-5 --depois ESPELHO.git --commit-map ARQ

Confere (todos têm de passar):
 a. a árvore da ponta é idêntica (`<ref-antes>^{tree}` == `main^{tree}` do espelho);
 b. todo commit anterior ao primeiro commit reescrito mantém o sha (pelo commit-map: old == new), e
    todo commit de `<ref-antes>` tem entrada no commit-map;
 c. todo commit de autor "Historico normativo (replay)" tem, depois, a mesma data de autor, a mesma
    mensagem e a mesma árvore de `plugins/normas/`;
 d. em todo commit, a árvore de `plugins/normas/` é igual antes e depois, e o que mudou fora dela
    está só em `plugins/julgados-*/` (layout antigo) ou `julgados/`;
 e. nenhum commit do espelho (nem tag anotada) tem e-mail de autor, committer ou tagger fora de
    `@users.noreply.github.com`, `.invalid` ou `noreply@github.com`;
 f. cada tag `v*` do original existe no espelho e aponta para o commit mapeado da tag original.

Saída: só shas, nomes de tag e contagens; nenhum e-mail, nome ou trecho de arquivo. Saída do
processo: 0 se tudo passar; 1 com a lista do que falhou; 2 em erro de execução.
"""
import argparse
import os
import re
import subprocess
import sys

REPLAY = "Historico normativo (replay)"
NORMAS = "plugins/normas"
# o histórico guarda os julgados em plugins/julgados-*/ (até a Fase 6) e em julgados/ (depois)
JULGADOS = re.compile(r"^(?:plugins/julgados-[^/]+(?:/|$)|julgados(?:/|$))")
EMAIL_OK = re.compile(r"(@users\.noreply\.github\.com|\.invalid)$|^noreply@github\.com$", re.I)
ZEROS = "0" * 40
LIMITE = 20  # shas listados por verificação


class ErroConferencia(Exception):
    pass


# ---------------------------------------------------------------- git

def _bytes(repo, *args, entrada=None, ok=(0,)):
    r = subprocess.run(["git", "-C", repo] + list(args), input=entrada, capture_output=True)
    if r.returncode not in ok:
        raise ErroConferencia("git %s falhou (código %d)" % (args[0], r.returncode))
    return r.stdout


def _texto(repo, *args, **kw):
    return _bytes(repo, *args, **kw).decode("utf-8", "replace").strip()


def _verificar_repo(repo, rotulo):
    if not os.path.isdir(repo):
        raise ErroConferencia("%s não existe" % rotulo)
    _bytes(repo, "rev-parse", "--git-dir")


def _resolver(repo, ref):
    r = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", ref], capture_output=True)
    return r.stdout.decode().strip() if r.returncode == 0 else None


def ler_commit_map(caminho):
    if not os.path.isfile(caminho):
        raise ErroConferencia("o commit-map não existe")
    mapa = {}
    with open(caminho, encoding="ascii") as f:
        next(f, None)  # cabeçalho
        for linha in f:
            p = linha.split()
            if len(p) == 2:
                mapa[p[0]] = p[1]
    if not mapa:
        raise ErroConferencia("o commit-map está vazio")
    return mapa


def dados_dos_commits(repo, shas):
    """{sha: (autor, data do autor, mensagem, árvore raiz)} para os commits existentes no repo."""
    if not shas:
        return {}
    out = _bytes(repo, "log", "--stdin", "--no-walk=unsorted", "--date=raw",
                 "--format=%H%x1f%an%x1f%ad%x1f%T%x1f%B%x1e",
                 entrada=("\n".join(shas) + "\n").encode())
    dados = {}
    for reg in out.decode("utf-8", "replace").split("\x1e"):
        reg = reg.lstrip("\n")
        if not reg:
            continue
        h, autor, data, arvore, msg = reg.split("\x1f", 4)
        dados[h] = (autor, data, msg, arvore)
    return dados


def arvores_normas(repo, shas):
    """{sha: sha da árvore plugins/normas ou None se não existir}."""
    if not shas:
        return {}
    entrada = "".join("%s:%s\n" % (s, NORMAS) for s in shas).encode()
    out = _bytes(repo, "cat-file", "--batch-check", entrada=entrada).decode().split("\n")
    saida = {}
    for s, linha in zip(shas, out):
        saida[s] = None if linha.endswith(" missing") else linha.split(" ")[0]
    return saida


class Diferencas:
    """Caminhos que diferem entre duas árvores de repositórios distintos (comparação por sha)."""

    def __init__(self, antes, depois):
        self.repos = {"a": antes, "d": depois}
        self._ls = {}
        self._memo = {}

    def _listar(self, lado, sha):
        chave = (lado, sha)
        if chave not in self._ls:
            out = _bytes(self.repos[lado], "ls-tree", "-z", sha)
            itens = {}
            for reg in out.split(b"\0"):
                if not reg:
                    continue
                meta, nome = reg.split(b"\t", 1)
                modo, tipo, oid = meta.decode().split(" ")
                itens[nome.decode("utf-8", "surrogateescape")] = (modo, tipo, oid)
            self._ls[chave] = itens
        return self._ls[chave]

    def caminhos(self, arv_a, arv_d, prefixo=""):
        if arv_a == arv_d:
            return []
        chave = (arv_a, arv_d, prefixo)
        if chave in self._memo:
            return self._memo[chave]
        a, d = self._listar("a", arv_a), self._listar("d", arv_d)
        res = []
        for nome in sorted(set(a) | set(d)):
            ea, ed = a.get(nome), d.get(nome)
            caminho = prefixo + nome
            if ea == ed:
                continue
            if ea and ed and ea[1] == "tree" and ed[1] == "tree":
                res += self.caminhos(ea[2], ed[2], caminho + "/")
            else:
                res.append(caminho)
        self._memo[chave] = res
        return res


# ---------------------------------------------------------------- verificações

def _lista(shas):
    shas = sorted(shas)
    txt = " ".join(shas[:LIMITE])
    return txt + (" ... (+%d)" % (len(shas) - LIMITE) if len(shas) > LIMITE else "")


def conferir(antes, ref_antes, depois, commit_map, ref_depois="main"):
    """Devolve {letra: [falhas]} (lista vazia = passou)."""
    _verificar_repo(antes, "o repo --antes")
    _verificar_repo(depois, "o espelho --depois")
    cmap = ler_commit_map(commit_map)
    res = {k: [] for k in "abcdef"}

    # a. árvore da ponta
    ta, td = _resolver(antes, ref_antes + "^{tree}"), _resolver(depois, ref_depois + "^{tree}")
    if ta is None:
        raise ErroConferencia("--ref-antes não resolve no repo original")
    if td is None:
        raise ErroConferencia("%s não resolve no espelho" % ref_depois)
    if ta != td:
        res["a"].append("a árvore da ponta difere (antes %s, depois %s)" % (ta, td))

    # b. commits anteriores ao primeiro reescrito
    ordem = [s for s in _texto(antes, "rev-list", "--topo-order", "--reverse", ref_antes).split("\n") if s]
    sem_entrada = [s for s in ordem if s not in cmap]
    if sem_entrada:
        res["b"].append("%d commit(s) de %s sem entrada no commit-map: %s"
                        % (len(sem_entrada), ref_antes, _lista(sem_entrada)))
    primeiro = next((s for s in ordem if s in cmap and cmap[s] != s), None)
    if primeiro:
        antes_do_primeiro = ordem[:ordem.index(primeiro)]
        mudou = [s for s in antes_do_primeiro if s in cmap and cmap[s] != s]
        if mudou:  # só ocorreria se a ordem mudasse; deixa a verificação explícita
            res["b"].append("commit(s) anteriores ao primeiro reescrito mudaram: %s" % _lista(mudou))

    # universo de c, d, e: os commits do commit-map
    removidos = sorted(o for o, n in cmap.items() if n == ZEROS)
    if removidos:
        res["d"].append("%d commit(s) removido(s) pelo filter-repo: %s" % (len(removidos), _lista(removidos)))
    pares = sorted((o, n) for o, n in cmap.items() if n != ZEROS)
    velhos, novos = [o for o, _ in pares], [n for _, n in pares]
    da, dd = dados_dos_commits(antes, velhos), dados_dos_commits(depois, novos)
    ausentes = [o for o, n in pares if o not in da or n not in dd]
    if ausentes:
        res["d"].append("%d commit(s) do mapa ausentes no original ou no espelho: %s"
                        % (len(ausentes), _lista(ausentes)))
    pares = [(o, n) for o, n in pares if o in da and n in dd]
    na, nd = arvores_normas(antes, [o for o, _ in pares]), arvores_normas(depois, [n for _, n in pares])

    # c. commits de replay
    c_data, c_msg, c_norm = [], [], []
    for o, n in pares:
        if da[o][0] != REPLAY:
            continue
        if da[o][1] != dd[n][1]:
            c_data.append(o)
        if da[o][2] != dd[n][2]:
            c_msg.append(o)
        if na[o] != nd[n]:
            c_norm.append(o)
    for rotulo, lst in (("data de autor", c_data), ("mensagem", c_msg), ("árvore de plugins/normas", c_norm)):
        if lst:
            res["c"].append("%d commit(s) de replay com %s diferente: %s" % (len(lst), rotulo, _lista(lst)))

    # d. normas igual em todo commit; fora dela, só julgados
    d_norm = [o for o, n in pares if na[o] != nd[n]]
    if d_norm:
        res["d"].append("%d commit(s) com árvore de plugins/normas diferente: %s" % (len(d_norm), _lista(d_norm)))
    dif, d_fora, exemplos = Diferencas(antes, depois), [], set()
    for o, n in pares:
        for caminho in dif.caminhos(da[o][3], dd[n][3]):
            if caminho == NORMAS or caminho.startswith(NORMAS + "/") or JULGADOS.match(caminho):
                continue
            d_fora.append(o)
            exemplos.add("/".join(caminho.split("/")[:2]))
            break
    if d_fora:
        res["d"].append("%d commit(s) com mudança fora de plugins/julgados-*/ e julgados/ (em %s): %s"
                        % (len(d_fora), ", ".join(sorted(exemplos)[:5]), _lista(d_fora)))

    # e. e-mails no espelho
    ruins = set()
    for linha in _texto(depois, "log", "--all", "--format=%H %ae %ce").split("\n"):
        if not linha:
            continue
        h, *emails = linha.split(" ")
        if len(emails) != 2 or not all(e and EMAIL_OK.search(e) for e in emails):
            ruins.add(h)
    if ruins:
        res["e"].append("%d commit(s) com e-mail de autor ou committer fora da lista: %s"
                        % (len(ruins), _lista(ruins)))
    tags_ruins = []
    for linha in _texto(depois, "for-each-ref", "--format=%(refname:short)\x1f%(taggeremail)",
                        "refs/tags").split("\n"):
        if not linha:
            continue
        nome, _, email = linha.partition("\x1f")
        email = email.strip("<>")
        if email and not EMAIL_OK.search(email):
            tags_ruins.append(nome)
    if tags_ruins:
        res["e"].append("%d tag(s) com e-mail de tagger fora da lista: %s"
                        % (len(tags_ruins), " ".join(sorted(tags_ruins))))

    # f. tags v*
    tags = [t for t in _texto(antes, "for-each-ref", "--format=%(refname:short)", "refs/tags/v*").split("\n") if t]
    for t in tags:
        orig = _resolver(antes, "refs/tags/%s^{commit}" % t)
        novo = _resolver(depois, "refs/tags/%s^{commit}" % t)
        if novo is None:
            res["f"].append("a tag %s não existe no espelho" % t)
        elif orig not in cmap:
            res["f"].append("o commit da tag %s não está no commit-map" % t)
        elif novo != cmap[orig]:
            res["f"].append("a tag %s não aponta para o commit mapeado" % t)
    return res


DESCRICOES = {
    "a": "árvore da ponta idêntica",
    "b": "commits anteriores ao primeiro reescrito mantêm o sha",
    "c": "commits de replay: data, mensagem e plugins/normas",
    "d": "plugins/normas igual e mudanças só em plugins/julgados-*/ ou julgados/",
    "e": "e-mails de autor, committer e tagger",
    "f": "tags v* apontam para o commit mapeado",
}


def _parser():
    p = argparse.ArgumentParser(description="Confere a reescrita do histórico (gate da Fase 5).")
    p.add_argument("--antes", required=True, help="repo original")
    p.add_argument("--ref-antes", required=True, help="ref do original que corresponde à main do espelho")
    p.add_argument("--depois", required=True, help="espelho reescrito (bare)")
    p.add_argument("--commit-map", required=True, help="commit-map gravado pelo filter-repo")
    p.add_argument("--ref-depois", default="main", help="ref do espelho (padrão: main)")
    return p


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        res = conferir(args.antes, args.ref_antes, args.depois, args.commit_map, args.ref_depois)
    except ErroConferencia as e:
        print("erro: %s" % e, file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - exceção conta como falha de execução, nunca como ok
        print("erro: %s" % type(e).__name__, file=sys.stderr)
        return 2
    falhou = False
    for k in "abcdef":
        if res[k]:
            falhou = True
            print("[FALHOU] %s. %s" % (k, DESCRICOES[k]))
            for f in res[k]:
                print("    - %s" % f)
        else:
            print("[ok] %s. %s" % (k, DESCRICOES[k]))
    print("RESULTADO: %s" % ("FALHOU" if falhou else "PASSOU"))
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
