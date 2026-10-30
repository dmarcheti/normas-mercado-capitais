#!/usr/bin/env python3
"""Texto vigente por script (Fase 2b): da fonte oficial da CVM ao Markdown da SPEC, sem LLM.

Fonte, na ordem: consolidado DOCX > DOC > HTM > ato DOCX > DOC > HTM > PDF.
- DOCX: converter.docx_para_md, com as caixas de texto (diagramas) em blocos "> [Diagrama]" e a
  âncora [k] das notas de rodapé, numeradas na ordem de exibição como a seção final.
- DOC e HTM: convertidos para DOCX pelo `textutil` do macOS e depois como DOCX.
- PDF: no macOS, o texto do PDFKit (scripts/pdf_macos.py); fora dele, ou se o PDFKit falhar, o
  do pypdf (dependência opcional, fora da biblioteca padrão). Os dois passam por NFKC (desfaz
  as ligaduras ﬁ/ﬂ), preservando º e ª. Nível de verificação menor.
  PDF ilegível (fração de palavras alfabéticas de 3+ letras abaixo de 0,5, ou menos de 50
  palavras: fonte Type3 sem mapa Unicode, escaneado) vai para o OCR do Vision (macOS), aceito
  com confiança média >= 0,85 e 50+ palavras, sem a regra da fração alfabética (há ofício que é
  tabela de tickers e ISINs); sem OCR aceito, não vira arquivo e o relatório marca `sem-texto`
  com o motivo.
No consolidado, texto tachado (~~...~~, redação antiga) sai; no ato, fica marcado (num
Documento de Revisão de CPC o tachado é o trecho excluído, conteúdo do ato). As notas de
alteração do consolidado ficam, como nas leis, porque não há histórico de commits que as substitua.

Conferência independente: o texto da fonte extraído pelo `textutil -convert txt` (DOCX,
DOC, HTM) ou pelo pypdf (PDF cujo texto veio do PDFKit) contra o Markdown; sem PDFKit, ou no
OCR, o PDF não tem conferência independente. `cobertura` = fração das palavras da fonte
presentes no Markdown convertido, antes de tirar o tachado (multiconjunto; palavra =
`[^\W_]+`, "_" separa, para as URLs do rodapé do SEI); `palavras_tachadas` = quantas palavras
estão em texto tachado.

Datas: `baixado_em` = data do download da fonte (mtime do arquivo em cache, fuso de São Paulo),
que é a data-base do texto no `incerteza`; `verificado_em` = data da execução.

Frontmatter: campos de validar.CAMPOS, na ordem, mais `vigencia_inicio` (só com bloco
"vigente a partir de") e `nivel_verificacao` (consolidado-convertido, ato-convertido,
pdf-extraido ou ocr). Resoluções e Instruções: `situacao: vigente`; Pareceres e Ofícios-Circulares:
`nao-informada` (a CVM não publica a vigência deles).

Fase 2c (SPEC v0.4.0):
- Camada 4 (CMN e BCB): as normas de fontes/perimetro-camada4.json com decisao "entra", juntadas a
  fontes/acervo-bcb.json. Fonte: o campo Texto da API da busca de normas do BCB (cache em
  dados/fase-2c/bcb/<tipo_bcb com _>-NNNNN.json; se faltar, a API), gravado como .htm e convertido
  por scripts/html_bcb.py (item com `conversor: "html_bcb"`; não passa pelo textutil). Conferência
  independente: `textutil -convert txt` do .htm (macOS); sem textutil, o texto do html.parser e
  `conferencia_independente: false`. No consolidado do BCB, o tachado sai e, com ele, as linhas de
  tabela que ficam vazias. Norma sem texto na API: o PDF da última versão listado em Documentos
  (sufixo L, texto compilado; v1 O, ato original), em normativos.bcb.gov.br/Lists/Normativos/
  Attachments/<Id>/<arquivo>; sem PDF, `sem-texto` com o motivo.
- Camada 5 (ANBIMA e B3): fontes/acervo-anbima.json (situacao "vigente") e fontes/acervo-b3.json
  (entra true); PDF do cache dados/fase-2c/pdf-anbima|pdf-b3/<sha1(url)[:10]>.pdf, senão baixado;
  extração como a dos PDFs da CVM. Slug do título, até 80 caracteres; colisão ganha -2 e aviso.
- Frontmatter: `orgao` do item (padrão cvm); camada 5 com `numero` e `publicacao_dou` vazios;
  `incerteza` por órgão.

Uso:
  python3 scripts/texto_vigente.py --camada 1|2|4|5 [--acervo fontes/acervo.json]
      [--saida plugins/normas/normas] [--limite N] [--cache DIR] [--relatorio ARQ]
    camada 1: Resoluções vigentes mais a 249, menos as 8 do núcleo, e Instruções vigentes;
    camada 2: os Pareceres de Orientação e os Ofícios-Circulares desde 2022-01-01;
    camada 4: CMN e BCB (--perimetro, --acervo-bcb, --cache-bcb);
    camada 5: ANBIMA e B3 (--acervo-anbima, --acervo-b3, --cache-anbima, --cache-b3).
    Relatório em dados/texto-vigente-camada-N.json; fontes baixadas em dados/texto-vigente-fontes/.
  python3 scripts/texto_vigente.py <itens.json> <pasta de saída>   (modo do piloto)
    itens.json: lista de {id, tipo, numero, data, dou, ementa, situacao, url_pagina, arquivo,
    fontes: {consolidado: {ext: url}, ato: {ext: url}}, alteradoras, vigente_ate_ato};
    relatório em <pasta de saída>/relatorio.json, fontes em <pasta de saída>/fontes/.
"""
import argparse
import datetime
import email.utils
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import docx_para_md, normalizar_artigos, ordem_das_notas, textos_das_caixas  # noqa: E402
import bcb_versoes  # noqa: E402
import html_bcb  # noqa: E402
from inventario import USER_AGENT  # noqa: E402
from inventario_acervo import citadas  # noqa: E402
from validar import CAMPOS, MARCA_VIGENCIA  # noqa: E402

ORDEM = [("consolidado", "docx"), ("consolidado", "doc"), ("consolidado", "htm"),
         ("ato", "docx"), ("ato", "doc"),
         ("ato", "htm"), ("consolidado", "pdf"), ("ato", "pdf")]
DATA_BASE = time.strftime("%Y-%m-%d")
NUCLEO = (17, 21, 30, 50, 60, 80, 160, 175)  # já no acervo, com histórico (Fase 2)
INCLUIR_FORA_DO_ESTOQUE = (249,)  # editada depois da última atualização do Estoque (C1)
CORTE_OFICIOS = "2022-01-01"  # C8
LEGIBILIDADE_MIN, PALAVRAS_MIN = 0.5, 50
OCR_CONFIANCA_MIN = 0.85  # média das páginas; o OCR não passa pela regra da fração alfabética
# DOCX/DOC: texto curto em português fica perto de 0,45 ("de", "o", "1º"); lixo binário, perto de 0,2
LEGIBILIDADE_MIN_WORD = 0.3
NAO_INFORMADA = {
    "parecer-orientacao": "pareceres de orientação",
    "oficio-circular": "ofícios-circulares",
}
# Fase 2c. Camada 4: tipo -> (orgao, prefixo do id, pasta sob o diretório de saída)
TIPOS_BCB = {
    "resolucao-cmn": ("cmn", "cmn-res-", "cmn/resolucoes"),
    "resolucao-bcb": ("bcb", "bcb-res-", "bcb/resolucoes"),
    "resolucao-conjunta": ("bcb", "bcb-resc-", "bcb/resolucoes-conjuntas"),
    "circular": ("bcb", "bcb-circ-", "bcb/circulares"),
    "carta-circular": ("bcb", "bcb-cc-", "bcb/cartas-circulares"),
    "instrucao-normativa-bcb": ("bcb", "bcb-in-", "bcb/instrucoes-normativas"),
}
CACHE_BCB = "dados/fase-2c/bcb"
CACHE_PDF = {"anbima": "dados/fase-2c/pdf-anbima", "b3": "dados/fase-2c/pdf-b3"}
PDF_BCB = "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/%s/%s"
API_BCB = "https://www.bcb.gov.br/api/conteudo/app/normativos/exibenormativo?"
PALAVRAS_MIN_HTML = 30  # o mesmo corte do inventario_bcb (formato "html" x "sem-texto")
NOMES = {"anbima": "ANBIMA", "b3": "B3"}
TIPOS_ANBIMA = {"codigo": "codigo-autorregulacao", "regras-procedimentos": "regras-procedimentos",
                "glossario": "glossario", "deliberacao": "orientacao-autorregulacao",
                "parecer": "orientacao-autorregulacao", "diretrizes": "orientacao-autorregulacao",
                "orientacao": "orientacao-autorregulacao"}
SLUG_MAX = 80
MESES = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}


# ---------------------------------------------------------------- escolhas

def normalizar_fontes(fontes):
    """Chave de cada fonte pela extensão real da URL: a página da CVM rotula "[DOC]" o
    consolidado em Word 97 e o inventário o guarda em `docx` (ex.: Res. 9, 11, 13)."""
    out = {}
    for tipo, porext in (fontes or {}).items():
        for ext, url in (porext or {}).items():
            real = url.split("?", 1)[0].rsplit(".", 1)[-1].lower() if url else ext
            real = "htm" if real == "html" else real
            chave = real if real in ("docx", "doc", "htm", "pdf") else ext
            out.setdefault(tipo, {}).setdefault(chave, url)
    return out


def fontes_candidatas(fontes):
    """[(tipo, ext, url)] das fontes disponíveis, na ordem de preferência."""
    fontes = normalizar_fontes(fontes)
    return [(tipo, ext, fontes[tipo][ext]) for tipo, ext in ORDEM if fontes.get(tipo, {}).get(ext)]


def escolher_fonte(fontes):
    """(tipo, ext, url) da melhor fonte disponível, ou None."""
    c = fontes_candidatas(fontes)
    return c[0] if c else None


def nivel_verificacao(tipo_fonte, ext, ocr=False):
    if ext == "pdf":
        return "ocr" if ocr else "pdf-extraido"
    return "consolidado-convertido" if tipo_fonte == "consolidado" else "ato-convertido"


def limpar_ementa(texto):
    """Ementa sem as notas "(Publicada no DOU ...)", "(Retificada ...)" e o que vem depois."""
    t = re.sub(r"\s+", " ", (texto or "").replace("\xa0", " ")).strip()
    return re.split(r"\s*\(\s*(?:Publicad|Retificad|Republicad)", t)[0].strip()


def numero_oficio(titulo):
    """Número do Ofício-Circular no título; no ofício anual, o ano."""
    m = re.search(r"Anual\s+(\d{4})", titulo, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*/\s*(?:\d{4}|\d{2})\b", titulo)
    return int(m.group(1)) if m else None


def _num_ato(txt):
    """'577/16' -> 577; 209 -> 209."""
    m = re.match(r"\s*(\d+)", str(txt))
    return int(m.group(1)) if m else 0


def _vigente_ate(fontes, alteradoras):
    escolha = escolher_fonte(fontes)
    if escolha and escolha[0] == "consolidado" and alteradoras:
        return str(max(_num_ato(a) for a in alteradoras))
    return ""


def _pasta_slug(oc):
    """(pasta, slug) do ofício: o `slug` do acervo (único e em kebab-case, gravado pelo
    inventário); em acervo antigo, sem o campo, o nome da url_pagina."""
    url = oc["url_pagina"]
    slug = oc.get("slug") or url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    pasta = oc.get("superintendencia") or url.split("/oficios-circulares/", 1)[1].split("/")[0]
    return pasta, slug


def itens_do_acervo(acervo, camada, cache_bcb=CACHE_BCB, cache_pdf=None):
    """Itens prontos para `processar`, a partir de fontes/acervo.json.

    Camada 1: Resoluções vigentes e as de INCLUIR_FORA_DO_ESTOQUE, menos o NUCLEO; Instruções
    vigentes. Camada 2: Pareceres de Orientação (todos) e Ofícios-Circulares desde CORTE_OFICIOS.
    Camada 4: `acervo` = {"perimetro": [...], "bcb": acervo-bcb.json} (itens_camada4).
    Camada 5: `acervo` = {"anbima": acervo-anbima.json, "b3": acervo-b3.json} (itens_camada5).
    """
    revogadas = (["Instrução CVM %d" % i["numero"] for i in acervo.get("instrucoes", [])
                  if i.get("situacao") == "revogada"]
                 + ["Resolução CVM %d" % r["numero"] for r in acervo.get("resolucoes", [])
                    if r.get("situacao") == "revogada"])
    itens = []
    if camada == 1:
        data_estoque = acervo.get("estoque_regulatorio", {}).get("atualizado_em")
        for r in acervo.get("resolucoes", []):
            n = r["numero"]
            if n in NUCLEO or not (r["situacao"] == "vigente" or n in INCLUIR_FORA_DO_ESTOQUE):
                continue
            fontes = {"consolidado": r.get("consolidado") or {}, "ato": r.get("ato") or {}}
            alt = [str(a) for a in r.get("alteradoras", [])]
            notas = []
            if r["situacao"] != "vigente":
                notas.append("Editada depois da última atualização do Estoque Regulatório da CVM "
                             "(%s); vigente por inferência [verificar]." % data_estoque)
            itens.append({
                "id": "cvm-res-%d" % n, "tipo": "resolucao", "numero": n,
                "data": r["data"], "dou": r.get("dou"), "ementa": limpar_ementa(r["ementa"]),
                "situacao": "vigente", "url_pagina": r.get("url_pagina"), "fontes": fontes,
                "alteradoras": alt, "vigente_ate_ato": _vigente_ate(fontes, alt),
                "arquivo": "cvm/resolucoes/%04d.md" % n, "notas": notas,
            })
        for i in acervo.get("instrucoes", []):
            if i.get("situacao") != "vigente":
                continue
            n = i["numero"]
            fontes = i.get("arquivos") or {}
            alt = list(i.get("alterada_por", []))
            itens.append({
                "id": "cvm-instr-%d" % n, "tipo": "instrucao", "numero": n,
                "data": i["data"], "dou": i.get("dou"),
                "ementa": limpar_ementa(i.get("ementa") or i["descricao"]),
                "situacao": "vigente", "url_pagina": i.get("url_pagina"), "fontes": fontes,
                "alteradoras": alt, "vigente_ate_ato": _vigente_ate(fontes, alt),
                "arquivo": "cvm/instrucoes/%04d.md" % n, "notas": [],
            })
    elif camada == 2:
        for p in acervo.get("pareceres", []):
            n = p["numero"]
            fontes = p.get("arquivos") or {}
            ementa = limpar_ementa(p.get("ementa") or p["descricao"])
            alt = list(p.get("alterada_por", []))
            itens.append({
                "id": "cvm-po-%d" % n, "tipo": "parecer-orientacao", "numero": n,
                "data": p["data"], "dou": p.get("dou"), "ementa": ementa,
                "situacao": "nao-informada", "url_pagina": p.get("url_pagina"), "fontes": fontes,
                "alteradoras": alt, "vigente_ate_ato": _vigente_ate(fontes, alt),
                "arquivo": "cvm/pareceres-orientacao/%04d.md" % n,
                "revogadas_citadas": _revogadas_citadas(ementa, revogadas), "notas": [],
            })
        for oc in acervo.get("oficios_circulares", []):
            if not oc.get("data") or oc["data"] < CORTE_OFICIOS:
                continue
            pasta, slug = _pasta_slug(oc)
            ementa = limpar_ementa(oc.get("ementa") or oc["descricao"])
            itens.append({
                "id": oc.get("id") or "cvm-%s" % slug, "tipo": "oficio-circular", "numero": numero_oficio(oc["titulo"]),
                "titulo": oc["titulo"], "data": oc["data"], "dou": None, "ementa": ementa,
                "situacao": "nao-informada", "url_pagina": oc["url_pagina"],
                "fontes": {"ato": {"pdf": oc["url_pdf"]}} if oc.get("url_pdf") else {},
                "alteradoras": [], "vigente_ate_ato": "",
                "arquivo": "cvm/oficios-circulares/%s/%s.md" % (pasta, slug),
                "revogadas_citadas": _revogadas_citadas(ementa, revogadas), "notas": [],
            })
    elif camada == 4:
        return itens_camada4(acervo["perimetro"], acervo["bcb"], cache_bcb=cache_bcb)
    elif camada == 5:
        return itens_camada5(acervo.get("anbima") or {}, acervo.get("b3") or {}, cache_pdf=cache_pdf)
    else:
        raise ValueError("camada deve ser 1, 2, 4 ou 5, veio %r" % camada)
    return itens


def _arquivo_api_bcb(tipo_bcb, numero, cache_bcb=CACHE_BCB):
    return os.path.join(cache_bcb, "%s-%05d.json" % (tipo_bcb.replace(" ", "_"), numero))


def itens_camada4(perimetro, acervo_bcb, cache_bcb=CACHE_BCB):
    """Itens das normas do CMN e do BCB com decisao "entra" no perímetro (C1), com os campos de
    identificação de fontes/acervo-bcb.json. Texto da API (html_bcb) se o formato é "html";
    "sem-texto": o PDF, resolvido em processar (preparar_bcb), que precisa do Id da API."""
    idx = {(n["tipo"], n["numero"]): n for n in acervo_bcb.get("normas", [])}
    itens = []
    for p in perimetro:
        if p.get("decisao") != "entra":
            continue
        tipo, numero = p["tipo"], int(p["numero"])
        orgao, prefixo, pasta = TIPOS_BCB[tipo]
        n = idx.get((tipo, numero))
        item = {"id": "%s%d" % (prefixo, numero), "orgao": orgao, "tipo": tipo, "numero": numero,
                "data": p.get("data"), "dou": None, "ementa": "", "situacao": "vigente",
                "url_pagina": None, "fontes": {}, "alteradoras": [], "vigente_ate_ato": "",
                "arquivo": "%s/%04d.md" % (pasta, numero), "notas": []}
        if n is None:
            item["sem_texto_motivo"] = "norma do perímetro ausente de fontes/acervo-bcb.json"
            itens.append(item)
            continue
        formato = n.get("formato") or ""
        item.update({
            "data": n.get("data") or p.get("data"), "dou": n.get("dou"),
            "ementa": limpar_ementa(n.get("assunto")), "url_pagina": n.get("url_pagina"),
            "tipo_bcb": n["tipo_bcb"], "versao": n.get("versao"), "formato": formato,
            "documentos": n.get("documentos") or "",
            "cache_api": _arquivo_api_bcb(n["tipo_bcb"], numero, cache_bcb),
        })
        if formato.startswith("html"):
            item["conversor"] = "html_bcb"
            item["fontes"] = {"consolidado": {"htm": n.get("url_pagina")}}
        itens.append(item)
    return itens


def documentos_bcb(documentos):
    """[(arquivo, versão, sufixo)] do campo Documentos da API ("Circ_3290_v3_L.pdf;21#;...")."""
    out = []
    for parte in re.split(r";\d*#;?", documentos or ""):
        nome = parte.strip().strip(";")
        m = re.search(r"_v(\d+)_([A-Za-z])\.pdf$", nome, re.I)
        if m:
            out.append((nome, int(m.group(1)), m.group(2).upper()))
    return out


def pdf_da_ultima_versao(documentos):
    """(arquivo, versão, sufixo) do PDF da última versão: maior vN; nela, L (texto compilado
    limpo) antes de O (ato original) e de P; ou None."""
    docs = documentos_bcb(documentos)
    if not docs:
        return None
    ordem = {"L": 0, "O": 1, "P": 2}
    return sorted(docs, key=lambda d: (-d[1], ordem.get(d[2], 3)))[0]


def _ler_api_bcb(item):
    """JSON da norma na API do BCB: o cache, ou a API (gravando o cache, como inventario_bcb)."""
    destino = item["cache_api"]
    if not (os.path.exists(destino) and os.path.getsize(destino)):
        import urllib.parse
        from inventario_bcb import _get
        d = _get(API_BCB + urllib.parse.urlencode({"p1": item["tipo_bcb"], "p2": item["numero"]}))
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    with open(destino, encoding="utf-8") as f:
        return json.load(f)


def orgaos_conjunta(texto_html):
    """Órgãos que editam a Resolução Conjunta, pelo preâmbulo ("A X e o Y tornam público"), ou None."""
    t = re.sub(r"\s+", " ", html_bcb.INVISIVEIS.sub("", re.sub(r"<[^>]+>", " ", texto_html or "")))
    import html as htmllib
    t = re.sub(r"\s+", " ", htmllib.unescape(t).replace("\xa0", " ")).strip()
    m = re.search(r"(?:^|[.;:]\s)(?:[AO]s? )?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^.;:]{3,300}?) tornam? público", t)
    return m.group(1).strip() if m else None


def versao_bcb(item, conteudo, documentos):
    """Decisão HTML x PDF da última versão (bcb_versoes.decidir_fonte): baixa o PDF L para
    dados/fase-3/bcb-versoes/ e o compara, pelo PDFKit, com o HTML da API sem o tachado."""
    texto = conteudo.get("Texto") or ""
    md = sem_tachado_bcb(html_bcb.html_para_md(texto)) if texto.strip() else ""
    return bcb_versoes.decidir_fonte(item, conteudo, documentos, md, _pdfkit_txt, data_base=DATA_BASE)


def preparar_bcb(item, versoes=None):
    """Completa o item da camada 4 com a API: Id e PDFs (fonte_original; fonte da norma sem
    texto), DOU que faltar e órgãos da Resolução Conjunta. Devolve o conteúdo da API.
    Norma com HTML e versão >= 2 em Documentos (Fase 3): se o HTML não cobre o PDF L da última
    versão (99% nos dois sentidos), a fonte passa a ser esse PDF. `versoes` (padrão versao_bcb)
    devolve a decisão; o resumo dela fica em item["versao_bcb"] para o relatório."""
    c = (_ler_api_bcb(item).get("conteudo") or [{}])[0]
    if not item.get("dou"):
        from inventario_bcb import data_dou
        item["dou"] = data_dou(c.get("DOU"))
    if item.get("versao") is None and c.get("VersaoNormativo"):
        item["versao"] = c.get("VersaoNormativo")
    docs = c.get("Documentos") if isinstance(c.get("Documentos"), str) else item.get("documentos")
    ident = c.get("Id")
    originais = [d for d in documentos_bcb(docs) if d[2] == "O"]
    if ident and originais:
        item["fonte_original"] = PDF_BCB % (ident, sorted(originais, key=lambda d: d[1])[0][0])
    if item["tipo"] == "resolucao-conjunta":
        org = orgaos_conjunta(c.get("Texto"))
        item["notas"] = item.get("notas", []) + [
            "Resolução Conjunta; órgãos no preâmbulo: %s; o acervo a classifica sob o BCB." % org if org else
            "Resolução Conjunta do BCB com outro órgão; o acervo a classifica sob o BCB "
            "[verificar os órgãos no preâmbulo]."]
    if item.get("conversor") == "html_bcb" and ident:
        dec = (versoes or versao_bcb)(item, c, documentos_bcb(docs))
        if dec:
            item["versao_bcb"] = {k: v for k, v in dec.items() if k != "path"}
        if dec and dec["decisao"] == "pdf":
            del item["conversor"]
            item["fontes"] = {"consolidado": {"pdf": dec["url"]}}
            item["pdf_bcb"] = {"arquivo": dec["arquivo"], "versao": dec["versao"], "sufixo": dec["sufixo"]}
            item["cache_pdf"] = dec["path"]
            item["notas"] = (item.get("notas", []) + [bcb_versoes.incerteza_pdf(dec["versao"], dec["arquivo"])]
                             + dec.get("notas_vigencia", []))
            if dec.get("aviso"):
                item["notas"].append("[verificar] %s." % dec["aviso"])
    elif item.get("conversor") != "html_bcb":
        ultima = pdf_da_ultima_versao(docs)
        if not ultima or not ident:
            item["sem_texto_motivo"] = (
                "sem texto HTML na API do BCB (formato %s) e %s" % (
                    item.get("formato") or "?",
                    "sem PDF no campo Documentos" if not ultima else "sem Id da norma na API"))
        else:
            arq, versao, sufixo = ultima
            tipo_fonte = "ato" if sufixo == "O" else "consolidado"
            item["fontes"] = {tipo_fonte: {"pdf": PDF_BCB % (ident, arq)}}
            item["pdf_bcb"] = {"arquivo": arq, "versao": versao, "sufixo": sufixo}
    return c


def gravar_htm_bcb(item, destino, conteudo=None):
    """Grava o campo Texto da API como .htm, com o mtime do cache da API (data da leitura, C5)."""
    if conteudo is None:
        conteudo = (_ler_api_bcb(item).get("conteudo") or [{}])[0]
    with open(destino, "w", encoding="utf-8") as f:
        f.write("<html><head><meta charset='utf-8'></head><body>%s</body></html>"
                % (conteudo.get("Texto") or ""))
    t = os.path.getmtime(item["cache_api"])
    os.utime(destino, (t, t))
    return destino


# ---------------------------------------------------------------- camada 5

def slug(texto, maximo=SLUG_MAX):
    s = unicodedata.normalize("NFKD", texto or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:maximo].rstrip("-")


def titulo_anbima(titulo):
    """Título sem "(vigente ...)"."""
    t = re.sub(r"\s*\(\s*vigente\b[^)]*\)", "", titulo or "", flags=re.I)
    return re.sub(r"\s+", " ", t).strip()


def titulo_b3(rotulo):
    """Rótulo sem "- Sem Marca(s)", "(.PDF, 2MB)", "*"; rótulo genérico de versão ("Versão em
    vigor", "versão 28/10/2024") vale como vazio (o slug sai do nome do arquivo)."""
    t = re.sub(r"\(\s*\.?\s*pdf\b[^)]*\)", "", rotulo or "", flags=re.I)
    t = re.sub(r"\s*[-–]\s*sem\s+marcas?\b\*?", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t.replace("*", " ")).strip(" -–")
    if re.match(r"^vers[aã]o\b", t, re.I):
        return ""
    return t


def tipo_b3(nome):
    n = slug(nome, 1000)
    if "regulamento" in n:
        return "regulamento"
    if "glossario" in n:
        return "glossario"
    return "manual"


def _data_last_modified(valor):
    try:
        d = email.utils.parsedate_to_datetime(valor)
    except (TypeError, ValueError, IndexError):
        return None
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001
        fuso = datetime.timezone(datetime.timedelta(hours=-3))
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(fuso).strftime("%Y-%m-%d")


def _cache_pdf(url, pasta):
    return os.path.join(pasta, "%s.pdf" % hashlib.sha1(url.encode("utf-8")).hexdigest()[:10])


def itens_camada5(anbima, b3, cache_pdf=None):
    """Itens da autorregulação: ANBIMA (situacao "vigente") e B3 (entra true), na ordem dos acervos."""
    cache_pdf = dict(CACHE_PDF, **(cache_pdf or {}))
    itens, usados = [], {"anbima": {}, "b3": {}}
    docs = [("anbima", d, anbima.get("lido_em")) for d in anbima.get("documentos", [])
            if d.get("situacao") == "vigente"]
    docs += [("b3", d, b3.get("lido_em")) for d in b3.get("documentos", []) if d.get("entra") is True]
    for orgao, d, lido_em in docs:
        nome_arq = re.sub(r"\.pdf$", "", d.get("arquivo") or "", flags=re.I)
        if orgao == "anbima":
            titulo = titulo_anbima(d.get("titulo"))
            tipo = TIPOS_ANBIMA.get(d.get("tipo"), "orientacao-autorregulacao")
        else:
            titulo = d.get("titulo") or titulo_b3((d.get("rotulos") or [""])[0])  # título curado no inventário
            tipo = tipo_b3(titulo + " " + nome_arq)
        base = slug(titulo) or slug(nome_arq) or "documento"
        avisos = []
        s, k = base, 1
        while s in usados[orgao]:
            k += 1
            suf = "-%d" % k
            s = base[:SLUG_MAX - len(suf)].rstrip("-") + suf
        if s != base:
            avisos.append("slug %r já usado por %s; este ficou %r" % (base, usados[orgao][base], s))
        usados[orgao][s] = d.get("arquivo") or d.get("url")
        if d.get("vigente_desde"):
            data, origem = d["vigente_desde"], "vigencia"
        elif d.get("data_nome"):
            data, origem = d["data_nome"], "versao"
        elif _data_last_modified(d.get("last_modified")):
            data, origem = _data_last_modified(d.get("last_modified")), "last-modified"
        else:
            data, origem = lido_em or DATA_BASE, "leitura"
        url = d["url"]
        itens.append({
            "id": "%s-%s" % (orgao, s), "orgao": orgao, "tipo": tipo, "numero": None,
            "data": data, "data_origem": origem, "dou": None, "ementa": titulo or nome_arq,
            "situacao": "vigente", "url_pagina": (d.get("paginas") or [url])[0],
            "fontes": {"ato": {"pdf": url}}, "alteradoras": [], "vigente_ate_ato": "",
            "arquivo": "autorregulacao/%s/%s.md" % (orgao, s), "notas": [], "avisos": avisos,
            "cache_pdf": _cache_pdf(url, cache_pdf[orgao]), "camada": 5,
        })
    return itens


def _revogadas_citadas(texto, revogadas):
    cit = ["%s CVM %s" % tuple(c.split(" ", 1)) for c in citadas(texto)]
    return [c for c in cit if c in set(revogadas)]


# ---------------------------------------------------------------- conversão

def sem_tachado(md):
    return re.sub(r"~~.*?~~", "", md)


def _celulas_md(linha):
    return [c.strip() for c in re.split(r"(?<!\\)\|", linha.strip())[1:-1]]


def _tabela_sem_tachado(linhas):
    """Linhas de uma tabela em pipes sem o tachado: some a linha que fica vazia; sem linhas, a tabela."""
    rows = []
    for i, ln in enumerate(linhas):
        cel = _celulas_md(ln)
        if i == 1 and all(re.fullmatch(r":?-{3,}:?", c) for c in cel):
            continue  # separador
        cel = [re.sub(r"\s{2,}", " ", sem_tachado(c)).strip() for c in cel]
        if any(c for c in cel):
            rows.append(cel)
    if not rows:
        return []
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows]
    out = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * n]
    return out + ["| " + " | ".join(r) + " |" for r in rows[1:]]


def sem_tachado_bcb(md):
    """Tachado fora do Markdown do html_bcb (redações revogadas no texto compilado do BCB):
    tira o trecho, a linha ou a linha de tabela que ficar vazia, e a tabela inteira se for o caso.
    Não mexe em bloco de código (texto de largura fixa, <pre>)."""
    out, tabela, cerca = [], [], False

    def fecha():
        out.extend(_tabela_sem_tachado(tabela))
        tabela.clear()

    for ln in md.split("\n"):
        if ln.startswith("```"):
            fecha()
            cerca = not cerca
            out.append(ln)
            continue
        if cerca:
            out.append(ln)
            continue
        if ln.startswith("|"):
            tabela.append(ln)
            continue
        fecha()
        if "~~" in ln:
            ln = re.sub(r" {2,}", " ", sem_tachado(ln)).strip()
            if not re.search(r"[^\W_]", ln):
                continue
        out.append(ln)
    fecha()
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n") + "\n"


def palavras(txt):
    """Palavras da métrica de cobertura: "_" separa (URLs do SEI, itálico do Markdown)."""
    return re.findall(r"[^\W_]+", txt.lower())


def cobertura(fonte_txt, md):
    a, b = Counter(palavras(fonte_txt)), Counter(palavras(md))
    total = sum(a.values())
    return round(sum(min(n, b[w]) for w, n in a.items()) / total, 4) if total else 0.0


def legibilidade(txt):
    """(fração de palavras legíveis, total de palavras). Legível: alfabética de 3+ letras, ou
    código de 4 a 14 maiúsculas ASCII e dígitos, com os dois (ticker, ISIN). Número puro fica fora da fração
    (tabela de negociação traz milhares), mas conta no total; fonte Type3 sem mapa sai como
    dígito solto ou símbolo e continua ilegível."""
    ps = re.findall(r"\w+", txt or "")
    if not ps:
        return 0.0, 0
    resto = [p for p in ps if not p.isdigit()]
    if not resto:
        return 0.0, len(ps)
    leg = sum(1 for p in resto if (p.isalpha() and len(p) >= 3) or
              (re.fullmatch(r"[A-Z0-9]{4,14}", p) and re.search(r"[A-Z]", p) and re.search(r"\d", p)))
    return round(leg / len(resto), 4), len(ps)


def motivo_sem_texto(txt, type3=False):
    """Motivo para não gravar o texto extraído de um PDF, ou None se ele é legível."""
    frac, n = legibilidade(txt)
    if n < PALAVRAS_MIN:
        return ("PDF sem camada de texto: %d palavras extraídas (mínimo %d); provável "
                "documento escaneado, só OCR resolve" % (n, PALAVRAS_MIN))
    if frac < LEGIBILIDADE_MIN:
        causa = ("fonte Type3 sem mapa Unicode" if type3 else
                 "codificação de fonte sem mapa Unicode ou texto embaralhado")
        return ("PDF ilegível: fração de palavras alfabéticas %.2f (mínimo %.2f) em %d palavras; "
                "%s, só OCR resolve" % (frac, LEGIBILIDADE_MIN, n, causa))
    return None


class SemTexto(Exception):
    def __init__(self, motivo, legibilidade, palavras):
        super().__init__(motivo)
        self.motivo, self.legibilidade, self.palavras = motivo, legibilidade, palavras


def _textutil(origem, formato, destino):
    subprocess.run(["textutil", "-convert", formato, "-output", destino, origem],
                   check=True, capture_output=True)
    return destino


def _pdf_txt(path):
    from pypdf import PdfReader  # dependência opcional
    return "\f".join(p.extract_text() or "" for p in PdfReader(path).pages)  # \f: página, como o PDFKit


def _pdfkit_txt(path):
    """Texto do PDF pelo PDFKit (macOS), ou None fora do macOS ou se ele falhar."""
    if sys.platform != "darwin":
        return None
    try:
        import pdf_macos
        return pdf_macos.texto_pdfkit(path)
    except Exception:  # noqa: BLE001 — cai no pypdf
        return None


def _ocr(path):
    """(texto, [confiança média por página]) pelo Vision (macOS), ou None fora dele ou se falhar."""
    if sys.platform != "darwin":
        return None
    try:
        import pdf_macos
        return pdf_macos.ocr(path)
    except Exception:  # noqa: BLE001 — fica sem-texto
        return None


def normalizar_pdf(txt):
    """NFKC do texto extraído de PDF (ligaduras ﬁ/ﬂ, espaço não separável), preservando º e ª,
    que o NFKC trocaria por "o" e "a" ("nº", "1º")."""
    return "".join(p if p in ("º", "ª") else unicodedata.normalize("NFKC", p)
                   for p in re.split("([ºª])", txt or ""))


def _md_pdf(txt):
    linhas = [re.sub(r"\s+", " ", x).strip() for x in txt.replace("\f", "\n").split("\n")]
    return "\n\n".join(x for x in linhas if x)


def _fmt(x):
    return ("%.2f" % x).replace(".", ",")


# Página de registro das assinaturas eletrônicas (PDFs assinados da ANBIMA): nome, e-mail, IP e
# localização de quem assinou. Dado pessoal, fora do texto da norma: corta-se do marcador ao fim.
MARCA_ASSINATURAS = re.compile(r"(?m)^.*Escaneie para realizar a valida[çc][ãa]o das assinaturas.*$")


def sem_registro_de_assinaturas(txt):
    """(texto sem a página de registro das assinaturas eletrônicas, cortou?)."""
    if txt is None:
        return None, False
    m = MARCA_ASSINATURAS.search(txt)
    return (txt[:m.start()].rstrip() + "\n", True) if m else (txt, False)


def converter_pdf(path, limpar=None, legivel=None):
    """(markdown, texto de conferência, conferência independente?); PDF ilegível tenta OCR e,
    sem OCR aceito, levanta SemTexto. Grava o extrator e o OCR em converter_fonte.extras.
    A página de registro das assinaturas eletrônicas sai dos dois textos (norma e conferência);
    `limpar(txt)` (PDF do BCB: cabeçalho, rodapé e aviso do DOU) também se aplica aos dois;
    `legivel(txt)`: o texto sobre o qual se mede a legibilidade (padrão: o próprio)."""
    legivel = legivel or (lambda t: t)
    kit = _pdfkit_txt(path)
    try:
        pyp = _pdf_txt(path)
    except ImportError:
        if kit is None:
            raise
        pyp = None
    kit = None if kit is None else normalizar_pdf(kit)
    pyp = None if pyp is None else normalizar_pdf(pyp)
    kit, corte_kit = sem_registro_de_assinaturas(kit)
    pyp, corte_pyp = sem_registro_de_assinaturas(pyp)
    if limpar:
        kit, pyp = limpar(kit), limpar(pyp)
    for nome, txt, conf in (("pdfkit", kit, pyp), ("pypdf", pyp, None)):
        if txt is not None and motivo_sem_texto(legivel(txt)) is None:
            converter_fonte.extras = {"extrator": nome, "legibilidade": legibilidade(legivel(txt)),
                                      "assinaturas_retiradas": corte_kit or corte_pyp}
            return _md_pdf(txt), (txt if conf is None else conf), conf is not None
    base = pyp if pyp is not None else kit
    frac, n = legibilidade(base)
    motivo = motivo_sem_texto(base, type3=False)
    if n >= PALAVRAS_MIN:
        motivo = motivo_sem_texto(base, type3=_pdf_type3(path))
    r = _ocr(path)
    if r is not None:
        txt, conf = normalizar_pdf(r[0]), list(r[1])
        media = sum(conf) / len(conf) if conf else 0.0
        n_ocr = legibilidade(txt)[1]
        if conf and media >= OCR_CONFIANCA_MIN and n_ocr >= PALAVRAS_MIN:
            converter_fonte.extras = {
                "extrator": "ocr", "legibilidade": legibilidade(txt),
                "ocr": {"media": round(media, 4), "minima": round(min(conf), 4), "paginas": len(conf)}}
            return _md_pdf(txt), txt, False
        motivo += ("; OCR recusado: confiança média %s (mínimo %s), %d palavras (mínimo %d)"
                   % (_fmt(media), _fmt(OCR_CONFIANCA_MIN), n_ocr, PALAVRAS_MIN))
    raise SemTexto(motivo, frac, n)


def data_arquivo(path):
    """AAAA-MM-DD do mtime do arquivo no fuso de São Paulo (data do download da fonte)."""
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001 — sem base de fusos: UTC-3 (sem horário de verão desde 2019)
        fuso = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.fromtimestamp(os.path.getmtime(path), fuso).strftime("%Y-%m-%d")


def _pdf_type3(path):
    """O PDF usa fonte Type3 sem /ToUnicode? (False se o pypdf não conseguir dizer.)"""
    try:
        from pypdf import PdfReader
        for pagina in PdfReader(path).pages:
            fontes = (pagina.get("/Resources") or {}).get("/Font") or {}
            for ref in fontes.values():
                f = ref.get_object()
                if f.get("/Subtype") == "/Type3" and "/ToUnicode" not in f:
                    return True
    except Exception:  # noqa: BLE001 — diagnóstico auxiliar, não decide nada
        return False
    return False


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extras_docx(path):
    """(notas de rodapé, palavras em caixas de texto) de um DOCX.

    As notas vêm na ordem de exibição (ordem_das_notas: a primeira referência no texto), a mesma
    da âncora [k] de docx_para_md(notas=True); nota sem referência e com texto vai para o fim.
    Ficam de fora as notas especiais do Word (separadores, w:type) e as vazias sem referência.
    As palavras de caixa contam cada caixa uma vez (mc:AlternateContent grava duas cópias)."""
    import xml.etree.ElementTree as ET
    textos = {}
    with zipfile.ZipFile(path) as z:
        nomes = z.namelist()
        if "word/footnotes.xml" in nomes:
            for fn in ET.fromstring(z.read("word/footnotes.xml")).iter(W + "footnote"):
                if int(fn.get(W + "id", "0")) <= 0 or fn.get(W + "type", "normal") != "normal":
                    continue  # separadores
                textos[fn.get(W + "id")] = re.sub(
                    r"\s+", " ", "".join(t.text or "" for t in fn.iter(W + "t"))).strip()
        doc = ET.fromstring(z.read("word/document.xml"))
    ordem = [k for k in ordem_das_notas(doc) if k in textos]
    ordem += [k for k in textos if k not in ordem and textos[k]]
    notas = [textos[k] or "(nota sem texto no arquivo da CVM)" for k in ordem]
    caixa = sum(len(re.findall(r"\w+", t)) for t in textos_das_caixas(doc))
    return notas, caixa


def secao_notas(notas):
    if not notas:
        return ""
    return "\n\n## Notas de rodapé\n\n" + "\n\n".join(
        "[%d] %s" % (i, n) for i, n in enumerate(notas, 1)) + "\n"


def texto_conferencia(path, ext):
    """Texto da fonte pelo `textutil` (conversor independente do nosso)."""
    with tempfile.TemporaryDirectory() as d:
        with open(_textutil(path, "txt", os.path.join(d, "f.txt")), encoding="utf-8",
                  errors="replace") as f:
            return f.read()


def _texto_html(html):
    """Texto simples do HTML, para a métrica quando não há `textutil` (não é conferência independente)."""
    import html as htmllib
    t = re.sub(r"(?is)<(style|script|title|head)\b.*?</\1\s*>", " ", html)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", t))


def converter_html_bcb(path):
    """(markdown, texto de conferência, conferência independente?) do HTML da API do BCB."""
    with open(path, encoding="utf-8", errors="replace") as f:
        html = f.read()
    md = html_bcb.html_para_md(html)
    frac, n = legibilidade(md)
    if n < PALAVRAS_MIN_HTML:
        raise SemTexto("HTML do BCB sem texto: %d palavras (mínimo %d)" % (n, PALAVRAS_MIN_HTML), frac, n)
    converter_fonte.extras = {}
    if shutil.which("textutil"):
        return md, texto_conferencia(path, "htm"), True
    return md, _texto_html(html), False


def converter_fonte(path, ext, conversor=None, limpar=None, legivel=None):
    """(markdown, texto da fonte para conferência, conferência independente?).
    PDF ilegível sem OCR aceito levanta SemTexto. `conversor` "html_bcb": HTML da API do BCB;
    `limpar` e `legivel`: limpeza e prova de legibilidade do texto do PDF (converter_pdf)."""
    if conversor == "html_bcb":
        return converter_html_bcb(path)
    if ext == "pdf":
        return converter_pdf(path, limpar, legivel) if limpar or legivel else converter_pdf(path)
    if ext == "docx" and not zipfile.is_zipfile(path):
        ext = "doc"  # Word 97 servido com nome .docx: passa pelo textutil
    with tempfile.TemporaryDirectory() as d:
        docx = path if ext == "docx" else _textutil(path, "docx", os.path.join(d, "f.docx"))
        md = docx_para_md(docx, caixas=True, notas=True)
        notas, caixa = extras_docx(docx)
    frac, n = legibilidade(md)
    if n == 0 or frac < LEGIBILIDADE_MIN_WORD:  # ato curto existe: aqui não há mínimo de palavras
        raise SemTexto("%s sem texto legível: %d palavras, fração alfabética %.2f (ex.: RTF com a "
                       "página escaneada embutida como imagem)" % (ext.upper(), n, frac), frac, n)
    converter_fonte.extras = {"notas": len(notas), "caixa": caixa}
    return md + secao_notas(notas), texto_conferencia(path, ext), True


def _baixar(url, destino):
    import urllib.request
    if not (os.path.exists(destino) and os.path.getsize(destino)):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r:
            corpo = r.read()
        with open(destino, "wb") as f:
            f.write(corpo)
        time.sleep(0.7)
    return destino


# ---------------------------------------------------------------- frontmatter

def _data_por_extenso(txt):
    m = re.search(r"(\d{1,2})\s*[º°o]?\s+de\s+([a-zç]+)\s+de\s+(\d{4})", txt, re.I)
    if m and m.group(2).lower() in MESES:
        return "%s-%02d-%02d" % (m.group(3), MESES[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", txt)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    return None


def vigencia(corpo):
    """(data do primeiro bloco "vigente a partir de" ou None, [demais datas distintas], há bloco?)."""
    datas = []
    for m in MARCA_VIGENCIA.finditer(corpo):
        datas.append(_data_por_extenso(corpo[m.end():].split("\n", 1)[0]))
    if not datas:
        return None, [], False
    validas = [d for d in datas if d]
    primeira = validas[0] if validas else None
    return primeira, sorted({d for d in validas if d != primeira}), True


def _e(lista):
    return lista[0] if len(lista) == 1 else "%s e %s" % (", ".join(lista[:-1]), lista[-1])


def _versao_bcb(v):
    """"versão N da busca de normas" (VersaoNormativo da API, C5), ou a busca sem número de versão."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "busca de normas, sem número de versão"
    return "versão %s da busca de normas" % (int(f) if f == int(f) else f)


DATA_ORIGEM = {
    "vigencia": "vigente a partir de %s, segundo a página da entidade",
    "versao": "versão de %s",
    "last-modified": "data %s do cabeçalho Last-Modified do PDF [verificar a vigência]",
    "leitura": "sem data no documento nem na página; %s é a data da leitura da página [verificar]",
}


def _abertura(item, tipo_fonte, ext, baixado_em):
    """Primeira frase do `incerteza`, por órgão."""
    orgao = item.get("orgao", "cvm")
    if orgao in ("cmn", "bcb"):
        versao = _versao_bcb(item.get("versao"))
        if ext != "pdf":
            return ("Texto vigente compilado pelo BCB (%s), convertido por script "
                    "do HTML, data-base %s; sem histórico de redações nem conferência contra o DOU."
                    % (versao, baixado_em))
        arq = (item.get("pdf_bcb") or {}).get("arquivo", "")
        if tipo_fonte == "ato":
            return ("Texto do ato original (PDF %s do BCB, %s), extraído por script "
                    "do PDF, data-base %s; o BCB não publica o texto em HTML: [verificar] alterações "
                    "posteriores não aplicadas; sem histórico de redações nem conferência contra o DOU."
                    % (arq, versao, baixado_em))
        return ("Texto vigente compilado pelo BCB (PDF %s, %s), extraído por script "
                "do PDF, data-base %s; sem histórico de redações nem conferência contra o DOU."
                % (arq, versao, baixado_em))
    if orgao in NOMES:
        nome = NOMES[orgao]
        quando = DATA_ORIGEM.get(item.get("data_origem"), DATA_ORIGEM["leitura"]) % item["data"]
        return ("Documento de autorregulação da %s (%s), extraído por script do PDF, data-base %s. "
                "Vincula só as instituições aderentes ou participantes. Texto de titularidade da %s, "
                "reproduzido para uso informativo; retirado a pedido (ver autorregulacao/README.md)."
                % (nome, quando, baixado_em, nome))
    situacao = item.get("situacao", "vigente")
    texto = "Texto vigente" if situacao == "vigente" else "Texto"
    return ("%s convertido por script de %s %s da CVM, data-base %s, sem histórico de redações "
            "nem conferência ato a ato." % (texto, tipo_fonte, ext.upper(), baixado_em))


def incertezas(item, tipo_fonte, ext, sem_dou, vig, baixado_em=None, ocr=None):
    situacao = item.get("situacao", "vigente")
    out = [_abertura(item, tipo_fonte, ext, baixado_em or DATA_BASE)]
    if tipo_fonte == "ato" and item.get("alteradoras"):
        out.append("A CVM não publica consolidado desta norma: o texto é o do ato original; "
                   "[verificar] alterações de %s não aplicadas." % _e([str(a) for a in item["alteradoras"]]))
    if ext == "pdf":
        out.append("Extraído de PDF: quebras de linha, tabelas e numeração podem estar "
                   "deslocadas [verificar].")
    if ocr:
        out.append("Texto por OCR (confiança média %s, mínima %s por página); erros pontuais de "
                   "reconhecimento são esperados [verificar no PDF oficial]."
                   % (_fmt(ocr["media"]), _fmt(ocr["minima"])))
    if situacao == "nao-informada":
        out.append("A CVM não publica a vigência de %s; este texto pode tratar de norma já revogada."
                   % NAO_INFORMADA.get(item["tipo"], "atos deste tipo"))
        if item.get("revogadas_citadas"):
            out.append("A descrição cita norma revogada: %s." % _e(item["revogadas_citadas"]))
    if sem_dou and item.get("orgao", "cvm") not in NOMES:
        out.append("Sem publicação no DOU informada pel%s; publicacao_dou repete a data do ato."
                   % ("o BCB" if item.get("orgao") in ("cmn", "bcb") else "a CVM"))
    primeira, outras, ha_bloco = vig
    if ha_bloco and not primeira:
        out.append('[verificar] bloco "vigente a partir de" sem data reconhecida pelo script.')
    if outras:
        out.append('Outros blocos "vigente a partir de" com datas diferentes: %s.' % _e(outras))
    out += item.get("notas", [])
    return " ".join(out)


def frontmatter(item, tipo_fonte, ext, url, sha, corpo, baixado_em=None, ocr=None):
    orgao = item.get("orgao", "cvm")
    autorregulacao = orgao in NOMES
    # "vigente a partir de" é bloco dos consolidados da CVM; nos outros órgãos não se lê
    vig = vigencia(corpo) if orgao == "cvm" else (None, [], False)
    baixado_em = baixado_em or DATA_BASE
    sem_dou = not item.get("dou")
    v = {
        "id": item["id"], "orgao": orgao, "tipo": item["tipo"],
        "numero": "" if item.get("numero") is None or autorregulacao else item["numero"],
        "data": item["data"],
        "publicacao_dou": "" if autorregulacao else (item.get("dou") or item["data"]),
        "ementa": item["ementa"], "situacao": item.get("situacao", "vigente"),
        "versao_texto": "consolidado" if tipo_fonte == "consolidado" else "original",
        "vigente_ate_ato": item.get("vigente_ate_ato", "") if tipo_fonte == "consolidado" else "",
        "aguarda_consolidado_oficial": "false", "historico_parcial": "true",
        "fonte_original": (item.get("fonte_original")
                           or item.get("fontes", {}).get("ato", {}).get("pdf") or url),
        "fonte_consolidada": url, "sha256_fonte": sha, "baixado_em": baixado_em,
        "verificado_em": DATA_BASE,
        "incerteza": incertezas(item, tipo_fonte, ext, sem_dou, vig, baixado_em, ocr),
    }
    pares = [(c, v[c]) for c in CAMPOS]
    if vig[0]:
        pares.append(("vigencia_inicio", vig[0]))
    pares.append(("nivel_verificacao", nivel_verificacao(tipo_fonte, ext, ocr=bool(ocr))))
    return "---\n" + "\n".join(("%s: %s" % (k, x)) if x != "" else "%s:" % k
                               for k, x in pares) + "\n---\n\n"


def montar(item, path, tipo_fonte, ext, url):
    """(markdown com frontmatter, relatório). PDF ilegível levanta SemTexto."""
    converter_fonte.extras = {}
    conversor = item.get("conversor")
    if ext == "pdf" and item.get("orgao") in ("cmn", "bcb") and item.get("numero") is not None:
        numero = item["numero"]
        md, txt, independente = converter_fonte(path, ext, limpar=lambda t: bcb_versoes.limpar_pdf(t, numero),
                                                legivel=bcb_versoes.texto_legivel)
    else:
        md, txt, independente = (converter_fonte(path, ext, conversor) if conversor
                                 else converter_fonte(path, ext))
    extras = converter_fonte.extras
    if extras.get("caixa"):
        item = dict(item, notas=item.get("notas", []) + [
            "O arquivo da CVM tem %d palavras em caixas de texto (diagramas), que estão como texto "
            "em blocos \"[Diagrama]\", sem o desenho (setas e posição perdidas) "
            "[verificar no original]." % extras["caixa"]])
    if extras.get("notas"):
        item = dict(item, notas=item.get("notas", []) + [
            "As %d notas de rodapé do arquivo da CVM estão na seção final \"Notas de rodapé\"."
            % extras["notas"]])
    if extras.get("assinaturas_retiradas"):
        item = dict(item, notas=item.get("notas", []) + [
            "A página final de registro das assinaturas eletrônicas do PDF (nomes, e-mails, IP e "
            "localização dos signatários) foi retirada; a validação das assinaturas é feita no PDF oficial."])
    limpar = sem_tachado_bcb if conversor == "html_bcb" else sem_tachado
    tachado = len(palavras(md)) - len(palavras(limpar(md)))
    corpo = normalizar_artigos(limpar(md) if tipo_fonte == "consolidado" else md)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    baixado_em, ocr = data_arquivo(path), extras.get("ocr")
    cab = frontmatter(item, tipo_fonte, ext, url, sha, corpo, baixado_em, ocr)
    rel = {"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "resultado": "ok",
           "nivel_verificacao": nivel_verificacao(tipo_fonte, ext, ocr=bool(ocr)),
           "artigos": len(re.findall(r"(?m)^## Art\. ", corpo)),
           "linhas": corpo.count("\n") + 1, "tabelas": len(re.findall(r"(?m)^\|.*\|\s*$\n(?!\|)", corpo)),
           "cobertura": cobertura(txt, md), "palavras_tachadas": tachado,
           "conferencia_independente": independente, "caracteres": len(corpo),
           "palavras_em_caixa_de_texto": extras.get("caixa", 0), "notas_de_rodape": extras.get("notas", 0)}
    rel["baixado_em"] = baixado_em
    if item.get("versao_bcb"):
        rel["versao_bcb"] = item["versao_bcb"]
    if item.get("avisos"):
        rel["avisos"] = list(item["avisos"])
    if ext == "pdf":
        rel["extrator"] = extras.get("extrator")
        rel["legibilidade"], rel["palavras"] = extras.get("legibilidade") or legibilidade(txt)
        if ocr:
            rel["ocr_confianca_media"], rel["ocr_confianca_minima"] = (
                round(ocr["media"], 4), round(ocr["minima"], 4))
            rel["ocr_paginas"] = ocr["paginas"]
    return cab + corpo.strip() + "\n", rel


# ---------------------------------------------------------------- lote

def obter_fonte(item, tipo_fonte, ext, url, cache, conteudo_api=None):
    """Caminho local da fonte: o .htm gravado do cache da API do BCB (html_bcb), o PDF do cache
    da autorregulação (cópia com o mtime, que é a data do download) ou o download."""
    destino = os.path.join(cache, "%s.%s" % (item["id"], ext))
    if item.get("conversor") == "html_bcb" and ext == "htm":
        return gravar_htm_bcb(item, destino, conteudo_api)
    origem = item.get("cache_pdf")
    if ext == "pdf" and origem and os.path.exists(origem) and os.path.getsize(origem) \
            and not (os.path.exists(destino) and os.path.getsize(destino)):
        shutil.copy2(origem, destino)
    return _baixar(url, destino)


def processar(itens, saida, cache, mostrar=False):
    """Converte cada item e grava em <saida>/<arquivo>; devolve o relatório (lista)."""
    os.makedirs(cache, exist_ok=True)
    relatorio = []

    def registra(rel):
        relatorio.append(rel)
        if mostrar:
            print(json.dumps(rel, ensure_ascii=False))

    for item in itens:
        t0 = time.time()
        item = dict(item)
        base = {"id": item["id"], "arquivo": item["arquivo"]}
        conteudo_api = None
        if item.get("cache_api"):
            try:
                conteudo_api = preparar_bcb(item)
            except Exception as e:  # noqa: BLE001 — registra e segue
                registra(dict(base, resultado="erro", erro=("API do BCB: %s: %s" % (type(e).__name__, e))[:200]))
                continue
        if item.get("sem_texto_motivo"):
            registra(dict(base, resultado="sem-texto", motivo=item["sem_texto_motivo"]))
            continue
        candidatas = fontes_candidatas(item.get("fontes"))
        if not candidatas:
            relatorio.append({"id": item["id"], "resultado": "erro", "erro": "sem fonte"})
            continue
        tentativas = []
        try:
            for i, (tipo_fonte, ext, url) in enumerate(candidatas):
                base = {"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "arquivo": item["arquivo"]}
                try:
                    path = obter_fonte(item, tipo_fonte, ext, url, cache, conteudo_api)
                    md, rel = montar(item, path, tipo_fonte, ext, url)
                    break
                except SemTexto as e:
                    tentativas.append("%s %s: %s" % (tipo_fonte, ext, e.motivo))
                    if i == len(candidatas) - 1:
                        raise
            if tentativas:
                rel["fontes_descartadas"] = tentativas
        except SemTexto as e:
            rel = dict(base, resultado="sem-texto", motivo=" | ".join(tentativas) or e.motivo,
                       legibilidade=e.legibilidade, palavras=e.palavras)
            relatorio.append(rel)
            if mostrar:
                print(json.dumps(rel, ensure_ascii=False))
            continue
        except Exception as e:  # noqa: BLE001 — registra e segue
            rel = dict(base, resultado="erro", erro=("%s: %s" % (type(e).__name__, e))[:200])
            relatorio.append(rel)
            if mostrar:
                print(json.dumps(rel, ensure_ascii=False))
            continue
        destino = os.path.join(saida, item["arquivo"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(md)
        rel["segundos"] = round(time.time() - t0, 1)
        rel["arquivo"] = item["arquivo"]
        relatorio.append(rel)
        if mostrar:
            print(json.dumps(rel, ensure_ascii=False))
    return relatorio


def resumo(relatorio):
    res = Counter(r.get("resultado", "ok") for r in relatorio)
    conferidos = [r["cobertura"] for r in relatorio
                  if r.get("resultado") == "ok" and r.get("conferencia_independente")]
    baixa = [r["id"] for r in relatorio if r.get("resultado") == "ok"
             and r.get("conferencia_independente") and r["cobertura"] < 0.99]
    linhas = ["itens: %d %s" % (len(relatorio), dict(res)),
              "cobertura mínima (conferência independente): %s" % (min(conferidos) if conferidos else "n/a"),
              "abaixo de 99%%: %s" % (", ".join(baixa) or "nenhum")]
    for r in relatorio:
        if r.get("resultado") in ("erro", "sem-texto"):
            linhas.append("  %s %s: %s" % (r["resultado"], r["id"], r.get("erro") or r.get("motivo")))
    for r in relatorio:
        for a in r.get("avisos", []):
            linhas.append("  aviso %s: %s" % (r["id"], a))
    return "\n".join(linhas)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("itens", nargs="?", help="itens.json (modo do piloto)")
    ap.add_argument("pasta", nargs="?", help="pasta de saída (modo do piloto)")
    ap.add_argument("--camada", type=int, choices=(1, 2, 4, 5))
    ap.add_argument("--acervo", default="fontes/acervo.json")
    ap.add_argument("--perimetro", default="fontes/perimetro-camada4.json")
    ap.add_argument("--acervo-bcb", default="fontes/acervo-bcb.json")
    ap.add_argument("--cache-bcb", default=CACHE_BCB, help="JSON da API do BCB por norma")
    ap.add_argument("--acervo-anbima", default="fontes/acervo-anbima.json")
    ap.add_argument("--acervo-b3", default="fontes/acervo-b3.json")
    ap.add_argument("--cache-anbima", default=CACHE_PDF["anbima"])
    ap.add_argument("--cache-b3", default=CACHE_PDF["b3"])
    ap.add_argument("--saida", default="plugins/normas/normas")
    ap.add_argument("--limite", type=int, help="só os N primeiros itens")
    ap.add_argument("--cache", help="padrão: dados/texto-vigente-fontes (camada) ou <pasta>/fontes")
    ap.add_argument("--relatorio", help="padrão: dados/texto-vigente-camada-N.json")
    args = ap.parse_args(argv[1:])
    def ler(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)

    if args.camada in (4, 5):
        acervo = ({"perimetro": ler(args.perimetro), "bcb": ler(args.acervo_bcb)} if args.camada == 4
                  else {"anbima": ler(args.acervo_anbima), "b3": ler(args.acervo_b3)})
        itens = itens_do_acervo(acervo, args.camada, cache_bcb=args.cache_bcb,
                                cache_pdf={"anbima": args.cache_anbima, "b3": args.cache_b3})
    if args.camada:
        if args.camada in (1, 2):
            itens = itens_do_acervo(ler(args.acervo), args.camada)
        saida, cache = args.saida, args.cache or "dados/texto-vigente-fontes"
        destino_rel = args.relatorio or "dados/texto-vigente-camada-%d.json" % args.camada
    elif args.itens and args.pasta:
        with open(args.itens, encoding="utf-8") as f:
            itens = json.load(f)
        saida, cache = args.pasta, args.cache or os.path.join(args.pasta, "fontes")
        destino_rel = args.relatorio or os.path.join(args.pasta, "relatorio.json")
    else:
        ap.print_help()
        return 2
    if args.limite:
        itens = itens[:args.limite]
    relatorio = processar(itens, saida, cache, mostrar=True)
    os.makedirs(os.path.dirname(os.path.abspath(destino_rel)), exist_ok=True)
    with open(destino_rel, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(resumo(relatorio))
    print("-> %s" % destino_rel)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
