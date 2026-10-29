#!/usr/bin/env python3
"""Fontes da Onda 1 do histórico (29 Resoluções CVM fora do núcleo; plano da Fase 2b, seção 7).

Etapas (cada uma lê o que a anterior gravou; nada é baixado duas vezes):
  inventario   acrescenta as 29 normas a fontes/inventario.json, a partir das páginas em cache
               (dados/paginas-cvm/resolNNN.html), sem tocar nas 8 entradas existentes.
  baixar       ctresb/leis (api.github.com) -> dados/fontes/ctresb-NNNN.md; DOCX/HTM do ato
               -> dados/fontes/cvm-NNNN.{docx,htm}; PDF do original sem ctresb
               -> dados/fontes/cvm-NNNN.pdf; consolidado -> dados/resolNNNconsolid.{docx,doc,htm}.
  textos       dados/fontes/dou-NNNN.md de cada original e de cada ato novo.
  alteradoras  plugins/normas/normas/cvm/alteradoras/NNNN.md dos atos novos (não sobrescreve).

Fonte do texto, em ordem: ctresb/leis (conversão do HTML do DOU; `url_dou` = slug do
in.gov.br); DOCX do ato na CVM; PDF do ato na CVM pelo PDFKit (texto refeito em parágrafos
por `paragrafos_pdf`). Fonte não-DOU: `url_dou` vazio e incerteza INCERTEZA_NAO_DOU.

Uso: python3 scripts/fontes_onda.py inventario|baixar|textos|alteradoras
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from alteradoras import escrever_alteradora, md_do_ctresb, md_do_docx  # noqa: E402
from baixar import permitido, slug_ctresb  # noqa: E402
from converter import normalizar_artigos  # noqa: E402
from inventario import BASE, URL_PAGINA, USER_AGENT, extrair_pagina, montar_inventario  # noqa: E402

RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DADOS = os.path.join(RAIZ, "dados")
FONTES = os.path.join(DADOS, "fontes")
PAGINAS = os.path.join(DADOS, "paginas-cvm")
INVENTARIO = os.path.join(RAIZ, "fontes", "inventario.json")
ALTERADORAS = os.path.join(RAIZ, "plugins", "normas", "normas", "cvm", "alteradoras")
DATA_BASE = "2026-10-29"

NORMAS = [6, 8, 9, 11, 13, 19, 20, 31, 32, 35, 43, 44, 45, 46, 47, 53, 54, 67, 77, 81, 86, 88,
          135, 161, 166, 193, 210, 215, 232]
# Alteradora que é norma do acervo (resolucoes/NNNN.md): o texto do ato é o da própria norma;
# não ganha alteradoras/NNNN.md.
NORMAS_DO_ACERVO = {60: "plugins/normas/normas/cvm/resolucoes/0060.md"}
# Campos manuais da Fase 2 que valem para o ato onde quer que ele apareça (fontes/INVENTARIO.md:
# `url_dou` do DOU salvo no navegador, `dou`/`dou_original` da Res. 59).
MANUAIS = ("dou", "dou_original", "url_dou")

DOU = "https://www.in.gov.br/web/dou/-/"
CTRESB = "https://api.github.com/repos/ctresb/leis/contents/reguladores/cvm/resolucoes/%d"
INCERTEZA_NAO_DOU = "Texto do arquivo do ato no site da CVM, não da página do DOU [verificar no DOU]."
PAUSA = 1.0
_ultima = [0.0]


# ---------------------------------------------------------------- inventário

def links_consolidado(html, numero):
    """{htm, pdf, docx|doc} do consolidado e o PDF da redação original, pelos href da página
    (a página de 210, 215 e 232 rotula os links como [HTML]/[PDF]/[DOC], que extrair_pagina
    não lê). Devolve (consolidado, [url_original])."""
    cons, orig = {}, []
    for href in dict.fromkeys(re.findall(r'href="([^"]+)"', html)):
        arq = href.rsplit("/", 1)[-1].lower()
        m = re.fullmatch(r"resol0*%dconsolid\.(htm|pdf|docx|doc)" % numero, arq)
        if m:
            cons.setdefault(m.group(1), BASE + href if href.startswith("/") else href)
        elif re.fullmatch(r"resol0*%d\.pdf" % numero, arq):
            orig.append(BASE + href if href.startswith("/") else href)
    return cons, orig


def _url_dou(slug):
    return DOU + slug if slug else ""


def conhecidos_do_inventario(inv):
    """{numero: campos MANUAIS} dos atos e normas já no inventário (Fase 2)."""
    saida = {}
    for x in inv:
        saida.setdefault(x["numero"], {k: x[k] for k in MANUAIS if k in x})
        for a in x["alteradoras"]:
            saida.setdefault(a["numero"], {k: a[k] for k in MANUAIS if k in a})
    return saida


def montar_onda(numeros, paginas, htmls, nomes_ctresb, conhecidos=None):
    """Entradas do inventário das `numeros`, no formato das 8 da Fase 2, mais:
    `url_dou` (slug do ctresb, ou vazio), `retificacoes` ([{dou}] da página da CVM) e
    `norma_do_acervo` (alteradora que é norma do acervo). Para ato já no inventário,
    os campos MANUAIS de `conhecidos` valem sobre a página e o ctresb."""
    conhecidos = conhecidos or {}
    inv = montar_inventario(numeros, paginas)
    for item in inv:
        n = item["numero"]
        cons, orig = links_consolidado(htmls[n], n)
        for k, v in cons.items():
            if k == "doc":
                item["url_consolidado"].setdefault("docx", v)  # rótulo [DOC]: arquivo Word 97
            else:
                item["url_consolidado"].setdefault(k, v)
        if not item["url_original"]:
            item["url_original"] = orig
        novo = {}
        for k, v in item.items():
            novo[k] = v
            if k == "dou":
                novo["url_dou"] = _url_dou(slug_ctresb(nomes_ctresb, n))
                if paginas[n].get("retificada_dou"):
                    novo["retificacoes"] = [{"dou": d} for d in paginas[n]["retificada_dou"]]
        item.clear()
        item.update(novo)
        alts = []
        for a in item["alteradoras"]:
            na = a["numero"]
            ajuste = conhecidos.get(na, {})
            b = {}
            for k, v in a.items():
                b[k] = ajuste.get(k, v)
                if k == "dou":
                    if "dou_original" in ajuste:
                        b["dou_original"] = ajuste["dou_original"]
                    b["url_dou"] = ajuste.get("url_dou", _url_dou(slug_ctresb(nomes_ctresb, na)))
                    if paginas[na].get("retificada_dou"):
                        b["retificacoes"] = [{"dou": d} for d in paginas[na]["retificada_dou"]]
                    if na in NORMAS_DO_ACERVO:
                        b["norma_do_acervo"] = NORMAS_DO_ACERVO[na]
            alts.append(b)
        item["alteradoras"] = alts
    return inv


def acrescentar(existente, novas):
    """Inventário existente + entradas novas (sem repetir id; as existentes ficam intactas)."""
    ids = {x["id"] for x in existente}
    return existente + [x for x in novas if x["id"] not in ids]


def _nomes_ctresb():
    nomes = []
    for arq in sorted(os.listdir(FONTES)):
        if re.fullmatch(r"ctresb-\d{4}\.json", arq):
            with open(os.path.join(FONTES, arq), encoding="utf-8") as f:
                nomes += [x["name"] for x in json.load(f)]
    return nomes


def _ler_pagina(n):
    with open(os.path.join(PAGINAS, "resol%03d.html" % n), encoding="utf-8") as f:
        return f.read()


def etapa_inventario():
    htmls, paginas = {}, {}
    for n in NORMAS:
        htmls[n] = _ler_pagina(n)
        paginas[n] = extrair_pagina(htmls[n])
        paginas[n]["url_pagina"] = URL_PAGINA % n
        for a in paginas[n]["alteradoras"]:
            if a["numero"] not in paginas:
                htmls[a["numero"]] = _ler_pagina(a["numero"])
                paginas[a["numero"]] = extrair_pagina(htmls[a["numero"]])
                paginas[a["numero"]]["url_pagina"] = URL_PAGINA % a["numero"]
    with open(INVENTARIO, encoding="utf-8") as f:
        inv = json.load(f)
    novo = acrescentar(inv, montar_onda(NORMAS, paginas, htmls, _nomes_ctresb(),
                                        conhecidos_do_inventario(inv)))
    with open(INVENTARIO, "w", encoding="utf-8") as f:
        json.dump(novo, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("inventário: %d -> %d normas" % (len(inv), len(novo)))
    return 0


def onda(inv=None):
    """(normas da onda, {ato: item de alteradora}) do inventário."""
    if inv is None:
        with open(INVENTARIO, encoding="utf-8") as f:
            inv = json.load(f)
    normas = [x for x in inv if x["numero"] in NORMAS]
    atos = {}
    for x in normas:
        for a in x["alteradoras"]:
            atos.setdefault(a["numero"], a)
    return normas, dict(sorted(atos.items()))


# ---------------------------------------------------------------- PDF em parágrafos

_TITULO_ATO = re.compile(r"^RESOLU[ÇC][ÃA]O\s+CVM\s+N[ºo°]\s*\d+,?\s+DE\s+.*\d{4}\.?$", re.I)
_ABRE_SEMPRE = re.compile(
    r"^(?:Art\.?\s*\d|CAP[ÍI]TULO\b|T[ÍI]TULO\b|LIVRO\b|PARTE\b|ANEXO\b|AP[ÊE]NDICE\b"
    r"|Se[çc][ãa]o\s+[IVXLC]+\b|SE[ÇC][ÃA]O\s+[IVXLC]+\b|Subse[çc][ãa]o\b|SUBSE[ÇC][ÃA]O\b"
    r"|O PRESIDENTE\b|A PRESIDENTE\b|CONSIDERANDO\b|APROVOU\b)")
# Abrem parágrafo só depois de linha terminada em pontuação (podem aparecer no meio de uma frase).
_ABRE_DEPOIS_DE_PONTO = re.compile(
    r"^(?:§\s*\d|Parágrafo único|[IVXLC]+\s*[–—-]\s|[a-z]\)\s|\d+(?:\.\d+)*\.?\s*[–—-]\s|\d+(?:\.\d+)*\.\s"
    r"|[“\"])")
# O primeiro inciso ("I –") e a primeira alínea ("a)") abrem parágrafo mesmo depois de linha
# sem pontuação (título de anexo ou de quadro seguido da lista).
_PRIMEIRO_DA_LISTA = re.compile(r"^(?:I\s*[–—-]\s|a\)\s)")
# "ANEXO A À RESOLUÇÃO CVM Nº 88, DE 27 DE ABRIL DE 2022": o título do anexo vem na linha seguinte.
_ANEXO_DO_ATO = re.compile(r"^ANEXO\b.*\bDE\s+\d{4}\.?$", re.I)
_FIM_DE_FRASE = re.compile(r"(?:[.;:!?”\"]|\(NR\)|[.;:,]\s+(?:e|ou))$")
_PAGINA = re.compile(r"^(?:\d{1,3}|P[áa]gina \d+ de \d+)$")
_ASSINADO = re.compile(r"^Assinado eletronicamente por$", re.I)
_CARGO = re.compile(r"^Presidente(?: Interino| em exerc[íi]cio| Substituto)?$", re.I)
_NOME_CAIXA_ALTA = re.compile(r"^[A-ZÁÂÃÀÉÊÍÓÔÕÚÇ][A-ZÁÂÃÀÉÊÍÓÔÕÚÇ .'-]+$")


def _caixa_alta(linha):
    letras = [c for c in linha if c.isalpha() and c not in "ºª"]
    return len(letras) >= 4 and all(c.isupper() for c in letras)


def linhas_pdf(txt):
    """Texto do PDFKit (páginas separadas por \\f) -> linhas do corpo, sem o cabeçalho que se
    repete no topo das páginas (endereço da CVM, título corrente), sem números de página e
    sem a assinatura ("Assinado eletronicamente por", nome, "Presidente")."""
    from collections import Counter
    paginas = [[l.strip() for l in p.split("\n") if l.strip()] for p in txt.split("\f")]
    paginas = [p for p in paginas if p]
    conta = Counter(l for p in paginas for l in set(p[:8]) if not _PAGINA.match(l))
    minimo = max(2, (len(paginas) + 1) // 2)
    cabecalho = {l for l, c in conta.items() if c >= minimo} if len(paginas) > 1 else set()
    corpo = []
    for i, p in enumerate(paginas):
        k = 0
        while k < len(p) and (p[k] in cabecalho or _PAGINA.match(p[k])):
            if i == 0 and _TITULO_ATO.match(p[k]):
                break  # o título do ato fica na primeira página
            k += 1
        fim = len(p)
        while fim > k and _PAGINA.match(p[fim - 1]):
            fim -= 1
        corpo += p[k:fim]
    saida = []
    for j, l in enumerate(corpo):
        if _ASSINADO.match(l):
            continue
        if _CARGO.match(l) and saida and _NOME_CAIXA_ALTA.match(saida[-1]) and not _ABRE_SEMPRE.match(saida[-1]):
            saida.pop()
            continue
        saida.append(l)
    return saida


def paragrafos_pdf(txt):
    """Texto do PDFKit -> markdown com um parágrafo por dispositivo (linhas quebradas pelo
    layout do PDF voltam a ser uma só) e `## Art. N` (normalizar_artigos), no formato dos
    dou-NNNN.md. Heurística: abre parágrafo o título do ato, cabeçalho em caixa alta, artigo,
    capítulo, seção e anexo; §, inciso, alínea e item só depois de linha terminada em
    pontuação ou de linha curta; e qualquer linha depois de linha curta terminada em
    pontuação. Tabelas do PDF saem achatadas (uma célula atrás da outra)."""
    linhas = linhas_pdf(txt)
    if not linhas:
        return ""
    tams = sorted(len(l) for l in linhas)
    cheia = tams[int(0.9 * (len(tams) - 1))]
    pars = []
    ant = None
    for l in linhas:
        l = re.sub(r"^(Art\.\s*\d+)o\b", "\\1º", l)  # "Art. 4o" (ordinal como letra no PDF)
        novo = (
            ant is None
            or _TITULO_ATO.match(l) or _TITULO_ATO.match(ant)
            or _ANEXO_DO_ATO.match(pars[-1])
            or _ABRE_SEMPRE.match(l) or _PRIMEIRO_DA_LISTA.match(l)
            or (_caixa_alta(l) and not (_caixa_alta(ant) and not _FIM_DE_FRASE.search(ant)))
            or (_caixa_alta(ant) and not _caixa_alta(l))
            or (_ABRE_DEPOIS_DE_PONTO.match(l) and (_FIM_DE_FRASE.search(pars[-1]) or len(ant) < 0.8 * cheia))
            or (_FIM_DE_FRASE.search(pars[-1]) and len(ant) < 0.8 * cheia and l not in ("e", "ou"))
        )
        if novo:
            pars.append(l)
        elif re.search(r"\w-$", pars[-1]):
            pars[-1] += l  # palavra composta partida no hífen ("considera-" + "se")
        else:
            pars[-1] += " " + l
        ant = l
    return normalizar_artigos("\n\n".join(pars) + "\n")


# ---------------------------------------------------------------- downloads

def _get(url, headers=None):
    if not permitido(url):
        raise ValueError("domínio fora da lista: %s" % url)
    espera = PAUSA - (time.time() - _ultima[0])
    if espera > 0:
        time.sleep(espera)
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
            return r.read()
    finally:
        _ultima[0] = time.time()


def baixar(url, destino, headers=None):
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        return destino, False
    corpo = _get(url, headers)
    if not corpo:
        raise ValueError("resposta vazia: %s" % url)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "wb") as f:
        f.write(corpo)
    return destino, True


def _ctresb_item(numero, ano_hint=None):
    for arq in sorted(os.listdir(FONTES)):
        if not re.fullmatch(r"ctresb-\d{4}\.json", arq):
            continue
        with open(os.path.join(FONTES, arq), encoding="utf-8") as f:
            for x in json.load(f):
                if slug_ctresb([x["name"]], numero):
                    return x
    return None


def etapa_baixar():
    normas, atos = onda()
    falhas, novos = [], 0
    alvo = {n["numero"]: n for n in normas}
    for num in sorted(set(alvo) | {a for a in atos if a not in NORMAS_DO_ACERVO}):
        if num in atos and os.path.exists(os.path.join(ALTERADORAS, "%04d.md" % num)):
            continue  # ato já no acervo (Fase 2)
        ct = _ctresb_item(num)
        try:
            if ct:
                _, b = baixar(ct["url"], os.path.join(FONTES, "ctresb-%04d.md" % num),
                              {"Accept": "application/vnd.github.raw"})
                novos += b
            urls = (atos[num] if num in atos else {}).get("url_ato", {})
            for ext in ("docx", "htm"):
                if ext in urls:
                    _, b = baixar(urls[ext], os.path.join(FONTES, "cvm-%04d.%s" % (num, ext)))
                    novos += b
            if not ct and num in alvo and "docx" not in urls:
                pdf = next(iter(alvo[num]["url_original"]), None)
                if pdf:
                    _, b = baixar(pdf, os.path.join(FONTES, "cvm-%04d.pdf" % num))
                    novos += b
        except Exception as e:  # noqa: BLE001 — registra e segue
            falhas.append((num, str(e)[:200]))
    for n in normas:
        num = n["numero"]
        for ext in ("docx", "htm"):
            url = n["url_consolidado"].get(ext)
            if not url:
                continue
            real = "doc" if url.lower().endswith(".doc") else ext
            try:
                _, b = baixar(url, os.path.join(DADOS, "resol%03dconsolid.%s" % (num, real)))
                novos += b
            except Exception as e:  # noqa: BLE001
                falhas.append(("consolidado-%d-%s" % (num, ext), str(e)[:200]))
    print("baixar: %d arquivo(s) novo(s), %d falha(s)" % (novos, len(falhas)))
    for f in falhas:
        print("  falhou %s: %s" % f)
    return 1 if falhas else 0


# ---------------------------------------------------------------- textos e alteradoras

def _ler(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _fonte(num):
    """Arquivo de onde sai o texto de `num`: ('ctresb'|'docx'|'pdf', caminho) ou (None, None)."""
    for tipo, nome in (("ctresb", "ctresb-%04d.md"), ("docx", "cvm-%04d.docx"), ("pdf", "cvm-%04d.pdf")):
        path = os.path.join(FONTES, nome % num)
        if os.path.exists(path):
            return tipo, path
    return None, None


def texto_original(num):
    """dou-NNNN.md de uma norma (redação original): ctresb ou PDF da CVM pelo PDFKit."""
    from texto_vigente import _pdfkit_txt
    tipo, path = _fonte(num)
    if tipo == "ctresb":
        return md_do_ctresb(_ler(path), ato=False)
    if tipo == "pdf":
        txt = _pdfkit_txt(path)
        if not txt:
            raise ValueError("PDFKit não leu %s" % path)
        return paragrafos_pdf(txt)
    raise ValueError("norma %d sem fonte do texto" % num)


def texto_ato(num):
    """dou-NNNN.md de um ato alterador: ctresb (tabelas do DOCX da CVM, se houver) ou DOCX."""
    tipo, path = _fonte(num)
    docx = os.path.join(FONTES, "cvm-%04d.docx" % num)
    if tipo == "ctresb":
        return md_do_ctresb(_ler(path), ato=True, docx=docx if os.path.exists(docx) else None)
    if tipo == "docx":
        return md_do_docx(path, ato=True)
    raise ValueError("ato %d sem ctresb nem DOCX" % num)


def _atos_novos(atos):
    return sorted(a for a in atos if a not in NORMAS_DO_ACERVO
                  and not os.path.exists(os.path.join(ALTERADORAS, "%04d.md" % a)))


def etapa_textos():
    normas, atos = onda()
    feitos, falhas = 0, []
    for num, func in [(n["numero"], texto_original) for n in normas] + [(a, texto_ato) for a in _atos_novos(atos)]:
        destino = os.path.join(FONTES, "dou-%04d.md" % num)
        if os.path.exists(destino):
            continue  # não sobrescreve (dou-0060.md e os da Fase 2)
        try:
            md = func(num)
        except Exception as e:  # noqa: BLE001
            falhas.append((num, str(e)[:200]))
            continue
        with open(destino, "w", encoding="utf-8") as f:
            f.write(md)
        feitos += 1
    print("textos: %d dou-NNNN.md novo(s), %d falha(s)" % (feitos, len(falhas)))
    for f in falhas:
        print("  falhou %s: %s" % f)
    return 1 if falhas else 0


INCERTEZA_DOCX = ("Ato alterador, não consolidado: fonte_consolidada é o DOCX do ato no site da CVM, usado "
                  "para conferir o texto do DOU; sha256_fonte é o hash desse DOCX. Texto do DOU via "
                  "ctresb/leis (o in.gov.br bloqueia acesso por script).")
INCERTEZA_CTRESB = ("Ato alterador, não consolidado: a CVM só publica PDF deste ato; fonte_consolidada é o "
                    "arquivo do ctresb/leis (conversão do HTML do DOU) e sha256_fonte é o hash desse "
                    "arquivo. Sem DOCX da CVM para conferir o texto.")


def campos_alteradora(item, tipo, docx_path=None, ctresb_path=None, ctresb_raw=None):
    """(fonte_original, fonte_consolidada, sha256_fonte, incerteza) de um ato novo, nas convenções
    da Fase 2; ato só com DOCX da CVM: `url_dou` vazio e INCERTEZA_NAO_DOU."""
    urls = item.get("url_ato", {})
    if tipo == "ctresb" and docx_path:
        r = [item["url_dou"], urls["docx"], _sha256(docx_path), INCERTEZA_DOCX]
    elif tipo == "ctresb":
        r = [item["url_dou"], ctresb_raw, _sha256(ctresb_path), INCERTEZA_CTRESB]
    elif tipo == "docx":
        r = [urls["docx"], urls["docx"], _sha256(docx_path), INCERTEZA_NAO_DOU]
    else:
        raise ValueError("ato %d sem fonte" % item["numero"])
    if not r[0]:
        raise ValueError("ato %d sem fonte_original" % item["numero"])
    ret = [x["dou"] for x in item.get("retificacoes", [])]
    if ret:
        r[3] += (" Retificação no DOU de %s registrada só no inventário: o texto não incorpora a "
                 "retificação." % " e ".join(ret))
    return tuple(r)


def etapa_alteradoras():
    _, atos = onda()
    feitos, falhas = 0, []
    for num in _atos_novos(atos):
        try:
            tipo, path = _fonte(num)
            docx = os.path.join(FONTES, "cvm-%04d.docx" % num)
            raw = None
            if tipo == "ctresb":
                raw = "https://raw.githubusercontent.com/ctresb/leis/main/" + _ctresb_item(num)["path"]
            orig, cons, sha, inc = campos_alteradora(
                atos[num], tipo, docx if os.path.exists(docx) else None, path, raw)
            md = _ler(os.path.join(FONTES, "dou-%04d.md" % num))
            conteudo = escrever_alteradora(num, md, atos[num], orig, inc, sha256_fonte=sha,
                                           fonte_consolidada=cons, data_base=DATA_BASE)
        except Exception as e:  # noqa: BLE001
            falhas.append((num, str(e)[:200]))
            continue
        with open(os.path.join(ALTERADORAS, "%04d.md" % num), "x", encoding="utf-8") as f:
            f.write(conteudo)
        feitos += 1
    print("alteradoras: %d arquivo(s) novo(s), %d falha(s)" % (feitos, len(falhas)))
    for f in falhas:
        print("  falhou %s: %s" % f)
    return 1 if falhas else 0


if __name__ == "__main__":
    etapas = {"inventario": etapa_inventario, "baixar": etapa_baixar, "textos": etapa_textos,
              "alteradoras": etapa_alteradoras}
    if len(sys.argv) != 2 or sys.argv[1] not in etapas:
        print(__doc__)
        sys.exit(2)
    sys.exit(etapas[sys.argv[1]]())
