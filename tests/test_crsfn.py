"""Testes do crsfn.py (classificação por órgão e conversão dos acórdãos da CVM), sem rede e
sem macOS: o cliente HTTP e o PDFKit são falsos; as fontes são 4 itens reais do CRSFN."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from contextlib import redirect_stderr

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import crsfn  # noqa: E402
import julgados_extracao as je  # noqa: E402
import pdf_macos  # noqa: E402
import validar  # noqa: E402

FIX = os.path.join(AQUI, "fixtures", "crsfn")


def setUpModule():
    # lista positiva hermética: sem os dados abertos de dados/
    je._PESSOAS_PADRAO = je.Pessoas(acusados={}, partes_tc={}, descricoes={})


def tearDownModule():
    je._PESSOAS_PADRAO = None
PREF = ("https://www.gov.br/fazenda/pt-br/composicao/orgaos/orgaos-colegiados/crsfn/servicos/"
        "busca-de-ata-pautas-distribuicoes-e-decisoes/acordaos-e-decisoes-monocraticas/")


def item(ano, caminho, titulo, recurso=None, orgao="INDETERMINADO",
         criterio="sem critério na listagem", tipo="recurso/processo", nup_titulo=None):
    return {"ano": ano, "item_url": PREF + caminho, "titulo": titulo, "tipo": tipo,
            "recurso": recurso, "nup_titulo": nup_titulo, "processo_origem": None,
            "orgao": orgao, "criterio": criterio, "data_sessao": None}


I1999 = item(1999, "1999/175a-sessao-de-julgamento/recurso-2613", "Recurso 2613", 2613)
I2005 = item(2005, "2005/250a-sessao-de-julgamento/recurso-5279", "Recurso 5279", 5279)
ISEI = item(2023, "2023/471a-sessao-de-julgamento/processo-10372-100012-2021-00",
            "Processo 10372.100012/2021-00", nup_titulo="10372.100012/2021-00")
IBCB = item(2021, "2021/453a-sessao-de-julgamento/recurso-sei-10372-100124-2021-52",
            "Recurso SEI 10372.100124/2021-52", orgao="BCB",
            criterio="abertura do item (amostra)", nup_titulo="10372.100124/2021-52")
ICOAF = item(2019, "2019/440a-sessao-de-julgamento/processo-11893-000123-2018-11",
             "Processo 11893.000123/2018-11", orgao="COAF", criterio="prefixo NUP 11893",
             nup_titulo="11893.000123/2018-11")


def ler(nome, modo="rb"):
    with open(os.path.join(FIX, nome), modo) as f:
        return f.read()


class ClienteFalso:
    def __init__(self, rotas):
        self.rotas, self.n, self.pedidos = rotas, 0, []

    def get(self, url):
        self.n += 1
        self.pedidos.append(url)
        if url not in self.rotas:
            raise OSError("404 %s" % url)
        dados, cab, final = self.rotas[url]
        return dados, cab, final or url


def rotas():
    pdf = {"content-type": "application/pdf"}
    sei = "https://sei.economia.gov.br/sei/publicacoes/controlador_publicacoes.php?x=1"
    return {
        I1999["item_url"] + "/@@download/file": (ler("pdf-1999-recurso-2613.pdf"), pdf, None),
        I2005["item_url"] + "/@@download/file": (ler("pdf-2005-recurso-5279.pdf"), pdf, None),
        ISEI["item_url"]: (ler("sei-cvm-10372-100012-2021-00.html"),
                           {"content-type": "text/html; charset=iso-8859-1"}, sei),
        IBCB["item_url"]: (ler("sei-bcb-10372-100124-2021-52.html"),
                           {"content-type": "text/html; charset=iso-8859-1"}, sei),
    }


class PdfFalso:
    """PDFKit falso: o texto de cada PDF do cache vem do .txt da fixture."""
    ErroPdfMacos = pdf_macos.ErroPdfMacos
    TEXTOS = {"crsfn-2613.pdf": "pdf-1999-recurso-2613.txt",
              "crsfn-5279.pdf": "pdf-2005-recurso-5279.txt"}

    def texto_pdfkit(self, path):
        return ler(self.TEXTOS[os.path.basename(path)], "r")

    def ocr(self, path, detalhe=False):
        raise pdf_macos.ErroPdfMacos("sem macOS")


class Base(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.cam = crsfn.caminhos(self.raiz)
        self.inv = [I1999, I2005, ISEI, IBCB, ICOAF]
        os.makedirs(os.path.dirname(self.cam["inventario"]))
        with open(self.cam["inventario"], "w", encoding="utf-8") as f:
            json.dump({"n": len(self.inv), "itens": self.inv}, f)
        self.cli = ClienteFalso(rotas())
        self.log = []

    def tearDown(self):
        shutil.rmtree(self.raiz)

    def rodar(self, *args):
        with redirect_stderr(io.StringIO()):
            return crsfn.main(list(args), cliente=self.cli, raiz=self.raiz, pm=PdfFalso(),
                              log=self.log.append)

    def classif(self):
        with open(self.cam["classificacao"], encoding="utf-8") as f:
            return json.load(f)["itens"]


class TestIds(unittest.TestCase):
    def test_bases(self):
        self.assertEqual(crsfn.id_base(I2005), "crsfn-5279")
        self.assertEqual(crsfn.id_base(item(2015, "x", "Recurso 14.485")), "crsfn-14485")
        self.assertEqual(crsfn.id_base(item(2015, "x", "Revisão 2168", tipo="revisao")),
                         "crsfn-revisao-2168")
        self.assertEqual(crsfn.id_base(item(2010, "x", "EDCL Recurso 9001", 9001, tipo="embargos")),
                         "crsfn-edcl-9001")
        self.assertEqual(crsfn.id_base(item(2014, "x", "Acórdão 9572")), "crsfn-acordao-9572")
        self.assertEqual(crsfn.id_base(item(2015, "x", "Decisão Monocrática 13.977")),
                         "crsfn-monocratica-13977")
        self.assertEqual(crsfn.id_base(ISEI), "crsfn-10372-100012-2021-00")

    def test_colisao_em_ordem_estavel(self):
        dup = dict(ISEI, item_url=PREF + "2023/475a-sessao-de-julgamento/processo-10372-100012-2021-00")
        pares = crsfn.atribuir_ids([dup, ISEI])
        self.assertEqual([i for i, _ in pares],
                         ["crsfn-10372-100012-2021-00", "crsfn-10372-100012-2021-00-2"])
        self.assertIs(pares[0][1], ISEI)


class TestClassificar(Base):
    def test_orgaos_e_processo(self):
        self.assertEqual(self.rodar("classificar"), 0)
        c = self.classif()
        self.assertEqual(c["crsfn-2613"]["orgao"], "CVM")
        self.assertEqual(c["crsfn-5279"]["orgao"], "CVM")
        self.assertEqual(c["crsfn-10372-100012-2021-00"]["orgao"], "CVM")
        self.assertEqual(c["crsfn-10372-100124-2021-52"]["orgao"], "BCB")
        self.assertEqual(c["crsfn-5279"]["processo"], "rj2002-5101")
        self.assertEqual(c["crsfn-2613"]["processo_origem"], "97/0873")
        sei = c["crsfn-10372-100012-2021-00"]
        self.assertEqual(sei["processo"], "19957-007543-2019-03")
        self.assertEqual(sei["nup"], "19957-007543-2019-03")
        self.assertIn("rj2019-5673", sei["processos"])
        self.assertIn("preâmbulo", sei["criterio"])

    def test_prefixo_nup_sem_download(self):
        self.rodar("classificar", "--ids", "crsfn-11893-000123-2018-11")
        c = self.classif()["crsfn-11893-000123-2018-11"]
        self.assertEqual(c["orgao"], "COAF")
        self.assertIn("sem download", c["criterio"])
        self.assertEqual(self.cli.n, 0)

    def test_retomada_sem_requisicao(self):
        self.rodar("classificar", "--limite", "2")
        self.assertEqual(len(self.classif()), 2)
        n = self.cli.n
        self.rodar("classificar", "--limite", "2")
        self.assertEqual(len(self.classif()), 4)
        self.assertEqual(self.cli.n, n + 1)  # COAF (sem download) e BCB (1 requisição)
        self.rodar("classificar")
        self.assertEqual(len(self.classif()), 5)
        self.assertEqual(self.cli.n, n + 2)  # só o SEI da CVM; os já feitos não baixam

    def test_ligacoes(self):
        self.rodar("classificar")
        with open(self.cam["ligacoes"], encoding="utf-8") as f:
            lig = json.load(f)["ligacoes"]
        self.assertEqual(lig["rj2002-5101"], ["crsfn-5279"])
        self.assertEqual(lig["19957-007543-2019-03"], ["crsfn-10372-100012-2021-00"])
        self.assertEqual(lig["rj2019-5673"], ["crsfn-10372-100012-2021-00"])
        self.assertNotIn("crsfn-10372-100124-2021-52", sum(lig.values(), []))

    def test_sinais(self):
        self.assertEqual(crsfn.orgao_por_sinais("RECORRIDO: BANCO CENTRAL DO BRASIL")[0], "BCB")
        self.assertEqual(crsfn.orgao_por_sinais("Processo CVM RJ2002/5101")[0], "CVM")
        o, crit = crsfn.orgao_por_sinais("Processo BCB 1234 RECORRIDO: COMISSÃO DE VALORES MOBILIÁRIOS")
        self.assertEqual(o, "INDETERMINADO")
        self.assertIn("conflitantes", crit)
        self.assertEqual(crsfn.orgao_por_sinais("Recurso 1")[1], "sem sinal no preâmbulo")

    def test_processo_de_origem_da_cvm_decide_o_conflito(self):
        # acórdão antigo: modelo com "RECORRIDO: BANCO CENTRAL", processo de origem da CVM
        for texto in ("Processo origem CVM 95/1449 RECURSOS VOLUNTÁRIOS RECORRIDO: BANCO CENTRAL DO BRASIL",
                      "Processo BCB CVM RJ/2001/007686 RECORRIDA: COMISSÃO DE VALORES MOBILIÁRIOS e BACEN",
                      "Processo na primeira instância CVM 08/2009 EMBARGADO: CONSELHO; BANCO CENTRAL"):
            o, crit = crsfn.orgao_por_sinais(texto)
            self.assertEqual(o, "CVM", texto)
            self.assertIn("processo de origem da CVM", crit)
        # processo do BCB com a CVM só citada continua em conflito
        self.assertEqual(crsfn.orgao_por_sinais("Processo BCB 0301203449 RECORRIDO: COMISSÃO DE "
                                                "VALORES MOBILIÁRIOS; Banco Central")[0], "INDETERMINADO")


class TestConverter(Base):
    def setUp(self):
        super().setUp()
        self.rodar("classificar")
        self.rodar("converter")
        rels = os.listdir(self.cam["relatorios"])
        with open(os.path.join(self.cam["relatorios"], rels[0]), encoding="utf-8") as f:
            self.rel = {x["id"]: x for x in json.load(f)["itens"]}

    def arquivo(self, id_):
        with open(os.path.join(self.raiz, self.rel[id_]["arquivo"]), encoding="utf-8") as f:
            return f.read()

    def fm(self, id_):
        txt = self.arquivo(id_)
        pares, _, _ = validar.ler_frontmatter(txt)
        return dict(pares)

    def test_so_cvm_e_caminho(self):
        self.assertEqual(sorted(self.rel), ["crsfn-10372-100012-2021-00", "crsfn-2613", "crsfn-5279"])
        self.assertEqual(self.rel["crsfn-5279"]["arquivo"],
                         os.path.join("plugins", crsfn.jc.caminho_relativo("acordao-crsfn", "crsfn-5279", 2005)))
        self.assertTrue(self.rel["crsfn-5279"]["arquivo"].endswith("/julgados/crsfn/2005/5279.md"))

    def test_reconversao_preserva_o_tema_extraido(self):
        caminho = os.path.join(self.raiz, self.rel["crsfn-5279"]["arquivo"])
        v, corpo = je.ler_julgado(caminho)
        v.update(tema="processual", tema_fonte="extracao")
        je.gravar(caminho, {k: v.get(k, "") for k in crsfn.jc.CAMPOS}, corpo)
        self.rodar("converter", "--ids", "crsfn-5279")
        v, _ = je.ler_julgado(caminho)
        self.assertEqual((v["tema"], v["tema_fonte"]), ("processual", "extracao"))

    def test_valido_pelo_validador(self):
        for id_ in self.rel:
            caminho = os.path.join(self.raiz, self.rel[id_]["arquivo"])
            self.assertEqual(validar.validar_julgado(caminho), [], id_)

    def test_secoes(self):
        self.assertEqual(self.rel["crsfn-5279"]["secoes"],
                         ["Texto", "Ementa", "Relatório", "Voto", "Acórdão"])
        self.assertEqual(self.rel["crsfn-2613"]["secoes"], ["Texto", "Ementa", "Acórdão"])
        self.assertEqual(self.rel["crsfn-10372-100012-2021-00"]["secoes"],
                         ["Texto", "Ementa", "Acórdão", "Relatório", "Voto"])

    def test_metadados(self):
        a, b, s = self.fm("crsfn-2613"), self.fm("crsfn-5279"), self.fm("crsfn-10372-100012-2021-00")
        self.assertEqual((a["data"], a["resultado"], a["processo"]), ("1999-07-29", "absolvicao", "97/0873"))
        self.assertEqual((b["data"], b["resultado"], b["processo"]), ("2005-06-28", "condenacao", "RJ2002/5101"))
        self.assertEqual(b["relator"], "SILVÂNIO COVAS")
        self.assertEqual((s["data"], s["resultado"]), ("2023-05-09", "condenacao"))
        self.assertEqual(s["processo"], "19957.007543/2019-03; RJ2019/5673")
        self.assertEqual(s["nup"], "19957-007543-2019-03")
        self.assertEqual(s["relator"], "Sérgio Varella Bruna")
        self.assertEqual(s["ementa_fonte"], "crsfn")
        self.assertTrue(s["ementa"].startswith("RECURSO VOLUNTÁRIO. MANIPULAÇÃO DE PREÇOS."))
        self.assertTrue(b["ementa"].endswith("Apelos a que se nega provimento."))
        self.assertEqual(s["nivel_verificacao"], "html-convertido")
        self.assertEqual(b["nivel_verificacao"], "pdf-extraido")
        self.assertEqual(len(s["sha256_fonte"]), 64)

    def test_timbre_e_rodape_fora(self):
        s = self.arquivo("crsfn-10372-100012-2021-00")
        for lixo in ("MINISTÉRIO DA FAZENDA", "Conselho de recursos do Sistema financeiro nacional",
                     "Documento assinado eletronicamente", "código CRC", "Boletim de Serviço",
                     "@md_crsfn", "Modalidade(s)"):
            self.assertNotIn(lixo, s)
        self.assertIn("# Processo 10372.100012/2021-00\n", s)
        self.assertIn("## Voto\n", s)

    def test_cobertura_html(self):
        cob = self.rel["crsfn-10372-100012-2021-00"]["cobertura"]
        self.assertIsNotNone(cob)
        self.assertGreaterEqual(cob, 0.9)

    def test_resultado_regras(self):
        self.assertEqual(crsfn.resultado("RECURSO VOLUNTÁRIO", "negar provimento ao recurso"), "condenacao")
        self.assertEqual(crsfn.resultado("RECURSO DE OFÍCIO", "negar provimento ao recurso"), "absolvicao")
        self.assertEqual(crsfn.resultado("RECURSO VOLUNTÁRIO", "dar provimento parcial"), "")
        self.assertEqual(crsfn.resultado("RECURSO VOLUNTÁRIO", "negar provimento, reconhecida a prescrição"), "")
        self.assertEqual(crsfn.resultado("RECURSO VOLUNTÁRIO E RECURSO DE OFÍCIO", "negar provimento"), "")
        self.assertEqual(crsfn.resultado("RECURSO VOLUNTÁRIO", "negar-lhe provimento. Vencido o Relator, "
                                         "que votou por dar parcial provimento."), "condenacao")


class TestSecoes(unittest.TestCase):
    def test_cabecalhos_de_voto_e_documento_sem_cabecalho_conhecido(self):
        docs = ["1ª Sessão\nRECURSO VOLUNTÁRIO\nEMENTA: Ementa.\nACÓRDÃO CRSFN 1/2020\nVistos.",
                "MINISTÉRIO DA FAZENDA\nRECURSO VOLUNTÁRIO\nRELATÓRIO\nFatos.\nDECISÃO\nDa CVM.",
                "MINISTÉRIO DA FAZENDA\nEMENTA: Outra.\nVoto dA relatorA\nRazões.",
                "MINISTÉRIO DA FAZENDA\nVOTO-VISTA\nDivirjo."]
        secs, retirado = crsfn.secoes(docs)
        self.assertEqual([n for n, _ in secs], ["Texto", "Ementa", "Acórdão", "Relatório", "Voto"])
        self.assertIn("Da CVM.", dict(secs)["Relatório"])  # DECISÃO depois do relatório não abre seção
        self.assertTrue(dict(secs)["Voto"].startswith("EMENTA: Outra."))
        self.assertIn("Divirjo.", dict(secs)["Voto"])
        self.assertEqual(len(retirado), 3)

    def test_datas(self):
        cands = crsfn.datas_candidatas("Sem data", "attachment; filename*=UTF-8''362%C2%AA%20Sess%C3%A3o"
                                       "%20-%2021%20de%20janeiro%20de%202014%20-%20Recurso.pdf")
        self.assertEqual(crsfn.escolher_data(cands, 2014), ("2014-01-21", ""))
        d, aviso = crsfn.escolher_data([("2013-12-10", "fecho")], 2014)
        self.assertEqual(d, "2013-12-10")
        self.assertIn("fora do ano", aviso)


class TestEmentaSemPessoas(unittest.TestCase):
    def test_nome_do_acusado_sai_da_ementa_do_frontmatter(self):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta)
        html = ler("sei-cvm-10372-100012-2021-00.html").replace(
            b"interna da BSM.", b"interna da BSM sobre Fulano Exemplar Teste.")
        cam = os.path.join(pasta, "fonte.html")
        with open(cam, "wb") as f:
            f.write(html)
        lista = je.Pessoas(acusados={"19957007543201903": ["Fulano Exemplar Teste"]},
                           partes_tc={}, descricoes={})
        reg = {"id": "crsfn-10372-100012-2021-00"}
        with mock.patch.object(je, "_PESSOAS_PADRAO", lista):
            valores, corpo, _ = crsfn.converter_item(reg, ISEI, cam, {}, PdfFalso())
        self.assertIn("Apuração interna da BSM sobre [pessoa física].", valores["ementa"])
        self.assertEqual(valores["ementa_fonte"], "crsfn")
        self.assertIn(je.AVISO_EMENTA, valores["incerteza"])
        self.assertIn("Apuração interna da BSM sobre Fulano Exemplar Teste.", corpo)
        self.assertEqual(corpo.count("## Ementa\n"), 1)


class TestPii(unittest.TestCase):
    def test_pii_no_corpo(self):
        cpf = "123" + ".456." + "789-09"
        secs, _ = crsfn.secoes(["EMENTA: Teste.\nACÓRDÃO/CRSFN 1/05: CPF " + cpf + " decidiu."])
        corpo = crsfn.pii.limpar("\n".join(t for _, t in secs))
        self.assertNotIn(cpf, corpo)


if __name__ == "__main__":
    unittest.main()
