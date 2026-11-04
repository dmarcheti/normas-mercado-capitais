"""Testes de scripts/detectar.py, sem rede e sem macOS: a rede é um dicionário de respostas
montado a partir dos recortes em tests/fixtures/detectar/ (páginas reais aparadas; nas de
julgados, títulos e partes trocados por marcadores)."""
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import detectar as dt  # noqa: E402
import inventario_acervo as ia  # noqa: E402
import inventario_b3 as ib3  # noqa: E402
import inventario_bcb as ibcb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import julgados_inventario as ji  # noqa: E402
import julgados_noticias as jn  # noqa: E402
import leis as mleis  # noqa: E402
from controle import sem_controle  # noqa: E402

FIX = os.path.join(AQUI, "fixtures", "detectar")
HOJE = "2026-11-04"


def fx(nome, modo="r"):
    with open(os.path.join(FIX, nome), "rb" if modo == "rb" else "r", **({} if modo == "rb" else {"encoding": "utf-8"})) as f:
        return f.read()


def ok(corpo="", cab=None):
    return dt.Resposta(200, corpo.encode("utf-8") if isinstance(corpo, str) else corpo,
                       dict({"content-type": "text/html; charset=utf-8"}, **(cab or {})))


def erro(status=500):
    return dt.Resposta(status, b"", {}, "", "HTTP %d" % status)


class Rede:
    """Rede falsa: [(chave, resposta)], a primeira chave que casa responde. Chave é texto (contido
    na URL) ou função; resposta é Resposta ou função url -> Resposta. Sem rota: 404."""

    def __init__(self, rotas):
        self.rotas, self.pedidos = list(rotas), []

    def _resp(self, metodo, url):
        url = jc.absoluta(url)
        self.pedidos.append((metodo, url))
        for chave, resp in self.rotas:
            if (chave(url) if callable(chave) else chave in url):
                return resp(url) if callable(resp) else resp
        return erro(404)

    def get(self, url, ua=None):
        return self._resp("GET", url)

    def post(self, url, campos, ua=None):
        return self._resp("POST", url)

    def head(self, url, ua=None):
        return self._resp("HEAD", url)


def ctx(rotas, **kw):
    return dt.Contexto(hoje=HOJE, rede=Rede(rotas), **kw)


DECISAO = {"fonte": "teste", "decisao": "fora-do-perimetro", "motivo": "teste", "data": HOJE}


class Cenarios:
    """Os seis cenários do brief para cada fonte. Cada classe define nada(), novo(**kw), piso()
    e http(), e CLASSE (a classe esperada do item novo)."""
    FONTE, CLASSE, HTTP_NA_FONTE = None, None, True

    def rodar(self, c, excluir=()):
        return dt.detectar(c, [self.FONTE], "todas", excluir)

    def novos(self, s):
        return [i["id"] for i in s["itens"] if i["classe"] == self.CLASSE]

    def test_nada_novo(self):
        s, cod = self.rodar(self.nada())
        ent = s["fontes"][self.FONTE]
        self.assertEqual((cod, ent["status"], ent["motivo"]), (0, "ok", ""))
        self.assertEqual(s["itens"], [])
        self.assertGreaterEqual(ent["contagem"], ent["piso"])

    def test_item_novo(self):
        s, cod = self.rodar(self.novo())
        self.assertEqual(cod, 0, s["fontes"][self.FONTE]["motivo"])
        self.assertTrue(self.novos(s), [(i["classe"], i["id"]) for i in s["itens"]])
        return s

    def test_piso_violado(self):
        s, cod = self.rodar(self.piso())
        ent = s["fontes"][self.FONTE]
        self.assertEqual((cod, ent["status"]), (2, "falha"))
        self.assertIn("piso", ent["motivo"])
        self.assertEqual(s["itens"], [])

    def test_http_diferente_de_200(self):
        s, cod = self.rodar(self.http())
        ent = s["fontes"][self.FONTE]
        self.assertEqual((cod, ent["status"]), (2, "falha"))
        self.assertEqual(s["itens"], [])
        self.assertTrue(ent["motivo"])
        if self.HTTP_NA_FONTE:
            self.assertEqual(ent["http"], 500)
            self.assertIn("HTTP 500", ent["motivo"])

    def test_ja_decidido(self):
        s, _ = self.rodar(self.novo())
        ids = self.novos(s)
        # alteração (H, I, G) só sai com decisão daquele par (id, classe)
        par = {"classe": self.CLASSE} if self.CLASSE in dt.ALTERACAO else {}
        s2, cod = self.rodar(self.novo(decisoes=[dict(DECISAO, id=i, **par) for i in ids]))
        self.assertEqual(cod, 0)
        self.assertEqual(self.novos(s2), [])
        self.assertGreaterEqual(s2["fontes"][self.FONTE]["descartados"], len(ids))

    def test_excluido_por_excluir_ids(self):
        s, _ = self.rodar(self.novo())
        ids = self.novos(s)
        s2, cod = self.rodar(self.novo(), excluir=set(ids))
        self.assertEqual(cod, 0)
        self.assertEqual(self.novos(s2), [])


# ---------------------------------------------------------------- CVM

URL_CONS = "https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/200/resol246consolid.docx"
LM = "Mon, 03 Aug 2026 10:00:00 GMT"
URL_OFICIO = "https://conteudo.cvm.gov.br/legislacao/oficios-circulares/smi/oc-smi-0426.html"


class TestCVM(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "cvm", "A"

    def rotas(self, busca=None, head=None, busca_status=200):
        res = busca or fx("cvm-busca-resolucoes.html")
        return [
            (ia.BUSCA % "resolucoes", ok(res) if busca_status == 200 else erro(busca_status)),
            (ia.BUSCA % "oficios-circulares", ok(fx("cvm-busca-oficios.html"))),
            ("/legislacao/index.html?buscado=true", ok("<html><body></body></html>")),
            ("resolucoes/resol249.html", ok(fx("cvm-resolucao-249.html"))),
            ("resolucoes/resol248.html", ok(fx("cvm-resolucao-248.html"))),
            (URL_OFICIO, ok(fx("cvm-oficio.html"))),
            (URL_CONS, head or ok(b"", {"content-length": "1000", "last-modified": LM})),
        ]

    def acervo(self, nums, oficio=True, extra=0):
        res = [{"numero": n} for n in nums] + [{"numero": 1000 + i} for i in range(extra)]
        res.insert(0, {"numero": 246, "consolidado": {"docx": URL_CONS},
                       "consolidado_head": {"bytes": 1000, "last_modified": LM}})
        return {"lido_em": "2026-10-28", "resolucoes": res, "instrucoes": [], "pareceres": [],
                "oficios_circulares": [{"id": "cvm-oc-smi-0426", "url_pagina": URL_OFICIO}] if oficio else []}

    def c(self, nums, oficio=True, extra=0, **kw):
        kw.setdefault("rotas", self.rotas())
        return ctx(kw.pop("rotas"), acervo=self.acervo(nums, oficio, extra),
                   publicados={"cvm-res-246", "cvm-res-67"}, com_historico={"cvm-res-67"}, **kw)

    def nada(self):
        return self.c([248, 249])

    def novo(self, **kw):
        return self.c([], oficio=False, **kw)

    def piso(self):
        return self.c([248, 249], extra=10)

    def http(self):
        return self.c([248, 249], rotas=self.rotas(busca_status=500))

    def test_alteradora_de_norma_com_historico_e_c(self):
        s = self.test_item_novo()
        c = [i for i in s["itens"] if i["id"] == "cvm-res-248"]
        self.assertEqual([(i["classe"], i["norma_alvo"]) for i in c], [("C", ["cvm-res-67"])])
        self.assertTrue(c[0]["data_dou"])

    def test_alteradora_de_norma_sem_historico_e_b(self):
        c = self.c([], oficio=False)
        c.com_historico = set()
        s, _ = self.rodar(c)
        self.assertIn(("B", "cvm-res-248", ["cvm-res-67"]), [(i["classe"], i["id"], i["norma_alvo"]) for i in s["itens"]])

    def test_oficio_novo_e_f_com_formato(self):
        s = self.test_item_novo()
        f = [i for i in s["itens"] if i["classe"] == "F"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["dados"]["formato"], "pdf")
        self.assertTrue(f[0]["id"].startswith("cvm-"))

    def test_consolidado_novo_e_b(self):
        rotas = self.rotas(head=ok(b"", {"content-length": "2000", "last-modified": LM}))
        s, _ = self.rodar(self.c([248, 249], rotas=rotas))
        self.assertEqual([(i["classe"], i["id"], i["dados"]["consolidado_novo"]) for i in s["itens"]],
                         [("B", "cvm-res-246", True)])

    def test_revogada_na_busca_e_d(self):
        busca = fx("cvm-busca-resolucoes.html").replace("Resolução CVM 246", "Resolução CVM 246 (Revogada)")
        s, _ = self.rodar(self.c([248, 249], rotas=self.rotas(busca=busca)))
        self.assertEqual([(i["classe"], i["id"]) for i in s["itens"]], [("D", "cvm-res-246")])


# ---------------------------------------------------------------- BCB

class TestBCB(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "bcb", "H-novo"

    def setUp(self):
        self.rows = json.loads(fx("bcb-busca.json"))["Rows"]
        self.norma = json.loads(fx("bcb-norma.json"))

    def rotas(self, busca_status=200, norma=None):
        def busca(url):
            if busca_status != 200:
                return erro(busca_status)
            if "Resolu%C3%A7%C3%A3o+CMN" in url:
                return ok(fx("bcb-busca.json"))
            return ok(json.dumps({"TotalRows": 0, "RowCount": 0, "Rows": []}))
        return [(ibcb.BUSCA, busca), (ibcb.NORMA, ok(json.dumps(norma or self.norma)))]

    def c(self, conhecidas, versao=6.0, contagem=3, rotas=None, **kw):
        normas = [dict(ibcb.item_da_busca(r)) for r in self.rows[:conhecidas]]
        c0 = self.norma["conteudo"][0]
        normas.append({"tipo": "resolucao-bcb", "tipo_bcb": "Resolução BCB", "numero": 102,
                       "url_pagina": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o+BCB&numero=102",
                       "versao": versao, "documentos": "",
                       "atualizacoes": [a for a in c0["Atualizacoes"].split(";#") if a.strip()]})
        bcb = {"lido_em": "2026-10-29", "contagem": ["resolucao-cmn vigente %d" % contagem], "normas": normas}
        return ctx(rotas or self.rotas(), desde="2000-01-01", bcb=bcb, publicados={"bcb-res-102"}, **kw)

    def nada(self):
        return self.c(3)

    def novo(self, **kw):
        return self.c(2, **kw)

    def piso(self):
        return self.c(3, contagem=100)

    def http(self):
        return self.c(3, rotas=self.rotas(busca_status=500))

    def test_h_novo_traz_perimetro(self):
        s = self.test_item_novo()
        i = [x for x in s["itens"] if x["classe"] == "H-novo"][0]
        self.assertIn(i["dados"]["perimetro"], ("dentro", "fora", "duvidosa", "alteradora"))
        self.assertTrue(i["id"].startswith("cmn-res-"))

    def test_versao_nova_e_h(self):
        s, _ = self.rodar(self.c(3, versao=5.0))
        self.assertEqual([(i["classe"], i["id"]) for i in s["itens"]], [("H", "bcb-res-102")])

    def test_total_rows_sem_linhas_e_falha(self):
        def busca(url):
            if "Resolu%C3%A7%C3%A3o+CMN" in url:
                d = json.loads(fx("bcb-busca.json"))
                if "startrow=0" not in url:
                    d["Rows"] = []
                d["TotalRows"] = 500
                return ok(json.dumps(d))
            return ok(json.dumps({"TotalRows": 0, "RowCount": 0, "Rows": []}))
        s, cod = self.rodar(self.c(3, rotas=[(ibcb.BUSCA, busca), (ibcb.NORMA, ok(json.dumps(self.norma)))]))
        self.assertEqual(cod, 2)
        self.assertIn("linha(s) lida(s) de 500", s["fontes"]["bcb"]["motivo"])

    def test_adiado_sem_classe_nao_esconde_h(self):
        s, _ = self.rodar(self.c(3, versao=5.0, decisoes=[dict(DECISAO, id="bcb-res-102", decisao="adiado")]))
        self.assertEqual([i["classe"] for i in s["itens"]], ["H"])
        s, _ = self.rodar(self.c(3, versao=5.0, decisoes=[dict(DECISAO, id="bcb-res-102", decisao="adiado", classe="H")]))
        self.assertEqual(s["itens"], [])

    def test_revogada_e_d(self):
        norma = copy.deepcopy(self.norma)
        norma["conteudo"][0]["Revogado"] = "True"
        s, _ = self.rodar(self.c(3, rotas=self.rotas(norma=norma)))
        self.assertEqual([(i["classe"], i["id"]) for i in s["itens"]], [("D", "bcb-res-102")])


# ---------------------------------------------------------------- leis

class TestLeis(Cenarios, unittest.TestCase):
    FONTE, CLASSE, HTTP_NA_FONTE = "leis", "G", False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        item = json.loads(fx("lei-item.json"))
        self.url = item.pop("url_lida")
        self.item = item
        self.html = fx("lei-planalto.html", "rb")
        for rel, conteudo in mleis.montar_lei(dict(item, url=self.url), self.html).items():
            with open(os.path.join(self.tmp, rel), "w", encoding="utf-8") as f:
                f.write(sem_controle(conteudo))
        self.arquivo = os.path.join(self.tmp, rel)

    def c(self, status=200, leis=None, **kw):
        rotas = [(self.url, ok(self.html) if status == 200 else erro(status)),
                 (mleis.PLANALTO, ok(self.html) if status == 200 else erro(status))]
        return ctx(rotas, leis=leis or [self.item], pasta_leis=self.tmp, **kw)

    def nada(self):
        return self.c()

    def novo(self, **kw):
        with open(self.arquivo, encoding="utf-8") as f:
            t = f.read()
        if "texto antigo do teste" not in t:
            t = re.sub(r"(?m)^(## Art\. 1\S*\n\n)", r"\1texto antigo do teste\n\n", t, count=1)
            with open(self.arquivo, "w", encoding="utf-8") as f:
                f.write(t)
        return self.c(**kw)

    def piso(self):
        fantasmas = [dict(self.item, id="lei-9999%d" % k, numero=99990 + k, planalto=["x%d.htm" % k]) for k in range(2)]
        return ctx([(self.url, ok(self.html))], leis=[self.item] + fantasmas, pasta_leis=self.tmp)

    def http(self):
        return self.c(status=500)

    def test_g_lista_o_artigo(self):
        s = self.test_item_novo()
        self.assertTrue(any(a.startswith("Art. 1") for a in s["itens"][0]["dados"]["artigos"]))


# ---------------------------------------------------------------- B3

class TestB3(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "b3", "I-novo"

    def setUp(self):
        self.ac = json.loads(fx("b3-acervo.json"))
        self.entra = [d for d in self.ac["documentos"] if d.get("entra") is True]

    def rotas(self, status=200, lm=None):
        pag = self.ac["paginas"][0]
        heads = {d["url"]: d for d in self.ac["documentos"]}
        return [(pag, ok(fx("b3-pagina.html")) if status == 200 else erro(status)),
                (lambda u: u in heads, lambda u: ok(b"", {"last-modified": lm or heads[u]["last_modified"] or ""})),
                ("/regulamentos-e-manuais/", ok("<html><body></body></html>"))]

    def c(self, docs=None, rotas=None, **kw):
        return ctx(rotas or self.rotas(), b3=dict(self.ac, documentos=docs if docs is not None else self.ac["documentos"]), **kw)

    def nada(self):
        return self.c()

    def novo(self, **kw):
        fora = self.entra[0]["url"]
        return self.c([d for d in self.ac["documentos"] if d["url"] != fora], **kw)

    def piso(self):
        extra = [{"url": "https://www.b3.com.br/data/files/x%d.pdf" % k, "arquivo": "x%d.pdf" % k, "entra": False} for k in range(10)]
        return self.c(self.ac["documentos"] + extra)

    def http(self):
        return self.c(rotas=self.rotas(status=500))

    def test_last_modified_novo_e_i(self):
        s, _ = self.rodar(self.c(rotas=self.rotas(lm="Tue, 03 Nov 2026 10:00:00 GMT")))
        self.assertEqual({i["classe"] for i in s["itens"]}, {"I"})
        self.assertEqual(len(s["itens"]), len(self.entra))


# ---------------------------------------------------------------- ANBIMA

class TestAnbima(Cenarios, unittest.TestCase):
    FONTE, CLASSE, HTTP_NA_FONTE = "anbima", "I-novo", False

    def setUp(self):
        self.ac = json.loads(fx("anbima-acervo.json"))
        self.pag = self.ac["documentos"][0]["paginas"][0]
        self.vig = [d for d in self.ac["documentos"] if d["situacao"] == "vigente"]

    def c(self, docs=None, navegador=True, estatico=200, tam=None, **kw):
        heads = {d["url"]: d for d in self.ac["documentos"]}
        rotas = [(self.pag, ok(fx("anbima-pagina.html")) if estatico == 200 else (
                     ok("<html></html>") if estatico == "vazio" else erro(estatico))),
                 (lambda u: u in heads, lambda u: ok(b"", {"content-length": str(tam or heads[u].get("bytes") or 0),
                                                           "last-modified": heads[u].get("last_modified") or ""}))]
        nav = (lambda u: fx("anbima-pagina.html") if u == self.pag else None) if navegador else (lambda u: None)
        return ctx(rotas, navegador=nav, anbima=dict(self.ac, documentos=docs if docs is not None else self.ac["documentos"]), **kw)

    def nada(self):
        return self.c()

    def novo(self, **kw):
        alvo = self.vig[-1]["url"]
        return self.c([d for d in self.ac["documentos"] if d["url"] != alvo], **kw)

    def piso(self):
        extra = [{"url": "https://www.anbima.com.br/data/files/x%d.pdf" % k, "titulo": "x", "situacao": "fora",
                  "paginas": [self.pag]} for k in range(10)]
        return self.c(self.ac["documentos"] + extra)

    def http(self):
        return self.c(navegador=False, estatico=500)

    def test_piso_de_paginas_sem_chrome_tambem_explica(self):
        s, cod = self.rodar(self.c(navegador=False, estatico=500))
        self.assertEqual(cod, 2)
        self.assertIn("páginas da ANBIMA lidas", s["fontes"]["anbima"]["motivo"])
        self.assertIn("sem leitura por script; conferência mensal no navegador", s["fontes"]["anbima"]["motivo"])

    def test_sem_chrome_e_sem_estatico_explica(self):
        s, cod = self.rodar(self.c(navegador=False, estatico="vazio"))
        self.assertEqual(cod, 2)
        self.assertIn("sem leitura por script; conferência mensal no navegador", s["fontes"]["anbima"]["motivo"])

    def test_tamanho_novo_e_i(self):
        s, _ = self.rodar(self.c(tam=123))
        self.assertEqual({i["classe"] for i in s["itens"]}, {"I"})
        self.assertEqual(len(s["itens"]), len(self.vig))


# ---------------------------------------------------------------- julgados

COL_ANTIGO = {"id": "cvm-col-20260918-d3619", "tipo": "decisao-colegiado", "classe": "recurso",
              "processo": "19957.015113/2026-86", "data": "2026-09-18",
              "url": "https://conteudo.cvm.gov.br/decisoes/2026/20260918_R1/20260918_D3619.html"}
COL_NOVO = dict(COL_ANTIGO, id="cvm-col-20261020-d3700", data="2026-10-20",
                url="https://conteudo.cvm.gov.br/decisoes/2026/20261020_R1/20261020_D3700.html")


def fantasmas(base, n, tipo=None):
    return [dict(base, id="%s-x%d" % (base["id"], k), tipo=tipo or base["tipo"], processo="",
                 url=base["url"].replace(".html", "x%d.html" % k)) for k in range(n)]


class TestColegiado(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "colegiado", "J"

    def c(self, julgados, status=200, **kw):
        return ctx([("/decisoes/index.html", ok(fx("colegiado.html")) if status == 200 else erro(status))],
                   julgados=julgados, **kw)

    def nada(self):
        return self.c([COL_ANTIGO, COL_NOVO])

    def novo(self, **kw):
        return self.c([COL_ANTIGO], **kw)

    def piso(self):
        return self.c([COL_ANTIGO, COL_NOVO] + fantasmas(COL_ANTIGO, 5))

    def http(self):
        return self.c([COL_ANTIGO], status=500)

    def test_j_sem_nome_de_parte(self):
        s = self.test_item_novo()
        i = s["itens"][0]
        self.assertEqual((i["id"], i["dados"]["tipo"]), ("cvm-col-20261020-d3700", "decisao-colegiado"))
        self.assertEqual(set(i["dados"]) >= {"tipo", "processo", "url", "data", "plugin"}, True)
        self.assertNotIn("titulo", i["dados"])


PAS_ANTIGO = {"id": "cvm-pas-19957-003286-2024-90", "tipo": "pas", "classe": "", "processo": "19957.003286/2024-90",
              "data": "2026-10-22", "url": "https://www.gov.br/cvm/pt-br/assuntos/noticias/2026/caso-a"}
PAS_NOVO = dict(PAS_ANTIGO, id="cvm-pas-19957-000222-2025-33", processo="19957.000222/2025-33")


class TestPAS(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "pas", "J"

    def c(self, julgados, status=200, **kw):
        return ctx([(jn.URL_BUSCA, ok(fx("noticias-busca.html")) if status == 200 else erro(status)),
                    ("controlador_publicacoes.php", ok(fx("sei-extratos.html")))], julgados=julgados, **kw)

    def nada(self):
        return self.c([PAS_ANTIGO, PAS_NOVO])

    def novo(self, **kw):
        return self.c([PAS_ANTIGO], **kw)

    def piso(self):
        return self.c([PAS_ANTIGO, PAS_NOVO] + [dict(PAS_ANTIGO, id="cvm-pas-x%d" % k, processo="") for k in range(5)])

    def http(self):
        return self.c([PAS_ANTIGO], status=500)

    def busca_com(self, url):
        sub = sorted(jn.SUBTITULOS_RESULTADO)[0].title()
        return ('<html><body><ul class="noticias"><li><div class="conteudo"><span class="subtitulo-noticia">%s</span>'
                '<h2 class="titulo"><a href="%s">CVM julga caso</a></h2><span class="data">20/10/2026</span>'
                '</div></li></ul></body></html>' % (sub, url))

    def test_noticia_nao_lida_vira_j_com_leitura_falhou(self):
        url = "https://www.gov.br/cvm/pt-br/assuntos/noticias/2026/caso-b"
        c = ctx([(url, erro(500)), (jn.URL_BUSCA, ok(self.busca_com(url))),
                 ("controlador_publicacoes.php", ok(fx("sei-extratos.html")))], julgados=[PAS_ANTIGO, PAS_NOVO])
        s, cod = self.rodar(c)
        self.assertEqual(cod, 0)
        self.assertEqual([(i["id"], i["dados"]["leitura_falhou"]) for i in s["itens"]],
                         [("cvm-pas-noticia-caso-b", True)])
        self.assertEqual(s["fontes"]["pas"]["n_erros"], 1)

    def test_noticia_conhecida_que_falha_nao_volta(self):
        url = PAS_ANTIGO["url"]
        c = ctx([(url, erro(500)), (jn.URL_BUSCA, ok(self.busca_com(url))),
                 ("controlador_publicacoes.php", ok(fx("sei-extratos.html")))], julgados=[PAS_ANTIGO, PAS_NOVO])
        s, _ = self.rodar(c)
        self.assertEqual(s["itens"], [])

    def test_corte_da_busca_vira_aviso(self):
        col = dt.Coleta("pas")
        c = ctx([(jn.URL_BUSCA, ok(self.busca_com("https://www.gov.br/cvm/x") + '<a class="proximo" href="?b_start:int=20">')),
                 ("controlador_publicacoes.php", ok(fx("sei-extratos.html")))], julgados=[PAS_ANTIGO, PAS_NOVO])
        orig = jn.proximo_inicio
        jn.proximo_inicio = lambda html, inicio: (inicio or 0) + 20
        try:
            dt.pas(c, col, maximo_paginas=2)
        except dt.Falha:
            pass
        finally:
            jn.proximo_inicio = orig
        self.assertTrue(any("cortada em 2 páginas" in a for a in col.avisos))

    def test_id_do_pas_novo(self):
        s = self.test_item_novo()
        self.assertEqual([(i["id"], i["dados"]["tipo"], i["dados"]["origem"]) for i in s["itens"]],
                         [("cvm-pas-19957-000222-2025-33", "pas", "extrato")])


TC_ANTIGO = {"id": "cvm-col-20260623-d3553", "tipo": "termo-compromisso", "classe": "", "processo": "19957.009587/2025-16",
             "data": "2026-06-23", "url": "https://conteudo.cvm.gov.br/decisoes/2026/20260623_R1/20260623_D3553.html"}
TC_NOVO = dict(TC_ANTIGO, id="cvm-col-20261015-d3690", processo="19957.000333/2025-44", data="2026-10-15",
               url="https://conteudo.cvm.gov.br/decisoes/2026/20261015_R1/20261015_D3690.html")


class TestTC(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "tc", "J"

    def c(self, julgados, status=200, **kw):
        return ctx([("resultadoTermoCompromissoRejeitado", ok(fx("tc-rejeitados.html"))),
                    ("resultadoTermoCompromisso", ok(fx("tc-aceitos.html")) if status == 200 else erro(status))],
                   julgados=julgados, **kw)

    def nada(self):
        return self.c([TC_ANTIGO, TC_NOVO])

    def novo(self, **kw):
        return self.c([TC_ANTIGO], **kw)

    def piso(self):
        return self.c([TC_ANTIGO, TC_NOVO] + fantasmas(TC_ANTIGO, 5))

    def http(self):
        return self.c([TC_ANTIGO], status=500)

    def test_tc_novo(self):
        s = self.test_item_novo()
        self.assertEqual([(i["id"], i["dados"]["tipo"], i["dados"]["resultado"]) for i in s["itens"]],
                         [("cvm-col-20261015-d3690", "termo-compromisso", "aceito")])


def url_crsfn(ano, n):
    return dt.CRSFN_ANO % ano + "/sessao-507/recurso-%d.pdf" % n


class TestCRSFN(Cenarios, unittest.TestCase):
    FONTE, CLASSE = "crsfn", "J"

    def rotas(self, status=200):
        def ano(u):
            return u.split("/acordaos-e-decisoes-monocraticas/")[1][:4]
        return [(lambda u: u.endswith("/sessao-507"), lambda u: ok(fx("crsfn-sessao.html").replace("ANO", ano(u)))),
                (dt.CRSFN_ANO % 2025, ok(fx("crsfn-ano.html").replace("ANO", "2025")) if status == 200 else erro(status)),
                (dt.CRSFN_ANO % 2026, ok(fx("crsfn-ano.html").replace("ANO", "2026")))]

    def c(self, conhecidos, status=200, **kw):
        self.chamados = []

        def classificar(id_, item):
            self.chamados.append(id_)
            return "CVM", "teste"
        return ctx(self.rotas(status), crsfn={u: "crsfn-%d" % k for k, u in enumerate(conhecidos)},
                   classificador_crsfn=classificar, **kw)

    def todos(self):
        return [url_crsfn(a, n) for a in (2025, 2026) for n in (11111, 22222, 33333)]

    def nada(self):
        return self.c(self.todos())

    def novo(self, **kw):
        return self.c([u for u in self.todos() if u != url_crsfn(2026, 11111)], **kw)

    def piso(self):
        return self.c(self.todos() + [url_crsfn(2026, k) for k in range(10)])

    def http(self):
        return self.c(self.todos(), status=500)

    def test_orgao_e_perimetro(self):
        s = self.test_item_novo()
        i = s["itens"][0]
        self.assertEqual((i["dados"]["orgao"], i["dados"]["perimetro"], i["dados"]["tipo"], i["url"]),
                         ("CVM", "dentro", "acordao-crsfn", url_crsfn(2026, 11111)))
        self.assertEqual(self.chamados, [])

    def test_indeterminado_usa_classificador(self):
        s, _ = self.rodar(self.c([u for u in self.todos() if u != url_crsfn(2026, 33333)]))
        self.assertEqual(len(self.chamados), 1)
        self.assertEqual(s["itens"][0]["dados"]["criterio"], "teste")

    def test_aba_com_documento_direto_e_sessao_que_falha(self):
        sei = "https://colaboragov.sei.gov.br/sei/publicacoes/controlador_publicacoes.php?acao=publicacao_visualizar&amp;id_documento=1&amp;id_orgao_publicacao=7"
        extra = ('<div class="tab-content" data-id="Processo 19957.015425/2024-28" data-url="%s"></div>'
                 '<div class="tab-content" data-id="508ª Sessão" data-url="%s/2026/sessao-508"></div>'
                 % (sei, dt.CRSFN_ANO.rsplit("/", 1)[0]))
        rotas = self.rotas()
        rotas.insert(1, (dt.CRSFN_ANO % 2026, ok(fx("crsfn-ano.html").replace("ANO", "2026").replace("</body>", extra + "</body>"))))
        rotas.insert(0, ("/sessao-508", erro(503)))
        c = ctx(rotas, crsfn={u: "crsfn-%d" % k for k, u in enumerate(self.todos())})
        s, cod = self.rodar(c)
        self.assertEqual(cod, 0)
        got = {i["id"]: i for i in s["itens"]}
        self.assertEqual(set(got), {"crsfn-19957-015425-2024-28", "crsfn-sessao-2026-508a-sessao"})
        self.assertEqual(got["crsfn-19957-015425-2024-28"]["dados"]["orgao"], "CVM")
        self.assertNotIn("leitura_falhou", got["crsfn-19957-015425-2024-28"]["dados"])
        self.assertTrue(got["crsfn-sessao-2026-508a-sessao"]["dados"]["leitura_falhou"])
        self.assertTrue(dt.permitido(sei.replace("&amp;", "&")))

    def test_corte_de_paginas_e_falha(self):
        col = dt.Coleta("crsfn")
        with self.assertRaises(dt.Falha) as e:
            dt.crsfn(self.nada(), col, maximo_paginas=1)
        self.assertIn("corte de 1 páginas", str(e.exception))

    def test_fora_do_perimetro_sai_marcado(self):
        s, _ = self.rodar(self.c([u for u in self.todos() if u != url_crsfn(2026, 22222)]))
        self.assertEqual((s["itens"][0]["dados"]["orgao"], s["itens"][0]["dados"]["perimetro"]), ("BCB", "fora"))


# ---------------------------------------------------------------- contrato e execução

class TestContrato(unittest.TestCase):
    CLASSES = {"A", "B", "C", "D", "E", "F", "G", "H", "H-novo", "I", "I-novo", "J"}

    def test_contrato_do_json(self):
        c = TestCVM()
        s, cod = dt.detectar(c.novo(), ["cvm"], "todas")
        s = json.loads(json.dumps(s, ensure_ascii=False))
        self.assertEqual(set(s), {"gerado_em", "fontes", "itens"})
        self.assertRegex(s["gerado_em"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-03:00$")
        for ent in s["fontes"].values():
            self.assertTrue({"status", "motivo", "contagem", "piso", "http"} <= set(ent))
            self.assertIn(ent["status"], ("ok", "falha"))
            for k in ("contagem", "piso", "http"):
                self.assertIsInstance(ent[k], int)
        self.assertTrue(s["itens"])
        for i in s["itens"]:
            self.assertEqual(set(i), {"fonte", "classe", "id", "norma_alvo", "url", "data", "data_dou", "motivo", "dados"})
            self.assertIn(i["classe"], self.CLASSES)
            self.assertIsInstance(i["norma_alvo"], list)
            self.assertIsInstance(i["dados"], dict)
            for k in ("url", "data", "data_dou", "motivo", "id"):
                self.assertIsInstance(i[k], str)

    def test_falha_de_uma_fonte_nao_para_as_outras(self):
        cvm = TestCVM().http()
        cvm.rede.rotas += [("/decisoes/index.html", ok(fx("colegiado.html")))]
        cvm.julgados = [COL_ANTIGO]
        s, cod = dt.detectar(cvm, ["cvm", "colegiado"], "todas")
        self.assertEqual(cod, 2)
        self.assertEqual((s["fontes"]["cvm"]["status"], s["fontes"]["colegiado"]["status"]), ("falha", "ok"))
        self.assertEqual({i["fonte"] for i in s["itens"]}, {"colegiado"})

    def test_frequencia_filtra_fontes_e_etapas(self):
        c = TestCVM().nada()
        s, _ = dt.detectar(c, list(dt.FONTES), "diaria")
        self.assertEqual(set(s["fontes"]), {"cvm", "bcb", "colegiado", "pas"})
        self.assertNotIn(("HEAD", URL_CONS), c.rede.pedidos)
        s, _ = dt.detectar(TestCVM().nada(), ["cvm", "leis"], "semanal")
        self.assertEqual(set(s["fontes"]), {"cvm", "leis"})
        self.assertEqual([e["etapa"] for e in s["fontes"]["cvm"]["etapas"]], ["consolidados"])

    def test_ler_excluir(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        for nome, txt in (("a.txt", "cvm-res-1\n\n# comentário\ncvm-res-2\n"), ("b.json", '["cvm-res-1", "cvm-res-2"]')):
            with open(os.path.join(d, nome), "w", encoding="utf-8") as f:
                f.write(txt)
            self.assertEqual(dt.ler_excluir(os.path.join(d, nome)), {"cvm-res-1", "cvm-res-2"})

    def test_rede_recusa_dominio_fora_da_lista(self):
        r = dt.Rede(cache=None, intervalo=0)
        self.assertEqual(r.get("https://exemplo.com/x").status, 0)
        self.assertIn("domínio fora da lista", r.get("https://exemplo.com/x").erro)

    def test_mudou_head_pela_data_do_last_modified(self):
        reg = {"bytes": 0, "last_modified": "Wed, 18 Jun 2025 15:26:10 GMT"}
        mesmo_dia = {"last-modified": "Wed, 18 Jun 2025 18:00:00 GMT"}
        self.assertEqual(dt.mudou_head(mesmo_dia, reg, "2026-01-01")[0], False)  # string diferente, mesma data
        self.assertEqual(dt.mudou_head({"last-modified": "Tue, 17 Jun 2025 10:00:00 GMT"}, reg, "2026-01-01")[0], False)
        self.assertEqual(dt.mudou_head({"last-modified": "Thu, 19 Jun 2025 10:00:00 GMT"}, reg, "2026-01-01")[0], True)
        self.assertEqual(dt.mudou_head({}, reg, "2026-01-01")[0], False)

    def test_head_sem_content_length_mede_pelo_get(self):
        url = "https://www.b3.com.br/data/files/x.pdf"
        rede = Rede([(url, lambda u: dt.Resposta(200, b"12345", {"last-modified": "x"}, u))])
        self.assertEqual(dt.head_com_tamanho(rede, url).cab["content-length"], "5")
        self.assertNotIn("content-length", dt.head_com_tamanho(rede, url, buscar=False).cab)

    def test_mudou_head(self):
        reg = {"bytes": 10, "last_modified": "a"}
        self.assertEqual(dt.mudou_head({"content-length": "10", "last-modified": "b"}, reg, "2026-01-01")[0], False)
        self.assertEqual(dt.mudou_head({"content-length": "11"}, reg, "2026-01-01")[0], True)
        self.assertEqual(dt.mudou_head({"last-modified": "Tue, 03 Nov 2026 10:00:00 GMT"}, None, "2026-10-01")[0], True)
        self.assertEqual(dt.mudou_head({"last-modified": "Tue, 03 Nov 2026 10:00:00 GMT"}, None, "2026-11-04")[0], False)

    def test_normas_com_historico(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        base = os.path.join(d, "cvm", "resolucoes")
        os.makedirs(os.path.join(base, "0175"))
        arquivos = {"0001.md": "id: cvm-res-1\nhistorico_parcial: false\n",
                    "0002.md": "id: cvm-res-2\nhistorico_parcial: true\nnivel_verificacao: historico-conferido\n",
                    "0003.md": "id: cvm-res-3\nhistorico_parcial: true\n",
                    "0175/index.md": "id: cvm-res-175\nhistorico_parcial: false\n"}
        for nome, fm in arquivos.items():
            with open(os.path.join(base, nome), "w", encoding="utf-8") as f:
                f.write("---\n" + fm + "---\ntexto\n")
        self.assertEqual(dt.normas_com_historico(d), {"cvm-res-1", "cvm-res-2", "cvm-res-175"})


if __name__ == "__main__":
    unittest.main()
