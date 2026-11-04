"""Testes de scripts/atualizar.py, sem rede, sem macOS e sem claude: a raiz é uma cópia mínima do
acervo numa pasta temporária; a rede é um dicionário de respostas (recortes de
tests/fixtures/detectar/) e os scripts chamados por subprocess são simulados por `Simulador`."""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import atualizar as at  # noqa: E402
import detectar as dt  # noqa: E402
import indice  # noqa: E402
import inventario_bcb as ibcb  # noqa: E402
import julgados_comum as jc  # noqa: E402
import leis as mleis  # noqa: E402

FIX = os.path.join(AQUI, "fixtures", "detectar")
HOJE = "2026-11-04"
URL_249 = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol249.html"
URL_250 = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol250.html"
URL_CONS = "https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/resolucoes/anexos/0/resol088consolid.docx"
URL_PO = "https://conteudo.cvm.gov.br/legislacao/pareceres-orientacao/pare042.html"
URL_PDF_VELHO = "https://www.anbima.com.br/data/files/velho.pdf"
URL_PDF_NOVO = "https://www.anbima.com.br/data/files/novo.pdf"
URL_SEI = "https://colaboragov.sei.gov.br/sei/publicacoes/controlador_publicacoes.php?id_documento=1"
CRSFN = "plugins/julgados-tc-crsfn/julgados/crsfn/2026"
NORMAS = "plugins/normas/normas"
CPF_FICTICIO = "529.982." + "247-25"  # por concatenação, para não haver CPF literal no repo


def cam_j(id_, ano="2026"):
    """Caminho do julgado do Colegiado como o julgados_converter grava."""
    return "plugins/" + jc.caminho_relativo("decisao-colegiado", id_, ano)


def fx(nome, modo="r"):
    with open(os.path.join(FIX, nome), "rb" if modo == "rb" else "r",
              **({} if modo == "rb" else {"encoding": "utf-8"})) as f:
        return f.read()


def ok(corpo="", cab=None):
    return dt.Resposta(200, corpo.encode("utf-8") if isinstance(corpo, str) else corpo,
                       dict({"content-type": "text/html; charset=utf-8"}, **(cab or {})))


class Rede:
    def __init__(self, rotas):
        self.rotas, self.pedidos = dict(rotas), []

    def get(self, url, ua=None):
        self.pedidos.append(url)
        return self.rotas.get(url) or dt.Resposta(404, b"", {}, url, "sem rota")

    def head(self, url, ua=None):
        return self.get(url)


def gravar(raiz, rel, conteudo):
    c = os.path.join(raiz, rel)
    os.makedirs(os.path.dirname(c), exist_ok=True)
    with open(c, "w", encoding="utf-8") as f:
        f.write(json.dumps(conteudo, ensure_ascii=False, indent=1) + "\n" if not isinstance(conteudo, str) else conteudo)


def gj(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    dt.gravar_json(caminho, obj)


def ler(raiz, rel):
    with open(os.path.join(raiz, rel), encoding="utf-8") as f:
        return json.load(f) if rel.endswith(".json") else f.read()


def norma_md(id_, corpo="Texto original."):
    return "---\nid: %s\ntipo: resolucao\nincerteza:\n---\n\n## Art. 1º\n\n%s\n" % (id_, corpo)


def montar_raiz(raiz):
    normas = []
    for n in range(88, 95):
        id_ = "cvm-res-%d" % n
        normas.append({"id": id_, "tipo": "resolucao", "titulo": "Resolução CVM %d" % n, "ementa": "",
                       "situacao": "vigente", "vigente_ate_ato": "", "caminho": "cvm/resolucoes/%04d.md" % n,
                       "grupo": ""})
        gravar(raiz, "%s/cvm/resolucoes/%04d.md" % (NORMAS, n), norma_md(id_))
    gravar(raiz, NORMAS + "/normas.json", normas)
    gravar(raiz, NORMAS + "/indice.md", "# Índice das normas\n")
    gravar(raiz, cam_j("cvm-col-20260101-d1"), "---\nid: cvm-col-20260101-d1\n---\n\nDecisão antiga.\n")
    gravar(raiz, CRSFN + "/19957-015425-2024-28.md",
           "---\nid: crsfn-19957-015425-2024-28\nsha256_fonte: %s\n---\n\nAcórdão.\n"
           % hashlib.sha256(b"acordao original").hexdigest())
    res = [{"numero": n, "titulo": "Resolução CVM %d" % n, "data": "2020-01-01", "dou": "2020-01-02",
            "ementa": "Dispõe sobre a matéria %d." % n, "no_estoque": True, "situacao": "vigente", "revogada": "",
            "alteradoras": [], "consolidado": {"docx": URL_CONS} if n == 88 else {}, "consolidado_em_partes": 0,
            "ato": {}, "url_pagina": "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol%03d.html" % n}
           for n in range(88, 95)]
    gravar(raiz, "fontes/acervo.json", {
        "lido_em": "2026-10-28", "estoque_regulatorio": {"atualizado_em": "2026-10-01",
                                                         "resolucoes": list(range(88, 95)), "grupos": {}},
        "resolucoes": res, "instrucoes": [], "pareceres": [], "oficios_circulares": []})
    for nome, vazio in (("pendentes", []), ("decisoes", []), ("julgados-inventario", [])):
        gravar(raiz, "fontes/%s.json" % nome, vazio)
    gravar(raiz, "fontes/acervo-bcb.json", {"lido_em": "2026-10-29", "normas": [
        {"tipo": "resolucao-bcb", "tipo_bcb": "Resolução BCB", "numero": 102, "data": "2021-06-07",
         "assunto": "Dispõe sobre o tema.", "situacao": "vigente", "versao": 5.0, "formato": "html",
         "url_pagina": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o+BCB&numero=102"}]})
    gravar(raiz, "fontes/perimetro-camada4.json", [{"tipo": "resolucao-bcb", "numero": 102, "decisao": "entra"}])
    gravar(raiz, "fontes/acervo-anbima.json", {"lido_em": "2026-10-29", "documentos": [
        {"titulo": "Regras do Código (vigente - consolidado)", "url": URL_PDF_VELHO, "arquivo": "velho.pdf",
         "situacao": "vigente", "tipo": "codigo", "bytes": 1000, "last_modified": ""}]})
    gravar(raiz, "fontes/acervo-b3.json", {"lido_em": "2026-10-29", "documentos": []})
    gravar(raiz, "fontes/leis.json", [json.loads(fx("lei-item.json"))])


class Simulador:
    """Faz o papel dos scripts chamados pelo atualizar (texto_vigente, testes, julgados, gate)."""

    def __init__(self, raiz):
        self.raiz, self.amb = raiz, None
        self.tv = {}            # id -> {texto, cobertura, nivel, resultado}
        self.atos = {}          # número -> texto do ato (modo piloto)
        self.rc = {}            # nome do script -> rc
        self.revisor = {}       # id -> {ok, alertas}
        self.julgado_extra = {}  # id -> texto acrescentado ao .md convertido
        self.reescrever = None  # rel de julgado existente que a conversão reescreve
        self.extra_tv = None    # rel de um arquivo a mais que o texto_vigente grava
        self.do_titulo = set()  # ids que a extração deixa com a ementa do título
        self.cobertura_j = {}   # id -> lista de conferências do relatório da conversão
        self.extracao_aplica = True
        self.chamadas, self.envs = [], {}

    def __call__(self, argv, env=None):
        nome = os.path.basename(argv[1]) if len(argv) > 1 else argv[0]
        if argv[:3] == ["python3", "-m", "unittest"]:
            nome = "unittest"
        self.chamadas.append((nome, argv))
        self.envs[nome] = env
        f = getattr(self, "_" + nome.replace(".py", ""), None)
        if f:
            return f(argv)
        return self.rc.get(nome, 0), "", ""

    @staticmethod
    def _opc(argv, chave):
        return argv[argv.index(chave) + 1] if chave in argv else None

    def _texto_vigente(self, argv):
        if "--camada" not in argv:  # modo piloto: texto do ato
            itens = at.ler_json(argv[2])
            for it in itens:
                gravar(argv[3], it["arquivo"], norma_md(it["id"], self.atos.get(it["numero"], "")))
            return 0, "", ""
        camada, ids = int(self._opc(argv, "--camada")), self._opc(argv, "--ids").split(",")
        relatorio = self._opc(argv, "--relatorio")
        entradas = at.ler_json(relatorio, []) or []
        for id_ in ids:
            cfg = self.tv.get(id_, {})
            item = at.item_tv(self.amb, camada, id_)
            if cfg.get("sem_entrada"):
                continue
            gravar(self.raiz, os.path.join(NORMAS, item["arquivo"]), norma_md(id_, cfg.get("texto", "Texto novo.")))
            e = {"id": id_, "arquivo": item["arquivo"], "resultado": cfg.get("resultado", "ok"),
                 "cobertura": cfg.get("cobertura", 1.0), "conferencia_independente": True,
                 "nivel_verificacao": cfg.get("nivel", "fonte-oficial")}
            if camada == 4 and cfg.get("versao_bcb", True):
                e["versao_bcb"] = {"decisao": "html", "versao": 6}
            entradas = [x for x in entradas if x["id"] != id_] + [e]
        if self.extra_tv:
            gravar(self.raiz, self.extra_tv, "intruso\n")
        if self.rc.get("texto_vigente.py"):
            return self.rc["texto_vigente.py"], "", "texto_vigente: erro simulado"
        gj(relatorio, entradas)
        return 0, "", ""

    def _julgados_baixar(self, argv):
        return 0, json.dumps({"itens": 1, "completos": 1, "sem_url": [], "com_erro": []}), ""

    def _julgados_converter(self, argv):
        ids = self._opc(argv, "--ids").split(",")
        inv = {x["id"]: x for x in at.ler_json(self._opc(argv, "--inventario"))["julgados"]}
        itens = []
        for id_ in ids:
            rel = cam_j(id_, inv[id_]["data"][:4])
            gravar(self.raiz, rel, "---\nid: %s\n---\n\nDecisão nova. %s\n" % (id_, self.julgado_extra.get(id_, "")))
            itens.append({"id": id_, "caminho": rel, "nivel": "texto", "paginas_ocr": 0, "avisos": [],
                          "cobertura": self.cobertura_j.get(id_, [{"arquivo": "01-pagina.html", "cobertura": 1.0,
                                                                   "conferencia": "html.parser"}])})
        if self.reescrever:
            gravar(self.raiz, self.reescrever, "---\nid: reescrito\n---\n\nOutro texto.\n")
        rel = self._opc(argv, "--relatorios")
        gj(os.path.join(rel, "conversao-20261104-120000.json"), {"itens": itens})
        return 0, "", ""

    def _julgados_extracao(self, argv):
        ids = self._opc(argv, "--ids").split(",")
        pasta = os.path.join(self._opc(argv, "--saida"), "lote-001")
        gj(os.path.join(pasta, "validacao.json"),
                           {"erros": [], "aplicados": {i: self.extracao_aplica for i in ids}, "retentar": {},
                            "ementa_do_titulo": [os.path.join(self.raiz, cam_j(i))
                                                 for i in ids if i in self.do_titulo]})
        gravar(pasta, "log.jsonl", json.dumps({"type": "result", "total_cost_usd": 0.0125}) + "\n")
        return 0, "", ""

    def _revisor(self, argv):
        arqs = self._opc(argv, "--arquivos").split(",")
        ids = [at.frontmatter_campo(at.ler_texto(a), "id") for a in arqs]
        out = {i: self.revisor.get(i, {"ok": True, "alertas": []}) for i in ids}
        return (0 if all(v["ok"] for v in out.values()) else 1), json.dumps(out), ""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="test-atualizar-")
        self.raiz = os.path.join(self.tmp, "repo")
        self.saida = os.path.join(self.tmp, "saida")
        montar_raiz(self.raiz)
        self.sim = Simulador(self.raiz)
        self.rotas = {URL_249: ok(fx("cvm-resolucao-249.html")), URL_250: ok(fx("cvm-resolucao-249.html"))}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def amb(self, **kw):
        a = at.Ambiente(self.raiz, self.saida, rodar=self.sim, rede=Rede(self.rotas), hoje=HOJE,
                        trabalho=os.path.join(self.tmp, "trab"), **kw)
        self.sim.amb = a
        return a

    def rodar(self, itens, **kw):
        crit = at.executar(self.amb(**kw), itens)
        return crit, {x["chave"]: x for x in crit["itens"]}

    def um(self, itens, **kw):
        crit, por = self.rodar(itens, **kw)
        self.assertEqual(len(por), 1, por)
        return crit, list(por.values())[0]


def item(classe, id_, alvos=(), url="", data="", dados=None, fonte="cvm", data_dou=""):
    return {"fonte": fonte, "classe": classe, "id": id_, "norma_alvo": list(alvos), "url": url,
            "data": data, "data_dou": data_dou, "motivo": "teste", "dados": dados or {}}


def b1(n=250, alvo="cvm-res-88"):
    return item("B", "cvm-res-%d" % n, [alvo], URL_250, "2026-11-03", {"ementa": "Altera."}, data_dou="2026-11-04")


def j(id_, data="2026-11-03"):
    return item("J", id_, (), "https://conteudo.cvm.gov.br/decisoes/2026/%s.html" % id_, data,
                {"tipo": "decisao-colegiado", "classe": "outros", "processo": "19957.000001/2026-01",
                 "url": "https://conteudo.cvm.gov.br/decisoes/2026/%s.html" % id_, "data": data,
                 "plugin": "julgados-colegiado-2016-2026"}, fonte="colegiado")


# ---------------------------------------------------------------- classes

class TestClasses(Base):
    def test_a_resolucao_nova_entra_no_acervo_e_converte(self):
        self.sim.tv["cvm-res-249"] = {"texto": "Programa Piloto DLT."}
        crit, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13", {"titulo": "Resolução CVM 249"})])
        acervo = ler(self.raiz, "fontes/acervo.json")
        e = next(x for x in acervo["resolucoes"] if x["numero"] == 249)
        self.assertTrue(e["incluida_pela_automacao"])
        self.assertEqual([x["numero"] for x in acervo["resolucoes"]][-1], 249)
        self.assertIn("Programa Piloto", ler(self.raiz, NORMAS + "/cvm/resolucoes/0249.md"))
        self.assertTrue(r["automatico"], r)
        self.assertEqual(r["condicoes"]["2-conferencia"], "ok")
        self.assertTrue(crit["conjunto"]["pr_automatico_antes_do_ci"], crit["conjunto"]["motivos"])
        self.assertFalse(crit["conjunto"]["pr_automatico"])  # CI pendente
        self.assertEqual(crit["conjunto"]["ci"], "pendente")
        self.assertEqual(r["condicoes"]["9-ci"], "pendente")

    def test_a_cobertura_baixa_vai_ao_diogo_e_volta_ao_estado_anterior(self):
        antes = ler(self.raiz, "fontes/acervo.json")
        self.sim.tv["cvm-res-249"] = {"cobertura": 0.9}
        crit, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13")])
        self.assertFalse(r["automatico"])
        self.assertEqual(r["condicoes"]["2-conferencia"], "falha")
        self.assertIn("cobertura", r["motivo"])
        self.assertEqual(ler(self.raiz, "fontes/acervo.json"), antes)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, NORMAS, "cvm/resolucoes/0249.md")))
        diogo = ler(self.saida, "itens-diogo.json")["itens"]
        self.assertEqual(diogo[0]["id"], "cvm-res-249")
        self.assertIn("+", diogo[0]["diff"])
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_b1_aviso_pendente_e_alteradora_registrada(self):
        crit, r = self.um([b1()])
        md = ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md")
        self.assertIn("incerteza: Alterada pela Resolução CVM 250 (DOU 2026-11-04); texto ainda sem a "
                      "alteração até o consolidado da CVM [verificar].", md)
        pend = ler(self.raiz, "fontes/pendentes.json")
        self.assertEqual([(p["norma"], p["ato_id"], p["classe"], p["data_deteccao"]) for p in pend],
                         [("cvm-res-88", "cvm-res-250", "B1", HOJE)])
        self.assertIn(250, [x["numero"] for x in ler(self.raiz, "fontes/acervo.json")["resolucoes"]])
        self.assertTrue(r["automatico"], r)
        self.assertEqual(r["classe"], "B1")
        self.assertEqual(r["condicoes"]["6-arquivos"], "ok")
        # segunda passagem não duplica aviso nem pendente
        self.rodar([b1()])
        self.assertEqual(ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md").count("Resolução CVM 250"), 1)
        self.assertEqual(len(ler(self.raiz, "fontes/pendentes.json")), 1)

    def test_b1_sem_alvo_vai_ao_diogo(self):
        _, r = self.um([item("B", "cvm-res-250", (), URL_250)])
        self.assertFalse(r["automatico"])
        self.assertIn("norma-alvo", r["motivo"])

    def b2(self):
        return item("B", "cvm-res-88", ["cvm-res-88"], URL_CONS, "2026-11-05",
                    {"consolidado_novo": True, "com_historico": False, "formato": "docx", "bytes": 4321,
                     "last_modified": "Thu, 05 Nov 2026 10:00:00 GMT"})

    def test_b1_e_depois_b2_verde_tira_aviso_e_pendente(self):
        self.rodar([b1()])
        self.sim.tv["cvm-res-88"] = {"texto": "Texto original.\n\nParágrafo incluído pela 250."}
        self.sim.atos[250] = "Art. 1º A Resolução 88 passa a vigorar com:\n\nParágrafo incluído pela 250."
        _, r = self.um([self.b2()])
        self.assertEqual(r["classe"], "B2")
        self.assertTrue(r["automatico"], r)
        self.assertEqual(ler(self.raiz, "fontes/pendentes.json"), [])
        e = next(x for x in ler(self.raiz, "fontes/acervo.json")["resolucoes"] if x["numero"] == 88)
        self.assertEqual(e["consolidado_head"], {"bytes": 4321, "last_modified": "Thu, 05 Nov 2026 10:00:00 GMT"})
        self.assertIn(250, e["alteradoras"])
        self.assertNotIn("Alterada pela", ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md"))

    def test_b2_vermelho_mantem_pendente_e_texto(self):
        self.rodar([b1()])
        texto_b1 = ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md")
        self.sim.tv["cvm-res-88"] = {"texto": "Texto original.\n\nLinha que o ato não traz."}
        self.sim.atos[250] = "Art. 1º Outra coisa."
        _, r = self.um([self.b2()])
        self.assertFalse(r["automatico"])
        self.assertEqual(r["condicoes"]["2-conferencia"], "falha")
        self.assertIn("teste 1", r["motivo"])
        self.assertEqual(len(ler(self.raiz, "fontes/pendentes.json")), 1)
        self.assertEqual(ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md"), texto_b1)

    def test_b2_com_historico_usa_teste_2(self):
        self.rotas[URL_CONS] = ok(b"docx", {"content-type": "application/octet-stream"})
        it = self.b2()
        it["dados"]["com_historico"] = True
        _, r = self.um([it])
        self.assertTrue(r["automatico"], r)
        self.assertIn("teste_final.py", [c[0] for c in self.sim.chamadas])
        self.sim.rc["teste_final.py"] = 1
        _, r = self.um([it])
        self.assertFalse(r["automatico"])
        self.assertIn("teste 2", r["motivo"])

    def test_c_aplica_aviso_e_fica_replay_manual(self):
        it = b1()
        it["classe"] = "C"
        _, r = self.um([it])
        self.assertFalse(r["automatico"])
        self.assertIn("replay manual", r["motivo"])
        self.assertIn("Alterada pela Resolução CVM 250", ler(self.raiz, NORMAS + "/cvm/resolucoes/0088.md"))
        self.assertEqual(ler(self.raiz, "fontes/pendentes.json")[0]["classe"], "C")

    def test_f_parecer_novo_e_f_ocr(self):
        self.rotas[URL_PO] = ok(fx("cvm-resolucao-249.html"))
        f = item("F", "cvm-po-42", ["cvm-po-42"], URL_PO, "2026-11-01",
                 {"formato": "pdf", "titulo": "Parecer de Orientação CVM 42", "ementa": "Orienta."})
        _, r = self.um([f])
        self.assertTrue(r["automatico"], r)
        self.assertIn(42, [p["numero"] for p in ler(self.raiz, "fontes/acervo.json")["pareceres"]])
        self.assertTrue(os.path.exists(os.path.join(self.raiz, NORMAS, "cvm/pareceres-orientacao/0042.md")))
        shutil.rmtree(self.raiz)
        montar_raiz(self.raiz)
        self.sim.tv["cvm-po-42"] = {"nivel": "ocr"}
        _, r = self.um([f])
        self.assertEqual(r["classe"], "F-OCR")
        self.assertFalse(r["automatico"])
        self.assertEqual(ler(self.raiz, "fontes/acervo.json")["pareceres"], [])

    def lei(self, remover=None):
        it = json.loads(fx("lei-item.json"))
        html = fx("lei-planalto.html", "rb")
        for rel, conteudo in mleis.montar_lei(dict(it, url=it["url_lida"]), html).items():
            if remover:
                conteudo = "\n".join(x for x in conteudo.split("\n") if remover not in x) + "\n"
            gravar(self.raiz, NORMAS + "/leis/" + rel, conteudo)
        self.rotas[it["url_lida"]] = ok(html)
        return item("G", it["id"], [it["id"]], it["url_lida"], fonte="leis")

    def test_g_lei_sem_mudanca_de_texto_e_automatica(self):
        _, r = self.um([self.lei()])
        self.assertTrue(r["automatico"], r)
        self.assertIn("teste_lei.py", [c[0] for c in self.sim.chamadas])

    def test_g_linha_nova_sem_nota_do_planalto_vai_ao_diogo(self):
        _, r = self.um([self.lei(remover="Art. 1º")])
        self.assertFalse(r["automatico"])
        self.assertIn("nota do Planalto", r["motivo"])

    def test_g_teste_lei_vermelho(self):
        self.sim.rc["teste_lei.py"] = 1
        _, r = self.um([self.lei()])
        self.assertFalse(r["automatico"])
        self.assertIn("teste_lei", r["motivo"])

    def test_h_versao_nova_do_bcb(self):
        url = ibcb.NORMA + "p1=Resolu%C3%A7%C3%A3o+BCB&p2=102"
        self.rotas[url] = ok(fx("bcb-norma.json"))
        _, r = self.um([item("H", "bcb-res-102", ["bcb-res-102"], "", dados={"versao": 6.0}, fonte="bcb")])
        self.assertTrue(r["automatico"], r)
        n = ler(self.raiz, "fontes/acervo-bcb.json")["normas"][0]
        self.assertNotEqual(n["versao"], 5.0)
        self.assertTrue(os.path.exists(os.path.join(self.raiz, NORMAS, "bcb/resolucoes/0102.md")))

    def i(self, tamanho):
        self.rotas[URL_PDF_NOVO] = ok(b"%PDF", {"content-length": str(tamanho), "last-modified": "Fri, 01 Nov 2024 00:00:00 GMT"})
        return item("I", "anbima-regras-do-codigo", ["anbima-regras-do-codigo"], URL_PDF_NOVO, "2024-11-01",
                    {"arquivo": "novo.pdf", "titulo": "Regras do Código (vigente a partir de 01.11.2024)",
                     "anterior": URL_PDF_VELHO}, fonte="anbima")

    def test_i_so_troca_de_url_atualiza_registro_sem_converter(self):
        _, r = self.um([self.i(1000)])
        self.assertEqual(r["estado"], "sem-mudanca")
        self.assertTrue(r["automatico"])
        docs = ler(self.raiz, "fontes/acervo-anbima.json")["documentos"]
        self.assertEqual([(d["url"], d["situacao"]) for d in docs], [(URL_PDF_NOVO, "vigente")])
        self.assertNotIn("texto_vigente.py", [c[0] for c in self.sim.chamadas])

    def test_i_pdf_novo_converte_e_antigo_vira_anterior(self):
        _, r = self.um([self.i(2000)])
        self.assertTrue(r["automatico"], r)
        docs = ler(self.raiz, "fontes/acervo-anbima.json")["documentos"]
        self.assertEqual([(d["url"], d["situacao"]) for d in docs],
                         [(URL_PDF_NOVO, "vigente"), (URL_PDF_VELHO, "anterior")])
        self.assertEqual(docs[0]["vigente_desde"], "2024-11-01")

    def test_j_julgado_novo_completo(self):
        crit, r = self.um([j("cvm-col-20261103-d3649")])
        self.assertTrue(r["automatico"], r)
        self.assertEqual(r["condicoes"]["5-revisor"], "ok")
        inv = ler(self.raiz, "fontes/julgados-inventario.json")
        self.assertEqual(inv, [{"id": "cvm-col-20261103-d3649", "tipo": "decisao-colegiado", "classe": "outros",
                                "processo": "19957.000001/2026-01", "data": "2026-11-03",
                                "url": "https://conteudo.cvm.gov.br/decisoes/2026/cvm-col-20261103-d3649.html",
                                "plugin": "julgados-colegiado-2016-2026"}])
        completo = ler(self.saida, "inventario-j.json")["julgados"][0]
        self.assertEqual((completo["proc"], completo["origem"]), ("19957-000001-2026-01", "colegiado"))
        auto = ler(self.saida, "itens-automaticos.json")["itens"]
        self.assertIn(cam_j("cvm-col-20261103-d3649"), auto[0]["arquivos"])
        self.assertEqual(crit["conjunto"]["julgados_novos"], 1)
        self.assertAlmostEqual(crit["conjunto"]["custo_llm_usd"], 0.0125)
        self.assertIn("US$ 0.0125", ler(self.saida, "resumo.md"))

    def test_j_crsfn_fora_vai_para_decisoes_com_classe(self):
        it = item("J", "crsfn-18600-008115-2023-43", (), "https://www.gov.br/x", fonte="crsfn",
                  dados={"tipo": "acordao-crsfn", "orgao": "BCB", "criterio": "prefixo NUP 18600", "perimetro": "fora"})
        _, r = self.um([it])
        self.assertEqual(r["estado"], "fora")
        self.assertTrue(r["automatico"], r)
        dec = ler(self.raiz, "fontes/decisoes.json")
        self.assertEqual([(d["id"], d["decisao"], d["classe"]) for d in dec],
                         [("crsfn-18600-008115-2023-43", "fora-do-perimetro", "J")])

    def crsfn2(self, corpo):
        self.rotas[URL_SEI] = ok(corpo)
        return item("J", "crsfn-19957-015425-2024-28-2", (), URL_SEI, fonte="crsfn",
                    dados={"tipo": "acordao-crsfn", "orgao": "CVM", "perimetro": "dentro"})

    def test_j_crsfn_menos_2_com_sha_igual_e_excecao(self):
        _, r = self.um([self.crsfn2(b"acordao original")])
        self.assertEqual(r["estado"], "excecao")
        self.assertEqual(ler(self.raiz, "fontes/decisoes.json")[0]["decisao"], "excecao")

    def test_j_crsfn_menos_2_com_sha_diferente_e_possivel_duplicata(self):
        _, r = self.um([self.crsfn2(b"outro acordao")])
        self.assertFalse(r["automatico"])
        self.assertIn("possível duplicata de crsfn-19957-015425-2024-28", r["motivo"])
        self.assertEqual(ler(self.raiz, "fontes/decisoes.json"), [])

    def test_leitura_falhou_vai_ao_diogo(self):
        it = j("cvm-col-x")
        it["dados"]["leitura_falhou"] = True
        _, r = self.um([it])
        self.assertFalse(r["automatico"])
        self.assertIn("leitura", r["motivo"])
        self.assertNotIn("julgados_baixar.py", [c[0] for c in self.sim.chamadas])

    def test_classes_so_do_diogo_trazem_o_que_seria_feito(self):
        itens = [item("D", "cvm-res-89", ["cvm-res-89"]), item("E", "cvm-res-90"),
                 item("H-novo", "bcb-res-999", dados={"perimetro": "dentro"}, fonte="bcb"),
                 item("I-novo", "anbima-novo", fonte="anbima"), item("G-novo", "lei-1", fonte="leis")]
        crit, por = self.rodar(itens)
        diogo = {x["id"]: x for x in ler(self.saida, "itens-diogo.json")["itens"]}
        self.assertEqual(set(diogo), {"cvm-res-89", "cvm-res-90", "bcb-res-999", "anbima-novo", "lei-1"})
        self.assertTrue(all(x["o_que_seria_feito"] for x in diogo.values()))
        self.assertTrue(all(x["condicoes"]["1-classes"] == "falha" for x in por.values()))
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_h_novo_fora_vai_para_decisoes(self):
        _, r = self.um([item("H-novo", "bcb-res-999", dados={"perimetro": "fora"}, fonte="bcb")])
        self.assertEqual(r["estado"], "fora")
        self.assertEqual(ler(self.raiz, "fontes/decisoes.json")[0]["classe"], "H-novo")


# ---------------------------------------------------------------- critério

class TestCriterio(Base):
    def test_sem_llm_julgado_vai_ao_diogo_sem_baixar(self):
        _, r = self.um([j("cvm-col-1")], sem_llm=True)
        self.assertFalse(r["automatico"])
        self.assertEqual(r["motivo"], "LLM indisponível")
        self.assertNotIn("julgados_baixar.py", [c[0] for c in self.sim.chamadas])
        self.assertEqual(ler(self.raiz, "fontes/julgados-inventario.json"), [])

    def test_sem_llm_classe_c(self):
        it = b1()
        it["classe"] = "C"
        _, r = self.um([it], sem_llm=True)
        self.assertIn("LLM indisponível", r["motivo"])

    def test_teto_de_julgados_processa_os_mais_antigos(self):
        crit, por = self.rodar([j("cvm-col-c", "2026-11-03"), j("cvm-col-a", "2026-11-01"),
                                j("cvm-col-b", "2026-11-02")], max_julgados=2)
        self.assertEqual(sorted(x["id"] for x in crit["itens"]), ["cvm-col-a", "cvm-col-b"])
        self.assertIn("adiados", ler(self.saida, "resumo.md"))
        self.assertFalse(os.path.exists(os.path.join(self.raiz, cam_j("cvm-col-c"))))
        self.assertFalse(crit["conjunto"]["pr_automatico_antes_do_ci"])
        self.assertTrue(any("volume acima do teto: possível mudança de formato da fonte" in m
                            for m in crit["conjunto"]["motivos"]), crit["conjunto"]["motivos"])

    def test_condicao_3_gate_vermelho(self):
        self.sim.rc["unittest"] = 1
        crit, r = self.um([b1()])
        self.assertEqual(r["condicoes"]["3-gate"], "falha")
        self.assertFalse(r["automatico"])
        self.assertTrue(any(m.startswith("gate:") for m in crit["conjunto"]["motivos"]))
        self.sim.rc = {"indice.py": 1}
        crit, _ = self.rodar([b1()])
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_condicao_4_varredura_cpf(self):
        self.sim.julgado_extra["cvm-col-1"] = "Inscrito no CPF sob o nº %s." % CPF_FICTICIO
        crit, r = self.um([j("cvm-col-1")])
        self.assertEqual(r["condicoes"]["4-varredura"], "falha")
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_condicao_4_caractere_de_controle(self):
        self.sim.julgado_extra["cvm-col-1"] = "texto" + chr(1)
        _, r = self.um([j("cvm-col-1")])
        self.assertEqual(r["condicoes"]["4-varredura"], "falha")

    def test_condicao_5_revisor_marcou(self):
        self.sim.revisor["cvm-col-1"] = {"ok": False, "alertas": [{"trecho": "nome de parte"}]}
        _, r = self.um([j("cvm-col-1")])
        self.assertEqual(r["condicoes"]["5-revisor"], "falha")
        self.assertIn("revisor marcou", r["motivo"])
        self.assertFalse(os.path.exists(os.path.join(self.raiz, cam_j("cvm-col-1"))))
        self.assertEqual(ler(self.raiz, "fontes/julgados-inventario.json"), [])

    def test_extracao_com_ementa_do_titulo_vai_ao_diogo(self):
        self.sim.do_titulo.add("cvm-col-1")
        _, r = self.um([j("cvm-col-1")])
        self.assertFalse(r["automatico"])
        self.assertIn("ementa do título", r["motivo"])
        self.assertNotIn("revisor.py", [c[0] for c in self.sim.chamadas])

    def test_condicao_6_arquivo_fora_do_esperado(self):
        self.sim.extra_tv = NORMAS + "/cvm/resolucoes/0093.md"
        crit, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13")])
        self.assertEqual(r["condicoes"]["6-arquivos"], "falha")
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_condicao_6_julgado_existente_reescrito(self):
        self.sim.reescrever = cam_j("cvm-col-20260101-d1")
        crit, _ = self.rodar([j("cvm-col-1")])
        self.assertTrue(any("julgado existente reescrito" in m for m in crit["conjunto"]["motivos"]))
        self.assertFalse(crit["conjunto"]["pr_automatico"])

    def test_condicao_7_teto_de_normas(self):
        itens = [b1(250 + k, "cvm-res-%d" % (88 + k)) for k in range(6)]
        for k in range(6):
            self.rotas["https://conteudo.cvm.gov.br/legislacao/resolucoes/resol%d.html" % (250 + k)] = ok(fx("cvm-resolucao-249.html"))
            itens[k]["url"] = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol%d.html" % (250 + k)
        crit, por = self.rodar(itens)
        self.assertEqual(crit["conjunto"]["normas_alteradas"], 6)
        self.assertTrue(all(x["condicoes"]["7-teto"] == "falha" for x in por.values()))
        self.assertFalse(crit["conjunto"]["pr_automatico"])
        crit, _ = self.rodar(itens[:5])
        self.assertTrue(crit["conjunto"]["pr_automatico_antes_do_ci"], crit["conjunto"]["motivos"])

    def test_item_do_diogo_sem_arquivo_nao_trava_o_pr_do_dia(self):
        crit, por = self.rodar([b1(), item("D", "cvm-res-300", ["cvm-res-300"])])
        d = next(x for x in por.values() if x["id"] == "cvm-res-300")
        self.assertFalse(d["automatico"])
        self.assertEqual([x["id"] for x in ler(self.saida, "itens-diogo.json")["itens"]], ["cvm-res-300"])
        self.assertTrue(crit["conjunto"]["pr_automatico_antes_do_ci"], crit["conjunto"]["motivos"])

    def test_so_item_do_diogo_nao_e_pr_automatico(self):
        crit, _ = self.um([item("D", "cvm-res-300", ["cvm-res-300"])])
        self.assertFalse(crit["conjunto"]["pr_automatico_antes_do_ci"])
        self.assertIn("nenhum item automático", crit["conjunto"]["motivos"])

    def c251(self):
        url = "https://conteudo.cvm.gov.br/legislacao/resolucoes/resol251.html"
        self.rotas[url] = ok(fx("cvm-resolucao-249.html"))
        c = b1(251, "cvm-res-89")
        c["classe"], c["url"] = "C", url
        return c

    def test_classe_c_aviso_e_pendente_sao_parte_automatica_do_pr_do_dia(self):
        c = self.c251()
        crit, por = self.rodar([b1(), c])
        x = por[at.chave(c)]
        self.assertFalse(x["automatico"])
        self.assertTrue(x["parte_automatica"])
        self.assertTrue(crit["conjunto"]["pr_automatico_antes_do_ci"], crit["conjunto"]["motivos"])
        auto = ler(self.saida, "itens-automaticos.json")["itens"]
        parte = [a for a in auto if a["id"] == "cvm-res-251"]
        self.assertEqual(len(parte), 1, auto)
        self.assertEqual((parte[0]["classe"], parte[0]["parte_de"]), ("B1", "C"))
        self.assertTrue(parte[0]["arquivos"])
        self.assertTrue(any("0089" in a for a in parte[0]["arquivos"]), parte[0]["arquivos"])
        diogo = ler(self.saida, "itens-diogo.json")["itens"]
        self.assertEqual([(d["id"], d["classe"], d["parte_automatica"]) for d in diogo],
                         [("cvm-res-251", "C", True)])
        self.assertIn("replay manual", ler(self.saida, "resumo.md"))

    def test_classe_c_sozinha_abre_pr_do_dia_com_a_parte_automatica(self):
        crit, x = self.um([self.c251()])
        self.assertTrue(x["parte_automatica"])
        self.assertTrue(crit["conjunto"]["pr_automatico_antes_do_ci"], crit["conjunto"]["motivos"])

    def test_classe_c_com_condicao_em_falha_trava_o_pr_do_dia(self):
        c = self.c251()
        real = at.varrer
        with mock.patch.object(at, "varrer", side_effect=lambda amb, arqs: (
                ["dado pessoal em %s" % arqs[0]] if any("0089" in a for a in arqs) else real(amb, arqs))):
            crit, por = self.rodar([b1(), c])
        x = por[at.chave(c)]
        self.assertFalse(x["parte_automatica"])
        self.assertEqual(x["condicoes"]["4-varredura"], "falha")
        self.assertFalse(crit["conjunto"]["pr_automatico_antes_do_ci"])
        self.assertTrue(any(m.startswith("item do Diogo com arquivo no PR do dia: cvm-res-251")
                            for m in crit["conjunto"]["motivos"]), crit["conjunto"]["motivos"])
        self.assertNotIn("cvm-res-251", [a["id"] for a in ler(self.saida, "itens-automaticos.json")["itens"]])

    def test_classe_c_sem_aviso_aplicado_e_revertida(self):
        c = self.c251()
        c["norma_alvo"] = ["cvm-res-9999"]  # alvo fora do plugin: a parte B1 falha
        crit, x = self.um([c])
        self.assertFalse(x["parte_automatica"])
        self.assertEqual(ler(self.saida, "itens-automaticos.json")["itens"], [])
        self.assertNotIn("item do Diogo com arquivo", " ".join(crit["conjunto"]["motivos"]))
        self.assertIn("nenhum item automático", crit["conjunto"]["motivos"])

    def test_reversao_incompleta_do_item_do_diogo_trava_o_pr_do_dia(self):
        a = self.amb()
        r_auto = dict(at.novo_resultado(b1()), estado="automatico", arquivos=[])
        r_d = dict(at.novo_resultado(item("A", "cvm-res-249", ["cvm-res-249"])), estado="diogo",
                   motivo="x", arquivos=[], nao_revertidos=[NORMAS + "/cvm/resolucoes/0249.md"])
        crit = at.criterio(a, {r_auto["chave"]: r_auto, r_d["chave"]: r_d}, [], [], {})
        self.assertFalse(crit["conjunto"]["pr_automatico_antes_do_ci"])
        self.assertTrue(any("cvm-res-249" in m for m in crit["conjunto"]["motivos"]))

    def test_condicao_8_plugin_grande(self):
        with mock.patch.object(at, "LIMITE_ARQUIVOS", 3):
            crit, r = self.um([b1()])
        self.assertEqual(r["condicoes"]["8-plugins"], "falha")
        self.assertTrue(any("plugin acima" in m for m in crit["conjunto"]["motivos"]))

    def test_sombra_registra_decisao_do_criterio(self):
        crit, _ = self.rodar([b1()], sombra=True)
        c = ler(self.saida, "criterio.json")["conjunto"]
        self.assertTrue(c["sombra"])
        self.assertIn("decisão do critério", c["registro"])
        self.assertTrue(c["pr_automatico_antes_do_ci"])
        self.assertFalse(c["pr_automatico"])
        self.assertIn("sombra", ler(self.saida, "resumo.md"))

    def test_gate_roda_suite_sem_macos_validar_e_indice(self):
        self.rodar([b1()])
        nomes = [c[0] for c in self.sim.chamadas]
        self.assertIn("unittest", nomes)
        validar = [c[1][2] for c in self.sim.chamadas if c[0] == "validar.py"]
        self.assertIn(NORMAS, validar)
        self.assertTrue(any(v.endswith("julgados-colegiado-2016-2026/julgados") for v in validar))
        self.assertTrue(any(c[0] == "indice.py" and "--verificar" in c[1] for c in self.sim.chamadas))
        env = next(c for c in self.sim.chamadas if c[0] == "unittest")
        self.assertTrue(env)


# ---------------------------------------------------------------- rodada de correção 1

class TestCorrecao1(Base):
    def test_j_cobertura_ausente_ou_baixa_vai_ao_diogo(self):
        for confs, trecho in (([{"arquivo": "02-anexo.pdf", "cobertura": None,
                                 "conferencia": "sem conferência independente"}], "sem conferência independente"),
                              ([{"arquivo": "02-anexo.pdf", "cobertura": 0.98}], "abaixo de 99%"),
                              ([], "sem conferência de cobertura")):
            shutil.rmtree(self.raiz)
            montar_raiz(self.raiz)
            self.sim.cobertura_j["cvm-col-1"] = confs
            _, r = self.um([j("cvm-col-1")])
            self.assertFalse(r["automatico"])
            self.assertEqual(r["condicoes"]["2-conferencia"], "falha")
            self.assertIn(trecho, r["motivo"])
            self.assertFalse(os.path.exists(os.path.join(self.raiz, cam_j("cvm-col-1"))))

    def test_h_sem_versao_bcb_e_falha(self):
        self.rotas[ibcb.NORMA + "p1=Resolu%C3%A7%C3%A3o+BCB&p2=102"] = ok(fx("bcb-norma.json"))
        self.sim.tv["bcb-res-102"] = {"versao_bcb": False}
        antes = ler(self.raiz, "fontes/acervo-bcb.json")
        _, r = self.um([item("H", "bcb-res-102", ["bcb-res-102"], "", dados={"versao": 6.0}, fonte="bcb")])
        self.assertFalse(r["automatico"])
        self.assertIn("versao_bcb", r["motivo"])
        self.assertEqual(ler(self.raiz, "fontes/acervo-bcb.json"), antes)

    def test_texto_vigente_rc_diferente_de_zero_e_falha(self):
        self.sim.rc["texto_vigente.py"] = 1
        _, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13")])
        self.assertFalse(r["automatico"])
        self.assertIn("texto_vigente rc 1", r["motivo"])

    def test_relatorio_do_texto_vigente_de_execucao_anterior_nao_vale(self):
        gj(os.path.join(self.saida, "tv-camada-1.json"), [
            {"id": "cvm-res-249", "arquivo": "cvm/resolucoes/0249.md", "resultado": "ok", "cobertura": 1.0,
             "conferencia_independente": True, "nivel_verificacao": "fonte-oficial"}])
        self.sim.tv["cvm-res-249"] = {"sem_entrada": True}
        _, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13")])
        self.assertFalse(r["automatico"])
        self.assertIn("sem entrada", r["motivo"])

    def test_extracao_le_so_os_lotes_desta_execucao(self):
        gj(os.path.join(self.saida, "extracao", "20261103T180000-1", "lote-001", "validacao.json"),
           {"aplicados": {"cvm-col-1": True}, "ementa_do_titulo": []})
        gj(os.path.join(self.saida, "extracao", "lote-001", "validacao.json"),
           {"aplicados": {"cvm-col-1": True}, "ementa_do_titulo": []})
        self.sim.extracao_aplica = False
        _, r = self.um([j("cvm-col-1")])
        self.assertFalse(r["automatico"])
        self.assertIn("não aplicada", r["motivo"])

    def test_saidas_velhas_apagadas_e_excecao_sai_com_rc(self):
        for nome in at.SAIDAS:
            gravar(self.saida, nome, "velho\n")
        det = os.path.join(self.tmp, "deteccao.json")
        dt.gravar_json(det, {"fontes": {"cvm": {}}, "itens": [b1()]})
        with mock.patch.object(at, "aplicar", side_effect=RuntimeError("quebrou")):
            rc = at.main(["--deteccao", det, "--raiz", self.raiz, "--saida", self.saida],
                         rodar=self.sim, rede=Rede(self.rotas))
        self.assertNotEqual(rc, 0)
        self.assertFalse(any(os.path.exists(os.path.join(self.saida, n)) for n in at.SAIDAS))

    def test_execucao_id_em_todas_as_saidas(self):
        a = self.amb()
        at.executar(a, [b1()])
        self.assertRegex(a.execucao_id, r"^\d{8}T\d{6}-\d+$")
        for nome in ("criterio.json", "itens-automaticos.json", "itens-diogo.json"):
            self.assertEqual(ler(self.saida, nome)["execucao_id"], a.execucao_id)
        self.assertIn(a.execucao_id, ler(self.saida, "resumo.md"))

    def test_ci_pendente_deixa_pr_automatico_falso(self):
        crit, _ = self.rodar([b1()])
        c = crit["conjunto"]
        self.assertFalse(c["pr_automatico"])
        self.assertTrue(c["pr_automatico_antes_do_ci"])
        self.assertIn("CI pendente (condição 9)", c["motivos"])

    def test_gate_cria_sem_macos_bin_na_saida(self):
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "dados", "sem-macos-bin")))
        self.rodar([b1()])
        path = self.sim.envs["unittest"]["PATH"]
        self.assertEqual(path, os.path.join(self.saida, "sem-macos-bin"))
        self.assertEqual(sorted(os.listdir(path)), ["git", "python3"])
        self.assertTrue(all(os.path.islink(os.path.join(path, n)) for n in os.listdir(path)))

    def test_varredura_tambem_nos_json(self):
        a = self.amb()
        gravar(self.raiz, "fontes/x.json", {"nome": "CPF " + CPF_FICTICIO, "t": "a" + chr(1)})
        falhas = at.varrer(a, ["fontes/x.json"])
        self.assertTrue(any("CPF" in f for f in falhas), falhas)
        self.assertTrue(any("controle" in f for f in falhas), falhas)
        gravar(self.raiz, "fontes/y.json", "{quebrado")
        self.assertEqual(at.varrer(a, ["fontes/y.json"]), ["fontes/y.json: JSON ilegível"])

    def test_plugin_json_nao_fica_isento_da_condicao_6(self):
        self.assertFalse(at.e_indice("plugins/normas/.claude-plugin/plugin.json"))
        self.assertFalse(at.e_indice(".claude-plugin/marketplace.json"))
        self.sim.extra_tv = "plugins/normas/.claude-plugin/plugin.json"
        crit, r = self.um([item("A", "cvm-res-249", ["cvm-res-249"], URL_249, "2026-10-13")])
        self.assertEqual(r["condicoes"]["6-arquivos"], "falha")
        self.assertFalse(crit["conjunto"]["pr_automatico_antes_do_ci"])

    def test_marketplace_json_mudado_sem_item_bloqueia(self):
        gravar(self.raiz, ".claude-plugin/marketplace.json", {"plugins": []})
        a = self.amb()
        with mock.patch.object(at, "aplicar", side_effect=lambda amb, itens: (
                gravar(self.raiz, ".claude-plugin/marketplace.json", {"plugins": ["x"]}) or ({}, []))):
            crit = at.executar(a, [])
        self.assertIn("arquivo sem item: .claude-plugin/marketplace.json", crit["conjunto"]["motivos"])

    def test_g_sem_baixado_em_e_falha(self):
        it = TestClasses.lei(self, remover="baixado_em:")
        _, r = self.um([it])
        self.assertFalse(r["automatico"])
        self.assertIn("baixado_em", r["motivo"])

    def test_j_ao_diogo_restaura_julgado_existente_sobrescrito(self):
        rel = cam_j("cvm-col-20260101-d1")
        antes = ler(self.raiz, rel)
        self.sim.revisor["cvm-col-20260101-d1"] = {"ok": False, "alertas": ["x"]}
        _, r = self.um([j("cvm-col-20260101-d1", "2026-01-01")])
        self.assertFalse(r["automatico"])
        self.assertEqual(ler(self.raiz, rel), antes)


class TestApoio(unittest.TestCase):
    def test_uniao_das_deteccoes_vale_a_posterior_por_fonte(self):
        tmp = tempfile.mkdtemp()
        try:
            a, b = os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")
            dt.gravar_json(a, {"fontes": {"cvm": {}, "crsfn": {}}, "itens": [
                {"fonte": "cvm", "id": "x"}, {"fonte": "crsfn", "id": "velho"}]})
            dt.gravar_json(b, {"fontes": {"crsfn": {}}, "itens": [{"fonte": "crsfn", "id": "novo"}]})
            itens, _ = at.unir_deteccoes([a, b])
            self.assertEqual([i["id"] for i in itens], ["x", "novo"])
        finally:
            shutil.rmtree(tmp)

    def test_classe_b_por_consolidado(self):
        self.assertEqual(at.classe_efetiva({"classe": "B", "dados": {}}), "B1")
        self.assertEqual(at.classe_efetiva({"classe": "B", "dados": {"consolidado_novo": True}}), "B2")

    def test_linhas_sem_nota(self):
        diff = "+++ b/x\n+Art. 2º Novo. (Incluído pela Lei nº 14.000, de 2024)\n+Art. 3º Sem nota.\n+id: x"
        self.assertEqual(at.linhas_sem_nota(diff, 2020), ["Art. 3º Sem nota."])
        self.assertEqual(len(at.linhas_sem_nota(diff, 2025)), 2)

    def test_indice_md_com_pendentes(self):
        pend = [{"norma": "cvm-res-88", "ato": "Resolução CVM 250", "ato_url": URL_250,
                 "data_dou": "2026-11-04", "data_deteccao": HOJE}]
        md = "\n".join(indice._md_resumo({}, 0, pend) if _aceita_pendentes() else indice._md_pendentes(pend))
        self.assertIn("## Atos publicados ainda não aplicados", md)
        self.assertIn("| cvm-res-88 | [Resolução CVM 250](%s) | 2026-11-04 | %s |" % (URL_250, HOJE), md)
        self.assertEqual(indice._md_pendentes([]), [])


def _aceita_pendentes():
    import inspect
    return "pendentes" in inspect.signature(indice._md_resumo).parameters


if __name__ == "__main__":
    unittest.main()
