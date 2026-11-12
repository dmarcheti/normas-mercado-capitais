#!/usr/bin/env python3
"""Teste 2 (final): a norma montada pelo histórico == o consolidado da CVM.

diferencas_final(md_norma, md_consolidado, aceitas=()) -> lista de diferenças
(vazia = ok). Compara linha a linha, depois de normalizar artigos e texto (ver
normalizar.py) e a partir do primeiro `## Art.`; título, ementa e considerandos
ficam de fora (a ementa vai no frontmatter e o título do consolidado traz a lista
de atos). Na norma, linhas `# título` (título de parte, Decisão 6) não contam.
Tabelas: compara o número delas e as células não vazias (Decisão 10). Linha de
tabela que a normalização esvazia (anotação de alteração dentro da tabela) continua
na tabela, sem partir; tabela sem nenhuma célula com texto depois da normalização
(toda riscada ou revogada) não conta.

Divergências aceitas (Decisão 11, `fontes/divergencias-aceitas.json`): cada
entrada {id, dispositivo, consolidado, norma, motivo, ref} tira do diff o par de
linhas que casa exatamente. Entrada sem par = erro "aceita não usada"; o
dispositivo tem de aparecer no `incerteza` da norma.

Uso: python3 scripts/teste_final.py <id> [--norma ARQ.md] [--consolidado ARQ.docx]
                                         [--aceitas ARQ.json]
--norma aceita o index.md de uma norma em partes (as partes entram na ordem do
índice). Sem --consolidado, usa dados/resolNNNconsolid.docx (baixa se faltar, com
a URL do inventário). As aceitas vêm de fontes/divergencias-aceitas.json sozinhas.
Saída 0 = ok; 1 = diferenças; 2 = uso/erro.
"""
import difflib
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from converter import docx_para_md, normalizar_artigos  # noqa: E402
from normalizar import normalizar_texto  # noqa: E402
from validar import texto_da_norma  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NORMAS = os.path.join(RAIZ, "plugins", "normas", "skills", "consultar-normas", "normas")
ACEITAS = os.path.join(RAIZ, "fontes", "divergencias-aceitas.json")
CAMPOS_ACEITA = ("id", "dispositivo", "consolidado", "norma", "motivo", "ref")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_HEADING = re.compile(r"^## Art\. (.+)$")
_TITULO_PARTE = re.compile(r"^# ")
_SEPARADOR = re.compile(r"^:?-{1,}:?$")


def _sem_assinatura(linhas):
    """Tira o bloco final "Original assinado por / NOME / Cargo" do consolidado
    (o DOU, de onde vem a norma, não o traz como texto normativo)."""
    for i in range(max(0, len(linhas) - 5), len(linhas)):
        if linhas[i].strip().lower() == "original assinado por":
            return linhas[:i]
    return linhas


def _celulas(linha):
    """Células não vazias de uma linha de tabela; [] se for só separador/vazia."""
    celulas = [c.strip() for c in linha.strip().strip("|").split("|")]
    celulas = [c for c in celulas if c]
    if all(_SEPARADOR.match(c) for c in celulas):
        return []
    return celulas


def _tabelas(linhas):
    """(linhas com cada linha de tabela reduzida às células não vazias, nº de tabelas).
    Uma tabela é uma sequência de linhas seguidas que começam com `|`; só conta se
    tiver ao menos uma célula com texto."""
    saida, n, com_texto = [], 0, False
    for l in linhas:
        if l.lstrip().startswith("|"):
            celulas = _celulas(l)
            if celulas:
                if not com_texto:
                    n += 1
                    com_texto = True
                saida.append("| " + " | ".join(celulas) + " |")
        else:
            com_texto = False
            saida.append(l)
    return saida, n


def _linhas(md, norma=False):
    """(linhas comparáveis a partir do primeiro `## Art.`, nº de tabelas)."""
    md = _FRONTMATTER.sub("", md, count=1)
    originais = normalizar_artigos(md).split("\n")
    brutas = normalizar_texto("\n".join(originais)).split("\n")
    # a normalização apaga a anotação de alteração dentro da tabela; a linha vira
    # "|" para a tabela não se partir (_tabelas descarta a linha sem células)
    brutas = ["|" if not l.strip() and o.lstrip().startswith("|") else l
              for o, l in zip(originais, brutas)]
    if norma:
        brutas = [l for l in brutas if not _TITULO_PARTE.match(l)]
    for i, l in enumerate(brutas):
        if _HEADING.match(l):
            brutas = brutas[i:]
            break
    else:
        return [], 0
    linhas, n = _tabelas(brutas)
    return _sem_assinatura([l for l in linhas if l.strip()]), n


def _contexto(linhas, i):
    while i >= 0:
        m = _HEADING.match(linhas[i])
        if m:
            return "Art. " + m.group(1)
        i -= 1
    return "?"


def _incerteza(md_norma):
    m = re.match(r"\A---\n(.*?)\n---\n", md_norma, re.S)
    for l in (m.group(1) if m else "").split("\n"):
        if l.startswith("incerteza:"):
            return l[len("incerteza:"):].strip()
    return ""


def _aplicar_aceitas(difs, aceitas, incerteza):
    """Tira de `difs` (lista de dicts lado/texto) o que as aceitas cobrem; devolve
    (restantes, erros, nº de aceitas usadas)."""
    erros, usadas, vistas = [], 0, []
    for a in aceitas:
        base = a["dispositivo"].split(",")[0].strip()
        if base.lower() not in incerteza.lower():
            erros.append("aceita fora do incerteza: %s não aparece no incerteza da norma" % a["dispositivo"])
        achados = []
        for lado in ("consolidado", "norma"):
            if not a[lado]:
                continue
            alvo = next((d for d in difs if d["lado"] == lado and d["texto"] == a[lado]
                         and d not in achados), None)
            if alvo is None:
                achados = None
                break
            achados.append(alvo)
        if not achados:
            # a entrada cobre as linhas iguais no mesmo contexto; cópia sem par em
            # outro contexto não é erro
            if a in vistas:
                continue
            erros.append("aceita não usada: %s (%s)" % (a["dispositivo"], a["ref"]))
            continue
        difs = [d for d in difs if d not in achados]
        vistas.append(a)
        usadas += 1
    return difs, erros, usadas


def analisar_final(md_norma, md_consolidado, aceitas=()):
    """(diferenças, nº de aceitas usadas). Ver diferencas_final."""
    norma, n_norma = _linhas(md_norma, norma=True)
    cons, n_cons = _linhas(md_consolidado)
    if not norma:
        return ["norma sem nenhum artigo (## Art.)"], 0
    if not cons:
        return ["consolidado sem nenhum artigo"], 0
    difs = []
    ops = difflib.SequenceMatcher(None, cons, norma, autojunk=False).get_opcodes()
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        for i in range(i1, i2):
            difs.append({"lado": "consolidado", "texto": cons[i], "ctx": _contexto(cons, i)})
        for j in range(j1, j2):
            difs.append({"lado": "norma", "texto": norma[j], "ctx": _contexto(norma, j)})
    # entrada com dispositivo "tabelas" aceita a diferença de contagem: norma e
    # consolidado trazem os números ("42" e "41"), não linhas de texto
    de_tabela = [a for a in aceitas if a["dispositivo"] == "tabelas"]
    aceitas = [a for a in aceitas if a["dispositivo"] != "tabelas"]
    difs, erros, usadas = _aplicar_aceitas(difs, aceitas, _incerteza(md_norma))
    saida = []
    for a in de_tabela:
        if "tabelas" not in _incerteza(md_norma).lower():
            erros.append("aceita fora do incerteza: tabelas não aparece no incerteza da norma")
        if (a["norma"], a["consolidado"]) == (str(n_norma), str(n_cons)) and n_norma != n_cons:
            usadas += 1
            n_cons = n_norma
        else:
            erros.append("aceita não usada: tabelas (%s)" % a["ref"])
    if n_norma != n_cons:
        saida.append("tabelas: %d na norma, %d no consolidado" % (n_norma, n_cons))
    for d in difs:
        rotulo = "só no consolidado" if d["lado"] == "consolidado" else "só na norma"
        saida.append("[%s] %s: %s" % (d["ctx"], rotulo, d["texto"]))
    return saida + erros, usadas


def diferencas_final(md_norma, md_consolidado, aceitas=()):
    return analisar_final(md_norma, md_consolidado, aceitas)[0]


def carregar_aceitas(caminho, id_norma):
    """Entradas de `caminho` para `id_norma`; [] se o arquivo não existe.
    ValueError se alguma entrada não trouxer os seis campos."""
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        entradas = json.load(f)
    if not isinstance(entradas, list):
        raise ValueError("%s: esperada uma lista de entradas" % caminho)
    for e in entradas:
        faltam = [c for c in CAMPOS_ACEITA if not isinstance(e, dict) or c not in e]
        if faltam:
            raise ValueError("%s: entrada sem %s" % (caminho, ", ".join(faltam)))
    return [e for e in entradas if e["id"] == id_norma]


def _numero(id_norma):
    m = re.fullmatch(r"cvm-res-(\d+)", id_norma)
    return int(m.group(1)) if m else None


def _baixar(url, destino):
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r, open(destino, "wb") as f:
        f.write(r.read())


def _caminho_norma(numero, informado):
    """Arquivo da norma: o informado (ou relativo ao acervo), ou NNNN.md / NNNN/index.md."""
    if informado:
        return informado if os.path.exists(informado) else os.path.join(NORMAS, informado)
    base = os.path.join(NORMAS, "cvm", "resolucoes", "%04d" % numero)
    return base + ".md" if os.path.exists(base + ".md") else os.path.join(base, "index.md")


def main(argv):
    args = argv[1:]
    opcoes = {}
    for chave in ("--norma", "--consolidado", "--aceitas"):
        if chave in args:
            i = args.index(chave)
            opcoes[chave] = args[i + 1] if i + 1 < len(args) else None
            del args[i:i + 2]
    if len(args) != 1 or None in opcoes.values():
        print(__doc__)
        return 2
    numero = _numero(args[0])
    if numero is None:
        print("teste_final: id inválido %r (esperado cvm-res-N)" % args[0])
        return 2
    norma = _caminho_norma(numero, opcoes.get("--norma"))
    consolidado = opcoes.get("--consolidado") or os.path.join(RAIZ, "dados", "resol%03dconsolid.docx" % numero)
    if not os.path.exists(norma):
        print("teste_final: norma não encontrada: %s" % norma)
        return 2
    if not os.path.exists(consolidado):
        from inventario import carregar_inventario
        item = next((x for x in carregar_inventario(os.path.join(RAIZ, "fontes", "inventario.json"))
                     if x["id"] == args[0]), None)
        url = (item or {}).get("url_consolidado", {}).get("docx")
        if not url:
            print("teste_final: sem consolidado DOCX no inventário para %s" % args[0])
            return 2
        _baixar(url, consolidado)
    try:
        aceitas = carregar_aceitas(opcoes.get("--aceitas") or ACEITAS, args[0])
    except ValueError as e:
        print("teste_final: %s" % e)
        return 2
    dif, n_aceitas = analisar_final(texto_da_norma(norma), docx_para_md(consolidado), aceitas)
    for d in dif:
        print(d)
    print("teste_final: %s, %d diferença(s), %d aceita(s)" % (args[0], len(dif), n_aceitas))
    return 1 if dif else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
