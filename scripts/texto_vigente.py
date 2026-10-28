#!/usr/bin/env python3
"""Texto vigente por script (Fase 2b): da fonte oficial da CVM ao Markdown da SPEC, sem LLM.

Fonte, na ordem: consolidado DOCX > DOC > HTM > ato DOCX > DOC > HTM > PDF.
- DOCX: converter.docx_para_md.
- DOC e HTM: convertidos para DOCX pelo `textutil` do macOS e depois como DOCX.
- PDF: pypdf (dependência opcional, fora da biblioteca padrão); nível de verificação menor.
  PDF ilegível (fração de palavras alfabéticas de 3+ letras abaixo de 0,5, ou menos de 50
  palavras: fonte Type3 sem mapa Unicode, escaneado) não vira arquivo; o relatório marca
  `sem-texto` com o motivo.
No consolidado, texto tachado (~~...~~, redação antiga) sai; no ato, fica marcado (num
Documento de Revisão de CPC o tachado é o trecho excluído, conteúdo do ato). As notas de
alteração do consolidado ficam, como nas leis, porque não há histórico de commits que as substitua.

Conferência independente: o texto da fonte extraído pelo `textutil -convert txt` (DOCX,
DOC, HTM) ou pelo próprio pypdf (PDF, sem conferência independente) contra o Markdown;
`cobertura` = fração das palavras da fonte presentes no Markdown convertido, antes de tirar
o tachado (multiconjunto); `palavras_tachadas` = quantas palavras estão em texto tachado.

Frontmatter: campos de validar.CAMPOS, na ordem, mais `vigencia_inicio` (só com bloco
"vigente a partir de") e `nivel_verificacao` (consolidado-convertido, ato-convertido ou
pdf-extraido). Resoluções e Instruções: `situacao: vigente`; Pareceres e Ofícios-Circulares:
`nao-informada` (a CVM não publica a vigência deles).

Uso:
  python3 scripts/texto_vigente.py --camada 1|2 [--acervo fontes/acervo.json]
      [--saida plugins/normas/normas] [--limite N] [--cache DIR] [--relatorio ARQ]
    camada 1: Resoluções vigentes mais a 249, menos as 8 do núcleo, e Instruções vigentes;
    camada 2: os Pareceres de Orientação e os Ofícios-Circulares desde 2022-01-01.
    Relatório em dados/texto-vigente-camada-N.json; fontes baixadas em dados/texto-vigente-fontes/.
  python3 scripts/texto_vigente.py <itens.json> <pasta de saída>   (modo do piloto)
    itens.json: lista de {id, tipo, numero, data, dou, ementa, situacao, url_pagina, arquivo,
    fontes: {consolidado: {ext: url}, ato: {ext: url}}, alteradoras, vigente_ate_ato};
    relatório em <pasta de saída>/relatorio.json, fontes em <pasta de saída>/fontes/.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import docx_para_md, normalizar_artigos  # noqa: E402
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
# DOCX/DOC: texto curto em português fica perto de 0,45 ("de", "o", "1º"); lixo binário, perto de 0,2
LEGIBILIDADE_MIN_WORD = 0.3
NAO_INFORMADA = {
    "parecer-orientacao": "pareceres de orientação",
    "oficio-circular": "ofícios-circulares",
}
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


def nivel_verificacao(tipo_fonte, ext):
    if ext == "pdf":
        return "pdf-extraido"
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


def itens_do_acervo(acervo, camada):
    """Itens prontos para `processar`, a partir de fontes/acervo.json.

    Camada 1: Resoluções vigentes e as de INCLUIR_FORA_DO_ESTOQUE, menos o NUCLEO; Instruções
    vigentes. Camada 2: Pareceres de Orientação (todos) e Ofícios-Circulares desde CORTE_OFICIOS.
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
    else:
        raise ValueError("camada deve ser 1 ou 2, veio %r" % camada)
    return itens


def _revogadas_citadas(texto, revogadas):
    cit = ["%s CVM %s" % tuple(c.split(" ", 1)) for c in citadas(texto)]
    return [c for c in cit if c in set(revogadas)]


# ---------------------------------------------------------------- conversão

def sem_tachado(md):
    return re.sub(r"~~.*?~~", "", md)


def palavras(txt):
    return re.findall(r"\w+", txt.lower())


def cobertura(fonte_txt, md):
    a, b = Counter(palavras(fonte_txt)), Counter(palavras(md))
    total = sum(a.values())
    return round(sum(min(n, b[w]) for w, n in a.items()) / total, 4) if total else 0.0


def legibilidade(txt):
    """(fração de palavras alfabéticas de 3+ letras sobre o total, total de palavras)."""
    ps = re.findall(r"\w+", txt or "")
    if not ps:
        return 0.0, 0
    alfa = sum(1 for p in ps if p.isalpha() and len(p) >= 3)
    return round(alfa / len(ps), 4), len(ps)


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
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


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
    """(notas de rodapé, palavras em caixas de texto) de um DOCX; o converter ignora os dois."""
    import xml.etree.ElementTree as ET
    notas, caixa = [], 0
    with zipfile.ZipFile(path) as z:
        nomes = z.namelist()
        if "word/footnotes.xml" in nomes:
            for fn in ET.fromstring(z.read("word/footnotes.xml")).iter(W + "footnote"):
                if int(fn.get(W + "id", "0")) <= 0:
                    continue  # separadores
                txt = re.sub(r"\s+", " ", "".join(t.text or "" for t in fn.iter(W + "t"))).strip()
                if txt:
                    notas.append(txt)
        doc = ET.fromstring(z.read("word/document.xml"))
        for tx in doc.iter(W + "txbxContent"):
            caixa += len(re.findall(r"\w+", " ".join(t.text or "" for t in tx.iter(W + "t"))))
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


def converter_fonte(path, ext):
    """(markdown, texto da fonte para conferência, conferência independente?).
    PDF ilegível levanta SemTexto."""
    if ext == "pdf":
        txt = _pdf_txt(path)
        motivo = motivo_sem_texto(txt, type3=False)
        if motivo:
            frac, n = legibilidade(txt)
            if n >= PALAVRAS_MIN:
                motivo = motivo_sem_texto(txt, type3=_pdf_type3(path))
            raise SemTexto(motivo, frac, n)
        linhas = [re.sub(r"\s+", " ", x).strip() for x in txt.split("\n")]
        return "\n\n".join(x for x in linhas if x), txt, False
    if ext == "docx" and not zipfile.is_zipfile(path):
        ext = "doc"  # Word 97 servido com nome .docx: passa pelo textutil
    with tempfile.TemporaryDirectory() as d:
        docx = path if ext == "docx" else _textutil(path, "docx", os.path.join(d, "f.docx"))
        md = docx_para_md(docx)
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


def incertezas(item, tipo_fonte, ext, sem_dou, vig):
    situacao = item.get("situacao", "vigente")
    texto = "Texto vigente" if situacao == "vigente" else "Texto"
    out = ["%s convertido por script de %s %s da CVM, data-base %s, sem histórico de redações "
           "nem conferência ato a ato." % (texto, tipo_fonte, ext.upper(), DATA_BASE)]
    if tipo_fonte == "ato" and item.get("alteradoras"):
        out.append("A CVM não publica consolidado desta norma: o texto é o do ato original; "
                   "[verificar] alterações de %s não aplicadas." % _e([str(a) for a in item["alteradoras"]]))
    if ext == "pdf":
        out.append("Extraído de PDF: quebras de linha, tabelas e numeração podem estar "
                   "deslocadas [verificar].")
    if situacao == "nao-informada":
        out.append("A CVM não publica a vigência de %s; este texto pode tratar de norma já revogada."
                   % NAO_INFORMADA.get(item["tipo"], "atos deste tipo"))
        if item.get("revogadas_citadas"):
            out.append("A descrição cita norma revogada: %s." % _e(item["revogadas_citadas"]))
    if sem_dou:
        out.append("Sem publicação no DOU informada pela CVM; publicacao_dou repete a data do ato.")
    primeira, outras, ha_bloco = vig
    if ha_bloco and not primeira:
        out.append('[verificar] bloco "vigente a partir de" sem data reconhecida pelo script.')
    if outras:
        out.append('Outros blocos "vigente a partir de" com datas diferentes: %s.' % _e(outras))
    out += item.get("notas", [])
    return " ".join(out)


def frontmatter(item, tipo_fonte, ext, url, sha, corpo):
    vig = vigencia(corpo)
    sem_dou = not item.get("dou")
    v = {
        "id": item["id"], "orgao": "cvm", "tipo": item["tipo"],
        "numero": "" if item.get("numero") is None else item["numero"],
        "data": item["data"], "publicacao_dou": item.get("dou") or item["data"],
        "ementa": item["ementa"], "situacao": item.get("situacao", "vigente"),
        "versao_texto": "consolidado" if tipo_fonte == "consolidado" else "original",
        "vigente_ate_ato": item.get("vigente_ate_ato", "") if tipo_fonte == "consolidado" else "",
        "aguarda_consolidado_oficial": "false", "historico_parcial": "true",
        "fonte_original": item.get("fontes", {}).get("ato", {}).get("pdf") or url,
        "fonte_consolidada": url, "sha256_fonte": sha, "baixado_em": DATA_BASE,
        "verificado_em": DATA_BASE, "incerteza": incertezas(item, tipo_fonte, ext, sem_dou, vig),
    }
    pares = [(c, v[c]) for c in CAMPOS]
    if vig[0]:
        pares.append(("vigencia_inicio", vig[0]))
    pares.append(("nivel_verificacao", nivel_verificacao(tipo_fonte, ext)))
    return "---\n" + "\n".join(("%s: %s" % (k, x)) if x != "" else "%s:" % k
                               for k, x in pares) + "\n---\n\n"


def montar(item, path, tipo_fonte, ext, url):
    """(markdown com frontmatter, relatório). PDF ilegível levanta SemTexto."""
    converter_fonte.extras = {}
    md, txt, independente = converter_fonte(path, ext)
    extras = converter_fonte.extras
    if extras.get("caixa"):
        item = dict(item, notas=item.get("notas", []) + [
            "O arquivo da CVM tem %d palavras em caixas de texto (diagramas), não convertidas "
            "[verificar no original]." % extras["caixa"]])
    if extras.get("notas"):
        item = dict(item, notas=item.get("notas", []) + [
            "As %d notas de rodapé do arquivo da CVM estão na seção final \"Notas de rodapé\", "
            "sem a âncora no texto." % extras["notas"]])
    tachado = len(palavras(md)) - len(palavras(sem_tachado(md)))
    corpo = normalizar_artigos(sem_tachado(md) if tipo_fonte == "consolidado" else md)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    cab = frontmatter(item, tipo_fonte, ext, url, sha, corpo)
    rel = {"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "resultado": "ok",
           "nivel_verificacao": nivel_verificacao(tipo_fonte, ext),
           "artigos": len(re.findall(r"(?m)^## Art\. ", corpo)),
           "linhas": corpo.count("\n") + 1, "tabelas": len(re.findall(r"(?m)^\|.*\|\s*$\n(?!\|)", corpo)),
           "cobertura": cobertura(txt, md), "palavras_tachadas": tachado,
           "conferencia_independente": independente, "caracteres": len(corpo),
           "palavras_em_caixa_de_texto": extras.get("caixa", 0), "notas_de_rodape": extras.get("notas", 0)}
    if ext == "pdf":
        rel["legibilidade"], rel["palavras"] = legibilidade(txt)
    return cab + corpo.strip() + "\n", rel


# ---------------------------------------------------------------- lote

def processar(itens, saida, cache, mostrar=False):
    """Converte cada item e grava em <saida>/<arquivo>; devolve o relatório (lista)."""
    os.makedirs(cache, exist_ok=True)
    relatorio = []
    for item in itens:
        t0 = time.time()
        candidatas = fontes_candidatas(item.get("fontes"))
        if not candidatas:
            relatorio.append({"id": item["id"], "resultado": "erro", "erro": "sem fonte"})
            continue
        tentativas = []
        try:
            for i, (tipo_fonte, ext, url) in enumerate(candidatas):
                base = {"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "arquivo": item["arquivo"]}
                try:
                    path = _baixar(url, os.path.join(cache, "%s.%s" % (item["id"], ext)))
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
    return "\n".join(linhas)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("itens", nargs="?", help="itens.json (modo do piloto)")
    ap.add_argument("pasta", nargs="?", help="pasta de saída (modo do piloto)")
    ap.add_argument("--camada", type=int, choices=(1, 2))
    ap.add_argument("--acervo", default="fontes/acervo.json")
    ap.add_argument("--saida", default="plugins/normas/normas")
    ap.add_argument("--limite", type=int, help="só os N primeiros itens")
    ap.add_argument("--cache", help="padrão: dados/texto-vigente-fontes (camada) ou <pasta>/fontes")
    ap.add_argument("--relatorio", help="padrão: dados/texto-vigente-camada-N.json")
    args = ap.parse_args(argv[1:])
    if args.camada:
        with open(args.acervo, encoding="utf-8") as f:
            itens = itens_do_acervo(json.load(f), args.camada)
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
