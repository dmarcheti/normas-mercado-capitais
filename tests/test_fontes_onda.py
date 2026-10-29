"""Testes das fontes da Onda 1 (scripts/fontes_onda.py), sem rede e sem PDFKit.

O texto de PDF é sintético, no formato que o PDFKit devolve para os PDFs da CVM: páginas
separadas por \\f, endereço da CVM e título corrente no topo de cada página, número de
página no fim e a assinatura eletrônica depois do último artigo.
"""
import hashlib
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import fontes_onda as fo  # noqa: E402


def pagina(n, dou=None, alteradoras=(), retificada=(), original=(), consolidado=None):
    return {"data": "2021-01-0%d" % (n % 9 + 1), "dou": dou or "2021-02-0%d" % (n % 9 + 1),
            "url_original": list(original), "url_consolidado": consolidado or {},
            "alteradoras": [{"numero": a} for a in alteradoras],
            "retificada_dou": list(retificada), "url_ato": {"docx": "https://cvm/resol%03d.docx" % n}}


class TestInventario(unittest.TestCase):
    def test_links_consolidado_le_rotulos_html_pdf_doc(self):
        html = ('<a href="/export/sites/cvm/legislacao/resolucoes/anexos/200/resol210.pdf">[PDF]</a>'
                '<a href="/legislacao/resolucoes/anexos/200/resol210consolid.htm">[HTML]</a>'
                '<a href="/export/sites/cvm/legislacao/resolucoes/anexos/200/resol210consolid.pdf">[PDF]</a>'
                '<a href="/export/sites/cvm/legislacao/resolucoes/anexos/200/resol210consolid.docx">[DOC]</a>'
                '<a href="/legislacao/resolucoes/anexos/200/resol2100consolid.htm">outra</a>')
        cons, orig = fo.links_consolidado(html, 210)
        self.assertEqual(sorted(cons), ["docx", "htm", "pdf"])
        self.assertTrue(cons["htm"].startswith(fo.BASE + "/legislacao/"))
        self.assertEqual(len(orig), 1)
        self.assertTrue(orig[0].endswith("/resol210.pdf"))

    def test_montar_onda_campos_novos_e_manuais(self):
        paginas = {
            8: pagina(8, alteradoras=[15, 60, 59], retificada=["2020-10-20"]),
            15: pagina(15), 59: pagina(59, dou="2021-12-23"), 60: pagina(60, retificada=["2021-12-27"]),
        }
        htmls = {8: '<a href="/x/resol008consolid.doc">[DOC]</a><a href="/x/resol008.pdf">o</a>'}
        nomes = ["resolucao-cvm-n-15-de-19-de-janeiro-de-2021-299780465.md",
                 "resolucao-cvm-n-8-de-14-de-outubro-de-2020-283000000.md"]
        conhecidos = {59: {"dou": "2022-05-13", "dou_original": "2021-12-23", "url_dou": "https://manual"}}
        item = fo.montar_onda([8], paginas, htmls, nomes, conhecidos)[0]
        self.assertEqual(item["url_dou"], fo.DOU + "resolucao-cvm-n-8-de-14-de-outubro-de-2020-283000000")
        self.assertEqual(item["retificacoes"], [{"dou": "2020-10-20"}])
        self.assertEqual(list(item)[:5], ["id", "numero", "data", "dou", "url_dou"])
        self.assertTrue(item["url_consolidado"]["docx"].endswith(".doc"))
        self.assertEqual(len(item["url_original"]), 1)
        alts = {a["numero"]: a for a in item["alteradoras"]}
        self.assertEqual(alts[15]["url_dou"],
                         fo.DOU + "resolucao-cvm-n-15-de-19-de-janeiro-de-2021-299780465")
        self.assertEqual(alts[59]["dou"], "2022-05-13")  # campo manual vale sobre a página
        self.assertEqual(alts[59]["dou_original"], "2021-12-23")
        self.assertEqual(alts[59]["url_dou"], "https://manual")
        self.assertEqual(alts[60]["url_dou"], "")  # sem ctresb: vazio
        self.assertEqual(alts[60]["retificacoes"], [{"dou": "2021-12-27"}])
        self.assertEqual(alts[60]["norma_do_acervo"], fo.NORMAS_DO_ACERVO[60])
        self.assertNotIn("norma_do_acervo", alts[15])

    def test_acrescentar_preserva_existentes(self):
        existente = [{"id": "cvm-res-17", "numero": 17, "x": 1}]
        novas = [{"id": "cvm-res-17", "numero": 17, "x": 2}, {"id": "cvm-res-8", "numero": 8}]
        saida = fo.acrescentar(existente, novas)
        self.assertEqual(saida, [{"id": "cvm-res-17", "numero": 17, "x": 1}, {"id": "cvm-res-8", "numero": 8}])

    def test_conhecidos_e_onda(self):
        inv = [
            {"id": "cvm-res-17", "numero": 17, "alteradoras": [{"numero": 179, "dou": "d", "url_dou": "u"}]},
            {"id": "cvm-res-8", "numero": 8, "alteradoras": [{"numero": 15}, {"numero": 60}]},
            {"id": "cvm-res-44", "numero": 44, "alteradoras": [{"numero": 60, "outro": 1}]},
        ]
        self.assertEqual(fo.conhecidos_do_inventario(inv)[179], {"dou": "d", "url_dou": "u"})
        normas, atos = fo.onda(inv)
        self.assertEqual([n["numero"] for n in normas], [8, 44])
        self.assertEqual(list(atos), [15, 60])
        self.assertNotIn("outro", atos[60])  # primeira ocorrência


TEXTO_PDF = "\f".join([
    "SGS 1 Rio de Janeiro\nRESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021\n"
    "Dispõe sobre um assunto de teste e dá outras\nprovidências.\n"
    "O PRESIDENTE DA COMISSÃO DE VALORES MOBILIÁRIOS torna público que o Colegiado aprovou\n"
    "a seguinte Resolução:\n"
    "CAPÍTULO I – DISPOSIÇÕES GERAIS\n"
    "Art. 1o Esta Resolução dispõe sobre o assunto de teste, e o texto desta linha é longo o\n"
    "bastante para quebrar no meio da frase e continuar na linha de baixo, como no PDF da\n"
    "autarquia, que quebra as linhas pela largura da página.\n"
    "Art. 2º São deveres do participante, sem prejuízo de outros previstos na regulamentação:\n"
    "I – manter cadastro atualizado dos clientes e dos seus representantes legais perante a\n"
    "instituição;\nII – comunicar a emissão; e\nIII – guardar os documentos.\n1",
    "SGS 1 Rio de Janeiro\nRESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021\n"
    "Parágrafo único. A obrigação de que trata o caput vale também para quem, ao pedir, considera-\n"
    "se autor do pedido.\n"
    "Art. 3º Esta Resolução entra em vigor na data de sua publicação.\n"
    "Assinado eletronicamente por\nFULANO DE TAL\nPresidente\n"
    "ANEXO A À RESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021\n"
    "QUADRO DE INFORMAÇÕES\n"
    "Quadro de informações do emissor e do valor mobiliário objeto da oferta em questão\n"
    "I – nome do emissor;\nII – CNPJ.\n2",
])


class TestPdf(unittest.TestCase):
    def test_linhas_pdf_tira_cabecalho_pagina_e_assinatura(self):
        linhas = fo.linhas_pdf(TEXTO_PDF)
        self.assertEqual(linhas[0], "RESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021")  # título fica
        self.assertEqual(linhas.count("RESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021"), 1)
        for fora in ("SGS 1 Rio de Janeiro", "1", "2", "Assinado eletronicamente por",
                     "FULANO DE TAL", "Presidente"):
            self.assertNotIn(fora, linhas)

    def test_paragrafos_pdf(self):
        md = fo.paragrafos_pdf(TEXTO_PDF)
        pars = md.strip("\n").split("\n\n")
        self.assertEqual(pars[0], "RESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021")
        self.assertEqual(pars[1], "Dispõe sobre um assunto de teste e dá outras providências.")
        self.assertIn("CAPÍTULO I – DISPOSIÇÕES GERAIS", pars)
        self.assertIn("## Art. 1º", pars)  # "Art. 1o" do PDF
        self.assertIn("## Art. 3º", pars)
        self.assertIn("Esta Resolução dispõe sobre o assunto de teste, e o texto desta linha é longo o "
                      "bastante para quebrar no meio da frase e continuar na linha de baixo, como no PDF da "
                      "autarquia, que quebra as linhas pela largura da página.", pars)
        self.assertIn("I – manter cadastro atualizado dos clientes e dos seus representantes legais "
                      "perante a instituição;", pars)
        self.assertIn("II – comunicar a emissão; e", pars)  # "e" sozinho não abre parágrafo
        self.assertIn("III – guardar os documentos.", pars)
        self.assertIn("Parágrafo único. A obrigação de que trata o caput vale também para quem, ao pedir, "
                      "considera-se autor do pedido.", pars)
        self.assertIn("ANEXO A À RESOLUÇÃO CVM Nº 99, DE 1º DE JULHO DE 2021", pars)  # título à parte
        self.assertIn("QUADRO DE INFORMAÇÕES", pars)
        self.assertIn("Quadro de informações do emissor e do valor mobiliário objeto da oferta em questão", pars)
        self.assertIn("I – nome do emissor;", pars)  # primeiro inciso depois de título sem ponto
        self.assertNotIn("FULANO", md)


class TestAlteradora(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.docx = os.path.join(self.dir.name, "cvm.docx")
        self.ct = os.path.join(self.dir.name, "ct.md")
        for p, b in ((self.docx, b"docx"), (self.ct, b"ctresb")):
            with open(p, "wb") as f:
                f.write(b)

    def tearDown(self):
        self.dir.cleanup()

    def test_campos_por_fonte(self):
        item = {"numero": 64, "url_dou": "https://dou/64", "retificacoes": [{"dou": "2022-02-09"}],
                "url_ato": {"docx": "https://cvm/resol064.docx", "pdf": "https://cvm/resol064.pdf"}}
        orig, cons, sha, inc = fo.campos_alteradora(item, "ctresb", self.docx, self.ct, "https://raw/ct.md")
        self.assertEqual((orig, cons), ("https://dou/64", "https://cvm/resol064.docx"))
        self.assertEqual(sha, hashlib.sha256(b"docx").hexdigest())
        self.assertTrue(inc.startswith(fo.INCERTEZA_DOCX))
        self.assertIn("2022-02-09", inc)

        item = {"numero": 15, "url_dou": "https://dou/15", "url_ato": {"pdf": "https://cvm/resol015.pdf"}}
        orig, cons, sha, inc = fo.campos_alteradora(item, "ctresb", None, self.ct, "https://raw/ct.md")
        self.assertEqual((orig, cons, inc), ("https://dou/15", "https://raw/ct.md", fo.INCERTEZA_CTRESB))
        self.assertEqual(sha, hashlib.sha256(b"ctresb").hexdigest())

        item = {"numero": 159, "url_dou": "", "url_ato": {"docx": "https://cvm/resol159.docx"}}
        orig, cons, sha, inc = fo.campos_alteradora(item, "docx", self.docx)
        self.assertEqual((orig, cons, inc),
                         ("https://cvm/resol159.docx", "https://cvm/resol159.docx", fo.INCERTEZA_NAO_DOU))

    def test_ctresb_sem_url_dou_falha(self):
        item = {"numero": 1, "url_dou": "", "url_ato": {}}
        with self.assertRaises(ValueError):
            fo.campos_alteradora(item, "ctresb", None, self.ct, "https://raw/ct.md")


if __name__ == "__main__":
    unittest.main()
