#!/usr/bin/env python3
"""Inventário dos julgados da CVM (Fase 2d).

Lê as listagens (PAS julgados; decisões do Colegiado em janelas semestrais; TCs aceitos e
rejeitados; decisões antigas de 1978 a 2001), a planilha de julgados por relator (2022 a 2025) e
os dados abertos de processo sancionador; classifica os itens do Colegiado pelo título;
deduplica por processo normalizado e URL; casa os TCs da tabela com o item do Colegiado que
apreciou a proposta. Os PAS que faltam na listagem (os da planilha e os julgados depois de
2025-05-27) vêm da notícia do resultado e do extrato do SEI (julgados_noticias, origem
`noticia`); o PAS da planilha sem nenhuma das duas fica como `fonte_pendente`.

Saídas:
- dados/fase-2d/julgados-inventario.json (completo, com título e ementa da listagem; ignorado
  pelo Git);
- fontes/julgados-inventario.json (enxuto: id, tipo, classe, processo, data, url, plugin; sem
  nome de parte).

Uso:
  python3 scripts/julgados_inventario.py --baixar   # grava as listagens em dados/fase-2d/listagens/
  python3 scripts/julgados_inventario.py            # monta o inventário com o que já foi baixado
"""
import argparse
import collections
import csv
import datetime
import io
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from html import unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import julgados_comum as jc  # noqa: E402
import julgados_noticias as jn  # noqa: E402

LISTAGENS = os.path.join(jc.RAIZ, "dados", "fase-2d", "listagens")
SAIDA_COMPLETA = os.path.join(jc.RAIZ, "dados", "fase-2d", "julgados-inventario.json")
SAIDA_ENXUTA = os.path.join(jc.RAIZ, "fontes", "julgados-inventario.json")
DADOS_ABERTOS = os.path.join(jc.RAIZ, "dados", "fase-2d", "inventario", "pas",
                             "processo_sancionador.csv")

URL_PAS = ("/sancionadores/index.html?buscado=true&searchPage=1&contCategoriasCheck=1"
           "&categoria0=/sancionadores/sancionador/&itensPagina=2000&ordenar=recentes"
           "&lastName=&filtro=&dataInicio=&dataFim=")
URL_COLEGIADO = ("/decisoes/index.html?buscadoDecisao=true&categoria=decisao&lastName="
                 "&filtro=todos&dataInicio={ini}&dataFim={fim}&itensPagina=1000&searchPage=1"
                 "&ordenar=antigas")
URL_TC = "/system/modules/br.com.squadra.principal/elements/resultadoTermoCompromisso.jsp"
URL_TC_REJ = ("/system/modules/br.com.squadra.principal/elements/"
              "resultadoTermoCompromissoRejeitado.jsp")
URL_ANTIGAS = ("/publicacao/decisoes_antigas.html?searchPage=1&itensPagina=100&lastName="
               "&filtro=&dataInicio=&dataFim=")
URL_PLANILHA = ("https://www.gov.br/cvm/pt-br/assuntos/processos/processos-julgados-por-relator/"
                "julgados-2022-2025.xlsx")
ANOS_COLEGIADO = (2002, 2026)
DIAS_LINK_SUSPEITO = 31


def _txt(html):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html or ""))).strip()


# ---------------------------------------------------------------- download das listagens

def arquivos_de_listagem():
    """[(nome do arquivo, método, URL, campos do POST)] na ordem de download."""
    out = [("pas.html", "GET", URL_PAS, None)]
    for ano in range(ANOS_COLEGIADO[0], ANOS_COLEGIADO[1] + 1):
        out.append(("colegiado/dec_%d_h1.html" % ano, "GET",
                    URL_COLEGIADO.format(ini="01/01/%d" % ano, fim="30/06/%d" % ano), None))
        out.append(("colegiado/dec_%d_h2.html" % ano, "GET",
                    URL_COLEGIADO.format(ini="01/07/%d" % ano, fim="31/12/%d" % ano), None))
    campos = {"searchPage": "1", "lastName": "", "itensPagina": "2000"}
    out += [("tc_aceitos.html", "POST", URL_TC, campos),
            ("tc_rejeitados.html", "POST", URL_TC_REJ, campos),
            ("antigas.html", "GET", URL_ANTIGAS, None),
            ("julgados-relator.xlsx", "GET", URL_PLANILHA, None)]
    return out


def baixar_listagens(destino=LISTAGENS, cliente=None, refazer=False, log=print):
    cliente = cliente or jc.Cliente()
    feitos = []
    for nome, metodo, url, campos in arquivos_de_listagem():
        alvo = os.path.join(destino, nome)
        if os.path.exists(alvo) and os.path.getsize(alvo) > 0 and not refazer:
            continue
        os.makedirs(os.path.dirname(alvo), exist_ok=True)
        dados = cliente.post(url, campos)[0] if metodo == "POST" else cliente.get(url)[0]
        with open(alvo + ".parcial", "wb") as f:
            f.write(dados)
        os.replace(alvo + ".parcial", alvo)
        feitos.append(nome)
        log("baixado %s (%d bytes)" % (nome, len(dados)))
    return feitos


# ---------------------------------------------------------------- parsers

def ler_artigos(html):
    """Itens <article> das buscas de PAS e do Colegiado: url, titulo, desc, data, reuniao."""
    out = []
    for a in re.findall(r"<article>(.*?)</article>", html, re.S):
        m = re.search(r'<h3>\s*<a[^>]*href="([^"]+)"[^>]*?(?:title="([^"]*)")?[^>]*>(.*?)</a>',
                      a, re.S)
        if not m:
            continue
        titulo = _txt(m.group(2) or m.group(3)) or _txt(m.group(3))
        d = re.search(r"<b>\s*Data:\s*</b>\s*(\d{1,2}/\d{1,2}/\d{4})", a)
        t = re.search(r"<b>\s*Tipo:\s*</b>\s*([^<]+)", a)
        desc = re.search(r'class="contentDesc"[^>]*>(.*?)</div>', a, re.S)
        out.append({"url": unescape(m.group(1)).strip(), "titulo": titulo,
                    "desc": _txt(desc.group(1)) if desc else "",
                    "data": jc.data_br(d.group(1)) if d else None,
                    "reuniao": _txt(t.group(1)) if t else ""})
    return out


def _linhas_tabela(html):
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if tds and "processo" not in _txt(tds[0]).lower():
            yield tds


def _links(html):
    return [jc.reparar_url(unescape(h)) for h in re.findall(r'href="([^"]+)"', html or "")]


def _linha_tc(cel_proc, data, links_decisao):
    pub = jc.processo_publicado(_txt(cel_proc))
    return {"processo": pub, "proc": jc.normalizar_processo(_txt(cel_proc)),
            "nup": jc.nup(_txt(cel_proc)), "procs": jc.processos(_txt(cel_proc)),
            "data": jc.data_br(_txt(data)), "decisao_urls": links_decisao}


def ler_tc_aceitos(html):
    """Linhas da tabela de TCs celebrados. Compromitentes não são guardados (D3)."""
    out = []
    for tds in _linhas_tabela(html):
        if len(tds) < 6:
            continue
        r = _linha_tc(tds[0], tds[1], _links(tds[5]))
        termo = _links(tds[0])
        r["termo_urls"] = [u for u in termo if not _e_pagina_de_decisao(u)]
        # link do número que aponta para a própria decisão vale como link de decisão
        r["decisao_urls"] += [u for u in termo if _e_pagina_de_decisao(u)
                              and u not in r["decisao_urls"]]
        r["assinatura"] = jc.data_br(_txt(tds[2]))
        r["arquivamento"] = jc.data_br(_txt(tds[6])) if len(tds) > 6 else None
        r["resultado"] = "aceito"
        out.append(r)
    return out


def ler_tc_rejeitados(html):
    out = []
    for tds in _linhas_tabela(html):
        if len(tds) < 3:
            continue
        r = _linha_tc(tds[0], tds[1], _links(tds[3]) if len(tds) > 3 else [])
        r["termo_urls"] = []
        r["resultado"] = "rejeitado"
        out.append(r)
    return out


def _e_pagina_de_decisao(url):
    return "/decisoes/" in (url or "") and url.lower().endswith((".html", ".htm"))


def ler_antigas(html):
    """[(ano, url)] dos PDFs anuais de decisões de 1978 a 2001."""
    vistos = {}
    for u in re.findall(r'href="([^"]*decisoes[-_](\d{4})\.pdf)"', html, re.I):
        vistos.setdefault(int(u[1]), unescape(u[0]))
    return sorted(vistos.items())


XL = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def ler_planilha(path):
    """Linhas da planilha de julgados por relator: processo, nup, tipo, rito, sup, relator, data."""
    z = zipfile.ZipFile(path)
    try:
        ss = ["".join(t.text or "" for t in si.iter(XL + "t"))
              for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(XL + "si")]
    except KeyError:
        ss = []
    linhas = []
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(XL + "row"):
        d = {}
        for c in row.iter(XL + "c"):
            v = c.find(XL + "v")
            if v is None:
                isv = c.find(XL + "is")
                if isv is None:
                    continue
                val = "".join(t.text or "" for t in isv.iter(XL + "t"))
            else:
                val = ss[int(v.text)] if c.get("t") == "s" else v.text
            d[re.match(r"[A-Z]+", c.get("r")).group(0)] = (val or "").strip()
        linhas.append(d)
    cab = next((i for i, d in enumerate(linhas) if "Processo SEI" in d.values()), None)
    if cab is None:
        raise ValueError("planilha sem o cabeçalho 'Processo SEI'")
    col = {v: k for k, v in linhas[cab].items()}
    out = []
    for d in linhas[cab + 1:]:
        proc = d.get(col.get("Processo SEI"), "")
        if not jc.nup(proc):
            continue
        serial = d.get(col.get("Data"), "")
        data = None
        if re.fullmatch(r"\d+(\.\d+)?", serial):
            data = (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(serial)))
                    ).isoformat()
        else:
            data = jc.data_br(serial)
        rito = d.get(col.get("Rito"), "").lower()
        out.append({"processo": re.sub(r"\s+", "", proc), "nup": jc.nup(proc),
                    "tipo_processo": d.get(col.get("Tipo"), ""),
                    "rito": "simplificado" if "simpl" in rito else
                            ("ordinario" if "ordin" in rito else ""),
                    "sup": d.get(col.get("Sup."), ""), "relator": d.get(col.get("Relator"), ""),
                    "data": data})
    return out


def ler_dados_abertos(path):
    """{nup normalizado: {"rito", "crsfn"}} dos dados abertos de processo sancionador."""
    with open(path, "rb") as f:
        bruto = f.read()
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    out = {}
    for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
        n = jc.nup(r.get("NUP", ""))
        if not n:
            continue
        juntos = " ".join([r.get("Objeto") or "", r.get("Subfase_Atual") or "",
                           r.get("Fase_Atual") or ""]).lower()
        rito = ("simplificado" if "rito simplificado" in juntos else
                "ordinario" if re.search(r"rito ordin[áa]rio", juntos) else "")
        crsfn = "crsfn" in juntos or "conselho de recursos" in juntos
        out[n] = {"rito": rito, "crsfn": crsfn}
    return out


# ---------------------------------------------------------------- classificação (Colegiado)

def classificar(titulo):
    """Classe bruta do item do Colegiado pelo título (regras de
    dados/fase-2d/inventario/colegiado/scripts/classif.py)."""
    u = re.sub(r"\s+", " ", (titulo or "").upper())
    h = u.split(" – ")[0]
    if re.search(r"TERMO DE COMPROMISSO|TERMOS DE COMPROMISSO", h):
        if re.search(r"CUMPRIMENTO|ARQUIVAMENTO|PRORROGA", h):
            return "tc_cumprimento"
        return "tc_proposta"
    if re.search(r"MULTA COMINAT|TAXA DE FISCALIZA|MECANISMO DE RESSARCIMENTO|FUNDO DE GARANTIA", u):
        return "recurso_multa_taxa_mre_fg"
    # "RITO SUMÁRIO" no título de audiência pública é o assunto da norma, não recurso de multa
    if re.search(r"RITO SUM", u) and not re.search(r"AUDIÊNCIA PÚBLICA|CONSULTA PÚBLICA|MINUTA", h):
        return "recurso_multa_taxa_mre_fg"
    if re.search(r"RECONSIDERA", h):
        return "pedido_reconsideracao"
    if re.search(r"^RECURSOS? ", h):
        return "recurso_outro"
    if re.search(r"DISPENSA|WAIVER", h):
        return "dispensa"
    if re.search(r"AUDIÊNCIA PÚBLICA|CONSULTA PÚBLICA|MINUTA|PROPOSTA DE (RESOLU|DELIBERA|INSTRU)|"
                 r"PROPOSTAS DE RESOLU|NORMA|REGULAMENTA", h):
        return "normativo_audiencia"
    if re.search(r"EFEITO SUSPENSIVO|PRODUÇÃO DE PROVAS|RECAPITULA|DEFINIÇÃO JURÍDICA|\bPAS\b|"
                 r"PROCESSO ADMINISTRATIVO SANCIONADOR|IMPEDIMENTO|SUSPENSÃO PREVENTIVA|"
                 r"ADITAMENTO|ACUSAÇÃO|RITO SUMÁRIO", u):
        return "pas_incidente"
    if re.search(r"TRATAMENTO CONFIDENCIAL", h):
        return "confidencial"
    if re.search(r"CONSULTA|ORIENTAÇÃO|PARECER DE ORIENTA", h):
        return "consulta"
    if re.search(r"REGISTRO|CANCELAMENTO|SUSPENSÃO DE OFÍCIO|AUTORIZA|ANUÊNCIA|EMISSÃO|OFERTA|"
                 r"OPA\b", h):
        return "registro_autorizacao"
    if re.search(r"ADIAMENTO|ASSEMBLEIA|COMPANHIA|AGO\b|AGE\b", u):
        return "societario_assembleia"
    if re.search(r"ORÇAMENTO|AUDITORIA INTERNA|PLANO|CONVÊNIO|COOPERAÇÃO|CONTRATO|ADMINISTRATIVO|"
                 r"SUPERVISÃO BASEAD|SERVIDOR|PESSOAL|CALENDÁRIO", u):
        return "institucional"
    return "outros"


CLASSE_CONTRATO = {
    "recurso_multa_taxa_mre_fg": "multa-cominatoria", "pedido_reconsideracao": "reconsideracao",
    "recurso_outro": "recurso", "dispensa": "dispensa", "normativo_audiencia": "normativo",
    "pas_incidente": "incidente-pas", "consulta": "consulta", "registro_autorizacao": "registro",
    "institucional": "institucional", "confidencial": "outros",
    "societario_assembleia": "outros", "tc_cumprimento": "outros", "outros": "outros",
}


# ---------------------------------------------------------------- montagem

def _dias(a, b):
    try:
        return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)
    except (TypeError, ValueError):
        return None


def _data_da_url(url):
    m = re.search(r"/(\d{4})(\d{2})(\d{2})_?R\d", url or "")
    return "%s-%s-%s" % m.groups() if m else None


def _unico(id_, usados, sufixo=None):
    if id_ not in usados:
        return id_
    if sufixo and id_ + sufixo not in usados:
        return id_ + sufixo
    n = 2
    while "%s-%d" % (id_, n) in usados:
        n += 1
    return "%s-%d" % (id_, n)


DESDE_NOTICIAS = "2025-06-01"  # a listagem de PAS para em 2025-05-27


def _campos_noticia(ent):
    """Campos do registro de PAS que vem da notícia do resultado e do extrato do SEI: a URL
    principal é a notícia (ou o extrato, sem notícia); só o último extrato (retificação)."""
    ext = sorted(ent.get("extratos", []), key=lambda e: (e["data_pub"] or "", e["id_documento"]))
    ult = ext[-1] if ext else None
    return {"origem": "noticia", "url": ent["noticia"] or (ult["url"] if ult else ""),
            "noticia": ent["noticia"], "outras_noticias": ent.get("outras_noticias", []),
            "pecas": [{"url": u, "rotulo": r} for u, r in ent["pecas"]],
            "sei_urls": [ult["url"]] if ult else [], "desc": ult["resumo"] if ult else "",
            "fonte_pendente": False}


def montar(pas, colegiado, tc_aceitos, tc_rejeitados, antigas, planilha, abertos, noticias=None,
           hoje=None):
    """Registros do inventário (dicionários) e o resumo de contagens. `noticias`: {NUP: entrada}
    de julgados_noticias.indice, para os PAS que faltam na listagem."""
    registros, usados = [], set()
    resumo = collections.Counter()

    def novo(r):
        usados.add(r["id"])
        r["plugin"] = jc.plugin_do_julgado(r["tipo"], r["data"][:4])
        registros.append(r)
        return r

    # --- Colegiado
    por_url = {}
    for it in sorted(colegiado, key=lambda x: (x["data"] or "", x["url"])):
        chave = jc.caminho_url(it["url"])
        if chave in por_url:
            resumo["colegiado_url_repetida"] += 1
            continue
        try:
            data_url, _, reuniao = jc.slug_colegiado(chave)
            data_url = "%s-%s-%s" % (data_url[:4], data_url[4:6], data_url[6:])  # ISO, como a listagem
            base = jc.id_colegiado(chave)
        except ValueError:
            resumo["colegiado_url_fora_do_padrao"] += 1
            continue
        bruta = classificar(it["titulo"])
        r = {"id": _unico(base, usados, "-r%d" % reuniao if reuniao > 1 else None),
             "tipo": "termo-compromisso" if bruta == "tc_proposta" else "decisao-colegiado",
             "classe": "" if bruta == "tc_proposta" else CLASSE_CONTRATO[bruta],
             "classe_bruta": bruta, "processo": jc.processo_publicado(it["titulo"]),
             "proc": jc.normalizar_processo(it["titulo"]), "nup": jc.nup(it["titulo"]),
             "procs": jc.processos(it["titulo"]), "data": it["data"] or data_url,
             "url": jc.absoluta(chave), "titulo": it["titulo"], "desc": it["desc"],
             "reuniao": it.get("reuniao", ""), "origem": "colegiado", "incerteza": []}
        if it["data"] and data_url and it["data"] != data_url:
            r["incerteza"].append("data da listagem %s difere da URL %s" % (it["data"], data_url))
        por_url[chave] = novo(r)

    # --- TCs da tabela: casa com o item do Colegiado (link; senão data + processo)
    por_data = collections.defaultdict(list)
    for r in por_url.values():
        por_data[r["data"]].append(r)
    linhas_tc = collections.OrderedDict()
    for linha in tc_aceitos + tc_rejeitados:
        # uma linha por compromitente: junta as do mesmo processo, data e resultado
        chave_tc = (linha["proc"] or linha["processo"], linha["data"], linha["resultado"],
                    tuple(linha["decisao_urls"]) if not linha["proc"] else ())
        if chave_tc in linhas_tc:
            resumo["tc_linha_juntada"] += 1
            base = linhas_tc[chave_tc]
            base["termo_urls"] += [u for u in linha["termo_urls"] if u not in base["termo_urls"]]
            base["decisao_urls"] += [u for u in linha["decisao_urls"]
                                     if u not in base["decisao_urls"]]
            continue
        linhas_tc[chave_tc] = dict(linha, termo_urls=list(linha["termo_urls"]),
                                   decisao_urls=list(linha["decisao_urls"]))
    for linha in linhas_tc.values():
        alvo, suspeito = None, []
        for u in linha["decisao_urls"]:
            c = jc.caminho_url(u)
            if c in por_url:
                d = _dias(linha["data"], _data_da_url(c))
                if d is not None and d > DIAS_LINK_SUSPEITO:
                    if set(por_url[c]["procs"]) & set(linha["procs"]):
                        # o item trata do mesmo processo: o link vale, a data diverge
                        suspeito.append("data da tabela de TCs (%s) difere da data da URL (%s)" %
                                        (linha["data"], _data_da_url(c)))
                        alvo = por_url[c]
                        break
                    suspeito.append("link de decisão suspeito: tabela %s, URL %s" %
                                    (linha["data"], _data_da_url(c)))
                    continue
                alvo = por_url[c]
                break
        modo = "link" if alvo else None
        if alvo is None and linha["procs"]:
            cands = [r for r in por_data.get(linha["data"], [])
                     if set(r["procs"]) & set(linha["procs"])]
            if len(cands) == 1:
                alvo, modo = cands[0], "data-processo"
        resumo["tc_%s" % linha["resultado"]] += 1
        if alvo is not None:
            resumo["tc_%s_casado_%s" % (linha["resultado"], modo)] += 1
            if alvo["tipo"] != "termo-compromisso":
                alvo["tipo_pelo_titulo"] = alvo["tipo"]
                alvo["tipo"], alvo["classe"] = "termo-compromisso", ""
                alvo["plugin"] = jc.plugin_do_julgado("termo-compromisso", alvo["data"][:4])
            alvo.setdefault("tc_tabela", []).append(
                {"resultado": linha["resultado"], "processo": linha["processo"],
                 "data": linha["data"], "termo_urls": linha["termo_urls"]})
            alvo["incerteza"] += suspeito
            continue
        resumo["tc_%s_avulso" % linha["resultado"]] += 1
        if not linha["proc"] or not linha["data"]:
            resumo["tc_sem_processo_ou_data"] += 1
            continue
        url = (linha["termo_urls"] or [""])[0]
        reuniao = [u for u in linha["decisao_urls"] if re.search(r"_R\d+\.html?$", u)]
        r = {"id": _unico(jc.id_tc_avulso(linha["proc"], linha["data"]), usados),
             "tipo": "termo-compromisso", "classe": "", "classe_bruta": "",
             "processo": linha["processo"], "proc": linha["proc"], "nup": linha["nup"],
             "procs": linha["procs"], "data": linha["data"], "url": jc.absoluta(url) if url else "",
             "titulo": "", "desc": "", "origem": "tc-tabela", "resultado": linha["resultado"],
             "termo_urls": [jc.absoluta(u) for u in linha["termo_urls"]],
             "decisao_urls": [jc.absoluta(u) for u in linha["decisao_urls"]],
             "fonte_pendente": not url, "incerteza": list(suspeito)}
        if reuniao:
            r["incerteza"].append("decisão só na página da reunião")
        if not url:
            r["incerteza"].append("sem termo nem item de decisão publicado na tabela")
        novo(r)
    for r in registros:
        tcs = r.get("tc_tabela")
        if tcs:
            res = {t["resultado"] for t in tcs}
            r["resultado"] = res.pop() if len(res) == 1 else "outro"
            if r["resultado"] == "outro":
                r["incerteza"].append("TC aceito para parte dos proponentes e rejeitado para outra")
            r["termo_urls"] = [jc.absoluta(u) for t in tcs for u in t["termo_urls"]]

    # --- PAS
    vistos_url, pas_por_nup = set(), collections.defaultdict(list)
    for it in sorted(pas, key=lambda x: (x["data"] or "", x["url"])):
        chave = jc.caminho_url(it["url"])
        if chave in vistos_url:
            resumo["pas_url_repetida"] += 1
            continue
        vistos_url.add(chave)
        proc = jc.normalizar_processo(it["titulo"]) or jc.normalizar_processo(
            os.path.basename(chave))
        if not proc:
            resumo["pas_sem_processo"] += 1
            continue
        n = jc.nup(it["titulo"]) or jc.nup(os.path.basename(chave))
        r = novo({"id": _unico(jc.id_pas(proc), usados), "tipo": "pas", "classe": "",
                  "classe_bruta": "", "processo": jc.processo_publicado(it["titulo"]),
                  "proc": proc, "nup": n, "procs": jc.processos(it["titulo"]),
                  "data": it["data"], "url": jc.absoluta(chave), "titulo": it["titulo"],
                  "desc": it["desc"], "origem": "pas", "incerteza": []})
        if n:
            pas_por_nup[n].append(r)
    por_nup_noticia = {jc.nup(k): v for k, v in (noticias or {}).items() if jc.nup(k)}
    for linha in planilha:
        achados = pas_por_nup.get(linha["nup"], [])
        if achados:
            alvo = min(achados, key=lambda r: _dias(r["data"], linha["data"]) or 0)
            alvo["rito"], alvo["relator"] = linha["rito"], linha["relator"]
            alvo["planilha"] = {"tipo_processo": linha["tipo_processo"], "sup": linha["sup"],
                                "data": linha["data"]}
            resumo["planilha_casada"] += 1
            continue
        r = novo({"id": _unico(jc.id_pas(linha["nup"]), usados), "tipo": "pas", "classe": "",
                  "classe_bruta": "", "processo": linha["processo"], "proc": linha["nup"],
                  "nup": linha["nup"], "procs": [linha["nup"]], "data": linha["data"],
                  "url": "", "titulo": "", "desc": "", "origem": "planilha-relator",
                  "rito": linha["rito"], "relator": linha["relator"], "fonte_pendente": True,
                  "planilha": {"tipo_processo": linha["tipo_processo"], "sup": linha["sup"],
                               "data": linha["data"]},
                  "incerteza": ["julgado na planilha da CVM e ausente da listagem de PAS"]})
        ent = por_nup_noticia.get(linha["nup"])
        if ent and (ent["noticia"] or ent.get("extratos")):
            r.update(_campos_noticia(ent))
            r["incerteza"] = ["julgado na planilha da CVM e ausente da listagem de PAS; fonte: "
                              "notícia do resultado e extrato do SEI"]
            resumo["planilha_com_noticia"] += 1
        else:
            resumo["pas_fonte_pendente"] += 1
        pas_por_nup[linha["nup"]].append(r)
    hoje = hoje or jc.hoje_sp()
    for n, ent in sorted(por_nup_noticia.items(), key=lambda x: (x[1]["data"] or "", x[0])):
        if n in pas_por_nup:
            continue
        if not ent["data"] or ent["data"] > hoje:
            resumo["noticia_futura"] += 1
            continue
        if ent["data"] < DESDE_NOTICIAS:
            resumo["noticia_fora_da_janela"] += 1
            continue
        resumo["noticia_nova"] += 1
        r = novo(dict({"id": _unico(jc.id_pas(n), usados), "tipo": "pas", "classe": "",
                       "classe_bruta": "", "processo": ent["nup"], "proc": n, "nup": n,
                       "procs": [n], "data": ent["data"], "titulo": "",
                       "incerteza": ["julgado ausente da listagem de PAS; fonte: notícia do "
                                     "resultado e extrato do SEI"]}, **_campos_noticia(ent)))
        if ent["data_fonte"] != "noticia":
            r["incerteza"].append("data aproximada: publicação do extrato no SEI")
        pas_por_nup[n].append(r)
    for n, rs in pas_por_nup.items():
        ab = abertos.get(n)
        if not ab:
            continue
        for r in rs:
            if not r.get("rito") and ab["rito"]:
                r["rito"] = ab["rito"]
            if ab["crsfn"]:
                r["incerteza"].append("recurso ao CRSFN (dados abertos)")
            resumo["pas_com_dados_abertos"] += 1

    # --- decisões antigas
    for ano, url in antigas:
        novo({"id": jc.id_decisao_antiga(ano), "tipo": "decisao-antiga", "classe": "outros",
              "classe_bruta": "", "processo": "", "proc": "", "nup": "", "procs": [],
              "data": "%d-01-01" % ano, "data_aproximada": True, "url": jc.absoluta(url),
              "titulo": "Decisões do Colegiado de %d" % ano, "desc": "", "origem": "antigas",
              "incerteza": []})

    for r in registros:
        r.setdefault("rito", "")
        r.setdefault("relator", "")
        r.setdefault("resultado", "")
        r.setdefault("fonte_pendente", False)
        r.setdefault("termo_urls", [])
    registros.sort(key=lambda r: (r["data"], r["id"]))
    return registros, resumo


def faixa(ano):
    ano = int(ano)
    return "ate-2009" if ano <= 2009 else ("2010-2018" if ano <= 2018 else "2019-2026")


def contagens(registros):
    """{tipo: {faixa: n}} e o total por tipo."""
    out = collections.defaultdict(collections.Counter)
    for r in registros:
        out[r["tipo"]][faixa(r["data"][:4])] += 1
    return {t: dict(c, total=sum(c.values())) for t, c in sorted(out.items())}


ENXUTO = ("id", "tipo", "classe", "processo", "data", "url", "plugin")


def enxuto(registros):
    return [{k: r.get(k, "") for k in ENXUTO} for r in registros]


def gravar_json(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho + ".parcial", "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(caminho + ".parcial", caminho)


def _ler(caminho):
    with open(caminho, "rb") as f:
        return jc.decodificar(f.read())


def carregar_listagens(pasta=LISTAGENS, dados_abertos=DADOS_ABERTOS):
    pas = ler_artigos(_ler(os.path.join(pasta, "pas.html")))
    colegiado = []
    pc = os.path.join(pasta, "colegiado")
    for nome in sorted(os.listdir(pc)):
        if nome.endswith(".html"):
            colegiado += ler_artigos(_ler(os.path.join(pc, nome)))
    tc_a = ler_tc_aceitos(_ler(os.path.join(pasta, "tc_aceitos.html")))
    tc_r = ler_tc_rejeitados(_ler(os.path.join(pasta, "tc_rejeitados.html")))
    antigas = ler_antigas(_ler(os.path.join(pasta, "antigas.html")))
    planilha = ler_planilha(os.path.join(pasta, "julgados-relator.xlsx"))
    abertos = ler_dados_abertos(dados_abertos) if os.path.exists(dados_abertos) else {}
    return pas, colegiado, tc_a, tc_r, antigas, planilha, abertos


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baixar", action="store_true", help="baixa as listagens que faltam")
    ap.add_argument("--refazer", action="store_true", help="baixa de novo mesmo as que existem")
    ap.add_argument("--listagens", default=LISTAGENS)
    a = ap.parse_args(argv)
    if a.baixar:
        baixar_listagens(a.listagens, refazer=a.refazer)
    fontes = carregar_listagens(a.listagens)
    print("listagens: PAS %d, Colegiado %d, TC aceitos %d, TC rejeitados %d, antigas %d, "
          "planilha %d, dados abertos %d" % tuple(len(x) for x in fontes))
    vazias = [n for n, x in zip(("PAS", "Colegiado", "TC aceitos", "TC rejeitados", "antigas"),
                                fontes) if not x]
    if vazias:  # a CVM devolve a página de busca vazia, com 200, quando a URL muda
        print("listagem sem itens: %s; confira a URL e rode com --refazer" % ", ".join(vazias),
              file=sys.stderr)
        return 1
    noticias = {}
    if os.path.isdir(jn.PASTA):
        fonte = jn.carregar()
        noticias = jn.indice(fonte)
        print("notícias de resultado %d (artigos faltando %d), extratos do SEI %d, NUPs %d"
              % (len(fonte["noticias"]), len(fonte["faltam"]), len(fonte["extratos"]),
                 len(noticias)))
    registros, resumo = montar(*fontes, noticias=noticias)
    gravar_json(SAIDA_COMPLETA, {"gerado_em": jc.hoje_sp(), "resumo": dict(resumo),
                                 "contagens": contagens(registros), "julgados": registros})
    gravar_json(SAIDA_ENXUTA, enxuto(registros))
    print(json.dumps({"contagens": contagens(registros), "resumo": dict(sorted(resumo.items()))},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
