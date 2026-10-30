#!/usr/bin/env python3
"""Fase 3: texto vigente da camada 4 (CMN e BCB) pela última versão compilada do BCB.

O campo Texto da API da busca de normas do BCB (exibenormativo) traz, para muitas normas alteradas,
a redação original. O texto vigente compilado pelo BCB está no PDF da última versão listado em
Documentos com sufixo L ("_vN_L.pdf": só o texto vigente, com as notas "(Redação dada ...)",
"(Incluído ...)", "(Revogado ...)"); o P é a mesma versão com o texto antigo tachado em vermelho e
não serve (o extrator lê o tachado como texto).

Para cada norma da camada 4 com versão >= 2 em Documentos (ou Atualizacoes não vazio, havendo PDF):
1. baixa o PDF da última versão (L; sem L, o de maior versão, registrado) para
   dados/fase-3/bcb-versoes/, pela lista de domínios de scripts/baixar.py;
2. compara o texto do HTML convertido (html_bcb, sem o tachado) com o do PDF (PDFKit), sem
   cabeçalho e rodapé do BCB, sem as notas de redação, sem o título e com as palavras hifenizadas na
   quebra de linha unidas, a partir do primeiro trecho de 6 palavras comum aos dois (a ementa do
   PDF e o cabeçalho do HTML antigo ficam fora): cobertura de palavras (multiconjunto) nos dois sentidos;
3. as duas >= 99%: o HTML já reflete a última versão e fica (consolidado-convertido); senão a
   norma passa a vir do PDF (pdf-extraido, versao_texto consolidado), o que texto_vigente aplica.

Cabeçalho e rodapé do PDF do BCB (sem_cabecalho_rodape), por página (o PDFKit separa as páginas
por form feed): título curto da própria norma ("Resolução nº 4.734, de 27 de junho de 2019"),
com ou sem "Página N de M" (e o número da página grudado no ano), "Página N de M" sozinho, número
de página sozinho no começo ou no fim da página, e o aviso "Este texto não substitui o publicado
no DOU..." (o HTML do BCB não o traz).

Vigência futura (vigencias_futuras): nota "(Redação dada, a partir de DD/MM/AAAA, ...)",
"(Incluído, a partir de ...)", "(Revogado, a partir de ...)" com data posterior à data-base.
O PDF L traz só a redação compilada (uma por dispositivo): com a futura, a atual não está no PDF,
e o texto_vigente não inventa a atual; descreve no `incerteza` (SPEC, "Vigência diferida", exige
as duas redações para o bloco "Vigente a partir de"). bloco_vigencia monta o bloco quando as duas
redações existem (SPEC), para uso quando a fonte as trouxer. Alteração futura listada no campo
Atualizacoes da API sem nota com a mesma data no PDF também vai para o `incerteza` (notas_vigencia).

Na conversão (texto_vigente.montar, PDF do CMN/BCB): limpar_pdf (cabeçalho, rodapé, aviso do DOU,
hifenização) nos dois extratores, e a legibilidade medida em texto_legivel (sem notas e números).

Uso: python3 scripts/bcb_versoes.py [--perimetro ...] [--acervo-bcb ...] [--cache-bcb ...]
  Baixa os PDFs e grava o relatório da decisão em dados/fase-3/bcb-versoes/decisao.json
  (o lote do texto vigente, `texto_vigente.py --camada 4`, decide de novo pelo mesmo critério).
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CACHE_VERSOES = "dados/fase-3/bcb-versoes"
COBERTURA_MIN = 0.99
PREFIXO_MAX = 150  # palavras antes do preâmbulo (título, ementa) que a comparação pode descartar
PDF_BCB = "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/%s/%s"
TIPOS_TITULO = r"(?:Resolu[çc][ãa]o(?: Conjunta)?|Circular|Carta[- ]Circular|Instru[çc][ãa]o Normativa)"
ORDEM_SUFIXO = {"L": 0, "O": 1, "P": 2}
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro")

# Notas de redação do texto compilado do BCB: "(Redação dada pela ...)", "(Incluído, a partir de
# 1º/10/2020, pela ...)", "(Revogado ...)", "(Vigência suspensa ...)", "(Renumerado ...)".
NOTA = re.compile(
    r"\((?:Reda[çc][ãa]o dada|Inclu[íi]d[oa]s?|Revogad[oa]s?|Renumerad[oa]s?|Acrescid[oa]s?|"
    r"Alterad[oa]s?|Suprimid[oa]s?|Exclu[íi]d[oa]s?|Vig[êe]ncia|Retificad[oa]s?|Revigorad[oa]s?)"
    r"\b[^()]*(?:\([^()]*\)[^()]*)*\)", re.I)
NOTA_A_PARTIR = re.compile(
    r"\((Reda[çc][ãa]o dada|Inclu[íi]d[oa]s?|Revogad[oa]s?|Renumerad[oa]s?|Acrescid[oa]s?)\s*,?\s*"
    r"(?:a partir de|produzindo efeitos a partir de)\s+(\d{1,2})[º°o]?/(\d{1,2})/(\d{4})", re.I)
AVISO_DOU = re.compile(r"(?im)^\s*Este texto não substitui o publicado no DOU.*$")
PAGINA = re.compile(r"P[áa]gina\s+\d+\s+de\s+\d+")


# ---------------------------------------------------------------- versão

def ultima_versao(docs):
    """(arquivo, versão, sufixo) do PDF a usar entre [(arquivo, versão, sufixo)]: a maior versão;
    nela, L (texto compilado limpo), depois O, depois P. None sem PDF."""
    if not docs:
        return None
    return sorted(docs, key=lambda d: (-d[1], ORDEM_SUFIXO.get(d[2], 3)))[0]


def precisa_versao(docs, atualizacoes):
    """A norma tem versão compilada a conferir? Versão >= 2 em Documentos, ou Atualizacoes não
    vazio com algum PDF (sem PDF não há o que conferir)."""
    if not docs:
        return False
    return max(d[1] for d in docs) >= 2 or bool((atualizacoes or "").strip())


# ---------------------------------------------------------------- limpeza do PDF

def _numero_regex(numero):
    """Número da norma como o BCB o escreve no rodapé: 4734, 4.734, 0102 ou 102 (o pypdf às vezes
    lê "1 .775")."""
    s = str(int(numero))
    alternativas = [re.escape(a) for a in sorted({s, "%04d" % int(numero)}, key=len, reverse=True)]
    if int(numero) >= 1000:
        alternativas.insert(0, r"%s\s?\.%s" % (s[:-3], s[-3:]))
    return "(?:%s)" % "|".join(alternativas)


def rodape_regex(numero):
    """Título curto da própria norma no cabeçalho/rodapé, com "Página N de M" opcional e o número
    da página que o PDF às vezes gruda no ano ("de19682" = 1968, página 2)."""
    return re.compile(
        r"%s(?: CMN| BCB)? n[º°o]\.?\s*%s,?\s+de\s+\d{1,2}[º°o]?\s+de\s+[A-Za-zçÇ]+\s+de\s*\d{4}(?:\d{1,3}(?!\d)|\.?\s*\d{1,3}(?!\d)|\.)?"
        r"(?:\s*%s)?" % (TIPOS_TITULO, _numero_regex(numero), PAGINA.pattern))


def _e_rodape(linha, rx, indice):
    """A linha (inteira) é cabeçalho ou rodapé da página `indice` (1-based)?"""
    s = linha.strip()
    if not s:
        return True
    if rx.fullmatch(s) or PAGINA.fullmatch(s):
        return True
    return s.isdigit() and int(s) == indice


def sem_cabecalho_rodape(txt, numero):
    """Texto do PDF do BCB sem cabeçalho e rodapé repetidos e sem o aviso do DOU; páginas
    separadas por form feed (saída do PDFKit). Rodapé grudado no começo da linha seguinte (sem form
    feed) também sai."""
    if txt is None:
        return None
    rx = rodape_regex(numero)
    paginas = txt.split("\f")
    out = []
    for i, pagina in enumerate(paginas, 1):
        linhas = pagina.split("\n")
        while linhas and _e_rodape(linhas[-1], rx, i):
            linhas.pop()
        while linhas and (_e_rodape(linhas[0], rx, i) if i > 1 else
                          linhas[0].strip() in ("", str(i))):  # na 1ª página, só o número
            linhas.pop(0)
        # linha inteira de rodapé no meio da página (o pypdf não segue a ordem visual)
        pagina = "\n".join(x for x in linhas if not rx.fullmatch(x.strip()))
        # rodapé no fim de uma linha ou grudado no texto (sem espaço antes): quebra de linha
        pagina = re.sub(r"(?m)(?<=\S)%s(?=\S|$)" % rx.pattern, "\n", pagina)
        pagina = re.sub(r"(?m)^%s(?:\s+(?=\S)|(?=\S))" % rx.pattern, "", pagina)  # no começo da linha
        pagina = re.sub(r"(?m)(?<=\S) ?%s$" % PAGINA.pattern, "", pagina)
        pagina = AVISO_DOU.sub("", pagina)
        out.append(pagina.strip("\n"))
    return "\n".join(p for p in out if p.strip()) + "\n"


# ---------------------------------------------------------------- comparação HTML x PDF

def sem_notas(txt):
    return NOTA.sub(" ", txt or "")


def sem_hifenizacao(txt):
    """Une a palavra partida no fim da linha do PDF ("ob-\\njeto" -> "objeto")."""
    return re.sub(r"(\w)-\n(?=[a-zà-ü])", r"\1", txt or "")


def palavras(txt):
    """As palavras da métrica do texto_vigente ("_" separa), em NFKC, minúsculas."""
    return re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", txt or "").lower())


TITULO = re.compile(r"(?i)^[\s#*>`]*(?:RESOLU[CÇ][AÃ]O|CIRCULAR|CARTA[- ]CIRCULAR|INSTRU[CÇ][AÃ]O"
                    r"(?: NORMATIVA)?)(?: CONJUNTA| CMN| BCB)?\s+N\b")


def _comparavel(txt):
    """Palavras (em ordem) sem notas de redação e sem o título (primeira linha "RESOLUÇÃO Nº ...",
    que o HTML em geral não traz e o HTML antigo traz como "RESOLUCAO N 000102")."""
    linhas = [x for x in (txt or "").split("\n") if x.strip() and not x.strip().startswith("```")]
    if linhas and TITULO.match(linhas[0]):
        linhas = linhas[1:]
    return palavras(sem_notas("\n".join(linhas)))


def limpar_pdf(txt, numero):
    """Texto do PDF do BCB para a norma: sem cabeçalho, rodapé e aviso do DOU, com as palavras
    partidas na quebra de linha unidas. As linhas ficam como o extrator as deu."""
    return None if txt is None else sem_hifenizacao(sem_cabecalho_rodape(txt, numero))


def texto_legivel(txt):
    """Texto para a prova de legibilidade do PDF (texto_vigente.motivo_sem_texto): sem as notas de
    redação, números, algarismos romanos e letras de alínea. Norma curta com muitos dispositivos
    revogados ("Art. 4º (Revogado, a partir de 1º/5/2021, pela Resolução CMN nº 4.903/2021.)") cai
    abaixo da fração alfabética mínima com texto perfeitamente legível e iria para o OCR."""
    return re.sub(r"\b\d+[ºª°]?\b|\b[IVXLC]+\b|\b[a-z]\)", " ", sem_notas(txt or ""))


def texto_comparavel_pdf(txt, numero):
    """Palavras do PDF para a comparação: sem cabeçalho e rodapé, hifenização, notas e título."""
    return _comparavel(limpar_pdf(txt, numero))


def texto_comparavel_html(md):
    return _comparavel(AVISO_DOU.sub("", md or ""))


def alinhar_inicio(a, b, n=6, maximo=PREFIXO_MAX):
    """(a, b) sem o que vem antes do primeiro trecho de `n` palavras comum aos dois (a ementa do
    PDF, o cabeçalho do HTML antigo), cortando no máximo `maximo` palavras de cada lado; sem trecho
    comum nesse limite, os dois ficam como estão."""
    pos_b = {}
    for j in range(min(len(b) - n + 1, maximo + 1)):
        pos_b.setdefault(tuple(b[j:j + n]), j)
    for i in range(min(len(a) - n + 1, maximo + 1)):
        j = pos_b.get(tuple(a[i:i + n]))
        if j is not None:
            return a[i:], b[j:]
    return a, b


def _cob(a, b):
    total = sum(a.values())
    return round(sum(min(n, b[w]) for w, n in a.items()) / total, 4) if total else 0.0


def coberturas(html_md, pdf_txt, numero):
    """(fração das palavras do HTML presentes no PDF, fração das do PDF presentes no HTML), em
    multiconjunto, depois de alinhar o começo dos dois textos."""
    a, b = alinhar_inicio(texto_comparavel_html(html_md), texto_comparavel_pdf(pdf_txt, numero))
    a, b = Counter(a), Counter(b)
    return _cob(a, b), _cob(b, a)


def decidir(cob_html_pdf, cob_pdf_html, minimo=COBERTURA_MIN):
    """"html" se o HTML já reflete a última versão (as duas coberturas >= mínimo), senão "pdf"."""
    return "html" if cob_html_pdf >= minimo and cob_pdf_html >= minimo else "pdf"


def faltam(a_txt, b_txt, n=15):
    """Palavras de a que faltam em b (diagnóstico do relatório)."""
    a, b = Counter(palavras(a_txt)), Counter(palavras(b_txt))
    return [w for w, _ in (a - b).most_common(n)]


# ---------------------------------------------------------------- vigência futura

def vigencias_futuras(txt, data_base):
    """[(AAAA-MM-DD, tipo da nota)] das notas com "a partir de" posterior a data_base (AAAA-MM-DD),
    em ordem de data, sem repetição."""
    t = re.sub(r"\s+", " ", txt or "")
    out = set()
    for m in NOTA_A_PARTIR.finditer(t):
        d = "%s-%02d-%02d" % (m.group(4), int(m.group(3)), int(m.group(2)))
        try:
            datetime.date.fromisoformat(d)
        except ValueError:
            continue
        if d > data_base:
            out.add((d, m.group(1).lower()))
    return sorted(out)


A_PARTIR = re.compile(r"a partir de\s+(\d{1,2})[º°o]?/(\d{1,2})/(\d{4})", re.I)


def atualizacoes_futuras(atualizacoes, data_base):
    """[(AAAA-MM-DD, texto)] das entradas do campo Atualizacoes da API ("...;#...") com
    "a partir de D/M/AAAA" posterior a data_base."""
    out = []
    for parte in (atualizacoes or "").split(";#"):
        parte = parte.strip().strip(";").strip()
        m = A_PARTIR.search(parte)
        if not m:
            continue
        d = "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
        if d > data_base:
            out.append((d, parte))
    return out


def notas_vigencia(txt, atualizacoes, versao, data_base):
    """Frases do `incerteza` sobre vigência futura de uma norma que vem do PDF L. O PDF L traz uma
    redação por dispositivo; sem as duas, não há bloco "Vigente a partir de" (SPEC): descreve-se.
    Também a alteração futura que a busca de normas lista e o PDF não traz (nenhuma nota com a data)."""
    out = []
    futuras = vigencias_futuras(txt, data_base)
    for d, tipo in futuras:
        out.append("O PDF da versão %d traz dispositivo %s a partir de %s; a redação anterior não está "
                   "no PDF e não foi reconstituída [verificar]." % (versao, tipo, _data_br(d)))
    datas = {d for d, _ in futuras}
    for d, texto in atualizacoes_futuras(atualizacoes, data_base):
        if d not in datas:
            out.append("A busca de normas do BCB lista alteração com vigência futura que o PDF da "
                       "versão %d não traz: \"%s\" [verificar]." % (versao, texto.rstrip(".")))
    return out


def _data_br(iso):
    a, m, d = iso.split("-")
    return "%d de %s de %s" % (int(d), MESES[int(m) - 1], a)


def bloco_vigencia(atual, futura, data_iso):
    """Dispositivo com as duas redações (SPEC, "Vigência diferida"): a atual e, depois, a futura,
    aberta por "Vigente a partir de <data>"."""
    return "%s\n\n> Vigente a partir de %s:\n>\n> %s\n" % (atual.strip(), _data_br(data_iso), futura.strip())


# ---------------------------------------------------------------- download e decisão

def baixar_pdf(url, destino):
    """PDF da versão no cache (nada é baixado duas vezes), pela lista de domínios de baixar.py."""
    import baixar
    return baixar.baixar(url, destino)


def incerteza_pdf(versao, arquivo):
    return ("Texto vigente compilado pelo BCB no PDF da versão %d (`%s`); o campo de texto da busca "
            "de normas do BCB traz a redação original." % (versao, arquivo))


def decidir_fonte(item, conteudo, documentos, html_md, extrair, cache=CACHE_VERSOES, baixar=None,
                  data_base=None):
    """Decisão HTML x PDF de uma norma da camada 4. `documentos` = [(arquivo, versão, sufixo)];
    `html_md` = Markdown do HTML da API sem o tachado; `extrair(path)` = texto do PDF (PDFKit).
    Devolve o dict da decisão (sem efeito no item) ou None se a norma não tem versão a conferir."""
    if not precisa_versao(documentos, conteudo.get("Atualizacoes")):
        return None
    ident = conteudo.get("Id")
    arq, versao, sufixo = ultima_versao(documentos)
    url = PDF_BCB % (ident, arq)
    dec = {"arquivo": arq, "versao": versao, "sufixo": sufixo, "url": url}
    if sufixo != "L":
        dec["aviso"] = "sem PDF L na versão %d; usado %s" % (versao, arq)
    path = (baixar or baixar_pdf)(url, os.path.join(cache, arq))
    dec["path"] = path
    txt = extrair(path)
    if txt is None:
        dec.update(decisao="html", motivo="PDF sem texto pelo PDFKit; mantido o HTML")
        return dec
    data_base = data_base or datetime.date.today().isoformat()
    if not (html_md or "").strip():
        dec.update(decisao="pdf", motivo="sem texto HTML na API do BCB")
    else:
        a, b = coberturas(html_md, txt, item["numero"])
        dec.update(cobertura_html_pdf=a, cobertura_pdf_html=b, decisao=decidir(a, b))
        if dec["decisao"] == "pdf":
            dec["faltam_no_html"] = faltam(sem_notas(limpar_pdf(txt, item["numero"])), html_md)
    if dec["decisao"] == "pdf":
        dec["notas_vigencia"] = notas_vigencia(limpar_pdf(txt, item["numero"]),
                                               conteudo.get("Atualizacoes"), versao, data_base)
    return dec


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perimetro", default="fontes/perimetro-camada4.json")
    ap.add_argument("--acervo-bcb", default="fontes/acervo-bcb.json")
    ap.add_argument("--cache-bcb", default="dados/fase-2c/bcb")
    ap.add_argument("--cache", default=CACHE_VERSOES)
    args = ap.parse_args(argv[1:])
    import html_bcb
    import texto_vigente as tv
    with open(args.perimetro, encoding="utf-8") as f:
        per = json.load(f)
    with open(args.acervo_bcb, encoding="utf-8") as f:
        ac = json.load(f)
    os.makedirs(args.cache, exist_ok=True)
    rel = []
    for item in tv.itens_camada4(per, ac, cache_bcb=args.cache_bcb):
        if not item.get("cache_api"):
            continue
        c = (tv._ler_api_bcb(item).get("conteudo") or [{}])[0]
        docs = tv.documentos_bcb(c.get("Documentos"))
        md = tv.sem_tachado_bcb(html_bcb.html_para_md(c.get("Texto") or "")) if c.get("Texto") else ""
        dec = decidir_fonte(item, c, docs, md, tv._pdfkit_txt, cache=args.cache)
        if dec:
            rel.append(dict(id=item["id"], **{k: v for k, v in dec.items() if k != "path"}))
            print(json.dumps(rel[-1], ensure_ascii=False))
    with open(os.path.join(args.cache, "decisao.json"), "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("pdf: %d; html: %d" % (sum(r["decisao"] == "pdf" for r in rel), sum(r["decisao"] == "html" for r in rel)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
