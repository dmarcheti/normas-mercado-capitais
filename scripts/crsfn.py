"""CRSFN: classifica os itens do inventário pelo órgão de origem e converte os da CVM.

Subcomandos:
  classificar  baixa a fonte de cada item (PDF do Plone até 2016; extrato do SEI depois) para
               dados/fase-2d/cache/crsfn/ e decide o órgão pelos sinais do preâmbulo (texto antes
               da EMENTA do primeiro documento). Item com prefixo de NUP de outro órgão no título
               não é baixado. Grava dados/fase-2d/crsfn-classificacao.json a cada 10 itens e no
               fim; itens já classificados são pulados (retomável).
  converter    converte os itens classificados como CVM em
               julgados/crsfn/AAAA/<id sem crsfn->.md (SPEC v0.5.0), com a
               cobertura conferida por extrator independente em dados/fase-2d/relatorios/.
Os dois regravam dados/fase-2d/crsfn-ligacoes.json (processo CVM normalizado -> ids).

Ids: crsfn-<recurso>; sem número de recurso, o NUP do título; embargos, revisão, acórdão
avulso e decisão monocrática levam prefixo (crsfn-edcl-, crsfn-revisao-, crsfn-acordao-,
crsfn-monocratica-). Colisão ganha -2, -3 na ordem (ano, item_url) do inventário inteiro.

Uso:
  python3 scripts/crsfn.py classificar [--ano 2005] [--limite 50] [--ids crsfn-5279,...]
  python3 scripts/crsfn.py converter   [--ano 2005] [--limite 50] [--ids crsfn-5279,...]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import julgados_comum as jc  # noqa: E402
import julgados_converter as jconv  # noqa: E402
import julgados_extracao as je  # noqa: E402
import pdf_macos  # noqa: E402
import pii  # noqa: E402

TIPO = "acordao-crsfn"
INTERVALO = 0.7
SALVAR_A_CADA = 10
MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
         "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}


def caminhos(raiz=jc.RAIZ):
    d = os.path.join(raiz, "dados", "fase-2d")
    return {"inventario": os.path.join(d, "inventario", "crsfn", "inventario.json"),
            "cache": os.path.join(d, "cache", "crsfn"),
            "classificacao": os.path.join(d, "crsfn-classificacao.json"),
            "ligacoes": os.path.join(d, "crsfn-ligacoes.json"),
            "relatorios": os.path.join(d, "relatorios")}


def _gravar_json(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    tmp = caminho + ".parcial"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=False)
    os.replace(tmp, caminho)


def _ler_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _agora():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------- ids

_NUM_TITULO = re.compile(
    r"\b(?:Recursos?|Revis[ãa]o|EDCL|Embargos(?:\s+de\s+Declara[çc][ãa]o)?|Ac[óo]rd[ãa]o|"
    r"Decis[ãa]o\s+Monocr[áa]tica)\s+(?:n[º°o.]*\s*)?(\d{1,2}\.\d{3}|\d{3,6})(?![\d./])", re.I)


def _sem_acento(txt):
    return "".join(c for c in unicodedata.normalize("NFD", txt) if unicodedata.category(c) != "Mn")


def _slug(txt):
    return re.sub(r"[^a-z0-9]+", "-", _sem_acento(txt).lower()).strip("-")


def id_base(item):
    """Id do item sem o sufixo de colisão."""
    titulo = item.get("titulo") or ""
    tipo = item.get("tipo") or ""
    if tipo == "embargos":
        pref = "edcl-"
    elif tipo == "revisao":
        pref = "revisao-"
    elif re.match(r"\s*Decis[ãa]o\s+Monocr", titulo, re.I):
        pref = "monocratica-"
    elif re.match(r"\s*Ac[óo]rd[ãa]o\b", titulo, re.I):
        pref = "acordao-"
    else:
        pref = ""
    if isinstance(item.get("recurso"), int):
        base = str(item["recurso"])
    else:
        m = _NUM_TITULO.search(titulo)
        base = (m.group(1).replace(".", "") if m else
                jc.nup(titulo) or jc.normalizar_processo(titulo) or _slug(titulo) or "sem-titulo")
    return "crsfn-" + pref + base


def atribuir_ids(itens):
    """[(id, item)] na ordem (ano, item_url); colisão ganha -2, -3..."""
    usados, saida = set(), []
    for it in sorted(itens, key=lambda x: (int(x.get("ano") or 0), x.get("item_url") or "")):
        base = cand = id_base(it)
        n = 1
        while cand in usados:
            n += 1
            cand = "%s-%d" % (base, n)
        usados.add(cand)
        saida.append((cand, it))
    return saida


def selecionar(pares, ids=None, ano=None, limite=None):
    sel = [(i, it) for i, it in pares
           if (not ids or i in ids) and (ano is None or int(it.get("ano") or 0) == ano)]
    return sel[:limite] if limite else sel


# ---------------------------------------------------------------- download

_SEI_HTML = re.compile(r"documento_conferir|controlador_externo|Conselho de recursos do Sistema", re.I)
_LINK_DOC = re.compile(r"href=\"([^\"]+?(?:@@download/file[^\"]*|controlador_externo\.php\?[^\"]+))\"",
                       re.I)


def _url_abs(base, href):
    import urllib.parse
    from html import unescape
    return urllib.parse.urljoin(base, unescape(href))


def baixar(item, id_, cliente, cache):
    """Fonte do item no cache: (caminho, meta). Já baixado: sem requisição."""
    meta_p = os.path.join(cache, id_ + ".json")
    if os.path.exists(meta_p):
        meta = _ler_json(meta_p, {})
        cam = os.path.join(cache, meta.get("arquivo", ""))
        if meta.get("arquivo") and os.path.exists(cam):
            return cam, dict(meta, requisicoes_agora=0)
    url = item["item_url"]
    fila = [url.rstrip("/") + "/@@download/file", url] if int(item.get("ano") or 0) <= 2016 else [url]
    n0, falhas, achado, seguidos = cliente.n, [], None, 0
    while fila and achado is None:
        u = fila.pop(0)
        try:
            dados, cab, final = cliente.get(u)
        except Exception as e:  # noqa: BLE001 — próxima URL; sem nenhuma, erro do item
            falhas.append("%s: %s" % (u, type(e).__name__))
            continue
        if dados.lstrip()[:5] == b"%PDF-":
            achado = (dados, cab, final, u, "pdf")
            break
        html = jc.decodificar(dados, cab)
        if "sei" in (final or "").lower() and _SEI_HTML.search(html) or \
                re.search(r"Conselho de recursos do Sistema financeiro", html, re.I) and \
                re.search(r"documento_conferir", html):
            achado = (dados, cab, final, u, "html")
            break
        m = _LINK_DOC.search(html)
        if m and seguidos < 2:
            seguidos += 1
            fila.insert(0, _url_abs(final or u, m.group(1)))
        else:
            falhas.append("%s: página sem documento" % u)
    if achado is None:
        raise RuntimeError("; ".join(falhas) or "sem fonte")
    dados, cab, final, u, ext = achado
    os.makedirs(cache, exist_ok=True)
    nome = "%s.%s" % (id_, ext)
    cam = os.path.join(cache, nome)
    with open(cam + ".parcial", "wb") as f:
        f.write(dados)
    os.replace(cam + ".parcial", cam)
    meta = {"arquivo": nome, "url": u, "url_final": final,
            "content_type": cab.get("content-type", ""),
            "content_disposition": cab.get("content-disposition", ""),
            "sha256": hashlib.sha256(dados).hexdigest(), "tamanho": len(dados),
            "baixado_em": jc.hoje_sp(), "requisicoes": cliente.n - n0}
    _gravar_json(meta_p, meta)
    return cam, dict(meta, requisicoes_agora=cliente.n - n0)


# ---------------------------------------------------------------- texto da fonte

def _pypdf_inicio(caminho, n=2):
    try:
        import logging
        import pypdf
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(caminho).pages[:n])
    except Exception:  # noqa: BLE001 — sem pypdf ou PDF ilegível: cai para texto_pdf
        return ""


def ler_fonte(caminho, pm=pdf_macos, so_inicio=False):
    """{texto, nivel, motor, avisos, retirado}. HTML do SEI vira Markdown; PDF pelo PDFKit
    (pypdf fora do macOS), sem as linhas repetidas. `so_inicio`: 2 primeiras páginas."""
    if caminho.endswith(".html"):
        with open(caminho, "rb") as f:
            md = jconv.sei_para_md(jc.decodificar(f.read()))
        return {"texto": md, "nivel": "html-convertido", "motor": "sei_para_md", "avisos": [],
                "retirado": []}
    if so_inicio:
        t = jc.normalizar_pdf(_pypdf_inicio(caminho))
        if len(t.strip()) >= 50:
            return {"texto": t, "nivel": "pdf-extraido", "motor": "pypdf", "avisos": [],
                    "retirado": []}
    paginas, nivel, motor, avisos, _ = jconv.texto_pdf(caminho, pm)
    if so_inicio:
        return {"texto": "\n".join(paginas[:2]), "nivel": nivel, "motor": motor,
                "avisos": avisos, "retirado": []}
    retirado = []
    texto, _ = jconv.tirar_repetidas(paginas, retirado=retirado)
    return {"texto": texto, "nivel": nivel, "motor": motor, "avisos": avisos,
            "retirado": retirado}


def plana(linha):
    return re.sub(r"\s+", " ", (linha or "").replace("*", "")).strip()


_EMENTA = re.compile(r"^EMENTA\s*:", re.I)


def preambulo(texto):
    """Texto antes da primeira EMENTA (sem ela, os primeiros 1.500 caracteres)."""
    linhas = texto.splitlines()
    for i, x in enumerate(linhas):
        if _EMENTA.match(plana(x)):
            return "\n".join(linhas[:i])
    return texto[:1500]


# ---------------------------------------------------------------- classificação

SINAIS = (
    ("CVM", (("Comissão de Valores Mobiliários", r"COMISS[ÃA]O\s+DE\s+VALORES\s+MOBILI[ÁA]RIOS"),
             ("sigla CVM", r"\bCVM\b"),
             ("NUP 19957", r"\b19957\.?\d{6}"),
             ("processo RJ/SP", r"\b(?:RJ|SP)\s*-?\s*\d{4}\s*[/-]\s*\d+"))),
    ("BCB", (("Banco Central", r"BANCO\s+CENTRAL"), ("sigla BCB/BACEN", r"\b(?:BCB|BACEN)\b"),
             ("NUP 18600", r"\b18600\.?\d{6}"))),
    ("COAF", (("COAF", r"\bCOAF\b|CONSELHO\s+DE\s+CONTROLE\s+DE\s+ATIVIDADES\s+FINANCEIRAS"),
              ("NUP 11893", r"\b11893\.?\d{6}"))),
    ("SUSEP", (("SUSEP", r"\bSUSEP\b|SUPERINTEND[ÊE]NCIA\s+DE\s+SEGUROS\s+PRIVADOS"),
               ("NUP 15414", r"\b15414\.?\d{6}"))),
    ("OUTRO", (("NUP 08224", r"\b08224\.?\d{6}"),
               ("Receita Federal", r"RECEITA\s+FEDERAL"))),
)


# "Processo origem CVM 95/1449", "Processo CVM RJ2001/6094", "Processo na primeira instância CVM
# 08/2009": o processo de primeira instância é da CVM, e isso decide sobre o "RECORRIDO: BANCO
# CENTRAL" que o modelo dos acórdãos antigos trazia em recursos da CVM.
ORIGEM_CVM = re.compile(r"\bPROCESSOS?\s+(?:DE\s+)?(?:ORIGEM\s+)?(?:NA\s+PRIMEIRA\s+INST[ÂA]NCIA\s*:?\s*)?"
                        r"(?:BCB\s+)?CVM\s+(?:N[º°O.]*\s*)?(?:RJ|SP)?\s*[-/]?\s*\d", re.I)


def orgao_por_sinais(texto):
    """(órgão, critério) pelos sinais do preâmbulo."""
    t = plana(texto.replace("\n", " "))
    achados = {}
    for orgao, sinais in SINAIS:
        nomes = [n for n, rx in sinais if re.search(rx, t, re.I)]
        if nomes:
            achados[orgao] = nomes
    if len(achados) == 1:
        (o, nomes), = achados.items()
        return o, "preâmbulo: " + ", ".join(nomes)
    if achados:
        conflito = "sinais conflitantes (%s)" % "; ".join(
            "%s: %s" % (o, ", ".join(n)) for o, n in achados.items())
        if "CVM" in achados and ORIGEM_CVM.search(t):
            return "CVM", "processo de origem da CVM; " + conflito
        return "INDETERMINADO", conflito
    return "INDETERMINADO", "sem sinal no preâmbulo"


_ORGAO_PREF = r"^(?:CRSFN\s*[-–]\s*)?(?:CVM|BCB|BACEN|COAF|SUSEP)\b\s*(?:n[º°o.]*\s*)?"


def processo_origem(texto):
    """(valor como publicado, normalizado, processos, nup) do processo de primeira instância."""
    valor = ""
    for x in texto.splitlines():
        p = plana(x)
        m = re.match(r"^Processo\s+na\s+primeira\s+inst[âa]ncia\s*:?\s*(.+)$", p, re.I) or \
            re.match(r"^Processos?\s+(?:de\s+)?(?:origem\s+)?(?:n[º°o.]*\s*)?(CVM\b.+)$", p, re.I)
        if m:
            valor = m.group(1).strip()
            break
    if not valor:
        m = re.search(r"Processo\s+(?:de\s+origem\s+)?(CVM\s+(?:n[º°o.]*\s*)?[\w./\-]+)", texto, re.I)
        valor = m.group(1) if m else ""
    sem_orgao = re.sub(_ORGAO_PREF, "", valor, flags=re.I).strip()
    publicado = jc.processo_publicado(sem_orgao) or sem_orgao.split(" ")[0] if sem_orgao else ""
    return publicado, jc.normalizar_processo(sem_orgao), jc.processos(sem_orgao), jc.nup(sem_orgao)


def classificar_item(id_, item, cliente, cache, pm=pdf_macos):
    """Registro de classificação do item (baixa a fonte, salvo prefixo de NUP de outro órgão)."""
    reg = {"id": id_, "item_url": item.get("item_url"), "ano": item.get("ano"),
           "titulo": item.get("titulo"), "tipo": item.get("tipo"),
           "orgao_inventario": item.get("orgao"), "criterio_inventario": item.get("criterio"),
           "orgao": "", "criterio": "", "processo_origem": "", "processo": "", "processos": [],
           "nup": "", "cache": "", "requisicoes": 0}
    crit_inv = item.get("criterio") or ""
    if crit_inv.startswith("prefixo NUP") and item.get("orgao") not in ("CVM", "INDETERMINADO"):
        reg.update(orgao=item["orgao"], criterio="%s no título (sem download)" % crit_inv)
        return reg
    cam, meta = baixar(item, id_, cliente, cache)
    reg["cache"] = os.path.basename(cam)
    reg["requisicoes"] = meta.get("requisicoes", 0)
    fonte = ler_fonte(cam, pm, so_inicio=True)
    texto = fonte["texto"]
    if cam.endswith(".html"):
        texto = documentos(texto)[0]
    pre = preambulo(texto)
    orgao, crit = orgao_por_sinais(pre)
    inv = item.get("orgao") or "INDETERMINADO"
    if orgao == "INDETERMINADO" and crit == "sem sinal no preâmbulo" and inv != "INDETERMINADO":
        orgao, crit = inv, "inventário: %s (sem sinal no preâmbulo)" % crit_inv
    elif inv not in ("INDETERMINADO", orgao):
        crit += " (inventário dizia %s)" % inv
    reg.update(orgao=orgao, criterio=crit)
    pub, norm, procs, nup = processo_origem(pre)
    reg.update(processo_origem=pub, processo=norm, processos=procs, nup=nup)
    return reg


def _sha_da_fonte(id_, cache):
    """sha256 da fonte do item no cache, ou None (sem fonte baixada)."""
    meta = _ler_json(os.path.join(cache, id_ + ".json"), {})
    cam = os.path.join(cache, meta.get("arquivo") or "")
    if not meta.get("arquivo") or not os.path.isfile(cam):
        return None
    with open(cam, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def duplicatas(ids, cache):
    """{id repetido: id mantido}. Mesmo sha256 da fonte é o mesmo arquivo e dá o mesmo corpo: um
    julgado só. Fica o primeiro de `ids` (a ordem de atribuir_ids, em que o id sem sufixo vem
    antes do -2); ids sem fonte no cache não entram."""
    primeiro, rep = {}, {}
    for i in ids:
        sha = _sha_da_fonte(i, cache)
        if sha is None:
            continue
        if sha in primeiro:
            rep[i] = primeiro[sha]
        else:
            primeiro[sha] = i
    return rep


def _ordem_id(i):
    """Ordem de atribuir_ids dentro do mesmo número: base, -2, -3..."""
    m = re.fullmatch(r"(.+?)-([2-9])", i)
    return (m.group(1), int(m.group(2))) if m else (i, 1)


def gravar_ligacoes(classif, destino, cache=None):
    lig = {}
    cvm = sorted((i for i, r in classif.get("itens", {}).items() if r.get("orgao") == "CVM"), key=_ordem_id)
    rep = duplicatas(cvm, cache) if cache else {}
    for i, r in sorted(classif.get("itens", {}).items()):
        if r.get("orgao") != "CVM" or i in rep:
            continue
        for p in dict.fromkeys([r.get("processo")] + list(r.get("processos") or [])):
            if p:
                lig.setdefault(p, [])
                if i not in lig[p]:
                    lig[p].append(i)
    _gravar_json(destino, {"gerado": _agora(), "n": len(lig), "ligacoes": lig})
    return lig


def classificar(pares, cliente, cam, pm=pdf_macos, log=print):
    classif = _ler_json(cam["classificacao"], {"gerado": "", "itens": {}, "erros": {}})
    classif.setdefault("erros", {})
    feitos = 0
    for id_, item in pares:
        if id_ in classif["itens"] and classif["itens"][id_]["orgao"] != "INDETERMINADO":
            continue  # indeterminado é reclassificado (a regra pode ter mudado)
        try:
            reg = classificar_item(id_, item, cliente, cam["cache"], pm)
        except Exception as e:  # noqa: BLE001 — erro do item fica registrado; nova tentativa depois
            classif["erros"][id_] = "%s: %s" % (type(e).__name__, e)
            log("%s: erro %s" % (id_, classif["erros"][id_]))
            continue
        classif["itens"][id_] = reg
        classif["erros"].pop(id_, None)
        log("%s: %s (%s)" % (id_, reg["orgao"], reg["criterio"]))
        feitos += 1
        if feitos % SALVAR_A_CADA == 0:
            classif["gerado"] = _agora()
            _gravar_json(cam["classificacao"], classif)
    classif["gerado"] = _agora()
    _gravar_json(cam["classificacao"], classif)
    gravar_ligacoes(classif, cam["ligacoes"], cam["cache"])
    return classif


# ---------------------------------------------------------------- seções

_TIMBRE = re.compile(
    r"^(?:MINIST[ÉE]RIO\s+D[AO]\s+(?:FAZENDA|ECONOMIA)\b.*|"
    r"CONSELHO\s+DE\s+RECURSOS\s+DO\s+SISTEMA\s+FINANCEIRO\s+NACIONAL\s*(?:[-–]\s*CRSFN)?|"
    r"CR[FS][SF]N\s*[-–]\s*CONSELHO\s+DE\s+RECURSOS\s+DO\s+SISTEMA\s+FINANCEIRO\s+NACIONAL)$", re.I)
_MINISTERIO = re.compile(r"^MINIST[ÉE]RIO\s+D[AO]\s+(?:FAZENDA|ECONOMIA)\b", re.I)
_RODAPE = re.compile(
    r"^(?:Boletim\s+de\s+Servi[çc]o\s+Eletr[ôo]nico\s+em\s+[\d/]+|"
    r"Documento\s+assinado\s+eletronicamente(?:\s+por\s+.*)?|"
    r"A\s+autenticidade\s+(?:deste|do)\s+documento\s+.*|"
    r"Refer[êe]ncia:\s*Processo\s+n.*|SEI\s+n[º°o]\s*[\d.]+|"
    r"Recurso\s+@md_\w+@|Modalidade\(s\)\s+de\s+Julgamento:.*|"
    r"Criado\s+por\s+\S+,\s+vers[ãa]o\s+\d+.*)$", re.I)
_ROTULO = re.compile(r"^(?:RECURSOS?(?:\s+\w+)?|RECORRENTES?|RECORRID[OA]S?|RELATORA?|"
                     r"ADVOGAD[OA]S?|INTERESSAD[OA]S?|\d+ª\s+Sess[ãa]o|Processo\b.*)\s*:?$", re.I)


def _lixo(linha):
    p = plana(linha)
    return bool(p) and bool(_TIMBRE.match(p) or _RODAPE.match(p))


def documentos(md):
    """Divide o extrato do SEI em documentos, a cada timbre do Ministério após conteúdo."""
    docs, atual, tem = [], [], False
    for x in md.splitlines():
        if _MINISTERIO.match(plana(x)) and tem:
            docs.append("\n".join(atual))
            atual, tem = [], False
        atual.append(x)
        if plana(x) and not _lixo(x):
            tem = True
    docs.append("\n".join(atual))
    return docs


def _compacto(p):
    return re.sub(r"[\s.:]+", "", p).upper()


def _gatilho(p, estado, ementa_vista, ementa_depois, voto_depois):
    """(seção, manter a linha, tirar rótulo da ementa) ou None."""
    if _EMENTA.match(p) and not ementa_vista:
        return "Ementa", True, True
    if re.match(r"^AC[ÓO]RD[ÃA]O\s*/?\s*CRSFN\b", p, re.I):
        if ementa_depois:
            return None
        return ("Relatório" if voto_depois else "Acórdão"), True, False
    c = _compacto(p)
    if len(p) <= 40 and c in ("RELATÓRIO", "RELATORIO"):
        return "Relatório", False, False
    if _e_voto(p):
        return "Voto", False, False
    # inicial maiúscula: "declaração de voto, na qual..." é a frase do relatório, não o título
    if (len(p) <= 120 and p[:1].isupper()
            and re.match(r"^(?:DECLARA[ÇC][ÃA]O|MANIFESTA[ÇC][ÃA]O)\s+DE\s+VOTO\b", p, re.I)):
        return "Declaração de voto", True, False
    if len(p) <= 40 and c in ("DECISÃO", "DECISAO") and estado in (None, "Texto", "Ementa"):
        return "Decisão", False, False
    if estado in ("Voto", "Declaração de voto") and re.match(r"^Vistos,?\s+relatados", p, re.I):
        return "Acórdão", True, False
    return None


_VOTO = re.compile(r"^VOTO(?:\s*[-–]\s*VISTA|\s+(?:D[OA]|VENCEDOR|VENCIDO|DIVERGENTE|REVISOR|"
                   r"DE\s+DESEMPATE|DE\s+VISTA)\b.*)\.?$", re.I)


def _e_voto(p):
    """Cabeçalho de voto: "VOTO", "V O T O", "Voto do relator", "VOTO-VISTA" (linha curta)."""
    return len(p) <= 40 and _compacto(p) == "VOTO" or len(p) <= 60 and bool(_VOTO.match(p))


def _escapar(linha):
    return "\\" + linha if linha.lstrip().startswith("#") else linha


def secoes(docs):
    """[(nome, texto)] na ordem da fonte, e as linhas retiradas (timbre e rodapé)."""
    saida, retirado, vistos, ementa_vista = [], [], set(), False

    def abrir(nome):
        if saida and saida[-1][0] == nome:
            return
        saida.append((nome, []))

    for k, doc in enumerate(docs):
        linhas = [x for x in doc.splitlines()]
        planas = [plana(x) for x in linhas]
        voto_idx = [i for i, p in enumerate(planas) if _e_voto(p)]
        ementa_idx = [i for i, p in enumerate(planas) if _EMENTA.match(p)]
        estado = "Texto" if k == 0 else None
        if k == 0:
            abrir("Texto")
        buffer = []
        for i, (x, p) in enumerate(zip(linhas, planas)):
            if _lixo(x):
                retirado.append(x)
                continue
            g = _gatilho(p, estado, ementa_vista,
                         any(j > i for j in ementa_idx) and not ementa_vista,
                         any(j > i for j in voto_idx))
            if g:
                nome, manter, tirar_rotulo = g
                if nome == "Ementa":
                    ementa_vista = True
                estado = nome
                abrir(nome)
                if buffer:
                    saida[-1][1].extend(buffer)
                    buffer = []
                if manter:
                    if tirar_rotulo:
                        x = re.sub(r"^\s*\**\s*EMENTA\s*\**\s*:\s*\**\s*", "", x, flags=re.I)
                    saida[-1][1].append(x)
                continue
            chave = p.lower()
            if estado is None:
                if p and (chave in vistos or (len(p) <= 120 and _ROTULO.match(p))):
                    continue
                buffer.append(x)
            else:
                saida[-1][1].append(x)
            if p:
                vistos.add(chave)
        if estado is None and any(plana(b) for b in buffer):
            abrir("Texto")
            saida[-1][1].extend(buffer)
    final = []
    for nome, ls in saida:
        txt = re.sub(r"\n{3,}", "\n\n", "\n".join(_escapar(x.rstrip()) for x in ls)).strip()
        if txt:
            if final and final[-1][0] == nome:
                final[-1] = (nome, final[-1][1] + "\n\n" + txt)
            else:
                final.append((nome, txt))
    return final, retirado


# ---------------------------------------------------------------- metadados

_DATA = r"(\d{1,2})º?\s+de\s+([a-zç]+)\s+de\s+(\d{4})"


def _data_ext(m, g=1):
    mes = MESES.get(_sem_acento(m.group(g + 1).lower())) or MESES.get(m.group(g + 1).lower())
    if not mes:
        return None
    try:
        return datetime.date(int(m.group(g + 2)), mes, int(m.group(g))).isoformat()
    except ValueError:
        return None


def datas_candidatas(texto, disposicao=""):
    """[(data, origem)] em ordem de preferência."""
    t = "\n".join(plana(x) for x in texto.splitlines())
    cands = []
    regras = (("sessão numerada", r"\d+ª\s+Sess[ãa]o[^\n]{0,40}?\s+em\s+" + _DATA),
              ("sessão encerrada", r"encerrada\s+em\s+" + _DATA),
              ("sessão", r"Sess[ãa]o[^\n]{0,60}?\s+em\s+" + _DATA),
              ("sala das sessões", r"Sala\s+das\s+Sess[õo]es[^\n,]*,\s*" + _DATA))
    for origem, rx in regras:
        for m in re.finditer(rx, t, re.I):
            d = _data_ext(m)
            if d:
                cands.append((d, origem))
    fechos = list(re.finditer(r"^(?:Bras[íi]lia|Rio\s+de\s+Janeiro|S[ãa]o\s+Paulo)(?:\s*[-/(]\s*\w{2}\)?)?"
                              r"\s*[,-]\s*" + _DATA, t, re.I | re.M))
    for m in reversed(fechos):
        d = _data_ext(m)
        if d:
            cands.append((d, "fecho"))
            break
    import urllib.parse
    m = re.search(_DATA, urllib.parse.unquote(disposicao or ""), re.I)
    if m and _data_ext(m):
        cands.append((_data_ext(m), "nome do arquivo"))
    for m in re.finditer(r"assinado\s+eletronicamente\s+por\s+.{0,200}?\s+em\s+(\d{2}/\d{2}/\d{4})", t, re.I):
        cands.append((jc.data_br(m.group(1)), "assinatura"))
    return cands


def escolher_data(cands, ano):
    """(data, aviso)."""
    if not cands:
        return None, ""
    for d, o in cands:
        if ano and d[:4] == str(ano):
            return d, ""
    d, o = cands[0]
    return d, "data da sessão (%s, %s) fora do ano da listagem (%s)" % (d, o, ano)


def _parece_nome(s):
    s = re.sub(r"\s*[-–]\s*$", "", s.strip())
    if not s or len(s) > 80 or re.search(r"[\d,;:()/]", s):
        return ""
    palavras = s.split()
    if not 2 <= len(palavras) <= 8:
        return ""
    for w in palavras:
        if w.lower() in ("de", "da", "do", "das", "dos", "e"):
            continue
        if not w[0].isupper():
            return ""
    return s


def relator(texto):
    linhas = [plana(x) for x in texto.splitlines() if not _lixo(x)]
    linhas = [x for x in linhas if x]
    for i, p in enumerate(linhas):
        m = re.match(r"^RELATORA?\s*:\s*(.*)$", p, re.I)
        if m:
            nome = _parece_nome(m.group(1)) or (_parece_nome(linhas[i + 1]) if i + 1 < len(linhas) else "")
            if nome:
                return nome
    for i, p in enumerate(linhas):
        if i and re.fullmatch(r"(?:Conselheir[oa]\s*[-–]?\s*)?Relatora?\.?", p, re.I):
            nome = _parece_nome(linhas[i - 1])
            if nome:
                return nome
    for p in linhas:
        m = re.search(r"([A-ZÀ-Ý][\wÀ-ÿ ]+?)\s*[-–]\s*Conselheir[oa]\s*[-–]?\s*Relatora?\b", p)
        if m and _parece_nome(m.group(1).split(". ")[-1]):
            return _parece_nome(m.group(1).split(". ")[-1])
    return ""


_VOLUNTARIO = re.compile(r"RECURSOS?(?:\(S\))?\s+VOLUNT[ÁA]RIOS?", re.I)
_OFICIO = re.compile(r"RECURSOS?(?:\(S\))?\s+DE\s+OF[ÍI]CIO", re.I)
_NEGA = re.compile(r"\bneg(?:ar|ou|aram)(?:-lhes?)?\s+provimento", re.I)
_BLOQUEIO = re.compile(r"parcial|\bd(?:ar|eu|ado)\s+provimento|prescri|nulidade|\banul|extin|"
                       r"n[ãa]o\s+conhec|devolu|\breduz|redu[çc][ãa]o|mitig|em\s+parte|\bprovido|"
                       r"reformar", re.I)


def resultado(pre_ementa, acordao):
    """condenacao (voluntário não provido), absolvicao (de ofício não provido) ou ""."""
    vol, ofi = bool(_VOLUNTARIO.search(pre_ementa)), bool(_OFICIO.search(pre_ementa))
    acordao = re.split(r"\bVencid[oa]s?\b|\bParticiparam\b|\bIniciad[oa]\s+na\b|\bPresentes\b",
                       acordao or "")[0]  # só o dispositivo; voto vencido não bloqueia
    if not acordao or vol == ofi or not _NEGA.search(acordao) or _BLOQUEIO.search(acordao):
        return ""
    return "condenacao" if vol else "absolvicao"


def ementa_oficial(texto_ementa):
    partes = []
    for x in texto_ementa.splitlines():
        p = plana(x)
        if not p:
            if partes:
                break
            continue
        if re.match(r"^(?:PENALIDADES?|BASE\s+LEGAL|AC[ÓO]RD[ÃA]O)\b", p, re.I):
            break
        partes.append(p)
    return pii.limpar(re.sub(r"\s+", " ", " ".join(partes)).strip())


# ---------------------------------------------------------------- conversão

# Documentos do CRSFN com mais de um acórdão no mesmo arquivo da fonte. Ficam inteiros
# (um julgado por arquivo da fonte); o incerteza registra os acórdãos que o corpo contém.
INCERTEZA_DOCUMENTO = {
    "crsfn-14361": "documento com 2 acórdãos: Ac. 48/2018 (2018-02-20, 410ª sessão); "
                   "Ac. 141/2018 (2018-06-26)",
}


def converter_item(reg, item, cam_fonte, meta, pm=pdf_macos):
    """(valores, corpo, info) do item CVM. Sem data: ValueError."""
    fonte = ler_fonte(cam_fonte, pm)
    html = cam_fonte.endswith(".html")
    docs = documentos(fonte["texto"]) if html else [fonte["texto"]]
    secs, retirado = secoes(docs)
    retirado = list(fonte["retirado"]) + retirado
    avisos, incerteza = list(fonte["avisos"]), []
    data, aviso = escolher_data(datas_candidatas(fonte["texto"], meta.get("content_disposition", "")),
                                item.get("ano"))
    if not data:
        raise ValueError("sem data da sessão")
    if aviso:
        incerteza.append(aviso)
    pre = preambulo(docs[0])
    pub, norm, procs, nup = processo_origem(pre)
    pub = pub or reg.get("processo_origem") or ""
    nup = nup or reg.get("nup") or ""
    if not pub:
        pub = jc.processo_publicado(item.get("titulo") or "") or item.get("titulo") or reg["id"]
        incerteza.append("processo CVM de origem não achado; processo do título do CRSFN")
    if reg["id"] in INCERTEZA_DOCUMENTO:
        incerteza.append(INCERTEZA_DOCUMENTO[reg["id"]])
    sec = dict(secs)
    ementa_txt = sec.get("Ementa", "")
    ementa = ementa_oficial(ementa_txt) if ementa_txt else ""
    if ementa:
        fonte_em = "crsfn"
    else:
        ementa, fonte_em = "Recurso ao CRSFN no Processo CVM %s." % pub, "titulo"
    acordao = "\n".join(t for n, t in secs if n == "Acórdão")
    res = resultado(pre + "\n" + ementa_txt, acordao)
    titulo = plana(item.get("titulo") or reg["id"])
    corpo_bruto = "# %s\n\n" % _escapar(titulo) + "\n\n".join("## %s\n\n%s" % (n, t) for n, t in secs) + "\n"
    corpo = pii.limpar(corpo_bruto)
    if not corpo.endswith("\n"):
        corpo += "\n"
    normas, disp, av = jconv.citacoes(corpo)
    if av:
        avisos.append(av)
    with open(cam_fonte, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    valores = {"id": reg["id"], "orgao": "crsfn", "tipo": TIPO, "classe": "", "processo": pub,
               "nup": nup, "rito": "", "data": data, "relator": relator(fonte["texto"]),
               "resultado": res, "ementa": ementa, "ementa_fonte": fonte_em, "tema": "",
               "tema_fonte": "", "normas_citadas": normas, "dispositivos_citados": disp,
               "fonte_original": item.get("item_url") or "", "sha256_fonte": sha,
               "baixado_em": meta.get("baixado_em") or jc.hoje_sp(),
               "nivel_verificacao": fonte["nivel"], "incerteza": "; ".join(incerteza)}
    info = {"motor": fonte["motor"], "retirado": "\n".join(retirado), "antes_pii": corpo_bruto,
            "secoes": [n for n, _ in secs], "avisos": avisos}
    valores, corpo, _ = je.ementa_sem_pessoas(valores, corpo)  # D3 na ementa do frontmatter
    return valores, corpo, info


def gravar(valores, corpo, raiz=jc.RAIZ):
    caminho = jc.caminho_julgado(TIPO, valores["id"], valores["data"][:4], raiz)
    valores = jconv._preservar_extracao(valores, caminho)  # reconversão não apaga o tema extraído
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho + ".parcial", "w", encoding="utf-8") as f:
        f.write(jc.sem_controle(jc.frontmatter(valores) + corpo))
    os.replace(caminho + ".parcial", caminho)
    return caminho


def _conferir(cam_fonte, motor, corpo, retirado, antes_pii):
    regiao = "sei" if cam_fonte.endswith(".html") else "artigo"
    try:
        return jconv.conferir(os.path.basename(cam_fonte), cam_fonte, motor, corpo, regiao=regiao,
                              retirado=retirado, antes_pii=antes_pii)
    except TypeError:  # assinatura antiga
        return jconv.conferir(os.path.basename(cam_fonte), cam_fonte, motor, corpo, regiao)


def converter(pares, cliente, cam, raiz=jc.RAIZ, pm=pdf_macos, log=print):
    classif = _ler_json(cam["classificacao"], {"itens": {}})
    relat = {"gerado": _agora(), "itens": [], "erros": [], "duplicatas": {}}
    cvm = sorted((i for i, r in classif["itens"].items() if r.get("orgao") == "CVM"), key=_ordem_id)
    rep = duplicatas(cvm, cam["cache"])
    for id_, item in pares:
        reg = classif["itens"].get(id_)
        if not reg or reg.get("orgao") != "CVM":
            continue
        if id_ in rep:  # mesma fonte de outro id: um julgado só
            relat["duplicatas"][id_] = rep[id_]
            log("%s: duplicata de %s (mesmo sha256), não convertido" % (id_, rep[id_]))
            continue
        try:
            cam_fonte, meta = baixar(item, id_, cliente, cam["cache"])
            valores, corpo, info = converter_item(reg, item, cam_fonte, meta, pm)
            destino = gravar(valores, corpo, raiz)
        except Exception as e:  # noqa: BLE001 — erro do item vai para o relatório
            relat["erros"].append({"id": id_, "erro": "%s: %s" % (type(e).__name__, e)})
            log("%s: erro %s" % (id_, e))
            continue
        conf = _conferir(cam_fonte, info["motor"], corpo, info["retirado"], info["antes_pii"])
        relat["itens"].append({
            "id": id_, "orgao": "CVM", "arquivo": os.path.relpath(destino, raiz),
            "cobertura": conf.get("cobertura"), "conferencia": conf,
            "kb": round(len((jc.frontmatter(valores) + corpo).encode("utf-8")) / 1024, 1),
            "secoes": info["secoes"], "nivel": valores["nivel_verificacao"],
            "motor": info["motor"], "resultado": valores["resultado"], "data": valores["data"],
            "avisos": info["avisos"] + ([valores["incerteza"]] if valores["incerteza"] else [])})
        log("%s: %s cobertura=%s seções=%s" % (id_, os.path.relpath(destino, raiz),
                                                conf.get("cobertura"), ",".join(info["secoes"])))
    os.makedirs(cam["relatorios"], exist_ok=True)
    nome = "crsfn-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    _gravar_json(os.path.join(cam["relatorios"], nome), relat)
    gravar_ligacoes(_ler_json(cam["classificacao"], {"itens": {}}), cam["ligacoes"], cam["cache"])
    return relat


# ---------------------------------------------------------------- CLI

def main(argv=None, cliente=None, raiz=jc.RAIZ, pm=pdf_macos, log=print):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("comando", choices=("classificar", "converter"))
    ap.add_argument("--ano", type=int)
    ap.add_argument("--limite", type=int)
    ap.add_argument("--ids", help="ids separados por vírgula")
    a = ap.parse_args(argv)
    cam = caminhos(raiz)
    inv = _ler_json(cam["inventario"], None)
    if inv is None:
        log("crsfn: inventário ausente em %s" % cam["inventario"])
        return 2
    ids = set(x.strip() for x in a.ids.split(",")) if a.ids else None
    pares = selecionar(atribuir_ids(inv["itens"]), ids, a.ano)
    cliente = cliente or jc.Cliente(intervalo=INTERVALO)
    if a.comando == "classificar":
        if a.limite:
            feitos = set(_ler_json(cam["classificacao"], {"itens": {}})["itens"])
            pares = [p for p in pares if p[0] not in feitos][:a.limite]
        c = classificar(pares, cliente, cam, pm, log)
        log("crsfn: %d classificado(s) no total, %d erro(s), %d requisição(ões) nesta rodada" % (
            len(c["itens"]), len(c["erros"]), cliente.n))
        return 0
    cvm = {i for i, r in _ler_json(cam["classificacao"], {"itens": {}})["itens"].items()
           if r.get("orgao") == "CVM"}
    pares = [p for p in pares if p[0] in cvm]
    if a.limite:
        pares = pares[:a.limite]
    r = converter(pares, cliente, cam, raiz, pm, log)
    log("crsfn: %d convertido(s), %d erro(s)" % (len(r["itens"]), len(r["erros"])))
    return 1 if r["erros"] else 0


if __name__ == "__main__":
    sys.exit(main())
