#!/usr/bin/env python3
"""Auditoria da Fase 3: universo, sorteio, insumos cegos por lote e comparador.

  python3 scripts/auditoria.py universo [--saida dados/fase-3/universo.json] [--camadas 1,2,3,4,5]
  python3 scripts/auditoria.py sortear --semente 20261030 [--universo ...] [--saida fontes/amostra-fase3.json]
  python3 scripts/auditoria.py sortear --semente 20261031 --categorias 1/inclusao,4/tachado
      (re-auditoria: só as categorias dadas, sem os itens já sorteados em fontes/amostra-fase3.json;
       grava fontes/amostra-fase3-20261031.json)
  python3 scripts/auditoria.py insumos --amostra fontes/amostra-fase3.json --saida <pasta> [--lote-max 10]
  python3 scripts/auditoria.py comparar --amostra fontes/amostra-fase3.json --saidas <pasta>
      [--relatorio dados/fase-3/comparacao.json]

Universo (C1 a C6 do plano da Fase 3): ver scripts/auditoria_universo.py. Sorteio: um
random.Random(semente) sobre o universo ordenado por (camada, categoria, norma, posição),
percorrido categoria a categoria nessa ordem; no máximo uma unidade por norma numa categoria
enquanto houver normas. Insumos: cada lote é uma pasta só com itens.json, os insumos e o
PROMPT.md, sem caminho que leve ao repo. Comparador (C7): texto normalizado (auditoria_texto)
e diff por palavra; leitura fora da pasta do lote no log stream-json = "vazou".
"""
import argparse
import datetime
import hashlib
import json
import logging
import os
import random
import re
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import auditoria_texto as T  # noqa: E402
import auditoria_universo as U  # noqa: E402

RAIZ = U.RAIZ
SEMENTE = 20261030

# tamanho por camada/categoria: inteiro, "censo" (todas as unidades) ou "censo-norma" (uma
# página sorteada por norma)
TAMANHOS = {
    "1/revogacao": "censo", "1/vigencia-diferida": "censo", "1/inclusao": 12,
    "1/nova-redacao": 15, "1/tabela-anexo": 12, "1/sem-historico": 10,
    "2/ocr": "censo-norma", "2/oficio-pdf": 12, "2/parecer-doc": 5, "2/nota-diagrama": 5,
    "3/redacao-incluido": 14, "3/revogado": 10, "3/rotulo-margem": 5, "3/tabela": "censo",
    "4/tachado": 10, "4/nota-redacao": 7, "4/tabela": 8, "4/so-pdf": "censo-norma",
    "5/sumario": 6, "5/quebra-pagina": 8, "5/tabela": 6, "5/assinaturas": "censo",
}
# metades fixas (C6 e lista numerada): campo e tamanho por valor
SUBGRUPOS = {"1/nova-redacao": ("sobrescrito", {False: 7, True: 8}),
             "1/sem-historico": ("lista_numerada", {False: 5, True: 5})}
REPLAY = {"revogacao", "inclusao", "nova-redacao", "tabela-anexo", "vigencia-diferida"}
PAGINAS = {("2", "ocr"), ("2", "oficio-pdf"), ("4", "so-pdf"), ("5", "sumario"),
           ("5", "quebra-pagina"), ("5", "tabela"), ("5", "assinaturas")}


def chave(u):
    return "%s/%s" % (u["camada"], u["categoria"])


def _gravar_json(caminho, dados):
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)
        f.write("\n")


def _ler_json(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- sorteio

def _sortear_n(rng, unidades, n):
    """n unidades: embaralha e pega uma por norma; se faltar norma, completa com as que sobram."""
    ordem = list(unidades)
    rng.shuffle(ordem)
    escolhidas, normas = [], set()
    for u in ordem:
        if len(escolhidas) >= n:
            break
        if u["norma"] not in normas:
            escolhidas.append(u)
            normas.add(u["norma"])
    for u in ordem:
        if len(escolhidas) >= n:
            break
        if u not in escolhidas:
            escolhidas.append(u)
    return escolhidas


def sortear(universo, semente, categorias=None, excluir=(), hoje=None):
    unidades = sorted(universo["unidades"], key=U.chave_ordem)
    excluir = set(excluir)
    rng = random.Random(semente)
    itens, resumo = [], {}
    for k in sorted(TAMANHOS):
        if categorias and k not in categorias:
            continue
        pool = [u for u in unidades if chave(u) == k and u["id"] not in excluir]
        pedido = TAMANHOS[k]
        if pedido == "censo":
            escolha = pool
        elif pedido == "censo-norma":
            escolha = []
            for norma in sorted({u["norma"] for u in pool}):
                escolha.append(rng.choice([u for u in pool if u["norma"] == norma]))
        elif k in SUBGRUPOS:
            campo, tam = SUBGRUPOS[k]
            escolha = []
            for valor in sorted(tam):
                escolha += _sortear_n(rng, [u for u in pool if bool(u.get(campo)) == valor], tam[valor])
        else:
            escolha = _sortear_n(rng, pool, pedido)
        escolha.sort(key=U.chave_ordem)
        itens += escolha
        resumo[k] = {"pedido": pedido, "universo": len(pool),
                     "normas_no_universo": len({u["norma"] for u in pool}),
                     "sorteado": len(escolha),
                     "abaixo_do_pedido": isinstance(pedido, int) and len(escolha) < pedido}
        if k in SUBGRUPOS:
            campo, tam = SUBGRUPOS[k]
            resumo[k]["por_%s" % campo] = {str(v).lower(): {
                "universo": sum(1 for u in pool if bool(u.get(campo)) == v),
                "sorteado": sum(1 for u in escolha if bool(u.get(campo)) == v)} for v in sorted(tam)}
    ids = "\n".join(sorted(u["id"] for u in universo["unidades"]))
    return {"semente": semente, "data": hoje or datetime.date.today().isoformat(),
            "metodo": "random.Random(semente) sobre o universo ordenado por (camada, categoria, "
                      "norma, posicao), categoria a categoria em ordem; shuffle e uma unidade por "
                      "norma até completar; censo-norma: uma unidade (página) por norma",
            "universo_sha256": hashlib.sha256(ids.encode("utf-8")).hexdigest(),
            "universo_data_base": universo.get("data_base"),
            "tamanhos": {k: v for k, v in TAMANHOS.items() if not categorias or k in categorias},
            "excluidos": len(excluir), "resumo": resumo, "itens": itens}


# ---------------------------------------------------------------- insumos

CONVENCOES_ACERVO = """\
- Artigo: a linha do título é `## Art. N` (por exemplo, `## Art. 5º`, `## Art. 10`, `## Art. 17-A`) e o
  texto do caput vem no parágrafo seguinte. Parágrafos, incisos e alíneas, um por linha, com linha em
  branco entre eles.
- Dispositivo revogado fica com a marca `(Revogado)` ou `(Revogado pela Resolução CVM nº X)`, como no ato.
- Notas de alteração ("Redação dada pela...", "(NR)", "Incluído pela...") que o ato não manda escrever
  não entram no texto.
- Anexo: a linha do título do anexo em caixa alta (por exemplo, `ANEXO A`), e o texto do anexo abaixo;
  tabela em Markdown com `|`.
"""

CONVENCOES_PLANALTO = """\
Convenções da conversão do Planalto que o texto do acervo segue (scripts/leis.py e converter.py):
- O texto tachado (`<strike>`, `<s>`, `<del>` ou `text-decoration: line-through`) é redação revogada
  ou substituída e sai. Exceção: se o que sobra visível de um dispositivo é só "(Revogado pela ...)"
  ou "(Revogada)", o rótulo riscado do dispositivo volta antes da marca (por exemplo,
  "§ 2º (Revogado pela Lei nº ...)").
- As notas do Planalto ("(Redação dada pela Lei nº ...)", "(Incluído pela Lei nº ...)",
  "(Revogado pela Lei nº ...)") ficam no texto, onde aparecem.
- Os rótulos de margem de vigência, links com "(Vigência)", "Vigência encerrada" ou
  "Produção de efeito(s)", saem.
- `<sup>o</sup>` é "º". Tabela de uma linha só (diagramação) vira texto; tabela de dados vira
  tabela com `|`.
- Artigo citado entre aspas (texto de outra lei que o artigo altera) é texto do artigo, não artigo novo.
"""

CONVENCOES_BCB = """\
Convenções da conversão do BCB que o texto do acervo segue (scripts/html_bcb.py e texto_vigente.py):
- O texto tachado (`<s>`, `<strike>`, `<del>` ou `text-decoration: line-through`) é redação revogada
  e sai inteiro; a linha que fica vazia sai, e a linha de tabela que fica vazia também.
- As notas em vermelho ("Redação dada pela Resolução ...", "Revogado pela ...") que não estão
  tachadas ficam no texto.
- Negrito e itálico não importam; links ficam só com o texto; lista vira linhas com "- ".
- Tabela com mais de uma célula numa linha vira tabela com `|`; tabela de uma célula por linha
  (diagramação) vira texto.
"""

PROMPT = """\
# Auditoria cega de transcrição

Você confere, de forma independente, trechos de normas. Nesta pasta estão só os insumos.

1. Leia `itens.json`. Cada item tem `id`, `categoria`, `instrucao` e a lista `insumos`.
2. Para cada item, leia os insumos dele e siga a `instrucao`. Grave a resposta em `<id>-saida.md`,
   nesta pasta, um arquivo por item.
3. Regras:
   - Leia e grave só arquivos desta pasta. Não abra nada fora dela, não use a web, não rode
     comandos, git nem commit.
   - Transcreva o que a fonte diz. Não corrija a fonte, não complete lacuna e não resuma. Se um
     trecho for ilegível, escreva `[ilegível]` no lugar.
   - Markdown simples: um parágrafo, inciso ou alínea por linha, com linha em branco entre eles.
     Sem comentário seu dentro da saída.
   - PDF: cada `<id>-fonte.pdf` já tem só as páginas do item. Leia o arquivo inteiro com a
     ferramenta Read, sem o parâmetro `pages`. Transcreva na ordem de leitura, sem o cabeçalho e o
     rodapé que se repetem nas páginas e sem o número da página.
4. Ao terminar todos os itens, pare.

## Convenções

%s
"""


def _sem_caminhos(txt, repo):
    """Tira do texto qualquer caminho que leve ao repo."""
    for p in {repo, os.path.realpath(repo)}:
        txt = txt.replace(p, "")
    return txt


def instrucao_replay(u):
    loc = u["localizador"]
    t = ("O arquivo `%s-antes.md` traz o dispositivo «%s» como estava antes do ato, e `%s-ato.md` "
         "o texto integral do ato. Aplique o ato e escreva em `%s-saida.md` o dispositivo «%s» "
         "inteiro depois do ato, do título até antes do dispositivo seguinte. Se o ato não muda "
         "o dispositivo, copie-o; se o revoga, escreva o que fica, com a marca de revogação."
         % (u["id"], loc, u["id"], u["id"], loc))
    if u["categoria"] == "vigencia-diferida":
        t += (" O ato dá a este dispositivo vigência própria (%s): escreva a redação que vale em "
              "2026-10-30." % (u.get("vigor") or "data no ato"))
    return t


MAX_PAGINAS = 4


def recortar_pdf(origem, paginas, destino):
    """Grava em `destino` só as `paginas` (1-based, no máximo MAX_PAGINAS) do PDF `origem`, pelo
    pypdf (dependência opcional, a mesma da conferência do texto_vigente). O Read do auditor não
    renderiza página escolhida com `pages` sem o pdftoppm, e PDF longo sem `pages` falha."""
    if not paginas or len(paginas) > MAX_PAGINAS:
        raise ValueError("recorte de PDF com %d páginas (de 1 a %d)" % (len(paginas or []), MAX_PAGINAS))
    from pypdf import PdfReader, PdfWriter  # dependência opcional
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # avisos de xref quebrado, inofensivos
    leitor, escritor = PdfReader(origem), PdfWriter()
    for p in paginas:
        escritor.add_page(leitor.pages[p - 1])
    with open(destino, "wb") as f:
        escritor.write(f)
    return destino


def instrucao_pagina(u, nome_pdf):
    pags = u["paginas"]
    faixa = "%d" % pags[0] if len(pags) == 1 else "%d a %d" % (pags[0], pags[-1])
    um = len(pags) == 1
    base = ("Leia o arquivo inteiro `%s`, sem o parâmetro `pages`: ele tem só a%s página%s %s da "
            "fonte (%s). Depois, " % (nome_pdf, "" if um else "s", "" if um else "s", faixa,
                                       "uma página" if um else "%d páginas, na ordem" % len(pags)))
    if u["categoria"] == "assinaturas":
        return (base + "responda na primeira linha de `%s-saida.md` `ASSINATURAS: sim` se uma "
                "dessas páginas é o registro das assinaturas eletrônicas (nomes, e-mails, IP, "
                "validação), ou `ASSINATURAS: não`. Depois, transcreva o texto normativo dessas "
                "páginas que vem antes do registro (o registro em si fica de fora)." % u["id"])
    if u["categoria"] == "quebra-pagina":
        return (base + "transcreva as duas páginas como um texto só, na ordem, sem o cabeçalho, o "
                "rodapé e o número de página entre elas, em `%s-saida.md`." % u["id"])
    if u["categoria"] == "sumario":
        return base + ("transcreva a página (é um sumário ou índice) linha a linha, com os números "
                       "de página como estão, em `%s-saida.md`." % u["id"])
    if u["categoria"] == "tabela":
        return base + ("transcreva a página em `%s-saida.md`; o conteúdo de tabela vai célula a "
                       "célula, linha por linha, na ordem de leitura." % u["id"])
    return base + "transcreva a página em `%s-saida.md`." % u["id"]


def _html_da_fonte(caminho, ext, pasta):
    if ext in ("htm", "html"):
        import converter
        with open(caminho, "rb") as f:
            return converter.decodificar_html(f.read())
    destino = U.textutil(caminho, "html", os.path.join(pasta, "fonte.html"))
    with open(destino, encoding="utf-8", errors="replace") as f:
        return f.read()


def alvo_acervo(repo, u):
    """Texto do acervo que localiza o trecho na fonte (seção do artigo ou bloco)."""
    texto = U.ler(repo, U.NORMAS + "/" + u["norma"])
    if u["categoria"] == "parecer-doc":
        return U.blocos_de_palavras(texto)[u["posicao"] - 1]
    if u["localizador"] == "texto":
        return T.corpo(texto)
    return T.texto_secao(texto, u["localizador"]) or ""


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"


def _sem_fallback(el):
    for filho in el:
        if filho.tag == MC + "Fallback":
            continue
        yield filho
        yield from _sem_fallback(filho)


def _texto_par(p):
    partes = []
    for el in _sem_fallback(p):
        if el.tag == W + "t":
            partes.append(el.text or "")
        elif el.tag == W + "tab":
            partes.append(" ")
        elif el.tag == W + "footnoteReference":
            partes.append(" [nota id=%s] " % el.get(W + "id"))
    return re.sub(r"\s+", " ", "".join(partes)).strip()


def fonte_notas_docx(docx):
    """Texto simples do DOCX, por um extrator à parte do converter: os parágrafos com chamada de
    nota (marcada `[nota id=N]`), as notas pela identificação interna e as caixas de texto."""
    with zipfile.ZipFile(docx) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
        notas = ET.fromstring(z.read("word/footnotes.xml")) if "word/footnotes.xml" in z.namelist() else None
    pars, caixas = [], []
    for el in _sem_fallback(doc):
        if el.tag == W + "txbxContent":
            caixas.append(" / ".join(t for t in (_texto_par(p) for p in el.iter(W + "p")) if t))
    for p in doc.iter(W + "p"):
        if p.find(".//" + W + "footnoteReference") is not None:
            pars.append(_texto_par(p))
    out = ["PARÁGRAFOS COM CHAMADA DE NOTA DE RODAPÉ", ""] + [x + "\n" for x in pars]
    out += ["NOTAS DE RODAPÉ (pela identificação interna do arquivo, não pela ordem de exibição)", ""]
    if notas is not None:
        for fn in notas.iter(W + "footnote"):
            if fn.get(W + "type", "normal") != "normal":
                continue
            txt = " ".join(t for t in (_texto_par(p) for p in fn.iter(W + "p")) if t)
            out.append("nota id=%s: %s\n" % (fn.get(W + "id"), txt))
    out += ["CAIXAS DE TEXTO (diagramas), na ordem do arquivo", ""]
    out += ["caixa %d: %s\n" % (i, c) for i, c in enumerate(caixas, 1) if c]
    return "\n".join(out) + "\n"


def _ancora_nota(texto, loc):
    """Começo do parágrafo do acervo que chama a nota, ou do texto do diagrama."""
    c = T.corpo(texto)
    if loc.startswith("nota "):
        k = loc.split()[1]
        for ln in c.split("\n" + T.NOTAS)[0].split("\n"):
            if re.search(r"\[%s\]" % k, ln):
                limpo = re.sub(r"\s*\[\d+\]", "", ln).lstrip("#> ").strip()
                return " ".join(limpo.split()[:14])
        return ""
    k = int(loc.split()[1])
    for ln in [x for x in c.split("\n") if x.startswith("> [Diagrama]")][k - 1:k]:
        return " ".join(ln[len("> [Diagrama]"):].split()[:10])
    return ""


def montar_insumo(repo, u, lote, tmp):
    """Grava os insumos do item `u` na pasta `lote`; devolve (insumos, instrução, aviso)."""
    cat, iid = u["categoria"], u["id"]
    if cat in REPLAY:
        antes = U.git_show(repo, u["commit"] + "^", U.NORMAS + "/" + u["norma"]) or ""
        sec = T.texto_secao(antes, u["localizador"])
        if sec is None:
            sec = ("(O dispositivo «%s» não existe no texto anterior ao ato: o ato o inclui.)\n"
                   % u["localizador"])
        atos = []
        for a in u.get("atos") or []:
            t = U.git_show(repo, u["commit"], U.NORMAS + "/" + a)
            if t:
                atos.append(T.corpo(t).strip("\n"))
        aviso = None if atos else "sem texto do ato no commit"
        _escrever(lote, iid + "-antes.md", sec)
        _escrever(lote, iid + "-ato.md", "\n\n---\n\n".join(atos) + "\n")
        return [iid + "-antes.md", iid + "-ato.md"], instrucao_replay(u), aviso
    if (u["camada"], cat) in PAGINAS:
        nome = iid + "-fonte.pdf"
        recortar_pdf(os.path.join(repo, u["fonte"]), u["paginas"], os.path.join(lote, nome))
        return [nome], instrucao_pagina(u, nome), None
    ext = u["fonte"].rsplit(".", 1)[-1]
    caminho = os.path.join(repo, u["fonte"])
    if cat == "nota-diagrama":
        docx = caminho if ext == "docx" and zipfile.is_zipfile(caminho) else U.textutil(
            caminho, "docx", os.path.join(tmp, "nota.docx"))
        _escrever(lote, iid + "-fonte.txt", fonte_notas_docx(docx))
        ancora = _ancora_nota(U.ler(repo, U.NORMAS + "/" + u["norma"]), u["localizador"])
        if u["localizador"].startswith("nota "):
            inst = ("`%s-fonte.txt` traz o texto do arquivo Word da norma. Ache o parágrafo que começa "
                    "por «%s» e a nota de rodapé que ele chama; transcreva em `%s-saida.md` só o texto "
                    "dessa nota." % (iid, ancora, iid))
        else:
            inst = ("`%s-fonte.txt` traz o texto do arquivo Word da norma. Transcreva em `%s-saida.md` "
                    "o texto da caixa de texto (diagrama) que começa por «%s»." % (iid, iid, ancora))
        return [iid + "-fonte.txt"], inst, None
    html = _html_da_fonte(caminho, ext, tmp)
    alvo = alvo_acervo(repo, u)
    recorte, achou = T.recortar_html(html, alvo)
    aviso = None
    if not achou:
        recorte, aviso = html, "trecho não localizado na fonte; HTML inteiro"
    _escrever(lote, iid + "-fonte.html", recorte)
    if cat == "parecer-doc":
        b = alvo.split()
        inst = ("`%s-fonte.html` é um trecho do documento original. Transcreva em `%s-saida.md` o "
                "texto que começa em «%s» e termina em «%s»." % (iid, iid, " ".join(b[:8]), " ".join(b[-8:])))
    else:
        nome = u["localizador"] if u["localizador"] != "texto" else "o texto inteiro da norma"
        inst = ("`%s-fonte.html` é um trecho da fonte oficial (HTML). Transcreva em `%s-saida.md` %s, "
                "do título até antes do artigo seguinte, seguindo as convenções do PROMPT.md."
                % (iid, iid, "o «%s»" % nome if nome.startswith("Art.") else nome))
    return [iid + "-fonte.html"], inst, aviso


def _escrever(pasta, nome, txt):
    with open(os.path.join(pasta, nome), "w", encoding="utf-8", newline="\n") as f:
        f.write(txt)


def lotes(itens, lote_max=10):
    """[(nome, [itens])]: mesma camada e categoria; dentro dela, ordenados pela fonte."""
    grupos = {}
    for u in itens:
        grupos.setdefault((u["camada"], u["categoria"]), []).append(u)
    res, k = [], 0
    for (cam, cat), us in sorted(grupos.items()):
        us = sorted(us, key=lambda u: (u.get("fonte") or u.get("commit") or "", U.chave_ordem(u)))
        for i in range(0, len(us), lote_max):
            k += 1
            res.append(("%02d-c%s-%s" % (k, cam, cat), us[i:i + lote_max]))
    return res


def _convencoes(cam, cat):
    if cat in REPLAY:
        return CONVENCOES_ACERVO
    if cam == "3":
        return CONVENCOES_PLANALTO
    if cam == "4" and cat != "so-pdf":
        return CONVENCOES_BCB
    if cam == "1":
        return CONVENCOES_ACERVO + "- O texto tachado do arquivo Word (consolidado) é redação revogada e sai.\n"
    return "- Transcreva o texto como aparece na fonte.\n"


def insumos(amostra, saida, repo=RAIZ, lote_max=10):
    os.makedirs(saida, exist_ok=True)
    feitos = []
    with tempfile.TemporaryDirectory() as tmp:
        for nome, us in lotes(amostra["itens"], lote_max):
            pasta = os.path.join(saida, nome)
            os.makedirs(pasta, exist_ok=True)
            itens, avisos = [], []
            for u in us:
                ins, inst, aviso = montar_insumo(repo, u, pasta, tmp)
                itens.append({"id": u["id"], "categoria": u["categoria"], "instrucao": inst,
                              "insumos": ins, "saida": u["id"] + "-saida.md"})
                if aviso:
                    avisos.append("%s: %s" % (u["id"], aviso))
            _gravar_json(os.path.join(pasta, "itens.json"), itens)
            _escrever(pasta, "PROMPT.md", PROMPT % _convencoes(us[0]["camada"], us[0]["categoria"]))
            for n in os.listdir(pasta):
                if n.endswith((".md", ".json", ".txt", ".html")):
                    p = os.path.join(pasta, n)
                    with open(p, encoding="utf-8", errors="replace") as f:
                        t = f.read()
                    if repo in t or os.path.realpath(repo) in t:
                        _escrever(pasta, n, _sem_caminhos(t, repo))
            feitos.append({"lote": nome, "itens": len(itens), "avisos": avisos})
    return feitos


# ---------------------------------------------------------------- comparador

def esperado(repo, u):
    """(texto esperado, modo): "secao" compara inteiro; "janela" procura o trecho no acervo."""
    cat = u["categoria"]
    if cat in REPLAY:
        t = U.git_show(repo, u["commit"], U.NORMAS + "/" + u["norma"]) or ""
        return T.texto_secao(t, u["localizador"]) or "", "secao"
    texto = U.ler(repo, U.NORMAS + "/" + u["norma"])
    if cat == "nota-diagrama":
        for loc, t in U.notas_e_diagramas(texto):
            if loc == u["localizador"]:
                return t, "secao"
        return "", "secao"
    if (u["camada"], cat) in PAGINAS or cat == "parecer-doc":
        return T.corpo(texto), "janela"
    if u["localizador"] == "texto":
        return T.corpo(texto), "secao"
    return T.texto_secao(texto, u["localizador"]) or "", "secao"


FERRAMENTAS_OK = {"Read", "Write"}


def vazamentos(lote):
    """Usos de ferramenta fora da pasta do lote no log stream-json (`log.jsonl`)."""
    log = os.path.join(lote, "log.jsonl")
    if not os.path.exists(log):
        return None
    base = os.path.realpath(lote)
    cwd, res = base, []
    with open(log, encoding="utf-8", errors="replace") as f:
        for ln in f:
            try:
                ev = json.loads(ln)
            except ValueError:
                continue
            if ev.get("type") == "system" and ev.get("cwd"):
                cwd = os.path.realpath(ev["cwd"])
            msg = ev.get("message") or {}
            for c in msg.get("content") or [] if isinstance(msg, dict) else []:
                if not isinstance(c, dict) or c.get("type") != "tool_use":
                    continue
                nome, inp = c.get("name"), c.get("input") or {}
                if nome not in FERRAMENTAS_OK:
                    res.append({"ferramenta": nome, "entrada": inp})
                    continue
                p = inp.get("file_path") or inp.get("path") or ""
                real = os.path.realpath(os.path.join(cwd, p))
                if not (real == base or real.startswith(base + os.sep)):
                    res.append({"ferramenta": nome, "caminho": p})
    return res


def _e_cabecalho(diff, repetidas):
    if not diff["esperado"] or diff["saida"]:
        return False
    s = re.sub(r"\d+", "#", diff["esperado"])
    return any(s in r or r in s for r in repetidas if len(r) >= 4)


def comparar_item(repo, u, saida_txt, repetidas=None):
    esp, modo = esperado(repo, u)
    res = {"assinaturas": None}
    if u["categoria"] == "assinaturas":
        linhas = saida_txt.lstrip().split("\n", 1)
        m = re.match(r"(?i)assinaturas:\s*(sim|n[ãa]o)", linhas[0].strip())
        res["assinaturas"] = m.group(1).lower() if m else None
        saida_txt = linhas[1] if m and len(linhas) > 1 else ("" if m else saida_txt)
    if modo == "janela":
        esp_txt, _i0, _i1 = T.janela(esp, saida_txt)
    else:
        esp_txt = esp
    diffs = T.diff_palavras(esp_txt, saida_txt)
    for d in diffs:
        d["cabecalho_rodape"] = _e_cabecalho(d, repetidas or set())
    reais = [d for d in diffs if not d["cabecalho_rodape"]]
    if u["categoria"] == "assinaturas" and res["assinaturas"] != "sim":
        reais.append({"op": "assinaturas", "esperado": "sim", "saida": res["assinaturas"] or "",
                      "antes": "", "depois": "", "cabecalho_rodape": False})
    if not esp_txt.strip():
        status = "sem-esperado"
    elif reais:
        status = "diferente"
    elif diffs:
        status = "igual-salvo-cabecalho"
    else:
        status = "igual"
    res.update(status=status, diffs=diffs, palavras_esperado=len(esp_txt.split()))
    return res


def _achar_saidas(pasta):
    res = {}
    for raiz, _d, arqs in os.walk(pasta):
        for a in arqs:
            if a.endswith("-saida.md"):
                res[a[:-len("-saida.md")]] = os.path.join(raiz, a)
    return res


def comparar(amostra, saidas, repo=RAIZ):
    achadas = _achar_saidas(saidas)
    itens, resumo, rep_cache, vaz_cache = [], {}, {}, {}
    for u in amostra["itens"]:
        r = {"id": u["id"], "camada": u["camada"], "categoria": u["categoria"], "norma": u["norma"],
             "localizador": u["localizador"], "commit": u.get("commit")}
        caminho = achadas.get(u["id"])
        if not caminho:
            r["status"] = "sem-saida"
        else:
            with open(caminho, encoding="utf-8", errors="replace") as f:
                txt = f.read()
            if u["norma"] not in rep_cache and (u["camada"], u["categoria"]) in PAGINAS:
                rep_cache[u["norma"]] = T.linhas_repetidas(U.ler(repo, U.NORMAS + "/" + u["norma"]))
            r.update(comparar_item(repo, u, txt, rep_cache.get(u["norma"])))
            lote = os.path.dirname(caminho)
            if lote not in vaz_cache:
                vaz_cache[lote] = vazamentos(lote)
            if vaz_cache[lote]:
                r["status"], r["vazamentos"] = "vazou", vaz_cache[lote]
            r["log"] = vaz_cache[lote] is not None
        itens.append(r)
        c = resumo.setdefault(chave(u), {})
        c[r["status"]] = c.get(r["status"], 0) + 1
    return {"gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
            "semente": amostra.get("semente"), "resumo": resumo, "itens": itens}


def resumo_texto(comp):
    linhas = ["comparação: %d itens" % len(comp["itens"])]
    for k in sorted(comp["resumo"]):
        linhas.append("  %-22s %s" % (k, ", ".join("%s %d" % kv for kv in sorted(comp["resumo"][k].items()))))
    for r in comp["itens"]:
        if r["status"] in ("diferente", "vazou"):
            linhas.append("- %s %s %s %s: %s" % (r["id"], r["categoria"], r["norma"], r["localizador"], r["status"]))
            for d in [d for d in r.get("diffs", []) if not d.get("cabecalho_rodape")][:5]:
                linhas.append("    [%s] ...%s {-%s-} {+%s+} %s..." % (d["op"], d["antes"], d["esperado"], d["saida"], d["depois"]))
    return "\n".join(linhas)


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(prog="auditoria.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("universo")
    a.add_argument("--saida", default=os.path.join(RAIZ, "dados", "fase-3", "universo.json"))
    a.add_argument("--camadas", default="1,2,3,4,5")
    a.add_argument("--repo", default=RAIZ)
    s = sub.add_parser("sortear")
    s.add_argument("--semente", type=int, default=SEMENTE)
    s.add_argument("--universo", default=os.path.join(RAIZ, "dados", "fase-3", "universo.json"))
    s.add_argument("--categorias")
    s.add_argument("--anterior", default=os.path.join(RAIZ, "fontes", "amostra-fase3.json"))
    s.add_argument("--saida")
    i = sub.add_parser("insumos")
    i.add_argument("--amostra", required=True)
    i.add_argument("--saida", required=True)
    i.add_argument("--lote-max", type=int, default=10)
    i.add_argument("--repo", default=RAIZ)
    c = sub.add_parser("comparar")
    c.add_argument("--amostra", required=True)
    c.add_argument("--saidas", required=True)
    c.add_argument("--relatorio", default=os.path.join(RAIZ, "dados", "fase-3", "comparacao.json"))
    c.add_argument("--repo", default=RAIZ)
    args = ap.parse_args(argv)

    if args.cmd == "universo":
        uni = U.construir(args.repo, camadas=tuple(args.camadas.split(",")))
        _gravar_json(args.saida, uni)
        for k, v in uni["contagem"].items():
            print("%-22s %5d unidades em %4d normas" % (k, v["unidades"], v["normas"]))
        if uni["vigencia"]:
            v = uni["vigencia"]
            print("vigência: %d atos, %d com vigor depois do DOU, sem data: %s, depois de %s: %s, gate %s"
                  % (v["total"], v["diferidos"], ", ".join(v["sem_data"]) or "nenhum", v["data_base"],
                     ", ".join(v["depois_da_data_base"]) or "nenhum", "ok" if v["gate_ok"] else "FALHOU"))
        print("avisos: %d" % len(uni["avisos"]))
        return 0 if not uni["vigencia"] or uni["vigencia"]["gate_ok"] else 1
    if args.cmd == "sortear":
        uni = _ler_json(args.universo)
        cats = set(args.categorias.split(",")) if args.categorias else None
        excluir = ()
        if cats and os.path.exists(args.anterior):
            excluir = [u["id"] for u in _ler_json(args.anterior)["itens"]]
        am = sortear(uni, args.semente, cats, excluir)
        destino = args.saida or (os.path.join(RAIZ, "fontes", "amostra-fase3.json") if not cats else
                                 os.path.join(RAIZ, "fontes", "amostra-fase3-%d.json" % args.semente))
        _gravar_json(destino, am)
        for k, v in am["resumo"].items():
            print("%-22s pedido %-11s universo %5d  sorteado %3d%s" % (
                k, v["pedido"], v["universo"], v["sorteado"], "  ABAIXO" if v["abaixo_do_pedido"] else ""))
        print("total: %d itens -> %s" % (len(am["itens"]), destino))
        return 0
    if args.cmd == "insumos":
        for l in insumos(_ler_json(args.amostra), args.saida, args.repo, args.lote_max):
            print("%s: %d itens%s" % (l["lote"], l["itens"], "".join("\n  aviso " + x for x in l["avisos"])))
        return 0
    if args.cmd == "comparar":
        comp = comparar(_ler_json(args.amostra), args.saidas, args.repo)
        _gravar_json(args.relatorio, comp)
        print(resumo_texto(comp))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
