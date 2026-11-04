#!/usr/bin/env python3
"""Detectores da Fase 4: comparam as fontes oficiais de hoje com o acervo no Git e listam o que
mudou, sem aplicar nada.

    python3 scripts/detectar.py [--fontes cvm,bcb,leis,b3,anbima,colegiado,pas,tc,crsfn]
        [--frequencia diaria|semanal|todas] [--desde AAAA-MM-DD] [--saida dados/auto/<data>]
        [--excluir-ids arquivo] [--execucao-id ID]
    python3 scripts/detectar.py --registrar-head   # grava tamanho e Last-Modified de referência

Grava <saida>/deteccao.json (com `execucao_id`: o recebido em --execucao-id, que o job confere,
ou um gerado) e imprime uma linha por fonte. Código de saída 0 com ou sem item
novo; 2 se alguma fonte falhou (as outras seguem).

Sem estado próprio (C2): a referência é o que está no Git (fontes/acervo*.json,
fontes/julgados-inventario.json, fontes/perimetro-camada4.json, fontes/leis.json,
fontes/decisoes.json, plugins/*/normas.json e o frontmatter). Cada fonte confere HTTP 200 e um
piso de 90% da contagem que o próprio acervo tem dela; abaixo do piso ou HTTP diferente de 200
na listagem, a fonte sai com status "falha" e nenhum item (C3, C19). Documento isolado que não
responde (HEAD de um consolidado, página de uma lei) conta como erro da fonte e sai da contagem
que vai contra o piso.

Classes (plano da Fase 4, seção 2): A resolução nova; B alteradora de norma sem histórico (ou
consolidado novo, com dados.consolidado_novo); C alteradora de norma com histórico; D revogada;
F ofício ou parecer novo; G lei com texto diferente; H norma do BCB alterada; H-novo norma nova
do BCB; I documento da autorregulação alterado; I-novo documento novo; J julgado novo.

Rede: um pedido por segundo no mínimo, User-Agent dos scripts, só os domínios de DOMINIOS, e
cache do dia em dados/auto/cache/ (ignorado pelo Git).
"""
import argparse
import collections
import datetime
import hashlib
import html as htmllib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)

import baixar  # noqa: E402
import inventario  # noqa: E402
import inventario_acervo as ia  # noqa: E402
import inventario_anbima as ian  # noqa: E402
import inventario_b3 as ib3  # noqa: E402
import inventario_bcb as ibcb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_inventario as ji  # noqa: E402
import julgados_noticias as jn  # noqa: E402
import leis as mleis  # noqa: E402
import perimetro_camada4 as pc  # noqa: E402
import texto_vigente as tv  # noqa: E402
from controle import sem_controle  # noqa: E402

RAIZ = os.path.normpath(os.path.join(AQUI, ".."))
FONTES = ("cvm", "bcb", "leis", "b3", "anbima", "colegiado", "pas", "tc", "crsfn")
DOMINIOS = tuple(baixar.DOMINIOS) + ("www.bcb.gov.br", "www.gov.br", "www.b3.com.br",
                                     "www.anbima.com.br", "sei.cvm.gov.br",
                                     "colaboragov.sei.gov.br")
PISO = 0.9
ALTERACAO = {"H", "I", "G"}  # alteração de documento que já está no acervo
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CRSFN_ANO = ("https://www.gov.br/fazenda/pt-br/composicao/orgaos/orgaos-colegiados/crsfn/servicos/"
             "busca-de-ata-pautas-distribuicoes-e-decisoes/acordaos-e-decisoes-monocraticas/%d")
CRSFN_PREFIXOS = {"19957": "CVM", "18600": "BCB", "11893": "COAF", "15414": "SUSEP",
                  "08224": "OUTRO"}  # fase-2d, inventário do CRSFN
PREFIXO_BCB = {"resolucao-cmn": "cmn-res", "resolucao-bcb": "bcb-res", "resolucao-conjunta": "bcb-resc",
               "circular": "bcb-circ", "carta-circular": "bcb-cc", "instrucao-normativa-bcb": "bcb-in"}
ALVO_BCB = {"resolucao": "cmn-res", "resolucao cmn": "cmn-res", "resolucao bcb": "bcb-res",
            "circular": "bcb-circ", "carta circular": "bcb-cc", "instrucao normativa bcb": "bcb-in"}
PERIMETRO = {"entra": "dentro", "revisar": "duvidosa", "fora": "fora", "alteradora": "alteradora"}
CATEGORIAS_CVM = {"resolucoes": "resolucoes", "instrucoes": "instrucoes",
                  "pareceres-orientacao": "pareceres", "oficios-circulares": "oficios_circulares"}
ALTERA_TAMBEM = re.compile(r"\b(altera|revoga|acrescenta|d[áa] nova reda[çc][ãa]o)", re.I)


# ---------------------------------------------------------------- rede

class Resposta:
    def __init__(self, status, dados=b"", cab=None, url="", erro=""):
        self.status, self.dados, self.cab, self.url, self.erro = status, dados or b"", cab or {}, url, erro

    def texto(self):
        return jc.decodificar(self.dados, self.cab)

    def json(self):
        return json.loads(self.dados.decode("utf-8"))


def permitido(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == "https" and p.hostname in DOMINIOS


class Rede(jc.Cliente):
    """Cliente dos detectores: o ritmo do julgados_comum.Cliente (1 pedido por segundo), a lista
    de domínios, o User-Agent dos scripts (o do inventario.py; os julgados passam o deles), uma
    nova tentativa em 3 s para erro de rede ou 5xx e cache do dia para GET e POST com 200."""

    def __init__(self, cache=None, intervalo=1.0, timeout=90):
        super().__init__(intervalo=intervalo, timeout=timeout)
        self.cache = cache

    def _arquivo(self, url, dados):
        if not self.cache:
            return None
        h = hashlib.sha1((url + "\n").encode("utf-8") + (dados or b"")).hexdigest()
        return os.path.join(self.cache, jc.hoje_sp(), h)

    def pedir(self, url, dados=None, metodo=None, ua=None):
        url = jc.absoluta(url)
        if not permitido(url):
            return Resposta(0, url=url, erro="domínio fora da lista: %s" % urllib.parse.urlsplit(url).hostname)
        arq = self._arquivo(url, dados) if metodo != "HEAD" else None
        if arq and os.path.exists(arq) and os.path.exists(arq + ".json"):
            with open(arq, "rb") as f, open(arq + ".json", encoding="utf-8") as g:
                return Resposta(200, f.read(), json.load(g), url)
        resp = None
        for tentativa in (1, 2):
            self._esperar()
            req = urllib.request.Request(url, data=dados, method=metodo,
                                         headers={"User-Agent": ua or inventario.USER_AGENT})
            if dados is not None:
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    corpo = r.read() if metodo != "HEAD" else b""
                    resp = Resposta(r.status, corpo, {k.lower(): v for k, v in r.headers.items()}, r.geturl())
            except urllib.error.HTTPError as e:
                cab = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
                resp = Resposta(e.code, b"", cab, url, "HTTP %d" % e.code)
            except Exception as e:  # noqa: BLE001 — rede: vira status 0 com o motivo
                resp = Resposta(0, b"", {}, url, "%s: %s" % (type(e).__name__, str(e)[:150]))
            if resp.status and resp.status < 500:
                break
            if tentativa == 1:
                time.sleep(3)
        if arq and resp.status == 200:
            os.makedirs(os.path.dirname(arq), exist_ok=True)
            with open(arq, "wb") as f:
                f.write(resp.dados)
            with open(arq + ".json", "w", encoding="utf-8") as g:
                json.dump(resp.cab, g)
        return resp

    def get(self, url, ua=None):
        return self.pedir(url, ua=ua)

    def post(self, url, campos, ua=None):
        return self.pedir(url, urllib.parse.urlencode(campos).encode("ascii"), ua=ua)

    def head(self, url, ua=None):
        return self.pedir(url, metodo="HEAD", ua=ua)


def navegador_chrome(pasta_perfil, rede=None):
    """Função url -> DOM (texto) lido pelo Chrome headless, ou None (sem Chrome, erro ou prazo)."""
    def ler(url):
        if not os.path.exists(CHROME) or not permitido(url):
            return None
        if rede is not None:
            rede._esperar()
        os.makedirs(pasta_perfil, exist_ok=True)
        perfil = tempfile.mkdtemp(dir=pasta_perfil)
        try:
            r = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-first-run",
                                "--user-data-dir=" + perfil, "--dump-dom",
                                "--virtual-time-budget=10000", url],
                               capture_output=True, timeout=90)
        except (OSError, subprocess.TimeoutExpired):
            return None
        finally:
            shutil.rmtree(perfil, ignore_errors=True)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 and r.stdout else None
    return ler


# ---------------------------------------------------------------- coleta

class Falha(Exception):
    pass


class Coleta:
    """Itens e contagens de uma fonte. `exigir` e `piso` levantam Falha."""

    def __init__(self, fonte):
        self.fonte, self.itens, self.etapas, self.erros = fonte, [], [], []
        self.contagem, self.piso_total, self.http, self.avisos = 0, 0, 200, []

    def item(self, classe, id_, norma_alvo=(), url="", data="", data_dou="", motivo="", dados=None):
        self.itens.append({"fonte": self.fonte, "classe": classe, "id": id_,
                           "norma_alvo": list(norma_alvo), "url": url or "", "data": data or "",
                           "data_dou": data_dou or "", "motivo": motivo, "dados": dados or {}})

    def exigir(self, resp, oque):
        if resp.status != 200:
            self.http = resp.status
            raise Falha("%s: HTTP %s%s" % (oque, resp.status or "sem resposta",
                                            " (%s)" % resp.erro if resp.erro and not resp.status else ""))
        return resp

    def erro(self, resp, url):
        self.erros.append("%s: HTTP %s%s" % (url, resp.status or "sem resposta",
                                             " (%s)" % resp.erro if resp.erro and not resp.status else ""))

    def aviso(self, texto):
        self.avisos.append(texto)

    def piso(self, etapa, contagem, base, oque):
        piso = math.ceil(base * PISO - 1e-9)  # 90% da base, arredondado para cima
        self.contagem += contagem
        self.piso_total += piso
        self.etapas.append({"etapa": etapa, "contagem": contagem, "piso": piso, "acervo": base})
        if contagem < piso:
            raise Falha("%s: %d, abaixo do piso de %d (90%% de %d no acervo)" % (oque, contagem, piso, base))


# ---------------------------------------------------------------- contexto (o que está no Git)

def _ler_json(caminho, padrao=None):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, obj):
    """Mesma formatação dos fontes/acervo*.json (indent=1, UTF-8, quebra de linha final)."""
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
    os.replace(tmp, caminho)


def frontmatter(caminho, linhas=60):
    """{chave: valor} das linhas simples do frontmatter."""
    out = {}
    with open(caminho, encoding="utf-8") as f:
        if f.readline().strip() != "---":
            return out
        for _ in range(linhas):
            ln = f.readline()
            if not ln or ln.strip() == "---":
                break
            m = re.match(r"^([a-z_]+):\s?(.*)$", ln.rstrip("\n"))
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def normas_com_historico(pasta_normas):
    """Ids das Resoluções e Instruções com histórico: historico_parcial false ou
    nivel_verificacao historico-conferido (no arquivo da norma ou no index.md da norma em partes)."""
    out = set()
    for sub in ("resolucoes", "instrucoes"):
        base = os.path.join(pasta_normas, "cvm", sub)
        if not os.path.isdir(base):
            continue
        for nome in sorted(os.listdir(base)):
            cam = os.path.join(base, nome)
            cam = os.path.join(cam, "index.md") if os.path.isdir(cam) else cam
            if not cam.endswith(".md") or not os.path.exists(cam):
                continue
            fm = frontmatter(cam)
            if fm.get("historico_parcial") == "false" or fm.get("nivel_verificacao") == "historico-conferido":
                out.add(fm.get("id"))
    out.discard(None)
    return out


def crsfn_publicados(pasta):
    """{url (fonte_original): id} dos acórdãos do CRSFN no plugin."""
    out = {}
    if not os.path.isdir(pasta):
        return out
    for ano in sorted(os.listdir(pasta)):
        d = os.path.join(pasta, ano)
        if not os.path.isdir(d):
            continue
        for nome in os.listdir(d):
            if nome.endswith(".md"):
                fm = frontmatter(os.path.join(d, nome))
                if fm.get("fonte_original"):
                    out[fm["fonte_original"]] = fm.get("id", "")
    return out


def bcb_id(tipo, numero):
    return "%s-%d" % (PREFIXO_BCB[tipo], int(numero))


class Contexto:
    """O acervo de referência e os meios de leitura. Os testes montam um com dados de fixture."""

    def __init__(self, hoje=None, desde=None, rede=None, navegador=None, classificador_crsfn=None,
                 acervo=None, publicados=(), com_historico=(), bcb=None, perimetro=(), leis=(),
                 pasta_leis="", anbima=None, b3=None, julgados=(), crsfn=None, decisoes=(),
                 pasta_noticias=None):
        self.hoje = hoje or jc.hoje_sp()
        self.desde = desde
        self.rede, self.navegador, self.classificador_crsfn = rede, navegador, classificador_crsfn
        self.acervo = acervo or {"lido_em": "", "resolucoes": [], "instrucoes": [], "pareceres": [],
                                 "oficios_circulares": []}
        self.publicados, self.com_historico = set(publicados), set(com_historico)
        self.bcb = bcb or {"lido_em": "", "contagem": [], "normas": []}
        self.perimetro, self.leis, self.pasta_leis = list(perimetro), list(leis), pasta_leis
        self.anbima = anbima or {"lido_em": "", "documentos": []}
        self.b3 = b3 or {"lido_em": "", "paginas": [], "documentos": []}
        self.julgados, self.crsfn = list(julgados), dict(crsfn or {})
        self.decisoes, self.pasta_noticias = list(decisoes), pasta_noticias
        self.decididos, self.decididos_url = self._decididos()
        self.decididos_par = collections.defaultdict(set)  # decisão com `classe`: vale só para o par
        for d in self.decisoes:
            if d.get("classe"):
                self.decididos_par[d["id"]].add(d["classe"])

    def decidido(self, it):
        """C15 pelo par (id, classe): decisão com `classe` vale só para ela; sem `classe` (e os
        registros do acervo), vale para todas menos as de alteração de norma já no acervo (H, I,
        G), para um "adiado" de hoje não esconder uma alteração futura."""
        if it["id"] in self.decididos_par:
            return it["classe"] in self.decididos_par[it["id"]]
        if it["classe"] in ALTERACAO:
            return False
        return it["id"] in self.decididos or bool(it["url"] and it["url"] in self.decididos_url)

    def _decididos(self):
        """Ids e URLs já decididos (C15): fontes/decisoes.json; registros do acervo da CVM fora do
        plugin (verbetes, revogadas, só-alteradoras); decisões "fora" e "alteradora" do perímetro
        da camada 4, fora do plugin."""
        ids = {d["id"] for d in self.decisoes if not d.get("classe")}
        urls = {d["url"] for d in self.decisoes if d.get("url") and not d.get("classe")}
        a = self.acervo
        reg = (["cvm-res-%d" % int(r["numero"]) for r in a.get("resolucoes", [])]
               + ["cvm-instr-%d" % int(r["numero"]) for r in a.get("instrucoes", [])]
               + ["cvm-po-%d" % int(r["numero"]) for r in a.get("pareceres", [])]
               + [o["id"] for o in a.get("oficios_circulares", [])])
        reg += [bcb_id(p["tipo"], p["numero"]) for p in self.perimetro if p.get("decisao") in ("fora", "alteradora")]
        ids |= {i for i in reg if i not in self.publicados}
        return ids, urls

    @classmethod
    def do_repo(cls, raiz=RAIZ, **kw):
        n = os.path.join(raiz, "plugins", "normas", "normas")
        publicados = {x["id"] for x in _ler_json(os.path.join(n, "normas.json"), [])}
        crsfn = crsfn_publicados(os.path.join(raiz, "plugins", "julgados-tc-crsfn", "julgados", "crsfn"))
        f = lambda nome, padrao=None: _ler_json(os.path.join(raiz, "fontes", nome), padrao)  # noqa: E731
        return cls(acervo=f("acervo.json"), publicados=publicados,
                   com_historico=normas_com_historico(n), bcb=f("acervo-bcb.json"),
                   perimetro=f("perimetro-camada4.json", []), leis=f("leis.json", []),
                   pasta_leis=os.path.join(n, "leis"), anbima=f("acervo-anbima.json"),
                   b3=f("acervo-b3.json"), julgados=f("julgados-inventario.json", []), crsfn=crsfn,
                   decisoes=f("decisoes.json", []), pasta_noticias=jn.PASTA, **kw)


# ---------------------------------------------------------------- utilidades

def data_lm(valor):
    return tv._data_last_modified(valor) if valor else None


def mudou_head(cab, registrado, lido_em):
    """(mudou?, motivo) do HEAD contra o registrado ({bytes, last_modified}). Com tamanho dos
    dois lados, vale só o tamanho: o Last-Modified da ANBIMA varia entre servidores para o mesmo
    arquivo (visto em 2026-11-04). Sem tamanho, a data do Last-Modified (interpretada, não a
    string) posterior à registrada; sem registro, a data do Last-Modified depois da leitura do
    acervo."""
    tam = int(cab.get("content-length") or 0)
    lm = cab.get("last-modified") or ""
    registrado = registrado or {}
    if registrado.get("bytes") and tam:
        if tam != registrado["bytes"]:
            return True, "tamanho %d -> %d" % (registrado["bytes"], tam)
        return False, ""
    d, d_reg = data_lm(lm), data_lm(registrado.get("last_modified"))
    if d_reg:
        if d and d > d_reg:
            return True, "Last-Modified %s -> %s" % (registrado["last_modified"], lm)
        return False, ""
    if d and lido_em and d > lido_em:
        return True, "Last-Modified %s, depois da leitura do acervo (%s)" % (lm, lido_em)
    return False, ""


def head_com_tamanho(rede, url, buscar=True):
    """HEAD; sem Content-Length (a B3 e os .htm da CVM não mandam) e com `buscar`, o tamanho
    vem de um GET (cache do dia) e entra no cabeçalho devolvido."""
    r = rede.head(url)
    if r.status == 200 and not r.cab.get("content-length") and buscar:
        g = rede.get(url)
        if g.status == 200:
            r.cab = dict(r.cab, **{"content-length": str(len(g.dados)), "x-tamanho-por": "GET"})
    return r


def _id_citada(c):
    tipo, n = c.split(" ", 1)
    return ("cvm-res-%s" if tipo == "Resolução" else "cvm-instr-%s") % int(n)


def _br(d):
    return d.strftime("%d/%m/%Y")


def semestres(hoje):
    """[(início, fim)] do semestre anterior e do corrente (datas)."""
    d = datetime.date.fromisoformat(hoje)
    if d.month <= 6:
        return [(datetime.date(d.year - 1, 7, 1), datetime.date(d.year - 1, 12, 31)),
                (datetime.date(d.year, 1, 1), datetime.date(d.year, 6, 30))]
    return [(datetime.date(d.year, 1, 1), datetime.date(d.year, 6, 30)),
            (datetime.date(d.year, 7, 1), datetime.date(d.year, 12, 31))]


# ---------------------------------------------------------------- CVM

def cvm_busca(ctx, col):
    """Busca por tipo (diária): A, B/C, D e F."""
    busca = {}
    for cat in ia.CATEGORIAS:
        r = col.exigir(ctx.rede.get(ia.BUSCA % cat), "busca da CVM (%s)" % cat)
        busca[cat] = ia.itens_da_busca(r.texto())
        col.piso(cat, len(busca[cat]), len(ctx.acervo[CATEGORIAS_CVM[cat]]), "busca da CVM (%s)" % cat)
    _cvm_resolucoes(ctx, col, busca["resolucoes"])
    _cvm_revogadas(ctx, col, busca["instrucoes"], "cvm-instr-%d", "Instrução CVM %d")
    _cvm_revogadas(ctx, col, busca["pareceres-orientacao"], "cvm-po-%d", "Parecer de Orientação CVM %d")
    _cvm_pareceres(ctx, col, busca["pareceres-orientacao"])
    _cvm_oficios(ctx, col, busca["oficios-circulares"])


def _alteracao(ctx, col, id_, alvos, url, data, dou, ementa, n):
    for a in alvos:
        classe = "C" if a in ctx.com_historico else "B"
        col.item(classe, id_, [a], url, data, dou,
                 "Resolução CVM %d altera %s (%s histórico)" % (n, a, "com" if classe == "C" else "sem"),
                 {"ementa": ementa})


def _cvm_resolucoes(ctx, col, itens):
    conhecidas = {int(r["numero"]) for r in ctx.acervo["resolucoes"]}
    for it in itens:
        n = ia._numero(it["titulo"])
        if n is None:
            continue
        id_ = "cvm-res-%d" % n
        revogada = "(Revogada)" in it["titulo"]
        if n in conhecidas:
            if revogada and id_ in ctx.publicados:
                col.item("D", id_, [id_], it["url"], it["data"], "",
                         "Resolução CVM %d aparece como (Revogada) na busca" % n, {"titulo": it["titulo"]})
            continue
        if revogada:
            continue
        html = col.exigir(ctx.rede.get(it["url"]), "página da Resolução CVM %d" % n).texto()
        pag, det = inventario.extrair_pagina(html), ia.detalhes_da_pagina(html)
        ementa = pag["ementa"] or det["ementa"] or it["descricao"]
        dou = pag["dou"] or det["dou"] or ""
        data = pag["data"] or it["data"]
        citadas = [_id_citada(c) for c in ia.citadas(ementa)]
        alvos = [a for a in dict.fromkeys(citadas) if a in ctx.publicados]
        if ia.SO_ALTERA.match(ementa):
            if not citadas:
                col.item("B", id_, [], it["url"], data, dou,
                         "Resolução CVM %d só alteradora, sem norma-alvo legível na ementa" % n,
                         {"ementa": ementa})
            _alteracao(ctx, col, id_, alvos, it["url"], data, dou, ementa, n)
            continue
        col.item("A", id_, [id_], it["url"], data, dou, "Resolução CVM %d nova" % n,
                 {"ementa": ementa, "titulo": it["titulo"], "citadas": citadas})
        if ALTERA_TAMBEM.search(ementa):
            _alteracao(ctx, col, id_, alvos, it["url"], data, dou, ementa, n)


def _cvm_revogadas(ctx, col, itens, padrao, nome):
    for it in itens:
        n = ia._numero(it["titulo"])
        if n is None or "(Revogad" not in it["titulo"]:
            continue
        id_ = padrao % n
        if id_ in ctx.publicados:
            col.item("D", id_, [id_], it["url"], it["data"], "", "%s aparece como revogada na busca" % (nome % n),
                     {"titulo": it["titulo"]})


def _formato(url):
    m = re.search(r"\.([a-z0-9]{2,5})$", (url or "").split("?")[0].lower())
    return m.group(1) if m else ""


def _cvm_pareceres(ctx, col, itens):
    conhecidos = {int(p["numero"]) for p in ctx.acervo["pareceres"]}
    for it in itens:
        n = ia._numero(it["titulo"])
        if n is None or n in conhecidos or "(Revogad" in it["titulo"]:
            continue
        html = col.exigir(ctx.rede.get(it["url"]), "página do Parecer de Orientação CVM %d" % n).texto()
        det = ia.detalhes_da_pagina(html)
        ato = det["arquivos"].get("ato") or det["arquivos"].get("consolidado") or {}
        ext = next((e for e in ("pdf", "docx", "doc", "htm", "html") if e in ato), "")
        id_ = "cvm-po-%d" % n
        col.item("F", id_, [id_], it["url"], it["data"], det["dou"] or "",
                 "Parecer de Orientação CVM %d novo" % n,
                 {"formato": ext, "url_arquivo": ato.get(ext, ""), "titulo": it["titulo"],
                  "ementa": det["ementa"] or it["descricao"]})


def _cvm_oficios(ctx, col, itens):
    conhecidos = {o["url_pagina"] for o in ctx.acervo["oficios_circulares"]}
    usados = {o["id"] for o in ctx.acervo["oficios_circulares"]}
    for it in itens:
        if it["url"] in conhecidos or "/legislacao/oficios-circulares/" not in it["url"]:
            continue
        r = col.exigir(ctx.rede.get(it["url"]), "página do ofício %s" % it["titulo"])
        of = ia.oficio(it, r.texto())
        pasta, slug = of["superintendencia"], of["slug"]
        id_ = "cvm-" + slug
        if id_ in usados:
            cand = "%s-%s" % (id_, ia.normalizar_slug(pasta or "sem-pasta"))
            id_, k = cand, 2
            while id_ in usados:
                id_, k = "%s-%d" % (cand, k), k + 1
        usados.add(id_)
        col.item("F", id_, [id_], it["url"], it["data"], "", "Ofício-Circular novo: %s" % it["titulo"],
                 {"formato": _formato(of["url_pdf"]), "url_arquivo": of["url_pdf"],
                  "url_arquivo_origem": of["url_pdf_origem"], "titulo": it["titulo"],
                  "superintendencia": pasta, "ementa": of["ementa"], "cita": of["cita"]})


def cvm_consolidados(ctx, col):
    """HEAD dos consolidados das resoluções do plugin (semanal): B com consolidado_novo."""
    alvos = []
    for r in ctx.acervo["resolucoes"]:
        id_ = "cvm-res-%d" % int(r["numero"])
        cons = r.get("consolidado") or {}
        url = cons.get("docx") or cons.get("htm")
        if id_ in ctx.publicados and url:
            alvos.append((id_, r, url))
    ok = 0
    for id_, r, url in alvos:
        resp = head_com_tamanho(ctx.rede, url, bool((r.get("consolidado_head") or {}).get("bytes")))
        if resp.status != 200:
            col.erro(resp, url)
            continue
        ok += 1
        mudou, motivo = mudou_head(resp.cab, r.get("consolidado_head"), ctx.acervo.get("lido_em"))
        if mudou:
            col.item("B", id_, [id_], url, data_lm(resp.cab.get("last-modified")) or "", "",
                     "consolidado da CVM mudou: %s" % motivo,
                     {"consolidado_novo": True, "com_historico": id_ in ctx.com_historico,
                      "formato": _formato(url), "bytes": int(resp.cab.get("content-length") or 0),
                      "last_modified": resp.cab.get("last-modified", ""),
                      "registrado": r.get("consolidado_head") or {}})
    col.piso("consolidados", ok, len(alvos), "HEAD dos consolidados da CVM com resposta 200")


# ---------------------------------------------------------------- CMN e BCB

def _contagem_bcb(bcb):
    base = collections.Counter()
    for linha in bcb.get("contagem", []):
        tipo, _sit, n = linha.split(" ")
        base[tipo] += int(n)
    return base


def _alvo_bcb(alvo):
    m = re.match(r"^(.*) ([\d.]+)$", alvo)
    if not m or m.group(1) not in ALVO_BCB:
        return None
    return "%s-%d" % (ALVO_BCB[m.group(1)], int(m.group(2).replace(".", "")))


def bcb_busca(ctx, col, linhas=100):
    """Busca por data (diária): H-novo para norma que não está no acervo da camada 4."""
    desde = ctx.desde or ctx.bcb.get("lido_em") or ctx.hoje
    conhecidas = {(n["tipo"], int(n["numero"])) for n in ctx.bcb["normas"]}
    conhecidas |= {(p["tipo"], int(p["numero"])) for p in ctx.perimetro}
    total, novas = collections.Counter(), []
    for tipo_bcb, tipo in ibcb.TIPOS.items():
        inicio, antigo, total_tipo = 0, False, 0
        while True:
            p = {"querytext": "ContentType:normativo AND contentSource:normativos", "rowlimit": linhas,
                 "startrow": inicio, "sortlist": "Data1OWSDATE:descending",
                 "refinementfilters": 'TipodoNormativoOWSCHCS:equals("%s")' % tipo_bcb}
            r = col.exigir(ctx.rede.get(ibcb.BUSCA + urllib.parse.urlencode(p)), "busca do BCB (%s)" % tipo_bcb)
            try:
                d = r.json()
            except ValueError:
                raise Falha("busca do BCB (%s): resposta não é JSON" % tipo_bcb)
            if inicio == 0:
                total_tipo = int(d.get("TotalRows") or 0)
                total[tipo] += total_tipo
            rows = d.get("Rows") or []
            for row in rows:
                it = ibcb.item_da_busca(row)
                if it["data"] and it["data"] < desde:
                    antigo = True
                    break
                if (it["tipo"], it["numero"]) not in conhecidas:
                    novas.append(it)
                    conhecidas.add((it["tipo"], it["numero"]))
            inicio += len(rows)
            if antigo or not rows or inicio >= int(d.get("TotalRows") or 0):
                break
        if not antigo and inicio < total_tipo:  # TotalRows sem as linhas: a busca não devolveu a lista
            raise Falha("busca do BCB (%s): %d linha(s) lida(s) de %d no TotalRows, sem chegar a %s"
                        % (tipo_bcb, inicio, total_tipo, desde))
    for tipo, base in sorted(_contagem_bcb(ctx.bcb).items()):
        col.piso(tipo, total[tipo], base, "busca do BCB (%s, todas as situações)" % tipo)
    for it in novas:
        dec, temas, fora, alvos = pc.classificar(it)
        ids_alvo = [a for a in (_alvo_bcb(x) for x in alvos) if a]
        id_ = bcb_id(it["tipo"], it["numero"])
        col.item("H-novo", id_, [a for a in ids_alvo if a in ctx.publicados], it["url_pagina"], it["data"], "",
                 "%s %d nova no BCB (perímetro: %s)" % (it["tipo_bcb"], it["numero"], PERIMETRO[dec]),
                 {"perimetro": PERIMETRO[dec], "tipo_bcb": it["tipo_bcb"], "assunto": it["assunto"],
                  "situacao": it["situacao"], "temas": temas, "exclusao": fora, "alvos": ids_alvo})


def _versao(v):
    if v in (None, "", "None"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return str(v)


def _documentos(v):
    return {p.strip() for p in str(v or "").split(";") if "." in p}


def _atualizacoes(v):
    if isinstance(v, list):
        return {a.strip() for a in v if a.strip()}
    return {a.strip() for a in str(v or "").split(";#") if a.strip()}


def bcb_128(ctx, col):
    """As normas do BCB no plugin, uma a uma pela API (semanal): H e D."""
    alvos = [n for n in ctx.bcb["normas"] if n["tipo"] in PREFIXO_BCB and bcb_id(n["tipo"], n["numero"]) in ctx.publicados]
    ok = 0
    for n in alvos:
        id_ = bcb_id(n["tipo"], n["numero"])
        url = ibcb.NORMA + urllib.parse.urlencode({"p1": n["tipo_bcb"], "p2": n["numero"]})
        r = ctx.rede.get(url)
        if r.status != 200:
            col.erro(r, url)
            continue
        try:
            c = (r.json().get("conteudo") or [None])[0]
        except ValueError:
            c = None
        if not c:
            col.erros.append("%s: resposta sem conteúdo" % url)
            continue
        ok += 1
        if ibcb._bool(c.get("Revogado")) or ibcb._bool(c.get("Cancelado")):
            sit = "cancelada" if ibcb._bool(c.get("Cancelado")) else "revogada"
            col.item("D", id_, [id_], n["url_pagina"], "", "", "%s %s %s na API do BCB" % (n["tipo_bcb"], n["numero"], sit),
                     {"situacao": sit})
            continue
        dif, dados = [], {}
        va, vr = _versao(c.get("VersaoNormativo")), _versao(n.get("versao"))
        if va != vr:
            dif.append("versão %s -> %s" % (vr, va))
            dados["versao"] = va
        da, dr = _documentos(c.get("Documentos")), _documentos(n.get("documentos"))
        if da != dr:
            dif.append("documentos +%d -%d" % (len(da - dr), len(dr - da)))
            dados["documentos_novos"] = sorted(da - dr)
            dados["documentos_saidos"] = sorted(dr - da)
        if "atualizacoes" in n:
            aa, ar = _atualizacoes(c.get("Atualizacoes")), _atualizacoes(n["atualizacoes"])
            if aa != ar:
                dif.append("Atualizacoes +%d -%d" % (len(aa - ar), len(ar - aa)))
                dados["atualizacoes_novas"] = sorted(aa - ar)
        if dif:
            col.item("H", id_, [id_], n["url_pagina"], "", "", "; ".join(dif), dados)
    col.piso("normas-bcb", ok, len(alvos), "API do BCB para as normas do plugin com resposta 200")


# ---------------------------------------------------------------- leis

_VOLATIL = re.compile(r"(?m)^(sha256_fonte|baixado_em|verificado_em):.*$")
_DATA_BASE = re.compile(r"data-base \d{4}-\d{2}-\d{2}")


def normalizar_lei(texto):
    """Texto do arquivo da lei sem o que muda a cada leitura (data-base, datas de leitura e hash
    do HTML, que muda com o leiaute)."""
    return _DATA_BASE.sub("data-base AAAA-MM-DD", _VOLATIL.sub(r"\1:", texto))


def _secoes(texto):
    out, chave, linhas, vistos = collections.OrderedDict(), "preâmbulo", [], collections.Counter()
    for ln in texto.split("\n") + ["## Art. FIM"]:
        m = mleis._HEADING.match(ln)
        if m:
            out[chave] = "\n".join(linhas)
            vistos[m.group(1)] += 1
            chave = "Art. %s" % m.group(1) + (" (%d)" % vistos[m.group(1)] if vistos[m.group(1)] > 1 else "")
            linhas = []
        else:
            linhas.append(ln)
    return out


def artigos_diferentes(antes, depois):
    a, b = _secoes(antes), _secoes(depois)
    return [k for k in list(dict.fromkeys(list(a) + list(b))) if a.get(k) != b.get(k)]


def _ler(caminho):
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as f:
        return f.read()


def leis(ctx, col):
    """Compilado do Planalto das leis do acervo (semanal): G com os artigos que mudaram. Lê a
    página de que o arquivo saiu (fonte_consolidada) e, se ela não responder, as de leis.json."""
    ok = 0
    for item in ctx.leis:
        nome = mleis.TIPOS_LEI[mleis._tipo(item)][1] % item["numero"]
        principal = os.path.join(ctx.pasta_leis, nome + ".md")
        if not os.path.exists(principal):
            principal = os.path.join(ctx.pasta_leis, nome, "index.md")
        fm = frontmatter(principal) if os.path.exists(principal) else {}
        urls = list(dict.fromkeys(([fm["fonte_consolidada"]] if fm.get("fonte_consolidada") else [])
                                  + [mleis.PLANALTO + p for p in item["planalto"]]))
        html, usada, ultima = None, "", None
        for url in urls:
            r = ctx.rede.get(url)
            if r.status == 200:
                html, usada = r.dados, url
                break
            ultima = r
        if html is None:
            col.erro(ultima, urls[0])
            continue
        ok += 1
        arquivos, artigos = [], []
        for rel, conteudo in sorted(mleis.montar_lei(dict(item, url=usada), html).items()):
            atual = _ler(os.path.join(ctx.pasta_leis, *rel.split("/")))
            novo = normalizar_lei(sem_controle(conteudo))
            if atual is None:
                arquivos.append(rel)
                artigos.append("%s (arquivo novo)" % rel)
            elif normalizar_lei(atual) != novo:
                arquivos.append(rel)
                artigos += artigos_diferentes(normalizar_lei(atual), novo)
        if arquivos:
            col.item("G", item["id"], [item["id"]], usada, item.get("data", ""), "",
                     "compilado do Planalto mudou em %d trecho(s)" % len(artigos),
                     {"artigos": list(dict.fromkeys(artigos)), "arquivos": arquivos})
    col.piso("leis", ok, len(ctx.leis), "compilados do Planalto com resposta 200")


# ---------------------------------------------------------------- autorregulação (B3 e ANBIMA)

def _ids_camada5(anbima, b3):
    return {x["fontes"]["ato"]["pdf"]: x["id"] for x in tv.itens_camada5(anbima, b3)}


def _heads(ctx, col, docs, lido_em, etapa, oque, campo=None):
    """HEAD de cada documento vigente: I se tamanho ou Last-Modified mudou."""
    ok = 0
    for id_, d in docs:
        r = head_com_tamanho(ctx.rede, d["url"], bool(d.get("bytes")))
        if r.status != 200:
            col.erro(r, d["url"])
            continue
        ok += 1
        reg = {"bytes": d.get("bytes") or 0, "last_modified": d.get("last_modified") or ""}
        mudou, motivo = mudou_head(r.cab, reg, lido_em)
        if mudou:
            col.item("I", id_, [id_], d["url"], data_lm(r.cab.get("last-modified")) or "", "",
                     "%s mudou: %s" % (oque, motivo),
                     {"arquivo": d.get("arquivo", ""), "bytes": int(r.cab.get("content-length") or 0),
                      "last_modified": r.cab.get("last-modified", ""), "registrado": reg})
    col.piso(etapa, ok, len(docs), "HEAD dos documentos vigentes (%s) com resposta 200" % oque)


def b3(ctx, col):
    paginas = {ib3.CATEGORIAS % n: n for n in ib3.NOMES}
    vistos, lidas, docs, fila = set(), 0, {}, list(paginas)
    while fila:
        url = fila.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        r = ctx.rede.get(url)
        if r.status != 200:
            if url in (ib3.CATEGORIAS % n for n in ib3.NOMES):
                col.exigir(r, "página da B3 %s" % url)
            col.erro(r, url)
            continue
        lidas += 1
        cat = paginas.get(url)
        for href, rot in ib3.links(r.texto()):
            if "estrutura-normativa/estrutura-normativa/" in href and not ib3.ARQ.search(href):
                sub = urllib.parse.urljoin(url, href)
                sub = ib3.RAIZ + "estrutura-normativa/" + sub.split("estrutura-normativa/estrutura-normativa/", 1)[1]
                if sub not in vistos:
                    paginas.setdefault(sub, cat)
                    fila.append(sub)
                continue
            if not ib3.ARQ.search(href.split("?", 1)[0]):
                continue
            u = ib3.url_arquivo(href)
            d = docs.setdefault(u, {"url": u, "arquivo": urllib.parse.unquote(u.rsplit("/", 1)[-1]),
                                    "rotulos": [], "paginas": []})
            if rot and rot not in d["rotulos"]:
                d["rotulos"].append(rot)
            if url not in d["paginas"]:
                d["paginas"].append(url)
    col.piso("paginas", lidas, len(ctx.b3.get("paginas", [])), "páginas da B3 lidas")
    col.piso("documentos", len(docs), len(ctx.b3["documentos"]), "documentos listados nas páginas da B3")
    conhecidos = {d["url"] for d in ctx.b3["documentos"]}
    entram = [d for d in ctx.b3["documentos"] if d.get("entra") is True]
    ids = _ids_camada5({"documentos": []}, ctx.b3)
    por_chave = {d.get("chave") or ib3.chave_versao(d["arquivo"]): d for d in entram}
    novos = []
    for u, d in docs.items():
        if u in conhecidos:
            continue
        txt = " ".join(d["rotulos"]) + " " + d["arquivo"]
        d.update({"http": 200, "bytes": 0, "last_modified": None,
                  "marcas": "com" if re.search(r"com\s*marca", txt, re.I) else (
                      "sem" if re.search(r"sem\s*marca", txt, re.I) else "n/a"),
                  "data_nome": ib3.data_do_nome(d["arquivo"]),
                  "formato": d["arquivo"].rsplit(".", 1)[-1].lower(), "categoria": paginas.get(d["paginas"][0])})
        d["entra"], d["motivo"] = ib3.perimetro(d)
        if not d["entra"]:
            continue
        d["titulo"], d["chave"] = ib3.titulo(d), ib3.chave_versao(d["arquivo"])
        antigo = por_chave.get(d["chave"])
        if antigo and ids.get(antigo["url"]):
            id_ = ids[antigo["url"]]
            col.item("I", id_, [id_], u, d["data_nome"] or "", "", "versão nova na B3: %s" % d["arquivo"],
                     {"arquivo": d["arquivo"], "titulo": d["titulo"], "anterior": antigo["url"],
                      "categoria": d["categoria"]})
        else:
            novos.append(d)
    if novos:
        ids_novos = _ids_camada5({"documentos": []}, dict(ctx.b3, documentos=entram + novos))
        for d in novos:
            col.item("I-novo", ids_novos[d["url"]], [], d["url"], d["data_nome"] or "", "",
                     "documento novo no perímetro da B3: %s" % d["titulo"],
                     {"arquivo": d["arquivo"], "titulo": d["titulo"], "categoria": d["categoria"],
                      "motivo_perimetro": d["motivo"]})
    _heads(ctx, col, [(ids[d["url"]], d) for d in entram if d["url"] in ids], ctx.b3.get("lido_em"),
           "head", "documento da B3")


def links_anbima(html):
    """[(rótulo, url)] dos links para data/files/ (como inventario_anbima.etica)."""
    out = []
    for href, x in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        if "data/files/" in href:
            rot = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
            if rot and not re.match(r"^\d{2}/\d{2}/\d{4}$", rot):
                out.append((rot, ian.BASE + "data/files/" + htmllib.unescape(href).split("data/files/", 1)[1]))
    return out


def anbima(ctx, col):
    """Páginas de código pelo Chrome headless (parte montada por JavaScript), com reserva no HTML
    estático; a de Ética, estática."""
    paginas = sorted({p for d in ctx.anbima["documentos"] for p in d.get("paginas", [])})
    docs, lidas, via = {}, 0, collections.Counter()
    ordem = {"vigente": 0, "anterior": 1, "fora": 2}
    for pag in paginas:
        achados = []
        if pag != ian.ETICA and ctx.navegador:
            for _ in range(2):  # o Chrome às vezes devolve a página antes de montar a lista
                dom = ctx.navegador(pag)
                achados = links_anbima(dom) if dom else []
                if achados:
                    break
            if achados:
                via["chrome"] += 1
        if not achados:
            r = ctx.rede.get(pag)
            if r.status != 200:
                col.erro(r, pag)
                continue
            achados = links_anbima(r.texto())
            via["estatico"] += 1
        lidas += 1
        for rot, url in achados:
            sit, desde, limpo = ian.classificar(rot)
            d = docs.setdefault(url, {"titulo": limpo, "url": url,
                                      "arquivo": urllib.parse.unquote(url.rsplit("/", 1)[-1]),
                                      "situacao": sit, "vigente_desde": desde, "paginas": []})
            if pag not in d["paginas"]:
                d["paginas"].append(pag)
            if ordem[sit] < ordem[d["situacao"]]:
                d.update(titulo=limpo, situacao=sit, vigente_desde=desde)
    col.etapas.append({"etapa": "leitura", "chrome": via["chrome"], "estatico": via["estatico"]})
    try:
        col.piso("paginas", lidas, len(paginas), "páginas da ANBIMA lidas")
        col.piso("documentos", len(docs), len(ctx.anbima["documentos"]), "documentos listados nas páginas da ANBIMA")
    except Falha as e:
        if not via["chrome"]:
            raise Falha("%s; sem leitura por script; conferência mensal no navegador" % e)
        raise
    conhecidos = {d["url"] for d in ctx.anbima["documentos"]}
    vigentes = [d for d in ctx.anbima["documentos"] if d.get("situacao") == "vigente"]
    ids = _ids_camada5(ctx.anbima, {"documentos": []})
    por_titulo = {tv.titulo_anbima(d["titulo"]).lower(): d for d in vigentes}
    novos = []
    for url, d in docs.items():
        if url in conhecidos:
            continue
        if d["arquivo"] in ian.SUBSTITUIDOS:
            d["situacao"] = "anterior"
        if d["situacao"] != "vigente":
            continue
        d["tipo"], d["formato"] = ian.tipo_doc(d["titulo"]), d["arquivo"].rsplit(".", 1)[-1].lower()
        antigo = por_titulo.get(tv.titulo_anbima(d["titulo"]).lower())
        if antigo and ids.get(antigo["url"]):
            id_ = ids[antigo["url"]]
            col.item("I", id_, [id_], url, d["vigente_desde"] or "", "", "versão nova na ANBIMA: %s" % d["titulo"],
                     {"arquivo": d["arquivo"], "titulo": d["titulo"], "anterior": antigo["url"]})
        else:
            novos.append(d)
    if novos:
        ids_novos = _ids_camada5(dict(ctx.anbima, documentos=vigentes + novos), {"documentos": []})
        for d in novos:
            col.item("I-novo", ids_novos[d["url"]], [], d["url"], d["vigente_desde"] or "", "",
                     "documento vigente novo na ANBIMA: %s" % d["titulo"],
                     {"arquivo": d["arquivo"], "titulo": d["titulo"], "tipo": d["tipo"]})
    _heads(ctx, col, [(ids[d["url"]], d) for d in vigentes if d["url"] in ids], ctx.anbima.get("lido_em"),
           "head", "documento da ANBIMA")


# ---------------------------------------------------------------- julgados

def _plugin(tipo, data):
    return jc.plugin_do_julgado(tipo, (data or "0000")[:4]) if data else jc.plugin_do_julgado(tipo, datetime.date.today().year)


def colegiado(ctx, col):
    """Listagem de decisões do Colegiado no semestre anterior e no corrente (diária)."""
    janelas = semestres(ctx.hoje)
    ini, fim = janelas[0][0].isoformat(), janelas[-1][1].isoformat()
    conhecidas = {jc.caminho_url(r["url"]) for r in ctx.julgados if r.get("url")}
    usados = {r["id"] for r in ctx.julgados}  # id decidido não ganha sufixo: sai no filtro de decididos
    base = sum(1 for r in ctx.julgados if "/decisoes/" in (r.get("url") or "")
               and r["tipo"] in ("decisao-colegiado", "termo-compromisso") and ini <= (r.get("data") or "") <= fim)
    itens = []
    for a, b in janelas:
        r = col.exigir(ctx.rede.get(ji.URL_COLEGIADO.format(ini=_br(a), fim=_br(b)), ua=jc.USER_AGENT),
                       "listagem do Colegiado de %s a %s" % (a, b))
        itens += ji.ler_artigos(r.texto())
    vistos = []
    for it in sorted(itens, key=lambda x: (x["data"] or "", x["url"])):
        chave = jc.caminho_url(it["url"])
        if chave in vistos:
            continue
        vistos.append(chave)
    col.piso("colegiado", len(vistos), base, "decisões listadas pelo Colegiado nos dois semestres")
    feitos = set()
    for it in sorted(itens, key=lambda x: (x["data"] or "", x["url"])):
        chave = jc.caminho_url(it["url"])
        if chave in conhecidas or chave in feitos:
            continue
        feitos.add(chave)
        try:
            data_url, _slug, reuniao = jc.slug_colegiado(chave)
            id_ = ji._unico(jc.id_colegiado(chave), usados, "-r%d" % reuniao if reuniao > 1 else None)
        except ValueError:
            col.erros.append("%s: URL fora do padrão do Colegiado" % chave)
            continue
        usados.add(id_)
        data = it["data"] or "%s-%s-%s" % (data_url[:4], data_url[4:6], data_url[6:])
        bruta = ji.classificar(it["titulo"])
        tipo = "termo-compromisso" if bruta == "tc_proposta" else "decisao-colegiado"
        url = jc.absoluta(chave)
        col.item("J", id_, [], url, data, "", "%s nova na listagem do Colegiado" % tipo,
                 {"tipo": tipo, "classe": "" if bruta == "tc_proposta" else ji.CLASSE_CONTRATO[bruta],
                  "processo": jc.processo_publicado(it["titulo"]), "url": url, "data": data,
                  "plugin": _plugin(tipo, data)})


def tc(ctx, col):
    """Tabelas de TCs celebrados e rejeitados (semanal)."""
    campos = {"searchPage": "1", "lastName": "", "itensPagina": "2000"}
    ra = col.exigir(ctx.rede.post(ji.URL_TC, campos, ua=jc.USER_AGENT), "tabela de TCs celebrados")
    rr = col.exigir(ctx.rede.post(ji.URL_TC_REJ, campos, ua=jc.USER_AGENT), "tabela de TCs rejeitados")
    linhas = collections.OrderedDict()
    for ln in ji.ler_tc_aceitos(ra.texto()) + ji.ler_tc_rejeitados(rr.texto()):
        chave = (ln["proc"] or ln["processo"], ln["data"], ln["resultado"],
                 tuple(ln["decisao_urls"]) if not ln["proc"] else ())
        if chave in linhas:
            base = linhas[chave]
            base["termo_urls"] += [u for u in ln["termo_urls"] if u not in base["termo_urls"]]
            base["decisao_urls"] += [u for u in ln["decisao_urls"] if u not in base["decisao_urls"]]
            continue
        linhas[chave] = dict(ln, termo_urls=list(ln["termo_urls"]), decisao_urls=list(ln["decisao_urls"]))
    desde = "2019-01-01"
    contagem = len({(ln["proc"] or ln["processo"], ln["data"]) for ln in linhas.values() if (ln["data"] or "") >= desde})
    base = sum(1 for r in ctx.julgados if r["tipo"] == "termo-compromisso" and (r.get("data") or "") >= desde)
    col.piso("tc", contagem, base, "TCs (processo e data) desde 2019 nas tabelas")
    caminhos = {jc.caminho_url(r["url"]) for r in ctx.julgados if r.get("url")}
    urls = {r["url"] for r in ctx.julgados if r.get("url")}
    ids = {r["id"] for r in ctx.julgados} | ctx.decididos
    proc_data = {(jc.normalizar_processo(r.get("processo") or ""), r.get("data")) for r in ctx.julgados}
    for ln in linhas.values():
        if not ln["proc"] or not ln["data"] or ln["data"] > ctx.hoje:
            continue
        if any(jc.caminho_url(u) in caminhos for u in ln["decisao_urls"]):
            continue
        if any(jc.absoluta(u) in urls for u in ln["termo_urls"]):
            continue
        avulso = jc.id_tc_avulso(ln["proc"], ln["data"])
        if any(i == avulso or i.startswith(avulso + "-") for i in ids) or (ln["proc"], ln["data"]) in proc_data:
            continue
        decisoes = [u for u in ln["decisao_urls"] if ji._e_pagina_de_decisao(u)]
        try:
            id_ = jc.id_colegiado(jc.caminho_url(decisoes[0])) if decisoes else avulso
        except ValueError:
            id_ = avulso
        url = jc.absoluta(decisoes[0]) if decisoes else jc.absoluta((ln["termo_urls"] or [""])[0])
        col.item("J", id_, [], url, ln["data"], "", "TC %s novo na tabela" % ln["resultado"],
                 {"tipo": "termo-compromisso", "resultado": ln["resultado"], "processo": ln["processo"],
                  "url": url, "data": ln["data"], "plugin": _plugin("termo-compromisso", ln["data"]),
                  "termo_urls": [jc.absoluta(u) for u in ln["termo_urls"]],
                  "decisao_urls": [jc.absoluta(u) for u in ln["decisao_urls"]]})


def pas(ctx, col, maximo_paginas=60):
    """Notícias de resultado de julgamento e extratos de sessão no SEI (diária), como
    julgados_noticias.py, do início do semestre anterior até hoje."""
    ini = semestres(ctx.hoje)[0][0]
    de, ate = _br(ini), _br(datetime.date.fromisoformat(ctx.hoje))
    resultado, inicio, paginas = collections.OrderedDict(), 0, 0
    while inicio is not None and paginas < maximo_paginas:
        q = {"form.submitted": "1", "texto": "julgamento", "dt_inicio": de, "dt_fim": ate}
        if inicio:
            q["b_start:int"] = str(inicio)
        r = col.exigir(ctx.rede.get(jn.URL_BUSCA + "?" + urllib.parse.urlencode(q), ua=jc.USER_AGENT),
                       "busca de notícias da CVM")
        html = r.texto()
        achados = jn.ler_busca(html)
        for it in achados:
            if jn.e_resultado(it):
                resultado.setdefault(it["url"], it)
        inicio = jn.proximo_inicio(html, inicio) if achados else None
        paginas += 1
    if inicio is not None:
        col.aviso("busca de notícias cortada em %d páginas (resultados mais antigos não lidos)" % maximo_paginas)
    artigos, falhas = [], []
    for url, it in resultado.items():
        cache = os.path.join(ctx.pasta_noticias, jn.nome_artigo(url)) if ctx.pasta_noticias else ""
        if cache and os.path.exists(cache):
            html = jn._ler(cache)
        else:
            r = ctx.rede.get(url, ua=jc.USER_AGENT)
            if r.status != 200:
                col.erro(r, url)
                falhas.append((url, it, r))
                continue
            html = r.texto()
        art = jn.ler_artigo(html)
        art["url"] = art["url"] or url
        art["data"] = it["data"] or art["data"]
        art["titulo"] = art["titulo"] or it["titulo"]
        artigos.append(art)
    extratos, off = {}, 0
    while off < 100 * jn.POR_PAGINA_SEI:
        campos = {"hdnInfraTipoPagina": "1", "hdnInicio": str(off), "hdnInfraPrefixoCookie": "CVM_SEI_",
                  "selOrgao[]": "0", "txtInteiroTeor": "", "txtResumo": "", "selUnidadeResponsavel": "",
                  "selSerie": jn.SERIE_EXTRATO, "txtNumero": "", "txtProtocoloPesquisa": "",
                  "selVeiculoPublicacao": "", "txtDataDocumento": "", "rdoDataPublicacao": "E",
                  "txtDataInicio": de, "txtDataFim": ate}
        r = col.exigir(ctx.rede.post(jn.URL_SEI, campos, ua=jc.USER_AGENT), "pesquisa de extratos no SEI")
        lidas = jn.ler_busca_sei(r.texto())
        for ln in lidas:
            if ln["serie"].startswith("Extrato de Sess"):
                extratos[ln["id_documento"]] = ln
        if len(lidas) < jn.POR_PAGINA_SEI:
            break
        off += jn.POR_PAGINA_SEI
    else:
        col.aviso("pesquisa de extratos no SEI cortada em 100 páginas")
    indice = jn.indice({"noticias": artigos, "extratos": sorted(
        extratos.values(), key=lambda x: (x["data_pub"] or "", x["id_documento"]))})
    inv = [r for r in ctx.julgados if r["tipo"] == "pas"]
    conhecidos = {jc.nup(r.get("processo") or "") for r in inv} | {r["id"][len("cvm-pas-"):] for r in inv}
    achados = {jc.nup(k) for k in indice if jc.nup(k)}
    base = sum(1 for r in inv if (r.get("data") or "") >= ini.isoformat())
    col.piso("pas", len(achados), base, "PAS (NUP) nas notícias e extratos do semestre anterior e do corrente")
    urls_inv = {r.get("url") for r in inv}
    for url, it, r in falhas:  # notícia que não respondeu não some: vai ao Diogo como J
        if url in urls_inv or url in ctx.decididos_url:
            continue
        slug = url.rstrip("/").rsplit("/", 1)[-1][:80]
        erro = r.erro or "HTTP %s" % r.status
        col.item("J", "cvm-pas-noticia-" + slug, [], url, it.get("data") or "", "",
                 "notícia de julgamento não lida (%s): conferir à mão" % erro,
                 {"tipo": "pas", "leitura_falhou": True, "erro": erro, "titulo": it.get("titulo") or "",
                  "url": url, "data": it.get("data") or "",
                  "plugin": jc.plugin_do_julgado("pas", (it.get("data") or ctx.hoje)[:4])})
    for k, ent in sorted(indice.items(), key=lambda x: (x[1]["data"] or "", x[0])):
        n = jc.nup(k)
        if not n or n in conhecidos or not ent["data"] or ent["data"] > ctx.hoje:
            continue
        ext = sorted(ent.get("extratos", []), key=lambda e: (e["data_pub"] or "", e["id_documento"]))
        url = ent["noticia"] or (ext[-1]["url"] if ext else "")
        col.item("J", jc.id_pas(n), [], url, ent["data"], "", "PAS julgado novo (%s)" % (
            "notícia" if ent["noticia"] else "extrato do SEI"),
                 {"tipo": "pas", "processo": k, "url": url, "data": ent["data"],
                  "plugin": jc.plugin_do_julgado("pas", ent["data"][:4]),
                  "origem": "noticia" if ent["noticia"] else "extrato", "sei_urls": [e["url"] for e in ext[-1:]]})


def ler_sessao_crsfn(html, url_sessao):
    """([{item_url, titulo}], próxima página ou None) da página de uma sessão do CRSFN."""
    i, j = html.find('id="content-core"'), html.find('id="viewlet-below-content-body"')
    seg = html[i:j] if i > 0 else html
    itens = []
    for m in re.finditer(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', seg, flags=re.S):
        u = htmllib.unescape(m.group(1))
        if u.startswith(url_sessao + "/"):
            u = u[:-5] if u.endswith("/view") else u
            itens.append({"item_url": u, "titulo": htmllib.unescape(re.sub(r"<[^>]+>|\s+", " ", m.group(2))).strip()})
    prox = re.findall(r'class="proximo" href="([^"]+)"', seg)
    return itens, (htmllib.unescape(prox[0]) if prox else None)


def item_crsfn(base, ano, sessao, url_sessao):
    """Item no formato do inventário do CRSFN (fase-2d, final.py)."""
    t = base["titulo"]
    m = re.match(r"(?:Recurso|recurso)\s+(\d{3,6})(?![\d/])", t) or re.match(r"EDCL\s+(?:Recurso\s+)?(\d{3,6})", t)
    nup = re.search(r"(\d{5}\.\d{3,6}/\d{4}-\d\d)", t)
    p = re.search(r"(\d{5})\.\d{3,6}/\d{4}-\d\d", t)
    p = p.group(1) if p else None
    return {"ano": ano, "sessao": sessao, "sessao_url": url_sessao, "item_url": base["item_url"], "titulo": t,
            "tipo": "embargos" if t.startswith("EDCL") else "revisao" if t.startswith("Revis") else "recurso/processo",
            "recurso": int(m.group(1)) if m else None, "nup_titulo": nup.group(1) if nup else None,
            "orgao": CRSFN_PREFIXOS.get(p, "INDETERMINADO"),
            "criterio": "prefixo NUP " + p if p in CRSFN_PREFIXOS else "sem critério na listagem"}


def _ano_crsfn(url):
    m = re.search(r"/acordaos-e-decisoes-monocraticas/(\d{4})/", url or "")
    return int(m.group(1)) if m else None


def classificador_crsfn(cache):
    """Classificação de órgão pelo crsfn.py (baixa a fonte do item; INDETERMINADO se falhar)."""
    def classificar(id_, item):
        import crsfn
        try:
            reg = crsfn.classificar_item(id_, item, jc.Cliente(intervalo=1.0), cache)
        except Exception as e:  # noqa: BLE001 — sem fonte: fica indeterminado, com o motivo
            return "INDETERMINADO", "erro na classificação: %s" % str(e)[:120]
        return reg.get("orgao") or "INDETERMINADO", reg.get("criterio") or ""
    return classificar


def crsfn(ctx, col, maximo_paginas=200):
    """Páginas do ano corrente e do anterior (semanal); acórdão novo classificado pelo órgão."""
    ano = int(ctx.hoje[:4])
    anos = (ano - 1, ano)
    itens, paginas, nao_lidas, cortadas = collections.OrderedDict(), 0, [], []
    for a in anos:
        r = col.exigir(ctx.rede.get(CRSFN_ANO % a, ua=jc.USER_AGENT), "página do CRSFN de %d" % a)
        sessoes = re.findall(r'<div class="tab-content" data-id="([^"]*)" data-url="([^"]*)"', r.texto())
        if not sessoes:
            raise Falha("página do CRSFN de %d sem sessões (leiaute mudou?)" % a)
        for rotulo, url_sessao in sessoes:
            rotulo = htmllib.unescape(rotulo)
            url_sessao, pagina = htmllib.unescape(url_sessao), htmllib.unescape(url_sessao)
            if "/acordaos-e-decisoes-monocraticas/" not in url_sessao:
                # aba que aponta direto para o documento (SEI do colaboragov, desde 2026): a aba é o acórdão
                itens.setdefault(url_sessao, item_crsfn({"item_url": url_sessao, "titulo": rotulo}, a, rotulo, url_sessao))
                continue
            while pagina and paginas < maximo_paginas:
                paginas += 1
                rs = ctx.rede.get(pagina, ua=jc.USER_AGENT)
                if rs.status != 200:
                    col.erro(rs, pagina)
                    nao_lidas.append((a, rotulo, pagina, rs))
                    pagina = None
                    break
                lidos, pagina = ler_sessao_crsfn(rs.texto(), url_sessao)
                for it in lidos:
                    itens.setdefault(it["item_url"], item_crsfn(it, a, rotulo, url_sessao))
            if pagina:
                cortadas.append(url_sessao)
    if cortadas:
        raise Falha("CRSFN: corte de %d páginas atingido com %d sessão(ões) por ler (a primeira: %s)"
                    % (maximo_paginas, len(cortadas), cortadas[0]))
    conhecidos = set(ctx.crsfn) | ctx.decididos_url
    base = sum(1 for u in conhecidos if _ano_crsfn(u) in anos)
    col.piso("crsfn", len(itens), base, "acórdãos listados pelo CRSFN nos dois anos")
    for a, rotulo, pagina, rs in nao_lidas:  # página que não respondeu não some: vai ao Diogo como J
        if pagina in conhecidos:
            continue
        nup = re.search(r"(\d{5}\.\d{3,6}/\d{4}-\d\d)", rotulo)
        id_ = "crsfn-" + (nup.group(1).replace(".", "-").replace("/", "-") if nup else
                          "sessao-%d-%s" % (a, re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", rotulo).encode("ascii", "ignore").decode().lower()).strip("-")))
        col.item("J", id_, [], pagina, "", "", "página do CRSFN não lida (%s): conferir à mão" % (
            rs.erro or "HTTP %s" % rs.status),
                 {"tipo": "acordao-crsfn", "leitura_falhou": True, "erro": rs.erro or "HTTP %s" % rs.status,
                  "sessao": rotulo, "ano": a, "url": pagina, "data": "",
                  "plugin": jc.plugin_do_julgado("acordao-crsfn", a)})
    usados = set(ctx.crsfn.values())  # idem
    for url, it in itens.items():
        if url in conhecidos:
            continue
        base_id = id_ = _id_base_crsfn(it)
        k = 1
        while id_ in usados:
            k += 1
            id_ = "%s-%d" % (base_id, k)
        usados.add(id_)
        orgao, criterio = it["orgao"], it["criterio"]
        if orgao == "INDETERMINADO" and ctx.classificador_crsfn:
            orgao, criterio = ctx.classificador_crsfn(id_, it)
        perimetro = "dentro" if orgao == "CVM" else ("duvidosa" if orgao == "INDETERMINADO" else "fora")
        col.item("J", id_, [], url, "", "", "acórdão novo do CRSFN (órgão de origem: %s)" % orgao,
                 {"tipo": "acordao-crsfn", "orgao": orgao, "criterio": criterio, "perimetro": perimetro,
                  "processo": it["nup_titulo"] or "", "ano": it["ano"], "sessao": it["sessao"],
                  "url": url, "data": "", "plugin": jc.plugin_do_julgado("acordao-crsfn", it["ano"])})


def _id_base_crsfn(item):
    """crsfn.id_base, com o crsfn.py importado só quando há acórdão novo."""
    import crsfn as mcrsfn
    return mcrsfn.id_base(item)


# ---------------------------------------------------------------- execução

ETAPAS = {
    "cvm": (("diaria", cvm_busca), ("semanal", cvm_consolidados)),
    "bcb": (("diaria", bcb_busca), ("semanal", bcb_128)),
    "leis": (("semanal", leis),),
    "b3": (("semanal", b3),),
    "anbima": (("semanal", anbima),),
    "colegiado": (("diaria", colegiado),),
    "pas": (("diaria", pas),),
    "tc": (("semanal", tc),),
    "crsfn": (("semanal", crsfn),),
}


def agora_sp():
    try:
        from zoneinfo import ZoneInfo
        fuso = ZoneInfo("America/Sao_Paulo")
    except Exception:  # noqa: BLE001
        fuso = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(fuso).replace(microsecond=0).isoformat()


def rodar_fonte(fonte, ctx, frequencia="todas"):
    """(Coleta, motivo da falha ou "")."""
    col = Coleta(fonte)
    try:
        for freq, fn in ETAPAS[fonte]:
            if frequencia in ("todas", freq):
                fn(ctx, col)
    except Falha as e:
        return col, str(e)
    except Exception as e:  # noqa: BLE001 — erro inesperado num detector não derruba os outros
        return col, "erro inesperado: %s: %s" % (type(e).__name__, str(e)[:200])
    return col, ""


def detectar(ctx, fontes=FONTES, frequencia="todas", excluir=()):
    """(deteccao, código de saída)."""
    excluir = set(excluir)
    saida = {"gerado_em": agora_sp(), "fontes": {}, "itens": []}
    vistos, falhou = {}, False
    for fonte in fontes:
        if not any(frequencia in ("todas", f) for f, _ in ETAPAS[fonte]):
            continue
        col, motivo = rodar_fonte(fonte, ctx, frequencia)
        ent = {"status": "falha" if motivo else "ok", "motivo": motivo or "; ".join(col.avisos),
               "contagem": col.contagem, "piso": col.piso_total, "http": col.http, "itens": 0, "descartados": 0,
               "etapas": col.etapas, "erros": col.erros[:30], "n_erros": len(col.erros)}
        saida["fontes"][fonte] = ent
        if motivo:
            falhou = True
            continue
        for it in col.itens:
            if it["id"] in excluir or ctx.decidido(it):
                ent["descartados"] += 1
                continue
            chave = (it["classe"], it["id"], tuple(it["norma_alvo"]))
            if chave in vistos:
                velho = vistos[chave]
                if it["classe"] == "J" and it["dados"].get("tipo") == "termo-compromisso":
                    velho["dados"].update({k: it["dados"][k] for k in ("tipo", "plugin", "resultado") if k in it["dados"]})
                    velho["dados"]["classe"] = ""
                continue
            vistos[chave] = it
            saida["itens"].append(it)
            ent["itens"] += 1
    return saida, (2 if falhou else 0)


def resumo(fonte, ent, itens):
    if ent["status"] != "ok":
        return "%-9s FALHA  %s" % (fonte, ent["motivo"])
    cl = collections.Counter(i["classe"] for i in itens if i["fonte"] == fonte)
    return "%-9s ok     contagem %d (piso %d), %d item(ns)%s%s%s" % (
        fonte, ent["contagem"], ent["piso"], ent["itens"],
        " [%s]" % ", ".join("%s %d" % kv for kv in sorted(cl.items())) if cl else "",
        ", %d descartado(s)" % ent["descartados"] if ent["descartados"] else "",
        ", %d erro(s) de documento" % ent["n_erros"] if ent["n_erros"] else "") + (
        "; aviso: %s" % ent["motivo"] if ent["motivo"] else "")


def ler_excluir(caminho):
    with open(caminho, encoding="utf-8") as f:
        txt = f.read()
    try:
        dados = json.loads(txt)
        if isinstance(dados, list):
            return {str(x) for x in dados}
    except ValueError:
        pass
    return {ln.strip() for ln in txt.splitlines() if ln.strip() and not ln.startswith("#")}


# ---------------------------------------------------------------- registro de HEAD

def registrar_head(raiz=RAIZ, rede=None, log=print):
    """Grava o tamanho e o Last-Modified de referência dos consolidados da CVM
    (fontes/acervo.json, `consolidado_head` em cada resolução do plugin) e dos PDFs vigentes da
    ANBIMA (fontes/acervo-anbima.json, `bytes` e `last_modified`), só quando a data do
    Last-Modified não passa da leitura do acervo: o que mudou depois fica sem registro e o
    detector o acusa. A B3 (fontes/acervo-b3.json, documentos que entram) tinha `bytes: 0`, porque
    o servidor não manda Content-Length no HEAD: o tamanho vem de um GET (head_com_tamanho)."""
    rede = rede or Rede()
    n = os.path.join(raiz, "plugins", "normas", "normas")
    publicados = {x["id"] for x in _ler_json(os.path.join(n, "normas.json"), [])}
    cam = os.path.join(raiz, "fontes", "acervo.json")
    acervo = _ler_json(cam)
    feitos = pulados = 0
    for r in acervo["resolucoes"]:
        cons = r.get("consolidado") or {}
        url = cons.get("docx") or cons.get("htm")
        if "cvm-res-%d" % int(r["numero"]) not in publicados or not url:
            continue
        h = head_com_tamanho(rede, url)
        lm = h.cab.get("last-modified") or ""
        if h.status == 200 and (not data_lm(lm) or data_lm(lm) <= acervo["lido_em"]):
            r["consolidado_head"] = {"bytes": int(h.cab.get("content-length") or 0), "last_modified": lm}
            feitos += 1
        else:
            pulados += 1
            log("consolidado sem registro: %s (HTTP %s, Last-Modified %s)" % (url, h.status, lm or "-"))
    gravar_json(cam, acervo)
    log("acervo.json: %d consolidados registrados, %d sem registro" % (feitos, pulados))
    cam = os.path.join(raiz, "fontes", "acervo-anbima.json")
    anb = _ler_json(cam)
    feitos = pulados = 0
    for d in anb["documentos"]:
        if d.get("situacao") != "vigente":
            continue
        h = head_com_tamanho(rede, d["url"])
        lm = h.cab.get("last-modified") or ""
        if h.status == 200 and (not data_lm(lm) or data_lm(lm) <= anb["lido_em"]):
            d["bytes"], d["last_modified"] = int(h.cab.get("content-length") or 0), lm
            feitos += 1
        else:
            pulados += 1
            log("ANBIMA sem registro: %s (HTTP %s, Last-Modified %s)" % (d["url"], h.status, lm or "-"))
    gravar_json(cam, anb)
    log("acervo-anbima.json: %d documentos registrados, %d sem registro" % (feitos, pulados))
    cam = os.path.join(raiz, "fontes", "acervo-b3.json")
    b3_ = _ler_json(cam)
    feitos = pulados = 0
    for d in b3_["documentos"]:
        if not d.get("entra"):
            continue
        h = head_com_tamanho(rede, d["url"])
        lm = h.cab.get("last-modified") or ""
        if h.status == 200 and h.cab.get("content-length") and (not data_lm(lm) or data_lm(lm) <= b3_["lido_em"]):
            d["bytes"], d["last_modified"] = int(h.cab["content-length"]), lm
            feitos += 1
        else:
            pulados += 1
            log("B3 sem registro: %s (HTTP %s, Last-Modified %s)" % (d["url"], h.status, lm or "-"))
    gravar_json(cam, b3_)
    log("acervo-b3.json: %d documentos registrados, %d sem registro" % (feitos, pulados))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fontes", default=",".join(FONTES))
    ap.add_argument("--frequencia", choices=("diaria", "semanal", "todas"), default="todas")
    ap.add_argument("--desde", help="BCB: data inicial da busca (padrão: lido_em do acervo-bcb.json)")
    ap.add_argument("--saida", help="pasta de saída (padrão: dados/auto/<hoje>)")
    ap.add_argument("--excluir-ids", help="arquivo com ids a pular (um por linha ou lista JSON)")
    ap.add_argument("--execucao-id", help="id gravado no deteccao.json (o job confere que é o desta execução)")
    ap.add_argument("--registrar-head", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    cache = os.path.join(RAIZ, "dados", "auto", "cache")
    rede = Rede(cache=os.path.join(cache, "http"))
    if args.registrar_head:
        registrar_head(rede=rede)
        return 0
    fontes = [f.strip() for f in args.fontes.split(",") if f.strip()]
    errado = [f for f in fontes if f not in FONTES]
    if errado:
        ap.error("fonte desconhecida: %s" % ", ".join(errado))
    if args.desde and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.desde):
        ap.error("--desde em AAAA-MM-DD")
    ctx = Contexto.do_repo(desde=args.desde, rede=rede,
                           navegador=navegador_chrome(os.path.join(cache, "chrome-perfil"), rede),
                           classificador_crsfn=classificador_crsfn(os.path.join(cache, "crsfn")))
    excluir = ler_excluir(args.excluir_ids) if args.excluir_ids else ()
    pasta = args.saida or os.path.join(RAIZ, "dados", "auto", ctx.hoje)
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, "deteccao.json")
    if os.path.exists(arq):
        os.remove(arq)  # detector que cai não deixa o arquivo de outra execução
    saida, codigo = detectar(ctx, [f for f in FONTES if f in fontes], args.frequencia, excluir)
    saida["execucao_id"] = args.execucao_id or "%s-%d" % (datetime.datetime.now().strftime("%Y%m%dT%H%M%S"),
                                                          os.getpid())
    gravar_json(os.path.join(pasta, "deteccao.json"), saida)
    for fonte, ent in saida["fontes"].items():
        print(resumo(fonte, ent, saida["itens"]))
    print("-> %s (%d itens)" % (os.path.join(pasta, "deteccao.json"), len(saida["itens"])))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
