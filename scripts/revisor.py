"""Revisor por LLM dos julgados novos e das normas alteradas (Task 4 da Fase 4).

Antes do merge automático, um modelo (Sonnet, `claude -p`) lê o que o pipeline acabou de gravar e
marca o que ele deixou errado. O prompt está em scripts/prompts/revisor.md.

Modo julgado: para cada julgado, o frontmatter (tipo, classe, resultado, ementa, ementa_fonte,
tema), a qualificação das partes (as primeiras 80 linhas do texto), o recorte da decisão de
`julgados_extracao.recorte_3b` e o fim do texto (últimas 30 linhas). Alertas: dado-pessoal,
corte-indevido, ementa-contraria, resultado-contrario, texto-truncado, lixo-conversao.

Modo norma: o diff unificado de uma norma e o trecho do ato ou da fonte. Alertas: texto-truncado,
lixo-conversao, dado-pessoal.

    python3 scripts/revisor.py --ids a,b,c
    python3 scripts/revisor.py --arquivos caminho1,caminho2
    python3 scripts/revisor.py --norma-diff a.diff,b.diff [--ato ato-a.txt,ato-b.txt]

Lotes de até 10 itens, cada um numa pasta de trabalho fora do cofre e do repositório (a mesma
execução isolada de `julgados_extracao`: `claude -p --tools Read,Write`). Valida o `saida.json`
(todo id do lote presente, tipos da lista fechada). Item sem resposta válida vira o alerta
`revisor-sem-resposta`, nunca ok. Diff de norma acima de 40.000 caracteres é cortado e o
item sai com o alerta `revisor-parcial`, nunca ok. Imprime {id: {ok, alertas}} em JSON; sai com 1 se algum item
tem alerta. O log stream-json, o custo (total_cost_usd) e a saída de cada lote ficam em
dados/fase-4/revisor/<data-hora>/lote-NNN/. Não roda git.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402

PROMPT = os.path.join(jc.AQUI, "prompts", "revisor.md")
LOGS = os.path.join(jc.RAIZ, "dados", "fase-4", "revisor")
TAMANHO_LOTE = 10
LINHAS_QUALIFICACAO = 80
LINHAS_FIM = 30
MAX_DIFF = 40000
MAX_ATO = 12000
MODELO = "sonnet"

TIPOS_JULGADO = ("dado-pessoal", "corte-indevido", "ementa-contraria", "resultado-contrario",
                 "texto-truncado", "lixo-conversao")
TIPOS_NORMA = ("texto-truncado", "lixo-conversao", "dado-pessoal")
TIPOS = {"julgado": TIPOS_JULGADO, "norma": TIPOS_NORMA}
SEM_RESPOSTA = "revisor-sem-resposta"
PARCIAL = "revisor-parcial"
CAMPOS_FRONTMATTER = ("tipo", "classe", "resultado", "ementa", "ementa_fonte", "tema")


# ---------------------------------------------------------------- itens


def _linhas(texto, n, do_fim=False):
    linhas = [x.rstrip() for x in texto.splitlines()]
    while linhas and not linhas[0].strip():
        linhas.pop(0)
    while linhas and not linhas[-1].strip():
        linhas.pop()
    return "\n".join(linhas[-n:] if do_fim else linhas[:n])


def item_julgado(caminho):
    """Item do modo julgado a partir de um .md gravado pelo conversor."""
    v, corpo = je.ler_julgado(caminho)
    tipo = v.get("tipo", "")
    return {"id": v["id"], "modo": "julgado",
            "frontmatter": {c: v.get(c, "") for c in CAMPOS_FRONTMATTER},
            "qualificacao": _linhas(corpo, LINHAS_QUALIFICACAO),
            "decisao": je.recorte_3b(corpo, tipo),
            "fim": _linhas(corpo, LINHAS_FIM, do_fim=True)}


def _ler(caminho, maximo, rotulo="DIFF"):
    """(texto, cortado): o arquivo, cortado em `maximo` caracteres com o aviso `rotulo`."""
    with open(caminho, encoding="utf-8", errors="replace") as f:
        texto = f.read()
    if len(texto) <= maximo:
        return texto, False
    omitido = len(texto) - maximo
    return (texto[:maximo] + "\n[%s CORTADO PELO SCRIPT: %d caracteres omitidos]\n"
            % (rotulo, omitido), True)


def item_norma(caminho_diff, caminho_ato=None):
    """Item do modo norma: o diff unificado e o trecho do ato ou da fonte (opcional)."""
    ato = _ler(caminho_ato, MAX_ATO, "ATO")[0] if caminho_ato else "(não informado)"
    diff, cortado = _ler(caminho_diff, MAX_DIFF)
    return {"id": os.path.splitext(os.path.basename(caminho_diff))[0], "modo": "norma",
            "diff": diff, "ato": ato, "parcial": cortado}


def texto_do_item(item):
    """O arquivo de texto que o modelo lê (um por item; linhas curtas, sem JSON de uma linha só)."""
    out = ["MODO: %s" % item["modo"], "ID: %s" % item["id"], ""]
    if item["modo"] == "julgado":
        out.append("== FRONTMATTER ==")
        out += ["%s: %s" % (c, item["frontmatter"].get(c, "")) for c in CAMPOS_FRONTMATTER]
        out += ["", "== QUALIFICAÇÃO DAS PARTES (primeiras linhas do texto) ==",
                item["qualificacao"],
                "", "== RECORTE DA DECISÃO ==", item["decisao"],
                "", "== FIM DO TEXTO (últimas linhas) ==", item["fim"]]
    else:
        out += ["== DIFF ==", item["diff"], "", "== ATO OU FONTE ==", item["ato"]]
    return "\n".join(out) + "\n"


def montar_lote(itens, pasta):
    """Grava <pasta>/lote.json (índice id → arquivo) e um NN.txt por item; devolve os ids."""
    os.makedirs(pasta, exist_ok=True)
    indice = []
    for n, item in enumerate(itens, 1):
        nome = "%02d.txt" % n
        with open(os.path.join(pasta, nome), "w", encoding="utf-8") as f:
            f.write(texto_do_item(item))
        indice.append({"id": item["id"], "arquivo": nome})
    with open(os.path.join(pasta, "lote.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=1)
    return [x["id"] for x in indice]


def lotes(itens, tamanho=TAMANHO_LOTE):
    ids = [i["id"] for i in itens]
    if len(set(ids)) != len(ids):
        raise ValueError("ids repetidos na entrada: %s" % sorted({i for i in ids if ids.count(i) > 1}))
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


# ---------------------------------------------------------------- validação


def _alerta_sem_resposta(motivo):
    return {"ok": False, "alertas": [{"tipo": SEM_RESPOSTA, "trecho": "", "motivo": motivo}]}


def _item_valido(obj, tipos):
    """(resultado, "") se o objeto é uma resposta válida; (None, motivo) se não."""
    if not isinstance(obj.get("ok"), bool):
        return None, "campo ok ausente ou não booleano"
    alertas = obj.get("alertas")
    if not isinstance(alertas, list):
        return None, "campo alertas ausente ou não é lista"
    limpos = []
    for a in alertas:
        if not isinstance(a, dict):
            return None, "alerta que não é objeto"
        if a.get("tipo") not in tipos:
            return None, "tipo de alerta fora da lista: %r" % (a.get("tipo"),)
        trecho, motivo = a.get("trecho"), a.get("motivo")
        if (not isinstance(trecho, str) or not trecho.strip() or not isinstance(motivo, str)
                or not motivo.strip()):
            return None, "alerta sem trecho ou sem motivo"
        limpos.append({"tipo": a["tipo"], "trecho": trecho, "motivo": motivo.strip()})
    if obj["ok"] and limpos:
        return None, "ok verdadeiro com alertas"
    if not obj["ok"] and not limpos:
        return None, "ok falso sem alertas"
    return {"ok": not limpos, "alertas": limpos}, ""


def validar_saida(ids, saida, modo="julgado"):
    """{id: {ok, alertas}} para todo id de `ids`. Id ausente ou resposta inválida vira o alerta
    `revisor-sem-resposta` (nunca ok). `saida` é o conteúdo do saida.json (ou None)."""
    tipos = TIPOS[modo]
    por_id = {}
    if isinstance(saida, list):
        for obj in saida:
            if isinstance(obj, dict) and isinstance(obj.get("id"), str) and obj["id"] not in por_id:
                por_id[obj["id"]] = obj
    resultado = {}
    for i in ids:
        if saida is None:
            resultado[i] = _alerta_sem_resposta("o revisor não gravou saida.json válido")
        elif i not in por_id:
            resultado[i] = _alerta_sem_resposta("id ausente do saida.json")
        else:
            r, motivo = _item_valido(por_id[i], tipos)
            resultado[i] = r if r is not None else _alerta_sem_resposta("resposta inválida: " + motivo)
    return resultado


def marcar_parcial(resultado, itens):
    """Item que o revisor viu cortado (diff acima de MAX_DIFF) ganha o alerta `revisor-parcial`:
    o que ficou fora do corte não foi revisado, então o item nunca sai ok."""
    for item in itens:
        if item.get("parcial"):
            r = resultado[item["id"]]
            r["ok"] = False
            r["alertas"].append({"tipo": PARCIAL, "trecho": "", "motivo": (
                "o diff passou de %d caracteres e foi cortado: o revisor não viu o resto"
                % MAX_DIFF)})
    return resultado


# ---------------------------------------------------------------- modelo


def _prompt():
    with open(PROMPT, encoding="utf-8") as f:
        texto = f.read()
    return texto + ("\n\n## Tarefa\n\nO lote está em `lote.json`, nesta pasta, e cada item no "
                    "arquivo que ele indica. Grave `saida.json` nesta pasta, conforme as regras "
                    "acima, e nada mais.\n")


def rodar_lote(itens, modelo=MODELO, pasta_log=None, trabalho=None, timeout=900):
    """Roda o modelo numa pasta só com o lote. Devolve ({id: {ok, alertas}}, info). Grava lote,
    saida.json, log.jsonl e execucao.json em `pasta_log`, se informada."""
    modo = itens[0]["modo"]
    ids = [i["id"] for i in itens]
    work = je.pasta_de_trabalho(trabalho)
    info = {"modelo": modelo, "modo": modo, "ids": ids, "codigo": None, "total_cost_usd": None,
            "saida": False, "erro": ""}
    saida = None
    try:
        montar_lote(itens, work)
        if pasta_log:
            os.makedirs(pasta_log, exist_ok=True)
            shutil.copytree(work, os.path.join(pasta_log, "entrada"), dirs_exist_ok=True)
        try:
            r = subprocess.run(je.comando(modelo), input=_prompt(), cwd=work,
                               capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.SubprocessError) as e:
            info["erro"] = "%s: %s" % (type(e).__name__, e)
            r = None
        if r is not None:
            info["codigo"] = r.returncode
            info["total_cost_usd"] = je.custo(r.stdout or "")
            if pasta_log:
                with open(os.path.join(pasta_log, "log.jsonl"), "w", encoding="utf-8") as f:
                    f.write(r.stdout or "")
                if r.stderr:
                    with open(os.path.join(pasta_log, "stderr.txt"), "w", encoding="utf-8") as f:
                        f.write(r.stderr)
        caminho = os.path.join(work, "saida.json")
        if os.path.exists(caminho):
            info["saida"] = True
            try:
                with open(caminho, encoding="utf-8") as f:
                    saida = json.load(f)
            except (ValueError, OSError) as e:
                info["erro"] = info["erro"] or "saida.json ilegível: %s" % e
            if pasta_log:
                shutil.copy(caminho, os.path.join(pasta_log, "saida.json"))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    resultado = marcar_parcial(validar_saida(ids, saida, modo), itens)
    if pasta_log:
        with open(os.path.join(pasta_log, "execucao.json"), "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
    return resultado, info


def revisar(itens, modelo=MODELO, saida=None, trabalho=None, tamanho=TAMANHO_LOTE, paralelo=1,
            timeout=900):
    """Revisa os itens em lotes. Devolve ({id: {ok, alertas}}, [info de cada lote]).
    `saida`: pasta do log (um lote-NNN por lote); None = sem log."""
    if not itens:
        return {}, []
    grupos = lotes(itens, tamanho)

    def um(n):
        pasta = os.path.join(saida, "lote-%03d" % (n + 1)) if saida else None
        return rodar_lote(grupos[n], modelo, pasta, trabalho, timeout)

    if paralelo > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=paralelo) as ex:
            partes = list(ex.map(um, range(len(grupos))))
    else:
        partes = [um(n) for n in range(len(grupos))]
    resultado, infos = {}, []
    for r, info in partes:
        resultado.update(r)
        infos.append(info)
    if saida:
        with open(os.path.join(saida, "resultado.json"), "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=1)
    return resultado, infos


# ---------------------------------------------------------------- linha de comando


def _lista(texto):
    return [x.strip() for x in (texto or "").split(",") if x.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="ids de julgados do acervo, separados por vírgula")
    g.add_argument("--arquivos", help="caminhos de julgados .md, separados por vírgula")
    g.add_argument("--norma-diff", help="diffs unificados de normas, separados por vírgula")
    ap.add_argument("--ato", help="trechos do ato ou da fonte, na ordem dos diffs (vírgula)")
    ap.add_argument("--model", default=MODELO)
    ap.add_argument("--saida", help="pasta do log (padrão: dados/fase-4/revisor/<data-hora>)")
    ap.add_argument("--trabalho", help="base das pastas de trabalho (fora do cofre e do repo)")
    ap.add_argument("--paralelo", type=int, default=1)
    a = ap.parse_args(argv)

    if a.norma_diff:
        diffs = _lista(a.norma_diff)
        atos = _lista(a.ato)
        if atos and len(atos) != len(diffs):
            ap.error("--ato precisa ter um arquivo por diff")
        itens = [item_norma(d, atos[n] if atos else None) for n, d in enumerate(diffs)]
    else:
        if a.arquivos:
            caminhos = _lista(a.arquivos)
        else:
            quer = set(_lista(a.ids))
            achados = {j["id"]: j["url"] for j in je.julgados() if j["id"] in quer}
            faltam = sorted(quer - set(achados))
            if faltam:
                ap.error("ids sem julgado no acervo: %s" % ", ".join(faltam))
            caminhos = [achados[i] for i in _lista(a.ids)]
        itens = [item_julgado(c) for c in caminhos]

    saida = a.saida or os.path.join(LOGS, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    resultado, infos = revisar(itens, a.model, saida, a.trabalho, paralelo=a.paralelo)
    custo = sum(i["total_cost_usd"] or 0 for i in infos)
    print(json.dumps(resultado, ensure_ascii=False, indent=1))
    print("lotes: %d; custo (stream-json): US$ %.4f; log: %s" % (len(infos), custo, saida),
          file=sys.stderr)
    return 1 if any(not r["ok"] for r in resultado.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
