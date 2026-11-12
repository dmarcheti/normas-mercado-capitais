#!/usr/bin/env python3
"""Extrator de dispositivos citados em texto corrido de português jurídico (SPEC v0.5.0).

extrair_citacoes(texto, ids=None, documento=None) -> lista de citações, na ordem do texto:
    {norma, rotulo, parte, artigo, paragrafo, inciso, alinea, trecho, posicao}
- `norma`: id do acervo (`cvm-res-175`, `lei-6404`, `cvm-instr-489`, `cmn-res-4966`...) ou
  `fora:<rotulo>` quando a norma não tem arquivo no acervo (`fora:icvm-358`,
  `fora:deliberacao-cvm-538`, `fora:lcp-105`);
- `rotulo`: rótulo canônico da norma (`res-cvm-175`, `icvm-358`, `lei-6404`...), o mesmo que
  vai depois de `fora:`;
- `parte`: anexo ou suplemento da norma (`Anexo II`, `Suplemento A`); vazio na parte geral;
- `artigo` (`2º`, `90`, `1.368-C`), `paragrafo` (`§ 1º`, `parágrafo único`), `inciso`
  (`XII`), `alinea` (`d`): vazios quando o texto não os traz;
- `trecho`: até ~200 caracteres em volta da citação, com os espaços normalizados;
- `posicao`: deslocamento (caractere) do início da citação no texto original.

`ids` é o conjunto de ids do acervo (None = lê `plugins/normas/skills/consultar-normas/normas/normas.json`).
`documento` é o id da norma que contém o texto, para "desta Lei", "desta Resolução"
(None = essas referências não se resolvem).

Regras: a citação só sai quando o dispositivo se liga a uma norma (logo depois, "art. 5º da
Lei nº 6.404/76"; logo antes, "Lei nº 14.430/22, art. 26, III"; por "em seu artigo 90";
ou por anáfora simples: "do referido Anexo", "da mesma Resolução", "da citada Lei",
"desta Lei" com `documento`). Artigo solto, sem norma, não sai (precisão antes de
cobertura). "Anexo Normativo N" sem norma é o anexo da última Resolução CVM citada (sem
nenhuma, a Res. CVM 175). Resolução sem órgão: CVM até o nº 999; CMN a partir do 1.000.

formatar_normas_citadas(citacoes, mencionadas=()) e formatar_dispositivos_citados(citacoes)
montam os campos `normas_citadas` e `dispositivos_citados` do julgado (separados por `; `).
dispositivo(c) -> `<norma> [<parte> ]art. N[, § N][, inciso X][, alínea y]`;
ler_dispositivo(texto) -> dict ou None (formato do contrato).

Uso: python3 scripts/citacoes.py ARQUIVO [--documento ID]   lista as citações do arquivo
"""
import json
import os
import re
import sys

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
NORMAS_JSON = os.path.join(REPO, "plugins", "normas", "skills", "consultar-normas", "normas", "normas.json")
TRECHO_MAX = 160  # caracteres do trecho, cortado em palavra
MAX_INTERVALO = 30  # "arts. 153 a 159": expande intervalos até este tamanho

# rótulo canônico (tipo) -> prefixo do id no acervo (None = nunca está no acervo)
PREFIXO_ID = {
    "res-cvm": "cvm-res-", "icvm": "cvm-instr-", "po-cvm": "cvm-po-",
    "deliberacao-cvm": None, "lei": "lei-", "lcp": "lcp-", "decreto": "decreto-",
    "decreto-lei": None, "mp": None, "res-cmn": "cmn-res-", "res-bcb": "bcb-res-",
    "resc": "bcb-resc-", "circular-bcb": "bcb-circ-", "carta-circular-bcb": "bcb-cc-",
    "in-bcb": "bcb-in-",
}
SLUG = r"[a-z0-9]+(?:-[a-z0-9]+)*"
NORMA_RE = re.compile(r"(?:fora:%s|%s)" % (SLUG, SLUG))
DISPOSITIVO_RE = re.compile(
    r"^(?P<norma>fora:%s|%s) "
    r"(?:(?P<parte>(?:Anexo|Suplemento) [A-Z0-9]+) )?"
    r"art\. (?P<artigo>\d{1,3}(?:\.\d{3})?º?(?:-[A-Z])?)"
    r"(?:, (?P<paragrafo>§ \d+º?|parágrafo único))?"
    r"(?:, inciso (?P<inciso>[IVXLC]+))?"
    r"(?:, alínea (?P<alinea>[a-z]))?$" % (SLUG, SLUG))

_ids_cache = {}


def carregar_ids(caminho=NORMAS_JSON):
    """Ids do acervo, lidos do normas.json (vazio se o arquivo não existir)."""
    if caminho not in _ids_cache:
        if not os.path.exists(caminho):
            _ids_cache[caminho] = frozenset()
        else:
            with open(caminho, encoding="utf-8") as f:
                _ids_cache[caminho] = frozenset(i["id"] for i in json.load(f))
    return _ids_cache[caminho]


def id_do_rotulo(rotulo):
    """'res-cvm-175' -> 'cvm-res-175'; tipo sem arquivo possível no acervo -> None."""
    m = re.fullmatch(r"(.+)-(\d+)", rotulo)
    if not m or m.group(1) not in PREFIXO_ID or PREFIXO_ID[m.group(1)] is None:
        return None
    return PREFIXO_ID[m.group(1)] + m.group(2)


def rotulo_do_id(id_):
    """'cvm-res-175' -> 'res-cvm-175'; id sem molde conhecido -> o próprio id."""
    for tipo, prefixo in PREFIXO_ID.items():
        if prefixo and id_.startswith(prefixo) and id_[len(prefixo):].isdigit():
            return tipo + "-" + id_[len(prefixo):]
    return id_


def _norma(rotulo, ids):
    id_ = id_do_rotulo(rotulo)
    return id_ if id_ and id_ in ids else "fora:" + rotulo


# --- texto normalizado (espaços colapsados), com o mapa para a posição original ---

def _normalizar(texto):
    partes, mapa, ultimo = [], [], 0
    for m in re.finditer(r"\s+", texto):
        trecho = texto[ultimo:m.start()]
        partes.append(trecho)
        mapa.extend(range(ultimo, m.start()))
        partes.append(" ")
        mapa.append(m.start())
        ultimo = m.end()
    partes.append(texto[ultimo:])
    mapa.extend(range(ultimo, len(texto)))
    return "".join(partes), mapa


# --- menções a normas ---

NUM = r"\d{1,3}(?:\.\d{3})+|\d+"
NO = r"(?:n(?:\.\s?)?[º°o]?\.?\s?|n[úu]mero\s+)?"  # nº, n°, n. º, no, n.
ANO = r"(?:\s?/\s?(?P<ano>\d{4}|\d{2})(?!\d))?"
ORG_CVM = r"CVM|Comiss[ãa]o\s+de\s+Valores\s+Mobili[áa]rios"
ORG_CMN = r"CMN|Conselho\s+Monet[áa]rio\s+Nacional"
ORG_BCB = r"BCB|BACEN|Banco\s+Central(?:\s+do\s+Brasil)?"


def _i(rx):
    """Trecho sem distinção de maiúsculas (o resto do padrão distingue: inciso é romano maiúsculo)."""
    return "(?i:%s)" % rx


RX_RES = re.compile(
    r"(?<![\w-])" + _i(r"resolu[çc][ãa]o") + r"(?P<conj>\s+" + _i("conjunta") + r")?"
    r"(?:\s+(?:d[oa]\s+)?(?P<org>" + _i(ORG_CVM) + "|" + _i(ORG_CMN) + "|" + _i(ORG_BCB) + r"))?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO +
    r"(?:" + _i(r",?\s+de\s+(?:\d{1,2}\.\d{1,2}\.\d{2,4}|\d{1,2}º?\s+de\s+[a-zç]+\s+de\s+\d{4}),?") + r")?"
    r"(?:,?\s+(?:d[oa]\s+)(?P<org2>" + _i(ORG_CVM) + "|" + _i(ORG_CMN) + "|" + _i(ORG_BCB) + r"))?")
# "Resolução 454/77, com a redação dada pela Resolução 2.785/00, ambas do Conselho Monetário Nacional"
RX_ORG_COLETIVO = re.compile(
    r"(?:[^.;]|\.(?=\d)){0,160}?\b" + _i(r"(?:ambas|todas)\s+d[oa]s?\s+") +
    r"(?P<org>" + _i(ORG_CVM) + "|" + _i(ORG_CMN) + r")")
RX_SIGLA = re.compile(
    r"(?<![\w-])(?P<sig>RCVM|ICVM|IN\s?CVM|Res\.\s?CVM|Instr?\.\s?CVM|RCMN|Res\.\s?CMN|Res\.\s?BCB)"
    r"\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_INSTR = re.compile(
    r"(?<![\w-])" + _i(r"instru[çc][ãa]o") + r"(?P<normativa>\s+" + _i("normativa") + r")?"
    r"(?:\s+(?:d[oa]\s+)?(?P<org>" + _i(ORG_CVM) + "|" + _i(ORG_BCB) + r"|RFB|SRF|DREI))?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_DELIB = re.compile(
    r"(?<![\w-])" + _i(r"delibera[çc][ãa]o") + r"\s+(?:d[ao]\s+)?(?:" + _i(ORG_CVM) + r")"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_PO = re.compile(
    r"(?<![\w-])" + _i(r"parecer\s+de\s+orienta[çc][ãa]o") + r"(?:\s+(?:d[ao]\s+)?(?:" + _i(ORG_CVM) + r"))?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_LEI = re.compile(
    r"(?<![\w-])" + _i("lei") + r"(?P<comp>\s+" + _i("complementar") + r")?(?:\s+" + _i("federal") + r")?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_DECRETO = re.compile(
    r"(?<![\w-])" + _i("decreto") + r"(?P<dl>[\s-]" + _i("lei") + r")?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_MP = re.compile(
    r"(?<![\w-])(?:" + _i(r"medida\s+provis[óo]ria") + r"|MP)\s*,?\s*" + _i(NO) +
    r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_CARTA = re.compile(
    r"(?<![\w-])" + _i(r"carta[\s-]circular") + r"(?:\s+(?:d[oa]\s+)?(?:" + _i(ORG_BCB) + r"))?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_CIRC = re.compile(
    r"(?<![\w-])" + _i("circular") + r"(?:\s+(?:d[oa]\s+)?(?:" + _i(ORG_BCB) + r"))?"
    r"\s*,?\s*" + _i(NO) + r"(?P<num>" + NUM + r")(?!\d)" + ANO)
RX_ALIAS = re.compile(
    r"(?<![\w-])(?:(?P<lsa>" + _i(r"lei\s+das\s+(?:S\.?\s?A\.?|sociedades\s+(?:por\s+a[çc][õo]es|an[ôo]nimas))") +
    r"|LSA)|(?P<cpc>" + _i(r"c[óo]digo\s+de\s+processo\s+civil") + r"|CPC)|(?P<cc>" + _i(r"c[óo]digo\s+civil") + r")"
    r"|(?P<estatais>" + _i(r"lei\s+das\s+estatais") + r"))"
    r"(?![\w])")
RX_ANEXO = re.compile(
    r"(?<![\w-])(?P<tipo>" + _i("anexo") + r"(?P<normativo>\s+" + _i("normativo") + r")?|" + _i("suplemento") + r")"
    r"\s+(?P<id>[IVXL]+|[A-Z])(?![\w])")


def _num(txt):
    return int(txt.replace(".", ""))


def _org(txt):
    if not txt:
        return None
    t = txt.lower()
    if t.startswith(("cvm", "comiss")):
        return "cvm"
    if t.startswith(("cmn", "conselho")):
        return "cmn"
    return "bcb"


def _rotulo_res(m):
    n = _num(m.group("num"))
    if m.group("conj"):
        return "resc-%d" % n
    org = _org(m.group("org"))
    if org is None:
        org2 = _org(m.group("org2"))
        if org2 not in ("cvm", "cmn"):
            col = RX_ORG_COLETIVO.match(m.string, m.end())
            org2 = _org(col.group("org")) if col else None
        org = org2 if org2 in ("cvm", "cmn") else ("cvm" if n < 1000 else "cmn")
    return "res-%s-%d" % (org, n)


def _rotulo_sigla(m):
    s = re.sub(r"[\s.]", "", m.group("sig")).upper()
    n = _num(m.group("num"))
    if s in ("RCVM", "RESCVM"):
        return "res-cvm-%d" % n
    if s in ("RCMN", "RESCMN"):
        return "res-cmn-%d" % n
    if s == "RESBCB":
        return "res-bcb-%d" % n
    return "icvm-%d" % n  # ICVM, IN CVM, Instr. CVM


def _rotulo_instr(m):
    n = _num(m.group("num"))
    org = (m.group("org") or "").upper()
    if m.group("normativa"):
        o = _org(org) if org and org not in ("RFB", "SRF", "DREI") else None
        if o == "bcb":
            return "in-bcb-%d" % n
        if o == "cvm":
            return "icvm-%d" % n
        return "in-%s-%d" % (org.lower(), n) if org else "in-%d" % n
    if org and _org(org) == "bcb":
        return "in-bcb-%d" % n
    return "icvm-%d" % n  # Instrução sem órgão: CVM


# "Lei nº 6 6.404/76", "Lei 6.4 404/76", "Lei nO 6.385176": o número que a fonte (OCR, quebra
# de linha) partiu ou sujou. Só se recupera número de lei do acervo.
RX_NUM_PARTIDO = re.compile(r"[\d.,;]+(?: [\d.,;]+){0,2}")


def _lei_recuperada(m):
    """Lei do acervo cujo número começa os dígitos que seguem a menção, ou None."""
    bruto = RX_NUM_PARTIDO.match(m.string, m.start("num"))
    if not bruto:
        return None
    txt = re.sub(r"(\d) (?=\1)", "", bruto.group(0))  # dígito repetido na quebra: "6 6.404", "6.4 404"
    digitos = re.sub(r"\D", "", txt)
    leis = sorted((i[4:] for i in carregar_ids() if re.fullmatch(r"lei-\d{4,}", i)), key=len, reverse=True)
    for n in leis:
        if digitos.startswith(n) and len(n) > len(m.group("num").replace(".", "")):
            return int(n)
    return None


def _rotulo_lei(m):
    if m.group("comp"):
        return "lcp-%d" % _num(m.group("num"))
    n = _num(m.group("num"))
    if n < 1000:
        n = _lei_recuperada(m) or n
    return "lei-%d" % n


def _rotulo_decreto(m):
    return ("decreto-lei-%d" if m.group("dl") else "decreto-%d") % _num(m.group("num"))


def _rotulo_alias(m):
    if m.group("lsa"):
        return "lei-6404"
    if m.group("cpc"):
        return "lei-13105"
    if m.group("estatais"):
        return "lei-13303"
    return "lei-10406"


MENCOES = [
    (RX_RES, _rotulo_res, "resolucao"),
    (RX_SIGLA, _rotulo_sigla, None),
    (RX_INSTR, _rotulo_instr, "instrucao"),
    (RX_DELIB, lambda m: "deliberacao-cvm-%d" % _num(m.group("num")), "deliberacao"),
    (RX_PO, lambda m: "po-cvm-%d" % _num(m.group("num")), "parecer"),
    (RX_DECRETO, _rotulo_decreto, "decreto"),
    (RX_LEI, _rotulo_lei, "lei"),
    (RX_MP, lambda m: "mp-%d" % _num(m.group("num")), "mp"),
    (RX_CARTA, lambda m: "carta-circular-bcb-%d" % _num(m.group("num")), "circular"),
    (RX_CIRC, lambda m: "circular-bcb-%d" % _num(m.group("num")), "circular"),
    (RX_ALIAS, _rotulo_alias, "lei"),
]
# tipo do rótulo -> espécie, para as anáforas ("da mesma Resolução", "da referida Lei")
ESPECIE = {
    "res-cvm": "resolucao", "res-cmn": "resolucao", "res-bcb": "resolucao", "resc": "resolucao",
    "icvm": "instrucao", "in-bcb": "instrucao", "deliberacao-cvm": "deliberacao",
    "po-cvm": "parecer", "lei": "lei", "lcp": "lei", "decreto": "decreto", "decreto-lei": "decreto",
    "mp": "mp", "circular-bcb": "circular", "carta-circular-bcb": "circular",
}


def _especie(rotulo):
    m = re.fullmatch(r"(.+?)-\d+(?:-\d{4})?", rotulo)  # "-2023": ano que não é o da norma do acervo
    if not m:
        return None
    return ESPECIE.get(m.group(1)) or ("instrucao" if m.group(1).startswith("in-") else None)


def _mencoes(t):
    """Menções a normas em `t`, sem sobreposição: [{ini, fim, rotulo, parte}]."""
    achadas = []
    for rx, fn, _esp in MENCOES:
        for m in rx.finditer(t):
            ano = m.group("ano") if "ano" in rx.groupindex else None
            achadas.append((m.start(), m.end(), fn(m), ano))
    achadas.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    mencoes, fim = [], -1
    for ini, f, rot, ano in achadas:
        if ini >= fim:
            mencoes.append({"ini": ini, "fim": f, "rotulo": rot, "parte": "",
                            "impossivel": _impossivel(rot), "ano": ano})
            fim = f
    return mencoes


_anos_cache = {}


def carregar_anos(caminho=NORMAS_JSON):
    """{id: ano} das normas do acervo, pelo título ("Resolução CVM nº 17/2021" -> 2021)."""
    if caminho not in _anos_cache:
        anos = {}
        if os.path.exists(caminho):
            with open(caminho, encoding="utf-8") as f:
                for i in json.load(f):
                    m = re.search(r"/(\d{4})\b", i.get("titulo") or "")
                    if m:
                        anos[i["id"]] = int(m.group(1))
        _anos_cache[caminho] = anos
    return _anos_cache[caminho]


def _ano_escrito(txt):
    """Ano escrito na menção; None quando não é ano ("/7610": "/76" com a nota de rodapé 10)."""
    a = int(txt)
    if len(txt) == 2:
        return a + (2000 if a <= 30 else 1900)
    return a if 1900 <= a <= 2030 else None


TOLERANCIA_ANO = 1


def _ajustar_ano(mencoes, ids):
    """Número com ano que não é o da norma do acervo ("Resolução CVM nº 17/2023", e a 17 é de
    2021) não vira o id: fica fora:, com o rótulo como escrito (`fora:res-cvm-17-2023`). Ano a
    1 de distância é erro de digitação comum da fonte ("Lei 6.385/75") e liga à norma."""
    anos = carregar_anos()
    for m in mencoes:
        id_ = id_do_rotulo(m["rotulo"])
        if not m.get("ano") or not id_ or id_ not in ids or id_ not in anos:
            continue
        ano = _ano_escrito(m["ano"])
        if ano and abs(ano - anos[id_]) > TOLERANCIA_ANO:
            m["rotulo"] = "%s-%d" % (m["rotulo"], ano)
    return mencoes


def _impossivel(rotulo):
    """Número que a espécie nunca teve (ICVM com 4 dígitos: "6074/2019" por "607/2019"). A
    menção fica no lugar, para o artigo não se ligar à norma vizinha, mas não vira citação."""
    m = re.fullmatch(r"icvm-(\d+)", rotulo)
    return bool(m and int(m.group(1)) >= 1000)


ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _romano(s):
    total = 0
    for i, c in enumerate(s):
        v = ROMANOS[c]
        total += -v if i + 1 < len(s) and ROMANOS[s[i + 1]] > v else v
    return total


def _para_romano(n):
    saida = ""
    for v, s in ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            saida += s
            n -= v
    return saida


# conector entre o dispositivo (ou o anexo) e a norma
CONECTOR = r"\s?,?\s?(?:" + _i(r"d[oa]s?|de|à|às|ao|aos|n[oa]s?|em|pel[oa]s?|a") + r")\s"
RX_CONECTOR = re.compile(CONECTOR)
ANAFORA = re.compile(
    r"(?:" + CONECTOR + r"|\s?,?\s)?" + _i(
        r"(?:(?P<pre>referid[oa]s?|mesm[oa]s?|citad[oa]s?|aludid[oa]s?|mencionad[oa]s?|dest[ea]s?|dess[ea]s?|"
        r"nest[ea]s?|ness[ea]s?)\s+(?P<esp>resolu[çc][ãa]o|instru[çc][ãa]o|lei|anexo(?:\s+normativo)?|norma|"
        r"diploma(?:\s+legal)?|decreto|circular|delibera[çc][ãa]o|rcvm|icvm)"
        r"|(?P<esp2>resolu[çc][ãa]o(?:\s+(?:cvm|cmn|bcb))?|instru[çc][ãa]o(?:\s+cvm)?|lei)\s+"
        r"(?P<pos>mencionad[oa]|citad[oa]|referid[oa]))(?![\w])"))


def _resolver_anexos(t, mencoes):
    """Junta 'Anexo Normativo II à Resolução CVM nº 175' numa menção com parte; 'Anexo
    Normativo II' sem norma vira anexo da última Resolução CVM citada (ou da 175)."""
    por_ini = {m["ini"]: m for m in mencoes}
    novas = []
    for a in RX_ANEXO.finditer(t):
        tipo = "Suplemento" if a.group("tipo").lower().startswith("suplemento") else "Anexo"
        parte = "%s %s" % (tipo, a.group("id"))
        c = re.compile(r"\s?,?\s?(?:" + _i(r"à|a|da|do|de") + r")\s").match(t, a.end())
        alvo = por_ini.get(c.end()) if c else None
        if alvo is None and c:
            an = ANAFORA.match(t, a.end())
            if an:
                alvo = _anafora(an, mencoes + novas, a.start(), None)
                if alvo:
                    novas.append({"ini": a.start(), "fim": an.end(), "rotulo": alvo["rotulo"], "parte": parte,
                                  "impossivel": alvo.get("impossivel", False)})
                    continue
        if alvo is not None:
            novas.append({"ini": a.start(), "fim": alvo["fim"], "rotulo": alvo["rotulo"], "parte": parte,
                          "impossivel": alvo.get("impossivel", False)})
        elif a.group("normativo"):
            antes = [m for m in mencoes if m["fim"] <= a.start() and m["rotulo"].startswith("res-cvm-")]
            rotulo = antes[-1]["rotulo"] if antes else "res-cvm-175"
            novas.append({"ini": a.start(), "fim": a.end(), "rotulo": rotulo, "parte": parte})
    return sorted(mencoes + novas, key=lambda m: (m["ini"], m["fim"]))


def _anafora(m, mencoes, pos, documento):
    """Menção a que a anáfora se refere, ou None."""
    pre = (m.group("pre") or m.group("pos") or "").lower()
    esp = (m.group("esp") or m.group("esp2") or "").lower()
    esp = re.sub(r"[çc][ãa]o", "cao", esp.split()[0])
    if esp == "rcvm":
        esp = "resolucao"
    elif esp == "icvm":
        esp = "instrucao"
    if pre.startswith(("dest", "nest")):
        if documento and esp in ("norma", "diploma", _especie(rotulo_do_id(documento))):
            return {"ini": pos, "fim": pos, "rotulo": rotulo_do_id(documento), "parte": ""}
        return None
    antes = [x for x in mencoes if x["fim"] <= pos]
    if esp == "anexo":
        antes = [x for x in antes if x["parte"]]
    elif esp not in ("norma", "diploma"):
        antes = [x for x in antes if _especie(x["rotulo"]) == esp]
    return antes[-1] if antes else None


# --- dispositivos ---

ARTNUM = r"\d{1,3}(?:\.\d{3})?(?!\d)(?:\s?[º°]|o(?![\w]))?(?:\s?-\s?[A-Z](?![\w]))?"
ROM = r"[IVXLC]+(?![\w])"
ORDN = r"\d+(?:\s?[º°]|o(?![\w]))?"
RX_ART = re.compile(
    r"(?<![\w])(?P<kw>" + _i(r"artigos?|arts?\.?") + r")\s?(?P<lista>(?P<primeiro>" + ARTNUM +
    r")(?:\s?(?:,|e|a|ao)\s?" + ARTNUM + r")*)")
RX_PAR = re.compile(
    r"\s?,?\s?(?:§§?|" + _i(r"par[áa]grafos?") + r")\s?(?P<v>" + _i(r"[úu]nico") + "|" + ORDN +
    r"(?:\s?(?:,|e|a)\s?" + ORDN + r")*)")
RX_INC = re.compile(
    r"\s?,?\s?(?:" + _i(r"incisos?|inc\.") + r"\s?)(?P<v>" + ROM + r"(?:\s?(?:,|e|a|ao)\s?" + ROM + r")*)")
RX_INC_SOLTO = re.compile(r"\s?,\s?(?P<v>" + ROM + r")(?=\s?[,;.)]|\s(?:d[oa]|e|ou)\s|$)")
ASP = r"[\"“”'‘’]"
RX_ALI = re.compile(
    r"\s?,?\s?" + _i(r"al[íi]neas?") + r"\s?(?P<v>" + ASP + r"?[a-z]" + ASP + r"?(?:\s?(?:,|e|a)\s?" + ASP +
    r"?[a-z]" + ASP + r"?)*)(?![\w])")
RX_ALI_SOLTA = re.compile(r"\s?,\s?(?P<v>" + ASP + r"[a-z]" + ASP + r")")
RX_CAPUT = re.compile(r"\s?,?\s?" + _i("caput"))
RX_PARTE_GERAL = re.compile(_i(r"parte\s+geral") + r"(?:" + CONECTOR + r")?")
# prefixo em ordem inversa: "alínea “a” do inciso XII do", "parágrafo único do", "§ 1º do"
RX_PREFIXO = re.compile(
    r"(?:" + _i(r"al[íi]nea") + r"\s?(?P<ali>" + ASP + r"?[a-z]" + ASP + r"?)\s(?:" + _i(r"d[oa]") + r")\s)?"
    r"(?:(?:" + _i(r"inciso") + r"\s?)(?P<inc>" + ROM + r")\s(?:" + _i(r"d[oa]") + r")\s)?"
    r"(?:(?:§|" + _i(r"par[áa]grafo") + r")\s?(?P<par>" + _i(r"[úu]nico") + "|" + ORDN + r")\s(?:" +
    _i(r"d[oa]") + r")\s)?$")
RX_SEU = re.compile(_i(r"(?:(?:em|n[oa])\s+)?seus?\s+") + r"$")
RX_MESMO_ARTIGO = re.compile(
    r"(?<![\w])(?:(?:§|" + _i(r"par[áa]grafo") + r")\s?(?P<par>" + _i(r"[úu]nico") + "|" + ORDN + r")|" +
    _i(r"inciso") + r"\s?(?P<inc>" + ROM + r"))\s" +
    _i(r"d[oa]\s+(?:mesmo|referido|citado)\s+artigo") + r"(?![\w])")
GAP_CADEIA = re.compile(r"^\s?,?\s?(?:" + _i(r"e|ou|e/ou") + r")?\s?(?:" + _i(r"n[oa]s?|a[os]?|o|d[oa]s?") + r")?\s?$")
GAP_ESQUERDA = re.compile(r"^[\s”\"')]*[,(–-]?\s?(?:" + _i(r"(?:em|n[oa])\s+seus?") + r"\s)?$")


def _fmt_art(txt):
    t = re.sub(r"\s", "", txt).replace("°", "º")
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})?)(º|o)?(-[A-Z])?", t)
    if not m:
        return t
    n = int(m.group(1).replace(".", ""))
    base = m.group(1) + ("º" if n < 10 else "")
    return base + (m.group(3) or "")


def _fmt_par(txt):
    t = txt.strip().lower()
    if t.startswith(("ú", "u")):
        return "parágrafo único"
    n = int(re.match(r"\d+", t).group())
    return "§ %d%s" % (n, "º" if n < 10 else "")


def _lista(txt, item, expande):
    """'153 e 154' -> ['153', '154']; '153 a 155' -> ['153', '154', '155'] (até MAX_INTERVALO)."""
    # conectivo entre não letras, não \b: "4ºe 5º" (º conta como letra) e "132 e133" na fonte
    pedacos = re.split(r"\s?(,|(?<![A-Za-zÀ-ÿ])(?:e|ao|a)(?![A-Za-zÀ-ÿ]))\s?", txt)
    valores, intervalo = [], False
    for p in pedacos:
        p = p.strip()
        if not p or p in (",", "e"):
            continue
        if p in ("a", "ao"):
            intervalo = True
            continue
        if intervalo and valores:
            ini, fim = expande(valores[-1]), expande(p)
            if ini is not None and fim is not None and 0 < fim - ini <= MAX_INTERVALO:
                valores += [item(ini, k) for k in range(ini + 1, fim)]
        valores.append(p)
        intervalo = False
    return valores


def _arts(txt):
    def expande(a):
        m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})?)\s?[º°o]?", a.strip())
        return int(m.group(1).replace(".", "")) if m else None
    # artigo gerado no intervalo leva o ponto de milhar, como o publicado ("1.009")
    return [_fmt_art(a) for a in _lista(txt, lambda _i0, k: "{:,}".format(k).replace(",", "."), expande)]


def _romanos(txt):
    return _lista(txt, lambda _i0, k: _para_romano(k), lambda r: _romano(r) if re.fullmatch("[IVXLC]+", r) else None)


def _alineas(txt):
    """'"a" e "b"' -> ['a', 'b']; '"a" a "c"' -> ['a', 'b', 'c']."""
    letra = re.compile(r"\s?" + ASP + r"?([a-z])" + ASP + r"?")
    sep = re.compile(r"\s?(,|e|a)\s?")
    letras, pos, intervalo = [], 0, False
    while True:
        m = letra.match(txt, pos)
        if not m:
            return letras
        if intervalo and letras:
            letras += [chr(c) for c in range(ord(letras[-1]) + 1, ord(m.group(1)))]
        letras.append(m.group(1))
        s = sep.match(txt, m.end())
        if not s:
            return letras
        intervalo, pos = s.group(1) == "a", s.end()


def _modificadores(t, pos):
    """Lê § / inciso / alínea depois do artigo. Devolve (fim, pars, incs, alis)."""
    pars, incs, alis = [""], [""], [""]
    while True:
        for rx, alvo in ((RX_PAR, "p"), (RX_INC, "i"), (RX_ALI, "a"), (RX_INC_SOLTO, "i"),
                         (RX_ALI_SOLTA, "a"), (RX_CAPUT, None)):
            m = rx.match(t, pos)
            if not m:
                continue
            if alvo == "p" and pars == [""]:
                v = m.group("v")
                pars = ["parágrafo único"] if v.lower().startswith(("ú", "u")) else [
                    _fmt_par(x) for x in _lista(v, lambda _i0, k: str(k),
                                                lambda x: int(re.match(r"\d+", x).group()))]
            elif alvo == "i" and incs == [""]:
                incs = _romanos(m.group("v"))
            elif alvo == "a" and alis == [""]:
                alis = _alineas(m.group("v"))
            elif alvo is not None:
                continue
            pos = m.end()
            break
        else:
            return pos, pars, incs, alis


def _dispositivos_brutos(t):
    """[{ini, fim, arts, pars, incs, alis}] na ordem do texto."""
    brutos = []
    for m in RX_ART.finditer(t):
        plural = m.group("kw").lower() in ("arts", "arts.", "artigos")
        lista = m.group("lista") if plural else m.group("primeiro")  # "art. 5º, 30 dias" não é lista
        fim, pars, incs, alis = _modificadores(t, m.end("lista") if plural else m.end("primeiro"))
        ini = m.start()
        p = RX_PREFIXO.search(t[max(0, ini - 120):ini])
        if p and p.group(0):
            ini -= len(p.group(0))
            if p.group("par") and pars == [""]:
                pars = [_fmt_par(p.group("par"))]
            if p.group("inc") and incs == [""]:
                incs = [p.group("inc")]
            if p.group("ali") and alis == [""]:
                alis = [re.sub(ASP, "", p.group("ali"))]
        brutos.append({"ini": ini, "ini_art": m.start(), "fim": fim, "arts": _arts(lista),
                       "pars": pars, "incs": incs, "alis": alis})
    return brutos


def _ligacao_direita(t, d, mencoes, por_ini, documento):
    """Norma (menção) ligada logo depois do dispositivo, e o fim da ligação."""
    pos = d["fim"]
    c = RX_CONECTOR.match(t, pos)
    if c:
        g = RX_PARTE_GERAL.match(t, c.end())  # "art. 90 da parte geral da RCVM 175"
        if g and g.end() in por_ini:
            alvo = por_ini[g.end()]
            return dict(alvo, parte=""), alvo["fim"]
    if c and c.end() in por_ini:
        alvo = por_ini[c.end()]
        return alvo, alvo["fim"]
    an = ANAFORA.match(t, pos)
    if an and (c or (an.group("pre") or "").lower().startswith(("dest", "dess", "nest", "ness"))):
        alvo = _anafora(an, mencoes, d["ini"], documento)
        if alvo:
            return alvo, an.end()
    return None, pos


def _ligacao_esquerda(t, d, mencoes):
    antes = [m for m in mencoes if m["fim"] <= d["ini"]]
    if not antes:
        return None
    ultima = max(antes, key=lambda m: (m["fim"], -m["ini"]))
    gap = t[ultima["fim"]:d["ini"]]
    if GAP_ESQUERDA.match(gap):
        return ultima
    if RX_SEU.search(t[max(0, d["ini"] - 30):d["ini"]]) and d["ini"] - ultima["fim"] <= 400:
        parte_geral = re.search(_i(r"parte\s+geral"), gap)
        return dict(ultima, parte="") if parte_geral else ultima
    return None


def _trecho(t, ini, fim):
    if fim - ini >= TRECHO_MAX:
        corte = t.rfind(" ", ini, ini + TRECHO_MAX + 1)
        return t[ini:corte if corte > ini else ini + TRECHO_MAX].rstrip()
    folga = TRECHO_MAX - (fim - ini)
    a = max(0, ini - folga // 3)
    b = min(len(t), fim + folga - (ini - a))
    if a > 0:
        esp = t.find(" ", a, ini)
        a = esp + 1 if esp != -1 else a
    if b < len(t):
        esp = t.rfind(" ", fim, b)
        b = esp if esp != -1 else b
    return t[a:b].strip()


def extrair_citacoes(texto, ids=None, documento=None):
    if ids is None:
        ids = carregar_ids()
    t, mapa = _normalizar(texto)
    mencoes = _resolver_anexos(t, _ajustar_ano(_mencoes(t), ids))
    por_ini = {}
    for m in mencoes:  # a menção mais longa que começa na posição (anexo com a norma)
        if m["ini"] not in por_ini or m["fim"] > por_ini[m["ini"]]["fim"]:
            por_ini[m["ini"]] = m
    brutos = _dispositivos_brutos(t)
    ligados = [None] * len(brutos)
    fins = [d["fim"] for d in brutos]
    for k, d in enumerate(brutos):
        ligados[k], fins[k] = _ligacao_direita(t, d, mencoes, por_ini, documento)
    for k in range(len(brutos) - 2, -1, -1):  # cadeia: "art. 33, ..., e no art. 34, ..., da Res."
        if ligados[k] is None and ligados[k + 1] is not None and \
                GAP_CADEIA.match(t[brutos[k]["fim"]:brutos[k + 1]["ini"]]):
            ligados[k] = ligados[k + 1]
    for k, d in enumerate(brutos):
        if ligados[k] is None:
            ligados[k] = _ligacao_esquerda(t, d, mencoes)
    saida = []
    for d, alvo, fim in zip(brutos, ligados, fins):
        if alvo is None or alvo.get("impossivel"):
            continue
        rot = alvo["rotulo"]
        trecho = _trecho(t, d["ini"], max(fim, d["fim"]))
        for k, art in enumerate(d["arts"]):
            ultimo = k == len(d["arts"]) - 1
            for par in (d["pars"] if ultimo else [""]):
                for inc in (d["incs"] if ultimo else [""]):
                    for ali in (d["alis"] if ultimo else [""]):
                        saida.append({"norma": _norma(rot, ids), "rotulo": rot, "parte": alvo["parte"],
                                      "artigo": art, "paragrafo": par, "inciso": inc, "alinea": ali,
                                      "trecho": trecho, "posicao": mapa[d["ini"]] if mapa else 0})
    saida += _mesmo_artigo(t, mapa, saida)
    saida.sort(key=lambda c: c["posicao"])
    return saida


def _mesmo_artigo(t, mapa, citacoes):
    """'§ 2º do mesmo artigo': repete a norma e o artigo da citação anterior."""
    extra = []
    for m in RX_MESMO_ARTIGO.finditer(t):
        pos = mapa[m.start()]
        antes = [c for c in citacoes if c["posicao"] < pos]
        if not antes:
            continue
        base = antes[-1]
        extra.append(dict(base, paragrafo=_fmt_par(m.group("par")) if m.group("par") else "",
                          inciso=m.group("inc") or "", alinea="", posicao=pos,
                          trecho=_trecho(t, m.start(), m.end())))
    return extra


def normas_mencionadas(texto, ids=None):
    """Normas citadas no texto, com ou sem dispositivo (ids ou fora:), na ordem da 1ª menção."""
    if ids is None:
        ids = carregar_ids()
    t, _mapa = _normalizar(texto)
    return list(dict.fromkeys(_norma(m["rotulo"], ids) for m in _resolver_anexos(t, _ajustar_ano(_mencoes(t), ids))
                              if not m.get("impossivel")))


def dispositivo(c):
    """Citação -> '<norma> [<parte> ]art. N[, § N][, inciso X][, alínea y]'."""
    s = c["norma"] + " " + (c["parte"] + " " if c.get("parte") else "") + "art. " + c["artigo"]
    if c.get("paragrafo"):
        s += ", " + c["paragrafo"]
    if c.get("inciso"):
        s += ", inciso " + c["inciso"]
    if c.get("alinea"):
        s += ", alínea " + c["alinea"]
    return s


def ler_dispositivo(texto):
    """'cvm-res-175 Anexo II art. 2º, inciso XII' -> {norma, parte, artigo, paragrafo, inciso,
    alinea} (vazios como ''), ou None fora do formato."""
    m = DISPOSITIVO_RE.match(texto)
    if not m:
        return None
    return {k: v or "" for k, v in m.groupdict().items()}


def formatar_normas_citadas(citacoes, mencionadas=()):
    return "; ".join(dict.fromkeys([c["norma"] for c in citacoes] + list(mencionadas)))


def formatar_dispositivos_citados(citacoes):
    return "; ".join(dict.fromkeys(dispositivo(c) for c in citacoes))


def main(argv):
    if len(argv) not in (2, 4) or (len(argv) == 4 and argv[2] != "--documento"):
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        texto = f.read()
    for c in extrair_citacoes(texto, documento=argv[3] if len(argv) == 4 else None):
        print("%s\t%s" % (dispositivo(c), c["trecho"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
