#!/usr/bin/env python3
"""Texto vigente por script (Fase 2b): da fonte oficial da CVM ao Markdown da SPEC, sem LLM.

Fonte, na ordem: consolidado DOCX > DOC > HTM > ato DOCX > DOC > HTM > PDF.
- DOCX: converter.docx_para_md.
- DOC e HTM: convertidos para DOCX pelo `textutil` do macOS e depois como DOCX.
- PDF: pypdf (dependência opcional, fora da biblioteca padrão); nível de verificação menor.
No consolidado, texto tachado (~~...~~, redação antiga) sai; no ato, fica marcado (num
Documento de Revisão de CPC o tachado é o trecho excluído, conteúdo do ato). As notas de alteração do consolidado ficam, como nas leis,
porque não há histórico de commits que as substitua.

Conferência independente: o texto da fonte extraído pelo `textutil -convert txt` (DOCX,
DOC, HTM) ou pelo próprio pypdf (PDF, sem conferência independente) contra o Markdown;
`cobertura` = fração das palavras da fonte presentes no Markdown convertido, antes de tirar
o tachado (multiconjunto); `palavras_tachadas` = quantas palavras estão em texto tachado.

Uso: python3 scripts/texto_vigente.py <itens.json> <pasta de saída>
itens.json: lista de {id, tipo, numero, data, dou, ementa, situacao, url_pagina,
fontes: {consolidado: {ext: url}, ato: {ext: url}}, vigente_ate_ato}
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import docx_para_md, normalizar_artigos  # noqa: E402
from inventario import USER_AGENT  # noqa: E402

ORDEM = [("consolidado", "docx"), ("consolidado", "doc"), ("consolidado", "htm"),
         ("ato", "docx"), ("ato", "doc"),
         ("ato", "htm"), ("consolidado", "pdf"), ("ato", "pdf")]
DATA_BASE = time.strftime("%Y-%m-%d")


def escolher_fonte(fontes):
    """(tipo, ext, url) da melhor fonte disponível, ou None."""
    for tipo, ext in ORDEM:
        url = fontes.get(tipo, {}).get(ext)
        if url:
            return tipo, ext, url
    return None


def sem_tachado(md):
    return re.sub(r"~~.*?~~", "", md)


def palavras(txt):
    return re.findall(r"\w+", txt.lower())


def cobertura(fonte_txt, md):
    a, b = Counter(palavras(fonte_txt)), Counter(palavras(md))
    total = sum(a.values())
    return round(sum(min(n, b[w]) for w, n in a.items()) / total, 4) if total else 0.0


def _textutil(origem, formato, destino):
    subprocess.run(["textutil", "-convert", formato, "-output", destino, origem],
                   check=True, capture_output=True)
    return destino


def _pdf_txt(path):
    from pypdf import PdfReader  # dependência opcional
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


def converter_fonte(path, ext):
    """(markdown, texto da fonte para conferência, conferência independente?)."""
    if ext == "pdf":
        txt = _pdf_txt(path)
        linhas = [re.sub(r"\s+", " ", x).strip() for x in txt.split("\n")]
        return "\n\n".join(x for x in linhas if x), txt, False
    with tempfile.TemporaryDirectory() as d:
        docx = path if ext == "docx" else _textutil(path, "docx", os.path.join(d, "f.docx"))
        md = docx_para_md(docx)
        with open(_textutil(path, "txt", os.path.join(d, "f.txt")), encoding="utf-8",
                  errors="replace") as f:
            txt = f.read()
    return md, txt, True


def _baixar(url, destino):
    import urllib.request
    if not (os.path.exists(destino) and os.path.getsize(destino)):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
            f.write(r.read())
        time.sleep(0.7)
    return destino


def montar(item, path, tipo_fonte, ext, url):
    """(markdown com frontmatter, relatório)."""
    md, txt, independente = converter_fonte(path, ext)
    tachado = len(palavras(md)) - len(palavras(sem_tachado(md)))
    corpo = normalizar_artigos(sem_tachado(md) if tipo_fonte == "consolidado" else md)
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    artigos = len(re.findall(r"(?m)^## Art\. ", corpo))
    incerteza = ["Texto vigente convertido por script de %s %s da CVM, data-base %s, sem "
                 "histórico de redações nem conferência ato a ato." % (tipo_fonte, ext.upper(), DATA_BASE)]
    if tipo_fonte == "ato" and item.get("alteradoras"):
        incerteza.append("A CVM não publica consolidado: o texto é o do ato original e não reflete "
                         "as alterações de %s [verificar]." % ", ".join(item["alteradoras"]))
    if ext == "pdf":
        incerteza.append("Extraído de PDF: quebras de linha, tabelas e numeração podem estar "
                         "deslocadas [verificar].")
    fm = [
        ("id", item["id"]), ("orgao", "cvm"), ("tipo", item["tipo"]), ("numero", item["numero"]),
        ("data", item["data"]), ("publicacao_dou", item.get("dou") or item["data"]),
        ("ementa", item["ementa"]), ("situacao", item.get("situacao", "vigente")),
        ("versao_texto", "consolidado" if tipo_fonte == "consolidado" else "original"),
        ("vigente_ate_ato", item.get("vigente_ate_ato", "")),
        ("aguarda_consolidado_oficial", "false"), ("historico_parcial", "true"),
        ("fonte_original", item.get("fontes", {}).get("ato", {}).get("pdf") or url),
        ("fonte_consolidada", url), ("sha256_fonte", sha), ("baixado_em", DATA_BASE),
        ("verificado_em", DATA_BASE), ("incerteza", " ".join(incerteza)),
    ]
    cab = "---\n" + "\n".join(("%s: %s" % (k, v)) if v != "" else "%s:" % k for k, v in fm) + "\n---\n\n"
    rel = {"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "artigos": artigos,
           "linhas": corpo.count("\n") + 1, "tabelas": len(re.findall(r"(?m)^\|.*\|\s*$\n(?!\|)", corpo)),
           "cobertura": cobertura(txt, md), "palavras_tachadas": tachado, "conferencia_independente": independente,
           "caracteres": len(corpo)}
    return cab + corpo.strip() + "\n", rel


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        itens = json.load(f)
    saida = argv[2]
    cache = os.path.join(saida, "fontes")
    os.makedirs(cache, exist_ok=True)
    relatorio = []
    for item in itens:
        t0 = time.time()
        escolha = escolher_fonte(item["fontes"])
        if not escolha:
            relatorio.append({"id": item["id"], "erro": "sem fonte"})
            continue
        tipo_fonte, ext, url = escolha
        path = _baixar(url, os.path.join(cache, "%s.%s" % (item["id"], ext)))
        try:
            md, rel = montar(item, path, tipo_fonte, ext, url)
        except Exception as e:  # noqa: BLE001 — registra e segue
            relatorio.append({"id": item["id"], "fonte": "%s %s" % (tipo_fonte, ext), "erro": str(e)[:200]})
            continue
        destino = os.path.join(saida, item["arquivo"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(md)
        rel["segundos"] = round(time.time() - t0, 1)
        rel["arquivo"] = item["arquivo"]
        relatorio.append(rel)
        print(json.dumps(rel, ensure_ascii=False))
    with open(os.path.join(saida, "relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
