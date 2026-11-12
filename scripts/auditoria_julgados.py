#!/usr/bin/env python3
"""Auditoria da Fase 3b (julgados): universo, sorteio, insumos cegos por lote, comparador,
censos por script e runner das sessões auditoras.

  python3 scripts/auditoria_julgados.py universo [--saida dados/fase-3b/universo.json]
  python3 scripts/auditoria_julgados.py sortear [--semente 20261103] [--saida fontes/amostra-fase3b.json]
  python3 scripts/auditoria_julgados.py sortear --semente 20261104 --estratos A/pas-pdf,B/tc
      (re-auditoria: só os estratos dados, sem os itens já sorteados em fontes/amostra-fase3b.json;
       grava fontes/amostra-fase3b-20261104.json)
  python3 scripts/auditoria_julgados.py insumos --amostra fontes/amostra-fase3b.json --saida <pasta>
  python3 scripts/auditoria_julgados.py comparar --amostra fontes/amostra-fase3b.json --saidas <pasta>
      [--relatorio dados/fase-3b/comparacao.json]
  python3 scripts/auditoria_julgados.py censos [--relatorio dados/fase-3b/censos.json]
  python3 scripts/auditoria_julgados.py rodar --lotes <pasta fora do cofre> [--paralelo 4]

Blocos e estratos: seção 1 do plano da Fase 3b (A texto, B metadados, C resultado/ementa/tema,
D citações, E dados pessoais, F completude e CRSFN). Estrato F/crsfn-cvm-preambulo: CRSFN
classificado como não CVM com "CVM" ou "Comissão de Valores Mobiliários" nas 2 primeiras páginas
da fonte (CRITERIO_F; o critério estrito, só o preâmbulo antes da EMENTA, dava 2 itens e fica no
censo (c)). Sorteio: um random.Random(semente) sobre o
universo ordenado por (bloco, estrato, id); em cada estrato, a ordem embaralhada é percorrida até
completar o tamanho, pulando o julgado em que não há trecho válido (página sem texto, trecho sem
citação ou sem qualificação pessoal). O localizador (página do PDF ou blocos do HTML da fonte em
cache) é sorteado com o mesmo gerador. A amostra guarda só ids, caminhos e localizadores.

Insumos: cada lote (até 10 itens do mesmo estrato) é uma pasta só com `itens.json`, os insumos
recortados da fonte em cache e o `PROMPT.md`; o id do item é opaco (`A001`), para não entregar
data nem processo ao auditor. O modelo de cada lote fica em `<saida>/lotes.json`, fora dos lotes.
Comparador: texto normalizado (auditoria_texto) com hifenização do PDF e º/o como não erro,
campos normalizados, precisão e recall das citações e respostas fechadas; leitura fora da pasta do
lote no log stream-json = "vazou".
"""
import argparse
import concurrent.futures
import datetime
import glob
import json
import logging
import os
import random
import re
import subprocess
import sys
import unicodedata

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import auditoria as AU  # noqa: E402
import auditoria_texto as T  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_extracao as je  # noqa: E402

RAIZ = jc.RAIZ
SEMENTE = 20261103
SEMENTE_REAUDITORIA = 20261104
LOTE_MAX = 10
PARALELO_MAX = 4
MIN_CARACTERES = 300   # página de PDF com texto (pypdf) que vale como trecho
MIN_PALAVRAS_HTML = 120
MAX_BLOCOS = 8
MARCA_PII = jc.PII
PAGINAS_HTML = ("pagina", "noticia")

# (bloco, estrato): (rótulo, tamanho da amostra, universo do plano)
ESTRATOS = {
    ("A", "pas-pdf"): ("PAS, PDF com texto", 20, 1345),
    ("A", "pas-ocr"): ("PAS, OCR", 10, 74),
    ("A", "colegiado-html"): ("Colegiado, HTML", 15, 3506),
    ("A", "colegiado-pdf"): ("Colegiado, anexo em PDF", 20, 6897),
    ("A", "colegiado-ocr"): ("Colegiado, OCR", 8, 98),
    ("A", "tc-pdf"): ("TC, PDF com texto", 12, 1502),
    ("A", "tc-ocr"): ("TC, OCR", 8, 131),
    ("A", "tc-html"): ("TC, extrato HTML", 4, 81),
    ("A", "crsfn-html"): ("CRSFN, HTML", 8, 569),
    ("A", "crsfn-pdf"): ("CRSFN, PDF", 10, 772),
    ("A", "antigas"): ("Decisões antigas (PDF anual)", 6, 24),
    ("B", "pas"): ("Metadados, PAS", 15, 1419),
    ("B", "colegiado"): ("Metadados, Colegiado", 20, 10501),
    ("B", "tc"): ("Metadados, TC", 15, 1714),
    ("B", "crsfn"): ("Metadados, CRSFN", 10, 1342),
    ("C", "resultado-colegiado"): ("Resultado, Colegiado", 40, None),
    ("C", "resultado-tc"): ("Resultado, TC", 20, None),
    ("C", "resultado-pas"): ("Resultado, PAS", 10, None),
    ("C", "resultado-crsfn"): ("Resultado, CRSFN", 10, None),
    ("C", "ementa-tema"): ("Ementa extraída e tema (mesmos itens)", 40, 7830),
    ("D", "citacoes"): ("Julgados com dispositivo citado", 40, 11921),
    ("E", "qualificacao"): ("Termos e extratos do SEI com dado pessoal retirado", 40, 700),
    ("F", "crsfn-cvm-preambulo"): ("CRSFN não CVM com CVM nas 2 primeiras páginas", 30, None),
}
PLANO_EXTRA = {"C/resultado (total)": 13763, "C/tema (total)": 14976,
               "F/inventario-cvm": 13752, "F/crsfn-classificados": 11906,
               "F/crsfn-indeterminado": 39}
ESTRATO_A = {("pas", "pdf-extraido"): "pas-pdf", ("pas", "ocr"): "pas-ocr",
             ("decisao-colegiado", "html-convertido"): "colegiado-html",
             ("decisao-colegiado", "pdf-extraido"): "colegiado-pdf",
             ("decisao-colegiado", "ocr"): "colegiado-ocr",
             ("termo-compromisso", "pdf-extraido"): "tc-pdf",
             ("termo-compromisso", "ocr"): "tc-ocr",
             ("termo-compromisso", "html-convertido"): "tc-html",
             ("acordao-crsfn", "html-convertido"): "crsfn-html",
             ("acordao-crsfn", "pdf-extraido"): "crsfn-pdf",
             ("acordao-crsfn", "ocr"): "crsfn-pdf"}
CURTO = {"pas": "pas", "decisao-colegiado": "colegiado", "termo-compromisso": "tc",
         "acordao-crsfn": "crsfn"}
CAMPOS_B = ("data", "processo", "relator", "tipo", "classe")
CAMPOS_FICHA = CAMPOS_B + ("resultado",)

# Sinal de qualificação pessoal na fonte (mais largo que o pii.py, de propósito: o bloco E quer
# achar também o que a regra deixou passar).
QUALIFICACAO = re.compile(
    r"\b(?:CPF|C\.\s?P\.\s?F|RG\b|identidade|residente|domiciliad[oa]|brasileir[oa]s?|"
    r"casad[oa]|solteir[oa]|divorciad[oa]|vi[uú]v[oa]|nascid[oa]|portador[a]?|e-mail|telefone|"
    r"ag[êe]ncia)\b", re.I)
CRITERIO_F = ("acordao-crsfn classificado como não CVM (crsfn-classificacao.json) com 'CVM' ou "
              "'Comissão de Valores Mobiliários' nas 2 primeiras páginas da fonte em cache (pypdf) "
              "ou no primeiro documento do HTML do SEI; inclui os do critério estrito (preâmbulo "
              "antes da EMENTA)")
CVM_NO_TEXTO = re.compile(r"COMISS[ÃA]O\s+DE\s+VALORES\s+MOBILI[ÁA]RIOS|\bCVM\b", re.I)


def caminhos(raiz=RAIZ):
    d3b = os.path.join(raiz, "dados", "fase-3b")
    d2d = os.path.join(raiz, "dados", "fase-2d")
    return {"dados": d3b, "cache": os.path.join(d2d, "cache"),
            "classificacao": os.path.join(d2d, "crsfn-classificacao.json"),
            "inventario": os.path.join(raiz, "fontes", "julgados-inventario.json"),
            "resultados": os.path.join(raiz, "fontes", "RESULTADOS.md"),
            "universo": os.path.join(d3b, "universo.json"),
            "preambulos": os.path.join(d3b, "preambulos-crsfn.json"),
            "censos": os.path.join(d3b, "censos.json"),
            "comparacao": os.path.join(d3b, "comparacao.json"),
            "amostra": os.path.join(raiz, "fontes", "amostra-fase3b.json"),
            "temas": os.path.join(raiz, "scripts", "prompts", "julgados-extracao.md")}


INDICE_JULGADOS = ("plugins", "normas", "skills", "consultar-normas", "julgados")
_PREFIXO_ARQUIVO = re.compile(r"^(?:\.\./)*julgados/")


def _rel(p, raiz):
    return os.path.relpath(p, raiz)


def _agora():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- base publicada e fontes


def publicados(raiz=RAIZ, com_corpo=False):
    """[{id, tipo, nivel, data, arquivo, ...}] dos julgados de `julgados/` (ordem do caminho)."""
    out = []
    for c in sorted(glob.glob(os.path.join(raiz, "julgados", "**", "*.md"), recursive=True)):
        if os.sep + "indices" + os.sep in c or os.path.basename(c) == "indice.md":
            continue
        try:
            v, corpo = je.ler_julgado(c)
        except ValueError:
            continue
        if not v.get("id"):
            continue
        j = {"id": v["id"], "tipo": v.get("tipo", ""), "nivel": v.get("nivel_verificacao", ""),
             "data": v.get("data", ""), "arquivo": _rel(c, raiz),
             "ementa_fonte": v.get("ementa_fonte", ""), "resultado": v.get("resultado", ""),
             "tema": v.get("tema", ""), "dispositivos": v.get("dispositivos_citados", ""),
             "pii": MARCA_PII in corpo, "sha256_fonte": v.get("sha256_fonte", "")}
        if com_corpo:
            j["valores"], j["corpo"] = v, corpo
        out.append(j)
    return out


def _ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def mapa_fontes(raiz=RAIZ):
    """{id: [{arquivo (relativo à raiz), papel, ext, content_type}]} da fonte em cache: registro.json
    de cada julgado da CVM e o arquivo do CRSFN indicado na classificação."""
    cam = caminhos(raiz)
    m = {}
    for r in sorted(glob.glob(os.path.join(cam["cache"], "*", "*", "*", "registro.json"))):
        reg = _ler_json(r, {})
        pasta = os.path.dirname(r)
        m[reg.get("id") or os.path.basename(pasta)] = [
            {"arquivo": _rel(os.path.join(pasta, a["arquivo"]), raiz), "papel": a.get("papel", ""),
             "ext": os.path.splitext(a["arquivo"])[1].lower(),
             "content_type": a.get("content_type", "")}
            for a in reg.get("arquivos", []) if os.path.exists(os.path.join(pasta, a["arquivo"]))]
    cl = _ler_json(cam["classificacao"], {}) or {}
    for id_, it in (cl.get("itens") or {}).items():
        if it.get("cache"):
            p = os.path.join(cam["cache"], "crsfn", it["cache"])
            if os.path.exists(p):
                m[id_] = [{"arquivo": _rel(p, raiz), "papel": "acordao",
                           "ext": os.path.splitext(p)[1].lower(), "content_type": ""}]
    return m


# ---------------------------------------------------------------- leitura da fonte

_PDF = {}


def paginas_pdf(caminho):
    """Texto de cada página pelo pypdf (normalizado como no conversor); [] se não abre."""
    if caminho not in _PDF:
        try:
            from pypdf import PdfReader  # dependência opcional
            logging.getLogger("pypdf").setLevel(logging.ERROR)
            leitor = PdfReader(caminho)
            pags = []
            for p in leitor.pages:
                try:
                    pags.append(jc.normalizar_pdf(p.extract_text() or ""))
                except Exception:  # noqa: BLE001 — página ilegível vale como sem texto
                    pags.append("")
        except Exception:  # noqa: BLE001 — sem pypdf ou PDF quebrado
            pags = []
        if len(_PDF) > 200:
            _PDF.clear()
        _PDF[caminho] = pags
    return _PDF[caminho]


def html_fonte(caminho, content_type=""):
    with open(caminho, "rb") as f:
        return jc.decodificar(f.read(), {"content-type": content_type})


def _corpo_html(html, papel):
    if papel in PAGINAS_HTML:
        m = re.search(r"<article\b[^>]*contentTextoGeral[^>]*>(.*?)</article>", html, re.S | re.I)
        if m:
            return m.group(1)
    corpo = T.corpo_html(html)[1]
    return re.sub(r"(?is)<img\b[^>]*>|<script\b.*?</script\s*>", "", corpo)


def blocos_fonte(raiz, fonte):
    html = html_fonte(os.path.join(raiz, fonte["arquivo"]), fonte.get("content_type", ""))
    return T.blocos_html(_corpo_html(html, fonte.get("papel", "")))


def _eh_pdf(f):
    return f["ext"] == ".pdf"


def _eh_html(f):
    return f["ext"] in (".html", ".htm")


def ancora(raiz, loc):
    """Texto da fonte no localizador (página do PDF pelo pypdf ou texto visível dos blocos)."""
    caminho = os.path.join(raiz, loc["fonte"])
    if "blocos" in loc:
        k0, k1 = loc["blocos"]
        return T.texto_visivel("".join(blocos_fonte(raiz, {"arquivo": loc["fonte"],
                                                           "papel": loc.get("papel", "")})[k0:k1]))
    pags = paginas_pdf(caminho)
    return "\n".join(pags[p - 1] for p in loc.get("paginas", []) if 0 < p <= len(pags))


# ---------------------------------------------------------------- estratos e universo


def estratos_do_julgado(j, fontes):
    """[(bloco, estrato)] de um julgado publicado (os blocos A a E)."""
    out = []
    t = j["tipo"]
    if t == "decisao-antiga":
        out.append(("A", "antigas"))
    elif (t, j["nivel"]) in ESTRATO_A:
        out.append(("A", ESTRATO_A[(t, j["nivel"])]))
    if t in CURTO:
        out.append(("B", CURTO[t]))
        if j["resultado"]:
            out.append(("C", "resultado-" + CURTO[t]))
    if j["ementa_fonte"] == "extracao":
        out.append(("C", "ementa-tema"))
    if j["dispositivos"]:
        out.append(("D", "citacoes"))
    sei = any(f["papel"] == "sei" or (t == "acordao-crsfn" and _eh_html(f)) for f in fontes)
    if j["pii"] and (t == "termo-compromisso" or sei):
        out.append(("E", "qualificacao"))
    return out


def preambulo_crsfn(caminho):
    """Texto do preâmbulo do acórdão (antes da EMENTA) e das 2 primeiras páginas, sem macOS."""
    import crsfn
    import julgados_converter as jconv
    if caminho.endswith((".html", ".htm")):
        with open(caminho, "rb") as f:
            inicio = crsfn.documentos(jconv.sei_para_md(jc.decodificar(f.read())))[0]
    else:
        inicio = jc.normalizar_pdf(crsfn._pypdf_inicio(caminho))
    return crsfn.preambulo(inicio), inicio


def censo_preambulos(raiz=RAIZ, log=print, gravar=True):
    """{id: {orgao, criterio, texto, cvm_preambulo, cvm_inicio}} dos acórdãos do CRSFN não
    classificados como CVM, com fonte em cache. Guarda em dados/fase-3b/preambulos-crsfn.json
    (reaproveitado se o tamanho do arquivo não mudou)."""
    cam = caminhos(raiz)
    cl = _ler_json(cam["classificacao"], {}) or {}
    antes = _ler_json(cam["preambulos"], {}) or {}
    out, n = {}, 0
    for id_, it in sorted((cl.get("itens") or {}).items()):
        if it.get("orgao") == "CVM":
            continue
        reg = {"orgao": it.get("orgao", ""), "criterio": it.get("criterio", ""), "cache": "",
               "texto": False, "cvm_preambulo": False, "cvm_inicio": False}
        p = os.path.join(cam["cache"], "crsfn", it.get("cache") or "")
        if not it.get("cache") or not os.path.exists(p):
            out[id_] = reg
            continue
        tam = os.path.getsize(p)
        if antes.get(id_, {}).get("tamanho") == tam:
            out[id_] = antes[id_]
            continue
        pre, inicio = preambulo_crsfn(p)
        reg.update(cache=it["cache"], tamanho=tam, texto=len(inicio.strip()) >= 50,
                   cvm_preambulo=bool(CVM_NO_TEXTO.search(pre)),
                   cvm_inicio=bool(CVM_NO_TEXTO.search(inicio)))
        out[id_] = reg
        n += 1
        if n % 1000 == 0:
            log("preâmbulos lidos: %d" % n)
    if gravar:
        AU._gravar_json(cam["preambulos"], out)
    return out


def universo(raiz=RAIZ, preambulos=None, log=print):
    pubs = publicados(raiz)
    fontes = mapa_fontes(raiz)
    grupos = {k: [] for k in ESTRATOS}
    sem_fonte, extra = [], {"C/resultado (total)": 0, "C/tema (total)": 0}
    for j in pubs:
        fj = fontes.get(j["id"])
        if not fj:
            sem_fonte.append(j["id"])
            continue
        for k in estratos_do_julgado(j, fj):
            grupos[k].append(j["id"])
        extra["C/resultado (total)"] += bool(j["resultado"])
        extra["C/tema (total)"] += bool(j["tema"])
    if preambulos is None:
        preambulos = censo_preambulos(raiz, log=log)
    grupos[("F", "crsfn-cvm-preambulo")] = sorted(i for i, r in preambulos.items()
                                                  if r.get("cvm_inicio"))
    cl = _ler_json(caminhos(raiz)["classificacao"], {}) or {}
    orgaos = {}
    for it in (cl.get("itens") or {}).values():
        orgaos[it.get("orgao", "")] = orgaos.get(it.get("orgao", ""), 0) + 1
    inv = _ler_json(caminhos(raiz)["inventario"], []) or []
    extra.update({"F/inventario-cvm": len(inv),
                  "F/crsfn-classificados": len(cl.get("itens") or {}),
                  "F/crsfn-indeterminado": orgaos.get("INDETERMINADO", 0),
                  "F/crsfn-erros-classificacao": len(cl.get("erros") or {}),
                  "F/crsfn-orgaos": orgaos,
                  "F/crsfn-cvm-nas-2-paginas": sum(1 for r in preambulos.values()
                                                   if r.get("cvm_inicio")),
                  "F/crsfn-sem-texto-pypdf": sum(1 for r in preambulos.values()
                                                 if r.get("cache") and not r.get("texto")),
                  "F/crsfn-sem-cache": sum(1 for r in preambulos.values() if not r.get("cache")),
                  "E/pii-fora-do-estrato": {}})
    for j in pubs:
        if j["pii"] and j["id"] not in set(grupos[("E", "qualificacao")]):
            d = extra["E/pii-fora-do-estrato"]
            d[j["tipo"]] = d.get(j["tipo"], 0) + 1
    ests = []
    for (b, e), ids in sorted(grupos.items()):
        rot, n, plano = ESTRATOS[(b, e)]
        ests.append({"bloco": b, "estrato": e, "rotulo": rot, "n": len(ids), "plano": plano,
                     "amostra": n, "ids": sorted(ids)})
        if (b, e) == ("F", "crsfn-cvm-preambulo"):
            ests[-1]["criterio"] = CRITERIO_F
    return {"gerado_em": _agora(), "publicados": len(pubs), "sem_fonte_em_cache": sem_fonte,
            "estratos": ests, "extra": extra, "plano_extra": PLANO_EXTRA}


def _dif(n, plano):
    if not plano:
        return ""
    d = (n - plano) / plano
    return "%+.1f%%%s" % (100 * d, "  <-- difere >5%" if abs(d) > 0.05 else "")


def resumo_universo(u):
    linhas = ["universo: %d julgados publicados; %d sem fonte em cache" % (
        u["publicados"], len(u["sem_fonte_em_cache"]))]
    for e in u["estratos"]:
        linhas.append("  %s/%-22s %6d  plano %6s  amostra %3d  %s" % (
            e["bloco"], e["estrato"], e["n"], e["plano"] if e["plano"] is not None else "-",
            e["amostra"], _dif(e["n"], e["plano"])))
    for k, v in sorted(u["extra"].items()):
        p = u["plano_extra"].get(k)
        linhas.append("  %-32s %s%s" % (k, v, ("  plano %s  %s" % (p, _dif(v, p))) if p else ""))
    return "\n".join(linhas)


# ---------------------------------------------------------------- sorteio e localizadores


def _trecho(rng, raiz, fontes, filtro=None, exigir_texto=True):
    """Localizador de um trecho: uma página de PDF (com texto, se `exigir_texto`) ou uma sequência
    de blocos do HTML, que passe no `filtro` (texto -> bool). None se não houver."""
    ordem = list(fontes)
    rng.shuffle(ordem)
    for f in ordem:
        if _eh_pdf(f):
            pags = paginas_pdf(os.path.join(raiz, f["arquivo"]))
            cand = [i for i, t in enumerate(pags)
                    if (not exigir_texto or len(t.strip()) >= MIN_CARACTERES)
                    and (filtro is None or filtro(t))]
            if cand:
                p = rng.choice(cand)
                return {"fonte": f["arquivo"], "paginas": [p + 1],
                        "ancora": "fonte" if len(pags[p].strip()) >= MIN_CARACTERES else "saida"}
        elif _eh_html(f):
            try:
                blocos = blocos_fonte(raiz, f)
            except OSError:
                continue
            ws = [len(T.palavras(T.texto_visivel(b))) for b in blocos]
            inicios = [k for k, w in enumerate(ws) if w >= 5]
            rng.shuffle(inicios)
            for k in inicios:
                k1, tot = k, 0
                while k1 < len(blocos) and tot < MIN_PALAVRAS_HTML and k1 - k < MAX_BLOCOS:
                    tot += ws[k1]
                    k1 += 1
                if filtro is None or filtro(T.texto_visivel("".join(blocos[k:k1]))):
                    return {"fonte": f["arquivo"], "papel": f["papel"], "blocos": [k, k1],
                            "ancora": "fonte"}
    return None


def _n_paginas(raiz, f):
    try:
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        return len(PdfReader(os.path.join(raiz, f["arquivo"])).pages)
    except Exception:  # noqa: BLE001
        return 0


def pecas(raiz, j, fontes, so_inicio=False):
    """Peças da fonte para a ficha cega (B, C) e para o bloco F: o HTML do item no Colegiado e no
    TC; a primeira e a última página do PAS e do acórdão do CRSFN (até 4 páginas no total)."""
    pag = [f for f in fontes if f["papel"] in PAGINAS_HTML and _eh_html(f)]
    sei = [f for f in fontes if _eh_html(f) and f["papel"] not in PAGINAS_HTML]
    pdfs = [f for f in fontes if _eh_pdf(f)]
    t = j["tipo"]

    def html(f):
        return {"fonte": f["arquivo"], "papel": f["papel"]}

    if t in ("decisao-colegiado", "termo-compromisso") and pag:
        return [html(pag[0])]
    if t == "acordao-crsfn" and sei:
        return [html(sei[0])]
    out = [html(pag[0])] if t == "pas" and pag and not so_inicio else []
    if pdfs:
        a, b = pdfs[0], pdfs[-1]
        na = _n_paginas(raiz, a)
        if so_inicio:
            if na:
                out.append({"fonte": a["arquivo"], "paginas": list(range(1, min(2, na) + 1))})
        elif a is b:
            if na:
                ps = list(range(1, na + 1)) if na <= AU.MAX_PAGINAS else [1, 2, na - 1, na]
                out.append({"fonte": a["arquivo"], "paginas": ps})
        else:
            nb = _n_paginas(raiz, b)
            if na:
                out.append({"fonte": a["arquivo"], "paginas": list(range(1, min(2, na) + 1))})
            if nb:
                out.append({"fonte": b["arquivo"], "paginas": list(range(max(1, nb - 1), nb + 1))})
    elif sei:
        out.append(html(sei[0]))
    return out or None


def _paragrafos(corpo):
    """[(início, fim)] em caracteres de cada parágrafo (separados por linha em branco)."""
    return [(m.start(), m.end()) for m in re.finditer(r"(?s)\S.*?(?=\n\s*\n|\Z)", corpo)]


def trecho_acervo(corpo, alvo, margem=1):
    """Parágrafos do corpo publicado que cobrem o `alvo` (texto da fonte), mais `margem` de cada
    lado, como estão no arquivo. "" se a janela não acha o alvo."""
    _, i0, i1 = T.janela(corpo, alvo)
    if i1 <= i0:
        return ""
    pars = _paragrafos(corpo)
    acum, dono = 0, []
    for k, (a, b) in enumerate(pars):
        n = len(T.palavras(corpo[a:b]))
        dono.append((acum, acum + n))
        acum += n
    ks = [k for k, (a, b) in enumerate(dono) if b > i0 and a < i1]
    if not ks:
        return ""
    k0, k1 = max(0, ks[0] - margem), min(len(pars), ks[-1] + 1 + margem)
    return corpo[pars[k0][0]:pars[k1 - 1][1]]


def trecho_por_marcador(corpo, k, margem=2):
    """Parágrafos em volta da k-ésima marca de dado pessoal retirado."""
    pos = [m.start() for m in re.finditer(re.escape(MARCA_PII), corpo)]
    if not pos:
        return ""
    alvo = pos[min(k, len(pos) - 1)]
    pars = _paragrafos(corpo)
    ks = [i for i, (a, b) in enumerate(pars) if a <= alvo < b] or [0]
    k0, k1 = max(0, ks[0] - margem), min(len(pars), ks[0] + 1 + margem)
    return corpo[pars[k0][0]:pars[k1 - 1][1]]


def dispositivos_do_trecho(texto):
    """Dispositivos que o citacoes.py extrai do texto (a mesma rotina do conversor)."""
    import julgados_converter as jconv
    _n, disp, _aviso = jconv.citacoes(texto)
    return [x.strip() for x in (disp or "").split(";") if x.strip()]


def _corpo(raiz, j):
    return je.ler_julgado(os.path.join(raiz, j["arquivo"]))[1]


def _por_posicao(rng, raiz, fontes, corpo):
    """Bloco E sem texto na fonte (OCR): a página estimada pela posição de uma marca no corpo."""
    pdfs = [(f, _n_paginas(raiz, f)) for f in fontes if _eh_pdf(f)]
    pdfs = [(f, n) for f, n in pdfs if n]
    marcas = [m.start() for m in re.finditer(re.escape(MARCA_PII), corpo)]
    if not pdfs or not marcas:
        return None
    k = rng.randrange(len(marcas))
    total = sum(n for _f, n in pdfs)
    g = min(total - 1, int(marcas[k] / max(1, len(corpo)) * total))
    for f, n in pdfs:
        if g < n:
            ps = [g + 1] + ([g + 2] if g + 1 < n else [])
            return {"fonte": f["arquivo"], "paginas": ps, "ancora": "posicao", "marcador": k}
        g -= n
    return None


def localizar(bloco, estrato, j, fontes, rng, raiz=RAIZ):
    """Localizador do item sorteado, ou None se o julgado não tem trecho válido."""
    if not fontes:
        return None
    if bloco == "A":
        if estrato.endswith("-html"):
            return _trecho(rng, raiz, [f for f in fontes if _eh_html(f)])
        pdfs = [f for f in fontes if _eh_pdf(f)]
        if estrato.endswith("-ocr"):
            return _trecho(rng, raiz, pdfs, exigir_texto=False)
        return _trecho(rng, raiz, pdfs) or _trecho(rng, raiz, pdfs, exigir_texto=False)
    if bloco in ("B", "C"):
        ps = pecas(raiz, j, fontes)
        return {"pecas": ps} if ps else None
    if bloco == "F":
        ps = pecas(raiz, j, fontes, so_inicio=True)
        return {"pecas": ps} if ps else None
    if bloco == "D":
        return _trecho(rng, raiz, fontes, filtro=lambda t: bool(dispositivos_do_trecho(t)))
    if bloco == "E":
        corpo = _corpo(raiz, j)
        loc = _trecho(rng, raiz, fontes, filtro=lambda t: bool(QUALIFICACAO.search(t))
                      and bool(trecho_acervo(corpo, t)))
        return loc or _por_posicao(rng, raiz, fontes, corpo)
    raise ValueError("bloco desconhecido: %s" % bloco)


def _j_crsfn(id_):
    return {"id": id_, "tipo": "acordao-crsfn", "arquivo": ""}


def sortear(univ, semente, raiz=RAIZ, estratos=None, excluir=(), log=print):
    rng = random.Random(semente)
    pubs = {j["id"]: j for j in publicados(raiz)}
    fontes = mapa_fontes(raiz)
    excluir = set(excluir)
    itens, faltas, pulados, cont = [], [], {}, {}
    prefixo = "" if semente == SEMENTE else "R"
    for est in sorted(univ["estratos"], key=lambda e: (e["bloco"], e["estrato"])):
        b, e = est["bloco"], est["estrato"]
        chave = "%s/%s" % (b, e)
        if estratos and chave not in estratos:
            continue
        ordem = sorted(set(est["ids"]) - excluir)
        rng.shuffle(ordem)
        tomados = 0
        for id_ in ordem:
            if tomados >= est["amostra"]:
                break
            j = pubs.get(id_) or (_j_crsfn(id_) if b == "F" else None)
            if j is None:
                continue
            loc = localizar(b, e, j, fontes.get(id_, []), rng, raiz)
            if loc is None:
                pulados[chave] = pulados.get(chave, 0) + 1
                continue
            cont[b] = cont.get(b, 0) + 1
            it = {"uid": "%s%s%03d" % (prefixo, b, cont[b]), "bloco": b, "estrato": e,
                  "id": id_, "tipo": j["tipo"], "arquivo": j["arquivo"]}
            it.update(loc)
            itens.append(it)
            tomados += 1
        if tomados < est["amostra"]:
            faltas.append({"estrato": chave, "pedido": est["amostra"], "sorteado": tomados})
        log("  %-26s %3d de %3d (universo %d%s)" % (
            chave, tomados, est["amostra"], est["n"],
            ", %d pulados sem trecho válido" % pulados[chave] if pulados.get(chave) else ""))
    return {"semente": semente, "gerado_em": _agora(), "universo_gerado_em": univ.get("gerado_em"),
            "itens": itens, "faltas": faltas, "pulados": pulados}


# ---------------------------------------------------------------- insumos

REGRAS = """\
   - Leia e grave só arquivos desta pasta. Não abra nada fora dela, não use a web, não rode
     comandos, git nem commit.
   - PDF: cada `.pdf` desta pasta já tem só as páginas do item. Leia o arquivo inteiro com a
     ferramenta Read, sem o parâmetro `pages`.
   - HTML: vale o texto visível; ignore marcação, menus e links.
   - Grave um arquivo de saída por item, com o nome dado em `saida`, nesta pasta."""

PROMPT = """\
# Auditoria cega de julgados: %(titulo)s

Você confere, de forma independente, julgados da CVM e do CRSFN contra a fonte oficial. Nesta
pasta estão só os insumos.

1. Leia `itens.json`. Cada item tem `id`, a lista `insumos`, o arquivo de `saida`%(campos)s.
2. %(tarefa)s
3. Regras:
%(regras)s
%(extra)s
4. Ao terminar todos os itens, pare.
%(anexo)s"""

TAREFA_A = ("Para cada item, leia os insumos e siga a `instrucao`: transcreva o trecho da fonte "
            "em `<id>-saida.md`.")
EXTRA_A = """\
   - Transcreva o que a fonte diz, inclusive nomes e números. Não corrija a fonte, não complete
     lacuna e não resuma. Trecho ilegível vira `[ilegível]`.
   - Markdown simples: um parágrafo por linha, com linha em branco entre eles. Sem comentário seu
     dentro da saída.
   - Sem o cabeçalho e o rodapé que se repetem nas páginas e sem o número da página."""

FICHA = """\
## Ficha

Grave em `<id>-saida.json` um objeto JSON com exatamente estas chaves (texto; `""` quando a fonte
não traz o dado):

```json
{"data": "", "processo": "", "relator": "", "tipo": "", "classe": "", "resultado": ""}
```

- `data`: data da sessão de julgamento, da reunião do Colegiado ou da decisão, AAAA-MM-DD.
- `processo`: número(s) do processo como publicado(s) na fonte (ex.: `19957.001770/2022-12`,
  `RJ2015/1234`, `SP2007/0113`), separados por `; `, sem nome de parte.
- `relator`: nome ou sigla do relator (diretor relator ou área técnica relatora), como publicado.
- `tipo`, um destes:
  - `pas`: julgamento de processo administrativo sancionador pela CVM;
  - `termo-compromisso`: apreciação de proposta de termo de compromisso;
  - `decisao-colegiado`: demais deliberações do Colegiado da CVM;
  - `decisao-antiga`: decisão do Colegiado de 1978 a 2001 (PDF anual);
  - `acordao-crsfn`: acórdão do CRSFN em recurso.
- `classe`: só em `decisao-colegiado` (nos demais tipos, `""`), pelo assunto do item: `recurso`,
  `consulta`, `dispensa`, `registro`, `normativo`, `reconsideracao`, `incidente-pas`,
  `multa-cominatoria`, `institucional` ou `outros`.
- `resultado`, lista fechada por tipo (`""` se a fonte não traz deliberação de mérito):
  - `pas` e `acordao-crsfn`: `condenacao`, `absolvicao`, `parcial` (condenação e absolvição no
    mesmo processo), `extincao`, `arquivamento`, `outro`;
  - `termo-compromisso`: `aceito`, `rejeitado`, `outro`;
  - `decisao-colegiado` e `decisao-antiga`: `deferido`, `indeferido`, `provido`, `nao-provido`,
    `parcial`, `conhecimento`, `outro`.

Preencha pelo que a fonte diz, sem supor."""

TAREFA_B = ("Para cada item, leia as peças da fonte oficial de um julgado (os `insumos`) e preencha "
            "a ficha abaixo.")

TAREFA_C = ("Para cada item, leia a `ementa` e o `tema` dados no `itens.json` e a decisão da fonte "
            "oficial (os `insumos`), e responda às perguntas abaixo.")
PERGUNTAS_C = """\
## Perguntas

Grave em `<id>-saida.json`:

```json
{"afirma_sem_suporte": "nao", "omite_decisao": "nao", "nome_pessoa_fisica": "nao",
 "tema_defensavel": "sim", "observacao": ""}
```

- `afirma_sem_suporte`: `sim` se a ementa afirma algo que o texto da fonte não sustenta ou
  contradiz (parte, fato, norma, valor, resultado).
- `omite_decisao`: `sim` se a ementa não diz o que foi decidido, quando a fonte traz a decisão.
- `nome_pessoa_fisica`: `sim` se a ementa traz nome de pessoa física (nome completo, nome e
  sobrenome ou sobrenome composto). Nome de empresa, fundo ou entidade não conta; `[pessoa física]`
  é a marca de nome omitido e não conta.
- `tema_defensavel`: `sim` se o tema é uma leitura defensável do assunto principal do caso, pela
  tabela abaixo; `nao` se outro tema da tabela é claramente o certo.
- `observacao`: uma frase curta quando alguma resposta indica problema (sem copiar nome de pessoa).

%s"""

TAREFA_D = ("Para cada item, leia o trecho da fonte (os `insumos`) e a lista `dispositivos` do "
            "`itens.json`, extraída desse trecho por script, e marque o que está certo e o que falta.")
PERGUNTAS_D = """\
## Respostas

Grave em `<id>-saida.json`:

```json
{"dispositivos": [{"n": 1, "certo": "sim"}], "faltam": ["Lei 6.404/1976, art. 117, § 1º"]}
```

- `dispositivos`: uma entrada por item da lista, na ordem, com o `n` dado. `certo` é `sim` se o
  trecho cita esse dispositivo da norma indicada (artigo e, quando listados, parágrafo, inciso e
  alínea); `nao` se o trecho não o cita ou se a norma ou o dispositivo estão trocados.
- `faltam`: dispositivos que o trecho cita, com norma identificável, e que não estão na lista.
  Citação sem artigo (só a norma) não conta.

Notação da lista: `<norma> [parte ]art. N[, § N | , parágrafo único][, inciso X][, alínea y]`.
Normas: `lei-6404` = Lei nº 6.404/1976; `lcp-105` = Lei Complementar nº 105; `decreto-N`;
`cvm-res-N` = Resolução CVM nº N; `cvm-po-N` = Parecer de Orientação CVM nº N; `cmn-res-N` e
`bcb-res-N` = Resoluções do CMN e do BCB; `fora:` antecede norma fora do acervo, com rótulo
próprio (`fora:icvm-358` = Instrução CVM nº 358; `fora:deliberacao-cvm-538`; `fora:res-cmn-2689`;
`fora:lei-9784`)."""

TAREFA_E = ("Para cada item, compare o trecho da fonte oficial (`<id>-fonte...`) com o mesmo trecho "
            "no acervo (`<id>-acervo.md`), em que dados pessoais foram trocados por "
            "`[dado pessoal retirado]`.")
PERGUNTAS_E = """\
## Regra do acervo

Saem: CPF, RG e outros documentos de identidade, endereço residencial, e-mail pessoal, telefone,
data de nascimento, dados bancários, a qualificação pessoal (nacionalidade, estado civil,
profissão) e as linhas de testemunha. Ficam: nome da pessoa, cargo, CNPJ, nome e endereço de
empresa, e-mail institucional.

## Respostas

Grave em `<id>-saida.json`:

```json
{"dado_pessoal_restante": [], "corte_indevido": []}
```

- `dado_pessoal_restante`: um item por dado pessoal que a regra manda tirar e que ficou no trecho
  do acervo. Descreva o tipo e onde está (ex.: "CPF do segundo compromitente, 3º parágrafo"), sem
  copiar o número, o endereço nem o dado.
- `corte_indevido`: um item por `[dado pessoal retirado]` do acervo que cobre texto que não é dado
  pessoal (ex.: "cortou o nome da companhia junto com o endereço"), dizendo o que sumiu.
- Listas vazias quando não há."""

TAREFA_F = ("Para cada item, leia o início do acórdão do CRSFN (os `insumos`) e diga de que órgão "
            "vem a decisão recorrida.")
PERGUNTAS_F = """\
## Resposta

Grave em `<id>-saida.json`:

```json
{"orgao_de_origem": "", "trecho": ""}
```

- `orgao_de_origem`: `CVM`, `BCB`, `COAF`, `SUSEP`, `outro` ou `indeterminado`: o órgão que
  proferiu a decisão de primeira instância objeto do recurso (o recorrido ou o processo de
  origem), e não um órgão só mencionado.
- `trecho`: até 20 palavras da fonte que mostram o órgão (sem nome de pessoa)."""


def _temas(raiz):
    try:
        with open(caminhos(raiz)["temas"], encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return "## Temas\n\n" + "\n".join("- `%s`" % t for t in je.TEMAS)
    m = re.search(r"(?ms)^## Temas\n.*?(?=^## |\Z)", txt)
    return m.group(0).strip() if m else ""


def modelo_do_lote(bloco, estrato):
    """Opus transcreve PDF e OCR (bloco A); Sonnet faz o HTML e os blocos B a F (C5)."""
    return "opus" if bloco == "A" and not estrato.endswith("-html") else "sonnet"


def lotes(itens, lote_max=LOTE_MAX):
    """[(nome, [itens])]: mesmo bloco e estrato, na ordem da amostra, até `lote_max` por lote."""
    grupos, ordem = {}, []
    for u in itens:
        k = (u["bloco"], u["estrato"])
        if k not in grupos:
            grupos[k] = []
            ordem.append(k)
        grupos[k].append(u)
    res, n = [], 0
    for b, e in sorted(ordem):
        us = grupos[(b, e)]
        for i in range(0, len(us), lote_max):
            n += 1
            res.append(("%02d-%s-%s" % (n, b.lower(), e), us[i:i + lote_max]))
    return res


def _html_insumo(fragmento):
    return ('<!DOCTYPE html>\n<html><head><meta charset="utf-8"></head><body>\n%s\n</body></html>\n'
            % fragmento)


def _gravar_peca(raiz, peca, pasta, nome):
    """Grava a peça no lote; devolve o nome do arquivo."""
    origem = os.path.join(raiz, peca["fonte"])
    if "paginas" in peca:
        nome += ".pdf"
        AU.recortar_pdf(origem, peca["paginas"], os.path.join(pasta, nome))
        return nome
    html = html_fonte(origem)
    corpo = _corpo_html(html, peca.get("papel", ""))
    if "blocos" in peca:
        k0, k1 = peca["blocos"]
        corpo = "\n".join(T.blocos_html(corpo)[k0:k1])
    nome += ".html"
    AU._escrever(pasta, nome, _html_insumo(corpo))
    return nome


def _instrucao_a(u, nome):
    if nome.endswith(".pdf"):
        um = len(u["paginas"]) == 1
        return ("Leia o arquivo inteiro `%s`, sem o parâmetro `pages`: ele tem só %s da fonte. "
                "Transcreva %s em `%s-saida.md`, sem cabeçalho, rodapé e número de página."
                % (nome, "uma página" if um else "%d páginas, na ordem" % len(u["paginas"]),
                   "a página" if um else "as páginas como um texto só", u["uid"]))
    return ("`%s` é um trecho da fonte oficial (HTML). Transcreva o texto visível dele, na ordem, "
            "em `%s-saida.md`." % (nome, u["uid"]))


def montar_item(raiz, u, pasta):
    """Grava os insumos do item na pasta do lote; devolve a entrada do itens.json."""
    b = u["bloco"]
    ent = {"id": u["uid"], "insumos": [], "saida": u["uid"] + ("-saida.md" if b == "A"
                                                               else "-saida.json")}
    if b in ("A", "D", "E"):
        nome = _gravar_peca(raiz, u, pasta, u["uid"] + "-fonte")
        ent["insumos"].append(nome)
        if b == "A":
            ent["instrucao"] = _instrucao_a(u, nome)
        elif b == "D":
            disp = dispositivos_do_trecho(ancora(raiz, u))
            ent["dispositivos"] = [{"n": i + 1, "dispositivo": d} for i, d in enumerate(disp)]
        else:
            corpo = _corpo(raiz, u)
            if u.get("ancora") == "posicao":
                ac = trecho_por_marcador(corpo, u.get("marcador", 0))
            else:
                ac = trecho_acervo(corpo, ancora(raiz, u))
            AU._escrever(pasta, u["uid"] + "-acervo.md", ac.strip() + "\n")
            ent["insumos"].append(u["uid"] + "-acervo.md")
    else:
        for i, p in enumerate(u["pecas"], 1):
            ent["insumos"].append(_gravar_peca(raiz, p, pasta, "%s-fonte-%d" % (u["uid"], i)))
        if b == "C" and u["estrato"] == "ementa-tema":
            v, _ = je.ler_julgado(os.path.join(raiz, u["arquivo"]))
            ent["ementa"], ent["tema"] = v.get("ementa", ""), v.get("tema", "")
    return ent


def prompt_do_lote(raiz, bloco, estrato):
    base = {"regras": REGRAS, "extra": "", "anexo": "", "campos": ""}
    if bloco == "A":
        base.update(titulo="transcrição", tarefa=TAREFA_A, extra=EXTRA_A,
                    campos=" e a `instrucao`")
    elif bloco == "B" or (bloco == "C" and estrato.startswith("resultado")):
        base.update(titulo="ficha de campos", tarefa=TAREFA_B, anexo="\n" + FICHA + "\n")
    elif bloco == "C":
        base.update(titulo="ementa e tema", tarefa=TAREFA_C, campos=", a `ementa` e o `tema`",
                    anexo="\n" + PERGUNTAS_C % _temas(raiz) + "\n")
    elif bloco == "D":
        base.update(titulo="citações", tarefa=TAREFA_D, campos=" e a lista `dispositivos`",
                    anexo="\n" + PERGUNTAS_D + "\n")
    elif bloco == "E":
        base.update(titulo="dados pessoais", tarefa=TAREFA_E, anexo="\n" + PERGUNTAS_E + "\n")
    elif bloco == "F":
        base.update(titulo="órgão de origem no CRSFN", tarefa=TAREFA_F,
                    anexo="\n" + PERGUNTAS_F + "\n")
    return PROMPT % base


def insumos(amostra, saida, raiz=RAIZ, lote_max=LOTE_MAX, log=print):
    os.makedirs(saida, exist_ok=True)
    feitos = []
    for nome, us in lotes(amostra["itens"], lote_max):
        pasta = os.path.join(saida, nome)
        os.makedirs(pasta, exist_ok=True)
        itens, avisos = [], []
        for u in us:
            try:
                itens.append(montar_item(raiz, u, pasta))
            except Exception as e:  # noqa: BLE001 — item sem insumo vai para avisos
                avisos.append("%s: %s: %s" % (u["uid"], type(e).__name__, str(e)[:200]))
        AU._gravar_json(os.path.join(pasta, "itens.json"), itens)
        AU._escrever(pasta, "PROMPT.md", prompt_do_lote(raiz, us[0]["bloco"], us[0]["estrato"]))
        for n in os.listdir(pasta):
            if n.endswith((".md", ".json", ".html")):
                p = os.path.join(pasta, n)
                with open(p, encoding="utf-8", errors="replace") as f:
                    t = f.read()
                if raiz in t or os.path.realpath(raiz) in t:
                    AU._escrever(pasta, n, AU._sem_caminhos(t, raiz))
        b, e = us[0]["bloco"], us[0]["estrato"]
        feitos.append({"lote": nome, "bloco": b, "estrato": e, "modelo": modelo_do_lote(b, e),
                       "itens": [i["id"] for i in itens], "avisos": avisos})
        if avisos:
            log("%s: %s" % (nome, "; ".join(avisos)))
    AU._gravar_json(os.path.join(saida, "lotes.json"), feitos)
    return feitos


# ---------------------------------------------------------------- comparador


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn")


def norm_data(s):
    s = (s or "").strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})$", s)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return s


def norm_processos(s):
    out = set()
    for p in re.split(r"\s*;\s*|\s*,\s*|\s+e\s+", s or ""):
        p = p.strip()
        if p:
            out.add(jc.normalizar_processo(p) or re.sub(r"\W", "", p.lower()))
    return out


_TITULOS = re.compile(r"\b(?:diretora?|relatora?|presidente|sr|sra|dr|dra|conselheira?|"
                      r"do|da|de|dos|das|e)\b\.?")


def norm_relator(s):
    t = _sem_acento(s).lower()
    t = _TITULOS.sub(" ", t)
    return " ".join(re.findall(r"[a-z0-9]+", t))


def compara_campo(campo, publicado, auditor):
    """(igual?, valor publicado normalizado, valor do auditor normalizado)."""
    if campo == "data":
        a, b = norm_data(publicado), norm_data(auditor)
        return a == b, a, b
    if campo == "processo":
        a, b = norm_processos(publicado), norm_processos(auditor)
        return (a == b or bool(a & b)) if (a or b) else True, sorted(a), sorted(b)
    if campo == "relator":
        a, b = norm_relator(publicado), norm_relator(auditor)
        ok = a == b or (bool(a) and bool(b) and (set(a.split()) <= set(b.split())
                                                 or set(b.split()) <= set(a.split())))
        return ok, a, b
    a, b = (publicado or "").strip().lower(), (auditor or "").strip().lower()
    return a == b, a, b


def _pontas(anc, n=3):
    linhas = [T.normalizar(x) for x in anc.splitlines() if x.strip()]
    return [x for x in linhas[:n] + linhas[-n:] if x]


def classificar_diff(d, pontas=()):
    """hifenizacao, cabecalho_rodape, pii ou erro (C7)."""
    e, s = d.get("esperado") or "", d.get("saida") or ""
    if e and s and re.sub(r"[\s\-‐‑­]", "", e) == re.sub(r"[\s\-‐‑­]", "", s):
        return "hifenizacao"
    if "dado pessoal retirado" in e:
        return "pii"
    so = s if not e else (e if not s else "")
    if so and len(so) >= 3 and any(so in p for p in pontas):
        return "cabecalho_rodape"
    return "erro"


def compara_texto(corpo, anc, saida_txt):
    """Bloco A: a janela do corpo publicado localizada pela âncora da fonte (sem âncora, pela
    própria saída), e o diff por palavra contra a transcrição."""
    if anc and anc.strip():
        _, i0, i1 = T.janela(corpo, anc, margem=40)
        if i1 <= i0:
            return {"status": "sem-esperado", "diffs": [], "palavras_esperado": 0}
        pal = T.palavras(corpo)
        regiao = " ".join(pal[max(0, i0 - 40):i1 + 40])
    else:
        regiao = corpo
    esp, _a, _b = T.janela(regiao, saida_txt)
    if not esp.strip():
        return {"status": "sem-esperado", "diffs": [], "palavras_esperado": 0}
    pontas = _pontas(anc or "")
    diffs = T.diff_palavras(esp, saida_txt)
    for d in diffs:
        d["classe"] = classificar_diff(d, pontas)
    erros = [d for d in diffs if d["classe"] == "erro"]
    pii = [d for d in diffs if d["classe"] == "pii"]
    status = "diferente" if erros else ("pii" if pii else
                                        ("igual-salvo-ressalvas" if diffs else "igual"))
    return {"status": status, "diffs": diffs, "palavras_esperado": len(esp.split())}


def _sim(v):
    return _sem_acento(str(v or "")).strip().lower() in ("sim", "s", "yes", "true")


def _nao(v):
    return _sem_acento(str(v or "")).strip().lower() in ("nao", "n", "no", "false")


def _achar_saidas(pasta):
    res = {}
    for raiz_, _d, arqs in os.walk(pasta):
        for a in arqs:
            m = re.match(r"^(.+)-saida\.(md|json)$", a)
            if m:
                res[m.group(1)] = os.path.join(raiz_, a)
    return res


def comparar_item(raiz, u, txt):
    """Resultado de um item: {status, erros: [..], ...}."""
    b = u["bloco"]
    if b == "A":
        corpo = _corpo(raiz, u)
        anc = ancora(raiz, u) if u.get("ancora") == "fonte" else ""
        r = compara_texto(corpo, anc, txt)
        r["erro"] = r["status"] == "diferente"
        return r
    try:
        s = json.loads(txt)
    except ValueError:
        return {"status": "saida-invalida", "erro": False}
    if not isinstance(s, dict):
        return {"status": "saida-invalida", "erro": False}
    v, _corpo_ = je.ler_julgado(os.path.join(raiz, u["arquivo"])) if u.get("arquivo") else ({}, "")
    if b == "B" or (b == "C" and u["estrato"].startswith("resultado")):
        campos = CAMPOS_B if b == "B" else ("resultado",)
        dif = {}
        for c in campos:
            ok, a, x = compara_campo(c, v.get(c, ""), s.get(c, ""))
            if not ok:
                dif[c] = {"publicado": a, "auditor": x}
        return {"status": "diferente" if dif else "igual", "erro": bool(dif), "campos": dif}
    if b == "C":
        ementa = [k for k in ("afirma_sem_suporte", "omite_decisao", "nome_pessoa_fisica")
                  if _sim(s.get(k))]
        tema = _nao(s.get("tema_defensavel"))
        return {"status": "diferente" if ementa or tema else "igual", "erro": bool(ementa),
                "erro_ementa": ementa, "erro_tema": tema, "observacao": s.get("observacao", "")}
    if b == "D":
        lista = dispositivos_do_trecho(ancora(raiz, u))
        resp = {int(x.get("n", 0)): x for x in s.get("dispositivos") or [] if isinstance(x, dict)}
        certos = sum(1 for i in range(1, len(lista) + 1) if _sim(resp.get(i, {}).get("certo")))
        errados = [lista[i - 1] for i in range(1, len(lista) + 1)
                   if _nao(resp.get(i, {}).get("certo"))]
        faltam = [x for x in s.get("faltam") or [] if str(x).strip()]
        return {"status": "diferente" if errados or faltam else "igual", "erro": bool(errados),
                "listados": len(lista), "certos": certos, "errados": errados, "faltam": faltam}
    if b == "E":
        resto = [x for x in s.get("dado_pessoal_restante") or [] if str(x).strip()]
        corte = [x for x in s.get("corte_indevido") or [] if str(x).strip()]
        return {"status": "diferente" if resto or corte else "igual", "erro": bool(resto or corte),
                "dado_pessoal_restante": resto, "corte_indevido": corte}
    if b == "F":
        o = str(s.get("orgao_de_origem", "")).strip().upper()
        return {"status": "diferente" if o == "CVM" else "igual", "erro": o == "CVM",
                "orgao_de_origem": o, "trecho": s.get("trecho", "")}
    raise ValueError("bloco desconhecido: %s" % b)


def _pct(x):
    s = ("%.2f" % (100.0 * x)).rstrip("0").rstrip(".")
    return s.replace(".", ",") + "%"


def frase(n, erros):
    if not n:
        return "sem item conferido"
    if erros:
        return "%d erro(s) em %d (%s)" % (erros, n, _pct(erros / n))
    return "taxa abaixo de 3/%d (%s) com 95%% de confiança" % (n, _pct(3.0 / n))


def comparar(amostra, saidas, raiz=RAIZ):
    achadas = _achar_saidas(saidas)
    itens, vaz_cache, grupos = [], {}, {}

    def conta(chave, r, campo="erro"):
        g = grupos.setdefault(chave, {"N": 0, "erros": 0, "sem_saida": 0, "vazou": 0,
                                      "invalidas": 0})
        if r["status"] == "sem-saida":
            g["sem_saida"] += 1
        elif r["status"] == "vazou":
            g["vazou"] += 1
        elif r["status"] in ("saida-invalida", "sem-esperado"):
            g["invalidas"] += 1
        else:
            g["N"] += 1
            g["erros"] += bool(r.get(campo))
        return g

    for u in amostra["itens"]:
        r = {"uid": u["uid"], "bloco": u["bloco"], "estrato": u["estrato"], "id": u["id"]}
        caminho = achadas.get(u["uid"])
        if not caminho:
            r["status"] = "sem-saida"
        else:
            with open(caminho, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            r.update(comparar_item(raiz, u, txt))
            lote = os.path.dirname(caminho)
            if lote not in vaz_cache:
                vaz_cache[lote] = AU.vazamentos(lote)
            if vaz_cache[lote]:
                r["status"], r["vazamentos"] = "vazou", vaz_cache[lote]
            r["log"] = vaz_cache[lote] is not None
        itens.append(r)
        if u["bloco"] == "C" and u["estrato"] == "ementa-tema":
            conta("C/ementa", r, "erro_ementa")
            conta("C/tema", r, "erro_tema")
        else:
            g = conta("%s/%s" % (u["bloco"], u["estrato"]), r)
            if u["bloco"] == "D" and r["status"] not in ("sem-saida", "vazou", "saida-invalida"):
                g["listados"] = g.get("listados", 0) + r.get("listados", 0)
                g["certos"] = g.get("certos", 0) + r.get("certos", 0)
                g["faltam"] = g.get("faltam", 0) + len(r.get("faltam", []))
    for k, g in grupos.items():
        g["frase"] = frase(g["N"], g["erros"])
        if "listados" in g:
            g["precisao"] = g["certos"] / g["listados"] if g["listados"] else None
            tot = g["certos"] + g["faltam"]
            g["recall"] = g["certos"] / tot if tot else None
    por_bloco = {}
    for k, g in grupos.items():
        pb = por_bloco.setdefault(k.split("/")[0], {"N": 0, "erros": 0})
        pb["N"] += g["N"]
        pb["erros"] += g["erros"]
    for g in por_bloco.values():
        g["frase"] = frase(g["N"], g["erros"])
    return {"gerado_em": _agora(), "semente": amostra.get("semente"), "resumo": grupos,
            "por_bloco": por_bloco, "itens": itens}


def resumo_comparacao(comp):
    linhas = ["comparação: %d itens" % len(comp["itens"])]
    for k in sorted(comp["resumo"]):
        g = comp["resumo"][k]
        extra = ""
        if g.get("precisao") is not None:
            extra = "; precisão %s, recall %s" % (_pct(g["precisao"]),
                                                  _pct(g["recall"]) if g.get("recall") is not None
                                                  else "-")
        linhas.append("  %-26s N=%d erros=%d sem saída=%d vazou=%d inválidas=%d: %s%s" % (
            k, g["N"], g["erros"], g["sem_saida"], g["vazou"], g["invalidas"], g["frase"], extra))
    return "\n".join(linhas)


# ---------------------------------------------------------------- censos


def excecoes_resultados(raiz=RAIZ):
    """Ids citados entre crases nas exceções da Fase 2d no RESULTADOS.md."""
    try:
        with open(caminhos(raiz)["resultados"], encoding="utf-8") as f:
            txt = f.read()
    except OSError:
        return set()
    return set(re.findall(r"`((?:cvm|crsfn)-[a-z0-9-]+)`", txt))


def censo_completude(raiz=RAIZ, pubs=None):
    cam = caminhos(raiz)
    pubs = pubs if pubs is not None else publicados(raiz)
    ids_pub = {j["id"] for j in pubs}
    exc = excecoes_resultados(raiz)
    inv = _ler_json(cam["inventario"], []) or []
    ids_inv = {x["id"] for x in inv}
    faltam = sorted(ids_inv - ids_pub)
    cvm = {"inventario": len(inv), "publicados_cvm": sum(1 for j in pubs
                                                         if j["tipo"] != "acordao-crsfn"),
           "faltam_nas_excecoes": [i for i in faltam if i in exc],
           "faltam_sem_excecao": [i for i in faltam if i not in exc],
           "sobram": sorted(j["id"] for j in pubs
                            if j["tipo"] != "acordao-crsfn" and j["id"] not in ids_inv)}
    cl = _ler_json(cam["classificacao"], {}) or {}
    itens = cl.get("itens") or {}
    crsfn_pub = {j["id"] for j in pubs if j["tipo"] == "acordao-crsfn"}
    cvm_ids = {i for i, it in itens.items() if it.get("orgao") == "CVM"}
    faltam_c = sorted(cvm_ids - crsfn_pub)
    crs = {"classificados": len(itens), "erros_classificacao": sorted(cl.get("erros") or {}),
           "cvm": len(cvm_ids), "publicados": len(crsfn_pub),
           "faltam_nas_excecoes": [i for i in faltam_c if i in exc],
           "faltam_sem_excecao": [i for i in faltam_c if i not in exc],
           "publicados_nao_cvm": sorted(i for i in crsfn_pub if i in itens and i not in cvm_ids),
           "publicados_fora_da_classificacao": sorted(i for i in crsfn_pub if i not in itens),
           "excecoes_cvm_fora": sorted(i for i in exc if i in itens and i not in cvm_ids)}
    return {"cvm": cvm, "crsfn": crs}


def _nome_em_slug(slug, pessoas_):
    toks = [t for t in re.split(r"[-_./\s]+", slug or "") if t]
    return je.tem_nome(" ".join(t[:1].upper() + t[1:] for t in toks), pessoas_)


def _linhas_indice(raiz):
    """[(arquivo do índice, arquivo do julgado, linha)] das tabelas dos índices dos julgados.
    `arquivo do julgado` é o caminho sob `julgados/`: o prefixo relativo (`../../julgados/`) que a
    célula "Arquivo" traz até a raiz do repositório sai."""
    out = []
    for c in sorted(glob.glob(os.path.join(raiz, *INDICE_JULGADOS, "**", "*.md"), recursive=True)):
        if not (os.sep + "indices" + os.sep in c or os.path.basename(c) == "indice.md"):
            continue
        plugin = _rel(c, raiz)
        with open(c, encoding="utf-8") as f:
            for ln in f:
                if not ln.startswith("| ") or ln.startswith("|---"):
                    continue
                m = re.search(r"\|\s*([^|]+\.md)\s*\|\s*$", ln.rstrip("\n"))
                if m:
                    out.append((plugin, _PREFIXO_ARQUIVO.sub("", m.group(1).strip()), ln.rstrip("\n")))
    return out


def censo_nomes(raiz=RAIZ, pessoas=None, pubs=None, log=print):
    """Nome de pessoa física (lista positiva do julgado) no id, no nome do arquivo, na ementa do
    frontmatter e nas linhas dos índices."""
    pessoas = pessoas or je.Pessoas()
    pubs = pubs if pubs is not None else publicados(raiz, com_corpo=True)
    achados, por_arquivo, n = [], {}, 0
    for j in pubs:
        if "valores" not in j:
            j["valores"], j["corpo"] = je.ler_julgado(os.path.join(raiz, j["arquivo"]))
        ps = pessoas.do_julgado(j["valores"], j["corpo"])
        partes = j["arquivo"].split(os.sep)
        por_arquivo["/".join(partes[1:])] = ps
        n += 1
        for campo, txt, fn in (("id", j["id"], _nome_em_slug),
                               ("arquivo", os.path.splitext(os.path.basename(j["arquivo"]))[0],
                                _nome_em_slug),
                               ("ementa", j["valores"].get("ementa", ""), je.tem_nome)):
            t = fn(txt, ps)
            if t:
                achados.append({"id": j["id"], "campo": campo, "trecho": t})
    linhas = _linhas_indice(raiz)
    sem_dono = 0
    for indice, arq, ln in linhas:
        ps = por_arquivo.get(arq)
        if ps is None:
            sem_dono += 1
            continue
        t = je.tem_nome(ln.rsplit("|", 2)[0], ps)
        if t:
            achados.append({"indice": indice, "arquivo": arq, "campo": "indice", "trecho": t})
    return {"julgados": n, "linhas_de_indice": len(linhas), "linhas_sem_julgado": sem_dono,
            "achados": achados}


def censo_crsfn(raiz=RAIZ, preambulos=None, log=print):
    preambulos = preambulos if preambulos is not None else censo_preambulos(raiz, log=log)
    cl = _ler_json(caminhos(raiz)["classificacao"], {}) or {}
    itens = cl.get("itens") or {}
    cand = sorted(i for i, r in preambulos.items() if r.get("cvm_preambulo"))
    indet = sorted(i for i, it in itens.items() if it.get("orgao") == "INDETERMINADO")
    return {"nao_cvm": len(preambulos),
            "nao_cvm_sem_cache": sorted(i for i, r in preambulos.items() if not r.get("cache")),
            "nao_cvm_sem_texto_pypdf": sorted(i for i, r in preambulos.items()
                                             if r.get("cache") and not r.get("texto")),
            "cvm_no_preambulo": [{"id": i, "orgao": preambulos[i]["orgao"],
                                  "criterio": preambulos[i]["criterio"]} for i in cand],
            "cvm_nas_2_primeiras_paginas": sum(1 for r in preambulos.values() if r.get("cvm_inicio")),
            "indeterminado": [{"id": i, "criterio": itens[i].get("criterio", ""),
                               "ano": itens[i].get("ano")} for i in indet],
            "outro": sorted(i for i, it in itens.items() if it.get("orgao") == "OUTRO"),
            "erros_classificacao": sorted(cl.get("erros") or {})}


NUMERO_ACORDAO = re.compile(r"AC[ÓO]RD[ÃA]O\W{0,4}CRSFN\W{0,4}(?:n[ºo°.]*\s*)?(\d{1,5})\s*/\s*(\d{4})",
                            re.I)


def numero_acordao(corpo):
    """"n/AAAA" do primeiro "ACÓRDÃO CRSFN n/AAAA" do início do corpo, ou ""."""
    m = NUMERO_ACORDAO.search(corpo[:3000])
    return "%d/%s" % (int(m.group(1)), m.group(2)) if m else ""


def censo_duplicatas(raiz=RAIZ, pubs=None):
    """(e) Julgados com o mesmo sha256_fonte (em todo `julgados/`): corpo idêntico depois de
    normalizar = duplicata; corpos diferentes = a mesma página traz acórdãos distintos. Mais os
    acórdãos do CRSFN com o mesmo número no corpo e sha256 diferente."""
    pubs = pubs if pubs is not None else publicados(raiz, com_corpo=True)
    por_sha, por_num = {}, {}
    for j in pubs:
        if j.get("sha256_fonte"):
            por_sha.setdefault(j["sha256_fonte"], []).append(j)
        if j["tipo"] == "acordao-crsfn":
            n = numero_acordao(j.get("corpo") or _corpo(raiz, j))
            if n:
                por_num.setdefault(n, []).append(j)
    grupos = []
    for sha, js in sorted(por_sha.items()):
        if len(js) < 2:
            continue
        corpos = {T.normalizar(j.get("corpo") or _corpo(raiz, j)) for j in js}
        grupos.append({"sha256_fonte": sha, "ids": sorted(j["id"] for j in js),
                       "datas": sorted({j["data"] for j in js}),
                       "classe": "duplicata" if len(corpos) == 1 else "acordaos-distintos"})
    numeros = []
    for n, js in sorted(por_num.items()):
        shas = {j.get("sha256_fonte") for j in js}
        if len(js) > 1 and len(shas) > 1:
            corpos = {T.normalizar(j.get("corpo") or _corpo(raiz, j)) for j in js}
            numeros.append({"acordao": n, "ids": sorted(j["id"] for j in js),
                            "datas": sorted({j["data"] for j in js}),
                            "corpo_identico": len(corpos) == 1})
    return {"grupos_sha": grupos, "arquivos_sha": sum(len(g["ids"]) for g in grupos),
            "mesmo_numero_sha_diferente": numeros}


_ATO = r"(?:julgamento|discuss[ãa]o|delibera[çc][ãa]o|decis[ãa]o|aprecia[çc][ãa]o|aprova[çc][ãa]o)"
SUSPENSAO = re.compile(
    r"solicit(?:ou|ad[oa])\s+vista|pedi(?:u|do)\s+(?:de\s+)?vista|" + _ATO +
    r"\s+(?:\w+\s+){0,2}(?:suspens|adiad)\w*|(?:suspens|adiad)\w*\s+(?:a|o|sua|seu)\s+" + _ATO,
    re.I)
RETOMADA = re.compile(r"\(\s*pedido\s+de\s+vista[^)]*\)", re.I)  # rótulo da retomada após vista
DELIBERACAO = re.compile(
    r"deliber(?:ou|aram)|decidi(?:u|ram)|por\s+unanimidade|por\s+maioria|aprov(?:ou|aram)|"
    r"\bdeferi(?:u|ram)|indeferi(?:u|ram)|(?:deu|dar|negou|negar)\s+provimento|"
    r"conhec(?:eu|er)\s+d[oa]|acompanh(?:ou|ando|aram)|determin(?:ou|aram)|aceit(?:ou|ar)|"
    r"rejeit(?:ou|ar)", re.I)


def _secao_decisao(corpo):
    m = re.search(r"(?ms)^## Decis[ãa]o\s*\n(.*?)(?=^## |\Z)", corpo)
    return m.group(1) if m else corpo[:2000]


def censo_suspensas(raiz=RAIZ, pubs=None):
    """(f) Decisões do Colegiado com resultado preenchido cuja seção de decisão traz pedido de
    vista, suspensão ou adiamento e nenhum verbo de deliberação final. Só lista."""
    pubs = pubs if pubs is not None else publicados(raiz, com_corpo=True)
    out = []
    for j in pubs:
        if j["tipo"] != "decisao-colegiado" or not j["resultado"]:
            continue
        dec = RETOMADA.sub(" ", _secao_decisao(j.get("corpo") or _corpo(raiz, j)))
        m = SUSPENSAO.search(dec)
        if m and not DELIBERACAO.search(dec):
            out.append({"id": j["id"], "resultado": j["resultado"], "arquivo": j["arquivo"],
                        "sinal": m.group(0)})
    return out


def censos(raiz=RAIZ, pessoas=None, preambulos=None, log=print):
    pubs = publicados(raiz, com_corpo=True)
    return {"gerado_em": _agora(), "completude": censo_completude(raiz, pubs),
            "nomes": censo_nomes(raiz, pessoas, pubs, log=log),
            "crsfn": censo_crsfn(raiz, preambulos, log=log),
            "duplicatas": censo_duplicatas(raiz, pubs), "suspensas": censo_suspensas(raiz, pubs)}


def resumo_censos(c):
    a, n, f = c["completude"], c["nomes"], c["crsfn"]
    linhas = [
        "(a) completude CVM: inventário %d, publicados %d; faltam %d nas exceções (%s), %d sem "
        "exceção; sobram %d" % (a["cvm"]["inventario"], a["cvm"]["publicados_cvm"],
                                len(a["cvm"]["faltam_nas_excecoes"]),
                                ", ".join(a["cvm"]["faltam_nas_excecoes"]),
                                len(a["cvm"]["faltam_sem_excecao"]), len(a["cvm"]["sobram"])),
        "    completude CRSFN: classificados %d (+%d erros), CVM %d, publicados %d; faltam %d nas "
        "exceções, %d sem exceção; publicados não CVM %d; fora da classificação %d" % (
            a["crsfn"]["classificados"], len(a["crsfn"]["erros_classificacao"]), a["crsfn"]["cvm"],
            a["crsfn"]["publicados"], len(a["crsfn"]["faltam_nas_excecoes"]),
            len(a["crsfn"]["faltam_sem_excecao"]), len(a["crsfn"]["publicados_nao_cvm"]),
            len(a["crsfn"]["publicados_fora_da_classificacao"])),
        "(b) nomes: %d julgados, %d linhas de índice (%d sem julgado); %d achado(s) (%s)" % (
            n["julgados"], n["linhas_de_indice"], n["linhas_sem_julgado"], len(n["achados"]),
            ", ".join("%s: %d" % (k, sum(1 for x in n["achados"] if x["campo"] == k))
                      for k in ("id", "arquivo", "ementa", "indice"))),
        "(c) CRSFN não CVM com CVM no preâmbulo: %d (de %d não CVM; %d sem cache, %d sem texto "
        "pelo pypdf; CVM nas 2 primeiras páginas: %d)" % (
            len(f["cvm_no_preambulo"]), f["nao_cvm"], len(f["nao_cvm_sem_cache"]),
            len(f["nao_cvm_sem_texto_pypdf"]), f["cvm_nas_2_primeiras_paginas"]),
        "(d) CRSFN indeterminado: %d; outro: %d; erros de classificação: %d" % (
            len(f["indeterminado"]), len(f["outro"]), len(f["erros_classificacao"])),
        "(e) mesmo sha256_fonte: %d grupos, %d arquivos (%d duplicata, %d acórdãos distintos); "
        "mesmo número de acórdão com sha diferente: %d grupos (%d com corpo idêntico)" % (
            len(c["duplicatas"]["grupos_sha"]), c["duplicatas"]["arquivos_sha"],
            sum(1 for g in c["duplicatas"]["grupos_sha"] if g["classe"] == "duplicata"),
            sum(1 for g in c["duplicatas"]["grupos_sha"] if g["classe"] != "duplicata"),
            len(c["duplicatas"]["mesmo_numero_sha_diferente"]),
            sum(1 for g in c["duplicatas"]["mesmo_numero_sha_diferente"] if g["corpo_identico"])),
        "(f) Colegiado com resultado e deliberação suspensa (vista/adiamento, sem deliberação "
        "final): %d" % len(c["suspensas"])]
    return "\n".join(linhas)


# ---------------------------------------------------------------- runner

PEDIDO = "Leia o PROMPT.md desta pasta e siga as instruções dele."


def _dentro(p, base):
    p, base = os.path.realpath(p), os.path.realpath(base)
    return p == base or p.startswith(base + os.sep)


def lote_completo(pasta):
    itens = AU._ler_json(os.path.join(pasta, "itens.json")) if os.path.exists(
        os.path.join(pasta, "itens.json")) else None
    return bool(itens) and all(os.path.exists(os.path.join(pasta, i["saida"])) for i in itens)


def rodar_lote(pasta, modelo, run=subprocess.run, timeout=3600):
    cmd = je.comando(modelo)
    inicio = _agora()
    with open(os.path.join(pasta, "log.jsonl"), "w", encoding="utf-8") as out, \
            open(os.path.join(pasta, "stderr.txt"), "w", encoding="utf-8") as err:
        r = run(cmd, input=PEDIDO, cwd=pasta, stdout=out, stderr=err, text=True,
                timeout=timeout)
    with open(os.path.join(pasta, "log.jsonl"), encoding="utf-8", errors="replace") as f:
        custo = je.custo(f.read())
    info = {"modelo": modelo, "comando": cmd, "codigo": r.returncode, "inicio": inicio,
            "fim": _agora(), "total_cost_usd": custo, "completo": lote_completo(pasta)}
    AU._gravar_json(os.path.join(pasta, "execucao.json"), info)
    return info


def rodar(pasta_lotes, paralelo=PARALELO_MAX, run=subprocess.run, log=print):
    """Roda os lotes pendentes de `pasta_lotes` (até 4 em paralelo). A pasta fica fora do cofre e
    do repositório: o auditor não pode carregar o AGENTS.md nem ver o acervo."""
    for proibida in (je.COFRE, RAIZ):
        if _dentro(pasta_lotes, proibida):
            raise SystemExit("pasta dos lotes dentro do cofre ou do repositório (%s); copie os "
                             "lotes para o scratchpad e rode de lá" % pasta_lotes)
    manifesto = os.path.join(pasta_lotes, "lotes.json")
    modelos = {x["lote"]: x["modelo"] for x in AU._ler_json(manifesto)} \
        if os.path.exists(manifesto) else {}
    pend = []
    for nome in sorted(os.listdir(pasta_lotes)):
        p = os.path.join(pasta_lotes, nome)
        if nome.startswith(("_", ".")) or not os.path.isfile(os.path.join(p, "itens.json")):
            continue
        if lote_completo(p):
            log("%s: completo, pulado" % nome)
            continue
        if nome not in modelos:
            raise SystemExit("%s fora do lotes.json: sem modelo" % nome)
        pend.append((nome, p, modelos[nome]))
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(paralelo,
                                                                     PARALELO_MAX))) as ex:
        fut = {ex.submit(rodar_lote, p, m, run): nome for nome, p, m in pend}
        for f in concurrent.futures.as_completed(fut):
            nome = fut[f]
            try:
                res[nome] = f.result()
            except Exception as e:  # noqa: BLE001 — falha num lote não para os outros
                res[nome] = {"erro": "%s: %s" % (type(e).__name__, e)}
            log("%s: %s" % (nome, json.dumps(
                {k: v for k, v in res[nome].items() if k != "comando"}, ensure_ascii=False)))
    return res


# ---------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    cam = caminhos()
    p = sub.add_parser("universo")
    p.add_argument("--saida", default=cam["universo"])
    p = sub.add_parser("sortear")
    p.add_argument("--semente", type=int, default=SEMENTE)
    p.add_argument("--universo", default=cam["universo"])
    p.add_argument("--saida")
    p.add_argument("--estratos", help="bloco/estrato separados por vírgula (re-auditoria)")
    p.add_argument("--amostra-anterior", default=cam["amostra"])
    p = sub.add_parser("insumos")
    p.add_argument("--amostra", default=cam["amostra"])
    p.add_argument("--saida", required=True)
    p.add_argument("--lote-max", type=int, default=LOTE_MAX)
    p = sub.add_parser("comparar")
    p.add_argument("--amostra", default=cam["amostra"])
    p.add_argument("--saidas", required=True)
    p.add_argument("--relatorio", default=cam["comparacao"])
    p = sub.add_parser("censos")
    p.add_argument("--relatorio", default=cam["censos"])
    p = sub.add_parser("rodar")
    p.add_argument("--lotes", required=True)
    p.add_argument("--paralelo", type=int, default=PARALELO_MAX)
    a = ap.parse_args(argv)

    if a.cmd == "universo":
        u = universo()
        AU._gravar_json(a.saida, u)
        print(resumo_universo(u))
        print("gravado: %s" % a.saida)
    elif a.cmd == "sortear":
        univ = AU._ler_json(a.universo)
        estratos = [x.strip() for x in a.estratos.split(",")] if a.estratos else None
        excluir = set()
        if estratos:
            ant = AU._ler_json(a.amostra_anterior) if os.path.exists(a.amostra_anterior) else {}
            excluir = {u["id"] for u in ant.get("itens", [])}
        saida = a.saida or (cam["amostra"] if a.semente == SEMENTE and not estratos else
                            cam["amostra"].replace(".json", "-%d.json" % a.semente))
        am = sortear(univ, a.semente, estratos=estratos, excluir=excluir)
        AU._gravar_json(saida, am)
        print("%d itens sorteados; faltas: %s" % (len(am["itens"]), am["faltas"] or "nenhuma"))
        print("gravado: %s" % saida)
    elif a.cmd == "insumos":
        feitos = insumos(AU._ler_json(a.amostra), a.saida, lote_max=a.lote_max)
        por = {}
        for x in feitos:
            por[x["modelo"]] = por.get(x["modelo"], 0) + 1
        print("%d lotes em %s (%s); %d com aviso" % (
            len(feitos), a.saida, ", ".join("%s: %d" % kv for kv in sorted(por.items())),
            sum(1 for x in feitos if x["avisos"])))
    elif a.cmd == "comparar":
        comp = comparar(AU._ler_json(a.amostra), a.saidas)
        AU._gravar_json(a.relatorio, comp)
        print(resumo_comparacao(comp))
    elif a.cmd == "censos":
        c = censos()
        AU._gravar_json(a.relatorio, c)
        print(resumo_censos(c))
        print("gravado: %s" % a.relatorio)
    elif a.cmd == "rodar":
        res = rodar(a.lotes, a.paralelo)
        return 0 if all(r.get("completo") for r in res.values()) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
