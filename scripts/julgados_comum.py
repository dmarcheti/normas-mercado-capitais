#!/usr/bin/env python3
"""Peças comuns dos julgados da CVM (Fase 2d, contrato da SPEC v0.5.0).

- plugin_do_julgado(tipo, ano): o plugin de cada julgado; única fonte do corte por período.
- processos(texto) / normalizar_processo(texto) / nup(texto): números de processo normalizados
  (NUP `19957.011607/2024-20` -> `19957-011607-2024-20`; `RJ2015/1234`, `RJ-2015-1234`,
  `PAS CVM nº RJ2015/1234` -> `rj2015-1234`; `SP97/00250` -> `sp1997-0250`; `22/1996` ->
  `22-1996`); processo_publicado(texto): só os números, como publicados, sem nome de parte.
- id_pas, id_colegiado, id_tc_avulso, id_decisao_antiga e caminho_julgado: ids e caminhos.
- frontmatter(valores): o bloco YAML na ordem do contrato, um valor por linha.
- ementa_de_titulo(titulo, classe): ementa montada do título "TIPO – PARTE – PROC. nº", sem as
  partes (ementa_fonte `titulo`).
- ementa_sem_partes(ementa): tira a lista de acusados que abre as ementas antigas dos PAS.
- anexo_alheio(rotulo): convênio, termo aditivo e acordo de cooperação ficam fora do julgado.
- selecionar(itens, ...): seleção comum a julgados_baixar e julgados_converter.
"""
import datetime
import os
import re
import unicodedata

import controle

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
USER_AGENT = "Mozilla/5.0"
BASE = "https://conteudo.cvm.gov.br"

TIPOS = ("pas", "termo-compromisso", "decisao-colegiado", "decisao-antiga", "acordao-crsfn")
CLASSES = ("recurso", "consulta", "dispensa", "registro", "normativo", "reconsideracao",
           "incidente-pas", "multa-cominatoria", "institucional", "outros")
RESULTADOS = {
    "pas": ("condenacao", "absolvicao", "parcial", "extincao", "arquivamento", "outro"),
    "acordao-crsfn": ("condenacao", "absolvicao", "parcial", "extincao", "arquivamento", "outro"),
    "termo-compromisso": ("aceito", "rejeitado", "outro"),
    "decisao-colegiado": ("deferido", "indeferido", "provido", "nao-provido", "parcial",
                          "conhecimento", "outro"),
    "decisao-antiga": ("deferido", "indeferido", "provido", "nao-provido", "parcial",
                       "conhecimento", "outro"),
}
EMENTA_FONTES = ("cvm", "crsfn", "extracao", "titulo")
NIVEIS = ("html-convertido", "pdf-extraido", "ocr")
CAMPOS = ("id", "orgao", "tipo", "classe", "processo", "nup", "rito", "data", "relator",
          "resultado", "ementa", "ementa_fonte", "tema", "tema_fonte", "normas_citadas",
          "dispositivos_citados", "fonte_original", "sha256_fonte", "baixado_em",
          "nivel_verificacao", "incerteza")
PII = "[dado pessoal retirado]"

PLUGIN_PAS = "julgados-pas"
PLUGIN_TC_CRSFN = "julgados-tc-crsfn"
PERIODOS_COLEGIADO = ((None, 2008, "julgados-colegiado-2002-2008"),
                      (2009, 2015, "julgados-colegiado-2009-2015"),
                      (2016, None, "julgados-colegiado-2016-2026"))
PLUGINS_JULGADOS = (PLUGIN_PAS, PLUGIN_TC_CRSFN) + tuple(p[2] for p in PERIODOS_COLEGIADO)
ONDAS = {1: (2019, 2026), 2: (2010, 2018), 3: (None, 2009)}


def plugin_do_julgado(tipo, ano):
    """Plugin do julgado: PAS em julgados-pas; TCs e acórdãos do CRSFN em julgados-tc-crsfn; o
    resto do Colegiado (e as decisões antigas, 1978 a 2001) por período."""
    if tipo not in TIPOS:
        raise ValueError("tipo de julgado desconhecido: %r" % (tipo,))
    if tipo == "pas":
        return PLUGIN_PAS
    if tipo in ("termo-compromisso", "acordao-crsfn"):
        return PLUGIN_TC_CRSFN
    ano = int(ano)
    for ini, fim, nome in PERIODOS_COLEGIADO:
        if (ini is None or ano >= ini) and (fim is None or ano <= fim):
            return nome
    raise AssertionError("período sem plugin: %s" % ano)


# ---------------------------------------------------------------- processos

# NUP: 5 + 6 dígitos / ano - DV, com separadores variáveis ("19957.011607/2024- 20",
# "19957003190/2019-64", "19957.005740_2020_13", "19957011607202420").
_NUP = re.compile(r"(?<![\d])(\d{5})[.\s_]{0,2}(\d{6})\s*[/_.\-]?\s*(\d{4})\s*[-_.]?\s*(\d{1,2})(?!\d)")
# Célula só com "NN/AA" (numeração dos PAS na tabela de TCs antiga: "12/09" = PAS 12/2009).
_CURTO_2 = re.compile(r"^\s*(\d{1,3})\s*/\s*(\d{2})\s*$")
# Antigo: RJ/SP/IA/BSB + ano (2 ou 4 dígitos) + número ("RJ2015/1234", "RJ-2015-1234",
# "RJ 01/08489", "SP97/00250", "IA 2016/5452", "SP2018-15").
_ANTIGO = re.compile(r"(?<![A-Za-z])(RJ|SP|IA|BSB|DF)\s*[-/]?\s*(\d{4}|\d{2})\s*[/-]\s*(\d{1,6})(?!\d)",
                     re.I)
# Numeração curta dos PAS antigos ("Processo Sancionador 22/1996", "PAS 13/2014", "06/2007").
_CURTO = re.compile(r"(?<![0-9A-Za-zÀ-ÿ/.\-])(\d{1,3})\s*/\s*((?:19|20)\d{2})(?![\d/])")


_ANO_MIN = 1976  # criação da CVM


def _ano_atual():
    return datetime.date.today().year


def _ano4(a):
    a = int(a)
    if a >= 100:
        return a
    return 1900 + a if a >= 70 else 2000 + a


def _achados(texto):
    """[(início, fim, normalizado, é_nup)] dos números de processo do texto, em ordem."""
    texto = texto or ""
    out, ocupado = [], []

    def livre(a, b):
        return all(b <= x or a >= y for x, y in ocupado)

    for m in _NUP.finditer(texto):
        out.append((m.start(), m.end(), "%s-%s-%s-%s" % m.groups(), True))
        ocupado.append((m.start(), m.end()))
    for m in _ANTIGO.finditer(texto):
        if livre(m.start(), m.end()):
            norm = "%s%d-%s" % (m.group(1).lower(), _ano4(m.group(2)),
                                str(int(m.group(3))).zfill(4))
            out.append((m.start(), m.end(), norm, False))
            ocupado.append((m.start(), m.end()))
    for m in _CURTO.finditer(texto):
        # "96/2035", "99/1946": protocolo sem prefixo (AA/NNNN), não PAS nº/ano
        if livre(m.start(), m.end()) and _ANO_MIN <= int(m.group(2)) <= _ano_atual():
            out.append((m.start(), m.end(), "%s-%s" % (str(int(m.group(1))).zfill(2), m.group(2)),
                        False))
            ocupado.append((m.start(), m.end()))
    if not out:
        m = _CURTO_2.match(texto)
        if m and int(m.group(1)):
            out.append((m.start(1), m.end(2), "%s-%d" % (str(int(m.group(1))).zfill(2),
                                                          _ano4(m.group(2))), False))
    return sorted(out)


def processos(texto):
    """Números de processo normalizados, na ordem em que aparecem, sem repetição."""
    return list(dict.fromkeys(a[2] for a in _achados(texto)))


def normalizar_processo(texto):
    """O processo principal da célula: o NUP, se houver; senão o primeiro número. "" sem número."""
    ach = _achados(texto)
    for a in ach:
        if a[3]:
            return a[2]
    return ach[0][2] if ach else ""


def nup(texto):
    """NUP normalizado (primeiro da célula) ou "". Dígito verificador truncado na fonte
    ("19957.004598/2020-9") não vira NUP."""
    return next((a[2] for a in _achados(texto) if a[3] and len(a[2]) == 20), "")


def processo_publicado(texto):
    """Os números de processo como publicados (espaços colapsados), separados por "; ", sem o
    resto da célula (nome de parte fica fora)."""
    vistos = []
    for a in _achados(texto):
        bruto = re.sub(r"\s+", "", texto[a[0]:a[1]])
        if bruto not in vistos:
            vistos.append(bruto)
    return "; ".join(vistos)


_PAS_TITULO = re.compile(r"\bPAS\s+(?:CVM\s+)?(?:N[º°o]\.?\s*)?"
                         r"((?:TA)?(?:RJ|SP)\s*\d{4}\s*/\s*\d{1,6}|\d{1,3}\s*/\s*\d{2}(?:\d{2})?)(?![\d/])")


def pas_do_titulo(titulo):
    """Número do PAS como publicado no título do Colegiado ("PAS CVM Nº 27/99", "PAS Nº
    TARJ2001/7557") ou "". Nos TCs de 2004–2006 o número só aparece aí."""
    m = _PAS_TITULO.search(titulo or "")
    return re.sub(r"\s+", "", m.group(1)) if m else ""


# ---------------------------------------------------------------- ids e caminhos

def id_pas(proc):
    return "cvm-pas-" + proc


def slug_colegiado(url):
    """(AAAAMMDD, slug, nº da reunião) da URL de um item do Colegiado:
    /decisoes/2025/20251202_R1/20251202_D3228.html -> ("20251202", "d3228", 1).
    Formas antigas: pasta "20151124_e_25", "20161006_D1", "AAAAMMDDR1"; arquivo "NNNN.html",
    "AAAAMMDD_NNNN.html" ou sem extensão. O slug é o nome do arquivo sem o prefixo da pasta ou
    da data, em minúsculas, com "d" na frente quando começa por dígito."""
    m = re.search(r"/decisoes/(\d{4})/((\d{8})[^/]*)/([^/?#]+?)(?:\.html?)?$", url or "")
    if not m:
        raise ValueError("URL de item do Colegiado fora do padrão: %r" % (url,))
    pasta, data, nome = m.group(2), m.group(3), m.group(4)
    r = re.search(r"R(\d+)$", pasta)
    reuniao = int(r.group(1)) if r else 1
    if nome.startswith(pasta + "_"):
        nome = nome[len(pasta) + 1:]
    else:
        nome = re.sub(r"^\d{8}_?", "", nome)
    slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
    if not slug or slug[0].isdigit():
        slug = "d" + slug
    return data, slug, reuniao


def reparar_url(url):
    """Conserta URL colada em dobro na tabela de TCs ("https://sei.../https://sei.../...0sei/...")."""
    url = (url or "").strip()
    k = url.rfind("http://"), url.rfind("https://")
    k = max(k)
    if k > 0:
        url = url[k:]
    m = re.search(r"(?<=id_orgao_publicacao=\d)(?=\D)", url)
    return url[:m.start()] if m else url


def id_colegiado(url):
    data, slug, _ = slug_colegiado(url)
    return "cvm-col-%s-%s" % (data, slug)


def id_tc_avulso(proc, data):
    """TC sem item do Colegiado: cvm-tc-<proc>-AAAAMMDD."""
    return "cvm-tc-%s-%s" % (proc, (data or "").replace("-", ""))


def id_decisao_antiga(ano, n=None):
    return "cvm-dec-%s" % ano + ("-%03d" % n if n else "")


_PREFIXO_ARQ = {"pas": "cvm-pas-", "termo-compromisso": "cvm-", "decisao-colegiado": "cvm-",
                "decisao-antiga": "cvm-dec-", "acordao-crsfn": "crsfn-"}
_PASTA = {"pas": "cvm/pas/%s", "termo-compromisso": "cvm/colegiado/%s",
          "decisao-colegiado": "cvm/colegiado/%s", "decisao-antiga": "cvm/decisoes-antigas",
          "acordao-crsfn": "crsfn/%s"}


def caminho_relativo(tipo, id_, ano):
    """Caminho sob plugins/: <plugin>/julgados/<pasta>/<id sem prefixo>.md."""
    pref = _PREFIXO_ARQ[tipo]
    if not id_.startswith(pref):
        raise ValueError("id %r não combina com o tipo %s" % (id_, tipo))
    pasta = _PASTA[tipo] % ano if "%s" in _PASTA[tipo] else _PASTA[tipo]
    return os.path.join(plugin_do_julgado(tipo, ano), "julgados", pasta, id_[len(pref):] + ".md")


def caminho_julgado(tipo, id_, ano, raiz=RAIZ):
    return os.path.join(raiz, "plugins", caminho_relativo(tipo, id_, ano))


# ---------------------------------------------------------------- frontmatter

# Caractere de controle que a extração deixa no lugar de um glifo que ela não leu: regra comum
# às normas e aos julgados, em controle.py (o NUL vira "\ufffd"; o STX do SEI vira "-").
_CONTROLE = controle.CONTROLE
sem_controle = controle.sem_controle


def frontmatter(valores):
    """Frontmatter na ordem do contrato; campo ausente fica vazio; campo fora do contrato é erro."""
    extras = set(valores) - set(CAMPOS)
    if extras:
        raise ValueError("campos fora do contrato: %s" % ", ".join(sorted(extras)))
    linhas = ["---"]
    for c in CAMPOS:
        v = valores.get(c)
        v = "" if v is None else re.sub(r"\s+", " ", str(v)).strip()
        linhas.append("%s: %s" % (c, v) if v else "%s:" % c)
    return "\n".join(linhas + ["---", ""]) + "\n"


# ---------------------------------------------------------------- ementas

ACRONIMOS = {
    "CVM", "SEP", "SNC", "SGE", "SRE", "SIN", "SMI", "SMD", "SPS", "SSR", "SSE", "SDM", "SFI",
    "SOI", "SAD", "SEI", "PAS", "OPA", "MRE", "BSM", "PFE", "CRSFN", "CTC", "AGE", "AGO", "AGOE",
    "FIDC", "FIDCS", "FII", "FIP", "CRI", "CRA", "BDR", "BDRS", "ETF", "CPC", "IFRS", "IPO", "B3",
    "ANBIMA", "BM&FBOVESPA", "BOVESPA", "BM&F", "CETIP", "BNDES", "DTVM", "CTVM", "CCTVM", "CVC",
    "SA", "S.A.", "S/A", "LTDA", "LTDA.", "CNPJ", "PJ", "PF", "SPS", "SCP", "DRI", "CEO", "IA",
    "RJ", "SP", "DF", "BSB", "UF", "STF", "STJ", "TCU", "CGU", "AGU", "BCB", "CMN", "SUSEP", "PREVIC",
    "ICVM", "RCVM", "TC", "TCS", "OPAS", "IOSCO", "ANCORD", "APIMEC", "ABRASCA", "IBRACON", "CFC",
    "SELIC", "CDI", "IPCA", "EUA", "SBR", "SSF",
}
_SEP_TITULO = re.compile(r"\s*[–—]\s*|\s+-\s*|\s*-\s+")
_SEGMENTO_PROC = re.compile(r"^(PROCS?\.?|PROCESSOS?|PAS|PA|IA|INQUÉRITO|TERMO DE ACUSAÇÃO|SEI)\b",
                            re.I)


def _caixa_de_frase(txt):
    out = []
    for i, w in enumerate(txt.split()):
        nucleo = w.strip("()[],;:\"“”'")
        up = nucleo.upper()
        if up in ACRONIMOS or (re.fullmatch(r"[IVXL]{2,}", up)) or re.search(r"\d", nucleo):
            out.append(w)
        else:
            out.append(w.lower())
    s = " ".join(out)
    return s[:1].upper() + s[1:] if s else s


def _proc_da_ementa(seg):
    s = re.sub(r"\s+", " ", seg).strip().rstrip(".")
    s = re.sub(r"^PROCS\.?\s*", "Procs. ", s, flags=re.I)
    s = re.sub(r"^PROC\.?\s*", "Proc. ", s, flags=re.I)
    s = re.sub(r"^PROCESSOS?\b", lambda m: m.group(0).capitalize(), s, flags=re.I)
    s = re.sub(r"\bN[º°]\s*", "nº ", s)
    return re.sub(r"\s+E\s+", " e ", s)


def ementa_de_titulo(titulo, classe=None):
    """Ementa do título da CVM no padrão "TIPO – PARTE – PROC. nº": fica o tipo (em caixa de
    frase) e o processo; os segmentos do meio (partes) saem. Na classe `normativo`, os segmentos
    do meio ficam (assunto da norma, não parte)."""
    t = re.sub(r"\s+", " ", titulo or "").strip()
    if not t:
        return ""
    segs = [s for s in _SEP_TITULO.split(t) if s.strip()]
    proc = None
    if len(segs) > 1 and _SEGMENTO_PROC.match(segs[-1].strip()) and processos(segs[-1]):
        proc = segs.pop()
    elif len(segs) > 1:
        # processo colado no último segmento ("... S.A. PROC. RJ2010/1)")
        m = re.search(r"\b(PROCS?\.\s*.+)$", segs[-1], re.I)
        if m and processos(m.group(1)):
            segs[-1] = segs[-1][:m.start()].strip()
            proc = m.group(1)
    principal = segs[0]
    if classe == "normativo" and len(segs) > 1:
        principal = " – ".join(segs)
    frase = _caixa_de_frase(principal).rstrip(" .;,")
    out = frase + "."
    if proc:
        out += " " + _proc_da_ementa(proc) + "."
    return out


_MAIUSC = re.compile(r"[A-ZÀ-Ý]")
_MINUSC = re.compile(r"[a-zß-ÿ]")
_PALAVRAS_LIGACAO = re.compile(r"\b(e|de|da|do|das|dos|outros|outras|em|liquidação)\b")


def _caixa_alta(txt):
    sem = _PALAVRAS_LIGACAO.sub("", txt)
    up, low = len(_MAIUSC.findall(sem)), len(_MINUSC.findall(sem))
    return up >= 3 and up >= 0.85 * (up + low)


def ementa_sem_partes(ementa):
    """Ementa de PAS sem a lista de acusados que abre as ementas antigas ("NÚCLEO DTVM LTDA.,
    FULANO DE TAL e OUTROS - Ocorrência de ..."). Sem prefixo em caixa alta, devolve igual."""
    e = re.sub(r"[ \t]+", " ", ementa or "").strip()
    linhas = [x.strip() for x in e.split("\n") if x.strip()]
    if len(linhas) > 1 and _caixa_alta(linhas[0]) and not _caixa_alta(" ".join(linhas[1:])):
        e = " ".join(linhas[1:])
    else:
        e = " ".join(linhas)
    m = re.match(r"^(.{3,400}?)\s+[-–]\s+(?=\S)", e)
    if m and _caixa_alta(m.group(1)):
        e = e[m.end():]
    e = re.sub(r"^-\s*", "", e).strip()
    return re.sub(r"^Ementa:\s*", "", e).strip()


# ---------------------------------------------------------------- anexos e seleção

_ALHEIO = re.compile(r"^\s*(TERMOS? ADITIVOS?|CONV[ÊE]NIOS?|ACORDOS? DE COOPERA[ÇC][ÃA]O|"
                     r"PROTOCOLOS? DE INTEN[ÇC][ÕO]ES|MEMORANDOS? DE ENTENDIMENTO)\b", re.I)


def anexo_alheio(rotulo):
    """Anexo que não é peça da decisão (convênio, termo aditivo, acordo de cooperação...)."""
    return bool(_ALHEIO.search(rotulo or ""))


def ano_do_item(item):
    d = item.get("data") or ""
    return int(d[:4]) if re.match(r"\d{4}", d) else None


def selecionar(itens, ids=None, ano=None, tipo=None, onda=None, limite=None):
    """Itens do inventário filtrados por ids, ano, tipo e onda (1: 2019-2026; 2: 2010-2018;
    3: até 2009), na ordem do inventário; `limite` corta no fim. Itens sem URL (fonte pendente)
    ficam fora, salvo quando pedidos por id."""
    ids = set(ids or [])
    out = []
    for it in itens:
        if ids and it["id"] not in ids:
            continue
        if not ids and not it.get("url"):
            continue
        a = ano_do_item(it)
        if ano is not None and a != int(ano):
            continue
        if tipo and it["tipo"] != tipo:
            continue
        if onda:
            ini, fim = ONDAS[int(onda)]
            if a is None or (ini is not None and a < ini) or (fim is not None and a > fim):
                continue
        out.append(it)
    return out[:limite] if limite else out


# ---------------------------------------------------------------- utilidades

def hoje_sp():
    """AAAA-MM-DD no fuso de São Paulo."""
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001 — sem base de fusos: UTC-3 (sem horário de verão desde 2019)
        fuso = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(fuso).strftime("%Y-%m-%d")


def data_br(txt):
    """dd/mm/aaaa -> AAAA-MM-DD (ou None)."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", txt or "")
    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else None


def normalizar_pdf(txt):
    """NFKC do texto extraído de PDF (ligaduras, espaço não separável), preservando º e ª."""
    return "".join(p if p in ("º", "ª") else unicodedata.normalize("NFKC", p)
                   for p in re.split("([ºª])", txt or ""))


# ---------------------------------------------------------------- rede

class Cliente:
    """HTTP com User-Agent fixo e no máximo 1 requisição por `intervalo` segundos.

    get/post devolvem (bytes, cabeçalhos em minúsculas, URL final); head devolve os cabeçalhos.
    Os testes trocam o cliente por um falso com a mesma interface."""

    def __init__(self, intervalo=1.0, timeout=90):
        self.intervalo, self.timeout, self._ultimo, self.n = intervalo, timeout, 0.0, 0

    def _esperar(self):
        import time
        falta = self.intervalo - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()
        self.n += 1

    def _abrir(self, url, dados=None, metodo=None):
        import urllib.request
        self._esperar()
        req = urllib.request.Request(absoluta(url), data=dados, method=metodo,
                                     headers={"User-Agent": USER_AGENT})
        if dados is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
        return urllib.request.urlopen(req, timeout=self.timeout)

    def get(self, url):
        with self._abrir(url) as r:
            return r.read(), {k.lower(): v for k, v in r.headers.items()}, r.geturl()

    def post(self, url, campos):
        import urllib.parse
        with self._abrir(url, urllib.parse.urlencode(campos).encode("ascii")) as r:
            return r.read(), {k.lower(): v for k, v in r.headers.items()}, r.geturl()

    def head(self, url):
        with self._abrir(url, metodo="HEAD") as r:
            return {k.lower(): v for k, v in r.headers.items()}


def absoluta(url):
    """URL absoluta: caminho relativo ganha o domínio da CVM."""
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE + url
    return url


def caminho_url(url):
    """Chave de comparação de URL da CVM: caminho sem domínio, sem barra dupla."""
    url = (url or "").strip()
    url = re.sub(r"^https?://(?:www\.)?conteudo\.cvm\.gov\.br", "", url, flags=re.I)
    url = re.sub(r"^https?://(?:www\.)?cvm\.gov\.br", "", url, flags=re.I)
    return re.sub(r"/{2,}", "/", url)


def decodificar(dados, cabecalhos=None):
    """Bytes de uma página em texto: charset do cabeçalho ou do <meta>; senão UTF-8, ISO-8859-1."""
    cs = None
    ct = (cabecalhos or {}).get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ct, re.I) or \
        re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", dados[:4000], re.I)
    if m:
        cs = m.group(1) if isinstance(m.group(1), str) else m.group(1).decode("ascii")
    for c in ([cs] if cs else []) + ["utf-8"]:
        try:
            return dados.decode(c)
        except (LookupError, UnicodeDecodeError):
            pass
    return dados.decode("iso-8859-1")
