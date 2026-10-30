#!/usr/bin/env python3
"""Índice das normas do acervo (SPEC v0.4.0).

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
  (resolução no Estoque) e `baixado_em` (lei, decreto, LC, CMN, BCB e autorregulação).

Uso: python3 scripts/indice.py [raiz] [--acervo CAMINHO] [--perimetro CAMINHO]
                               [--acervo-bcb CAMINHO]              grava os arquivos
     python3 scripts/indice.py ... --verificar                    saída 1 se defasados
A raiz padrão é plugins/normas/normas; os JSON padrão, os de fontes/. Ao
gravar, apaga de `indices/` o subíndice que não é mais gerado; `--verificar` acusa
esse subíndice. Sem data de geração: a saída só muda quando o acervo muda.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validar import (  # noqa: E402
    TIPOS, TIPOS_AUTORREGULACAO, TIPOS_BCB, arquivos_de_normas, ler_frontmatter,
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


def _md_resumo(contagens):
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
    arquivos["indice.md"] = "\n".join(_md_resumo(contagens)).rstrip("\n") + "\n"
    publicos = [{k: v for k, v in i.items() if not k.startswith("_")} for i in itens]
    arquivos["normas.json"] = json.dumps(publicos, ensure_ascii=False, indent=2) + "\n"
    return arquivos, publicos


def _sobrando(raiz, arquivos):
    pasta = os.path.join(raiz, PASTA_SUBINDICES)
    if not os.path.isdir(pasta):
        return []
    return sorted("%s/%s" % (PASTA_SUBINDICES, n) for n in os.listdir(pasta)
                  if n.endswith(".md") and "%s/%s" % (PASTA_SUBINDICES, n) not in arquivos)


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
    raiz = args[0] if args else RAIZ_PADRAO
    if not os.path.isdir(raiz):
        print("indice: %s não existe" % raiz)
        return 2
    arquivos, itens = gerar_indice(raiz, acervo, perimetro, acervo_bcb)
    sobrando = _sobrando(raiz, arquivos)
    if verificar:
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
            print("indice: desatualizado (%s); rode python3 scripts/indice.py" % ", ".join(defasados))
            return 1
        print("indice: em dia (%d norma(s), %d arquivo(s))" % (len(itens), len(arquivos)))
        return 0
    for rel, conteudo in arquivos.items():
        caminho = os.path.join(raiz, *rel.split("/"))
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
    for rel in sobrando:
        os.remove(os.path.join(raiz, *rel.split("/")))
    print("indice: %d norma(s) em %d arquivo(s) gravado(s) em %s%s" % (
        len(itens), len(arquivos), raiz,
        "; apagado(s): %s" % ", ".join(sobrando) if sobrando else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
