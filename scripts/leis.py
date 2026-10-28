#!/usr/bin/env python3
"""Leis do acervo: do HTML compilado do Planalto ao Markdown da SPEC v0.2.0 (Decisões 6 a 8).

- montar_lei(item, html) -> dict[str, str]: caminho relativo a `leis/` -> conteúdo.
  `item` é uma entrada de `fontes/leis.json` (id, numero, data, planalto, e opcionais
  `partes`, `recorte`, `url`); `html` são os bytes (ou o texto) da página baixada.
  - lei comum: {"lei-NNNNN.md": ...};
  - `partes: "capitulo"` (Lei 6.404): `lei-NNNNN/index.md` (frontmatter, título, ementa,
    preâmbulo e `## Partes`) e um `cap-NN.md` por capítulo (`cap-NN-a.md` se o capítulo
    tem sufixo de letra). A linha "CAPÍTULO I ..." fica no texto da parte; o `# título`
    do arquivo é só navegação;
  - `recorte: [primeiro, último]` (Código Civil): só do primeiro ao último artigo, com o
    título de divisão que abre o primeiro (CAPÍTULO X...) e sem o título de divisão
    que antecede o artigo seguinte; o recorte é descrito em `incerteza`.
  O corpo é a conversão de `converter.planalto_html_para_md` + `normalizar_artigos`
  (artigo citado em lei alterada não vira cabeçalho). Antes do preâmbulo o corpo só
  guarda o título da lei e a ementa; o cabeçalho da página (Presidência da República,
  links de veto etc.) sai. Tabela de uma linha só (layout do Planalto) vira texto.
  Nenhum texto é inventado: a data de publicação no DOU vem do rodapé da página
  ("publicado no DOU de ..."); sem ele, vale a data da lei e a `incerteza` diz isso.
- escrever_leis(itens, pasta_fontes, pasta_saida) -> caminhos gravados. Lê o HTML de
  `pasta_fontes` (nome em `relatorio.json`) e a URL efetivamente usada.

Uso: python3 scripts/leis.py [fontes/leis.json]
Grava em plugins/normas/normas/leis/ a partir de dados/fontes/ (cache de baixar.py).
Depois: python3 scripts/teste_lei.py lei-N, validar.py e indice.py.
"""
import hashlib
import html as html_lib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import decodificar_html, normalizar_artigos, planalto_html_para_md  # noqa: E402
from teste_lei import ESTRUTURA, _chave  # noqa: E402
from validar import CAMPOS  # noqa: E402

RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LEIS = os.path.join(RAIZ, "plugins", "normas", "normas", "leis")
FONTES_JSON = os.path.join(RAIZ, "fontes", "leis.json")
PASTA_FONTES = os.path.join(RAIZ, "dados", "fontes")
DATA_BASE = "2026-10-28"
PLANALTO = "https://www.planalto.gov.br/"

_TITULO_LEI = re.compile(r"^LEI\s+N", re.I)
_PREAMBULO = re.compile(r"^(?:O|A)\s+PRESIDENT[EA]\b")
_HEADING = re.compile(r"^## Art\. (\S+)$")
_CAPITULO = re.compile(r"^CAP[ÍI]TULO\s+([IVXLCDM]+)(?:-([A-Z]))?(?=[\s.]|$)\.?\s*(.*)$")
_DOU = re.compile(
    r"publicado\s+no\s+D\.?\s?O\.?\s?U\.?\s*de\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.\s*(\d{4})", re.I)
_NOTA = re.compile(r"Reda[çc][ãa]o dada|Inclu[ií]d[oa] pel|Revogad[oa] pel")
_SEPARADOR = re.compile(r"^\|(?:\s*:?-{3,}:?\s*\|)+$")
_ROMANOS = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def _celulas(linha):
    return [c.strip() for c in re.split(r"(?<!\\)\|", linha.strip().strip("|")) if c.strip()]


def _romano(texto):
    total = 0
    for atual, proximo in zip(texto, texto[1:] + " "):
        v = _ROMANOS[atual]
        total += -v if _ROMANOS.get(proximo, 0) > v else v
    return total


def _texto_visivel(html):
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _ementa_e_corpo(md):
    """(título da lei, ementa, linhas do preâmbulo em diante) do Markdown cru do Planalto."""
    linhas = md.split("\n")
    t = next((i for i, l in enumerate(linhas) if _TITULO_LEI.match(l.strip())), None)
    if t is None:
        raise ValueError("título 'LEI Nº ...' não encontrado")
    p = next((i for i in range(t + 1, len(linhas)) if _PREAMBULO.match(linhas[i].strip())), None)
    if p is None:
        raise ValueError("preâmbulo 'O PRESIDENTE DA REPÚBLICA ...' não encontrado")
    ementa = ""
    for l in linhas[t + 1:p]:
        l = l.strip()
        if not l or _SEPARADOR.match(l):
            continue
        if l.startswith("|"):
            cels = _celulas(l)
            if not cels:
                continue
            l = cels[-1]
        ementa = " ".join(l.split())
        break
    if not ementa:
        raise ValueError("ementa não encontrada entre o título e o preâmbulo")
    return " ".join(linhas[t].split()), ementa, linhas[p:]


def _tabelas_de_layout_em_texto(linhas):
    """Tabela de uma linha só (layout do Planalto) vira texto: células não vazias, em uma linha."""
    saida, i = [], 0
    while i < len(linhas):
        if not linhas[i].lstrip().startswith("|"):
            saida.append(linhas[i])
            i += 1
            continue
        bloco = []
        while i < len(linhas) and linhas[i].lstrip().startswith("|"):
            bloco.append(linhas[i].strip())
            i += 1
        dados = [l for l in bloco if not _SEPARADOR.match(l)]
        if len(dados) <= 1:
            texto = " ".join(_celulas(dados[0])) if dados else ""
            if texto:
                saida.append(texto)
        else:
            saida += bloco
    return saida


def _juntar(linhas):
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip("\n")


def _paragrafos_antes(linhas, i, n):
    """Índices das n últimas linhas não vazias antes de `i`, da mais próxima para a mais distante."""
    achados = []
    j = i - 1
    while j >= 0 and len(achados) < n:
        if linhas[j].strip():
            achados.append(j)
        j -= 1
    return achados


def _recortar(linhas, primeiro, ultimo):
    """Linhas do artigo `primeiro` (com o título de divisão que o abre) até o artigo `ultimo`
    inclusive, sem o título de divisão que antecede o artigo seguinte."""
    ini = next((i for i, l in enumerate(linhas) if l == "## Art. " + primeiro), None)
    fim_art = next((i for i, l in enumerate(linhas) if l == "## Art. " + ultimo), None)
    if ini is None or fim_art is None:
        raise ValueError("recorte fora do texto: Art. %s a Art. %s" % (primeiro, ultimo))
    for k, j in enumerate(_paragrafos_antes(linhas, ini, 3)):
        if ESTRUTURA.match(linhas[j].strip()):
            ini = j
            break
    base = _chave(ultimo)[0]
    fim = len(linhas)
    for i in range(fim_art + 1, len(linhas)):
        m = _HEADING.match(linhas[i])
        if m and _chave(m.group(1)) and _chave(m.group(1))[0] != base:
            fim = i
            break
    if fim < len(linhas):
        for i in range(fim_art + 1, fim):
            if ESTRUTURA.match(linhas[i].strip()):
                fim = i
                break
    return linhas[ini:fim]


def _partes(linhas):
    """Divide em (antes do 1º capítulo, [(nome do arquivo, título, linhas do capítulo)])."""
    pos = []
    for i, l in enumerate(linhas):
        m = _CAPITULO.match(l.strip())
        if m:
            pos.append((i, m))
    if not pos:
        raise ValueError("lei em partes sem nenhuma linha 'CAPÍTULO ...'")
    antes = linhas[:pos[0][0]]
    if any(_HEADING.match(l) for l in antes):
        raise ValueError("artigo antes do primeiro capítulo")
    partes, vistos = [], set()
    for n, (i, m) in enumerate(pos):
        fim = pos[n + 1][0] if n + 1 < len(pos) else len(linhas)
        corpo = linhas[i:fim]
        numero, letra, resto = _romano(m.group(1)), (m.group(2) or "").lower(), m.group(3).strip()
        if not resto:
            seguinte = next((l.strip() for l in corpo[1:] if l.strip()), "")
            if seguinte and not re.match(r"^(?:SE[ÇC][ÃA]O\b|## |CAP[ÍI]TULO\b)", seguinte, re.I):
                resto = seguinte
        nome = "cap-%02d%s.md" % (numero, "-" + letra if letra else "")
        if nome in vistos:
            raise ValueError("capítulo repetido: %s" % nome)
        vistos.add(nome)
        rotulo = "Capítulo %s%s" % (m.group(1), "-" + m.group(2) if m.group(2) else "")
        titulo = "# %s - %s" % (rotulo, " ".join(resto.split())) if resto else "# " + rotulo
        partes.append((nome, titulo, corpo))
    return antes, partes


def _incerteza(item, html_txt, url, tem_dou, recorte):
    notas = len(_NOTA.findall(html_txt))
    frases = [
        "Texto da página do Planalto, data-base %s, sem histórico de redações: as notas do Planalto "
        "(\"Redação dada pela...\") ficam no texto e o texto tachado (revogado ou substituído) sai." % DATA_BASE
    ]
    pref = item["planalto"][0]
    if url != PLANALTO + pref:
        frases.append(
            "A URL de compilado (%s) não foi a usada: o texto vem da página %s, que traz %d notas de alteração."
            % (PLANALTO + pref, url, notas))
    if notas == 0:
        frases.append(
            "Página do Planalto sem notas de alteração (redação como publicada); não confirmei se a lei foi "
            "alterada depois [verificar].")
    if not tem_dou:
        frases.append("A página não indica a publicação no DOU; publicacao_dou repete a data da lei.")
    if recorte:
        frases.append(
            "Recorte: somente os arts. %s a %s; os demais artigos da lei não constam deste arquivo." % tuple(recorte))
    return " ".join(frases)


def _frontmatter(item, html_bytes, html_txt, ementa, url, tem_dou, publicacao, recorte):
    planalto = item["planalto"]
    original = next((p for p in planalto if "compilad" not in p and "consol" not in p), planalto[0])
    valores = {
        "id": item["id"], "orgao": "federal", "tipo": "lei", "numero": str(item["numero"]),
        "data": item["data"], "publicacao_dou": publicacao, "ementa": ementa,
        "situacao": "vigente", "versao_texto": "consolidado", "vigente_ate_ato": "",
        "aguarda_consolidado_oficial": "false", "historico_parcial": "true",
        "fonte_original": PLANALTO + original, "fonte_consolidada": url,
        "sha256_fonte": hashlib.sha256(html_bytes).hexdigest(),
        "baixado_em": DATA_BASE, "verificado_em": DATA_BASE,
        "incerteza": _incerteza(item, html_txt, url, tem_dou, recorte),
    }
    linhas = ["%s: %s" % (c, valores[c]) if valores[c] else "%s:" % c for c in CAMPOS]
    return "---\n" + "\n".join(linhas) + "\n---\n"


def montar_lei(item, html):
    """Ver o docstring do módulo."""
    html_bytes = html if isinstance(html, bytes) else html.encode("utf-8")
    html_txt = _texto_visivel(decodificar_html(html_bytes))
    md = normalizar_artigos(planalto_html_para_md(html_bytes), ignorar_citacoes=True)
    titulo, ementa, corpo = _ementa_e_corpo(md)
    corpo = _tabelas_de_layout_em_texto(corpo)
    m = _DOU.search(html_txt)
    tem_dou = bool(m)
    publicacao = "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else item["data"]
    url = item.get("url") or PLANALTO + item["planalto"][0]
    recorte = item.get("recorte")
    cabecalho = _frontmatter(item, html_bytes, html_txt, ementa, url, tem_dou, publicacao, recorte)
    nome = "lei-%05d" % item["numero"]

    if recorte:
        return {nome + ".md": cabecalho + "\n" + _juntar(_recortar(corpo, *recorte)) + "\n"}
    if item.get("partes") != "capitulo":
        return {nome + ".md": cabecalho + "\n" + _juntar([titulo, "", ementa, ""] + corpo) + "\n"}

    antes, partes = _partes(corpo)
    lista = "\n".join("- " + p[0] for p in partes)
    index = cabecalho + "\n" + _juntar([titulo, "", ementa, ""] + antes + ["", "## Partes", "", lista]) + "\n"
    saida = {nome + "/index.md": index}
    for arquivo, rotulo, linhas in partes:
        saida["%s/%s" % (nome, arquivo)] = rotulo + "\n\n" + _juntar(linhas) + "\n"
    return saida


def escrever_leis(itens, pasta_fontes, pasta_saida):
    """Monta e grava as leis de `itens`; devolve os caminhos gravados (relativos a `pasta_saida`)."""
    with open(os.path.join(pasta_fontes, "relatorio.json"), encoding="utf-8") as f:
        relatorio = json.load(f)
    gravados = []
    for item in itens:
        entrada = relatorio.get(item["id"])
        if not entrada or not entrada.get("ok"):
            raise ValueError("%s sem download ok em relatorio.json" % item["id"])
        with open(os.path.join(pasta_fontes, os.path.basename(entrada["arquivo"])), "rb") as f:
            html = f.read()
        for caminho, conteudo in montar_lei(dict(item, url=entrada["url"]), html).items():
            destino = os.path.join(pasta_saida, *caminho.split("/"))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "w", encoding="utf-8", newline="\n") as f:
                f.write(conteudo)
            gravados.append(caminho)
    return gravados


def main(argv):
    if len(argv) > 2 or (len(argv) == 2 and argv[1] in ("-h", "--help")):
        print(__doc__)
        return 2
    with open(argv[1] if len(argv) == 2 else FONTES_JSON, encoding="utf-8") as f:
        itens = json.load(f)
    for caminho in escrever_leis(itens, PASTA_FONTES, LEIS):
        print("leis: gravado leis/%s" % caminho)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
