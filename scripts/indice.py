#!/usr/bin/env python3
"""Índice das normas do acervo e dos julgados (SPEC v0.5.0).

gerar_indice(raiz, acervo=None, perimetro=None, acervo_bcb=None) -> (arquivos, itens).
`raiz` é `plugins/normas/normas`; `acervo` é o caminho de `fontes/acervo.json` (None ou
arquivo ausente = sem grupos e sem verbetes); `perimetro` e `acervo_bcb`, os de
`fontes/perimetro-camada4.json` e `fontes/acervo-bcb.json` (None ou ausente = sem a
seção de atos só alteradores do CMN e do BCB). `arquivos` mapeia o caminho relativo à
raiz no conteúdo:

- `indice.md`: resumo curto (aviso, perímetro, contagem por tipo e link para cada
  subíndice);
- `indices/resolucoes.md` (por grupo temático do Estoque Regulatório da CVM, as
  normas contábeis por último), `indices/instrucoes.md`,
  `indices/pareceres-orientacao.md`, `indices/oficios-circulares.md` (por pasta da
  CVM, data decrescente, com os verbetes sem texto do acervo.json), `indices/leis.md`
  (leis, leis complementares e decretos), `indices/cmn.md` e `indices/bcb.md` (por
  tipo; ao fim, os atos só alteradores do perímetro que tocam norma do acervo, sem
  arquivo, com ementa e link do BCB), `indices/anbima.md` e `indices/b3.md` (por tipo)
  e `indices/alteradoras.md`. Subíndice vazio não é gerado;
- `normas.json`: todas as normas (sem os atos alteradores nem os verbetes), cada uma
  {id, tipo, titulo, ementa, situacao, vigente_ate_ato, caminho} mais `grupo`
  (resolução no Estoque) e `baixado_em` (lei, decreto, LC, CMN, BCB e autorregulação);
- v0.5.0: `indices/citacoes/<id>.md` (índice reverso: dispositivo -> pareceres, ofícios e
  autorregulação que o citam, pelo `citacoes.py`; acima de 40 KB, a pasta
  `indices/citacoes/<id>/` com `index.md` e um arquivo por artigo, `art-0155.md`,
  `anexo-ii-art-0002.md`) e `indices/citacoes.md`; nada sem citação.

gerar_indice_julgados(raiz, normas) -> (arquivos, n): índices de um plugin `julgados-*`
(`indice.md`, `indices/<tipo>-<ano>.md`, `indices/tema-<tema>.md`, `indices/norma-<id>.md`).
Sem raiz posicional, o script cuida das normas e de todo `plugins/julgados-*/julgados`; com
uma raiz chamada `julgados`, só dela (normas lidas do normas.json); com outra raiz, só normas.

Uso: python3 scripts/indice.py [raiz] [--acervo CAMINHO] [--perimetro CAMINHO]
                               [--acervo-bcb CAMINHO]              grava os arquivos
     python3 scripts/indice.py ... --verificar                    saída 1 se defasados
A raiz padrão é plugins/normas/normas; os JSON padrão, os de fontes/. Ao
gravar, apaga de `indices/` o subíndice que não é mais gerado; `--verificar` acusa
esse subíndice. Sem data de geração: a saída só muda quando o acervo muda.
"""
import glob
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import citacoes as cit  # noqa: E402
from validar import (  # noqa: E402
    TIPOS, TIPOS_AUTORREGULACAO, TIPOS_BCB, arquivos_de_julgados, arquivos_de_normas, ler_frontmatter,
    texto_da_norma,
)

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
RAIZ_PADRAO = os.path.join(REPO, "plugins", "normas", "normas")
ACERVO_PADRAO = os.path.join(REPO, "fontes", "acervo.json")
PERIMETRO_PADRAO = os.path.join(REPO, "fontes", "perimetro-camada4.json")
ACERVO_BCB_PADRAO = os.path.join(REPO, "fontes", "acervo-bcb.json")
PASTA_SUBINDICES = "indices"
SEM_GRUPO = "Sem grupo no Estoque Regulatório"
AVISO = ("Material não oficial. Não substitui o Diário Oficial da União nem os sites dos órgãos "
         "e entidades de origem.")
GERADO = "Gerado por `scripts/indice.py`; não edite à mão."

ORDEM_TIPOS = ["resolucao", "instrucao", "parecer-orientacao", "oficio-circular",
               "lei", "lei-complementar", "decreto",
               "resolucao-cmn", "resolucao-bcb", "resolucao-conjunta", "circular", "carta-circular",
               "instrucao-normativa-bcb"] + list(TIPOS_AUTORREGULACAO)
NOME_TIPO = {
    "resolucao": "Resolução CVM",
    "instrucao": "Instrução CVM",
    "parecer-orientacao": "Parecer de Orientação CVM",
    "lei": "Lei",
    "lei-complementar": "Lei Complementar",
    "decreto": "Decreto",
    "resolucao-cmn": "Resolução CMN",
    "resolucao-bcb": "Resolução BCB",
    "resolucao-conjunta": "Resolução Conjunta",
    "circular": "Circular",
    "carta-circular": "Carta Circular",
    "instrucao-normativa-bcb": "Instrução Normativa BCB",
}
SECAO_FEDERAL = {"lei": "Leis", "lei-complementar": "Leis complementares", "decreto": "Decretos"}
SECAO_TIPO = {
    "resolucao-cmn": "Resoluções CMN",
    "resolucao-bcb": "Resoluções BCB",
    "resolucao-conjunta": "Resoluções Conjuntas",
    "circular": "Circulares",
    "carta-circular": "Cartas Circulares",
    "instrucao-normativa-bcb": "Instruções Normativas BCB",
    "codigo-autorregulacao": "Códigos de autorregulação",
    "regras-procedimentos": "Regras e procedimentos",
    "regulamento": "Regulamentos",
    "manual": "Manuais",
    "glossario": "Glossários",
    "orientacao-autorregulacao": "Orientações (deliberações, pareceres, alinhamentos, perguntas e respostas)",
}
TIPOS_CMN = tuple(t for t in TIPOS_BCB if TIPOS[t][0] == "cmn")
TIPOS_SO_BCB = tuple(t for t in TIPOS_BCB if TIPOS[t][0] == "bcb")
SECAO_ALTERADORAS = "Atos só alteradores, sem arquivo"
# Prefixo do campo `altera` de perimetro-camada4.json (sem acento) -> tipo. "resolucao" sem
# complemento é do CMN (as resoluções até a 4.838 não levam "CMN" no nome).
ALTERA_TIPO = [
    ("resolucao conjunta", "resolucao-conjunta"),
    ("resolucao cmn", "resolucao-cmn"),
    ("resolucao bcb", "resolucao-bcb"),
    ("resolucao", "resolucao-cmn"),
    ("carta circular", "carta-circular"),
    ("circular", "circular"),
    ("instrucao normativa bcb", "instrucao-normativa-bcb"),
]
SITUACAO_LEGIVEL = {"nao-informada": "não informada pela CVM"}
# subíndice -> (título, tipos que entram nele)
SUBINDICES = [
    ("resolucoes", "Resoluções CVM", ("resolucao",)),
    ("instrucoes", "Instruções CVM", ("instrucao",)),
    ("pareceres-orientacao", "Pareceres de Orientação CVM", ("parecer-orientacao",)),
    ("oficios-circulares", "Ofícios-Circulares CVM", ("oficio-circular",)),
    ("leis", "Leis, leis complementares e decretos", ("lei", "lei-complementar", "decreto")),
    ("cmn", "Normas do CMN", TIPOS_CMN),
    ("bcb", "Normas do BCB", TIPOS_SO_BCB),
    ("anbima", "Autorregulação ANBIMA", TIPOS_AUTORREGULACAO),
    ("b3", "Autorregulação B3", TIPOS_AUTORREGULACAO),
    ("alteradoras", "Atos alteradores (texto integral do ato)", ()),
]
# v0.5.0: índice reverso de citações (dispositivo -> documentos de interpretação que o citam)
PASTA_CITACOES = "citacoes"
TIPOS_INTERPRETACAO = ("parecer-orientacao", "oficio-circular") + tuple(TIPOS_AUTORREGULACAO)
TITULO_CURTO = 90
LIMITE_SUBINDICE = 40 * 1024  # bytes: acima disso, o subíndice de citações vira pasta
assert set(ORDEM_TIPOS) == set(TIPOS)


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        pares, _corpo, erro = ler_frontmatter(f.read())
    if erro:
        raise ValueError("%s: %s" % (caminho, erro))
    return dict((c, v) for c, v in pares if c is not None)


def ler_acervo(caminho):
    """(grupos {numero: grupo}, ofícios [{titulo, data, superintendencia, ...}]) do acervo.json."""
    if not caminho or not os.path.exists(caminho):
        return {}, []
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    grupos = (dados.get("estoque_regulatorio") or {}).get("grupos") or {}
    return {str(k): v for k, v in grupos.items()}, dados.get("oficios_circulares") or []


def _lista_json(caminho):
    """Lista de normas de um JSON de fontes/: a própria lista, ou a chave `normas`."""
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, list) else (dados.get("normas") or [])


def ler_alteradoras(perimetro, acervo_bcb):
    """Atos só alteradores do perímetro da camada 4: [{tipo, numero, data, altera: [(tipo,
    numero)], ementa, url}]. Vazio se algum dos dois arquivos faltar."""
    if not (perimetro and acervo_bcb and os.path.exists(perimetro) and os.path.exists(acervo_bcb)):
        return []
    bcb = {(n.get("tipo"), int(n["numero"])): n for n in _lista_json(acervo_bcb)
           if str(n.get("numero", "")).isdigit()}
    atos = []
    for n in _lista_json(perimetro):
        if n.get("decisao") != "alteradora" or not str(n.get("numero", "")).isdigit():
            continue
        altera = [a for a in (_ref_altera(x) for x in n.get("altera") or []) if a]
        if not altera:
            continue
        fonte = bcb.get((n.get("tipo"), int(n["numero"]))) or {}
        atos.append({"tipo": n.get("tipo"), "numero": int(n["numero"]), "data": n.get("data") or "",
                     "altera": altera, "ementa": fonte.get("assunto") or "",
                     "url": fonte.get("url_pagina") or ""})
    return atos


def _ref_altera(texto):
    """'resolucao cmn 4.966' -> ('resolucao-cmn', 4966); fora do padrão -> None."""
    t = " ".join(str(texto).lower().split())
    for prefixo, tipo in ALTERA_TIPO:
        if t.startswith(prefixo + " "):
            numero = t[len(prefixo) + 1:].replace(".", "")
            return (tipo, int(numero)) if numero.isdigit() else None
    return None


def _arquivos(raiz, pasta):
    achados = []
    for dirpath, _dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) == pasta:
            achados += [os.path.join(dirpath, n) for n in nomes if n.endswith(".md")]
    return achados


def _milhar(n):
    return format(int(n), ",").replace(",", ".")


def _slug_do_verbete(oc):
    """Nome do arquivo do ofício: o `slug` do acervo (normalizado e único entre os ofícios);
    em acervo antigo, sem o campo, o nome da url_pagina."""
    if oc.get("slug"):
        return oc["slug"]
    url = oc.get("url_pagina") or oc.get("url_pdf") or ""
    return os.path.splitext(url.rstrip("/").split("/")[-1])[0]


def _titulo(v, caminho_rel, titulos_oc):
    ano = v["data"][:4]
    if v["tipo"] == "oficio-circular":
        slug = v["id"][len("cvm-"):]
        if slug in titulos_oc:
            return titulos_oc[slug]
        pasta = caminho_rel.split("/")[2] if caminho_rel.count("/") >= 3 else ""
        return "Ofício-Circular nº %s/%s/CVM/%s" % (v["numero"], ano, pasta.upper().replace("-", "/"))
    if v["tipo"] in TIPOS_AUTORREGULACAO:
        return v["ementa"]  # sem número: o documento é nomeado pela ementa (título na entidade)
    if v["tipo"] in ("lei", "decreto") or v["tipo"] in TIPOS_BCB:
        return "%s nº %s/%s" % (NOME_TIPO[v["tipo"]], _milhar(v["numero"]), ano)
    if v["tipo"] in NOME_TIPO:
        return "%s nº %s/%s" % (NOME_TIPO[v["tipo"]], v["numero"], ano)
    return "%s nº %s/%s" % (v["tipo"], v["numero"], ano)


def _item(raiz, caminho, grupos, titulos_oc):
    v = _ler(caminho)
    rel = os.path.relpath(caminho, raiz).replace(os.sep, "/")
    item = {
        "id": v["id"],
        "tipo": v["tipo"],
        "titulo": _titulo(v, rel, titulos_oc),
        "ementa": v["ementa"],
        "situacao": v["situacao"],
        "vigente_ate_ato": v["vigente_ate_ato"],
        "caminho": rel,
    }
    if v["tipo"] == "resolucao" and v["numero"] in grupos:
        item["grupo"] = grupos[v["numero"]]
    if v["tipo"] in ("lei", "lei-complementar", "decreto") or v["tipo"] in TIPOS_BCB + TIPOS_AUTORREGULACAO:
        item["baixado_em"] = v["baixado_em"]
    item["_data"] = v["data"]
    item["_orgao"] = v["orgao"]
    item["_numero"] = int(v["numero"]) if v["numero"].isdigit() else 0
    return item


def _chave(item):
    tipo = item["tipo"]
    pos = ORDEM_TIPOS.index(tipo) if tipo in ORDEM_TIPOS else len(ORDEM_TIPOS)
    # ofícios: por pasta e slug (o número se repete entre pastas e anos)
    numero = 0 if tipo == "oficio-circular" else item["_numero"]
    return (pos, numero, item["caminho"])


def _celula(txt):
    return " ".join((txt or "").split()).replace("|", "\\|")


def _situacao(s):
    return SITUACAO_LEGIVEL.get(s, s)


def _eh_contabil(grupo):
    g = grupo.lower()
    return "contáb" in g or "contab" in g


def _cabecalho(titulo, extra=()):
    return ["# %s" % titulo, "", AVISO, GERADO,
            "Caminhos relativos a `normas/` (a pasta do `indice.md`)."] + list(extra) + [""]


def _tabela_cvm(itens):
    md = ["| Norma | Ementa | Situação | Vigente até o ato | Arquivo |", "|---|---|---|---|---|"]
    for i in itens:
        md.append("| %s | %s | %s | %s | %s |" % (
            i["titulo"], _celula(i["ementa"]), _situacao(i["situacao"]),
            i["vigente_ate_ato"] or "redação original", i["caminho"]))
    return md


def _md_resolucoes(itens):
    por_grupo = {}
    for i in itens:
        por_grupo.setdefault(i.get("grupo", SEM_GRUPO), []).append(i)
    contabeis = sorted(g for g in por_grupo if g != SEM_GRUPO and _eh_contabil(g))
    comuns = sorted(g for g in por_grupo if g != SEM_GRUPO and not _eh_contabil(g))
    ordem = comuns + ([SEM_GRUPO] if SEM_GRUPO in por_grupo else []) + contabeis
    md = _cabecalho("Resoluções CVM", [
        "Agrupadas pelo grupo temático do Estoque Regulatório da CVM; as normas contábeis vêm por último."])
    for g in ordem:
        md += ["## %s" % g, ""] + _tabela_cvm(por_grupo[g]) + [""]
    return md


def _md_simples(titulo, itens):
    return _cabecalho(titulo) + _tabela_cvm(itens) + [""]


def _md_oficios(itens, verbetes):
    linhas = {}  # pasta -> [(data, ordem, linha)]
    for i in itens:
        pasta = i["caminho"].split("/")[2]
        linhas.setdefault(pasta, []).append((i["_data"], i["titulo"], "| %s | %s | %s | %s | %s |" % (
            i["titulo"], i["_data"], _celula(i["ementa"]), _situacao(i["situacao"]), i["caminho"])))
    for oc in verbetes:
        link = oc.get("url_pdf") or oc.get("url_pagina") or ""
        texto = "só verbete; texto não incluído" + (" ([link](%s))" % link if link else "")
        linhas.setdefault(oc.get("superintendencia") or "sem-pasta", []).append((
            oc.get("data", ""), oc.get("titulo", ""), "| %s | %s | %s | %s | %s |" % (
                _celula(oc.get("titulo", "")), oc.get("data", ""), _celula(oc.get("descricao", "")),
                _situacao("nao-informada"), texto)))
    md = _cabecalho("Ofícios-Circulares CVM", [
        "Por pasta da CVM (superintendência), do mais recente ao mais antigo. A CVM não informa a "
        "vigência dos ofícios. Os marcados \"só verbete\" não têm o texto no acervo: siga o link."])
    for pasta in sorted(linhas):
        md += ["## %s (`%s`)" % (pasta.upper().replace("-", "/"), pasta), "",
               "| Ofício | Data | Assunto | Situação | Texto |", "|---|---|---|---|---|"]
        for _d, _t, linha in sorted(linhas[pasta], key=lambda x: (x[0], x[1]), reverse=True):
            md.append(linha)
        md.append("")
    return md


def _md_leis(itens):
    md = _cabecalho("Leis, leis complementares e decretos", [
        "Texto compilado do Planalto; a data-base é `baixado_em`."])
    for tipo in ("lei", "lei-complementar", "decreto"):
        do_tipo = [i for i in itens if i["tipo"] == tipo]
        if not do_tipo:
            continue
        md += ["## %s" % SECAO_FEDERAL[tipo], "",
               "| Norma | Ementa | Situação | Data-base | Arquivo |", "|---|---|---|---|---|"]
        for i in do_tipo:
            md.append("| %s | %s | %s | %s | %s |" % (
                i["titulo"], _celula(i["ementa"]), _situacao(i["situacao"]), i["baixado_em"], i["caminho"]))
        md.append("")
    return md


def _titulo_ato(tipo, numero, data):
    return "%s nº %s/%s" % (NOME_TIPO.get(tipo, tipo), _milhar(numero), data[:4])


def _md_bcb(titulo, itens, tipos, alteradoras):
    """CMN ou BCB: uma seção por tipo; ao fim, os atos só alteradores que tocam estas normas."""
    md = _cabecalho(titulo, [
        "Texto compilado pelo BCB, sem conferência contra o DOU; a data-base é `baixado_em`."])
    for tipo in tipos:
        do_tipo = [i for i in itens if i["tipo"] == tipo]
        if not do_tipo:
            continue
        md += ["## %s" % SECAO_TIPO[tipo], "",
               "| Norma | Ementa | Situação | Data-base | Arquivo |", "|---|---|---|---|---|"]
        for i in do_tipo:
            md.append("| %s | %s | %s | %s | %s |" % (
                i["titulo"], _celula(i["ementa"]), _situacao(i["situacao"]), i["baixado_em"], i["caminho"]))
        md.append("")
    if alteradoras:
        md += ["## %s" % SECAO_ALTERADORAS, "",
               "Atos do perímetro que só alteram normas deste subíndice. A alteração já está no texto "
               "compilado da norma alterada; o ato não tem arquivo no acervo: siga o link.", "",
               "| Ato | Data | Ementa | Altera | Link |", "|---|---|---|---|---|"]
        for a, alteradas in alteradoras:
            link = "[BCB](%s)" % a["url"] if a["url"] else ""
            md.append("| %s | %s | %s | %s | %s |" % (
                _titulo_ato(a["tipo"], a["numero"], a["data"]), a["data"], _celula(a["ementa"]),
                "; ".join(alteradas), link))
        md.append("")
    return md


def _md_autorregulacao(titulo, itens):
    md = _cabecalho(titulo, [
        "Autorregulação: texto de titularidade da entidade, uso informativo (ver "
        "`autorregulacao/README.md`). Vincula só aderentes e participantes; não é norma estatal. "
        "Cite o documento com a data de início de vigência ou da versão."])
    for tipo in TIPOS_AUTORREGULACAO:
        do_tipo = [i for i in itens if i["tipo"] == tipo]
        if not do_tipo:
            continue
        md += ["## %s" % SECAO_TIPO[tipo], "",
               "| Documento | Vigência ou versão | Data-base | Arquivo |", "|---|---|---|---|"]
        for i in do_tipo:
            md.append("| %s | %s | %s | %s |" % (
                _celula(i["titulo"]), i["_data"], i["baixado_em"], i["caminho"]))
        md.append("")
    return md


def _alteradoras_do_subindice(atos, itens):
    """[(ato, [títulos das normas alteradas deste subíndice])], só os atos que tocam `itens`
    e que não têm arquivo no acervo."""
    por_ref = {(i["tipo"], i["_numero"]): i["titulo"] for i in itens}
    saida = []
    for a in atos:
        alteradas = [por_ref[r] for r in a["altera"] if r in por_ref]
        if alteradas:
            saida.append((a, list(dict.fromkeys(alteradas))))
    return sorted(saida, key=lambda x: (ORDEM_TIPOS.index(x[0]["tipo"]) if x[0]["tipo"] in ORDEM_TIPOS
                                        else len(ORDEM_TIPOS), x[0]["numero"]))


def _md_alteradoras(atos):
    md = _cabecalho("Atos alteradores (texto integral do ato)") + ["| Ato | Ementa | Arquivo |", "|---|---|---|"]
    for i in atos:
        md.append("| %s | %s | %s |" % (i["titulo"], _celula(i["ementa"]), i["caminho"]))
    return md + [""]


def _md_resumo(contagens, n_citadas=0):
    md = [
        "# Índice das normas", "", AVISO, GERADO, "",
        "## Perímetro", "",
        "- Camada 1: Resoluções e Instruções da CVM, em texto vigente.",
        "- Camada 2: Pareceres de Orientação e Ofícios-Circulares da CVM (a CVM não informa a vigência deles).",
        "- Camada 3: leis, leis complementares e decretos federais, no texto compilado do Planalto.",
        "- Camada 4: normas do CMN e do BCB, no texto compilado pelo BCB (sem conferência contra o DOU).",
        "- Camada 5: autorregulação, texto de titularidade da ANBIMA e da B3, uso informativo "
        "(ver `autorregulacao/README.md`).",
        "",
        "## Conteúdo", "",
        "O detalhe de cada tipo (ementa, situação, data-base e arquivo) está no subíndice.", "",
        "| Tipo | Arquivos | Subíndice |", "|---|---|---|",
    ]
    for nome, titulo, n, extra in contagens:
        rel = "%s/%s.md" % (PASTA_SUBINDICES, nome)
        md.append("| %s | %d | [%s](%s)%s |" % (titulo, n, rel, rel, extra))
    md += ["", "## Citações e julgados", ""]
    if n_citadas:
        rel = "%s/%s.md" % (PASTA_SUBINDICES, PASTA_CITACOES)
        md.append("- [%s](%s): por norma e dispositivo, os pareceres, ofícios-circulares e documentos de "
                  "autorregulação do acervo que o citam (%d norma(s) citada(s); extração por script)." % (rel, rel, n_citadas))
    md.append("- Os julgados da CVM e do CRSFN ficam nos plugins `julgados-*`. Julgado não é norma: diz o que "
              "se decidiu num caso, com a redação da época.")
    return md + [""]


def gerar_indice(raiz, acervo=None, perimetro=None, acervo_bcb=None):
    grupos, oficios = ler_acervo(acervo)
    titulos_oc = {_slug_do_verbete(oc): oc["titulo"] for oc in oficios if oc.get("titulo")}
    caminhos = arquivos_de_normas(raiz)
    itens = sorted((_item(raiz, c, grupos, titulos_oc) for c in caminhos), key=_chave)
    com_arquivo_bcb = {(i["tipo"], i["_numero"]) for i in itens if i["tipo"] in TIPOS_BCB}
    atos_bcb = [a for a in ler_alteradoras(perimetro, acervo_bcb)
                if (a["tipo"], a["numero"]) not in com_arquivo_bcb]
    atos = sorted((_item(raiz, c, {}, {}) for c in _arquivos(raiz, "alteradoras")),
                  key=lambda i: i["caminho"])
    com_arquivo = {i["id"][len("cvm-"):] for i in itens if i["tipo"] == "oficio-circular"}
    verbetes = [oc for oc in oficios if _slug_do_verbete(oc) not in com_arquivo]

    arquivos, contagens = {}, []
    for nome, titulo, tipos in SUBINDICES:
        do_tipo = [i for i in itens if i["tipo"] in tipos]
        extra = ""
        if nome == "resolucoes":
            md = _md_resolucoes(do_tipo) if do_tipo else None
        elif nome == "oficios-circulares":
            md = _md_oficios(do_tipo, verbetes) if do_tipo or verbetes else None
            if verbetes:
                extra = " (mais %d só verbete, sem texto)" % len(verbetes)
        elif nome == "leis":
            md = _md_leis(do_tipo) if do_tipo else None
        elif nome in ("cmn", "bcb"):
            alt = _alteradoras_do_subindice(atos_bcb, do_tipo)
            md = _md_bcb(titulo, do_tipo, tipos, alt) if do_tipo else None
            if alt:
                extra = " (mais %d ato(s) só alterador(es), sem arquivo)" % len(alt)
        elif nome in ("anbima", "b3"):
            do_tipo = [i for i in do_tipo if i["_orgao"] == nome]
            md = _md_autorregulacao(titulo, do_tipo) if do_tipo else None
        elif nome == "alteradoras":
            do_tipo = atos
            md = _md_alteradoras(atos) if atos else None
        else:
            md = _md_simples(titulo, do_tipo) if do_tipo else None
        if md is None:
            continue
        arquivos["%s/%s.md" % (PASTA_SUBINDICES, nome)] = "\n".join(md).rstrip("\n") + "\n"
        contagens.append((nome, titulo, len(do_tipo), extra))
    citados = _citacoes_do_acervo(raiz, itens)
    arquivos.update(_md_citacoes(citados, {i["id"]: i for i in itens}))
    arquivos["indice.md"] = "\n".join(_md_resumo(contagens, len(citados))).rstrip("\n") + "\n"
    publicos = [{k: v for k, v in i.items() if not k.startswith("_")} for i in itens]
    arquivos["normas.json"] = json.dumps(publicos, ensure_ascii=False, indent=2) + "\n"
    return arquivos, publicos


# ---------------------------------------------------------------- citações (v0.5.0)

def _num_artigo(a):
    m = re.match(r"([\d.]+)º?(?:-([A-Z]))?", a)
    return (int(m.group(1).replace(".", "")), m.group(2) or "") if m else (0, a)


def _num_parte(p):
    """'' (parte geral) primeiro, depois os anexos (romano ou número) e os suplementos."""
    if not p:
        return (0, 0, "")
    tipo, ident = p.split(" ", 1)
    rom = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    if ident.isdigit():
        n = int(ident)
    elif set(ident) <= set(rom):
        n, ant = 0, 0
        for ch in reversed(ident):
            v = rom[ch]
            n, ant = (n - v, ant) if v < ant else (n + v, v)
    else:
        n = 0
    return (1 if tipo == "Anexo" else 2, n, ident)


def _ordem_dispositivo(d):
    return (_num_parte(d.get("parte", "")), _num_artigo(d["artigo"]), d.get("paragrafo", "") != "",
            d.get("paragrafo", ""), d.get("inciso", ""), d.get("alinea", ""))


def _citacoes_do_acervo(raiz, itens):
    """{id da norma citada: [(documento, citação)]}: o extrator sobre pareceres, ofícios e
    autorregulação; só normas do acervo, sem autocitação, sem repetir (documento, dispositivo)."""
    ids = frozenset(i["id"] for i in itens)
    citados = {}
    for doc in itens:
        if doc["tipo"] not in TIPOS_INTERPRETACAO:
            continue
        texto = texto_da_norma(os.path.join(raiz, *doc["caminho"].split("/")))
        _pares, texto, _erro = ler_frontmatter(texto)  # o frontmatter não entra no trecho
        vistos = set()
        for c in cit.extrair_citacoes(texto, ids=ids):
            if c["norma"].startswith("fora:") or c["norma"] == doc["id"]:
                continue
            d = cit.dispositivo(c)
            if d in vistos:
                continue
            vistos.add(d)
            citados.setdefault(c["norma"], []).append((doc, c))
    return citados


def _curto(txt, n=TITULO_CURTO):
    txt = " ".join((txt or "").split())
    return txt if len(txt) <= n else txt[:n - 1].rstrip() + "…"


def _nome_artigo(parte, artigo):
    """Nome estável e ordenável do arquivo de um artigo: 'art-0155', 'anexo-ii-art-0002',
    'art-1368-c'."""
    num, letra = _num_artigo(artigo)
    nome = "art-%04d" % num + ("-" + letra.lower() if letra else "")
    return (parte.lower().replace(" ", "-") + "-" if parte else "") + nome


def _secao_artigo(nid, parte, artigo, linhas):
    md = ["## %sart. %s" % (parte + ", " if parte else "", artigo), "",
          "| Dispositivo | Documento | Tipo | Data | Arquivo | Trecho |", "|---|---|---|---|---|---|"]
    for doc, c in sorted(linhas, key=lambda x: (_ordem_dispositivo(x[1]), x[0]["_data"], x[0]["caminho"])):
        md.append("| %s | %s | %s | %s | %s | %s |" % (
            cit.dispositivo(c)[len(nid) + 1:], _celula(_curto(doc["titulo"])), doc["tipo"], doc["_data"],
            doc["caminho"], _celula(c["trecho"])))
    return md + [""]


def _texto(md):
    return "\n".join(md).rstrip("\n") + "\n"


def _md_citacoes(citados, por_id):
    """`indices/citacoes/<id>.md` (uma seção por artigo citado) ou, acima de LIMITE_SUBINDICE
    bytes, a pasta `indices/citacoes/<id>/` (`index.md` e um arquivo por artigo); e
    `indices/citacoes.md`."""
    if not citados:
        return {}
    arquivos, linhas = {}, []
    explicacao = ("Pareceres, ofícios-circulares e documentos de autorregulação do acervo que citam esta norma, "
                  "por dispositivo. Extração por script (regex), sem conferência manual: abra o documento antes "
                  "de citá-lo.")
    for nid in sorted(citados, key=lambda x: _chave(por_id[x])):
        norma = por_id[nid]
        secoes = {}
        for doc, c in citados[nid]:
            secoes.setdefault((c["parte"], c["artigo"]), []).append((doc, c))
        ordem = sorted(secoes, key=lambda k: (_num_parte(k[0]), _num_artigo(k[1])))
        cab = ["", explicacao + " Norma: `%s`." % norma["caminho"]]
        md = _cabecalho("Citações: %s" % norma["titulo"], cab)
        for parte, artigo in ordem:
            md += _secao_artigo(nid, parte, artigo, secoes[(parte, artigo)])
        base = "%s/%s" % (PASTA_SUBINDICES, PASTA_CITACOES)
        unico = _texto(md)
        if len(unico.encode("utf-8")) <= LIMITE_SUBINDICE:
            arquivos["%s/%s.md" % (base, nid)] = unico
            link = "%s/%s.md" % (PASTA_CITACOES, nid)
        else:
            idx = _cabecalho("Citações: %s" % norma["titulo"], cab + [
                "Um arquivo por artigo citado, nesta pasta (o índice passaria de %d KB num arquivo só)."
                % (LIMITE_SUBINDICE // 1024)])
            idx += ["| Parte | Artigo | Citações | Arquivo |", "|---|---|---|---|"]
            for parte, artigo in ordem:
                nome = _nome_artigo(parte, artigo) + ".md"
                titulo = "Citações: %s, %sart. %s" % (norma["titulo"], parte + ", " if parte else "", artigo)
                arquivos["%s/%s/%s" % (base, nid, nome)] = _texto(
                    _cabecalho(titulo, cab) + _secao_artigo(nid, parte, artigo, secoes[(parte, artigo)]))
                idx.append("| %s | %s | %d | [%s](%s) |" % (parte or "parte geral", artigo,
                                                            len(secoes[(parte, artigo)]), nome, nome))
            arquivos["%s/%s/index.md" % (base, nid)] = _texto(idx)
            link = "%s/%s/index.md" % (PASTA_CITACOES, nid)
        docs = {d["id"] for d, _c in citados[nid]}
        linhas.append("| %s | %d | %d | [%s](%s) |" % (norma["titulo"], len(docs), len(citados[nid]), nid, link))
    resumo = _cabecalho("Citações por norma", [
        "", "Índice reverso: para cada norma do acervo, os pareceres, ofícios-circulares e documentos de "
        "autorregulação que citam um dispositivo dela. Extração por script (regex); só normas do acervo. "
        "Os links da última coluna são relativos a `indices/`; norma muito citada tem uma pasta, com um "
        "arquivo por artigo e o `index.md`."])
    resumo += ["| Norma | Documentos | Citações | Subíndice |", "|---|---|---|---|"] + linhas
    arquivos["%s/%s.md" % (PASTA_SUBINDICES, PASTA_CITACOES)] = "\n".join(resumo) + "\n"
    return arquivos


# ---------------------------------------------------------------- julgados (v0.5.0)

NOME_JULGADO = {
    "pas": "Processos Administrativos Sancionadores (PAS)",
    "termo-compromisso": "Termos de compromisso",
    "decisao-colegiado": "Decisões do Colegiado",
    "decisao-antiga": "Decisões antigas (1978 a 2001)",
    "acordao-crsfn": "Acórdãos do CRSFN (recursos contra decisões da CVM)",
}
AVISO_JULGADO = ("Julgado não é norma: diz o que a CVM (ou o CRSFN) decidiu num caso concreto, com a "
                 "redação das normas da época, e não vincula como norma. Para o texto vigente, use o "
                 "plugin `normas`.")
NOTA_REDACAO = "texto vigente hoje; o julgado aplicou a redação da época"
PERIMETRO_JULGADOS = {
    "julgados-pas": "Processos administrativos sancionadores (PAS) julgados pela CVM.",
    "julgados-tc-crsfn": "Termos de compromisso (aceitos e rejeitados) e acórdãos do CRSFN em recursos contra decisões da CVM.",
    "julgados-colegiado-2002-2008": "Decisões do Colegiado da CVM de 2002 a 2008 e decisões antigas (1978 a 2001).",
    "julgados-colegiado-2009-2015": "Decisões do Colegiado da CVM de 2009 a 2015.",
    "julgados-colegiado-2016-2026": "Decisões do Colegiado da CVM de 2016 em diante.",
}


def slug_tema(tema):
    t = unicodedata.normalize("NFKD", tema).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _cab_julgados(titulo, extra=()):
    return ["# %s" % titulo, "", AVISO, AVISO_JULGADO, GERADO,
            "Caminhos relativos a `julgados/` (a pasta do `indice.md`)."] + list(extra) + [""]


def _ler_julgados(raiz):
    itens = []
    for caminho in arquivos_de_julgados(raiz):
        v = _ler(caminho)
        v["_caminho"] = os.path.relpath(caminho, raiz).replace(os.sep, "/")
        itens.append(v)
    return sorted(itens, key=lambda v: (v.get("data", ""), v["_caminho"]), reverse=True)


def _tabela_julgados(itens, com_tipo=False, extra=None):
    cab = (["Tipo"] if com_tipo else []) + ["Processo", "Data", "Resultado", "Tema", "Ementa", "Arquivo"]
    if extra:
        cab = [extra[0]] + cab
    md = ["| %s |" % " | ".join(cab), "|%s" % ("---|" * len(cab))]
    for linha in itens:
        v, pre = (linha if extra else (linha, None))
        cel = ([v["tipo"]] if com_tipo else []) + [
            _celula(v.get("processo")) or "—", v.get("data", ""), v.get("resultado") or "—",
            v.get("tema") or "—", _celula(v.get("ementa")), v["_caminho"]]
        if extra:
            cel = [pre] + cel
        md.append("| %s |" % " | ".join(cel))
    return md


def _arquivo_norma(norma):
    return "norma-%s.md" % (norma.replace("fora:", "fora-"))


def gerar_indice_julgados(raiz, normas, link_normas="../../../normas/normas", plugin=None):
    """(arquivos, n_julgados) dos índices de um plugin de julgados. `raiz` é a pasta `julgados/`;
    `normas` mapeia o id da norma no item do normas.json (titulo, caminho); `link_normas` é o
    caminho de `julgados/indices/` até a raiz das normas. Sem julgados, nada é gerado."""
    itens = _ler_julgados(raiz)
    if not itens:
        return {}, 0
    plugin = plugin or os.path.basename(os.path.dirname(os.path.abspath(raiz)))
    arquivos = {}
    ordem_tipos = list(NOME_JULGADO)
    por_tipo_ano, por_tema, por_norma = {}, {}, {}
    for v in itens:
        por_tipo_ano.setdefault((v["tipo"], v.get("data", "")[:4]), []).append(v)
        if v.get("tema"):
            por_tema.setdefault(v["tema"], []).append(v)
        disps = [d for d in (cit.ler_dispositivo(x) for x in (v.get("dispositivos_citados") or "").split("; ")
                             if x) if d]
        com_disp = set()
        for d in disps:
            por_norma.setdefault(d["norma"], {"disp": [], "sem": []})["disp"].append((d, v))
            com_disp.add(d["norma"])
        for n in (v.get("normas_citadas") or "").split("; "):
            if n and n not in com_disp:
                por_norma.setdefault(n, {"disp": [], "sem": []})["sem"].append(v)

    for (tipo, ano), lista in por_tipo_ano.items():
        md = _cab_julgados("%s, %s" % (NOME_JULGADO.get(tipo, tipo), ano)) + _tabela_julgados(lista)
        arquivos["%s/%s-%s.md" % (PASTA_SUBINDICES, tipo, ano)] = "\n".join(md) + "\n"
    temas = {}
    for tema, lista in por_tema.items():
        rel = "%s/tema-%s.md" % (PASTA_SUBINDICES, slug_tema(tema))
        temas[tema] = (rel, len(lista))
        md = _cab_julgados("Julgados do tema %s" % tema) + _tabela_julgados(lista, com_tipo=True)
        arquivos[rel] = "\n".join(md) + "\n"
    normas_idx = {}
    for nid, grupos in por_norma.items():
        rel = "%s/%s" % (PASTA_SUBINDICES, _arquivo_norma(nid))
        if nid.startswith("fora:"):
            titulo, ref = nid[5:], "fora do acervo"
        elif nid in normas:
            titulo = normas[nid]["titulo"]
            ref = "[%s](%s/%s) (%s)" % (normas[nid]["caminho"], link_normas, normas[nid]["caminho"], NOTA_REDACAO)
        else:
            titulo, ref = nid, "não encontrada no normas.json"
        md = _cab_julgados("Julgados que citam %s" % titulo, ["", "Norma: %s." % ref])
        secoes = {}
        for d, v in grupos["disp"]:
            secoes.setdefault((d["parte"], d["artigo"]), []).append((d, v))
        for parte, artigo in sorted(secoes, key=lambda k: (_num_parte(k[0]), _num_artigo(k[1]))):
            linhas = sorted(secoes[(parte, artigo)], key=lambda x: (_ordem_dispositivo(x[0]), x[1]["_caminho"]))
            vistos, uniq = set(), []
            for d, v in linhas:
                rot = cit.dispositivo(d)[len(nid) + 1:]
                if (rot, v["_caminho"]) not in vistos:
                    vistos.add((rot, v["_caminho"]))
                    uniq.append((v, rot))
            md += ["## %sart. %s" % (parte + ", " if parte else "", artigo), ""]
            md += _tabela_julgados(uniq, com_tipo=True, extra=("Dispositivo",)) + [""]
        if grupos["sem"]:
            md += ["## Citada sem dispositivo identificado", ""] + _tabela_julgados(grupos["sem"], com_tipo=True) + [""]
        arquivos[rel] = "\n".join(md).rstrip("\n") + "\n"
        normas_idx[nid] = (rel, titulo, len({v["_caminho"] for _d, v in grupos["disp"]} |
                                              {v["_caminho"] for v in grupos["sem"]}))

    md = ["# Índice dos julgados: %s" % plugin, "", AVISO, AVISO_JULGADO, GERADO, "",
          "## Perímetro", "", PERIMETRO_JULGADOS.get(plugin, "Julgados do plugin `%s`." % plugin),
          "Sem nome de pessoa física nas linhas dos índices: cada julgado é descrito pela ementa.", "",
          "## Por tipo e ano", "", "| Tipo | Ano | Julgados | Subíndice |", "|---|---|---|---|"]
    for (tipo, ano) in sorted(por_tipo_ano, key=lambda k: (ordem_tipos.index(k[0]) if k[0] in ordem_tipos
                                                            else len(ordem_tipos), -int(k[1] or 0))):
        rel = "%s/%s-%s.md" % (PASTA_SUBINDICES, tipo, ano)
        md.append("| %s | %s | %d | [%s](%s) |" % (NOME_JULGADO.get(tipo, tipo), ano,
                                                   len(por_tipo_ano[(tipo, ano)]), rel, rel))
    contagem = {}
    for v in itens:
        contagem[v["tipo"]] = contagem.get(v["tipo"], 0) + 1
    md += ["", "Total: %s." % "; ".join("%s, %d" % (NOME_JULGADO.get(t, t), n) for t, n in
                                           sorted(contagem.items(), key=lambda x: ordem_tipos.index(x[0])
                                                  if x[0] in ordem_tipos else 99))]
    if temas:
        md += ["", "## Por tema", "", "| Tema | Julgados | Subíndice |", "|---|---|---|"]
        for tema in sorted(temas):
            md.append("| %s | %d | [%s](%s) |" % (tema, temas[tema][1], temas[tema][0], temas[tema][0]))
    if normas_idx:
        md += ["", "## Por norma citada", "",
               "Dispositivo citado -> julgados (índice reverso). O link para a norma leva ao %s." % NOTA_REDACAO,
               "", "| Norma | Julgados | Subíndice |", "|---|---|---|"]
        for nid in sorted(normas_idx, key=lambda x: (x.startswith("fora:"), x)):
            rel, titulo, n = normas_idx[nid]
            md.append("| %s | %d | [%s](%s) |" % (titulo, n, rel, rel))
    arquivos["indice.md"] = "\n".join(md) + "\n"
    return arquivos, len(itens)


def raizes_de_julgados(repo=REPO):
    return sorted(d for d in glob.glob(os.path.join(repo, "plugins", "julgados-*", "julgados")) if os.path.isdir(d))


def _sobrando(raiz, arquivos, pastas=(PASTA_SUBINDICES,), raiz_md=(),
              recursivas=(PASTA_SUBINDICES + "/" + PASTA_CITACOES,)):
    """Arquivos .md de `pastas` (só o nível), de `recursivas` (com as subpastas) e da raiz
    (`raiz_md`) que não são mais gerados."""
    sobra = [n for n in raiz_md if os.path.exists(os.path.join(raiz, n)) and n not in arquivos]
    for rel in pastas:
        pasta = os.path.join(raiz, *rel.split("/"))
        if os.path.isdir(pasta):
            sobra += ["%s/%s" % (rel, n) for n in os.listdir(pasta)
                      if n.endswith(".md") and "%s/%s" % (rel, n) not in arquivos]
    for rel in recursivas:
        pasta = os.path.join(raiz, *rel.split("/"))
        for dirpath, _dirs, nomes in os.walk(pasta):
            sub = os.path.relpath(dirpath, raiz).replace(os.sep, "/")
            sobra += ["%s/%s" % (sub, n) for n in nomes
                      if n.endswith(".md") and "%s/%s" % (sub, n) not in arquivos]
    return sorted(set(sobra))


def _alvos(args, acervo, perimetro, acervo_bcb):
    """[(raiz, arquivos, sobrando, descrição)] a verificar ou gravar."""
    raiz = args[0] if args else None
    alvos = []
    normas = None
    if raiz is None or os.path.basename(os.path.normpath(os.path.abspath(raiz))) != "julgados":
        rn = raiz or RAIZ_PADRAO
        arquivos, itens = gerar_indice(rn, acervo, perimetro, acervo_bcb)
        alvos.append((rn, arquivos, _sobrando(rn, arquivos), "%d norma(s)" % len(itens)))
        normas = {i["id"]: i for i in itens}
        if raiz is not None:
            return alvos
    if normas is None:
        nj = os.path.join(RAIZ_PADRAO, "normas.json")
        normas = {i["id"]: i for i in (_lista_json(nj) if os.path.exists(nj) else [])}
    for rj in ([raiz] if raiz else raizes_de_julgados()):
        # link relativo dentro do repositório: plugins/julgados-*/julgados/indices -> plugins/normas/normas
        arquivos, n = gerar_indice_julgados(rj, normas)
        alvos.append((rj, arquivos, _sobrando(rj, arquivos, (PASTA_SUBINDICES,), ("indice.md",), ()),
                      "%d julgado(s)" % n))
    return alvos


def main(argv):
    args, acervo, verificar = [], ACERVO_PADRAO, False
    perimetro, acervo_bcb = PERIMETRO_PADRAO, ACERVO_BCB_PADRAO
    resto = list(argv[1:])
    while resto:
        a = resto.pop(0)
        if a == "--verificar":
            verificar = True
        elif a == "--acervo" and resto:
            acervo = resto.pop(0)
        elif a == "--perimetro" and resto:
            perimetro = resto.pop(0)
        elif a == "--acervo-bcb" and resto:
            acervo_bcb = resto.pop(0)
        elif a.startswith("--"):
            print(__doc__)
            return 2
        else:
            args.append(a)
    if len(args) > 1:
        print(__doc__)
        return 2
    if args and not os.path.isdir(args[0]):
        print("indice: %s não existe" % args[0])
        return 2
    alvos = _alvos(args, acervo, perimetro, acervo_bcb)
    if verificar:
        rc = 0
        for raiz, arquivos, sobrando, desc in alvos:
            defasados = []
            for rel, conteudo in sorted(arquivos.items()):
                caminho = os.path.join(raiz, *rel.split("/"))
                atual = None
                if os.path.exists(caminho):
                    with open(caminho, encoding="utf-8") as f:
                        atual = f.read()
                if atual != conteudo:
                    defasados.append(rel)
            defasados += ["%s (sobrou de geração anterior)" % s for s in sobrando]
            if defasados:
                print("indice: %s desatualizado (%s); rode python3 scripts/indice.py" % (raiz, ", ".join(defasados)))
                rc = 1
            else:
                print("indice: em dia (%s, %d arquivo(s))" % (desc, len(arquivos)))
        return rc
    for raiz, arquivos, sobrando, desc in alvos:
        for rel, conteudo in arquivos.items():
            caminho = os.path.join(raiz, *rel.split("/"))
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(conteudo)
        for rel in sobrando:
            os.remove(os.path.join(raiz, *rel.split("/")))
            pasta = os.path.dirname(os.path.join(raiz, *rel.split("/")))
            if os.path.basename(os.path.dirname(pasta)) == PASTA_CITACOES and not os.listdir(pasta):
                os.rmdir(pasta)  # pasta de citações que voltou a ser arquivo único
        print("indice: %s em %d arquivo(s) gravado(s) em %s%s" % (
            desc, len(arquivos), raiz, "; apagado(s): %s" % ", ".join(sobrando) if sobrando else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
