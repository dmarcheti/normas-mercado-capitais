#!/usr/bin/env python3
"""Bateria de perguntas sobre julgados: respostas sem e com acervo (Sonnet) e juiz cego (Opus).

  python3 scripts/bateria.py responder [--gabarito G] [--ids P01,P07] [--saida DIR]
                                       [--plugins-de PASTA] [--modos sem,com]
  python3 scripts/bateria.py julgar    [--gabarito G] [--ids ...] [--saida DIR] [--semente N]

Protocolo da Fase 3b/5, sem mudança:
- resposta "sem": `claude -p --model sonnet --tools ""` (sem acervo);
- resposta "com": `--model sonnet --tools Read,Skill --allowedTools Read,Skill` com os 6 plugins
  (`--plugin-dir`), copiados para `<saida>/plugins/` na primeira vez (a bateria usa a cópia);
- juiz: `--model opus --tools ""`, cego ao modo, ids "Jnn" embaralhados com a semente.
Retomável: pula resposta ou nota já gravada. A saída (`dados/fase-5/bateria-v3/` por padrão) fica
em `dados/`, fora do Git. Roda `claude` de verdade: não é chamada pelos testes; os testes cobrem
só `montar_args`, `selecionar_ids`, `ids_cegos` e `tarefas_de_resposta`.

Só biblioteca padrão.
"""
import argparse
import concurrent.futures
import json
import os
import random
import shutil
import subprocess
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PLUGINS = ["normas", "julgados-pas", "julgados-tc-crsfn", "julgados-colegiado-2002-2008",
           "julgados-colegiado-2009-2015", "julgados-colegiado-2016-2026"]
GABARITO_PADRAO = os.path.join(REPO, "dados", "fase-3b", "bateria-v2-gabarito.json")
SAIDA_PADRAO = os.path.join(REPO, "dados", "fase-5", "bateria-v3")
SEMENTE_PADRAO = 20261103
MODOS = ("sem", "com")
EM_PARALELO = 4

JUIZ = """Você corrige a resposta de um assistente a uma pergunta sobre julgados da CVM e do CRSFN.
Compare com o gabarito, conferido na fonte oficial. Não use outra fonte; não busque nada.

Pergunta: {pergunta}

Gabarito: {gabarito}
{nota}
Ressalvas esperadas: {ressalvas}

Resposta a corrigir:
<<<
{resposta}
>>>

Dê 0 ou 1 em cada critério:
- caso: identifica o(s) caso(s) certo(s) (processo e data, ou, nas perguntas fora do escopo, recusa ou diz que o acervo não cobre, sem inventar caso);
- conteudo: o que foi decidido e por quê está certo e sem erro relevante (valor, resultado, quem foi condenado ou absolvido); nas fora do escopo, não inventa decisão, acórdão nem relator;
- ressalvas: traz as ressalvas que importam para esta pergunta (ementa extraída não oficial, redação da norma à época, possível reforma no CRSFN, julgado não vincula como norma), ou, se nenhuma for essencial, não afirma o contrário delas.
Responda só com JSON numa linha: {{"caso": 0|1, "conteudo": 0|1, "ressalvas": 0|1, "motivo": "uma frase"}}"""


# ---- funções puras (testadas)

def montar_args(modo, pasta_plugins=None):
    """Argumentos do `claude -p` para a resposta no `modo` ("sem" ou "com"). No modo "com",
    `pasta_plugins` é a pasta com os 6 plugins copiados."""
    if modo == "sem":
        return ["--model", "sonnet", "--tools", ""]
    if modo != "com":
        raise ValueError("modo desconhecido: %r (use sem ou com)" % (modo,))
    if not pasta_plugins:
        raise ValueError("o modo com precisa da pasta dos plugins")
    args = ["--model", "sonnet", "--tools", "Read,Skill", "--allowedTools", "Read,Skill"]
    for p in PLUGINS:
        args += ["--plugin-dir", os.path.join(pasta_plugins, p)]
    return args


def montar_args_juiz():
    return ["--model", "opus", "--tools", ""]


def comando_claude(args):
    return ["claude", "-p", "--output-format", "stream-json", "--verbose",
            "--no-session-persistence", "--strict-mcp-config"] + list(args)


def selecionar_ids(gabarito, ids=None):
    """Ids das perguntas a rodar, na ordem do gabarito. `ids` é "P01,P07" (ou lista); vazio ou
    "todos" = todas. Id fora do gabarito é erro (não ignora em silêncio)."""
    if isinstance(ids, str):
        ids = [x.strip() for x in ids.split(",") if x.strip()]
    if not ids or [x.lower() for x in ids] == ["todos"]:
        return list(gabarito)
    faltam = [x for x in ids if x not in gabarito]
    if faltam:
        raise ValueError("id fora do gabarito: %s" % ", ".join(faltam))
    return [p for p in gabarito if p in set(ids)]


def tarefas_de_resposta(gabarito, ids, modos, existentes=()):
    """[(id, modo)] ainda por fazer: o par cujo arquivo `<id>-<modo>.json` não está em `existentes`."""
    feitos = set(existentes)
    return [(pid, modo) for pid in ids for modo in modos if "%s-%s.json" % (pid, modo) not in feitos]


def ids_cegos(arquivos, semente=SEMENTE_PADRAO):
    """{arquivo de resposta: "Jnn"}: ids embaralhados pela semente, para o juiz não saber o modo."""
    arquivos = sorted(arquivos)
    ids = ["J%02d" % i for i in range(1, len(arquivos) + 1)]
    random.Random(semente).shuffle(ids)
    return dict(zip(arquivos, ids))


def modos_de(texto):
    modos = tuple(x.strip() for x in texto.split(",") if x.strip())
    for m in modos:
        if m not in MODOS:
            raise ValueError("modo desconhecido: %r (use sem, com ou sem,com)" % (m,))
    return modos or MODOS


# ---- execução (chama o `claude`)

def _claude(args, prompt, cwd, timeout=1800):
    r = subprocess.run(comando_claude(args), input=prompt, cwd=cwd, capture_output=True, text=True,
                       timeout=timeout)
    final, ferr, custo = "", 0, 0.0
    for ln in r.stdout.splitlines():
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        if ev.get("type") == "result":
            final, custo = ev.get("result") or "", ev.get("total_cost_usd") or 0.0
        msg = ev.get("message") or {}
        if isinstance(msg, dict):
            ferr += sum(1 for c in msg.get("content") or []
                        if isinstance(c, dict) and c.get("type") == "tool_use")
    return final, ferr, custo, r.stdout


def _ler_gabarito(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def responder(gab, ids, modos, saida, plugins_de):
    pl = os.path.join(saida, "plugins")
    if "com" in modos and not os.path.isdir(pl):
        for p in PLUGINS:
            shutil.copytree(os.path.join(plugins_de, p), os.path.join(pl, p))
    vazia = os.path.join(saida, "vazia")
    resp = os.path.join(saida, "respostas")
    os.makedirs(vazia, exist_ok=True)
    os.makedirs(resp, exist_ok=True)
    tarefas = tarefas_de_resposta(gab, ids, modos, os.listdir(resp))

    def um(t):
        pid, modo = t
        destino = os.path.join(resp, "%s-%s.json" % (pid, modo))
        final, ferr, custo, bruto = _claude(montar_args(modo, pl), gab[pid]["pergunta"], vazia)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump({"pergunta": pid, "modo": modo, "resposta": final, "ferramentas_usadas": ferr,
                       "custo_usd": custo}, f, ensure_ascii=False, indent=1)
        with open(destino[:-5] + ".jsonl", "w", encoding="utf-8") as f:
            f.write(bruto)
        return pid, modo, ferr, custo

    with concurrent.futures.ThreadPoolExecutor(EM_PARALELO) as ex:
        for r in ex.map(um, tarefas):
            print("%s %s ferramentas=%d custo=%.2f" % r, flush=True)


def julgar(gab, ids, saida, semente):
    resp = os.path.join(saida, "respostas")
    notas = os.path.join(saida, "notas")
    os.makedirs(notas, exist_ok=True)
    arquivos = sorted(f for f in os.listdir(resp) if f.endswith(".json")
                      and f.rsplit("-", 1)[0] in set(ids))
    mapa = ids_cegos(arquivos, semente)
    with open(os.path.join(saida, "mapa-cego.json"), "w", encoding="utf-8") as f:
        json.dump(mapa, f, indent=1)
    vazia = os.path.join(saida, "vazia")
    os.makedirs(vazia, exist_ok=True)

    def um(arq):
        destino = os.path.join(notas, mapa[arq] + ".json")
        if os.path.exists(destino):
            return mapa[arq], "pulado"
        with open(os.path.join(resp, arq), encoding="utf-8") as f:
            r = json.load(f)
        v = gab[r["pergunta"]]
        prompt = JUIZ.format(pergunta=v["pergunta"], gabarito=v["gabarito"],
                             nota=("Nota da conferência: " + v["nota"] + "\n") if v.get("nota") else "",
                             ressalvas=v["ressalvas"], resposta=r["resposta"])
        final, _, custo, _ = _claude(montar_args_juiz(), prompt, vazia)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump({"id_cego": mapa[arq], "saida": final, "custo_usd": custo}, f,
                      ensure_ascii=False, indent=1)
        return mapa[arq], "ok %.2f" % custo

    with concurrent.futures.ThreadPoolExecutor(EM_PARALELO) as ex:
        for r in ex.map(um, arquivos):
            print(*r, flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("comando", choices=("responder", "julgar"))
    ap.add_argument("--gabarito", default=GABARITO_PADRAO, help="JSON {id: {pergunta, gabarito, ressalvas, nota}}")
    ap.add_argument("--ids", default="todos", help="ids separados por vírgula, ou todos")
    ap.add_argument("--saida", default=SAIDA_PADRAO, help="pasta de saída (fora do Git)")
    ap.add_argument("--plugins-de", default=os.path.join(REPO, "plugins"),
                    help="pasta com os 6 plugins a copiar para a bateria")
    ap.add_argument("--modos", default="sem,com")
    ap.add_argument("--semente", type=int, default=SEMENTE_PADRAO, help="semente do embaralhamento do juiz")
    a = ap.parse_args(argv)
    gab = _ler_gabarito(a.gabarito)
    try:
        ids = selecionar_ids(gab, a.ids)
        modos = modos_de(a.modos)
    except ValueError as e:
        print("bateria: %s" % e, file=sys.stderr)
        return 2
    if a.comando == "responder":
        responder(gab, ids, modos, a.saida, a.plugins_de)
    else:
        julgar(gab, ids, a.saida, a.semente)
    return 0


if __name__ == "__main__":
    sys.exit(main())
