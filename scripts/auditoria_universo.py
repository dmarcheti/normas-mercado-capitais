#!/usr/bin/env python3
"""Universo da auditoria da Fase 3 (subcomando `universo` do scripts/auditoria.py).

Cada unidade auditável: {id, camada, categoria, norma, localizador, posicao, commit, fonte,
paginas, sobrescrito, ...}. `norma` é relativa a plugins/normas/skills/consultar-normas/normas/; `fonte` é relativa à
raiz do repo (dados/...). Funções com efeito externo (git, PDFKit, textutil) ficam isoladas em
`git`, `extrair_paginas` e `textutil`, para os testes trocarem.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import auditoria_texto as T  # noqa: E402

RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
NORMAS = "plugins/normas/skills/consultar-normas/normas"
FONTES_TV = "dados/texto-vigente-fontes"
DATA_BASE = "2026-10-30"
REF = "main"
EXCLUIR = ("cvm/alteradoras/", "indices/", "indice.md", "normas.json")
PALAVRAS_PAGINA = 30
PALAVRAS_BLOCO = 300
MARCA_LISTA = "QQLISTAQQ"
MARCA_ROTULO = "QQROTULOQQ"
MARCA_TACHADO = "QQTACHADOQQ"


# ---------------------------------------------------------------- efeitos externos

def git(repo, *args):
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def git_show(repo, rev, caminho):
    """Conteúdo do arquivo na revisão, ou None se ele não existe lá."""
    r = subprocess.run(["git", "-C", repo, "show", "%s:%s" % (rev, caminho)],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def textutil(origem, formato, destino):
    """`textutil -convert` do macOS (DOC/HTM -> DOCX ou HTML)."""
    subprocess.run(["textutil", "-convert", formato, "-output", destino, origem],
                   check=True, capture_output=True)
    return destino


def _paginas_pdfkit(path):
    import pdf_macos
    from texto_vigente import normalizar_pdf
    return [normalizar_pdf(p) for p in pdf_macos.texto_pdfkit(path).split("\f")]


CACHE_PAGINAS = os.path.join(RAIZ, "dados", "fase-3", "paginas")


def extrair_paginas(path):
    """Texto de cada página do PDF (PDFKit), com cache em dados/fase-3/paginas/."""
    with open(path, "rb") as f:
        chave = hashlib.sha1(f.read()).hexdigest()[:16]
    cache = os.path.join(CACHE_PAGINAS, chave + ".json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return json.load(f)
    pags = _paginas_pdfkit(path)
    os.makedirs(CACHE_PAGINAS, exist_ok=True)
    with open(cache, "w", encoding="utf-8") as f:
        json.dump(pags, f, ensure_ascii=False)
    return pags


# ---------------------------------------------------------------- utilitários

def ler(repo, rel):
    with open(os.path.join(repo, rel), encoding="utf-8") as f:
        return f.read()


def frontmatter(texto):
    linhas = texto.split("\n")
    fim = T.fim_frontmatter(linhas)
    res = {}
    for ln in linhas[1:max(0, fim - 1)]:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s?(.*)$", ln)
        if m:
            res[m.group(1)] = m.group(2).strip()
    return res


def camada_de(norma):
    if norma.startswith(("cvm/resolucoes/", "cvm/instrucoes/")):
        return "1"
    if norma.startswith(("cvm/oficios-circulares/", "cvm/pareceres-orientacao/")):
        return "2"
    if norma.startswith("leis/"):
        return "3"
    if norma.startswith(("cmn/", "bcb/")):
        return "4"
    if norma.startswith("autorregulacao/"):
        return "5"
    return "?"


def novo_id(*partes):
    return "u" + hashlib.sha1("|".join(str(p) for p in partes).encode("utf-8")).hexdigest()[:10]


def unidade(camada, categoria, norma, localizador, posicao, **extra):
    u = {"id": novo_id(camada, categoria, norma, localizador, extra.get("commit") or ""),
         "camada": camada, "categoria": categoria, "norma": norma, "localizador": localizador,
         "posicao": posicao, "commit": None, "fonte": None, "paginas": None, "sobrescrito": None}
    u.update(extra)
    return u


def relatorios(repo):
    """{arquivo do acervo: item do relatório do texto_vigente} das camadas 1, 2, 4 e 5."""
    res = {}
    for c in (1, 2, 4, 5):
        p = os.path.join(repo, "dados", "texto-vigente-camada-%d.json" % c)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for it in json.load(f):
                res[it["arquivo"]] = it
    return res


def fonte_do_item(item):
    """(caminho relativo da fonte em dados/texto-vigente-fontes, tipo, extensão)."""
    tipo, ext = item["fonte"].split()
    return "%s/%s.%s" % (FONTES_TV, item["id"], ext), tipo, ext


def arquivos_acervo(repo, prefixo):
    base = os.path.join(repo, NORMAS)
    res = []
    for raiz, _dirs, arqs in os.walk(os.path.join(base, prefixo)):
        for a in arqs:
            if a.endswith(".md"):
                res.append(os.path.relpath(os.path.join(raiz, a), base).replace(os.sep, "/"))
    return sorted(res)


def secoes_de_artigo(texto):
    """[(localizador, posição, texto)] das seções de artigo (nome com "Art.")."""
    linhas = texto.split("\n")
    return [(nome, a, "\n".join(linhas[a:b])) for nome, a, b in T.secoes(texto) if "Art." in nome]


def todas_secoes(texto):
    """[(localizador, posição, texto)] de todas as seções (preâmbulo, artigos, anexos, notas)."""
    linhas = texto.split("\n")
    return [(nome, a, "\n".join(linhas[a:b])) for nome, a, b in T.secoes(texto)]


# ---------------------------------------------------------------- camada 1: replay

def commits_replay(repo, ref=REF):
    """[(sha, mensagem)] dos commits de alteração e retificação, do mais antigo ao mais novo."""
    res = []
    for ln in git(repo, "log", ref, "--format=%H%x09%s").splitlines():
        sha, _, msg = ln.partition("\t")
        if "): altera" in msg or msg.startswith("Retificacao da"):
            res.append((sha, msg))
    return res[::-1]


def _excluido(rel):
    return rel.startswith(EXCLUIR) or rel in EXCLUIR


def diff_commit(repo, sha):
    """{arquivo relativo a NORMAS: [(sinal, linha 0-based, texto)]} do diff -U0 do commit."""
    saida = git(repo, "show", sha, "-U0", "--diff-algorithm=histogram", "--format=",
                "--no-color", "--", NORMAS + "/")
    res, atual, velho, novo = {}, None, 0, 0
    pref = NORMAS + "/"
    for ln in saida.split("\n"):
        if ln.startswith("+++ "):
            alvo = ln[4:]
            atual = alvo[2:][len(pref):] if alvo.startswith("b/" + pref) else None
            if atual is not None and _excluido(atual):
                atual = None
            if atual is not None:
                res.setdefault(atual, [])
            continue
        if ln.startswith("--- ") or ln.startswith("diff --git") or ln.startswith("index "):
            continue
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
        if m:
            velho, novo = int(m.group(1)), int(m.group(3))
            if (m.group(2) or "1") != "0":
                velho -= 1
            if (m.group(4) or "1") != "0":
                novo -= 1
            continue
        if atual is None or not ln:
            continue
        if ln[0] == "-":
            res[atual].append(("-", velho, ln[1:]))
            velho += 1
        elif ln[0] == "+":
            res[atual].append(("+", novo, ln[1:]))
            novo += 1
    return {k: v for k, v in res.items() if v}


def atos_do_commit(repo, sha):
    saida = git(repo, "show", sha, "--name-only", "--format=", "--", NORMAS + "/cvm/alteradoras/")
    return [ln[len(NORMAS) + 1:] for ln in saida.split("\n") if ln.strip()]


def categoria_replay(norma, localizador, novas, velhas):
    rev_n = sum(len(re.findall(r"\(Revogad", x)) for x in novas)
    rev_v = sum(len(re.findall(r"\(Revogad", x)) for x in velhas)
    if rev_n > rev_v:
        return "revogacao"
    if any(x.lstrip().startswith("|") for x in novas + velhas) or T.eh_anexo(localizador, norma):
        return "tabela-anexo"
    if novas and not velhas:
        return "inclusao"
    return "nova-redacao"


def universo_replay(repo, ref=REF):
    """Unidades (commit, arquivo, dispositivo) dos commits de replay."""
    unidades, finais = [], {}
    for ordem, (sha, msg) in enumerate(commits_replay(repo, ref)):
        atos = atos_do_commit(repo, sha)
        for norma, linhas in sorted(diff_commit(repo, sha).items()):
            depois = git_show(repo, sha, NORMAS + "/" + norma) or ""
            antes = git_show(repo, sha + "^", NORMAS + "/" + norma) or ""
            ld, la = depois.split("\n"), antes.split("\n")
            fd, fa = T.fim_frontmatter(ld), T.fim_frontmatter(la)
            sd, sa = T.secoes(depois), T.secoes(antes)
            grupos = {}
            for sinal, i, txt in linhas:
                if not txt.strip():
                    continue
                if sinal == "+":
                    if i < fd:
                        continue
                    loc = T.secao_da_linha(sd, i)
                else:
                    if i < fa:
                        continue
                    loc = T.secao_da_linha(sa, i)
                g = grupos.setdefault(loc, {"+": [], "-": [], "pos": None})
                g[sinal].append(txt)
                if sinal == "+" and g["pos"] is None:
                    g["pos"] = i
                elif g["pos"] is None:
                    g["pos"] = i
            if not grupos:
                continue
            if norma not in finais:
                fin = git_show(repo, ref, NORMAS + "/" + norma)
                finais[norma] = set(x.strip() for x in (fin or "").split("\n"))
            for loc, g in grupos.items():
                cat = categoria_replay(norma, loc, g["+"], g["-"])
                sobre = any(x.strip() and x.strip() not in finais[norma] for x in g["+"])
                u = unidade("1", cat, norma, loc, g["pos"], commit=sha, ordem_commit=ordem,
                            mensagem=msg, atos=atos, sobrescrito=sobre,
                            linhas_novas=len(g["+"]), linhas_removidas=len(g["-"]))
                unidades.append(u)
    return unidades


# ---------------------------------------------------------------- camada 1: vigência

def censo_vigencia(repo, data_base=DATA_BASE):
    """Datas de vigor dos atos alteradores (sem as retificações) e o gate (nenhuma data depois
    da data-base)."""
    atos = []
    for rel in arquivos_acervo(repo, "cvm/alteradoras"):
        if "retificacao" in rel:
            continue
        texto = ler(repo, NORMAS + "/" + rel)
        fm = frontmatter(texto)
        cl = T.clausulas_de_vigor(T.corpo(texto), fm.get("publicacao_dou"))
        proprias = sorted({d for c in cl if not c["citacao"] for d in c["datas"]})
        atos.append({"ato": rel.rsplit("/", 1)[-1][:-3], "arquivo": rel, "numero": fm.get("numero"),
                     "publicacao_dou": fm.get("publicacao_dou"), "clausulas": cl, "datas": proprias,
                     "data_max": proprias[-1] if proprias else None,
                     "diferida": bool(proprias) and proprias[-1] > (fm.get("publicacao_dou") or "")})
    depois = [a["ato"] for a in atos if a["data_max"] and a["data_max"] > data_base]
    return {"data_base": data_base, "atos": atos, "total": len(atos),
            "diferidos": sum(1 for a in atos if a["diferida"]),
            "sem_data": [a["ato"] for a in atos if not a["datas"]],
            "depois_da_data_base": depois, "gate_ok": not depois}


def universo_vigencia(repo, replay):
    """Unidades da vigência diferida: dispositivos de fontes/vigencia-excecoes.json casados com as
    unidades de replay do mesmo ato, arquivo e artigo. Sem o arquivo, lista vazia."""
    p = os.path.join(repo, "fontes", "vigencia-excecoes.json")
    if not os.path.exists(p):
        return [], []
    with open(p, encoding="utf-8") as f:
        excecoes = json.load(f)
    res, avisos = [], []
    for e in excecoes:
        ato = "cvm/alteradoras/%s.md" % e["ato"]
        achou = [u for u in replay if ato in u["atos"] and u["norma"] == e["norma"]
                 and (u["localizador"] == e["artigo"] or u["localizador"].endswith(", " + e["artigo"]))]
        if not achou:
            avisos.append("vigência: sem unidade de replay para %s %s %s" % (e["ato"], e["norma"], e["artigo"]))
            continue
        for u in achou:
            v = dict(u, categoria="vigencia-diferida", vigor=e.get("vigor"), unidade_replay=u["id"])
            v["id"] = novo_id("1", "vigencia-diferida", u["norma"], u["localizador"], u["commit"])
            res.append(v)
    return res, avisos


# ---------------------------------------------------------------- camada 1: sem histórico

def _docx_de(path, ext, pasta):
    if ext == "docx" and zipfile.is_zipfile(path):
        return path
    return textutil(path, "docx", os.path.join(pasta, "f.docx"))


def artigos_com_lista(path, ext, tipo_fonte):
    """Artigos (localizadores) que têm parágrafo numerado pela lista automática do Word, pela
    própria conversão do texto_vigente com uma marca no fim de cada parágrafo numerado."""
    import converter
    from texto_vigente import sem_tachado
    original = converter._paragrafo

    def marcado(p, numeracao=None, opc=None):
        visto = []

        class Espiao:
            def rotulo(self, par):
                r = numeracao.rotulo(par)
                if r:
                    visto.append(r)
                return r
        r = original(p, Espiao() if numeracao else None, opc)
        if r and visto and not re.fullmatch(r"~~[^~]*~~", r):
            r += " " + MARCA_LISTA
        return r

    converter._paragrafo = marcado
    try:
        with tempfile.TemporaryDirectory() as d:
            md = converter.docx_para_md(_docx_de(path, ext, d), caixas=True, notas=True)
    finally:
        converter._paragrafo = original
    texto = converter.normalizar_artigos(sem_tachado(md) if tipo_fonte == "consolidado" else md)
    return {nome for nome, _a, t in secoes_de_artigo(texto) if MARCA_LISTA in t}


_ITEM = re.compile(r"(?m)^(?:[IVXLC]+\s*[-–—]|[a-z]\)|\d+\.)\s")


def universo_sem_historico(repo, tocados, rels, avisos):
    res = []
    for norma, it in sorted(rels.items()):
        if camada_de(norma) != "1" or norma in tocados:
            continue
        fonte, tipo, ext = fonte_do_item(it)
        if ext not in ("docx", "doc", "htm"):
            continue
        texto = ler(repo, NORMAS + "/" + norma)
        metodo = "conversao"
        try:
            listas = artigos_com_lista(os.path.join(repo, fonte), ext, tipo)
        except Exception as e:  # noqa: BLE001 — sem textutil ou fonte ausente: heurística
            listas, metodo = None, "heuristica"
            avisos.append("lista numerada por heurística em %s: %s" % (norma, type(e).__name__))
        for loc, pos, t in secoes_de_artigo(texto):
            tem = (loc in listas) if listas is not None else bool(_ITEM.search(t))
            res.append(unidade("1", "sem-historico", norma, loc, pos, fonte=fonte,
                               tipo_fonte="%s %s" % (tipo, ext), lista_numerada=tem,
                               lista_numerada_metodo=metodo))
    return res


# ---------------------------------------------------------------- camada 2

def blocos_de_palavras(texto, alvo=PALAVRAS_BLOCO):
    """Blocos de parágrafos com ~`alvo` palavras do corpo (sem a seção de notas de rodapé)."""
    c = T.corpo(texto).split("\n" + T.NOTAS)[0]
    blocos, atual, n = [], [], 0
    for par in [p for p in c.split("\n") if p.strip()]:
        atual.append(par)
        n += len(par.split())
        if n >= alvo:
            blocos.append("\n\n".join(atual))
            atual, n = [], 0
    if atual:
        if blocos and n < alvo // 3:
            blocos[-1] += "\n\n" + "\n\n".join(atual)
        else:
            blocos.append("\n\n".join(atual))
    return blocos


def notas_e_diagramas(texto):
    """[(localizador, texto)] das notas de rodapé ("nota 3") e dos blocos [Diagrama]."""
    res = []
    c = T.corpo(texto)
    if T.NOTAS in c:
        for ln in c.split(T.NOTAS, 1)[1].split("\n"):
            m = re.match(r"^\[(\d+)\]\s+(.*)$", ln.strip())
            if m:
                res.append(("nota %s" % m.group(1), m.group(2)))
    k = 0
    for ln in c.split("\n"):
        if ln.startswith("> [Diagrama]"):
            k += 1
            res.append(("diagrama %d" % k, ln[len("> [Diagrama]"):].strip()))
    return res


def paginas_ocr(repo, id_):
    p = os.path.join(repo, "dados", "ocr", id_ + ".txt")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read().split("\f")


def universo_camada2(repo, rels, avisos):
    res = []
    for norma, it in sorted(rels.items()):
        if camada_de(norma) != "2":
            continue
        fonte, tipo, ext = fonte_do_item(it)
        nivel = it.get("nivel_verificacao")
        if nivel == "ocr":
            pags = paginas_ocr(repo, it["id"]) or extrair_paginas(os.path.join(repo, fonte))
            for k, _p in enumerate(pags, 1):
                res.append(unidade("2", "ocr", norma, "página %d" % k, k, fonte=fonte, paginas=[k]))
        elif ext == "pdf":
            try:
                pags = extrair_paginas(os.path.join(repo, fonte))
            except Exception as e:  # noqa: BLE001
                avisos.append("sem páginas de %s: %s" % (fonte, e))
                continue
            for k, p in enumerate(pags, 1):
                if len(p.split()) >= PALAVRAS_PAGINA:
                    res.append(unidade("2", "oficio-pdf", norma, "página %d" % k, k, fonte=fonte,
                                       paginas=[k]))
        else:
            texto = ler(repo, NORMAS + "/" + norma)
            for k, b in enumerate(blocos_de_palavras(texto), 1):
                res.append(unidade("2", "parecer-doc", norma, "bloco %d" % k, k, fonte=fonte,
                                   tipo_fonte=it["fonte"], inicio=" ".join(b.split()[:10]),
                                   fim=" ".join(b.split()[-10:])))
    # nota de rodapé e diagrama: em toda norma da CVM que os tem (C2 da tabela do plano)
    for norma in arquivos_acervo(repo, "cvm"):
        if _excluido(norma):
            continue
        texto = ler(repo, NORMAS + "/" + norma)
        itens = notas_e_diagramas(texto)
        if not itens:
            continue
        it = rels.get(norma)
        if not it or fonte_do_item(it)[2] not in ("docx", "doc"):
            avisos.append("nota/diagrama sem fonte DOCX/DOC: %s" % norma)
            continue
        fonte = fonte_do_item(it)[0]
        for k, (loc, txt) in enumerate(itens, 1):
            res.append(unidade("2", "nota-diagrama", norma, loc, k, fonte=fonte,
                               tipo_fonte=it["fonte"], camada_norma=camada_de(norma)))
    return res


# ---------------------------------------------------------------- camada 3

def artigos_com_rotulo(html_bytes):
    import converter
    html = converter.decodificar_html(html_bytes)
    marcado = converter._ROTULO_VIGENCIA.sub(" %s " % MARCA_ROTULO, html)
    md = converter.normalizar_artigos(converter.planalto_html_para_md(marcado), ignorar_citacoes=True)
    return {nome for nome, _a, t in secoes_de_artigo(md) if MARCA_ROTULO in t}


def html_planalto(repo, id_):
    p = os.path.join(repo, "dados", "fontes", "relatorio.json")
    with open(p, encoding="utf-8") as f:
        rel = json.load(f)
    e = rel.get(id_)
    if not e:
        return None
    return "dados/fontes/" + os.path.basename(e["arquivo"])


def universo_camada3(repo, avisos):
    res, grupos = [], {}
    for norma in arquivos_acervo(repo, "leis"):
        raiz = norma.split("/")[1]
        grupos.setdefault(raiz, []).append(norma)
    for raiz, normas in sorted(grupos.items()):
        principal = [n for n in normas if n.endswith(("/index.md",)) or n.count("/") == 1][0]
        id_ = frontmatter(ler(repo, NORMAS + "/" + principal)).get("id")
        fonte = html_planalto(repo, id_)
        rotulos = set()
        if fonte and os.path.exists(os.path.join(repo, fonte)):
            with open(os.path.join(repo, fonte), "rb") as f:
                rotulos = artigos_com_rotulo(f.read())
        else:
            avisos.append("lei sem HTML do Planalto: %s" % raiz)
        for norma in normas:
            for loc, pos, t in secoes_de_artigo(ler(repo, NORMAS + "/" + norma)):
                cats = []
                if re.search(r"\(Reda[çc][ãa]o dada|\(Inclu[íi]d", t):
                    cats.append("redacao-incluido")
                if re.search(r"\(Revogad", t):
                    cats.append("revogado")
                if loc in rotulos:
                    cats.append("rotulo-margem")
                if re.search(r"(?m)^\|", t):
                    cats.append("tabela")
                for c in cats:
                    res.append(unidade("3", c, norma, loc, pos, fonte=fonte, lei=id_))
    return res


# ---------------------------------------------------------------- camada 4

def artigos_com_tachado(html):
    import html_bcb
    from texto_vigente import sem_tachado_bcb
    import converter
    md = html_bcb.html_para_md(html)
    out, tabela_riscada, em_tabela = [], False, False
    for ln in md.split("\n"):
        if ln.startswith("|"):
            em_tabela = True
            tabela_riscada = tabela_riscada or "~~" in ln
            out.append(ln)
            continue
        if em_tabela:
            if tabela_riscada:
                out.append(MARCA_TACHADO)
            em_tabela, tabela_riscada = False, False
        out.append(ln + (" " + MARCA_TACHADO if "~~" in ln else ""))
    if em_tabela and tabela_riscada:
        out.append(MARCA_TACHADO)
    texto = converter.normalizar_artigos(sem_tachado_bcb("\n".join(out)))
    return {nome for nome, _a, t in todas_secoes(texto) if MARCA_TACHADO in t}


def universo_camada4(repo, rels, avisos):
    res = []
    for norma, it in sorted(rels.items()):
        if camada_de(norma) != "4":
            continue
        fonte, tipo, ext = fonte_do_item(it)
        if ext == "pdf":
            try:
                pags = extrair_paginas(os.path.join(repo, fonte))
            except Exception as e:  # noqa: BLE001
                avisos.append("sem páginas de %s: %s" % (fonte, e))
                continue
            for k, _p in enumerate(pags, 1):
                res.append(unidade("4", "so-pdf", norma, "página %d" % k, k, fonte=fonte, paginas=[k]))
            continue
        texto = ler(repo, NORMAS + "/" + norma)
        secs = todas_secoes(texto)
        tachados = set()
        try:
            with open(os.path.join(repo, fonte), encoding="utf-8", errors="replace") as f:
                tachados = artigos_com_tachado(f.read())
        except OSError as e:
            avisos.append("sem HTML do BCB %s: %s" % (fonte, e))
        for loc, pos, t in secs:
            cats = []
            if loc in tachados:
                cats.append("tachado")
            if re.search(r"reda[çc][ãa]o dada", t, re.I):
                cats.append("nota-redacao")
            if re.search(r"(?m)^\|", t):
                cats.append("tabela")
            for c in cats:
                res.append(unidade("4", c, norma, loc, pos, fonte=fonte))
    return res


# ---------------------------------------------------------------- camada 5

_PONTILHADO = re.compile(r"(?:\.{4,}|…{2,}|_{4,})\s*\d{1,3}\s*$")
_ENTRADA_SUMARIO = re.compile(r"\s\d{1,3}\s*$")


def eh_sumario(pagina):
    """Página de sumário: "sumário"/"índice" nas primeiras linhas e várias linhas que terminam em
    número de página, ou 6 linhas ou mais com pontilhado e número."""
    linhas = [x.strip() for x in pagina.split("\n") if x.strip()]
    if sum(1 for x in linhas if _PONTILHADO.search(x)) >= 6:
        return True
    topo = " ".join(linhas[:6]).lower()
    if re.search(r"\b(sum[áa]rio|[íi]ndice)\b", topo):
        return sum(1 for x in linhas if _ENTRADA_SUMARIO.search(x)) >= 5
    return False


def eh_tabela(pagina):
    """Página com tabela que o PDF achatou em texto: título "Tabela"/"Quadro" no começo de linha,
    ou metade das linhas curtas (até 3 palavras) com 15 linhas curtas ou mais e 5 linhas que são
    só número, percentual ou valor."""
    linhas = [x.strip() for x in pagina.split("\n") if x.strip()]
    if not linhas:
        return False
    if any(re.match(r"^(tabela|quadro)\s+(\d+|[ivx]+)\b", x, re.I) for x in linhas):
        return True
    curtas = [x for x in linhas if len(x.split()) <= 3]
    numeros = [x for x in curtas if re.fullmatch(r"[R$\s]*[\d.,%]+[%]?", x)]
    return len(curtas) >= 15 and len(curtas) >= len(linhas) / 2 and len(numeros) >= 5


def universo_camada5(repo, rels, avisos):
    res = []
    for norma, it in sorted(rels.items()):
        if camada_de(norma) != "5":
            continue
        fonte, _tipo, _ext = fonte_do_item(it)
        try:
            pags = extrair_paginas(os.path.join(repo, fonte))
        except Exception as e:  # noqa: BLE001
            avisos.append("sem páginas de %s: %s" % (fonte, e))
            continue
        for k, p in enumerate(pags, 1):
            if eh_sumario(p):
                res.append(unidade("5", "sumario", norma, "página %d" % k, k, fonte=fonte, paginas=[k]))
            elif eh_tabela(p):
                res.append(unidade("5", "tabela", norma, "página %d" % k, k, fonte=fonte, paginas=[k]))
        for k in range(1, len(pags)):
            if (len(pags[k - 1].split()) >= PALAVRAS_PAGINA and len(pags[k].split()) >= PALAVRAS_PAGINA
                    and not eh_sumario(pags[k - 1])):
                res.append(unidade("5", "quebra-pagina", norma, "páginas %d-%d" % (k, k + 1), k,
                                   fonte=fonte, paginas=[k, k + 1]))
        inc = frontmatter(ler(repo, NORMAS + "/" + norma)).get("incerteza", "")
        if "registro das assinaturas" in inc and len(pags) >= 2:
            n = len(pags)
            res.append(unidade("5", "assinaturas", norma, "páginas %d-%d" % (n - 1, n), n - 1,
                               fonte=fonte, paginas=[n - 1, n]))
    return res


# ---------------------------------------------------------------- tudo

def chave_ordem(u):
    return (u["camada"], u["categoria"], u["norma"], u["posicao"] if u["posicao"] is not None else -1,
            u["localizador"], u.get("commit") or "")


def construir(repo=RAIZ, ref=REF, data_base=DATA_BASE, camadas=("1", "2", "3", "4", "5")):
    avisos, unidades = [], []
    rels = relatorios(repo)
    vig = None
    if "1" in camadas:
        replay = universo_replay(repo, ref)
        tocados = {u["norma"] for u in replay}
        vig_u, av = universo_vigencia(repo, replay)
        avisos += av
        vig = censo_vigencia(repo, data_base)
        unidades += replay + vig_u + universo_sem_historico(repo, tocados, rels, avisos)
    if "2" in camadas:
        unidades += universo_camada2(repo, rels, avisos)
    if "3" in camadas:
        unidades += universo_camada3(repo, avisos)
    if "4" in camadas:
        unidades += universo_camada4(repo, rels, avisos)
    if "5" in camadas:
        unidades += universo_camada5(repo, rels, avisos)
    unidades.sort(key=chave_ordem)
    contagem = {}
    for u in unidades:
        k = "%s/%s" % (u["camada"], u["categoria"])
        c = contagem.setdefault(k, {"unidades": 0, "normas": set()})
        c["unidades"] += 1
        c["normas"].add(u["norma"])
    contagem = {k: {"unidades": v["unidades"], "normas": len(v["normas"])}
                for k, v in sorted(contagem.items())}
    return {"data_base": data_base, "ref": ref, "contagem": contagem, "vigencia": vig,
            "avisos": avisos, "unidades": unidades}
