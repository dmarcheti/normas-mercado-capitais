#!/usr/bin/env python3
"""Plano do histórico de commits do acervo: um ato = um commit, na ordem do DOU.

Cada cadeia (dados/replay-NNNN/commits.json) é uma lista, em ordem, de
{"ato": 162, "tipo": "original" | "alteracao" | "retificacao", "data_dou": "AAAA-MM-DD",
 "mensagem": "...", "arquivos": {"<caminho no repo>": "<caminho em dados/>"}}.
Um ato que mexe em várias normas aparece em várias cadeias e vira um commit só.

planejar_commits(cadeias, alteradoras) -> lista de commits, ordenada por
(data_dou, ato, tipo) com original antes de alteração e de retificação; retificações
do mesmo ato em datas diferentes são commits distintos. Num commit
de `alteracao` entra também o arquivo do ato (`alteradoras[ato]`, já no repo).
comandos_git(commit) -> [["git", "add", ...], ["env", "GIT_...", ..., "git", "commit", ...]];
só devolve as listas, não executa nada. A identidade é a de replay e a data é a do
DOU às 12:00:00 -0300.

Uso: python3 scripts/montar_historico.py --simular [--alteradoras DIR] [commits.json ...]
Sem commits.json, lê dados/replay-*/commits.json. --simular só imprime o plano.
Sem --simular o script recusa rodar (saída 2): a reescrita do histórico é feita à
mão, com o ok do Diogo (plano da Fase 2, Task 6). Saída 0 = ok; 2 = uso/erro.
"""
import copy
import glob
import json
import os
import re
import sys
from datetime import datetime

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ALTERADORAS = "plugins/normas/normas/cvm/alteradoras"
AUTOR_NOME = "Historico normativo (replay)"
AUTOR_EMAIL = "replay@normas-mercado-capitais.invalid"
FUSO = "-0300"
HORA = "12:00:00"
TIPOS = ("original", "alteracao", "retificacao")  # ordem de desempate no mesmo ato


def _erro_entrada(i, texto):
    return ValueError("entrada %d: %s" % (i, texto))


def _validar_entrada(e, i):
    if not isinstance(e, dict):
        raise _erro_entrada(i, "esperado um objeto")
    if "ato" not in e or "tipo" not in e:
        raise _erro_entrada(i, "formato antigo (sem ato e tipo); refaça o commits.json no formato novo")
    if not isinstance(e["ato"], int) or isinstance(e["ato"], bool):
        raise _erro_entrada(i, "ato deve ser inteiro, veio %r" % (e["ato"],))
    if e["tipo"] not in TIPOS:
        raise _erro_entrada(i, "tipo deve ser %s, veio %r" % (" | ".join(TIPOS), e["tipo"]))
    try:
        datetime.strptime(e.get("data_dou", ""), "%Y-%m-%d")
    except (TypeError, ValueError):
        raise _erro_entrada(i, "data_dou deve ser AAAA-MM-DD, veio %r" % (e.get("data_dou"),))
    if not isinstance(e.get("mensagem"), str) or not e["mensagem"].strip():
        raise _erro_entrada(i, "mensagem vazia")
    arquivos = e.get("arquivos")
    if (not isinstance(arquivos, dict) or not arquivos
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in arquivos.items())):
        raise _erro_entrada(i, "arquivos deve ser {caminho no repo: caminho em dados/}, não vazio")


def carregar_cadeia(caminho):
    """Lê um commits.json e confere o formato; ValueError se estiver fora dele."""
    with open(caminho, encoding="utf-8") as f:
        entradas = json.load(f)
    if not isinstance(entradas, list):
        raise ValueError("%s: esperada uma lista de entradas" % caminho)
    for i, e in enumerate(entradas):
        try:
            _validar_entrada(e, i)
        except ValueError as erro:
            raise ValueError("%s: %s" % (caminho, erro))
    return entradas


def _juntar(commit, e):
    if e["data_dou"] != commit["data_dou"] or e["mensagem"] != commit["mensagem"]:
        raise ValueError("ato %d (%s) com data ou mensagem diferentes entre as cadeias" % (e["ato"], e["tipo"]))
    for destino, origem in e["arquivos"].items():
        if commit["arquivos"].setdefault(destino, origem) != origem:
            raise ValueError("ato %d: %s com duas origens (%s e %s)" % (
                e["ato"], destino, commit["arquivos"][destino], origem))


def _chave(e):
    """Retificação: (ato, tipo, data_dou), porque um ato pode ter várias, cada uma
    com o próprio arquivo (NNNN-retificacao-AAAA-MM-DD.md). Os demais: (ato, tipo)."""
    if e["tipo"] == "retificacao":
        return (e["ato"], e["tipo"], e["data_dou"])
    return (e["ato"], e["tipo"])


def planejar_commits(cadeias, alteradoras):
    """Junta as entradas de mesma chave (`_chave`) num commit e ordena. Não altera a entrada."""
    commits = {}
    for cadeia in cadeias:
        for e in copy.deepcopy(cadeia):
            chave = _chave(e)
            if chave not in commits:
                commits[chave] = {"ato": e["ato"], "tipo": e["tipo"], "data_dou": e["data_dou"],
                                  "mensagem": e["mensagem"], "arquivos": {}}
            _juntar(commits[chave], e)
    for chave, commit in commits.items():
        ato, tipo = chave[0], chave[1]
        if tipo == "retificacao":
            arq = "%s/%04d-retificacao-%s.md" % (ALTERADORAS, ato, commit["data_dou"])
            commit["arquivos"][arq] = arq
        if tipo != "alteracao":
            continue
        if ato not in alteradoras:
            raise ValueError("ato %d sem arquivo em alteradoras/" % ato)
        commit["arquivos"][alteradoras[ato]] = alteradoras[ato]
        commit["mensagem"] = _mensagem(commit)
    return sorted(commits.values(), key=lambda c: (c["data_dou"], c["ato"], TIPOS.index(c["tipo"])))


def _lista(numeros):
    nums = [str(n) for n in sorted(numeros)]
    return nums[0] if len(nums) == 1 else "%s e %s" % (", ".join(nums[:-1]), nums[-1])


def _mensagem(commit):
    """A mensagem de alteração lista as resoluções da ementa (o que as cadeias
    escreveram) mais as normas do acervo que o commit toca."""
    m = re.match(r"^(.*: altera Res\. CVM )(.+)$", commit["mensagem"])
    if not m:
        return commit["mensagem"]
    numeros = {int(n) for n in re.findall(r"\d+", m.group(2))}
    for destino in commit["arquivos"]:
        r = re.search(r"/resolucoes/(\d{4})(?:\.md|/)", destino)
        if r:
            numeros.add(int(r.group(1)))
    return m.group(1) + _lista(numeros)


def ambiente_git(commit):
    data = "%s %s %s" % (commit["data_dou"], HORA, FUSO)
    return {
        "GIT_AUTHOR_NAME": AUTOR_NOME, "GIT_AUTHOR_EMAIL": AUTOR_EMAIL, "GIT_AUTHOR_DATE": data,
        "GIT_COMMITTER_NAME": AUTOR_NOME, "GIT_COMMITTER_EMAIL": AUTOR_EMAIL, "GIT_COMMITTER_DATE": data,
    }


def copias_do_commit(commit):
    """[(origem em dados/, destino no repo)] dos arquivos que precisam ser copiados,
    por destino; o que já está no repo (origem == destino) fica de fora."""
    return sorted(((o, d) for d, o in commit["arquivos"].items() if o != d), key=lambda c: c[1])


def comandos_git(commit):
    """Os dois comandos do commit, sem executar. No `git add`, primeiro os arquivos
    copiados e depois os que já estavam no repo (o arquivo do ato), cada grupo ordenado."""
    copiados = sorted(d for d, o in commit["arquivos"].items() if o != d)
    no_repo = sorted(d for d, o in commit["arquivos"].items() if o == d)
    env = ["%s=%s" % kv for kv in sorted(ambiente_git(commit).items())]
    return [
        ["git", "add", "--"] + copiados + no_repo,
        ["env"] + env + ["git", "commit", "-m", commit["mensagem"]],
    ]


def _alteradoras_em(pasta):
    """{ato: caminho no repo} dos NNNN.md de `pasta` (retificações ficam de fora)."""
    atos = {}
    for nome in os.listdir(pasta):
        if re.fullmatch(r"\d{4}\.md", nome):
            atos[int(nome[:4])] = "%s/%s" % (ALTERADORAS, nome)
    return atos


def _imprimir_plano(commits):
    for c in commits:
        print("%s  ato %-4d %-10s %d arquivo(s)  %s" % (
            c["data_dou"], c["ato"], c["tipo"], len(c["arquivos"]), c["mensagem"]))
        for destino in sorted(c["arquivos"]):
            print("    " + destino)
    n = {t: sum(1 for c in commits if c["tipo"] == t) for t in TIPOS}
    print("montar_historico: %d commit(s): %d original(is), %d alteração(ões), %d retificação(ões)" % (
        len(commits), n["original"], n["alteracao"], n["retificacao"]))


def main(argv):
    args = argv[1:]
    simular = "--simular" in args
    if simular:
        args.remove("--simular")
    pasta = os.path.join(RAIZ, *ALTERADORAS.split("/"))
    if "--alteradoras" in args:
        i = args.index("--alteradoras")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        pasta = args[i + 1]
        del args[i:i + 2]
    if not simular:
        print("montar_historico: recusa rodar sem --simular; a reescrita do histórico é feita "
              "à mão, com o ok do Diogo (plano da Fase 2, Task 6)")
        return 2
    caminhos = args or sorted(glob.glob(os.path.join(RAIZ, "dados", "replay-*", "commits.json")))
    if not caminhos:
        print("montar_historico: nenhum commits.json (dados/replay-*/commits.json)")
        return 2
    try:
        cadeias = [carregar_cadeia(c) for c in caminhos]
        commits = planejar_commits(cadeias, _alteradoras_em(pasta))
    except (OSError, ValueError) as e:
        print("montar_historico: %s" % e)
        return 2
    _imprimir_plano(commits)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
