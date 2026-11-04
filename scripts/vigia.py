#!/usr/bin/env python3
"""Vigia do job quinzenal (Fase 4, C11), para a Action `vigia.yml`: sem rede para as fontes, sem LLM.

Uso: ULTIMA_VERIFICACAO=<ISO> ULTIMO_STATUS=<status> EXECUCOES_SEM_OK=<n> python3 scripts/vigia.py
       [--hoje AAAA-MM-DD] [--abrir]

Problemas:
- heartbeat (`vars.ULTIMA_VERIFICACAO`, gravado pelo job) ausente ou com mais de 16 dias (14 da
  agenda quinzenal + 2 de folga); o job só grava o heartbeat quando roda, não nas checagens
  diárias fora da agenda;
- job fora de "ok" em 2 execuções seguidas ou mais (`vars.EXECUCOES_SEM_OK`, contado pelo job, com
  o `vars.ULTIMO_STATUS` no corpo): o job grava o heartbeat mesmo quando falha, e só a data
  esconderia a falha;
- plugin com conteúdo diferente do hash em `fontes/versoes-plugins.json` (o mesmo
  `publicar.hash_plugin`) há mais de 16 dias (o publicar roda a cada 14 dias, mais 2 de folga). "Há quanto tempo": data do primeiro commit que tocou
  o plugin depois do último commit do registro (`git log`, checkout com histórico completo).
Imprime um problema por linha. Com `--abrir`, abre uma issue `vigia` por problema pelo `gh`,
sem duplicar título já aberto. Saída 0 sempre que conseguiu verificar; 2 em erro.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import publicar as pub  # noqa: E402

DIAS_HEARTBEAT = 16  # 14 (quinzenal) + 2 de folga
DIAS_VERSAO = 16  # publicar quinzenal (14) + 2 de folga
EXECUCOES_SEM_OK = 2


def _git(raiz, *args):
    r = subprocess.run(["git"] + list(args), cwd=raiz, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def desde_quando(raiz, plugin_rel, git=_git):
    """Data (AAAA-MM-DD) do primeiro commit que tocou o plugin depois do último commit do registro."""
    base = git(raiz, "log", "-1", "--format=%H", "--", pub.REGISTRO).strip()
    if not base:
        return None
    datas = git(raiz, "log", "--reverse", "--format=%cs", "%s..HEAD" % base, "--", plugin_rel).split()
    return datas[0] if datas else git(raiz, "log", "-1", "--format=%cs", base).strip() or None


def problemas(raiz, hoje, ultima, git=_git, status=None, execucoes_sem_ok=None):
    hoje_d = datetime.date.fromisoformat(hoje)
    saida = []
    try:
        ult = datetime.datetime.fromisoformat(ultima).date() if ultima else None
    except ValueError:
        ult = None
    if ult is None:
        saida.append(("vigia: heartbeat ausente", "ULTIMA_VERIFICACAO vazia ou ilegível (%r)." % ultima))
    elif (hoje_d - ult).days > DIAS_HEARTBEAT:
        saida.append(("vigia: heartbeat parado", "Última verificação do job em %s, há %d dias (limite %d)."
                      % (ult, (hoje_d - ult).days, DIAS_HEARTBEAT)))
    try:
        n = int(execucoes_sem_ok) if execucoes_sem_ok not in (None, "") else None
    except ValueError:
        n = None
        saida.append(("vigia: EXECUCOES_SEM_OK ilegível",
                      "EXECUCOES_SEM_OK = %r (status %r)." % (execucoes_sem_ok, status)))
    if n is not None and n >= EXECUCOES_SEM_OK:
        saida.append(("vigia: job fora de ok", "O job ficou fora de \"ok\" em %d execuções seguidas "
                      "(limite %d); último status: %s. Ver a issue job-falhou e o log em ~/normas-auto/logs/."
                      % (n, EXECUCOES_SEM_OK, status or "?")))
    for nome, vr, va in pub.divergentes(raiz):
        rel = None
        for n, pasta, _ in pub.plugins_do_marketplace(raiz):
            if n == nome:
                rel = os.path.relpath(pasta, raiz)
        d = desde_quando(raiz, rel, git)
        dias = (hoje_d - datetime.date.fromisoformat(d)).days if d else None
        if dias is None or dias > DIAS_VERSAO:
            saida.append(("vigia: %s sem versão nova" % nome,
                          "Conteúdo de %s diferente do hash da versão %s desde %s (%s dias; limite %d)."
                          % (nome, vr, d or "data desconhecida", dias if dias is not None else "?", DIAS_VERSAO)))
    return saida


def abrir(titulo, corpo):
    r = subprocess.run(["gh", "issue", "list", "--state", "open", "--label", "vigia", "--json", "title"],
                       capture_output=True, text=True)
    if r.returncode == 0 and any(i.get("title") == titulo for i in json.loads(r.stdout or "[]")):
        return
    subprocess.run(["gh", "label", "create", "vigia", "--color", "b60205"], capture_output=True)
    r = subprocess.run(["gh", "issue", "create", "--title", titulo, "--label", "vigia", "--body", corpo],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("gh issue create rc %d: %s" % (r.returncode, (r.stderr or r.stdout).strip()[-300:]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raiz", default=pub.REPO)
    ap.add_argument("--hoje", default=datetime.date.today().isoformat())
    ap.add_argument("--abrir", action="store_true")
    a = ap.parse_args(argv)
    try:
        achados = problemas(a.raiz, a.hoje, os.environ.get("ULTIMA_VERIFICACAO", ""),
                            status=os.environ.get("ULTIMO_STATUS", ""),
                            execucoes_sem_ok=os.environ.get("EXECUCOES_SEM_OK", ""))
    except Exception as e:  # noqa: BLE001
        print("vigia: erro: %s: %s" % (type(e).__name__, e))
        return 2
    rc = 0
    for titulo, corpo in achados:
        print("%s: %s" % (titulo, corpo))
        if a.abrir:
            try:
                abrir(titulo, corpo)
            except (OSError, ValueError, RuntimeError) as e:
                print("vigia: não abriu a issue %r: %s" % (titulo, e))
                rc = 1
    if not achados:
        print("vigia: ok")
    return rc


if __name__ == "__main__":
    sys.exit(main())
