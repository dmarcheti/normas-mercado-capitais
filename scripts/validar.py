#!/usr/bin/env python3
"""Validador do frontmatter das normas (formato em SPEC.md).

- validar_norma(path) -> lista de erros (vazia = ok). Aceita os tipos da SPEC
  (v0.4.0): resolução, instrução e parecer (`NNNN.md`), ofício-circular
  (`<slug>.md`), lei (`lei-NNNNN.md`), decreto (`decreto-NNNNN.md`), lei
  complementar (`lcp-NNN.md`), os atos do CMN e do BCB (`cmn/resolucoes/NNNN.md`,
  `bcb/<pasta do tipo>/NNNN.md`), os documentos de autorregulação
  (`autorregulacao/<anbima|b3>/<slug>.md`) e o `index.md` de norma em partes
  (`NNNN/index.md`, `lei-NNNNN/index.md` etc.).
- partes_da_norma(index_path) -> caminhos das partes, na ordem de `## Partes`.
- texto_da_norma(path) -> texto do arquivo único, ou do `index.md` seguido das
  partes (na ordem), concatenados.

Uso: python3 scripts/validar.py plugins/normas/normas
Valida cada norma em `<orgao>/resolucoes/`, `instrucoes/`, `pareceres-orientacao/`,
`oficios-circulares/<pasta>/`, `leis/`, nas pastas do BCB (`resolucoes-conjuntas/`,
`circulares/`, `cartas-circulares/`, `instrucoes-normativas/`) e em
`autorregulacao/<orgao>/` sob o diretório dado (arquivo único ou o `index.md` da
pasta). Os atos alteradores (`alteradoras/`), os índices (`indice.md`, `indices/`) e
o `autorregulacao/README.md` não seguem este schema.
Julgados (SPEC v0.5.0): `python3 scripts/validar.py plugins/julgados-<plugin>/julgados`
(raiz chamada `julgados`, ou qualquer raiz com `--julgados`). Valida cada `.md` sob a raiz,
fora o `indice.md` e a pasta `indices/`, com validar_julgado(path, ids). Os ids de
`normas_citadas` e `dispositivos_citados` são conferidos contra o `normas.json` do acervo
(`--normas-json CAMINHO`; sem o arquivo, só o formato é conferido).
Saída 0 = ok; 1 = erros; 2 = uso incorreto.
"""
import datetime
import os
import re
import sys

CAMPOS = [
    "id", "orgao", "tipo", "numero", "data", "publicacao_dou", "ementa",
    "situacao", "versao_texto", "vigente_ate_ato", "aguarda_consolidado_oficial",
    "historico_parcial", "fonte_original", "fonte_consolidada", "sha256_fonte",
    "baixado_em", "verificado_em", "incerteza",
]
OPCIONAIS = ["vigencia_inicio", "nivel_verificacao"]  # vêm depois de `incerteza`, nesta ordem
# tipo -> (orgao, prefixo do id, nome do arquivo, pasta sob o órgão). Ofício-circular:
# o nome do arquivo é o slug da página da CVM e o id é `cvm-<slug>` (molde None).
TIPOS = {
    "resolucao": ("cvm", "cvm-res-", "%04d", "resolucoes"),
    "instrucao": ("cvm", "cvm-instr-", "%04d", "instrucoes"),
    "parecer-orientacao": ("cvm", "cvm-po-", "%04d", "pareceres-orientacao"),
    "oficio-circular": ("cvm", "cvm-", None, "oficios-circulares"),
    "lei": ("federal", "lei-", "lei-%05d", "leis"),
    "decreto": ("federal", "decreto-", "decreto-%05d", "leis"),
    "lei-complementar": ("federal", "lcp-", "lcp-%03d", "leis"),
    # v0.4.0, camada 4: CMN e BCB (pasta sob a raiz: `<orgao>/<pasta>`)
    "resolucao-cmn": ("cmn", "cmn-res-", "%04d", "resolucoes"),
    "resolucao-bcb": ("bcb", "bcb-res-", "%04d", "resolucoes"),
    "resolucao-conjunta": ("bcb", "bcb-resc-", "%04d", "resolucoes-conjuntas"),
    "circular": ("bcb", "bcb-circ-", "%04d", "circulares"),
    "carta-circular": ("bcb", "bcb-cc-", "%04d", "cartas-circulares"),
    "instrucao-normativa-bcb": ("bcb", "bcb-in-", "%04d", "instrucoes-normativas"),
}
# v0.4.0, camada 5: autorregulação. Arquivo `autorregulacao/<orgao>/<slug>.md`; o id é
# `<orgao>-<slug>` (molde None); `numero` e `publicacao_dou` ficam vazios.
ORGAOS_AUTORREGULACAO = ("anbima", "b3")
PASTA_AUTORREGULACAO = "autorregulacao"
TIPOS_AUTORREGULACAO = ("codigo-autorregulacao", "regras-procedimentos", "regulamento",
                        "manual", "glossario", "orientacao-autorregulacao")
for _t in TIPOS_AUTORREGULACAO:
    TIPOS[_t] = (ORGAOS_AUTORREGULACAO, None, None, PASTA_AUTORREGULACAO)
TIPOS_FEDERAIS = tuple(t for t, (orgao, *_r) in TIPOS.items() if orgao == "federal")
TIPOS_BCB = tuple(t for t, (orgao, *_r) in TIPOS.items() if orgao in ("cmn", "bcb"))
# Tipos sem atos aplicados em sequência: `vigente_ate_ato` vazio, `historico_parcial: true`,
# `aguarda_consolidado_oficial: false` (a data-base é `baixado_em`).
TIPOS_SEM_SEQUENCIA = TIPOS_FEDERAIS + TIPOS_BCB + TIPOS_AUTORREGULACAO
SLUG_MAX = 80  # caracteres do slug da autorregulação
SITUACOES = ("vigente", "revogada", "parcialmente-revogada", "nao-informada")
# A CVM não publica a vigência de pareceres e ofícios: só neles cabe `nao-informada`.
TIPOS_SEM_VIGENCIA = ("parecer-orientacao", "oficio-circular")
NIVEIS_VERIFICACAO = ("historico-conferido", "consolidado-convertido", "ato-convertido",
                      "pdf-extraido", "ocr", "compilado-planalto")  # `ocr`: v0.3.1
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
VERSOES = ("consolidado", "original")
DATAS = ("data", "publicacao_dou", "baixado_em", "verificado_em")
BOOLEANOS = ("aguarda_consolidado_oficial", "historico_parcial")
# Linha que abre a redação futura de um dispositivo (vigência diferida).
MARCA_VIGENCIA = re.compile(r"^[\s>*_#-]*vigente a partir de\b", re.I | re.M)


def ler_frontmatter(texto):
    """Devolve (pares, corpo, erro). `pares` = lista [(chave, valor)] na ordem."""
    linhas = texto.split("\n")
    if not linhas or linhas[0].strip() != "---":
        return None, texto, "frontmatter ausente (o arquivo deve começar com ---)"
    for i in range(1, len(linhas)):
        if linhas[i].strip() == "---":
            fim = i
            break
    else:
        return None, texto, "frontmatter não fechado (falta o --- final)"
    pares = []
    for n, linha in enumerate(linhas[1:fim], start=2):
        if not linha.strip():
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):(?: (.*))?$", linha.rstrip())
        if not m:
            pares.append((None, "linha %d inválida no frontmatter: %r" % (n, linha)))
            continue
        valor = (m.group(2) or "").strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        pares.append((m.group(1), valor))
    return pares, "\n".join(linhas[fim + 1:]), None


def _data_valida(valor):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
        return False
    try:
        datetime.date.fromisoformat(valor)
    except ValueError:
        return False
    return True


def partes_da_norma(index_path):
    """Caminhos das partes, na ordem da seção `## Partes` do index.md (itens `- arquivo.md`)."""
    with open(index_path, encoding="utf-8") as f:
        linhas = f.read().split("\n")
    pasta = os.path.dirname(index_path)
    partes, dentro = [], False
    for linha in linhas:
        if re.match(r"^#{1,2}\s", linha):
            dentro = linha.strip() == "## Partes"
        elif dentro:
            m = re.match(r"^\s*[-*]\s+(.+?)\s*$", linha)
            if m:
                partes.append(os.path.join(pasta, m.group(1).strip("`")))
    return partes


def texto_da_norma(path):
    """Texto da norma: o arquivo, ou o index.md mais as partes (as que existem), em ordem."""
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    if os.path.basename(path) != "index.md":
        return texto
    for parte in partes_da_norma(path):
        if os.path.exists(parte):
            with open(parte, encoding="utf-8") as f:
                texto += "\n\n" + f.read()
    return texto


def _erros_partes(index_path):
    erros = []
    partes = partes_da_norma(index_path)
    nomes = [os.path.basename(p) for p in partes]
    if not partes:
        return ["seção '## Partes' ausente ou vazia no index.md"]
    for n in sorted({n for n in nomes if nomes.count(n) > 1}):
        erros.append("parte duplicada em '## Partes': %s" % n)
    for caminho, nome in zip(partes, nomes):
        if not os.path.isfile(caminho):
            erros.append("parte listada não existe: %s" % nome)
            continue
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()
        primeira = next((l for l in texto.split("\n") if l.strip()), "")
        if primeira.strip() == "---":
            erros.append("parte %s não pode ter frontmatter" % nome)
        elif not primeira.startswith("# "):
            erros.append("parte %s deve abrir com o título '# <título da parte>'" % nome)
    for nome in sorted(os.listdir(os.path.dirname(index_path))):
        if nome.endswith(".md") and nome != "index.md" and nome not in nomes:
            erros.append("arquivo fora da lista '## Partes': %s" % nome)
    return erros


def _erros_pasta(path, em_partes, v):
    """CMN, BCB e autorregulação: o arquivo fica em `<orgao>/<pasta do tipo>/` (CMN e BCB)
    ou em `autorregulacao/<orgao>/`; a pasta `resolucoes/` é dividida com a CVM."""
    orgao, _prefixo, _molde, pasta = TIPOS[v["tipo"]]
    esperado = [PASTA_AUTORREGULACAO, v["orgao"]] if isinstance(orgao, tuple) else [orgao, pasta]
    alvo = os.path.dirname(os.path.abspath(path))
    if em_partes:
        alvo = os.path.dirname(alvo)
    atual = [os.path.basename(os.path.dirname(alvo)), os.path.basename(alvo)]
    if atual != esperado:
        return ["arquivo deve ficar em %s/ para tipo %s, está em %s/" % ("/".join(esperado), v["tipo"], "/".join(atual))]
    return []


def validar_norma(path):
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    em_partes = os.path.basename(path) == "index.md"
    pares, corpo, erro = ler_frontmatter(texto)
    if erro:
        return [erro]
    erros = [valor for chave, valor in pares if chave is None]
    pares = [(c, v) for c, v in pares if c is not None]
    chaves = [c for c, _ in pares]
    valores = dict(pares)

    for c in sorted({c for c in chaves if chaves.count(c) > 1}):
        erros.append("campo repetido: %s" % c)
    for c in CAMPOS:
        if c not in valores:
            erros.append("campo obrigatório ausente: %s" % c)
    for c in chaves:
        if c not in CAMPOS and c not in OPCIONAIS:
            erros.append("campo desconhecido: %s" % c)
    esperado = [c for c in CAMPOS + OPCIONAIS if c in valores]
    if not erros and chaves != esperado:
        erros.append("ordem dos campos incorreta (esperado: %s)" % ", ".join(esperado))
    if erros:
        return erros

    v = valores
    if v["tipo"] not in TIPOS:
        erros.append("tipo fora da lista %s: %r" % (", ".join(TIPOS), v["tipo"]))
        orgao, prefixo, molde, _pasta = TIPOS["resolucao"]
    else:
        orgao, prefixo, molde, _pasta = TIPOS[v["tipo"]]
        if isinstance(orgao, tuple):
            if v["orgao"] not in orgao:
                erros.append("orgao deve ser %s para tipo %s, veio %r" % (" ou ".join(orgao), v["tipo"], v["orgao"]))
        elif v["orgao"] != orgao:
            erros.append("orgao deve ser %s para tipo %s, veio %r" % (orgao, v["tipo"], v["orgao"]))
    autorregulacao = v["tipo"] in TIPOS_AUTORREGULACAO
    if autorregulacao:
        numero_ok = False
        if v["numero"] != "":
            erros.append("numero deve ficar vazio em %s (autorregulação), veio %r" % (v["tipo"], v["numero"]))
    else:
        numero_ok = bool(re.fullmatch(r"[1-9]\d*", v["numero"]))
        if not numero_ok:
            erros.append("numero deve ser inteiro, veio %r" % v["numero"])
    if em_partes:
        nome_atual = os.path.basename(os.path.dirname(os.path.abspath(path)))
    else:
        nome_atual = os.path.basename(path)[:-3] if path.endswith(".md") else os.path.basename(path)
    if autorregulacao:
        # o id é `<orgao>-` + slug (nome do arquivo); sem número
        if not SLUG.fullmatch(nome_atual) or len(nome_atual) > SLUG_MAX:
            erros.append("nome do arquivo do documento de autorregulação deve ser um slug "
                         "(minúsculas, dígitos e hífen, até %d caracteres), veio %r" % (SLUG_MAX, nome_atual))
        elif v["id"] != "%s-%s" % (v["orgao"], nome_atual):
            erros.append("id %r incoerente com o nome do arquivo (esperado %s-%s)" % (v["id"], v["orgao"], nome_atual))
    elif v["tipo"] == "oficio-circular":
        # sem regra entre numero e id: o id vem do slug da página da CVM (nome do arquivo)
        if not SLUG.fullmatch(nome_atual):
            erros.append("nome do arquivo do ofício deve ser o slug da página da CVM "
                         "(minúsculas, dígitos e hífen), veio %r" % nome_atual)
        elif v["id"] != prefixo + nome_atual:
            erros.append("id %r incoerente com o nome do arquivo (esperado %s%s)" % (v["id"], prefixo, nome_atual))
    elif numero_ok:
        if v["id"] != "%s%s" % (prefixo, v["numero"]):
            erros.append("id %r incoerente com numero %s (esperado %s%s)" % (v["id"], v["numero"], prefixo, v["numero"]))
        nome = molde % int(v["numero"])
        if em_partes:
            if nome_atual != nome:
                erros.append("o index.md deve ficar na pasta %s/" % nome)
        elif nome_atual != nome:
            erros.append("nome do arquivo deve ser %s.md" % nome)
    if v["tipo"] in TIPOS_BCB or autorregulacao:
        erros += _erros_pasta(path, em_partes, v)
    for c in DATAS:
        if autorregulacao and c == "publicacao_dou":
            if v[c] != "":
                erros.append("publicacao_dou deve ficar vazio em %s (autorregulação), veio %r" % (v["tipo"], v[c]))
        elif not _data_valida(v[c]):
            erros.append("%s deve ser AAAA-MM-DD válida, veio %r" % (c, v[c]))
    if v["situacao"] not in SITUACOES:
        erros.append("situacao fora da lista %s: %r" % (", ".join(SITUACOES), v["situacao"]))
    elif v["situacao"] == "nao-informada" and v["tipo"] not in TIPOS_SEM_VIGENCIA:
        erros.append("situacao nao-informada só cabe em %s, não em %s" % (" e ".join(TIPOS_SEM_VIGENCIA), v["tipo"]))
    elif v["situacao"] != "vigente" and (v["tipo"] in TIPOS_BCB or autorregulacao):
        erros.append("situacao deve ser vigente em %s (o perímetro é só o vigente), veio %r" % (v["tipo"], v["situacao"]))
    if v["versao_texto"] not in VERSOES:
        erros.append("versao_texto fora da lista %s: %r" % (", ".join(VERSOES), v["versao_texto"]))
    elif autorregulacao and v["versao_texto"] != "original":
        erros.append("versao_texto deve ser original em %s (autorregulação), veio %r" % (v["tipo"], v["versao_texto"]))
    if v["tipo"] in TIPOS_SEM_SEQUENCIA:
        if v["vigente_ate_ato"] != "":
            erros.append("vigente_ate_ato deve ficar vazio em %s (a data-base é baixado_em), veio %r" % (v["tipo"], v["vigente_ate_ato"]))
        if v["historico_parcial"] != "true":
            erros.append("historico_parcial deve ser true em %s, veio %r" % (v["tipo"], v["historico_parcial"]))
        if v["aguarda_consolidado_oficial"] != "false":
            erros.append("aguarda_consolidado_oficial deve ser false em %s, veio %r" % (v["tipo"], v["aguarda_consolidado_oficial"]))
    elif v["vigente_ate_ato"] != "" and not re.fullmatch(r"[1-9]\d*", v["vigente_ate_ato"]):
        erros.append("vigente_ate_ato deve ser o número do ato (inteiro) ou vazio, veio %r" % v["vigente_ate_ato"])
    for c in BOOLEANOS:
        if v[c] not in ("true", "false"):
            erros.append("%s deve ser true ou false, veio %r" % (c, v[c]))
    for c in ("ementa", "fonte_original", "fonte_consolidada"):
        if not v[c]:
            erros.append("%s não pode ficar vazio" % c)
    if not re.fullmatch(r"[0-9a-f]{64}", v["sha256_fonte"]):
        erros.append("sha256_fonte deve ter 64 caracteres hexadecimais")

    if "nivel_verificacao" in v and v["nivel_verificacao"] not in NIVEIS_VERIFICACAO:
        erros.append("nivel_verificacao fora da lista %s: %r" % (", ".join(NIVEIS_VERIFICACAO), v["nivel_verificacao"]))
    elif autorregulacao and v.get("nivel_verificacao") != "pdf-extraido":
        erros.append("nivel_verificacao deve ser pdf-extraido em %s (autorregulação), veio %r" % (
            v["tipo"], v.get("nivel_verificacao", "(ausente)")))

    if em_partes:
        erros += _erros_partes(path)
        corpo = texto_da_norma(path)
    tem_marca = bool(MARCA_VIGENCIA.search(corpo))
    if "vigencia_inicio" in v:
        if not _data_valida(v["vigencia_inicio"]):
            erros.append("vigencia_inicio deve ser AAAA-MM-DD válida, veio %r" % v["vigencia_inicio"])
    elif tem_marca:
        erros.append('o texto tem bloco "vigente a partir de" mas falta vigencia_inicio no frontmatter')
    return erros


def _normas_em(dirpath, nomes, dirs):
    return ([os.path.join(dirpath, n) for n in nomes if n.endswith(".md")] +
            [os.path.join(dirpath, d, "index.md") for d in dirs
             if os.path.isfile(os.path.join(dirpath, d, "index.md"))])


def arquivos_da_pasta(raiz, pasta):
    """Normas das pastas chamadas `pasta` sob `raiz`: cada `.md` solto, e o `index.md`
    de cada subpasta (norma em partes; as partes não são normas por si)."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(dirpath) == pasta:
            achados += _normas_em(dirpath, nomes, dirs)
    return sorted(achados)


def arquivos_de_oficios(raiz):
    """Ofícios-circulares: normas de cada subpasta (superintendência) de `oficios-circulares/`."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(os.path.dirname(dirpath)) == "oficios-circulares":
            achados += _normas_em(dirpath, nomes, dirs)
    return sorted(achados)


def arquivos_de_autorregulacao(raiz):
    """Documentos de autorregulação: normas de cada subpasta (entidade) de `autorregulacao/`.
    O `autorregulacao/README.md` fica fora (não é norma)."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if os.path.basename(os.path.dirname(dirpath)) == PASTA_AUTORREGULACAO:
            achados += _normas_em(dirpath, nomes, dirs)
    return sorted(achados)


PASTAS_DE_NORMAS = ("resolucoes", "instrucoes", "pareceres-orientacao", "leis",
                    # v0.4.0: pastas do BCB (as resoluções do CMN e do BCB ficam em `resolucoes/`)
                    "resolucoes-conjuntas", "circulares", "cartas-circulares", "instrucoes-normativas")


def arquivos_de_normas(raiz):
    achados = arquivos_de_oficios(raiz) + arquivos_de_autorregulacao(raiz)
    for pasta in PASTAS_DE_NORMAS:
        achados += arquivos_da_pasta(raiz, pasta)
    return sorted(achados)


# ---------------------------------------------------------------- julgados (v0.5.0)

AQUI = os.path.dirname(os.path.abspath(__file__))
NORMAS_JSON = os.path.join(AQUI, "..", "plugins", "normas", "normas", "normas.json")
# id e arquivo por tipo: (órgão, regex do id, pasta sob julgados/ com {ano}, prefixo tirado do id)
_PROC = r"[a-z0-9]+(?:-[a-z0-9]+)*"
JULGADO_TIPOS = {
    "pas": ("cvm", r"cvm-pas-" + _PROC, "cvm/pas/{ano}", "cvm-pas-"),
    "termo-compromisso": ("cvm", r"cvm-(?:col-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*|tc-" + _PROC + r"-\d{8})",
                          "cvm/colegiado/{ano}", "cvm-"),
    "decisao-colegiado": ("cvm", r"cvm-col-\d{8}-[a-z0-9]+(?:-[a-z0-9]+)*", "cvm/colegiado/{ano}", "cvm-"),
    "decisao-antiga": ("cvm", r"cvm-dec-(?P<ano>\d{4})(?:-\d{3})?", "cvm/decisoes-antigas", "cvm-dec-"),
    "acordao-crsfn": ("crsfn", r"crsfn-" + _PROC, "crsfn/{ano}", "crsfn-"),
}
JULGADO_VAZIOS = ("classe", "nup", "rito", "relator", "resultado", "tema", "tema_fonte",
                  "normas_citadas", "dispositivos_citados", "incerteza")
RITOS = ("ordinario", "simplificado")
TEMA_FONTES = ("script", "extracao")
NUP_RE = re.compile(r"\d{5}-\d{6}-\d{4}-\d{2}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _contrato_julgados():
    """Listas fechadas do contrato, de `julgados_comum` (fonte única)."""
    import julgados_comum as jc
    return jc


def raiz_dos_julgados(path):
    """Ancestral mais próximo chamado `julgados` (ou None)."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if os.path.basename(d) == "julgados":
            return d
        pai = os.path.dirname(d)
        if pai == d:
            return None
        d = pai


def _erros_citacoes(v, ids):
    import citacoes
    erros = []

    def conferir_norma(norma, campo):
        if norma.startswith("fora:"):
            rotulo = norma[5:]
            id_ = citacoes.id_do_rotulo(rotulo)
            if ids and id_ in ids:
                erros.append("%s: %r está no acervo, use o id %s" % (campo, norma, id_))
        elif ids and norma not in ids:
            erros.append("%s: %r não está no normas.json (use fora:<rotulo>)" % (campo, norma))

    for campo, ler in (("normas_citadas", lambda x: x if citacoes.NORMA_RE.fullmatch(x) else None),
                       ("dispositivos_citados", lambda x: (citacoes.ler_dispositivo(x) or {}).get("norma"))):
        if not v.get(campo):
            continue
        itens = v[campo].split("; ")
        for c in sorted({x for x in itens if itens.count(x) > 1}):
            erros.append("%s: item repetido %r" % (campo, c))
        for item in itens:
            norma = ler(item)
            if not norma:
                erros.append("%s: item fora do formato: %r" % (campo, item))
            else:
                conferir_norma(norma, campo)
    return erros


def validar_julgado(path, ids=None):
    """Erros do julgado em `path` (contrato da SPEC v0.5.0). `ids`: ids do acervo de normas
    (None ou vazio = só o formato das citações é conferido)."""
    jc = _contrato_julgados()
    with open(path, encoding="utf-8") as f:
        texto = f.read()
    pares, corpo, erro = ler_frontmatter(texto)
    if erro:
        return [erro]
    erros = [valor for chave, valor in pares if chave is None]
    pares = [(c, x) for c, x in pares if c is not None]
    chaves = [c for c, _ in pares]
    v = dict(pares)
    campos = list(jc.CAMPOS)
    for c in sorted({c for c in chaves if chaves.count(c) > 1}):
        erros.append("campo repetido: %s" % c)
    for c in campos:
        if c not in v:
            erros.append("campo obrigatório ausente: %s" % c)
    for c in chaves:
        if c not in campos:
            erros.append("campo desconhecido: %s" % c)
    presentes = [c for c in dict.fromkeys(chaves) if c in campos]
    if presentes != [c for c in campos if c in presentes]:
        erros.append("campos fora da ordem da SPEC: %s" % ", ".join(presentes))
    for c in campos:
        if c in v and not v[c] and c not in JULGADO_VAZIOS:
            if not (c == "processo" and v.get("tipo") == "decisao-antiga"):
                erros.append("%s vazio" % c)

    tipo = v.get("tipo", "")
    if tipo not in JULGADO_TIPOS:
        erros.append("tipo %r desconhecido; aceitos: %s" % (tipo, ", ".join(JULGADO_TIPOS)))
    else:
        orgao, id_re, pasta, prefixo = JULGADO_TIPOS[tipo]
        if v.get("orgao") != orgao:
            erros.append("orgao deve ser %r no tipo %s, veio %r" % (orgao, tipo, v.get("orgao")))
        id_ = v.get("id", "")
        m = re.fullmatch(id_re, id_)
        if not m:
            erros.append("id %r fora do padrão do tipo %s" % (id_, tipo))
        ano = v.get("data", "")[:4]
        if m and m.groupdict().get("ano") and m.group("ano") != ano:
            erros.append("ano do id (%s) difere do ano de data (%s)" % (m.group("ano"), ano))
        raiz = raiz_dos_julgados(path)
        if raiz is None:
            erros.append("arquivo fora de uma pasta julgados/")
        elif m:
            esperado = os.path.join(pasta.format(ano=ano), id_[len(prefixo):] + ".md")
            rel = os.path.relpath(os.path.abspath(path), raiz)
            if rel.replace(os.sep, "/") != esperado:
                erros.append("caminho %s não combina com tipo, id e data (esperado %s)" % (rel, esperado))
        resultados = jc.RESULTADOS.get(tipo, ())
        if v.get("resultado") and v["resultado"] not in resultados:
            erros.append("resultado %r fora da lista do tipo %s: %s" % (v["resultado"], tipo, ", ".join(resultados)))
        if tipo == "decisao-colegiado" and "classe" in v and not v["classe"]:
            erros.append("classe vazia (obrigatória no item do Colegiado)")

    if v.get("classe") and v["classe"] not in jc.CLASSES:
        erros.append("classe %r fora da lista: %s" % (v["classe"], ", ".join(jc.CLASSES)))
    if v.get("rito") and v["rito"] not in RITOS:
        erros.append("rito %r fora da lista: %s" % (v["rito"], ", ".join(RITOS)))
    if v.get("nup") and not NUP_RE.fullmatch(v["nup"]):
        erros.append("nup %r fora do formato normalizado 00000-000000-0000-00" % v["nup"])
    for c in ("data", "baixado_em"):
        if v.get(c) and not _data_valida(v[c]):
            erros.append("%s deve ser AAAA-MM-DD válida, veio %r" % (c, v[c]))
    if v.get("ementa_fonte") and v["ementa_fonte"] not in jc.EMENTA_FONTES:
        erros.append("ementa_fonte %r fora da lista: %s" % (v["ementa_fonte"], ", ".join(jc.EMENTA_FONTES)))
    if v.get("tema_fonte") and v["tema_fonte"] not in TEMA_FONTES:
        erros.append("tema_fonte %r fora da lista: %s" % (v["tema_fonte"], ", ".join(TEMA_FONTES)))
    if v.get("tema") and not v.get("tema_fonte"):
        erros.append("tema preenchido sem tema_fonte")
    if v.get("tema_fonte") and not v.get("tema"):
        erros.append("tema_fonte preenchido com tema vazio")
    if v.get("nivel_verificacao") and v["nivel_verificacao"] not in jc.NIVEIS:
        erros.append("nivel_verificacao %r fora da lista: %s" % (v["nivel_verificacao"], ", ".join(jc.NIVEIS)))
    if v.get("sha256_fonte") and not SHA256_RE.fullmatch(v["sha256_fonte"]):
        erros.append("sha256_fonte deve ter 64 caracteres hexadecimais")
    erros += _erros_citacoes(v, ids)

    linhas = [x for x in corpo.split("\n") if x.strip()]
    if not linhas or not linhas[0].startswith("# "):
        erros.append("o corpo deve começar com '# <título>'")
    if not any(x.startswith("## ") for x in linhas):
        erros.append("o corpo não tem seção '## '")
    return erros


def arquivos_de_julgados(raiz):
    """Julgados sob `raiz`: todo `.md`, fora o `indice.md` da raiz e a pasta `indices/`."""
    achados = []
    for dirpath, dirs, nomes in os.walk(raiz):
        if dirpath == raiz:
            dirs[:] = [d for d in dirs if d != "indices"]
        achados += [os.path.join(dirpath, n) for n in nomes
                    if n.endswith(".md") and not (dirpath == raiz and n == "indice.md")]
    return sorted(achados)


def _main_julgados(raiz, normas_json):
    import citacoes
    ids = citacoes.carregar_ids(normas_json)
    if not ids:
        print("validar: %s ausente; citações conferidas só no formato" % normas_json)
    arquivos = arquivos_de_julgados(raiz)
    if not arquivos:
        print("validar: nenhum julgado em %s; nada a validar" % raiz)
        return 0
    total = 0
    for caminho in arquivos:
        for e in validar_julgado(caminho, ids):
            total += 1
            print("%s: %s" % (caminho, e))
    print("validar: %d julgado(s), %d erro(s)" % (len(arquivos), total))
    return 1 if total else 0


def main(argv):
    args = list(argv[1:])
    julgados = "--julgados" in args
    if julgados:
        args.remove("--julgados")
    normas_json = NORMAS_JSON
    if "--normas-json" in args:
        i = args.index("--normas-json")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        normas_json = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    raiz = args[0]
    if not os.path.isdir(raiz):
        print("validar: %s não existe ainda; nada a validar" % raiz)
        return 0
    if julgados or os.path.basename(os.path.normpath(os.path.abspath(raiz))) == "julgados":
        return _main_julgados(raiz, normas_json)
    arquivos = arquivos_de_normas(raiz)
    if not arquivos:
        print("validar: nenhuma norma em %s; nada a validar" % raiz)
        return 0
    total = 0
    for caminho in arquivos:
        for e in validar_norma(caminho):
            total += 1
            print("%s: %s" % (caminho, e))
    print("validar: %d arquivo(s), %d erro(s)" % (len(arquivos), total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
