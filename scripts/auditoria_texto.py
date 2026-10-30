#!/usr/bin/env python3
"""Peças de texto da auditoria da Fase 3 (scripts/auditoria.py): seções do Markdown do acervo
por dispositivo, normalização do comparador (C7), diff por palavra, janela do acervo que
corresponde a uma transcrição, recorte de HTML por trecho e datas de vigor dos atos.

Só biblioteca padrão. Nada aqui lê o Git nem roda ferramenta do macOS.
"""
import difflib
import html as htmllib
import re
import unicodedata
from collections import Counter

# ---------------------------------------------------------------- seções do acervo

ART = re.compile(r"^## (Art\. \S+)\s*$")
ANEXO = re.compile(r"^(?:ANEXO|SUPLEMENTO)\b[^a-z]{0,80}$")
NOTAS = "## Notas de rodapé"
PREAMBULO = "preambulo"


def fim_frontmatter(linhas):
    """Índice (0-based) da primeira linha depois do frontmatter; 0 se não há frontmatter."""
    if linhas and linhas[0].strip() == "---":
        for i in range(1, len(linhas)):
            if linhas[i].strip() == "---":
                return i + 1
    return 0


def corpo(texto):
    linhas = texto.split("\n")
    return "\n".join(linhas[fim_frontmatter(linhas):])


def secoes(texto):
    """[(localizador, primeira linha, linha depois da última)] do arquivo inteiro (índices 0-based
    sobre texto.split("\\n")), a partir do fim do frontmatter.

    Fronteiras: `## Art. N`, linha de anexo ("ANEXO A", "SUPLEMENTO B", em caixa alta) e a seção
    final "## Notas de rodapé". Artigo dentro de anexo leva o anexo no nome ("ANEXO A, Art. 1º").
    Antes do primeiro dispositivo: "preambulo". Nome repetido ganha " (2)", " (3)"."""
    linhas = texto.split("\n")
    ini = fim_frontmatter(linhas)
    marcos, anexo = [], None
    for i in range(ini, len(linhas)):
        ln = linhas[i].rstrip()
        m = ART.match(ln)
        if m:
            marcos.append((m.group(1) if not anexo else "%s, %s" % (anexo, m.group(1)), i))
        elif ln == NOTAS:
            marcos.append(("Notas de rodapé", i))
        elif ANEXO.match(ln) and len(ln) <= 80:
            anexo = re.sub(r"\s+", " ", ln.strip())
            marcos.append((anexo, i))
    if not marcos or marcos[0][1] > ini:
        marcos.insert(0, (PREAMBULO, ini))
    vistos, res = Counter(), []
    for k, (nome, i) in enumerate(marcos):
        fim = marcos[k + 1][1] if k + 1 < len(marcos) else len(linhas)
        vistos[nome] += 1
        if vistos[nome] > 1:
            nome = "%s (%d)" % (nome, vistos[nome])
        res.append((nome, i, fim))
    return res


def secao_da_linha(secs, i):
    """Localizador da seção que contém a linha i (0-based)."""
    for nome, a, b in secs:
        if a <= i < b:
            return nome
    return secs[-1][0] if secs else PREAMBULO


def texto_secao(texto, localizador):
    """Texto da seção `localizador`, ou None se ela não existe."""
    linhas = texto.split("\n")
    for nome, a, b in secoes(texto):
        if nome == localizador:
            return "\n".join(linhas[a:b]).strip("\n") + "\n"
    return None


def mapa_secoes(texto):
    linhas = texto.split("\n")
    return {nome: "\n".join(linhas[a:b]).strip("\n") + "\n" for nome, a, b in secoes(texto)}


def eh_anexo(localizador, arquivo=""):
    base = arquivo.rsplit("/", 1)[-1]
    return (localizador.startswith(("ANEXO", "SUPLEMENTO"))
            or base.startswith(("anexo", "suplemento")))


# ---------------------------------------------------------------- normalização (C7)

_ASPAS = str.maketrans({
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "‚": "'", "´": "'",
    "`": "'", "–": "-", "—": "-", "‒": "-", "―": "-", "−": "-", "‐": "-", "‑": "-",
    "º": "o", "°": "o", "ª": "a", " ": " ", " ": " ", " ": " ", "​": "",
    "﻿": "", "…": "...",
})
_LIGADURAS = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


def normalizar(txt):
    """Texto para comparação: NFKC, minúsculas, aspas e travessões retos, º/° = o, ligaduras,
    sem Markdown (#, *, >, |, separador de tabela, ~~), "Art. 10." = "art 10", espaços únicos."""
    t = txt or ""
    for k, v in _LIGADURAS.items():
        t = t.replace(k, v)
    t = t.translate(_ASPAS)
    t = unicodedata.normalize("NFKC", t).lower()
    linhas = []
    for ln in t.split("\n"):
        s = ln.strip()
        if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?", s):
            continue  # separador de tabela
        s = re.sub(r"^#{1,6}\s+", "", s)
        s = re.sub(r"^(>\s*)+", "", s)
        s = s.replace("[diagrama]", " ")
        linhas.append(s)
    t = " ".join(linhas)
    t = re.sub(r"[*_|~]+", " ", t)
    t = re.sub(r"\bart\s*\.\s*(\d)", r"art \1", t)
    t = re.sub(r"\b(art \d+(?:\.\d{3})*o?(?:-[a-z]{1,2})?)\s*\.(?=\s|$)", r"\1", t)
    # "(Revogado pela Resolução CVM nº 181)" = "(Revogado)": a autoria da revogação é nota, não texto
    t = re.sub(r"\((revogad[oa]s?)\s+(?:pel[oa]s?|por)\s[^)]*\)", r"(\1)", t)
    t = re.sub(r"\s+([,.;:!?)\]])", r"\1", t)
    t = re.sub(r"([(\[])\s+", r"\1", t)
    return re.sub(r"\s+", " ", t).strip()


def palavras(txt):
    return normalizar(txt).split()


# ---------------------------------------------------------------- diff por palavra

CONTEXTO = 8


def diff_palavras(esperado, saida, contexto=CONTEXTO):
    """[{op, esperado, saida, antes, depois}] das diferenças entre as palavras normalizadas."""
    a, b = palavras(esperado), palavras(saida)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    res = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        res.append({"op": op, "esperado": " ".join(a[i1:i2]), "saida": " ".join(b[j1:j2]),
                    "antes": " ".join(a[max(0, i1 - contexto):i1]),
                    "depois": " ".join(a[i2:i2 + contexto])})
    return res


# ---------------------------------------------------------------- janela do acervo

N_GRAMA = 6


def janela(acervo, saida, n=N_GRAMA, margem=20):
    """Trecho do `acervo` (texto) que melhor corresponde à `saida` (transcrição de uma página ou
    bloco): votação de deslocamento pelos n-gramas comuns e corte pelas pontas que casam.
    Devolve (texto normalizado da janela, início, fim em palavras) ou ("", 0, 0)."""
    a, b = palavras(acervo), palavras(saida)
    if not a or not b:
        return "", 0, 0
    indice = {}
    for i in range(len(a) - n + 1):
        indice.setdefault(tuple(a[i:i + n]), []).append(i)
    votos = Counter()
    for j in range(len(b) - n + 1):
        for i in indice.get(tuple(b[j:j + n]), ())[:50]:
            votos[i - j] += 1
    if not votos:
        return "", 0, 0
    desl = votos.most_common(1)[0][0]
    ini, fim = max(0, desl - margem), min(len(a), desl + len(b) + margem)
    sm = difflib.SequenceMatcher(None, a[ini:fim], b, autojunk=False)
    blocos = [m for m in sm.get_matching_blocks() if m.size >= 2]
    if not blocos:
        return "", 0, 0
    i0 = ini + blocos[0].a - blocos[0].b if blocos[0].b <= 3 else ini + blocos[0].a
    i1 = ini + blocos[-1].a + blocos[-1].size
    resto = len(b) - (blocos[-1].b + blocos[-1].size)
    if resto <= 3:
        i1 += resto
    i0, i1 = max(0, i0), min(len(a), i1)
    return " ".join(a[i0:i1]), i0, i1


def linhas_repetidas(texto, minimo=3):
    """Linhas normalizadas (sem dígitos) que aparecem `minimo` vezes ou mais: cabeçalho e rodapé."""
    c = Counter()
    for ln in corpo(texto).split("\n"):
        s = re.sub(r"\d+", "#", normalizar(ln))
        if len(s) >= 4:
            c[s] += 1
    return {s for s, k in c.items() if k >= minimo}


# ---------------------------------------------------------------- HTML

_BLOCO = re.compile(r"(?is)<(/?)(p|div|h[1-6]|li|table|blockquote|center|ul|ol)\b[^>]*>")


def corpo_html(html):
    """(cabeça com <style>, corpo) do HTML."""
    m = re.search(r"(?is)<body\b[^>]*>", html)
    ini = m.end() if m else 0
    f = re.search(r"(?is)</body\s*>", html)
    fim = f.start() if f else len(html)
    estilos = "\n".join(re.findall(r"(?is)<style\b.*?</style\s*>", html[:ini] if m else ""))
    return estilos, html[ini:fim]


def blocos_html(html_corpo):
    """Pedaços do corpo do HTML cortados no início de cada bloco (p, div, li, table...) fora de
    tabela; tabela inteira é um pedaço só."""
    cortes, prof = [0], 0
    for m in _BLOCO.finditer(html_corpo):
        tag, fecha = m.group(2).lower(), m.group(1) == "/"
        if tag == "table":
            if not fecha:
                if prof == 0:
                    cortes.append(m.start())
                prof += 1
            else:
                prof = max(0, prof - 1)
                if prof == 0:
                    cortes.append(m.end())
            continue
        if prof == 0 and not fecha:
            cortes.append(m.start())
    cortes = sorted(set(cortes)) + [len(html_corpo)]
    return [html_corpo[a:b] for a, b in zip(cortes, cortes[1:]) if html_corpo[a:b].strip()]


def texto_visivel(fragmento):
    t = re.sub(r"(?is)<(style|script|head|title)\b.*?</\1\s*>", " ", fragmento)
    t = re.sub(r"(?i)<br\s*/?>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return htmllib.unescape(t)


def recortar_html(html, alvo, margem=1):
    """HTML só com os blocos que cobrem o texto `alvo` (o trecho do acervo), mais `margem` blocos
    de cada lado, com o <style> original (o textutil marca o tachado por classe CSS).
    Devolve (html, achou?)."""
    estilos, corpo_ = corpo_html(html)
    blocos = blocos_html(corpo_)
    toks, dono = [], []
    for k, b in enumerate(blocos):
        p = palavras(texto_visivel(b))
        toks.extend(p)
        dono.extend([k] * len(p))
    _, i0, i1 = janela(" ".join(toks), alvo)
    if i1 <= i0:
        return None, False
    k0, k1 = max(0, dono[i0] - margem), min(len(blocos), dono[i1 - 1] + 1 + margem)
    cab = '<!DOCTYPE html>\n<html><head><meta charset="utf-8">\n%s\n</head><body>\n' % estilos
    return cab + "\n".join(blocos[k0:k1]) + "\n</body></html>\n", True


# ---------------------------------------------------------------- datas de vigor

MESES = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}
_DATA = re.compile(r"(\d{1,2})\s*[º°o]?\s+de\s+(%s)\s+de\s+(\d{4})" % "|".join(MESES), re.I)
_VIGOR = re.compile(r"entra(?:m|rá|rão)?\s+em\s+vigor", re.I)
_FECHA_CITACAO = re.compile(r'[”"“]\s*\(N\.?\s*R\.?\)|[”"]\s*[.;,]?\s*(?:\(N\.?\s*R\.?\))?[\s|]*$')
_PUBLICACAO = re.compile(r"(?:na\s+)?data\s+(?:de\s+)?(?:sua|da\s+sua)\s+publica[çc][ãa]o", re.I)


def datas_por_extenso(txt):
    """Datas "1º de fevereiro de 2021" do texto, em AAAA-MM-DD, na ordem."""
    return ["%s-%02d-%02d" % (m.group(3), MESES[m.group(2).lower()], int(m.group(1)))
            for m in _DATA.finditer(txt or "")]


def clausulas_de_vigor(corpo_ato, publicacao=None):
    """[{texto, datas, citacao}] das cláusulas "entra(m) em vigor" do corpo de um ato.

    A cláusula que termina em ":" leva os incisos seguintes ("I - em 2 de janeiro de 2025...").
    "na data de sua publicação" vale `publicacao`. `citacao`: a cláusula está dentro de texto
    citado (bloco que abre com aspas no começo da linha e fecha com aspas no fim de uma linha,
    com ou sem "(NR)"), isto é, é do texto alterado, não do próprio ato."""
    linhas = corpo_ato.split("\n")
    res, aberto = [], False
    for i, ln in enumerate(linhas):
        s = ln.strip()
        if s.startswith(("“", '"')):
            aberto = True
        citacao = aberto
        if aberto and _FECHA_CITACAO.search(s):
            aberto = False
        m = _VIGOR.search(ln)
        if not m:
            continue
        txt = s
        if txt.endswith(":"):
            for seg in linhas[i + 1:]:
                t = seg.strip()
                if not t:
                    continue
                if re.match(r"^(?:[IVXLC]+|\d+|[a-z])\s*[-–—).]", t):
                    txt += " " + t
                else:
                    break
        datas = datas_por_extenso(txt)
        if _PUBLICACAO.search(txt) and publicacao:
            datas = [publicacao] + datas
        res.append({"texto": txt, "datas": datas, "citacao": bool(citacao)})
    return res
