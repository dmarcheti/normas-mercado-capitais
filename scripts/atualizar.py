#!/usr/bin/env python3
"""Aplica os itens do deteccao.json por classe e calcula o critério de merge (Fase 4, Task 3a).

Uso:
  python3 scripts/atualizar.py --deteccao dados/auto/<data>/deteccao.json [--deteccao OUTRO]
      --raiz <cópia de trabalho> [--sombra] [--sem-llm] [--saida dados/auto/<data>]
      [--max-julgados 40]

`--deteccao` repetível: os itens são unidos e o arquivo posterior substitui os itens das fontes
que ele traz (o r4 refeito de crsfn e b3 vale sobre o da manhã). Tudo é gravado na cópia de
`--raiz` (a Task 3b passa um worktree); caches, relatórios e logs vão para `--saida`, nunca para
os padrões em dados/ (que pode ser link simbólico para o repo).

Classes (seção 2 do plano):
  A   entrada nova em fontes/acervo.json (inventario_acervo.resolucao_do_acervo) e
      texto_vigente --camada 1 --ids.
  B1  B sem consolidado novo: aviso no `incerteza` da norma-alvo, entrada em fontes/pendentes.json
      (o indice.md ganha a seção "Atos publicados ainda não aplicados") e registro da alteradora
      em fontes/acervo.json (só-alteradora), para não voltar a ser detectada.
  B2  B com consolidado novo. Sem histórico e com pendente: texto_vigente --ids e teste 1
      (linhas novas fora do texto do ato); verde tira aviso e pendente. Com histórico e sem
      pendente: teste 2 (teste_final) contra o consolidado novo. Verde registra o head.
  C   aviso e pendente da B1; o replay por LLM fica manual (precisa-diogo, "replay manual").
  F   Parecer de Orientação ou Ofício-Circular novo: texto_vigente --camada 2; OCR vira F-OCR.
  G   lei: leis.montar_lei, teste_lei e a regra das notas do Planalto (toda linha nova traz nota
      de alteração de ato posterior à data-base anterior).
  H   BCB, versão nova: acervo-bcb (inventario_bcb.detalhar) e texto_vigente --camada 4.
  I   ANBIMA, PDF novo: só troca de URL (tamanho igual) atualiza o registro; senão a entrada
      antiga vira "anterior" e texto_vigente --camada 5.
  J   julgado novo: julgados_baixar, julgados_converter (citações), extração Haiku, revisor;
      entrada enxuta em fontes/julgados-inventario.json. CRSFN "fora" e H-novo "fora" vão para
      fontes/decisoes.json com `classe`; "-2" com sha256 igual ao do existente é "excecao".
  D, E, F-OCR, H-novo, I-novo, G-novo e `leitura_falhou`: não aplica; precisa-diogo com o que
      seria feito.
Item automático que falha numa conferência volta ao estado anterior (arquivos restaurados) e vai
para o Diogo com o diff curto. `--sem-llm`: etapa de LLM não roda; o item vai para o Diogo com
"LLM indisponível" (C18).

Critério (seção 3): 9 condições por item e no conjunto, em <saida>/criterio.json; a 9 (CI) fica
"pendente" para a Task 3b. Saídas: criterio.json, itens-automaticos.json, itens-diogo.json,
resumo.md (corpo do PR, com o custo de LLM somado dos log.jsonl do stream-json). As quatro saídas
são apagadas no início e trazem `execucao_id` (timestamp e PID); itens-*.json são
{"execucao_id", "itens"}. `pr_automatico` fica false enquanto o CI está pendente; a 3b decide por
`pr_automatico_antes_do_ci` depois do CI verde. Exceção na execução: rc 2.
"""
import argparse
import difflib
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import detectar as det  # noqa: E402
import inventario_acervo as ia  # noqa: E402
import inventario_bcb as ibcb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402
import leis as mleis  # noqa: E402
import pii  # noqa: E402
import texto_vigente as tv  # noqa: E402
from controle import contar_controle, sem_controle  # noqa: E402
from teste_ato import linhas_novas_fora_do_ato  # noqa: E402

AUTOMATICAS = ("A", "B1", "B2", "F", "G", "H", "I", "J")
SO_DIOGO = ("D", "E", "F-OCR", "H-novo", "I-novo", "G-novo")
ORDEM = {"A": 1, "B1": 2, "C": 3, "B2": 4, "F": 5, "G": 6, "H": 7, "I": 8, "J": 9}
ESTADOS_OK = ("automatico", "fora", "sem-mudanca", "excecao")
COBERTURA_MIN = 0.99
TETO_JULGADOS, TETO_NORMAS = 40, 5
LIMITE_MB, LIMITE_ARQUIVOS = 180, 4500
CONDICOES = ("1-classes", "2-conferencia", "3-gate", "4-varredura", "5-revisor", "6-arquivos",
             "7-teto", "8-plugins", "9-ci")
NORMAS = os.path.join("plugins", "normas", "normas")
O_QUE_SERIA = {
    "D": "marcar a norma como revogada (situacao e aviso) e tirá-la do texto vigente",
    "E": "tratar o evento manualmente (classe sem aplicação automática)",
    "F-OCR": "publicar o texto do OCR, com nível ocr, depois de conferido",
    "H-novo": "incluir a norma do BCB/CMN no perímetro e convertê-la (texto_vigente --camada 4)",
    "I-novo": "incluir o documento da ANBIMA no acervo e convertê-lo (texto_vigente --camada 5)",
    "G-novo": "incluir a lei em fontes/leis.json e montá-la pelo leis.py",
    "C": "replay do ato por claude -p (Sonnet, prompts/replay.md), teste 1 e, com consolidado, teste 2",
    "J": "baixar, converter, extrair (Haiku) e revisar o julgado",
}
NOTA_PLANALTO = re.compile(r"\((?:Reda[çc][ãa]o dada|Inclu[íi]d|Revogad|Renumerad|Acrescid|Vide|Vig[êe]ncia)"
                           r"[^()]*\)", re.I)
CEP = re.compile(r"CEP\s*:?\s*\d{2}\.?\d{3}-?\d{3}", re.I)


# ---------------------------------------------------------------- utilitários

def ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def ler_texto(caminho):
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8", errors="replace") as f:
        return f.read()


def gravar_texto(caminho, texto):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write(sem_controle(texto))


def numero_do_id(id_):
    m = re.search(r"-(\d+)$", id_ or "")
    return int(m.group(1)) if m else None


def classe_efetiva(it):
    if it["classe"] == "B":
        return "B2" if (it.get("dados") or {}).get("consolidado_novo") else "B1"
    return it["classe"]


def chave(it):
    return "%s|%s|%s" % (it["id"], classe_efetiva(it), ",".join(it.get("norma_alvo") or []))


def unir_deteccoes(caminhos):
    """Itens das detecções; o arquivo posterior substitui os itens das fontes que ele traz."""
    itens, gerado = [], []
    for c in caminhos:
        d = ler_json(c)
        fontes = set((d.get("fontes") or {}).keys())
        itens = [i for i in itens if i.get("fonte") not in fontes] + list(d.get("itens") or [])
        gerado.append(d.get("gerado_em"))
    return itens, gerado


def diff_curto(antigo, novo, rel, maximo=60):
    linhas = list(difflib.unified_diff((antigo or "").splitlines(), (novo or "").splitlines(),
                                       "a/" + rel, "b/" + rel, n=0, lineterm=""))
    if len(linhas) > maximo:
        linhas = linhas[:maximo] + ["[... %d linha(s) a mais]" % (len(linhas) - maximo)]
    return "\n".join(linhas)


def foto(raiz):
    """{rel: (tamanho, mtime_ns)} de plugins/ e fontes/."""
    out = {}
    for base in ("plugins", "fontes"):
        for dp, _, fn in os.walk(os.path.join(raiz, base)):
            for f in fn:
                p = os.path.join(dp, f)
                st = os.stat(p)
                out[os.path.relpath(p, raiz)] = (st.st_size, st.st_mtime_ns)
    return out


def foto_hash(raiz):
    out = {}
    for base in ("plugins", "fontes", ".claude-plugin"):
        for dp, _, fn in os.walk(os.path.join(raiz, base)):
            for f in fn:
                p = os.path.join(dp, f)
                with open(p, "rb") as g:
                    out[os.path.relpath(p, raiz)] = hashlib.sha1(g.read()).hexdigest()
    return out


def diferentes(antes, depois):
    return sorted(k for k in set(antes) | set(depois) if antes.get(k) != depois.get(k))


def frontmatter_campo(texto, campo):
    m = re.search(r"(?m)^%s:[ \t]*(.*)$" % re.escape(campo), (texto or "").split("\n---", 1)[0])
    return m.group(1).strip() if m else ""


def e_indice(rel):
    base = os.path.basename(rel)
    if base in ("plugin.json", "marketplace.json"):
        return False
    return (base in ("indice.md", "normas.json") or "/indices/" in rel.replace(os.sep, "/")
            or (rel.startswith("plugins/") and base.endswith(".json") and "/julgados/" not in rel))


def e_julgado(rel):
    r = rel.replace(os.sep, "/")
    return bool(re.match(r"plugins/julgados-[^/]+/julgados/", r)) and not e_indice(r) and r.endswith(".md")


# ---------------------------------------------------------------- ambiente

class Ambiente:
    """Raiz da cópia, saída, opções e as duas portas para o mundo (injetáveis nos testes):
    `rodar(argv, env=None) -> (rc, stdout, stderr)` e `rede` (detectar.Rede)."""

    def __init__(self, raiz, saida, sem_llm=False, sombra=False, rodar=None, rede=None, hoje=None,
                 trabalho=None, max_julgados=TETO_JULGADOS):
        self.raiz, self.saida = os.path.abspath(raiz), os.path.abspath(saida)
        self.sem_llm, self.sombra, self.max_julgados = sem_llm, sombra, max_julgados
        os.makedirs(os.path.join(self.saida, "logs"), exist_ok=True)
        self._rodar = rodar or self._subprocess
        self.rede = rede if rede is not None else det.Rede(cache=os.path.join(self.saida, "cache-http"))
        self.hoje = hoje or jc.hoje_sp()
        base = "/private/tmp" if os.path.isdir("/private/tmp") else tempfile.gettempdir()
        self.trabalho = trabalho or tempfile.mkdtemp(prefix="atualizar-trabalho-", dir=base)
        self.n_cmd = 0
        self.execucao_id = "%s-%d" % (time.strftime("%Y%m%dT%H%M%S"), os.getpid())

    def _subprocess(self, argv, env=None):
        p = subprocess.run(argv, cwd=self.raiz, capture_output=True, text=True, env=env)
        return p.returncode, p.stdout, p.stderr

    def rodar(self, argv, env=None):
        self.n_cmd += 1
        rc, out, err = self._rodar(argv, env)
        nome = "%03d-%s.log" % (self.n_cmd, os.path.basename(argv[1] if len(argv) > 1 else argv[0]))
        with open(os.path.join(self.saida, "logs", nome), "w", encoding="utf-8") as f:
            f.write("$ %s\nrc=%s\n--- stdout\n%s\n--- stderr\n%s\n" % (" ".join(argv), rc, out, err))
        return rc, out, err

    def script(self, nome, *args):
        return self.rodar([sys.executable, os.path.join(self.raiz, "scripts", nome)] + list(args))

    def p(self, *partes):
        return os.path.join(self.raiz, *partes)

    def s(self, *partes):
        return os.path.join(self.saida, *partes)


# ---------------------------------------------------------------- resultado de item

def novo_resultado(it):
    return {"chave": chave(it), "id": it["id"], "classe": classe_efetiva(it), "classe_detectada": it["classe"],
            "fonte": it.get("fonte"), "norma_alvo": list(it.get("norma_alvo") or []),
            "estado": "automatico", "motivo": "", "o_que_seria_feito": "", "arquivos": [],
            "esperados": [], "conferencia": "n/a", "revisor": "n/a", "diff": "",
            "norma_alterada": False, "julgado_novo": False}


def para_diogo(r, motivo, o_que=None):
    r["estado"], r["motivo"] = "diogo", motivo
    if o_que is not None:
        r["o_que_seria_feito"] = o_que
    return r


class Guarda:
    """Volta o item ao estado anterior: arquivos de fontes/ e os declarados são copiados antes;
    o que surgiu depois é apagado."""

    def __init__(self, amb, declarados=()):
        self.amb = amb
        self.antes = foto(amb.raiz)
        self.copias = {}
        rels = [os.path.relpath(c, amb.raiz) for c in glob.glob(amb.p("fontes", "*.json"))] + list(declarados)
        for rel in rels:
            self.declarar(rel)

    def declarar(self, rel):
        c = self.amb.p(rel)
        if rel not in self.copias:
            self.copias[rel] = None
            if os.path.isfile(c):
                with open(c, "rb") as f:
                    self.copias[rel] = f.read()

    def tocados(self):
        return diferentes(self.antes, foto(self.amb.raiz))

    def desfazer(self):
        nao = []
        for rel in self.tocados():
            c = self.amb.p(rel)
            if rel in self.copias:
                if self.copias[rel] is None:
                    if os.path.exists(c):
                        os.remove(c)
                else:
                    with open(c, "wb") as f:
                        f.write(self.copias[rel])
            elif rel not in self.antes:
                if os.path.exists(c):
                    os.remove(c)
            else:
                nao.append(rel)
        return nao


# ---------------------------------------------------------------- normas: apoio

def caminho_norma(amb, id_):
    """Arquivo do frontmatter da norma (o .md ou o index.md das partes), relativo à raiz."""
    for n in ler_json(amb.p(NORMAS, "normas.json"), []):
        if n["id"] == id_:
            c = n["caminho"].rstrip("/")
            rel = os.path.join(NORMAS, c)
            if os.path.isdir(amb.p(rel)):
                rel = os.path.join(rel, "index.md")
            return rel
    return None


def esperado_norma(rel):
    """Prefixo esperado de uma norma: o .md, ou a pasta das partes."""
    if rel.endswith("/index.md"):
        return os.path.dirname(rel) + "/"
    return rel


def rodar_tv(amb, camada, ids):
    """texto_vigente --camada N --ids, com cache e relatório na saída; devolve {id: entrada}."""
    rel = amb.s("tv-camada-%d.json" % camada)
    if os.path.exists(rel):  # o texto_vigente mescla por id: entrada de execução anterior não vale
        os.remove(rel)
    rc, out, err = amb.script(
        "texto_vigente.py", "--camada", str(camada), "--ids", ",".join(ids),
        "--cache", amb.s("cache-tv"), "--relatorio", rel, "--cache-bcb", amb.s("cache-bcb"),
        "--cache-anbima", amb.s("pdf-anbima"), "--cache-b3", amb.s("pdf-b3"))
    entradas = {e.get("id"): e for e in (ler_json(rel, []) or [])}
    return rc, {i: entradas.get(i) for i in ids}, (err or out or "").strip().splitlines()[-1:] or [""]


def aceitar_tv(entrada, exigir_versao_bcb=False):
    """(ok, motivo, conferencia) da entrada do relatório do texto_vigente. Valor ausente conta
    como falha (cobertura, conferência independente e, na classe H, a decisão `versao_bcb`)."""
    if not entrada:
        return False, "texto_vigente sem entrada no relatório", "falha"
    if entrada.get("resultado", "ok") != "ok":
        return False, "texto_vigente: %s (%s)" % (entrada.get("resultado"),
                                                  (entrada.get("erro") or entrada.get("motivo") or "")[:150]), "falha"
    if entrada.get("nivel_verificacao") == "ocr":
        return False, "ocr", "falha"
    if not entrada.get("conferencia_independente"):
        return False, "sem conferência independente", "falha"
    cob = entrada.get("cobertura")
    if cob is None or cob < COBERTURA_MIN:
        return False, "cobertura %s abaixo de 99%%" % cob, "falha"
    vb = entrada.get("versao_bcb") or {}
    if exigir_versao_bcb and not vb:
        return False, "sem decisão HTML x PDF do BCB (versao_bcb) no relatório", "falha"
    if vb and (vb.get("aviso") or vb.get("decisao") not in ("html", "pdf")):
        return False, "decisão HTML x PDF do BCB com aviso: %s" % (vb.get("aviso") or vb.get("decisao")), "falha"
    return True, "", "ok"


def entrada_resolucao(amb, n, url, titulo=None):
    """Entrada de fontes/acervo.json para a Resolução CVM n, pela página (GET)."""
    r = amb.rede.get(url)
    if r.status != 200:
        return None, "página da Resolução CVM %d: HTTP %s %s" % (n, r.status, r.erro)
    acervo = ler_json(amb.p("fontes", "acervo.json"))
    estoque = set((acervo.get("estoque_regulatorio") or {}).get("resolucoes") or [])
    e = ia.resolucao_do_acervo(n, titulo or "Resolução CVM %d" % n, url, r.texto(), estoque)
    return e, ""


def incluir_resolucao(amb, entrada):
    cam = amb.p("fontes", "acervo.json")
    acervo = ler_json(cam)
    if any(int(r["numero"]) == entrada["numero"] for r in acervo["resolucoes"]):
        return False
    acervo["resolucoes"] = sorted(acervo["resolucoes"] + [entrada], key=lambda r: int(r["numero"]))
    det.gravar_json(cam, acervo)
    return True


def item_tv(amb, camada, id_):
    """Item do texto_vigente para o id (para saber o arquivo antes de converter)."""
    if camada in (1, 2):
        acervo = ler_json(amb.p("fontes", "acervo.json"))
    elif camada == 4:
        acervo = {"perimetro": ler_json(amb.p("fontes", "perimetro-camada4.json"), []),
                  "bcb": ler_json(amb.p("fontes", "acervo-bcb.json"), {})}
    else:
        acervo = {"anbima": ler_json(amb.p("fontes", "acervo-anbima.json"), {}),
                  "b3": ler_json(amb.p("fontes", "acervo-b3.json"), {})}
    itens = tv.itens_do_acervo(acervo, camada, cache_bcb=amb.s("cache-bcb"),
                               cache_pdf={"anbima": amb.s("pdf-anbima"), "b3": amb.s("pdf-b3")})
    achados, _ = tv.filtrar_ids(itens, [id_])
    return achados[0] if achados else None


def converter_e_aceitar(amb, r, guarda, camada, id_, exigir_versao_bcb=False):
    """texto_vigente do item; aceita pela cobertura; devolve o rel do arquivo ou None."""
    item = item_tv(amb, camada, id_)
    if item is None:
        para_diogo(r, "texto_vigente não acha o item %s na camada %d" % (id_, camada))
        return None
    rel = os.path.join(NORMAS, item["arquivo"])
    guarda.declarar(rel)
    antigo = ler_texto(amb.p(rel))
    rc, ent, ult = rodar_tv(amb, camada, [id_])
    ok, motivo, conf = aceitar_tv(ent.get(id_), exigir_versao_bcb)
    if rc != 0:
        ok, motivo, conf = False, "texto_vigente rc %s: %s" % (rc, ult[0][:150]), "falha"
    r["conferencia"] = conf
    r["diff"] = diff_curto(antigo, ler_texto(amb.p(rel)), rel)
    r["esperados"].append(esperado_norma(rel))
    if not ok:
        if motivo == "ocr" and r["classe"] == "F":
            r["classe"] = "F-OCR"
            para_diogo(r, "conversão caiu no OCR", O_QUE_SERIA["F-OCR"])
        else:
            para_diogo(r, motivo)
        return None
    r["norma_alterada"] = True
    return rel


# ---------------------------------------------------------------- classes de norma

def aplicar_a(amb, it, r, guarda):
    n = numero_do_id(it["id"])
    e, erro = entrada_resolucao(amb, n, it["url"], (it.get("dados") or {}).get("titulo"))
    if e is None:
        return para_diogo(r, erro)
    e["incluida_pela_automacao"] = True
    if not incluir_resolucao(amb, e):
        return para_diogo(r, "Resolução CVM %d já está em fontes/acervo.json" % n)
    converter_e_aceitar(amb, r, guarda, 1, it["id"])
    return r


def aviso_b1(it):
    n = numero_do_id(it["id"])
    dou = it.get("data_dou") or it.get("data") or "sem data"
    return ("Alterada pela Resolução CVM %d (DOU %s); texto ainda sem a alteração até o consolidado "
            "da CVM [verificar]." % (n, dou))


def aplicar_b1(amb, it, r, guarda, classe="B1"):
    """Aviso no incerteza do alvo, pendente e registro da alteradora; também a parte da C."""
    alvos = it.get("norma_alvo") or []
    if not alvos:
        return para_diogo(r, "alteradora sem norma-alvo legível na ementa",
                          "ler o ato, achar a norma alterada e aplicar o aviso (B1)")
    n = numero_do_id(it["id"])
    for alvo in alvos:
        rel = caminho_norma(amb, alvo)
        if rel is None:
            return para_diogo(r, "norma-alvo %s fora do plugin" % alvo)
        guarda.declarar(rel)
        texto = ler_texto(amb.p(rel))
        inc = frontmatter_campo(texto, "incerteza")
        aviso = aviso_b1(it)
        if "Alterada pela Resolução CVM %d " % n not in inc:
            novo = re.sub(r"(?m)^incerteza:[ \t]*(.*)$",
                          lambda m: "incerteza: " + (m.group(1).rstrip() + " " + aviso).strip(), texto, count=1)
            gravar_texto(amb.p(rel), novo)
            r["diff"] = diff_curto(texto, novo, rel)
        r["esperados"].append(esperado_norma(rel))
        r["norma_alterada"] = True
        cam = amb.p("fontes", "pendentes.json")
        pend = ler_json(cam, [])
        if not any(p.get("norma") == alvo and p.get("ato_id") == it["id"] for p in pend):
            pend.append({"norma": alvo, "ato": "Resolução CVM %d" % n, "ato_id": it["id"],
                         "ato_url": it.get("url") or "", "data_dou": it.get("data_dou") or "",
                         "data_deteccao": amb.hoje, "classe": classe})
            det.gravar_json(cam, pend)
    acervo = ler_json(amb.p("fontes", "acervo.json"))
    if not any(int(x["numero"]) == n for x in acervo["resolucoes"]):
        e, erro = entrada_resolucao(amb, n, it["url"])
        if e is None:
            return para_diogo(r, erro)
        incluir_resolucao(amb, e)
    return r


def aplicar_c(amb, it, r, guarda):
    aplicar_b1(amb, it, r, guarda, classe="C")
    if r["estado"] == "diogo":
        return r
    motivo = "LLM indisponível" if amb.sem_llm else "replay manual"
    return para_diogo(r, motivo + " (classe C: o aviso e o pendente já estão aplicados)", O_QUE_SERIA["C"])


def texto_do_ato(amb, n):
    """Texto do ato (Resolução CVM n) pelo modo piloto do texto_vigente, em <saida>/atos/n."""
    acervo = ler_json(amb.p("fontes", "acervo.json"))
    e = next((x for x in acervo["resolucoes"] if int(x["numero"]) == n), None)
    if e is None:
        return None
    falso = {"resolucoes": [dict(e, situacao="vigente", consolidado={}, alteradoras=[])],
             "estoque_regulatorio": {}}
    itens = tv.itens_do_acervo(falso, 1)
    if not itens:
        return None
    pasta = amb.s("atos", str(n))
    shutil.rmtree(pasta, ignore_errors=True)  # texto de execução anterior não vale
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, "itens.json"), "w", encoding="utf-8") as f:
        json.dump(itens, f, ensure_ascii=False)
    rc, _, _ = amb.script("texto_vigente.py", os.path.join(pasta, "itens.json"), pasta,
                          "--cache", amb.s("cache-tv-atos"))
    if rc != 0:
        return None
    return ler_texto(os.path.join(pasta, itens[0]["arquivo"]))


def baixar(amb, url, destino):
    r = amb.rede.get(url)
    if r.status != 200:
        return "HTTP %s %s" % (r.status, r.erro)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(r.dados)
    return ""


def registrar_head_resolucao(amb, alvo, dados):
    cam = amb.p("fontes", "acervo.json")
    acervo = ler_json(cam)
    n = numero_do_id(alvo)
    for x in acervo["resolucoes"]:
        if int(x["numero"]) == n:
            x["consolidado_head"] = {"bytes": int(dados.get("bytes") or 0),
                                     "last_modified": dados.get("last_modified") or ""}
    det.gravar_json(cam, acervo)


def aplicar_b2(amb, it, r, guarda):
    alvo, dados = it["id"], it.get("dados") or {}
    pend = [p for p in ler_json(amb.p("fontes", "pendentes.json"), []) if p.get("norma") == alvo]
    rel = caminho_norma(amb, alvo)
    if rel is None:
        return para_diogo(r, "norma %s fora do plugin" % alvo)
    r["esperados"].append(esperado_norma(rel))
    if dados.get("com_historico"):
        if pend:
            return para_diogo(r, "replay manual (norma com histórico e ato pendente)", O_QUE_SERIA["C"])
        if dados.get("formato") != "docx":
            return para_diogo(r, "consolidado novo em %s: teste 2 só com DOCX" % dados.get("formato"))
        arq = amb.s("consolidados", "%s.docx" % alvo)
        erro = baixar(amb, it["url"], arq)
        if erro:
            return para_diogo(r, "consolidado: %s" % erro)
        rc, out, _ = amb.script("teste_final.py", alvo, "--consolidado", arq)
        r["conferencia"] = "ok" if rc == 0 else "falha"
        if rc != 0:
            r["diff"] = "\n".join(out.strip().splitlines()[-20:])
            return para_diogo(r, "teste 2: consolidado novo difere do texto com histórico",
                              "replay das alterações do consolidado no histórico")
        registrar_head_resolucao(amb, alvo, dados)
        return r
    if not pend:
        return para_diogo(r, "consolidado mudou sem ato pendente conhecido",
                          "reconverter (texto_vigente --ids) e conferir a mudança")
    cam = amb.p("fontes", "acervo.json")
    acervo = ler_json(cam)
    n = numero_do_id(alvo)
    for x in acervo["resolucoes"]:
        if int(x["numero"]) == n:
            x["alteradoras"] = sorted(set(x.get("alteradoras") or []) | {numero_do_id(p["ato_id"]) for p in pend})
    det.gravar_json(cam, acervo)
    antigo = ler_texto(amb.p(rel))
    novo_rel = converter_e_aceitar(amb, r, guarda, 1, alvo)
    if novo_rel is None:
        return r
    diff = "\n".join(difflib.unified_diff(antigo.splitlines(), ler_texto(amb.p(novo_rel)).splitlines(),
                                          "a/" + novo_rel, "b/" + novo_rel, n=0, lineterm=""))
    atos = []
    for p in pend:
        t = texto_do_ato(amb, numero_do_id(p["ato_id"]))
        if t is None:
            r["conferencia"] = "falha"
            return para_diogo(r, "sem texto do ato %s para o teste 1" % p["ato"])
        atos.append(t)
    fora = linhas_novas_fora_do_ato(diff, "\n".join(atos))
    if fora:
        r["conferencia"] = "falha"
        r["diff"] = "\n".join("+" + x for x in fora[:30])
        return para_diogo(r, "teste 1: %d linha(s) nova(s) fora do texto do ato" % len(fora))
    r["conferencia"] = "ok"
    resto = [p for p in ler_json(amb.p("fontes", "pendentes.json"), []) if p.get("norma") != alvo]
    det.gravar_json(amb.p("fontes", "pendentes.json"), resto)
    registrar_head_resolucao(amb, alvo, dados)
    return r


def aplicar_f(amb, it, r, guarda):
    d = it.get("dados") or {}
    pag = amb.rede.get(it["url"])
    if pag.status != 200:
        return para_diogo(r, "página: HTTP %s %s" % (pag.status, pag.erro))
    cam = amb.p("fontes", "acervo.json")
    acervo = ler_json(cam)
    if it["id"].startswith("cvm-po-"):
        n = numero_do_id(it["id"])
        e = dict({"numero": n, "titulo": d.get("titulo") or "Parecer de Orientação CVM %d" % n,
                  "data": it.get("data"), "descricao": d.get("ementa") or "", "url_pagina": it["url"]},
                 **ia.detalhes_da_pagina(pag.texto()))
        acervo["pareceres"] = sorted(acervo["pareceres"] + [e], key=lambda x: int(x["numero"]))
    else:
        of = ia.oficio({"titulo": d.get("titulo") or "", "url": it["url"], "data": it.get("data") or "",
                        "descricao": d.get("ementa") or ""}, pag.texto())
        of["id"], of["slug"] = it["id"], it["id"][len("cvm-"):]
        if not of.get("data") or of["data"] < tv.CORTE_OFICIOS:
            return para_diogo(r, "ofício sem data ou antes do corte %s" % tv.CORTE_OFICIOS)
        acervo["oficios_circulares"].append(of)
    det.gravar_json(cam, acervo)
    converter_e_aceitar(amb, r, guarda, 2, it["id"])
    return r


def _ano(data):
    m = re.match(r"(\d{4})", data or "")
    return int(m.group(1)) if m else 0


def linhas_sem_nota(diff, ano_base):
    """Linhas novas (fora do frontmatter) sem nota do Planalto de ato do ano-base em diante."""
    fora = []
    for linha in diff.split("\n"):
        if not linha.startswith("+") or linha.startswith("+++"):
            continue
        t = linha[1:].strip()
        if not t or t == "---" or re.match(r"^[a-z_]+:", t):
            continue
        anos = [int(a) for n in NOTA_PLANALTO.findall(t) for a in re.findall(r"\b(1[89]\d\d|20\d\d)\b", n)]
        if not anos or max(anos) < ano_base:
            fora.append(t)
    return fora


def aplicar_g(amb, it, r, guarda):
    item = next((x for x in ler_json(amb.p("fontes", "leis.json"), []) if x["id"] == it["id"]), None)
    if item is None:
        return para_diogo(r, "lei fora de fontes/leis.json", O_QUE_SERIA["G-novo"])
    resp = amb.rede.get(it["url"])
    if resp.status != 200:
        return para_diogo(r, "Planalto: HTTP %s %s" % (resp.status, resp.erro))
    nome = mleis.TIPOS_LEI[mleis._tipo(item)][1] % item["numero"]
    html_arq = amb.s("leis", nome + ".html")
    os.makedirs(os.path.dirname(html_arq), exist_ok=True)
    with open(html_arq, "wb") as f:
        f.write(resp.dados)
    pasta = os.path.join(NORMAS, "leis")
    principal = os.path.join(pasta, nome + ".md")
    if not os.path.exists(amb.p(principal)):
        principal = os.path.join(pasta, nome, "index.md")
    ano_base = _ano(frontmatter_campo(ler_texto(amb.p(principal)), "baixado_em"))
    if not ano_base:
        return para_diogo(r, "lei sem baixado_em no frontmatter: sem data-base para a regra das notas do Planalto")
    diffs, sem_nota = [], []
    for rel_lei, conteudo in sorted(mleis.montar_lei(dict(item, url=it["url"]), resp.dados).items()):
        rel = os.path.join(pasta, *rel_lei.split("/"))
        guarda.declarar(rel)
        antigo = ler_texto(amb.p(rel))
        gravar_texto(amb.p(rel), conteudo)
        novo = ler_texto(amb.p(rel))
        d = "\n".join(difflib.unified_diff((antigo or "").splitlines(), novo.splitlines(), "a/" + rel,
                                           "b/" + rel, n=0, lineterm=""))
        diffs.append(d)
        sem_nota += linhas_sem_nota(d, ano_base)
    r["esperados"].append(os.path.join(pasta, nome))
    r["diff"] = "\n".join("\n".join(diffs).splitlines()[:60])
    rc, out, _ = amb.script("teste_lei.py", it["id"], "--html", html_arq)
    r["conferencia"] = "ok" if rc == 0 else "falha"
    if rc != 0:
        return para_diogo(r, "teste_lei: %s" % (out.strip().splitlines() or ["falhou"])[-1])
    if sem_nota:
        return para_diogo(r, "%d linha(s) nova(s) sem nota do Planalto de ato posterior a %d"
                          % (len(sem_nota), ano_base))
    r["norma_alterada"] = True
    return r


def _id_bcb(n):
    return "%s%d" % (tv.TIPOS_BCB[n["tipo"]][1], int(n["numero"]))


def aplicar_h(amb, it, r, guarda):
    cam = amb.p("fontes", "acervo-bcb.json")
    bcb = ler_json(cam)
    n = next((x for x in bcb["normas"] if x.get("tipo") in tv.TIPOS_BCB and _id_bcb(x) == it["id"]), None)
    if n is None:
        return para_diogo(r, "norma fora de fontes/acervo-bcb.json", O_QUE_SERIA["H-novo"])
    url = ibcb.NORMA + urllib.parse.urlencode({"p1": n["tipo_bcb"], "p2": n["numero"]})
    resp = amb.rede.get(url)
    if resp.status != 200:
        return para_diogo(r, "API do BCB: HTTP %s %s" % (resp.status, resp.erro))
    os.makedirs(amb.s("cache-bcb"), exist_ok=True)
    with open(amb.s("cache-bcb", "%s-%05d.json" % (n["tipo_bcb"].replace(" ", "_"), int(n["numero"]))), "wb") as f:
        f.write(resp.dados)
    ibcb.detalhar(n, amb.s("cache-bcb"))
    det.gravar_json(cam, bcb)
    converter_e_aceitar(amb, r, guarda, 4, it["id"], exigir_versao_bcb=True)
    return r


def aplicar_i(amb, it, r, guarda):
    d = it.get("dados") or {}
    cam = amb.p("fontes", "acervo-anbima.json")
    anb = ler_json(cam)
    pos = next((k for k, x in enumerate(anb["documentos"])
                if x.get("situacao") == "vigente" and x.get("url") == d.get("anterior")), None)
    if pos is None:
        return para_diogo(r, "documento vigente anterior não achado em acervo-anbima.json")
    velho = anb["documentos"][pos]
    h = det.head_com_tamanho(amb.rede, it["url"])
    if h.status != 200:
        return para_diogo(r, "HEAD do PDF novo: HTTP %s %s" % (h.status, h.erro))
    tam, lm = int(h.cab.get("content-length") or 0), h.cab.get("last-modified") or ""
    if tam and velho.get("bytes") and tam == velho["bytes"]:
        velho.update({"url": it["url"], "arquivo": d.get("arquivo") or velho.get("arquivo"),
                      "bytes": tam, "last_modified": lm})
        det.gravar_json(cam, anb)
        r["estado"], r["motivo"] = "sem-mudanca", "só troca de URL (tamanho igual): registro atualizado"
        return r
    novo = dict(velho, url=it["url"], arquivo=d.get("arquivo") or velho.get("arquivo"),
                vigente_desde=it.get("data") or None, bytes=tam, last_modified=lm)
    velho["situacao"] = "anterior"
    anb["documentos"].insert(pos, novo)
    det.gravar_json(cam, anb)
    converter_e_aceitar(amb, r, guarda, 5, it["id"])
    return r


# ---------------------------------------------------------------- julgados

def _proc(processo):
    return re.sub(r"[./]", "-", (processo or "").split(";")[-1].strip())


def entrada_completa(it):
    """Entrada do inventário completo dos julgados (o que julgados_baixar/converter leem)."""
    d = dict(it.get("dados") or {})
    p = _proc(d.get("processo"))
    e = dict(d, id=it["id"], incerteza=[], titulo=d.get("titulo", ""), proc=p, nup=p,
             procs=[p] if p else [], rito="", relator="", fonte_pendente=False)
    e.setdefault("resultado", "")
    e.setdefault("termo_urls", [])
    e.setdefault("classe", "")
    if d.get("tipo") == "pas":
        if d.get("origem") == "noticia":
            e.update(origem="noticia", noticia=d.get("url", ""), outras_noticias=[], pecas=[])
        else:
            e.update(origem="pas", noticia="", pecas=[])
    elif "/decisoes/" in (d.get("url") or ""):
        e["origem"] = "colegiado"
    else:
        e["origem"] = "tc-tabela"
    return e


def entrada_enxuta(it):
    d = it.get("dados") or {}
    return {"id": it["id"], "tipo": d.get("tipo", ""), "classe": d.get("classe", ""),
            "processo": d.get("processo", ""), "data": d.get("data") or it.get("data") or "",
            "url": d.get("url") or it.get("url") or "", "plugin": d.get("plugin", "")}


def gravar_decisao(amb, it, decisao, motivo, classe):
    cam = amb.p("fontes", "decisoes.json")
    dec = ler_json(cam, [])
    if not any(x["id"] == it["id"] and x.get("classe") == classe for x in dec):
        dec.append({"id": it["id"], "fonte": it.get("fonte"), "decisao": decisao, "motivo": motivo,
                    "data": amb.hoje, "url": it.get("url") or "", "classe": classe})
        det.gravar_json(cam, dec)


def triar_crsfn(amb, it, r):
    """Decide o J do CRSFN sem aplicar texto; devolve True se o item já está resolvido."""
    d = it.get("dados") or {}
    if d.get("perimetro") == "fora":
        gravar_decisao(amb, it, "fora-do-perimetro", "órgão de origem %s (%s)" % (d.get("orgao"), d.get("criterio")), "J")
        r["estado"], r["motivo"] = "fora", "CRSFN fora do perímetro (órgão %s): decisoes.json" % d.get("orgao")
        r["esperados"].append("fontes/decisoes.json")
        return True
    m = re.match(r"^(crsfn-\d{5}-\d{6}-\d{4}-\d{2})-(\d+)$", it["id"])
    if m:
        base = m.group(1)
        achados = glob.glob(amb.p("plugins", "julgados-tc-crsfn", "julgados", "crsfn", "*", base[len("crsfn-"):] + ".md"))
        if achados:
            sha = frontmatter_campo(ler_texto(achados[0]), "sha256_fonte")
            resp = amb.rede.get(it["url"])
            if resp.status == 200 and sha and hashlib.sha256(resp.dados).hexdigest() == sha:
                gravar_decisao(amb, it, "excecao", "duplicata de %s (sha256 da fonte igual)" % base, "J")
                r["estado"], r["motivo"] = "excecao", "duplicata de %s: decisoes.json" % base
                r["esperados"].append("fontes/decisoes.json")
                return True
            para_diogo(r, "possível duplicata de %s" % base,
                       "comparar os dois acórdãos e decidir entre excecao e julgado novo")
            return True
    para_diogo(r, "acórdão do CRSFN novo: conversão manual (os ids do crsfn.py dependem da ordem)",
               O_QUE_SERIA["J"])
    return True


def falha_cobertura_j(x):
    """Motivo se alguma conferência do julgado (`cobertura` do relatório do julgados_converter)
    falta ou fica abaixo de 99%; "" se todas passam."""
    confs = x.get("cobertura")
    if not isinstance(confs, list) or not confs:
        return "conversão sem conferência de cobertura"
    for c in confs:
        cob = c.get("cobertura") if isinstance(c, dict) else None
        arq = c.get("arquivo", "?") if isinstance(c, dict) else "?"
        if cob is None:
            return "%s: sem conferência independente (%s)" % (arq, (c or {}).get("conferencia") if isinstance(c, dict) else "")
        if cob < COBERTURA_MIN:
            return "%s: cobertura %s abaixo de 99%%" % (arq, cob)
    return ""


def caminho_previsto(it):
    """Caminho (relativo à raiz) em que o julgados_converter grava o julgado, ou None."""
    e = entrada_completa(it)
    try:
        return os.path.join("plugins", jc.caminho_relativo(e.get("tipo"), it["id"], (e.get("data") or "")[:4]))
    except (KeyError, ValueError, TypeError):
        return None


def _relatorio_conversao(amb, desde):
    arqs = [a for a in glob.glob(amb.s("relatorios", "conversao-*.json")) if os.path.getmtime(a) >= desde]
    linhas = {}
    for a in sorted(arqs):
        for x in (ler_json(a, {}) or {}).get("itens", []):
            linhas[x["id"]] = x
    return linhas


def _extracao(amb, ids, caminhos):
    """{id: motivo} dos ids que não saíram da extração com ementa nova aplicada. `caminhos`
    {id: caminho relativo à raiz}: o `ementa_do_titulo` do validacao.json traz caminhos."""
    pasta = amb.s("extracao", amb.execucao_id)  # só os lotes desta execução
    shutil.rmtree(pasta, ignore_errors=True)
    amb.script("julgados_extracao.py", "--ids", ",".join(ids), "--model", "haiku", "--raiz", amb.raiz,
               "--saida", pasta, "--trabalho", amb.trabalho)
    aplicados, do_titulo = set(), set()
    for v in glob.glob(os.path.join(pasta, "*", "validacao.json")):
        rel = ler_json(v, {}) or {}
        aplicados |= {i for i, ok in (rel.get("aplicados") or {}).items() if ok}
        do_titulo |= {os.path.realpath(amb.p(c)) for c in rel.get("ementa_do_titulo") or []}
    falhas = {}
    for i in ids:
        if os.path.realpath(amb.p(caminhos[i])) in do_titulo:
            falhas[i] = "extração: ficou a ementa do título"
        elif i not in aplicados:
            falhas[i] = "extração: saída do Haiku não aplicada"
    return falhas


def aplicar_julgados(amb, itens, resultados):
    """J que não é CRSFN, em lote: baixar, converter, extrair, revisar."""
    if not itens:
        return
    por_id = {it["id"]: resultados[chave(it)] for it in itens}
    if amb.sem_llm:
        for r in por_id.values():
            para_diogo(r, "LLM indisponível", O_QUE_SERIA["J"])
        return
    guarda = Guarda(amb)
    inv = amb.s("inventario-j.json")
    with open(inv, "w", encoding="utf-8") as f:
        json.dump({"julgados": [entrada_completa(it) for it in itens]}, f, ensure_ascii=False, indent=1)
    cam = amb.p("fontes", "julgados-inventario.json")
    lista = ler_json(cam, [])
    conhecidos = {x["id"] for x in lista}
    det.gravar_json(cam, lista + [entrada_enxuta(it) for it in itens if it["id"] not in conhecidos])
    ids = list(por_id)
    cache = amb.s("cache-julgados")
    rc, out, err = amb.script("julgados_baixar.py", "--ids", ",".join(ids), "--inventario", inv, "--cache", cache)
    com_erro = set()
    for linha in reversed(out.strip().splitlines()):
        try:
            com_erro = set(json.loads(linha).get("com_erro") or []) | set(json.loads(linha).get("sem_url") or [])
            break
        except ValueError:
            continue
    for i in com_erro:
        para_diogo(por_id[i], "download do julgado falhou", O_QUE_SERIA["J"])
    vivos = [i for i in ids if por_id[i]["estado"] == "automatico"]
    caminhos = {}
    for it in itens:  # julgado existente que a conversão sobrescrever volta se o item for ao Diogo
        prev = caminho_previsto(it)
        if prev:
            guarda.declarar(prev)
    if vivos:
        desde = time.time() - 1
        amb.script("julgados_converter.py", "--ids", ",".join(vivos), "--inventario", inv, "--cache", cache,
                   "--raiz", amb.raiz, "--relatorios", amb.s("relatorios"))
        rel = _relatorio_conversao(amb, desde)
        for i in vivos:
            x = rel.get(i)
            if not x or x.get("erro") or not x.get("caminho"):
                para_diogo(por_id[i], "conversão: %s" % ((x or {}).get("erro") or "sem relatório")[:150], O_QUE_SERIA["J"])
            elif x.get("nivel") == "ocr" or x.get("paginas_ocr"):
                caminhos[i] = x["caminho"]
                por_id[i]["conferencia"] = "falha"
                para_diogo(por_id[i], "conversão com OCR", O_QUE_SERIA["J"])
            elif falha_cobertura_j(x):
                caminhos[i] = x["caminho"]
                por_id[i]["conferencia"] = "falha"
                para_diogo(por_id[i], "conversão: %s" % falha_cobertura_j(x), O_QUE_SERIA["J"])
            else:
                caminhos[i] = x["caminho"]
                por_id[i]["conferencia"] = "ok"
    vivos = [i for i in vivos if por_id[i]["estado"] == "automatico"]
    if vivos:
        for i, m in _extracao(amb, vivos, caminhos).items():
            para_diogo(por_id[i], m, O_QUE_SERIA["J"])
    vivos = [i for i in vivos if por_id[i]["estado"] == "automatico"]
    if vivos:
        rc, out, err = amb.script("revisor.py", "--arquivos", ",".join(amb.p(caminhos[i]) for i in vivos),
                                  "--saida", amb.s("revisor"), "--trabalho", amb.trabalho)
        try:
            rev = json.loads(out)
        except ValueError:
            rev = {}
        for i in vivos:
            v = rev.get(i)
            if v is None:
                por_id[i]["revisor"] = "falha"
                para_diogo(por_id[i], "revisor sem resposta para o julgado", O_QUE_SERIA["J"])
            elif not v.get("ok"):
                por_id[i]["revisor"] = "falha"
                al = "; ".join(str(a.get("trecho") or a) if isinstance(a, dict) else str(a)
                               for a in (v.get("alertas") or []))
                para_diogo(por_id[i], "revisor marcou: %s" % al[:200], O_QUE_SERIA["J"])
            else:
                por_id[i]["revisor"] = "ok"
    # diff curto e reversão dos que foram para o Diogo
    tocados = guarda.tocados()
    diogo = [i for i in ids if por_id[i]["estado"] == "diogo"]
    for i in ids:
        r = por_id[i]
        if i in caminhos:
            r["esperados"].append(caminhos[i])
            r["diff"] = "\n".join((ler_texto(amb.p(caminhos[i])) or "").splitlines()[:40])
        r["esperados"].append("fontes/julgados-inventario.json")
        r["arquivos"] = [t for t in tocados if t == caminhos.get(i) or t == "fontes/julgados-inventario.json"]
        r["julgado_novo"] = r["estado"] == "automatico"
    if diogo:
        for i in diogo:
            c = caminhos.get(i)
            if c and c in guarda.copias:
                if guarda.copias[c] is None:
                    if os.path.exists(amb.p(c)):
                        os.remove(amb.p(c))
                else:
                    with open(amb.p(c), "wb") as f:
                        f.write(guarda.copias[c])
            elif c and os.path.exists(amb.p(c)):
                if c not in guarda.antes:
                    os.remove(amb.p(c))
                elif c in tocados:
                    por_id[i]["nao_revertidos"] = [c]
                    por_id[i]["motivo"] += "; julgado existente sobrescrito sem cópia: %s" % c
            por_id[i]["arquivos"] = []
        lista = ler_json(cam, [])
        det.gravar_json(cam, [x for x in lista if x["id"] not in set(diogo)])


# ---------------------------------------------------------------- aplicação

APLICAR = {"A": aplicar_a, "B1": aplicar_b1, "C": aplicar_c, "B2": aplicar_b2, "F": aplicar_f,
           "G": aplicar_g, "H": aplicar_h, "I": aplicar_i}


def aplicar(amb, itens):
    """Aplica os itens na cópia; devolve (resultados por chave, adiados)."""
    resultados, julgados, adiados = {}, [], []
    for it in sorted(itens, key=lambda x: (ORDEM.get(classe_efetiva(x), 99), x["id"])):
        r = novo_resultado(it)
        if r["chave"] in resultados:
            continue
        resultados[r["chave"]] = r
        d, c = it.get("dados") or {}, r["classe"]
        if d.get("leitura_falhou"):
            para_diogo(r, "leitura do documento falhou na detecção", O_QUE_SERIA.get(c, "ler e aplicar o item"))
        elif c == "H-novo" and d.get("perimetro") == "fora":
            gravar_decisao(amb, it, "fora-do-perimetro", "norma do BCB/CMN fora do perímetro", "H-novo")
            r["estado"], r["motivo"] = "fora", "H-novo fora do perímetro: decisoes.json"
            r["esperados"].append("fontes/decisoes.json")
        elif c in SO_DIOGO:
            para_diogo(r, "classe %s não tem aplicação automática: %s" % (c, it.get("motivo", "")), O_QUE_SERIA[c])
        elif c == "J":
            if d.get("tipo") == "acordao-crsfn":
                triar_crsfn(amb, it, r)
            else:
                julgados.append(it)
            continue
        elif c in APLICAR:
            guarda = Guarda(amb)
            try:
                APLICAR[c](amb, it, r, guarda)
            except Exception as e:  # noqa: BLE001 — um item ruim não para os outros
                para_diogo(r, "erro ao aplicar: %s: %s" % (type(e).__name__, str(e)[:150]))
            r["arquivos"] = guarda.tocados()
            if r["estado"] == "diogo" and c != "C":
                r["nao_revertidos"] = guarda.desfazer()
                r["arquivos"], r["norma_alterada"] = [], False
        else:
            para_diogo(r, "classe desconhecida %s" % c)
        if c in ("H-novo", "J") and r["estado"] == "fora":
            r["arquivos"] = ["fontes/decisoes.json"]
    # julgados: os mais antigos primeiro, até o teto
    julgados.sort(key=lambda x: ((x.get("dados") or {}).get("data") or x.get("data") or "9999", x["id"]))
    for it in julgados[amb.max_julgados:]:
        r = resultados[chave(it)]
        r["estado"], r["motivo"] = "adiado", "acima do teto de %d julgados novos por execução" % amb.max_julgados
        adiados.append(r)
    aplicar_julgados(amb, julgados[:amb.max_julgados], resultados)
    for r in resultados.values():
        if r["estado"] in ("fora", "excecao") and r["classe"] == "J":
            r["arquivos"] = ["fontes/decisoes.json"]
    return resultados, adiados


# ---------------------------------------------------------------- critério

def _textos_json(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            for t in _textos_json(v):
                yield t
    elif isinstance(obj, list):
        for v in obj:
            for t in _textos_json(v):
                yield t


def varrer(amb, rels):
    """Lista de falhas da varredura (CPF, RG, caractere de controle, CEP com endereço) nos .md e
    nos .json tocados (no .json, o texto bruto mais as strings decodificadas, onde o caractere de
    controle aparece; JSON ilegível é falha)."""
    falhas = []
    for rel in rels:
        if not rel.endswith((".md", ".json")):
            continue
        t = ler_texto(amb.p(rel))
        if t is None:
            continue
        if rel.endswith(".json"):
            try:
                t = t + "\n" + "\n".join(_textos_json(json.loads(t)))
            except ValueError:
                falhas.append("%s: JSON ilegível" % rel)
                continue
        if pii.achar_cpfs(t):
            falhas.append("%s: CPF" % rel)
        if pii.achar_rgs(t):
            falhas.append("%s: RG" % rel)
        if contar_controle(t):
            falhas.append("%s: caractere de controle" % rel)
        for m in CEP.finditer(t):
            janela = t[max(0, m.start() - 300):m.end() + 300]
            if pii._enderecos(janela):
                falhas.append("%s: CEP com endereço no contexto" % rel)
                break
    return falhas


def tamanho_plugins(amb):
    out = {}
    for p in sorted(glob.glob(amb.p("plugins", "*"))):
        if not os.path.isdir(p):
            continue
        n = b = 0
        for dp, _, fn in os.walk(p):
            for f in fn:
                n += 1
                b += os.path.getsize(os.path.join(dp, f))
        out[os.path.basename(p)] = {"arquivos": n, "mb": round(b / 1e6, 1)}
    return out


SAIDAS = ("criterio.json", "itens-automaticos.json", "itens-diogo.json", "resumo.md")


def pasta_sem_macos(amb):
    """PATH da suíte sem macOS: pasta em <saida> com links só para o python3 e o git (a
    dados/sem-macos-bin do repo é ignorada pelo Git e não existe num worktree novo). Devolve
    (pasta, erro)."""
    pasta = amb.s("sem-macos-bin")
    shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta)
    alvos = {"python3": sys.executable, "git": shutil.which("git")}
    for nome, alvo in alvos.items():
        if not alvo or not os.path.exists(alvo):
            return pasta, "sem %s para a suíte sem macOS" % nome
        os.symlink(alvo, os.path.join(pasta, nome))
    return pasta, ""


def rodar_gate(amb):
    """Suíte sem macOS, validar.py (normas e as pastas julgados-*/julgados) e indice.py --verificar."""
    falhas = []
    sem_macos, erro = pasta_sem_macos(amb)
    if erro:
        falhas.append("suíte sem macOS: %s" % erro)
    env = dict(os.environ, PATH=sem_macos)
    rc, out, err = amb.rodar(["python3", "-m", "unittest", "discover", "-s", "tests"], env=env)
    if rc != 0:
        falhas.append("suíte sem macOS: %s" % ((err or out).strip().splitlines() or ["rc %s" % rc])[-1])
    rc, out, _ = amb.script("validar.py", os.path.join(NORMAS))
    if rc != 0:
        falhas.append("validar normas: %s" % (out.strip().splitlines() or [""])[-1])
    for d in sorted(glob.glob(amb.p("plugins", "julgados-*", "julgados"))):
        rel = os.path.relpath(d, amb.raiz)
        rc, out, _ = amb.script("validar.py", rel)
        if rc != 0:
            falhas.append("validar %s: %s" % (rel, (out.strip().splitlines() or [""])[-1]))
    rc, out, _ = amb.script("indice.py", "--verificar")
    if rc != 0:
        falhas.append("indice --verificar: %s" % (out.strip().splitlines() or [""])[0])
    return falhas


def criterio(amb, resultados, mudados, gate_falhas, plugins, adiados=()):
    itens = [r for r in resultados.values() if r["estado"] != "adiado"]
    jul_novos = sum(1 for r in itens if r["julgado_novo"])
    normas_alt = len({a for r in itens if r["norma_alterada"] for a in (r["norma_alvo"] or [r["id"]])})
    reescritos = [m for m in mudados if e_julgado(m) and m in amb.hash_antes]
    grandes = ["%s (%s MB, %d arquivos)" % (p, v["mb"], v["arquivos"]) for p, v in plugins.items()
               if v["mb"] >= LIMITE_MB or v["arquivos"] >= LIMITE_ARQUIVOS]
    teto = []
    if adiados or jul_novos > TETO_JULGADOS:
        teto.append("volume acima do teto: possível mudança de formato da fonte (%d julgados novos no dia, "
                     "teto %d; %d adiado(s))" % (jul_novos + len(adiados), amb.max_julgados, len(adiados)))
    if jul_novos > TETO_JULGADOS:
        teto.append("%d julgados novos (teto %d)" % (jul_novos, TETO_JULGADOS))
    if normas_alt > TETO_NORMAS:
        teto.append("%d normas alteradas (teto %d)" % (normas_alt, TETO_NORMAS))
    atribuidos = set()
    saida_itens = []
    for r in sorted(itens, key=lambda x: (ORDEM.get(x["classe"], 99), x["id"])):
        meus = [m for m in mudados if m in r["arquivos"]]
        atribuidos |= set(meus)
        fora_esp = [m for m in meus if not (m.startswith("fontes/") and m.endswith(".json"))
                    and not e_indice(m) and not any(m == e or (e.endswith("/") and m.startswith(e))
                                                    for e in r["esperados"])]
        varr = varrer(amb, meus)
        ok_estado = r["estado"] in ESTADOS_OK
        cond = {
            "1-classes": "ok" if ok_estado and (r["classe"] in AUTOMATICAS or r["estado"] != "automatico") else "falha",
            "2-conferencia": r["conferencia"],
            "3-gate": "falha" if gate_falhas else "ok",
            "4-varredura": "falha" if varr else ("ok" if meus else "n/a"),
            "5-revisor": r["revisor"],
            "6-arquivos": "falha" if fora_esp or any(m in reescritos for m in meus) else ("ok" if meus else "n/a"),
            "7-teto": "falha" if teto else "ok",
            "8-plugins": "falha" if grandes else "ok",
            "9-ci": "pendente",
        }
        motivos = [r["motivo"]] if r["estado"] == "diogo" else []
        motivos += varr + ["fora do esperado: %s" % m for m in fora_esp]
        auto = ok_estado and all(v in ("ok", "n/a", "pendente") for v in cond.values())
        saida_itens.append({"id": r["id"], "chave": r["chave"], "classe": r["classe"], "estado": r["estado"],
                            "automatico": auto, "condicoes": cond,
                            "motivo": "; ".join(m for m in motivos if m) or r["motivo"]})
    sobra = [m for m in mudados if m not in atribuidos and not e_indice(m)
             and not (m.startswith("fontes/") and m.endswith(".json"))]
    motivos = []
    n_diogo = sum(1 for x in saida_itens if not x["automatico"])
    if n_diogo:
        motivos.append("%d item(ns) precisa(m) do Diogo" % n_diogo)
    motivos += ["gate: %s" % g for g in gate_falhas] + ["teto: %s" % t for t in teto]
    motivos += ["plugin acima do limite: %s" % g for g in grandes]
    motivos += ["julgado existente reescrito: %s" % m for m in reescritos]
    motivos += ["arquivo sem item: %s" % m for m in sobra]
    varr_geral = varrer(amb, [m for m in mudados if m not in atribuidos])
    motivos += varr_geral
    antes_do_ci = not motivos and bool(saida_itens)
    if not saida_itens:
        motivos.append("nenhum item")
    # a condição 9 (CI) fica pendente aqui: o PR só é automático depois do CI verde (Task 3b)
    conj = {"pr_automatico": False, "pr_automatico_antes_do_ci": antes_do_ci,
            "motivos": motivos + ["CI pendente (condição 9)"], "ci": "pendente",
            "julgados_novos": jul_novos, "normas_alteradas": normas_alt, "plugins": plugins,
            "arquivos_mudados": len(mudados)}
    if amb.sombra:
        conj.update({"sombra": True, "registro": "decisão do critério (sombra: a Task 3b não faz merge)"})
    return {"execucao_id": amb.execucao_id, "gerado_em": amb.hoje, "sombra": amb.sombra,
            "itens": saida_itens, "conjunto": conj}


def custo_llm(saida):
    total, n = 0.0, 0
    for c in glob.glob(os.path.join(saida, "**", "log.jsonl"), recursive=True):
        v = je.custo(ler_texto(c) or "")
        if v is not None:
            total += v
            n += 1
    return round(total, 4), n


def resumo_md(crit, resultados, adiados, custo, n_logs):
    c = crit["conjunto"]
    md = ["# Atualização automática do acervo (%s)" % crit["gerado_em"], ""]
    if crit["sombra"]:
        md += ["Execução em sombra: o critério registra a decisão, mas não há merge.", ""]
    md += ["Execução: `%s`." % crit["execucao_id"], ""]
    md += ["Decisão do critério: **%s**." % (
        "PR automático" if c["pr_automatico"] else
        "PR automático depois do CI verde" if c.get("pr_automatico_antes_do_ci") else "precisa do Diogo"), ""]
    if c["motivos"]:
        md += ["Motivos:", ""] + ["- %s" % m for m in c["motivos"]] + [""]
    md += ["| Item | Classe | Estado | Automático | Motivo |", "|---|---|---|---|---|"]
    for x in crit["itens"]:
        md.append("| %s | %s | %s | %s | %s |" % (x["id"], x["classe"], x["estado"], "sim" if x["automatico"] else "não",
                                                 (x["motivo"] or "").replace("|", "/")))
    md += ["", "Condições (por item): %s; a 9 (CI) fica pendente até o PR." % ", ".join(CONDICOES), ""]
    if adiados:
        md += ["Julgados adiados (acima do teto de %d por execução): %d." % (TETO_JULGADOS, len(adiados)), ""]
    md += ["Julgados novos: %d; normas alteradas: %d." % (c["julgados_novos"], c["normas_alteradas"]),
           "Custo de LLM (stream-json, %d log(s)): US$ %.4f." % (n_logs, custo), ""]
    return "\n".join(md)


# ---------------------------------------------------------------- principal

def limpar_saidas(amb):
    """Apaga as saídas de execução anterior: a 3b só lê o que esta execução gravou."""
    for nome in SAIDAS:
        if os.path.exists(amb.s(nome)):
            os.remove(amb.s(nome))


def executar(amb, itens):
    limpar_saidas(amb)
    amb.hash_antes = foto_hash(amb.raiz)
    resultados, adiados = aplicar(amb, itens)
    rc, out, err = amb.script("indice.py")
    gate = []
    if rc != 0:
        gate.append("indice.py rc %s: %s" % (rc, ((err or out).strip().splitlines() or [""])[-1][:200]))
    depois = foto_hash(amb.raiz)
    mudados = diferentes(amb.hash_antes, depois)
    gate += rodar_gate(amb)
    crit = criterio(amb, resultados, mudados, gate, tamanho_plugins(amb), adiados)
    custo, n_logs = custo_llm(amb.saida)
    crit["conjunto"]["custo_llm_usd"] = custo
    det.gravar_json(amb.s("criterio.json"), crit)
    por_chave = {x["chave"]: x for x in crit["itens"]}
    auto = [{"id": r["id"], "chave": r["chave"], "classe": r["classe"], "estado": r["estado"],
             "arquivos": [m for m in mudados if m in r["arquivos"]]}
            for r in resultados.values() if r["chave"] in por_chave and por_chave[r["chave"]]["automatico"]]
    diogo = [{"id": r["id"], "chave": r["chave"], "classe": r["classe"],
              "motivo": por_chave[r["chave"]]["motivo"] or r["motivo"],
              "o_que_seria_feito": r["o_que_seria_feito"], "diff": r["diff"]}
             for r in resultados.values() if r["chave"] in por_chave and not por_chave[r["chave"]]["automatico"]]
    det.gravar_json(amb.s("itens-automaticos.json"), {"execucao_id": amb.execucao_id, "itens": auto})
    det.gravar_json(amb.s("itens-diogo.json"), {"execucao_id": amb.execucao_id, "itens": diogo})
    with open(amb.s("resumo.md"), "w", encoding="utf-8") as f:
        f.write(resumo_md(crit, resultados, adiados, custo, n_logs))
    return crit


def main(argv=None, rodar=None, rede=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deteccao", action="append", required=True)
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--saida")
    ap.add_argument("--sombra", action="store_true")
    ap.add_argument("--sem-llm", action="store_true")
    ap.add_argument("--max-julgados", type=int, default=TETO_JULGADOS)
    ap.add_argument("--trabalho", help="base das pastas de trabalho do claude -p (fora do cofre e do repo)")
    a = ap.parse_args(argv)
    saida = a.saida or os.path.dirname(os.path.abspath(a.deteccao[0]))
    amb = Ambiente(a.raiz, saida, sem_llm=a.sem_llm, sombra=a.sombra, rodar=rodar, rede=rede,
                   trabalho=a.trabalho, max_julgados=a.max_julgados)
    limpar_saidas(amb)
    try:
        itens, _ = unir_deteccoes(a.deteccao)
        crit = executar(amb, itens)
    except Exception as e:  # noqa: BLE001 — qualquer exceção é falha da execução (rc != 0)
        import traceback
        traceback.print_exc()
        print("atualizar: execução %s falhou: %s: %s" % (amb.execucao_id, type(e).__name__, e), file=sys.stderr)
        return 2
    c = crit["conjunto"]
    print(json.dumps({"execucao_id": amb.execucao_id, "pr_automatico": c["pr_automatico"],
                      "pr_automatico_antes_do_ci": c["pr_automatico_antes_do_ci"], "sombra": amb.sombra,
                      "itens": len(crit["itens"]),
                      "automaticos": sum(1 for x in crit["itens"] if x["automatico"]),
                      "custo_llm_usd": c.get("custo_llm_usd"), "saida": amb.saida}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
