"""Testes do texto vigente por script (Fase 2b). Sem rede, sem textutil e sem pypdf
obrigatório: a conversão e a extração de PDF são substituídas onde dependem deles."""
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import texto_vigente as tv  # noqa: E402
from validar import CAMPOS, ler_frontmatter  # noqa: E402

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx(path, paragrafos):
    """DOCX mínimo: cada parágrafo é uma lista de (texto, tachado?)."""
    corpo = ""
    for runs in paragrafos:
        corpo += "<w:p>" + "".join(
            "<w:r>%s<w:t xml:space=\"preserve\">%s</w:t></w:r>"
            % ("<w:rPr><w:strike/></w:rPr>" if t else "", txt) for txt, t in runs) + "</w:p>"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", "<w:document %s><w:body>%s</w:body></w:document>" % (W, corpo))
    return path


ACERVO = {
    "lido_em": "2026-10-28",
    "estoque_regulatorio": {"atualizado_em": "2026-09-08", "resolucoes": [17, 35, 210, 1],
                            "grupos": {}},
    "resolucoes": [
        {"numero": 1, "titulo": "Resolução CVM 1", "data": "2020-08-06", "dou": "2020-08-07",
         "ementa": "Estabelece a nomenclatura de atos.", "situacao": "vigente", "alteradoras": [],
         "consolidado": {}, "ato": {"pdf": "https://x/resol001.pdf"}, "url_pagina": "https://x/r1"},
        {"numero": 17, "titulo": "Resolução CVM 17", "data": "2021-02-09", "dou": "2021-02-10",
         "ementa": "Agente fiduciário.", "situacao": "vigente", "alteradoras": [],
         "consolidado": {"docx": "https://x/resol017consolid.docx"}, "ato": {}, "url_pagina": "u"},
        {"numero": 26, "titulo": "Resolução CVM 26", "data": "2021-03-31", "dou": "2021-04-06",
         "ementa": "Prorroga prazos.", "situacao": "verificar", "alteradoras": [],
         "consolidado": {}, "ato": {"docx": "https://x/resol026.docx"}, "url_pagina": "u"},
        {"numero": 35, "titulo": "Resolução CVM 35", "data": "2021-05-26", "dou": "2021-05-27",
         "ementa": "Intermediação.", "situacao": "vigente", "alteradoras": [134, 209, 179],
         "consolidado": {"pdf": "https://x/resol035consolid.pdf", "docx": "https://x/resol035consolid.docx"},
         "ato": {"pdf": "https://x/resol035.pdf"}, "url_pagina": "u"},
        {"numero": 81, "titulo": "Resolução CVM 81 (Revogada)", "data": "2022-03-29", "dou": "2022-03-30",
         "ementa": "Assembleias.", "situacao": "revogada", "alteradoras": [],
         "consolidado": {}, "ato": {}, "url_pagina": "u"},
        {"numero": 210, "titulo": "Resolução CVM 210", "data": "2024-08-26", "dou": "2024-08-27",
         "ementa": "Portabilidade.", "situacao": "vigente", "alteradoras": [229],
         "consolidado": {"htm": "https://x/resol210consolid.htm"},
         "ato": {"docx": "https://x/resol210.docx", "pdf": "https://x/resol210.pdf"}, "url_pagina": "u"},
        {"numero": 249, "titulo": "Resolução CVM 249", "data": "2026-10-13", "dou": "2026-10-14",
         "ementa": "Programa Piloto DLT.", "situacao": "verificar", "alteradoras": [],
         "consolidado": {}, "ato": {"docx": "https://x/resol249.docx"}, "url_pagina": "u"},
    ],
    "instrucoes": [
        {"numero": 409, "titulo": "Instrução CVM 409 (Revogada)", "data": "2004-08-18",
         "descricao": "Fundos.", "revogada": True, "situacao": "revogada"},
        {"numero": 438, "titulo": "Instrução CVM 438", "data": "2006-07-12", "dou": "2006-07-13",
         "descricao": "Aprova o COFI. (Publicada no DOU de 13.07.06)", "url_pagina": "u",
         "situacao": "vigente", "alterada_por": ["465/08", "577/16", "512/11"],
         "arquivos": {"consolidado": {"doc": "https://x/inst438consolid.doc"},
                      "ato": {"pdf": "https://x/inst438.pdf"}}},
        {"numero": 489, "titulo": "Instrução CVM 489", "data": "2011-01-14", "dou": "2011-01-17",
         "descricao": "Demonstrações financeiras de FIDC. (Publicada no DOU de 17.01.11)",
         "ementa": "Demonstrações financeiras de FIDC.", "url_pagina": "u",
         "situacao": "vigente", "alterada_por": ["502/11", "576/16"],
         "arquivos": {"ato": {"doc": "https://x/inst489.doc", "pdf": "https://x/inst489.pdf"}}},
        {"numero": 577, "titulo": "Instrução CVM 577", "data": "2016-07-07", "descricao": "Altera o COFI.",
         "situacao": "so-alteradora", "alterada_por": [], "arquivos": {}},
    ],
    "pareceres": [
        {"numero": 35, "titulo": "Parecer de Orientação CVM 35", "data": "2008-09-01", "dou": "2008-09-02",
         "descricao": "Deveres fiduciários... (Publicado...", "ementa": "Deveres fiduciários dos "
         "administradores, à luz da Instrução CVM nº 409 e da Resolução CVM nº 175.",
         "url_pagina": "u", "alterada_por": [],
         "arquivos": {"ato": {"doc": "https://x/pare035.doc", "pdf": "https://x/pare035.pdf"}}},
    ],
    "oficios_circulares": [
        {"titulo": "Ofício Circular CVM/SSE 03/26", "data": "2026-09-11", "superintendencia": "sse1",
         "slug": "oc-sse-0326", "descricao": "Taxa de performance...",
         "ementa": "Taxa de performance de FIDC.",
         "url_pagina": "https://x/legislacao/oficios-circulares/sse1/oc-sse-0326.html",
         "url_pdf": "https://x/sse1/anexos/oc-sse-0326.pdf", "url_pdf_origem": "pagina", "cita": []},
        {"titulo": "Ofício Circular Anual 2022 CVM/SEP", "data": "2022-01-01", "superintendencia": "sep",
         "descricao": "Orientações anuais.", "url_pagina": "https://x/legislacao/oficios-circulares/sep/oc-anual-sep-2022.html",
         "url_pdf": "https://x/sep/anexos/oc-anual-sep-2022.pdf", "cita": []},
        {"titulo": "Ofício-Circular CVM/SIN 12/21", "data": "2021-12-31", "superintendencia": "sin",
         "slug": "oc-sin-1221", "descricao": "Antigo.", "url_pagina": "https://x/sin/oc-sin-1221.html",
         "url_pdf": "https://x/sin/anexos/oc-sin-1221.pdf", "cita": []},
    ],
}


class TestFonte(unittest.TestCase):
    def test_consolidado_htm_antes_de_ato_docx(self):
        f = {"consolidado": {"htm": "c.htm", "pdf": "c.pdf"}, "ato": {"docx": "a.docx", "pdf": "a.pdf"}}
        self.assertEqual(tv.escolher_fonte(f), ("consolidado", "htm", "c.htm"))

    def test_docx_antes_de_doc_e_pdf_por_ultimo(self):
        self.assertEqual(tv.escolher_fonte({"consolidado": {"doc": "c.doc", "docx": "c.docx"}}),
                         ("consolidado", "docx", "c.docx"))
        self.assertEqual(tv.escolher_fonte({"ato": {"pdf": "a.pdf", "doc": "a.doc"}}), ("ato", "doc", "a.doc"))
        self.assertEqual(tv.escolher_fonte({"ato": {"pdf": "a.pdf"}}), ("ato", "pdf", "a.pdf"))
        self.assertIsNone(tv.escolher_fonte({}))

    def test_extensao_real_da_url(self):
        f = {"consolidado": {"docx": "https://x/resol009consolid.doc", "pdf": "https://x/c.pdf"},
             "ato": {"docx": "https://x/a.docx"}}
        self.assertEqual(tv.escolher_fonte(f), ("consolidado", "doc", "https://x/resol009consolid.doc"))

    def test_nivel_verificacao(self):
        self.assertEqual(tv.nivel_verificacao("consolidado", "htm"), "consolidado-convertido")
        self.assertEqual(tv.nivel_verificacao("ato", "doc"), "ato-convertido")
        self.assertEqual(tv.nivel_verificacao("ato", "pdf"), "pdf-extraido")
        self.assertEqual(tv.nivel_verificacao("consolidado", "pdf"), "pdf-extraido")
        self.assertEqual(tv.nivel_verificacao("ato", "pdf", ocr=True), "ocr")

    def test_limpar_ementa(self):
        self.assertEqual(tv.limpar_ementa("Aprova o COFI. (Publicada no DOU de 13.07.06) (Retificada...)"),
                         "Aprova o COFI.")
        self.assertEqual(tv.limpar_ementa(" Deveres. (Publicado no DOU de 02.09.08)"), "Deveres.")


class TestItens(unittest.TestCase):
    def setUp(self):
        self.c1 = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 1)}
        self.c2 = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 2)}

    def test_camada1_exclui_nucleo_inclui_249(self):
        self.assertEqual(sorted(self.c1), ["cvm-instr-438", "cvm-instr-489", "cvm-res-1",
                                           "cvm-res-210", "cvm-res-249", "cvm-res-35"])
        self.assertNotIn("cvm-res-17", self.c1)  # núcleo
        self.assertNotIn("cvm-res-26", self.c1)  # verificar, fora
        r249 = self.c1["cvm-res-249"]
        self.assertEqual(r249["situacao"], "vigente")
        self.assertEqual(r249["arquivo"], "cvm/resolucoes/0249.md")

    def test_vigente_ate_ato_so_com_consolidado(self):
        r35 = self.c1["cvm-res-35"]
        self.assertEqual(r35["alteradoras"], ["134", "209", "179"])
        self.assertEqual(r35["vigente_ate_ato"], "209")
        self.assertEqual(self.c1["cvm-res-210"]["vigente_ate_ato"], "229")  # consolidado htm
        self.assertEqual(self.c1["cvm-res-1"]["vigente_ate_ato"], "")
        self.assertEqual(self.c1["cvm-instr-438"]["vigente_ate_ato"], "577")
        self.assertEqual(self.c1["cvm-instr-489"]["vigente_ate_ato"], "")

    def test_instrucoes(self):
        i438 = self.c1["cvm-instr-438"]
        self.assertEqual((i438["tipo"], i438["numero"], i438["arquivo"]),
                         ("instrucao", 438, "cvm/instrucoes/0438.md"))
        self.assertEqual(i438["ementa"], "Aprova o COFI.")
        self.assertEqual(i438["situacao"], "vigente")

    def test_camada2_corte_de_data_e_ids(self):
        self.assertEqual(sorted(self.c2), ["cvm-oc-anual-sep-2022", "cvm-oc-sse-0326", "cvm-po-35"])
        oc = self.c2["cvm-oc-sse-0326"]
        self.assertEqual((oc["tipo"], oc["numero"], oc["arquivo"]),
                         ("oficio-circular", 3, "cvm/oficios-circulares/sse1/oc-sse-0326.md"))
        self.assertEqual(oc["fontes"], {"ato": {"pdf": "https://x/sse1/anexos/oc-sse-0326.pdf"}})
        self.assertEqual(oc["situacao"], "nao-informada")
        self.assertEqual(oc["ementa"], "Taxa de performance de FIDC.")
        self.assertEqual(self.c2["cvm-oc-anual-sep-2022"]["numero"], 2022)
        po = self.c2["cvm-po-35"]
        self.assertEqual((po["tipo"], po["numero"], po["arquivo"], po["situacao"]),
                         ("parecer-orientacao", 35, "cvm/pareceres-orientacao/0035.md", "nao-informada"))

    def test_numero_oficio(self):
        self.assertEqual(tv.numero_oficio("Ofício-Circular nº 8/2024/CVM/SIN"), 8)
        self.assertEqual(tv.numero_oficio("Ofício CVM/SRE 211/05"), 211)
        self.assertEqual(tv.numero_oficio("Ofício Circular Anual 2026 CVM/SRE"), 2026)
        self.assertEqual(tv.numero_oficio("Oficio Circular CVM SIN Nº 01 / 2016"), 1)

    def test_oficio_usa_slug_e_id_do_acervo(self):
        oc = {"titulo": "Ofício Circular CVM/SIN 06/23", "data": "2023-09-27", "superintendencia": "sin",
              "slug": "oc-sin-0623-sin", "slug_cvm": "oc-sin-0623", "id": "cvm-oc-sin-0623-sin",
              "descricao": "x", "url_pagina": "https://x/legislacao/oficios-circulares/sin/oc-sin-0623.html",
              "url_pdf": "https://x/sin/anexos/oc-sin-0623.pdf"}
        camel = {"titulo": "Ofício Circular CVM/SSE 01/22", "data": "2022-06-21", "superintendencia": "sse1",
                 "slug": "oficio-circular-cvmsse0122", "slug_cvm": "OficioCircularCVMSSE0122",
                 "id": "cvm-oficio-circular-cvmsse0122", "descricao": "y",
                 "url_pagina": "https://x/legislacao/oficios-circulares/sse1/OficioCircularCVMSSE0122.html"}
        itens = {i["id"]: i for i in tv.itens_do_acervo({"oficios_circulares": [oc, camel]}, 2)}
        self.assertEqual(sorted(itens), ["cvm-oc-sin-0623-sin", "cvm-oficio-circular-cvmsse0122"])
        self.assertEqual(itens["cvm-oc-sin-0623-sin"]["arquivo"],
                         "cvm/oficios-circulares/sin/oc-sin-0623-sin.md")
        self.assertEqual(itens["cvm-oficio-circular-cvmsse0122"]["arquivo"],
                         "cvm/oficios-circulares/sse1/oficio-circular-cvmsse0122.md")


class TestMontar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.c1 = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 1)}
        self.c2 = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 2)}
        self.docx = _docx(os.path.join(self.dir, "f.docx"), [
            [("Art. 1º O prazo é de ", False), ("trinta", True), (" sessenta dias.", False)],
            [("Art. 2º Esta Resolução entra em vigor na data de sua publicação.", False)],
        ])
        p = mock.patch.object(tv, "texto_conferencia",
                              return_value="Art. 1º O prazo é de trinta sessenta dias. Art. 2º Esta "
                                           "Resolução entra em vigor na data de sua publicação.")
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def _fm(self, md):
        pares, corpo, erro = ler_frontmatter(md)
        self.assertIsNone(erro)
        return pares, dict(pares), corpo

    def test_tachado_sai_so_do_consolidado(self):
        md, rel = tv.montar(self.c1["cvm-res-35"], self.docx, "consolidado", "docx", "https://x/c.docx")
        _, v, corpo = self._fm(md)
        self.assertNotIn("trinta", corpo)
        self.assertIn("sessenta dias", corpo)
        self.assertEqual(rel["palavras_tachadas"], 1)
        md, _ = tv.montar(self.c1["cvm-res-249"], self.docx, "ato", "docx", "https://x/a.docx")
        _, _, corpo = self._fm(md)
        self.assertRegex(corpo, r"~~\s*trinta\s*~~")

    def test_frontmatter_resolucao_consolidado(self):
        md, rel = tv.montar(self.c1["cvm-res-35"], self.docx, "consolidado", "docx", "https://x/c.docx")
        pares, v, corpo = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual(v["situacao"], "vigente")
        self.assertEqual(v["versao_texto"], "consolidado")
        self.assertEqual(v["vigente_ate_ato"], "209")
        self.assertEqual(v["nivel_verificacao"], "consolidado-convertido")
        self.assertEqual(v["publicacao_dou"], "2021-05-27")
        self.assertEqual(rel["nivel_verificacao"], "consolidado-convertido")
        self.assertIn("## Art. 1º", corpo)

    def test_frontmatter_instrucao_489_ato(self):
        md, _ = tv.montar(self.c1["cvm-instr-489"], self.docx, "ato", "doc", "https://x/inst489.doc")
        pares, v, _ = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual((v["id"], v["tipo"], v["numero"]), ("cvm-instr-489", "instrucao", "489"))
        self.assertEqual(v["versao_texto"], "original")
        self.assertEqual(v["vigente_ate_ato"], "")
        self.assertEqual(v["nivel_verificacao"], "ato-convertido")
        self.assertIn("[verificar] alterações de 502/11 e 576/16 não aplicadas", v["incerteza"])

    def test_frontmatter_parecer_nao_informada(self):
        md, _ = tv.montar(self.c2["cvm-po-35"], self.docx, "ato", "doc", "https://x/pare035.doc")
        pares, v, _ = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual(v["situacao"], "nao-informada")
        self.assertEqual(v["tipo"], "parecer-orientacao")
        self.assertIn("A CVM não publica a vigência de pareceres de orientação; este texto pode "
                      "tratar de norma já revogada.", v["incerteza"])
        self.assertIn("Instrução CVM 409", v["incerteza"])
        self.assertNotIn("Resolução CVM 175", v["incerteza"])  # 175 não está revogada

    def test_frontmatter_oficio_pdf_sem_dou(self):
        texto = "Ofício circular sobre taxa de performance em fundos de direitos creditórios. " * 20
        with mock.patch.object(tv, "_pdf_txt", return_value=texto), \
                mock.patch.object(tv, "_pdfkit_txt", return_value=None):
            md, rel = tv.montar(self.c2["cvm-oc-sse-0326"], self.docx, "ato", "pdf",
                                "https://x/sse1/anexos/oc-sse-0326.pdf")
        pares, v, _ = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual((v["id"], v["tipo"], v["numero"]), ("cvm-oc-sse-0326", "oficio-circular", "3"))
        self.assertEqual(v["publicacao_dou"], "2026-09-11")
        self.assertEqual(v["situacao"], "nao-informada")
        self.assertEqual(v["nivel_verificacao"], "pdf-extraido")
        self.assertIn("ofícios-circulares", v["incerteza"])
        self.assertIn("DOU", v["incerteza"])
        self.assertFalse(rel["conferencia_independente"])

    def test_vigencia_inicio_antes_de_nivel(self):
        docx = _docx(os.path.join(self.dir, "v.docx"), [
            [("Art. 1º O prazo é de trinta dias.", False)],
            [("Vigente a partir de 1º de janeiro de 2027:", False)],
            [("Art. 1º O prazo é de sessenta dias.", False)],
        ])
        md, _ = tv.montar(self.c1["cvm-res-249"], docx, "ato", "docx", "https://x/a.docx")
        pares, v, _ = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["vigencia_inicio", "nivel_verificacao"])
        self.assertEqual(v["vigencia_inicio"], "2027-01-01")


class TestPdf(unittest.TestCase):
    def test_legibilidade(self):
        self.assertEqual(tv.legibilidade("/0 /1 /2/3 /4 □ /5"), (0.0, 6))
        frac, n = tv.legibilidade("O administrador do fundo deve divulgar as informações. " * 10)
        self.assertGreater(frac, 0.5)
        self.assertEqual(n, 80)

    def test_pdf_ilegivel_nao_grava_arquivo(self):
        item = tv.itens_do_acervo(ACERVO, 2)[1]  # ofício SSE 03/26
        self.assertEqual(item["id"], "cvm-oc-sse-0326")
        lixo = " ".join("/%d" % (i % 70) for i in range(3000))

        def baixar(url, destino):
            with open(destino, "wb") as f:
                f.write(b"%PDF-1.4 falso")
            return destino

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(tv, "_baixar", side_effect=baixar), \
                mock.patch.object(tv, "_pdf_txt", return_value=lixo), \
                mock.patch.object(tv, "_pdf_type3", return_value=True), \
                mock.patch.object(tv, "_pdfkit_txt", return_value=None), \
                mock.patch.object(tv, "_ocr", return_value=None):
            rel = tv.processar([item], os.path.join(d, "saida"), os.path.join(d, "cache"))
            self.assertFalse(os.path.exists(os.path.join(d, "saida", item["arquivo"])))
        self.assertEqual(rel[0]["resultado"], "sem-texto")
        self.assertIn("Type3", rel[0]["motivo"])
        self.assertEqual(rel[0]["palavras"], 3000)

    def test_pdf_poucas_palavras_e_escaneado(self):
        motivo = tv.motivo_sem_texto("Página 1", type3=False)
        self.assertIn("escaneado", motivo)
        self.assertIsNone(tv.motivo_sem_texto("O administrador do fundo deve divulgar. " * 20, type3=False))

    def test_pdf_real_em_branco(self):
        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("pypdf ausente (dependência opcional)")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "branco.pdf")
            w = PdfWriter()
            w.add_blank_page(width=595, height=842)
            with open(path, "wb") as f:
                w.write(f)
            item = tv.itens_do_acervo(ACERVO, 2)[1]
            with self.assertRaises(tv.SemTexto) as ctx, \
                    mock.patch.object(tv, "_pdfkit_txt", return_value=None), \
                    mock.patch.object(tv, "_ocr", return_value=None):
                tv.montar(item, path, "ato", "pdf", "https://x/a.pdf")
            self.assertEqual(ctx.exception.palavras, 0)


if __name__ == "__main__":
    unittest.main()


W_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx_com_extras(path):
    """DOCX com uma nota de rodapé e uma caixa de texto."""
    corpo = ('<w:p><w:r><w:t>Art. 1º Texto principal da norma com referência.</w:t></w:r>'
             '<w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
             '<w:p><w:r><w:pict><w:txbxContent><w:p><w:r><w:t>Fluxo do diagrama com sete palavras aqui'
             '</w:t></w:r></w:p></w:txbxContent></w:pict></w:r></w:p>')
    notas = ('<w:footnotes %s><w:footnote w:id="-1"><w:p><w:r><w:t>sep</w:t></w:r></w:p></w:footnote>'
             '<w:footnote w:id="1"><w:p><w:r><w:t>Restrito aos serviços públicos.</w:t></w:r></w:p>'
             '</w:footnote></w:footnotes>' % W_NS)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", '<w:document %s><w:body>%s</w:body></w:document>' % (W_NS, corpo))
        z.writestr("word/footnotes.xml", notas)


class TestExtrasDocx(unittest.TestCase):
    def test_notas_de_rodape_e_caixa_de_texto(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.docx")
            _docx_com_extras(p)
            notas, caixa = tv.extras_docx(p)
        self.assertEqual(notas, ["Restrito aos serviços públicos."])
        self.assertEqual(caixa, 7)

    def test_secao_de_notas(self):
        self.assertEqual(tv.secao_notas(["Um.", "Dois."]),
                         "\n\n## Notas de rodapé\n\n[1] Um.\n\n[2] Dois.\n")
        self.assertEqual(tv.secao_notas([]), "")


class TestFonteIlegivelPassaAdiante(unittest.TestCase):
    def test_tenta_a_proxima_fonte(self):
        fontes = {"ato": {"doc": "https://x/pare034.doc", "pdf": "https://x/pare034.pdf"}}
        self.assertEqual([(t, e) for t, e, _ in tv.fontes_candidatas(fontes)],
                         [("ato", "doc"), ("ato", "pdf")])


class TestCaixasENotasNoTextoVigente(unittest.TestCase):
    """O texto vigente traz caixas como blocos "[Diagrama]" e a âncora [k] das notas."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.docx = os.path.join(self.tmp.name, "a.docx")
        _docx_com_extras(self.docx)
        p = mock.patch.object(tv, "texto_conferencia", return_value="Art. 1º Texto principal.")
        p.start()
        self.addCleanup(p.stop)
        self.item = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 1)}["cvm-res-249"]

    def test_corpo_com_diagrama_e_ancora(self):
        md, rel = tv.montar(self.item, self.docx, "ato", "docx", "https://x/a.docx")
        self.assertIn("Texto principal da norma com referência. [1]", md)
        self.assertIn("> [Diagrama] Fluxo do diagrama com sete palavras aqui", md)
        self.assertIn("[1] Restrito aos serviços públicos.", md)
        self.assertEqual(rel["palavras_em_caixa_de_texto"], 7)

    def test_incerteza_descreve_diagrama_e_notas(self):
        md, _ = tv.montar(self.item, self.docx, "ato", "docx", "https://x/a.docx")
        inc = [l for l in md.split("\n") if l.startswith("incerteza:")][0]
        self.assertIn('blocos "[Diagrama]"', inc)
        self.assertIn("sem o desenho", inc)
        self.assertIn("[verificar no original]", inc)
        self.assertNotIn("não convertidas", inc)
        self.assertIn("Notas de rodapé", inc)
        self.assertNotIn("sem a âncora", inc)

    def test_notas_na_ordem_da_ancora(self):
        corpo = ('<w:p><w:r><w:t>a</w:t></w:r><w:r><w:footnoteReference w:id="3"/></w:r>'
                 '<w:r><w:footnoteReference w:id="1"/></w:r></w:p>')
        notas = ('<w:footnotes %s><w:footnote w:id="1"><w:p><w:r><w:t>Um.</w:t></w:r></w:p></w:footnote>'
                 '<w:footnote w:id="3"><w:p><w:r><w:t>Três.</w:t></w:r></w:p></w:footnote></w:footnotes>' % W_NS)
        p = os.path.join(self.tmp.name, "b.docx")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", '<w:document %s><w:body>%s</w:body></w:document>' % (W_NS, corpo))
            z.writestr("word/footnotes.xml", notas)
        self.assertEqual(tv.extras_docx(p)[0], ["Três.", "Um."])
        self.assertEqual(tv.docx_para_md(p, caixas=True, notas=True), "a [1] [2]\n")


# ---------------------------------------------------------------- PDFKit, OCR, métrica e datas

BOM = ("O administrador do fundo deve divulgar a operacionalização das informações aos cotistas "
       "em qualquer hipótese de entrega. ") * 6
PARTIDO = BOM.replace("operacionalização", "op eracionalização").replace("qualquer", "qualq uer")
LIXO = " ".join("/%d" % (i % 70) for i in range(300))
TABELA = "\n".join("PETR4 BRPETRACNPR6 %d,%02d" % (i, i % 100) for i in range(40))  # tickers e ISINs


def _pdf_falso(d, nome="a.pdf"):
    path = os.path.join(d, nome)
    with open(path, "wb") as f:
        f.write(b"%PDF-1.4 falso")
    return path


class TestExtratorPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = _pdf_falso(self.tmp.name)
        self.item = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 2)}["cvm-oc-sse-0326"]

    def _montar(self, pdfkit, pypdf, ocr=None):
        with mock.patch.object(tv, "_pdfkit_txt", return_value=pdfkit), \
                mock.patch.object(tv, "_pdf_txt", return_value=pypdf), \
                mock.patch.object(tv, "_pdf_type3", return_value=False), \
                mock.patch.object(tv, "_ocr", return_value=ocr):
            return tv.montar(self.item, self.pdf, "ato", "pdf", "https://x/a.pdf")

    def test_pdfkit_preferido_e_pypdf_como_conferencia(self):
        md, rel = self._montar(BOM, PARTIDO)
        self.assertIn("operacionalização", md)
        self.assertNotIn("op eracionalização", md)
        self.assertTrue(rel["conferencia_independente"])
        self.assertEqual(rel["extrator"], "pdfkit")
        self.assertEqual(rel["nivel_verificacao"], "pdf-extraido")
        # as palavras partidas pelo pypdf faltam no Markdown do PDFKit
        self.assertEqual(rel["cobertura"], tv.cobertura(PARTIDO, md.split("---\n", 2)[2]))
        self.assertLess(rel["cobertura"], 1.0)

    def test_sem_pdfkit_cai_no_pypdf_sem_conferencia(self):
        md, rel = self._montar(None, PARTIDO)
        self.assertIn("op eracionalização", md)
        self.assertFalse(rel["conferencia_independente"])
        self.assertEqual(rel["extrator"], "pypdf")

    def test_pdfkit_so_no_macos(self):
        with mock.patch.object(tv.sys, "platform", "linux"):
            self.assertIsNone(tv._pdfkit_txt(self.pdf))
            self.assertIsNone(tv._ocr(self.pdf))

    def test_pdfkit_que_falha_vira_none(self):
        falha = mock.Mock(side_effect=RuntimeError("swift ausente"))
        with mock.patch.object(tv.sys, "platform", "darwin"), \
                mock.patch.dict(sys.modules, {"pdf_macos": mock.Mock(texto_pdfkit=falha, ocr=falha)}):
            self.assertIsNone(tv._pdfkit_txt(self.pdf))
            self.assertIsNone(tv._ocr(self.pdf))

    def test_nfkc_some_ligadura_e_preserva_ordinais(self):
        self.assertEqual(tv.normalizar_pdf("a eﬁciência do ﬂuxo, art. 1º, nº 2, 1ª\xa0série"),
                         "a eficiência do fluxo, art. 1º, nº 2, 1ª série")
        md, _ = self._montar(BOM.replace("informações", "inﬁnitas informações"), BOM)
        self.assertIn("infinitas", md)
        self.assertNotIn("ﬁ", md)

    def test_ocr_aceito_por_confianca_apesar_da_legibilidade(self):
        self.assertLess(tv.legibilidade(TABELA)[0], tv.LEGIBILIDADE_MIN)
        md, rel = self._montar(LIXO, LIXO, ocr=(TABELA, [0.95, 0.80, 0.83]))
        pares, _, _ = ler_frontmatter(md)
        v = dict(pares)
        self.assertEqual(v["nivel_verificacao"], "ocr")
        self.assertEqual(rel["nivel_verificacao"], "ocr")
        self.assertEqual(rel["extrator"], "ocr")
        self.assertFalse(rel["conferencia_independente"])
        self.assertEqual((rel["ocr_confianca_media"], rel["ocr_confianca_minima"]), (0.86, 0.8))
        self.assertIn("Texto por OCR (confiança média 0,86, mínima 0,80 por página); erros pontuais "
                      "de reconhecimento são esperados [verificar no PDF oficial].", v["incerteza"])
        self.assertIn("BRPETRACNPR6", md)

    def test_ocr_recusado_por_confianca_baixa(self):
        with self.assertRaises(tv.SemTexto) as ctx:
            self._montar(LIXO, LIXO, ocr=(TABELA, [0.84, 0.80]))
        self.assertIn("OCR recusado", ctx.exception.motivo)
        self.assertEqual(ctx.exception.palavras, 300)

    def test_ocr_recusado_com_poucas_palavras(self):
        with self.assertRaises(tv.SemTexto) as ctx:
            self._montar(LIXO, LIXO, ocr=("Página 1", [0.99]))
        self.assertIn("OCR recusado", ctx.exception.motivo)

    def test_sem_ocr_fica_sem_texto(self):
        with self.assertRaises(tv.SemTexto) as ctx:
            self._montar(LIXO, LIXO, ocr=None)
        self.assertNotIn("OCR recusado", ctx.exception.motivo)

    def test_pdfkit_ilegivel_e_pypdf_legivel_usa_pypdf(self):
        md, rel = self._montar(LIXO, BOM)
        self.assertEqual(rel["extrator"], "pypdf")
        self.assertFalse(rel["conferencia_independente"])


class TestMetrica(unittest.TestCase):
    def test_sublinhado_separa_palavras(self):
        self.assertEqual(tv.palavras("acao=documento_conferir&id_orgao=0"),
                         ["acao", "documento", "conferir", "id", "orgao", "0"])
        fonte = "controlador.php?acao=documento\n_\nimprimir"
        self.assertEqual(tv.cobertura(fonte, "controlador.php?acao=documento_imprimir"), 1.0)

    def test_italico_markdown_nao_conta_como_perda(self):
        self.assertEqual(tv.cobertura("a palavra grifada", "a _palavra_ grifada"), 1.0)


class TestDatas(unittest.TestCase):
    def test_baixado_em_e_mtime_em_sao_paulo_e_verificado_em_hoje(self):
        import calendar
        # 2026-10-21 01:30 UTC = 2026-10-20 22:30 em São Paulo
        ts = calendar.timegm((2026, 10, 21, 1, 30, 0))
        with tempfile.TemporaryDirectory() as d:
            docx = _docx(os.path.join(d, "f.docx"), [[("Art. 1º Esta Resolução entra em vigor.", False)]])
            os.utime(docx, (ts, ts))
            self.assertEqual(tv.data_arquivo(docx), "2026-10-20")
            item = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 1)}["cvm-res-249"]
            with mock.patch.object(tv, "texto_conferencia", return_value="Art. 1º Esta Resolução."), \
                    mock.patch.object(tv, "DATA_BASE", "2026-10-29"):
                md, rel = tv.montar(item, docx, "ato", "docx", "https://x/a.docx")
        v = dict(ler_frontmatter(md)[0])
        self.assertEqual(v["baixado_em"], "2026-10-20")
        self.assertEqual(v["verificado_em"], "2026-10-29")
        self.assertIn("data-base 2026-10-20", v["incerteza"])
        self.assertEqual(rel["baixado_em"], "2026-10-20")
