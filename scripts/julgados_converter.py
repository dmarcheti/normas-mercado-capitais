"""Converte as fontes baixadas dos julgados (cache de julgados_baixar.py) em Markdown com o
frontmatter do contrato, no caminho de `julgados_comum.caminho_julgado`.

- Colegiado (e TC com item do Colegiado): HTML do <article> por html_bcb.html_para_md, em
  `## Decisão`; anexos em seções próprias (anexo alheio fica fora); termos em
  `## Termo de compromisso`.
- PAS: PDF pelo PDFKit; página com menos de 20 caracteres vai para OCR (Vision). Seções pelos
  cabeçalhos da peça (Extrato, Relatório, Voto, Declaração de voto, Manifestação da área
  técnica); sem cabeçalho reconhecível, `## Texto`.
- TC sem item do Colegiado: o termo (PDF ou extrato do SEI, ISO-8859-1, tabela vira bloco).
- Decisões antigas: um arquivo por ano, `## ATA ...` por reunião e `### ` por decisão
  (segmentação por heurística, anotada em `incerteza`).
- Linhas repetidas em 3 ou mais páginas saem (cabeçalho e rodapé); todo o texto passa por
  pii.limpar. Resultado só por regex segura; tema fica vazio; citações por citacoes.py
  (sem o módulo, ficam vazias).
- Cobertura: conferência independente (html.parser; pypdf para PDF, se instalado) da fração
  das palavras da fonte presentes na saída; um relatório JSON por lote em
  dados/fase-2d/relatorios/.

Uso:
  python3 scripts/julgados_converter.py --ids cvm-pas-rj2015-1234,cvm-col-20251202-d3228
  python3 scripts/julgados_converter.py --onda 1 --tipo pas --limite 20
"""
import argparse
import datetime
import json
import os
import re
import sys
from html import unescape
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import html_bcb  # noqa: E402
import julgados_baixar as jb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import pdf_macos  # noqa: E402
import pii  # noqa: E402
from inventario import _data_cvm  # noqa: E402

RELATORIOS = os.path.join(jc.RAIZ, "dados", "fase-2d", "relatorios")
MIN_CARACTERES_PAGINA = 20
MIN_PAGINAS_REPETIDA = 3
COBERTURA_BAIXA = 0.9

# ---------------------------------------------------------------- PDF


def _pypdf_paginas(caminho):
    """Páginas pelo pypdf, ou None sem o módulo (Python da CLT, por exemplo)."""
    try:
        import pypdf
    except ImportError:
        return None
    leitor = pypdf.PdfReader(caminho)
    return [(p.extract_text() or "") for p in leitor.pages]


def texto_pdf(caminho, pm=pdf_macos):
    """(páginas, nível, motor, avisos, nº de páginas por OCR). PDFKit primeiro (pypdf fora do
    macOS); páginas com menos de 20 caracteres passam pelo OCR do Vision."""
    avisos = []
    try:
        paginas, motor = pm.texto_pdfkit(caminho).split("\f"), "pdfkit"
    except pm.ErroPdfMacos:
        paginas, motor = _pypdf_paginas(caminho), "pypdf"
        if paginas is None:
            raise
    if paginas and not paginas[-1].strip() and len(paginas) > 1:
        paginas = paginas[:-1]
    paginas = [jc.normalizar_pdf(p) for p in paginas]
    vazias = [i for i, p in enumerate(paginas) if len(p.strip()) < MIN_CARACTERES_PAGINA]
    nivel, n_ocr = "pdf-extraido", 0
    if vazias:
        try:
            texto, conf = pm.ocr(caminho)
            pags_ocr = texto.split("\f")
            for i in vazias:
                if i < len(pags_ocr) and pags_ocr[i].strip():
                    paginas[i] = jc.normalizar_pdf(pags_ocr[i])
                    n_ocr += 1
            if n_ocr:
                nivel = "ocr"
                confs = [conf[i] for i in vazias if i < len(conf)]
                avisos.append("OCR em %d de %d página(s)%s" % (
                    n_ocr, len(paginas),
                    ", confiança média %.2f" % (sum(confs) / len(confs)) if confs else ""))
        except pm.ErroPdfMacos:
            avisos.append("%d página(s) sem texto e sem OCR (fora do macOS)" % len(vazias))
    return paginas, nivel, motor, avisos, n_ocr


_CABECALHOS = (
    ("Extrato", re.compile(r"EXTRATO D[AE] SESS[ÃA]O DE JULGAMENTO\b.*")),
    ("Relatório", re.compile(r"RELAT[ÓO]RIO|Relat[óo]rio")),
    ("Voto", re.compile(r"VOTO(?: (?:D[OA]|VENCEDOR|VENCIDO|DE DESEMPATE)\b.*)?|Voto")),
    ("Declaração de voto", re.compile(r"(?:DECLARA[ÇC][ÃA]O|MANIFESTA[ÇC][ÃA]O) DE VOTO\b.*|"
                                      r"(?:Declara[çc][ãa]o|Manifesta[çc][ãa]o) de [Vv]oto\b.*")),
    ("Manifestação da área técnica",
     re.compile(r"MANIFESTA[ÇC][ÃA]O D[AE] (?:[ÁA]REA T[ÉE]CNICA|SUPERINTEND[ÊE]NCIA)\b.*")),
)
_CURTOS = {"RELATÓRIO", "RELATORIO", "Relatório", "Relatorio", "VOTO", "Voto"}


def _cabecalho(linha):
    s = linha.strip()
    if len(s) > 90:
        return None
    for nome, rx in _CABECALHOS:
        if rx.fullmatch(s):
            return nome
    return None


def tirar_repetidas(paginas, minimo=MIN_PAGINAS_REPETIDA):
    """Junta as páginas sem as linhas (de 8 caracteres ou mais) que aparecem em `minimo` ou mais
    páginas, com os números trocados por # (cabeçalho e rodapé com número de página).
    Cabeçalho de peça fica. Devolve (texto, nº de linhas retiradas)."""
    def chave(linha):
        return re.sub(r"\d+", "#", re.sub(r"\s+", " ", linha.strip()))

    contagem = {}
    for p in paginas:
        for k in {chave(x) for x in p.splitlines() if len(x.strip()) >= 8}:
            contagem[k] = contagem.get(k, 0) + 1
    fora = {k for k, n in contagem.items() if n >= minimo}
    saida, retiradas = [], 0
    for p in paginas:
        for linha in p.splitlines():
            if len(linha.strip()) >= 8 and chave(linha) in fora and not _cabecalho(linha):
                retiradas += 1
                continue
            saida.append(linha.rstrip())
        saida.append("")
    return "\n".join(saida), retiradas


def _escapar(linha):
    return "\\" + linha if linha.lstrip().startswith("#") else linha


def _limpar_bloco(linhas):
    txt = "\n".join(_escapar(x) for x in linhas)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def segmentar(texto):
    """[(seção, texto)] pelos cabeçalhos de peça (linha inteira); sem nenhum, [("Texto", ...)].
    O que vem antes do primeiro cabeçalho fica em "Texto"."""
    secoes, atual, linhas = [], "Texto", []
    for linha in texto.splitlines():
        nome = _cabecalho(linha)
        if nome:
            if _limpar_bloco(linhas):
                secoes.append((atual, _limpar_bloco(linhas)))
            atual, linhas = nome, ([] if linha.strip() in _CURTOS else [linha.strip()])
            continue
        linhas.append(linha)
    if _limpar_bloco(linhas):
        secoes.append((atual, _limpar_bloco(linhas)))
    return secoes


# ---------------------------------------------------------------- HTML

_ARTIGO = re.compile(r"<article\b[^>]*contentTextoGeral[^>]*>(.*?)</article>", re.S | re.I)
_VEJA_MAIS = re.compile(r"<div[^>]*class=\"[^\"]*(?:contentVejaMais|bottomPrint)[^\"]*\".*",
                        re.S | re.I)
_TITULO_COL = re.compile(r"<p[^>]*class=\"[^\"]*text-uppercase[^\"]*\"[^>]*>(.*?)</p>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")


def _txt(html):
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", html or ""))).strip()


def artigo(html):
    m = _ARTIGO.search(html)
    return m.group(1) if m else html


class _Texto(HTMLParser):
    """Texto visível, para a conferência independente (sem script e style)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes, self._pular = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._pular += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._pular:
            self._pular -= 1

    def handle_data(self, data):
        if not self._pular:
            self.partes.append(data)


def texto_html_independente(html):
    p = _Texto()
    p.feed(html)
    return " ".join(p.partes)


def colegiado_da_pagina(html):
    """(título, data, relator, markdown da decisão) da página do item do Colegiado."""
    corpo = artigo(html)
    m = re.search(r"<h2[^>]*>(.*?)</h2>", corpo, re.S | re.I)
    data = jc.data_br(_txt(m.group(1))) if m else None
    t = _TITULO_COL.search(corpo)
    titulo = _txt(t.group(1)) if t else ""
    rel = re.search(r"Relator[a]?:\s*([^<\n(]+)", corpo)
    relator = _txt(rel.group(1)).rstrip(" .") if rel else ""
    miolo = _VEJA_MAIS.sub("", corpo)
    miolo = re.sub(r"<h2[^>]*>.*?</h2>", "", miolo, flags=re.S | re.I)
    if t:
        miolo = miolo.replace(t.group(0), "")
    return titulo, data, relator, html_bcb.html_para_md(miolo).strip()


def pas_da_pagina(html):
    """(título, data, ementa) da página do PAS."""
    corpo = artigo(html)
    m = re.search(r"<h2[^>]*>(.*?)</h2>", corpo, re.S | re.I)
    titulo = _txt(m.group(1)) if m else ""
    d = re.search(r"Data da Sess[ãa]o de julgamento</b>(.*?)</p>", corpo, re.S | re.I)
    data = _data_cvm(_txt(d.group(1))) if d else None
    e = re.search(r"<b>\s*Ementa\s*</b>(.*?)(?:<div|</section)", corpo, re.S | re.I)
    ementa = _txt(e.group(1)) if e else ""
    return titulo, data, ementa


def sei_para_md(html):
    """Extrato do SEI (ISO-8859-1): sem imagens; tabela, linha e célula viram bloco."""
    html = re.sub(r"<img\b[^>]*>", "", html, flags=re.I)
    html = re.sub(r"<(/?)(?:table|tbody|thead|tr|td|th)\b[^>]*>", r"<\1div>", html, flags=re.I)
    m = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
    return html_bcb.html_para_md(m.group(1) if m else html).strip()


# ---------------------------------------------------------------- metadados


def relator_do_texto(texto):
    m = re.search(r"(?m)^\s*(?:Diretora?\s+)?Relatora?(?: do [Vv]oto [Vv]encedor)?\s*:\s*(.+?)\s*$",
                  texto)
    if not m:
        return ""
    r = re.sub(r"^(?:Diretora?|Presidente)\s+", "", m.group(1)).strip(" .")
    return r if len(r) <= 80 else ""


def rito_do_texto(texto):
    achados = set()
    if re.search(r"rito\s+simplificado", texto, re.I):
        achados.add("simplificado")
    if re.search(r"rito\s+ordin[áa]rio", texto, re.I):
        achados.add("ordinario")
    return achados.pop() if len(achados) == 1 else ""


def _um(familias, texto):
    achados = [nome for nome, rx in familias if re.search(rx, texto, re.I)]
    return achados[0] if len(achados) == 1 else ""


_RES_TC = (("aceito", r"deliberou\s+(?:por\s+)?aceitar\b"),
           ("rejeitado", r"deliberou\s+(?:por\s+)?rejeitar\b"))
_RES_COL = (("provido", r"\bdeu\s+provimento\b|\bdar\s+provimento\b"),
            ("nao-provido", r"\bneg(?:ou|ar)\s+provimento\b"),
            ("parcial", r"\bprovimento\s+parcial\b|\bparcial\s+provimento\b"),
            ("deferido", r"\bdeferiu\b|\bdeferir\s+o\s+pedido\b"),
            ("indeferido", r"\bindeferiu\b|\bindeferir\s+o\s+pedido\b"))
_RES_PAS = (("absolvicao", r"\babsolv"),
            ("condenacao", r"\bcondena|\bmulta\b|\badvert[êe]ncia\b|\binabilita"),
            ("extincao", r"extin[çc][ãa]o\s+da\s+punibilidade"))


def resultado(tipo, texto, item):
    """Só por regex segura: um padrão e um só. Na dúvida, vazio."""
    if tipo == "termo-compromisso":
        return item.get("resultado") or _um(_RES_TC, texto)
    if tipo == "decisao-colegiado":
        return _um(_RES_COL, texto)
    if tipo == "pas":
        m = re.search(r"EXTRATO D[AE] SESS[ÃA]O.*?(?=\n##|\Z)", texto, re.S)
        return _um(_RES_PAS, m.group(0)) if m else ""
    return ""


_CITACOES = {}


def citacoes(texto):
    """(normas_citadas, dispositivos_citados, aviso) por citacoes.py; sem o módulo, vazios."""
    try:
        import citacoes as cit
        if "ids" not in _CITACOES:
            _CITACOES["ids"] = cit.carregar_ids()
        ids = _CITACOES["ids"]
        lista = cit.extrair_citacoes(texto, ids)
        normas = cit.formatar_normas_citadas(lista, cit.normas_mencionadas(texto, ids))
        return normas, cit.formatar_dispositivos_citados(lista), ""
    except Exception as e:  # noqa: BLE001 — módulo ausente ou em obras: campos vazios
        return "", "", "citações não extraídas (%s)" % type(e).__name__


# ---------------------------------------------------------------- cobertura


def _palavras(texto):
    return set(re.findall(r"[a-zà-ÿ0-9]{4,}", (texto or "").lower()))


def cobertura(referencia, saida):
    ref = _palavras(referencia)
    if not ref:
        return None
    return round(len(ref & _palavras(saida)) / len(ref), 4)


def conferir(arq, caminho, motor, saida):
    """Cobertura de um arquivo da fonte por extrator independente do usado na conversão."""
    if caminho.lower().endswith(".pdf"):
        if motor == "pypdf":
            return {"arquivo": arq, "cobertura": None, "conferencia": "sem conferência independente"}
        try:
            pags = _pypdf_paginas(caminho)
        except Exception as e:  # noqa: BLE001 — PDF que o pypdf não lê
            return {"arquivo": arq, "cobertura": None, "conferencia": "pypdf falhou (%s)" %
                    type(e).__name__}
        if pags is None:
            return {"arquivo": arq, "cobertura": None, "conferencia": "sem conferência independente"}
        return {"arquivo": arq, "cobertura": cobertura(" ".join(pags), saida),
                "conferencia": "pypdf"}
    with open(caminho, "rb") as f:
        html = jc.decodificar(f.read())
    return {"arquivo": arq, "cobertura": cobertura(texto_html_independente(artigo(html)), saida),
            "conferencia": "html.parser"}


# ---------------------------------------------------------------- conversão


_NIVEL_ORDEM = {"html-convertido": 0, "pdf-extraido": 1, "ocr": 2}

_SECAO_ANEXO = (("Parecer do Comitê de Termo de Compromisso", r"PARECER DO COMIT"),
                ("Declaração de voto", r"(?:DECLARA[ÇC][ÃA]O|MANIFESTA[ÇC][ÃA]O) DE VOTO"),
                ("Voto", r"^\s*VOTO\b"),
                ("Relatório", r"^\s*RELAT[ÓO]RIO\b"),
                ("Manifestação da área técnica", r"MANIFESTA[ÇC][ÃA]O D[AE] [ÁA]REA|"
                                                 r"MEMORANDO|PARECER (?:DA|DO) (?:SEP|SIN|SMI|SRE|"
                                                 r"SNC|SSE|SPS|SOI|SDM|SMI|SGE)"),
                ("Termo de compromisso", r"TERMO DE COMPROMISSO"),
                ("Extrato", r"EXTRATO"))


def secao_do_anexo(rotulo):
    for nome, rx in _SECAO_ANEXO:
        if re.search(rx, rotulo or "", re.I):
            return nome
    return "Texto"


class Conversao:
    """Acumula seções, nível, avisos e conferência de um julgado."""

    def __init__(self, pasta, pm):
        self.pasta, self.pm = pasta, pm
        self.secoes, self.avisos, self.conferencias = [], [], []
        self.nivel, self.paginas_ocr, self.linhas_repetidas = "html-convertido", 0, 0
        self._fontes = []  # (arquivo, caminho, motor)
        self.brutos = []  # texto dos PDFs antes de tirar as repetidas (relator, data)

    def _subir(self, nivel):
        if _NIVEL_ORDEM[nivel] > _NIVEL_ORDEM[self.nivel]:
            self.nivel = nivel

    def caminho(self, arq):
        return os.path.join(self.pasta, arq["arquivo"])

    def pdf(self, arq, limpar_repetidas=True):
        paginas, nivel, motor, avisos, n_ocr = texto_pdf(self.caminho(arq), self.pm)
        self._subir(nivel)
        self.paginas_ocr += n_ocr
        self.avisos += ["%s: %s" % (arq["arquivo"], a) for a in avisos]
        self._fontes.append((arq["arquivo"], self.caminho(arq), motor))
        self.brutos.append("\n".join(paginas))
        if limpar_repetidas:
            texto, n = tirar_repetidas(paginas)
            self.linhas_repetidas += n
            return texto
        return "\n".join(paginas)

    def html(self, arq):
        with open(self.caminho(arq), "rb") as f:
            dados = f.read()
        self._fontes.append((arq["arquivo"], self.caminho(arq), "html"))
        return jc.decodificar(dados, {"content-type": arq.get("content_type", "")})

    def documento(self, arq, secao_padrao):
        """Seções de um arquivo anexo: PDF segmentado (sem cabeçalho, `secao_padrao`), extrato
        do SEI ou página HTML."""
        if arq["arquivo"].lower().endswith(".pdf"):
            segs = segmentar(self.pdf(arq))
            return [(secao_padrao if s == "Texto" else s, t) for s, t in segs]
        html = self.html(arq)
        md = sei_para_md(html) if "sei.cvm.gov.br" in arq["url"] or arq["papel"] in (
            "termo", "sei") else html_bcb.html_para_md(artigo(html)).strip()
        return [(secao_padrao, md)] if md else []

    def conferir(self, saida):
        self.conferencias = [conferir(a, c, m, saida) for a, c, m in self._fontes]


def _arquivos(reg, *papeis):
    return [a for a in reg["arquivos"] if a["papel"] in papeis]


def _montar_corpo(titulo, secoes, nivel_secao="##"):
    partes = ["# " + (titulo or "Sem título")]
    for nome, texto in secoes:
        partes.append("%s %s\n\n%s" % (nivel_secao, nome, texto) if texto else
                      "%s %s" % (nivel_secao, nome))
    return "\n\n".join(partes).strip() + "\n"


_ATA = re.compile(r"ATA DA REUNI[ÃA]O(?: [A-ZÇÃÁÉÍÓÚÊÔ]+)? DO COLEGIADO(?: N[º°o]\.?\s*\d+)?"
                  r" DE (\d{1,2})\.(\d{1,2})\.(\d{2,4})")
_PARTICIPANTE = re.compile(r"^[A-ZÀ-Ý][A-ZÀ-Ý .'\-]+\s+[–-]\s+(?:Presidente|Diretora?|"
                           r"Superintendente|Procurador)", re.I)


def _ano4(a):
    a = int(a)
    return a + (1900 if a >= 50 else 2000) if a < 100 else a


def _caixa_alta(linha):
    letras = re.sub(r"[^A-Za-zÀ-ÿ]", "", linha)
    return len(letras) >= 12 and letras.upper() == letras


def decisoes_antigas(texto):
    """[(cabeçalho da ATA, data, [(título da decisão, texto)])] do PDF anual. Antes da primeira
    ATA (endereço, lista de datas) sai. Decisão = título em caixa alta depois dos participantes."""
    atas = list(_ATA.finditer(texto))
    out = []
    for i, m in enumerate(atas):
        fim = atas[i + 1].start() if i + 1 < len(atas) else len(texto)
        data = "%04d-%02d-%02d" % (_ano4(m.group(3)), int(m.group(2)), int(m.group(1)))
        linhas = texto[m.end():fim].splitlines()
        decisoes, titulo, corpo, abertura = [], None, [], []
        participantes = True
        for linha in linhas:
            s = linha.strip()
            if participantes and (not s or s.upper().startswith("PARTICIPANTES")
                                  or _PARTICIPANTE.match(s)):
                abertura.append(s)
                continue
            participantes = False
            if s and _caixa_alta(s) and not _PARTICIPANTE.match(s) and (titulo is None or corpo):
                if titulo is not None:
                    decisoes.append((titulo, _limpar_bloco(corpo)))
                titulo, corpo = s, []
                continue
            if s and _caixa_alta(s) and titulo is not None and not corpo:
                titulo += " " + s  # título em mais de uma linha
                continue
            if titulo is None:
                abertura.append(s)
            else:
                corpo.append(linha)
        if titulo is not None:
            decisoes.append((titulo, _limpar_bloco(corpo)))
        out.append((m.group(0), data, _limpar_bloco(abertura), decisoes))
    return out


def converter_item(item, pasta, pm=pdf_macos):
    """(valores do frontmatter, corpo, Conversao) de um julgado já baixado em `pasta`."""
    reg = jb.ler_registro(pasta)
    if not reg or not reg.get("arquivos"):
        raise ValueError("%s: fonte não baixada" % item["id"])
    cv = Conversao(pasta, pm)
    tipo = item["tipo"]
    principal = reg["arquivos"][0]
    incerteza = list(item.get("incerteza", []))
    titulo, data, relator, ementa, fonte_ementa = "", item.get("data"), item.get("relator", ""), \
        "", "titulo"
    secoes, rito = [], item.get("rito", "")

    if tipo == "pas":
        if principal["papel"] == "pagina":
            titulo, d, ementa_pag = pas_da_pagina(cv.html(principal))
            data = d or data
        else:
            ementa_pag = ""
        pdfs = _arquivos(reg, "pdf", "documento")
        for arq in pdfs:
            secoes += segmentar(cv.pdf(arq))
        texto = "\n".join(t for _, t in secoes)
        bruto = "\n".join(cv.brutos)
        if not relator:
            relator = relator_do_texto(bruto)
        if not data:
            m = re.search(r"Data do julgamento:\s*(\d{1,2}/\d{1,2}/\d{4})", bruto)
            data = jc.data_br(m.group(1)) if m else None
        if not ementa_pag:
            m = re.search(r"(?m)^\s*Ementa:\s*(.+(?:\n(?!\s*\n).+)*)", texto)
            ementa_pag = m.group(1) if m else ""
        ementa, fonte_ementa = jc.ementa_sem_partes(ementa_pag), "cvm"
        if not ementa:
            ementa, fonte_ementa = jc.ementa_de_titulo(item.get("titulo", "")), "titulo"
        if not pdfs:
            incerteza.append("sem PDF da decisão; corpo só com a ementa da página")
            secoes = [("Texto", ementa_pag)] if ementa_pag else []
        rito = rito or rito_do_texto(bruto)
        fonte = pdfs[0] if pdfs else principal
        titulo = titulo or item.get("processo", "")

    elif tipo == "decisao-antiga":
        texto = cv.pdf(principal, limpar_repetidas=False)
        atas = decisoes_antigas(texto)
        if not atas:
            secoes = segmentar(texto)
            incerteza.append("PDF anual sem ATA reconhecível; texto inteiro")
            corpo_md = _montar_corpo(item.get("titulo"), secoes)
        else:
            partes = ["# " + item.get("titulo", "")]
            for cab, _d, abertura, decs in atas:
                partes.append("## " + cab + ("\n\n" + abertura if abertura else ""))
                for t, c in decs:
                    partes.append("### %s\n\n%s" % (t, c) if c else "### " + t)
            corpo_md = "\n\n".join(partes).strip() + "\n"
            data = min(d for _, d, _, _ in atas)
            incerteza.append("decisões separadas por heurística (título em caixa alta), %d ATA(s) "
                             "e %d decisão(ões); data da primeira reunião do arquivo"
                             % (len(atas), sum(len(x[3]) for x in atas)))
        titulo = item.get("titulo", "")
        ementa = jc.ementa_de_titulo(titulo)
        fonte = principal

    elif principal["papel"] == "pagina":  # Colegiado e TC com item do Colegiado
        titulo, d, rel, md = colegiado_da_pagina(cv.html(principal))
        data, relator = d or data, rel or relator
        secoes = [("Decisão", md)] if md else []
        for arq in _arquivos(reg, "anexo"):
            if jc.anexo_alheio(arq.get("rotulo")):
                continue
            nome = secao_do_anexo(arq.get("rotulo"))
            for s, t in cv.documento(arq, nome):
                if s == "Texto" and arq.get("rotulo"):
                    t = "**%s**\n\n%s" % (arq["rotulo"], t)
                secoes.append((s, t))
        for arq in _arquivos(reg, "termo"):
            secoes += cv.documento(arq, "Termo de compromisso")
        titulo = titulo or item.get("titulo", "")
        ementa = jc.ementa_de_titulo(titulo, item.get("classe") or None)
        fonte = principal

    else:  # TC sem item do Colegiado: termo em PDF ou extrato do SEI
        for arq in _arquivos(reg, "documento", "sei", "termo"):
            secoes += cv.documento(arq, "Termo de compromisso")
        titulo = "Termo de compromisso – %s" % item.get("processo", "")
        incerteza.append("título montado (tabela de termos de compromisso)")
        ementa = "Termo de compromisso. Proc. %s." % item.get("processo", "")
        fonte = principal

    if tipo != "decisao-antiga":
        corpo_md = _montar_corpo(titulo, secoes)
    corpo_md, cortes = pii.limpar_contando(corpo_md)
    if not re.search(r"(?m)^## ", corpo_md):
        corpo_md = corpo_md.rstrip("\n") + "\n\n## Texto\n"
        incerteza.append("fonte sem texto extraível")
    cv.pii = cortes
    if cv.linhas_repetidas:
        cv.avisos.append("%d linha(s) de cabeçalho/rodapé retiradas" % cv.linhas_repetidas)

    normas, disp, aviso = citacoes(corpo_md)
    if aviso:
        cv.avisos.append(aviso)
    if tipo == "decisao-colegiado" or tipo == "termo-compromisso" or tipo == "pas":
        res = resultado(tipo, corpo_md, item)
    else:
        res = ""
    cv.conferir(corpo_md)
    baixas = [c for c in cv.conferencias if c["cobertura"] is not None
              and c["cobertura"] < COBERTURA_BAIXA]
    if baixas:
        incerteza.append("cobertura abaixo de %d%% na conferência independente"
                         % int(COBERTURA_BAIXA * 100))
    if cv.paginas_ocr:
        incerteza.append("%d página(s) por OCR" % cv.paginas_ocr)
    if not data:
        raise ValueError("%s: sem data (página, inventário e PDF)" % item["id"])
    valores = {
        "id": item["id"], "orgao": "cvm", "tipo": tipo, "classe": item.get("classe", ""),
        "processo": item.get("processo", ""), "nup": item.get("nup", ""), "rito": rito,
        "data": data, "relator": pii.limpar(relator), "resultado": res,
        "ementa": pii.limpar(ementa), "ementa_fonte": fonte_ementa if ementa else "",
        "tema": "", "tema_fonte": "", "normas_citadas": normas, "dispositivos_citados": disp,
        "fonte_original": fonte["url"], "sha256_fonte": fonte["sha256"],
        "baixado_em": fonte["baixado_em"], "nivel_verificacao": cv.nivel,
        "incerteza": "; ".join(dict.fromkeys(x for x in incerteza if x)),
    }
    return valores, corpo_md, cv


def gravar_julgado(valores, corpo, raiz=jc.RAIZ):
    caminho = jc.caminho_julgado(valores["tipo"], valores["id"], valores["data"][:4], raiz)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(jc.frontmatter(valores) + corpo)
    os.replace(tmp, caminho)
    return caminho


def main(argv=None, pm=pdf_macos):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="ids separados por vírgula")
    ap.add_argument("--ano", type=int)
    ap.add_argument("--tipo", choices=jc.TIPOS)
    ap.add_argument("--onda", type=int, choices=sorted(jc.ONDAS))
    ap.add_argument("--limite", type=int)
    ap.add_argument("--inventario", default=jb.INVENTARIO)
    ap.add_argument("--cache", default=jb.CACHE)
    ap.add_argument("--raiz", default=jc.RAIZ, help="raiz do repositório (saída em plugins/)")
    ap.add_argument("--relatorios", default=RELATORIOS)
    a = ap.parse_args(argv)
    ids = [x.strip() for x in a.ids.split(",") if x.strip()] if a.ids else None
    itens = jc.selecionar(jb.carregar_inventario(a.inventario), ids=ids, ano=a.ano, tipo=a.tipo,
                          onda=a.onda, limite=a.limite)
    relatorio = {"gerado_em": jc.hoje_sp(), "argumentos": vars(a), "itens": []}
    falhas = 0
    for it in itens:
        pasta = jb.pasta_do_item(it, a.cache)
        linha = {"id": it["id"], "tipo": it["tipo"]}
        try:
            valores, corpo, cv = converter_item(it, pasta, pm)
            caminho = gravar_julgado(valores, corpo, a.raiz)
            linha.update({"caminho": os.path.relpath(caminho, a.raiz), "bytes": len(corpo.encode()),
                          "nivel": cv.nivel, "paginas_ocr": cv.paginas_ocr,
                          "secoes": re.findall(r"(?m)^## (.+)$", corpo), "pii": cv.pii,
                          "cobertura": cv.conferencias, "avisos": cv.avisos,
                          "resultado": valores["resultado"], "incerteza": valores["incerteza"]})
            print("%s -> %s (%s)" % (it["id"], linha["caminho"], cv.nivel))
        except Exception as e:  # noqa: BLE001 — um julgado ruim não para o lote
            falhas += 1
            linha["erro"] = "%s: %s" % (type(e).__name__, str(e)[:300])
            print("%s: ERRO %s" % (it["id"], linha["erro"]), file=sys.stderr)
        relatorio["itens"].append(linha)
    os.makedirs(a.relatorios, exist_ok=True)
    nome = "conversao-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(a.relatorios, nome), "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("%d convertido(s), %d erro(s); relatório %s" % (len(itens) - falhas, falhas,
                                                         os.path.join(a.relatorios, nome)))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
