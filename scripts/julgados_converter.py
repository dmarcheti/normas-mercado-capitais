"""Converte as fontes baixadas dos julgados (cache de julgados_baixar.py) em Markdown com o
frontmatter do contrato, no caminho de `julgados_comum.caminho_julgado`.

- Colegiado (e TC com item do Colegiado): HTML do <article> por html_bcb.html_para_md, em
  `## Decisão`; anexos em seções próprias (anexo alheio fica fora); termos em
  `## Termo de compromisso`.
- PAS: PDF pelo PDFKit; página com menos de 20 caracteres vai para OCR (Vision). Seções pelos
  cabeçalhos da peça (Extrato, Relatório, Voto, Declaração de voto, Manifestação da área
  técnica); sem cabeçalho reconhecível, `## Texto`.
- PAS fora da listagem (origem `noticia`): `## Extrato` do SEI e as peças dos PDFs da notícia
  (seção pelo cabeçalho ou pelo rótulo do link); ementa (`ementa_fonte: cvm`), data, relator e
  resultado do extrato; `fonte_original` é a URL da notícia.
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
import julgados_extracao as je  # noqa: E402
import pdf_macos  # noqa: E402
import pii  # noqa: E402
from inventario import _data_cvm  # noqa: E402

RELATORIOS = os.path.join(jc.RAIZ, "dados", "fase-2d", "relatorios")
LIGACOES_CRSFN = os.path.join(jc.RAIZ, "dados", "fase-2d", "crsfn-ligacoes.json")
DADOS_ABERTOS_PAS = os.path.join(jc.RAIZ, "dados", "fase-2d", "inventario", "pas",
                                 "processo_sancionador.csv")
_LIGACOES_CRSFN = None  # carregam na 1ª consulta (ou vêm prontas, nos testes)
_FASES_PAS = None
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


def tirar_repetidas(paginas, minimo=MIN_PAGINAS_REPETIDA, retirado=None):
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
                if retirado is not None:
                    retirado.append(linha)
                continue
            saida.append(linha.rstrip())
        saida.append("")
    return "\n".join(saida), retiradas


# Timbre e rodapé da CVM e do SEI, por padrão explícito: valem também nas páginas por OCR e
# nos PDFs curtos, onde a regra da linha repetida não alcança. Saem antes do pii.py (o telefone
# da CVM não é dado pessoal).
_CEP_CVM = r"(?:20050-901|01333-010|70712-900)"
_SEDE_CVM = (r"(?:Rua\s+Sete\s+de\s+Setembro,?\s*111|Rua\s+Cincinato\s+Braga,?\s*340|"
             r"SCN\s*Q\.?\s*0?2\b|Corporate\s+Financial\s+Center)")
_TEL_CVM = r"\(?\b(?:21|11|61)\)?\s*(?:3554|2146|3327)[-.\s]?\d{4}(?:\s*/\s*\d{4})?"
_LINHA_TIMBRE = re.compile(
    r".*%s.*|.*%s.*(?:Andar|CEP|Tel|Brasil).*|" % (_CEP_CVM, _SEDE_CVM)
    + r"(?:(?:Site|Tel\.?|Fax|Telefone|SAC|Ouvidoria)[:.\s]*|www\.cvm\.gov\.br/?|https?://www\.cvm"
      r"\.gov\.br/?|%s|[\s|•–—,;/-])+|" % _TEL_CVM
    + r"SEI/CVM\s*-\s*\d{5,9}\s*-\s.{0,160}|"
      r"https?://sei\.cvm\.gov\.br/sei/controlador\.php\S*|"
      r"\d{1,3}\s+(?:of|de)\s+\d{1,3}\s+\d{2}/\d{2}/\d{4},?\s+\d{1,2}:\d{2}(?::\d{2})?|"
      r".{0,100}\(\d{6,9}\)\s*SEI\s*[\d./\s-]{10,30}/\s*pg\.?\s*\d+|"
      r"COMISS[ÃA]O\s+DE\s+VALORES\s+MOBILI[ÁA]RIOS", re.I)
_FRAGMENTO_TIMBRE = "COMISSÃO DE VALORES MOBILIÁRIOS"
_SPANS_SEI = (
    re.compile(r"Documento\s+assinado\s+eletronicamente\s+por\s.{1,300}?(?:Decreto\s+n\S*\s*8\.539"
               r"(?:,?\s*de\s+8\s+de\s+outubro\s+de\s+2015)?|de\s+8\s+de\s+outubro\s+de\s+2015)\.?",
               re.S | re.I),
    re.compile(r"Documento\s+assinado\s+eletronicamente\s+por\s[^\n]{1,200}?,\s*em\s+\d{1,2}/\d{1,2}/"
               r"\d{4}(?:,?\s+[àa]s\s+\d{1,2}:\d{2})?\.?", re.I),
    re.compile(r"A\s+autenticidade\s+(?:deste|do)\s+documento\s+pode\s+ser\s+conferida.{1,300}?"
               r"c[óo]digo\s+CRC[\s*_\"]{0,10}[0-9A-F]+[*_\"]*\.?[*_]*", re.S | re.I),
    re.compile(r"This\s+document'?s\s+authenticity\s+can\s+be\s+verified.{1,300}?C[óo]digo\s+CRC"
               r"[\s*_\"]{0,10}[0-9A-F]+[*_\"]*\.?[*_]*", re.S | re.I),
    re.compile(r"Refer[êe]ncia:\s*Processo\s+n\S*\s*[\d./-]+\s+SEI\s+n\S*\s*\d+\.?", re.I),
)


def _linha_de_timbre(linha):
    s = re.sub(r"\s+", " ", linha.strip())
    if not s:
        return False
    if len(s) >= 5 and s.upper() == s and s in _FRAGMENTO_TIMBRE and re.search(r"[A-ZÀ-Ý]{3}", s):
        return True  # pedaço do logotipo lido pelo OCR ("VALORES", "MOBILIÁRIOS")
    return bool(_LINHA_TIMBRE.fullmatch(s)) and bool(re.search(r"[A-Za-z0-9]", s))


def tirar_timbre(texto, retirado=None):
    """Texto sem o timbre e o rodapé da CVM e do SEI: endereços das sedes, CEPs, telefones e site
    da CVM; "Documento assinado eletronicamente por ...", "A autenticidade deste documento ...",
    "Referência: Processo nº ... SEI nº ..." (o número SEI citado no meio do texto fica);
    cabeçalho e rodapé da impressão do SEI. Devolve (texto, nº de trechos retirados)."""
    retirado = [] if retirado is None else retirado
    n0 = len(retirado)
    for rx in _SPANS_SEI:
        partes, ini = [], 0
        for m in rx.finditer(texto):
            a, b = m.start(), m.end()
            ls = texto.rfind("\n", 0, a) + 1
            if not texto[ls:a].strip(" \t*_"):
                a = ls
            le = texto.find("\n", b)
            le = len(texto) if le < 0 else le
            if not texto[b:le].strip(" \t*_."):
                b = min(le + 1, len(texto))
            partes.append(texto[ini:a])
            retirado.append(texto[a:b])
            ini = b
        partes.append(texto[ini:])
        texto = "".join(partes)
    linhas = []
    for linha in texto.split("\n"):
        if _linha_de_timbre(linha):
            retirado.append(linha)
        else:
            linhas.append(linha)
    return "\n".join(linhas), len(retirado) - n0


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
        disp = cit.formatar_dispositivos_citados(lista)
    except Exception as e:  # noqa: BLE001 — módulo ausente ou em obras: campos vazios
        return "", "", "citações não extraídas (%s)" % type(e).__name__
    return _sem_fora_sem_numero(normas, disp)


def _sem_fora_sem_numero(normas, disp):
    """Guarda: rótulo `fora:` sempre leva número (fora:lei-9784). Sem número, sai da lista de
    normas e dos dispositivos, com aviso."""
    def ruim(x):
        x = x.strip()
        return x.startswith("fora:") and not re.search(r"\d", x.split("#")[0].split(" ")[0])
    itens_n = [x for x in normas.split(";") if x.strip()] if normas else []
    itens_d = [x for x in disp.split(";") if x.strip()] if disp else []
    tirados = [x.strip() for x in itens_n + itens_d if ruim(x)]
    if not tirados:
        return normas, disp, ""
    n = "; ".join(x.strip() for x in itens_n if not ruim(x))
    d = "; ".join(x.strip() for x in itens_d if not ruim(x))
    return n, d, "rótulo fora: sem número descartado (%s)" % ", ".join(sorted(set(tirados)))


# ---------------------------------------------------------------- cobertura


def _palavras(texto):
    return set(re.findall(r"[a-zà-ÿ0-9]{4,}", (texto or "").lower()))


def _compacto(texto):
    t = re.sub(r"\s+", "", (texto or "").lower())
    return t, t.replace("-", "").replace("­", "")


def medir(referencia, saida, retirado="", antes_pii=""):
    """Cobertura das palavras (4+ letras) da referência na saída. Palavra ausente que é pedaço de
    texto da saída sem espaços conta como coberta (o extrator parte ou cola palavras); a que está
    no timbre/rodapé retirado vai para `retiradas`, e a cortada pelo pii.py para `pii`, fora da
    conta. Devolve {cobertura, palavras, retiradas, pii, faltam (até 20)}."""
    ref = _palavras(referencia)
    if not ref:
        return {"cobertura": None, "palavras": 0, "fragmentos": 0, "retiradas": 0, "pii": 0,
                "faltam": []}
    fora = sorted(ref - _palavras(saida))
    comp = _compacto(saida)
    n_fora = len(fora)
    fora = [w for w in fora if w not in comp[0] and w not in comp[1]]
    fragmentos = n_fora - len(fora)
    ret_p, ret_c = _palavras(retirado), _compacto(retirado)
    retiradas = [w for w in fora if w in ret_p or w in ret_c[0] or w in ret_c[1]]
    fora = [w for w in fora if w not in set(retiradas)]
    pii_p, pii_c = _palavras(antes_pii), _compacto(antes_pii)
    cortadas = [w for w in fora if w in pii_p or w in pii_c[0]]
    fora = [w for w in fora if w not in set(cortadas)]
    base = len(ref) - len(retiradas) - len(cortadas)
    return {"cobertura": round((base - len(fora)) / base, 4) if base else None,
            "palavras": len(ref), "fragmentos": fragmentos, "retiradas": len(retiradas),
            "pii": len(cortadas),
            "faltam": fora[:20]}


def cobertura(referencia, saida):
    return medir(referencia, saida)["cobertura"]


def regiao_html(html, regiao):
    """Trecho da página que o conversor usa: `artigo` (o <article> sem a caixa de anexos),
    `pas` (título, data e ementa da página do PAS) ou `sei` (corpo do extrato, sem imagens)."""
    if regiao == "pas":
        corpo = artigo(html)
        partes = re.findall(r"<h2[^>]*>.*?</h2>", corpo, re.S | re.I)
        d = re.search(r"Data da Sess[ãa]o de julgamento</b>(.*?)</p>", corpo, re.S | re.I)
        e = re.search(r"<b>\s*Ementa\s*</b>(.*?)(?:<div|</section)", corpo, re.S | re.I)
        if d:
            partes.append(_data_cvm(_txt(d.group(1))) or "")
        if e:
            partes.append(e.group(1))
        return " ".join(partes)
    if regiao == "sei":
        m = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
        return re.sub(r"<img\b[^>]*>", "", m.group(1) if m else html, flags=re.I)
    return _VEJA_MAIS.sub("", artigo(html))


def conferir(arq, caminho, motor, saida, regiao="artigo", retirado="", antes_pii=""):
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
        return dict({"arquivo": arq, "conferencia": "pypdf"},
                    **medir(" ".join(pags), saida, retirado, antes_pii))
    with open(caminho, "rb") as f:
        html = jc.decodificar(f.read())
    ref = texto_html_independente(regiao_html(html, regiao))
    return dict({"arquivo": arq, "conferencia": "html.parser"},
                **medir(ref, saida, retirado, antes_pii))


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
        self._fontes = []  # (arquivo, caminho, motor, região do HTML)
        self.brutos = []  # texto dos PDFs antes de tirar as repetidas (relator, data)
        self.retirado = []  # linhas e trechos de timbre e rodapé retirados
        self.trechos_timbre = 0

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
        self._fontes.append((arq["arquivo"], self.caminho(arq), motor, None))
        self.brutos.append("\n".join(paginas))
        if limpar_repetidas:
            texto, n = tirar_repetidas(paginas, retirado=self.retirado)
            self.linhas_repetidas += n
        else:
            texto = "\n".join(paginas)
        return self.timbre(texto)

    def timbre(self, texto):
        texto, n = tirar_timbre(texto, self.retirado)
        self.trechos_timbre += n
        return texto

    def html(self, arq, regiao="artigo"):
        with open(self.caminho(arq), "rb") as f:
            dados = f.read()
        self._fontes.append((arq["arquivo"], self.caminho(arq), "html", regiao))
        return jc.decodificar(dados, {"content-type": arq.get("content_type", "")})

    def documento(self, arq, secao_padrao):
        """Seções de um arquivo anexo: PDF segmentado (sem cabeçalho, `secao_padrao`), extrato
        do SEI ou página HTML."""
        if arq["arquivo"].lower().endswith(".pdf"):
            segs = segmentar(self.pdf(arq))
            return [(secao_padrao if s == "Texto" else s, t) for s, t in segs]
        sei = "sei.cvm.gov.br" in arq["url"] or arq["papel"] in ("termo", "sei")
        html = self.html(arq, "sei" if sei else "artigo")
        md = sei_para_md(html) if sei else html_bcb.html_para_md(artigo(html)).strip()
        md = self.timbre(md).strip()
        return [(secao_padrao, md)] if md else []

    def conferir(self, saida, antes_pii=""):
        ret = "\n".join(self.retirado)
        self.conferencias = [conferir(a, c, m, saida, r or "artigo", ret, antes_pii)
                             for a, c, m, r in self._fontes]


def _arquivos(reg, *papeis):
    return [a for a in reg["arquivos"] if a["papel"] in papeis]


def _montar_corpo(titulo, secoes, nivel_secao="##"):
    partes = ["# " + (titulo or "Sem título")]
    for nome, texto in secoes:
        partes.append("%s %s\n\n%s" % (nivel_secao, nome, texto) if texto else
                      "%s %s" % (nivel_secao, nome))
    return "\n\n".join(partes).strip() + "\n"


# Complemento entre COLEGIADO e a data ("COM O SUPERINTENDENTE GERAL", 1979) é aceito: ATA não
# reconhecida faz o texto dela cair junto com a capa.
_ATA = re.compile(r"ATA DA REUNI[ÃA]O(?: [A-ZÇÃÁÉÍÓÚÊÔ]+)? D[OE] COLEGIADO(?: N[º°o]\.?\s*\d+)?"
                  r"(?: [A-ZÇÃÁÉÍÓÚÊÔÀ ]{2,60}?)? DE (\d{1,2})\.(\d{1,2})\.(\d{2,4})")
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


_CARGO_RELATOR = re.compile(r"^(?:Presidente|Diretora?)(?:\s+(?:Interin[oa]|Substitut[oa]))?\s+")


# parágrafo depois da decisão: presença, composição da sessão e votos (o vencido não decide)
_FIM_DECISAO = (r"\n\s*\n\s*(?:Após|Presentes?\b|Participaram|Ausentes?\b|[OA] Diretora?\b|"
                r"[OA] President[ea]\b|[^\n]*\bvotou\b)")


def extrato_sei(md):
    """{data, relator, ementa, decisao} do extrato de sessão de julgamento do SEI em markdown."""
    plano = re.sub(r"\*+", "", md)
    d = re.search(r"Data do julgamento:\s*(\d{1,2}/\d{1,2}/\d{4})", plano)
    r = re.search(r"(?m)^\s*Relatora?:\s*(.+?)\s*$", plano)
    e = re.search(r"(?m)^\s*Ementa:\s*(.+?)\s*$", plano)
    dec = re.search(r"(?ms)^\s*Decis[ãa]o:\s*(.+?)(?=%s|\Z)" % _FIM_DECISAO, plano)
    relator = _CARGO_RELATOR.sub("", r.group(1)).strip(" .") if r else ""
    return {"data": jc.data_br(d.group(1)) if d else None,
            "relator": relator if len(relator) <= 80 else "",
            "ementa": re.sub(r"\s+", " ", e.group(1)).strip() if e else "",
            "decisao": dec.group(1) if dec else ""}


def _pas_da_noticia(item, reg, cv, incerteza):
    """PAS fora da listagem (origem `noticia`): `## Extrato` do SEI e as peças dos PDFs da
    notícia; ementa, data, relator e resultado do extrato; fonte original é a notícia."""
    secoes, ext = [], {"data": None, "relator": "", "ementa": "", "decisao": ""}
    for arq in _arquivos(reg, "sei"):
        segs = cv.documento(arq, "Extrato")
        secoes += segs
        ext = extrato_sei("\n".join(t for _, t in segs))
    if not _arquivos(reg, "sei"):
        incerteza.append("sem extrato do SEI")
    pdfs = _arquivos(reg, "pdf")
    for arq in pdfs:
        padrao = secao_do_anexo(arq.get("rotulo"))
        for s, t in segmentar(cv.pdf(arq)):
            s = padrao if s == "Texto" else s
            if secoes and secoes[-1][0] == s:  # capa da peça e a peça: uma seção só
                secoes[-1] = (s, secoes[-1][1] + "\n" + t)
            else:
                secoes.append((s, t))
    if not pdfs:
        incerteza.append("sem PDF das peças; corpo só com o extrato")
    titulo = "PAS CVM nº %s" % item.get("processo", "")
    ementa, fonte_ementa = jc.ementa_sem_partes(ext["ementa"]), "cvm"
    if not ementa:
        texto = "\n".join(t for _, t in secoes)
        m = re.search(r"(?m)^\s*Ementa:\s*(.+(?:\n(?!\s*\n).+)*)", texto)
        ementa = jc.ementa_sem_partes(m.group(1)) if m else ""
    if not ementa:
        ementa, fonte_ementa = "Processo administrativo sancionador. Proc. %s." % \
            item.get("processo", ""), "titulo"
    res = _um(_RES_PAS, ext["decisao"]) if ext["decisao"] else None
    noticia = _arquivos(reg, "noticia")
    fonte = noticia[0] if noticia else reg["arquivos"][0]
    return titulo, ext["data"], ext["relator"], ementa, fonte_ementa, secoes, fonte, res


def ligacoes_crsfn(caminho=LIGACOES_CRSFN):
    """{processo CVM normalizado: [ids de acórdão do CRSFN]} (crsfn.py); sem o arquivo, {}."""
    if not os.path.exists(caminho):
        return {}
    with open(caminho, encoding="utf-8") as f:
        return json.load(f).get("ligacoes") or {}


def fases_pas(caminho=DADOS_ABERTOS_PAS):
    """{NUP só dígitos: (fase atual, data da última movimentação)} dos dados abertos do PAS."""
    if not os.path.exists(caminho):
        return {}
    import csv
    out = {}
    with open(caminho, encoding="latin-1", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            nup_ = re.sub(r"\D", "", row.get("NUP") or "")
            if nup_:
                out[nup_] = ((row.get("Fase_Atual") or "").strip(),
                             (row.get("Data_Ultima_Movimentacao") or "").strip())
    return out


def recurso_crsfn(valores, ligacoes=None, fases=None):
    """Aviso de recurso ao CRSFN para o `incerteza` do PAS: os acórdãos ligados ao processo
    (crsfn-ligacoes.json) ou, sem acórdão, a fase "Recurso CRSFN" dos dados abertos; senão ""."""
    global _LIGACOES_CRSFN, _FASES_PAS
    if ligacoes is None:
        if _LIGACOES_CRSFN is None:
            _LIGACOES_CRSFN = ligacoes_crsfn()
        ligacoes = _LIGACOES_CRSFN
    chaves = jc.processos(valores.get("processo", "")) + [valores.get("nup") or ""]
    ids = []
    for k in chaves:
        for i in ligacoes.get(k, []) if k else []:
            if i not in ids:
                ids.append(i)
    if ids:
        return "recurso ao CRSFN: " + ", ".join(ids)
    if fases is None:
        if _FASES_PAS is None:
            _FASES_PAS = fases_pas()
        fases = _FASES_PAS
    nup_ = re.sub(r"\D", "", valores.get("nup") or jc.nup(valores.get("processo", "")))
    fase, data = fases.get(nup_, ("", "")) if nup_ else ("", "")
    if fase == "Recurso CRSFN":
        return "recurso ao CRSFN em andamento (dados abertos, %s)" % data
    return ""


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
    res_extrato, ementa_pag = None, ""

    if tipo == "pas" and item.get("origem") == "noticia":
        titulo, d, rel, ementa, fonte_ementa, secoes, fonte, res_extrato = _pas_da_noticia(
            item, reg, cv, incerteza)
        data, relator = d or data, relator or rel
        bruto = "\n".join(cv.brutos)
        relator = relator or relator_do_texto(bruto)
        rito = rito or rito_do_texto(bruto)

    elif tipo == "pas":
        if principal["papel"] == "pagina":
            titulo, d, ementa_pag = pas_da_pagina(cv.html(principal, "pas"))
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
        cv.retirado.append(ementa_pag)  # nomes das partes que saem da ementa não são falta
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
            # o PDF anual traz atas de anos anteriores: data da primeira reunião do ano do id
            datas = [d for _, d, _, _ in atas]
            ano = item["id"].split("-")[2][:4]
            data = min([d for d in datas if d[:4] == ano] or datas)
            incerteza.append("decisões separadas por heurística (título em caixa alta), %d ATA(s) "
                             "e %d decisão(ões); data da primeira reunião do ano do arquivo"
                             % (len(atas), sum(len(x[3]) for x in atas)))
        titulo = item.get("titulo", "")
        ementa = jc.ementa_de_titulo(titulo)
        fonte = principal

    elif principal["papel"] == "pagina":  # Colegiado e TC com item do Colegiado
        titulo, d, rel, md = colegiado_da_pagina(cv.html(principal))
        md = cv.timbre(md).strip()
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
    antes_pii = corpo_md
    corpo_md, cortes = pii.limpar_contando(corpo_md)
    if not re.search(r"(?m)^## ", corpo_md):
        corpo_md = corpo_md.rstrip("\n") + "\n\n## Texto\n"
        incerteza.append("fonte sem texto extraível")
    cv.pii = cortes
    if cv.linhas_repetidas:
        cv.avisos.append("%d linha(s) de cabeçalho/rodapé retiradas" % cv.linhas_repetidas)
    if cv.trechos_timbre:
        cv.avisos.append("%d trecho(s) de timbre/rodapé da CVM e do SEI retirados" % cv.trechos_timbre)

    normas, disp, aviso = citacoes(corpo_md)
    if aviso:
        cv.avisos.append(aviso)
    if tipo == "decisao-colegiado" or tipo == "termo-compromisso" or tipo == "pas":
        res = resultado(tipo, corpo_md, item)
    else:
        res = ""
    if res_extrato is not None:
        res = res_extrato
    cv.conferir("\n".join([corpo_md, ementa, data or "", relator]), antes_pii)
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
        "processo": item.get("processo", "") or jc.pas_do_titulo(item.get("titulo")),
        "nup": item.get("nup", ""), "rito": rito,
        "data": data, "relator": pii.limpar(relator), "resultado": res,
        "ementa": pii.limpar(ementa), "ementa_fonte": fonte_ementa if ementa else "",
        "tema": "", "tema_fonte": "", "normas_citadas": normas, "dispositivos_citados": disp,
        "fonte_original": fonte["url"], "sha256_fonte": fonte["sha256"],
        "baixado_em": fonte["baixado_em"], "nivel_verificacao": cv.nivel,
        "incerteza": "; ".join(dict.fromkeys(x for x in incerteza if x)),
    }
    if tipo == "pas":
        aviso = recurso_crsfn(valores)
        if aviso:
            valores["incerteza"] = "; ".join(dict.fromkeys(
                [x for x in valores["incerteza"].split("; ") if x] + [aviso]))
    # D3: nome de pessoa física na ementa sai do frontmatter; a publicada fica em ## Ementa
    publicada = re.sub(r"^\s*Ementa\s*:\s*", "", re.sub(r"\s+", " ", ementa_pag), flags=re.I)
    publicada = pii.limpar(publicada).strip()
    valores, corpo_md, _ = je.ementa_sem_pessoas(valores, corpo_md, publicada=publicada)
    return valores, corpo_md, cv


def _preservar_extracao(valores, caminho):
    """Reconversão não apaga a extração (Task 4): ementa e tema extraídos ficam enquanto a fonte
    não trouxer os seus; resultado e relator antigos ficam se a conversão não achar outros."""
    try:
        antigo, _ = je.ler_julgado(caminho)
    except (OSError, ValueError):
        return valores
    v = dict(valores)
    if antigo.get("ementa_fonte") == "extracao" and v.get("ementa_fonte") in ("titulo", ""):
        v["ementa"], v["ementa_fonte"] = antigo.get("ementa", ""), "extracao"
    if antigo.get("tema_fonte") == "extracao" and not v.get("tema"):
        v["tema"], v["tema_fonte"] = antigo.get("tema", ""), "extracao"
    for c in ("resultado", "relator"):
        if not v.get(c) and antigo.get(c):
            v[c] = antigo[c]
    return v


def gravar_julgado(valores, corpo, raiz=jc.RAIZ):
    caminho = jc.caminho_julgado(valores["tipo"], valores["id"], valores["data"][:4], raiz)
    valores = _preservar_extracao(valores, caminho)
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
