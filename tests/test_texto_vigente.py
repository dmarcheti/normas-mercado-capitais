"""Testes do texto vigente por script (Fase 2b). Sem rede, sem textutil e sem pypdf
obrigatório: a conversão e a extração de PDF são substituídas onde dependem deles."""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import texto_vigente as tv  # noqa: E402
from validar import CAMPOS, ler_frontmatter  # noqa: E402
from converter import docx_para_md  # noqa: E402


def _textutil_falso(origem, formato, destino):
    """No lugar do textutil (só macOS): a fixture .doc já é um DOCX."""
    if formato == "docx":
        shutil.copyfile(origem, destino)
    else:
        with open(destino, "w", encoding="utf-8") as f:
            f.write(docx_para_md(origem))
    return destino

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

    @mock.patch.object(tv, "_textutil", _textutil_falso)
    def test_frontmatter_instrucao_489_ato(self):
        md, _ = tv.montar(self.c1["cvm-instr-489"], self.docx, "ato", "doc", "https://x/inst489.doc")
        pares, v, _ = self._fm(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual((v["id"], v["tipo"], v["numero"]), ("cvm-instr-489", "instrucao", "489"))
        self.assertEqual(v["versao_texto"], "original")
        self.assertEqual(v["vigente_ate_ato"], "")
        self.assertEqual(v["nivel_verificacao"], "ato-convertido")
        self.assertIn("[verificar] alterações de 502/11 e 576/16 não aplicadas", v["incerteza"])

    @mock.patch.object(tv, "_textutil", _textutil_falso)
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
        # o PDF dá LIXO; o OCR (uma tabela de tickers) é aceito pela confiança média
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


# ---------------------------------------------------------------- Fase 2c: camadas 4 e 5

import json  # noqa: E402

from validar import validar_norma  # noqa: E402

PERIMETRO = [
    {"tipo": "resolucao-cmn", "numero": 4966, "data": "2021-11-25", "decisao": "entra"},
    {"tipo": "circular", "numero": 3290, "data": "2005-09-05", "decisao": "entra"},
    {"tipo": "resolucao-bcb", "numero": 277, "data": "2022-12-31", "decisao": "fora"},
    {"tipo": "resolucao-conjunta", "numero": 13, "data": "2024-12-03", "decisao": "entra"},
    {"tipo": "carta-circular", "numero": 9999, "data": "2020-01-01", "decisao": "entra"},
]
ACERVO_BCB = {"normas": [
    {"tipo": "resolucao-cmn", "tipo_bcb": "Resolução CMN", "numero": 4966, "data": "2021-11-25",
     "assunto": "Dispõe sobre instrumentos financeiros. (Publicada no DOU ...)", "situacao": "vigente",
     "url_pagina": "https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolução CMN&numero=4966",
     "dou": "2021-11-29", "versao": 7.0, "formato": "html", "documentos": "Res_4966_v1_O.pdf;300#;"},
    {"tipo": "circular", "tipo_bcb": "Circular", "numero": 3290, "data": "2005-09-05",
     "assunto": "Estabelece procedimentos.", "situacao": "vigente", "url_pagina": "https://x/c3290",
     "dou": None, "versao": None, "formato": "sem-texto+anexos",
     "documentos": "Circ_3290_v1_O.pdf;25#;Circ_3290_v3_P.pdf;21#;Circ_3290_v3_L.pdf;20#;Circ_3290_v2_L.pdf;19#;"},
    {"tipo": "resolucao-bcb", "tipo_bcb": "Resolução BCB", "numero": 277, "data": "2022-12-31",
     "assunto": "Câmbio.", "formato": "html", "documentos": ""},
    {"tipo": "resolucao-conjunta", "tipo_bcb": "Resolução Conjunta", "numero": 13, "data": "2024-12-03",
     "assunto": "Dispõe sobre o Open Finance.", "url_pagina": "https://x/rc13", "dou": "2024-12-05",
     "versao": 1.0, "formato": "html", "documentos": "Res_Conj_0013_v1_O.pdf;100#;"},
]}
ANBIMA = {"lido_em": "2026-10-29", "documentos": [
    {"titulo": "Código de Ofertas Públicas (vigente a partir de 03/02/2025)", "url": "https://anbima/cop.pdf",
     "arquivo": "cop.pdf", "situacao": "vigente", "vigente_desde": "2025-02-03", "tipo": "codigo",
     "paginas": ["https://anbima/codigos"]},
    {"titulo": "Código antigo", "url": "https://anbima/velho.pdf", "arquivo": "velho.pdf",
     "situacao": "revogado", "tipo": "codigo"},
    {"titulo": "Deliberação nº 1 do Conselho", "url": "https://anbima/d1.pdf", "arquivo": "d1.pdf",
     "situacao": "vigente", "tipo": "deliberacao", "paginas": ["https://anbima/delib"]},
    {"titulo": "Glossário ANBIMA", "url": "https://anbima/g.pdf", "arquivo": "g.pdf",
     "situacao": "vigente", "vigente_desde": None, "tipo": "glossario"},
]}
B3 = {"lido_em": "2026-10-29", "documentos": [
    {"url": "https://b3/RegBalcao.pdf", "arquivo": "RegBalcao.pdf", "rotulos": ["REGULAMENTO DO BALCÃO B3 - Sem Marcas*"],
     "data_nome": "2026-09-21", "last_modified": "Mon, 21 Sep 2026 12:00:00 GMT", "entra": True,
     "paginas": ["https://b3/regulamentos"]},
    {"url": "https://b3/Glossario.pdf", "arquivo": "Glossario.pdf", "rotulos": ["Glossário (.PDF, 2MB)"],
     "last_modified": "Fri, 25 Sep 2026 02:30:00 GMT", "entra": True, "paginas": ["https://b3/g"]},
    {"url": "https://b3/ManualOp_v12.pdf", "arquivo": "ManualOp_v12.pdf", "rotulos": ["Versão em vigor"],
     "entra": True, "paginas": ["https://b3/m"]},
    {"url": "https://b3/Fora.pdf", "arquivo": "Fora.pdf", "rotulos": ["Fora"], "entra": False},
]}


class TestItensCamada4(unittest.TestCase):
    def setUp(self):
        self.itens = {i["id"]: i for i in tv.itens_do_acervo(
            {"perimetro": PERIMETRO, "bcb": ACERVO_BCB}, 4, cache_bcb="/cache")}

    def test_so_entra_com_id_e_caminho(self):
        self.assertEqual(sorted(self.itens), ["bcb-cc-9999", "bcb-circ-3290", "bcb-resc-13", "cmn-res-4966"])
        i = self.itens["cmn-res-4966"]
        self.assertEqual((i["orgao"], i["tipo"], i["numero"], i["arquivo"]),
                         ("cmn", "resolucao-cmn", 4966, "cmn/resolucoes/4966.md"))
        self.assertEqual(self.itens["bcb-resc-13"]["arquivo"], "bcb/resolucoes-conjuntas/0013.md")
        self.assertEqual(self.itens["bcb-circ-3290"]["arquivo"], "bcb/circulares/3290.md")

    def test_html_usa_conversor_html_bcb_e_cache_da_api(self):
        i = self.itens["cmn-res-4966"]
        self.assertEqual(i["conversor"], "html_bcb")
        self.assertEqual(list(i["fontes"]), ["consolidado"])
        self.assertEqual(i["cache_api"], os.path.join("/cache", "Resolução_CMN-04966.json"))
        self.assertEqual((i["dou"], i["ementa"], i["versao"]), ("2021-11-29", "Dispõe sobre instrumentos financeiros.", 7.0))

    def test_sem_texto_resolve_o_pdf_depois_e_ausente_vira_sem_texto(self):
        self.assertNotIn("conversor", self.itens["bcb-circ-3290"])
        self.assertEqual(self.itens["bcb-circ-3290"]["fontes"], {})
        self.assertIn("ausente", self.itens["bcb-cc-9999"]["sem_texto_motivo"])

    def test_pdf_da_ultima_versao_l_antes_de_o_e_p(self):
        docs = ACERVO_BCB["normas"][1]["documentos"]
        self.assertEqual(tv.pdf_da_ultima_versao(docs), ("Circ_3290_v3_L.pdf", 3, "L"))
        self.assertEqual(tv.pdf_da_ultima_versao("C_Circ_3934_v1_O.pdf;17#;"), ("C_Circ_3934_v1_O.pdf", 1, "O"))
        self.assertIsNone(tv.pdf_da_ultima_versao(""))

    def _preparar(self, item, conteudo):
        with tempfile.TemporaryDirectory() as d:
            item = dict(item, cache_api=os.path.join(d, "api.json"))
            with open(item["cache_api"], "w", encoding="utf-8") as f:
                json.dump({"conteudo": [conteudo]}, f)
            tv.preparar_bcb(item)
        return item

    def test_preparar_pdf_da_norma_sem_texto(self):
        i = self._preparar(self.itens["bcb-circ-3290"], {
            "Id": 48371, "DOU": "DOU de 6/9/2005", "Documentos": ACERVO_BCB["normas"][1]["documentos"]})
        base = "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/48371/"
        self.assertEqual(i["fontes"], {"consolidado": {"pdf": base + "Circ_3290_v3_L.pdf"}})
        self.assertEqual(i["fonte_original"], base + "Circ_3290_v1_O.pdf")
        self.assertNotIn("sem_texto_motivo", i)

    def test_preparar_sem_pdf_nao_inventa_url(self):
        i = self._preparar(self.itens["bcb-circ-3290"], {"Id": 48371, "Documentos": ""})
        self.assertEqual(i["fontes"], {})
        self.assertIn("sem PDF", i["sem_texto_motivo"])

    def test_preparar_conjunta_poe_os_orgaos_no_incerteza(self):
        i = self._preparar(self.itens["bcb-resc-13"], {
            "Id": 1, "Documentos": "Res_Conj_0013_v1_O.pdf;100#;",
            "Texto": "<p>O Banco Central do Brasil e a Comissão de Valores Mobiliários tornam público "
                     "que ...</p>"})
        self.assertIn("órgãos no preâmbulo: Banco Central do Brasil e a Comissão de Valores Mobiliários",
                      " ".join(i["notas"]))
        self.assertEqual(list(i["fontes"]), ["consolidado"])  # HTML: a fonte não muda


class TestItensCamada5(unittest.TestCase):
    def setUp(self):
        self.lista = tv.itens_do_acervo({"anbima": ANBIMA, "b3": B3}, 5,
                                        cache_pdf={"anbima": "/pa", "b3": "/pb"})
        self.itens = {i["id"]: i for i in self.lista}

    def test_vigentes_e_entra_com_slug_e_tipo(self):
        self.assertEqual([i["id"] for i in self.lista], [
            "anbima-codigo-de-ofertas-publicas", "anbima-deliberacao-no-1-do-conselho", "anbima-glossario-anbima",
            "b3-regulamento-do-balcao-b3", "b3-glossario", "b3-manualop-v12"])
        tipos = {k: v["tipo"] for k, v in self.itens.items()}
        self.assertEqual(tipos["anbima-codigo-de-ofertas-publicas"], "codigo-autorregulacao")
        self.assertEqual(tipos["anbima-deliberacao-no-1-do-conselho"], "orientacao-autorregulacao")
        self.assertEqual(tipos["anbima-glossario-anbima"], "glossario")
        self.assertEqual(tipos["b3-regulamento-do-balcao-b3"], "regulamento")
        self.assertEqual(tipos["b3-glossario"], "glossario")
        self.assertEqual(tipos["b3-manualop-v12"], "manual")
        self.assertEqual(self.itens["b3-glossario"]["arquivo"], "autorregulacao/b3/glossario.md")

    def test_data_e_origem(self):
        o = {k: (v["data"], v["data_origem"]) for k, v in self.itens.items()}
        self.assertEqual(o["anbima-codigo-de-ofertas-publicas"], ("2025-02-03", "vigencia"))
        self.assertEqual(o["b3-regulamento-do-balcao-b3"], ("2026-09-21", "versao"))
        self.assertEqual(o["b3-glossario"], ("2026-09-24", "last-modified"))  # 02:30 GMT = 23:30 em SP
        self.assertEqual(o["anbima-glossario-anbima"], ("2026-10-29", "leitura"))

    def test_ementa_limpa_e_cache_por_sha1(self):
        self.assertEqual(self.itens["anbima-codigo-de-ofertas-publicas"]["ementa"], "Código de Ofertas Públicas")
        self.assertEqual(self.itens["b3-regulamento-do-balcao-b3"]["ementa"], "REGULAMENTO DO BALCÃO B3")
        self.assertEqual(self.itens["b3-glossario"]["ementa"], "Glossário")
        import hashlib
        h = hashlib.sha1(b"https://b3/Glossario.pdf").hexdigest()[:10]
        self.assertEqual(self.itens["b3-glossario"]["cache_pdf"], os.path.join("/pb", h + ".pdf"))

    def test_slug(self):
        self.assertEqual(tv.slug("Código de Ética — Associados (2024)"), "codigo-de-etica-associados-2024")
        longo = tv.slug("palavra " * 30)
        self.assertLessEqual(len(longo), 80)
        self.assertFalse(longo.endswith("-"))

    def test_colisao_ganha_sufixo_e_aviso(self):
        anbima = {"lido_em": "2026-10-29", "documentos": [
            {"titulo": "Código de Ética", "url": "https://a/1.pdf", "arquivo": "1.pdf", "situacao": "vigente", "tipo": "codigo"},
            {"titulo": "Código de Ética", "url": "https://a/2.pdf", "arquivo": "2.pdf", "situacao": "vigente", "tipo": "codigo"}]}
        it = tv.itens_do_acervo({"anbima": anbima, "b3": {}}, 5)
        self.assertEqual([i["id"] for i in it], ["anbima-codigo-de-etica", "anbima-codigo-de-etica-2"])
        self.assertEqual(it[0]["avisos"], [])
        self.assertIn("1.pdf", it[1]["avisos"][0])
        rel = [{"id": it[1]["id"], "resultado": "ok", "cobertura": 1.0, "avisos": it[1]["avisos"]}]
        self.assertIn("aviso anbima-codigo-de-etica-2", tv.resumo(rel))

    def test_camada_invalida(self):
        with self.assertRaises(ValueError):
            tv.itens_do_acervo({}, 3)


HTML_BCB = ("<html><head><meta charset='utf-8'></head><body>"
            "<p><s>Art. 1º Texto revogado da norma de teste.</s></p>"
            "<p>Art. 1º Esta Resolução dispõe sobre instrumentos financeiros e sobre a contabilidade "
            "das instituições autorizadas a funcionar pelo Banco Central do Brasil.</p>"
            "<table><tr><td><s>Coluna</s></td><td><s>Valor</s></td></tr>"
            "<tr><td><s>A</s></td><td><s>1</s></td></tr></table>"
            "<table><tr><td>Coluna</td><td>Valor</td></tr><tr><td>B</td><td>2</td></tr></table>"
            "<p>Art. 2º Esta Resolução entra em vigor na data de sua publicação.</p></body></html>")


class TestFrontmatterOrgaos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        c4 = {i["id"]: i for i in tv.itens_do_acervo({"perimetro": PERIMETRO, "bcb": ACERVO_BCB}, 4)}
        self.cmn = dict(c4["cmn-res-4966"], fonte_original="https://normativos/x/Res_4966_v1_O.pdf")
        self.circ = dict(c4["bcb-circ-3290"], fontes={"consolidado": {"pdf": "https://n/Circ_3290_v3_L.pdf"}},
                         pdf_bcb={"arquivo": "Circ_3290_v3_L.pdf", "versao": 3, "sufixo": "L"},
                         fonte_original="https://n/Circ_3290_v1_O.pdf")
        c5 = {i["id"]: i for i in tv.itens_do_acervo({"anbima": ANBIMA, "b3": B3}, 5)}
        self.anbima, self.b3 = c5["anbima-codigo-de-ofertas-publicas"], c5["b3-glossario"]
        self.htm = os.path.join(self.dir, "f.htm")
        with open(self.htm, "w", encoding="utf-8") as f:
            f.write(HTML_BCB)
        self.pdf_txt = "Capítulo I. Das disposições gerais do código de autorregulação da entidade. " * 20

    def _valida(self, md, item):
        """Grava no caminho do contrato e passa pelo validador da SPEC."""
        destino = os.path.join(self.dir, "saida", item["arquivo"])
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as f:
            f.write(md)
        self.assertEqual(validar_norma(destino), [])
        pares, _, _ = ler_frontmatter(md)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        return dict(pares)

    def test_cmn_html_sem_textutil_nao_e_conferencia_independente(self):
        with mock.patch.object(tv.shutil, "which", return_value=None):
            md, rel = tv.montar(self.cmn, self.htm, "consolidado", "htm", self.cmn["url_pagina"])
        v = self._valida(md, self.cmn)
        self.assertEqual((v["orgao"], v["numero"], v["publicacao_dou"]), ("cmn", "4966", "2021-11-29"))
        self.assertEqual(v["versao_texto"], "consolidado")
        self.assertEqual(v["nivel_verificacao"], "consolidado-convertido")
        self.assertEqual(v["fonte_original"], "https://normativos/x/Res_4966_v1_O.pdf")
        self.assertTrue(v["incerteza"].startswith(
            "Texto vigente compilado pelo BCB (versão 7 da busca de normas), convertido por script do HTML, "
            "data-base "))
        self.assertIn("sem histórico de redações nem conferência contra o DOU.", v["incerteza"])
        self.assertNotIn("CVM", v["incerteza"])
        self.assertFalse(rel["conferencia_independente"])
        self.assertEqual(rel["tabelas"], 1)  # a tabela toda tachada some
        corpo = md.split("\n---\n", 1)[1]
        self.assertNotIn("revogado", corpo)
        self.assertNotIn("~~", corpo)
        self.assertIn("| B | 2 |", corpo)
        self.assertIn("## Art. 1º", corpo)

    def test_cmn_html_com_textutil_usa_a_conferencia(self):
        with mock.patch.object(tv.shutil, "which", return_value="/usr/bin/textutil"), \
                mock.patch.object(tv, "texto_conferencia", return_value="Art. 1º texto") as conf:
            _, rel = tv.montar(self.cmn, self.htm, "consolidado", "htm", self.cmn["url_pagina"])
        conf.assert_called_once_with(self.htm, "htm")
        self.assertTrue(rel["conferencia_independente"])

    def test_bcb_pdf_compilado_sem_dou(self):
        with mock.patch.object(tv, "_pdf_txt", return_value="Art. 1º Fica estabelecido o procedimento. " * 20), \
                mock.patch.object(tv, "_pdfkit_txt", return_value=None):
            md, _ = tv.montar(self.circ, self.htm, "consolidado", "pdf", "https://n/Circ_3290_v3_L.pdf")
        v = self._valida(md, self.circ)
        self.assertEqual((v["orgao"], v["publicacao_dou"], v["data"]), ("bcb", "2005-09-05", "2005-09-05"))
        self.assertEqual(v["nivel_verificacao"], "pdf-extraido")
        self.assertIn("Texto vigente compilado pelo BCB (PDF Circ_3290_v3_L.pdf, busca de normas, sem número "
                      "de versão), extraído por script do PDF", v["incerteza"])
        self.assertIn("Sem publicação no DOU informada pelo BCB; publicacao_dou repete a data do ato.",
                      v["incerteza"])
        self.assertIn("Extraído de PDF", v["incerteza"])

    def _pdf(self, item):
        with mock.patch.object(tv, "_pdf_txt", return_value=self.pdf_txt), \
                mock.patch.object(tv, "_pdfkit_txt", return_value=None):
            md, _ = tv.montar(item, self.htm, "ato", "pdf", item["fontes"]["ato"]["pdf"])
        return self._valida(md, item)

    def test_anbima(self):
        v = self._pdf(self.anbima)
        self.assertEqual((v["orgao"], v["numero"], v["publicacao_dou"], v["versao_texto"]),
                         ("anbima", "", "", "original"))
        self.assertEqual(v["nivel_verificacao"], "pdf-extraido")
        self.assertTrue(v["incerteza"].startswith(
            "Documento de autorregulação da ANBIMA (vigente a partir de 2025-02-03, segundo a página da "
            "entidade), extraído por script do PDF, data-base "))
        self.assertIn(". Vincula só as instituições aderentes ou participantes. Texto de titularidade da "
                      "ANBIMA, reproduzido para uso informativo; retirado a pedido (ver "
                      "autorregulacao/README.md). Extraído de PDF", v["incerteza"])
        self.assertNotIn("DOU", v["incerteza"])

    def test_b3_data_do_last_modified(self):
        v = self._pdf(self.b3)
        self.assertEqual((v["orgao"], v["tipo"], v["data"]), ("b3", "glossario", "2026-09-24"))
        self.assertIn("Documento de autorregulação da B3 (data 2026-09-24 do cabeçalho Last-Modified do PDF "
                      "[verificar a vigência])", v["incerteza"])
        self.assertIn("Texto de titularidade da B3", v["incerteza"])


class TestProcessarCamadas4e5(unittest.TestCase):
    def test_sem_texto_motivo_nao_grava_arquivo(self):
        with tempfile.TemporaryDirectory() as d:
            item = {"id": "bcb-cc-9999", "arquivo": "bcb/cartas-circulares/9999.md", "fontes": {},
                    "sem_texto_motivo": "norma do perímetro ausente de fontes/acervo-bcb.json"}
            rel = tv.processar([item], os.path.join(d, "s"), os.path.join(d, "c"))
            self.assertEqual(rel[0]["resultado"], "sem-texto")
            self.assertFalse(os.path.exists(os.path.join(d, "s", item["arquivo"])))

    def test_htm_gravado_do_cache_da_api_com_o_mtime_dela(self):
        with tempfile.TemporaryDirectory() as d:
            api = os.path.join(d, "Resolução_CMN-04966.json")
            with open(api, "w", encoding="utf-8") as f:
                json.dump({"conteudo": [{"Id": 1, "Documentos": "Res_4966_v1_O.pdf;3#;", "VersaoNormativo": "7.0",
                                         "Texto": HTML_BCB.split("<body>")[1].split("</body>")[0]}]}, f)
            os.utime(api, (1790000000, 1790000000))  # 2026-09-21 em SP
            item = tv.itens_do_acervo({"perimetro": PERIMETRO[:1], "bcb": ACERVO_BCB}, 4, cache_bcb=d)[0]
            with mock.patch.object(tv.shutil, "which", return_value=None), \
                    mock.patch.object(tv, "_baixar", side_effect=AssertionError("sem rede")):
                rel = tv.processar([item], os.path.join(d, "s"), os.path.join(d, "c"))
            self.assertEqual(rel[0]["resultado"], "ok", rel)
            self.assertEqual(rel[0]["baixado_em"], tv.data_arquivo(api))
            with open(os.path.join(d, "s", "cmn/resolucoes/4966.md"), encoding="utf-8") as f:
                v = dict(ler_frontmatter(f.read())[0])
            self.assertEqual(v["fonte_original"],
                             "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/1/Res_4966_v1_O.pdf")
            self.assertEqual(v["baixado_em"], tv.data_arquivo(api))

    def test_pdf_da_autorregulacao_vem_do_cache(self):
        with tempfile.TemporaryDirectory() as d:
            it = tv.itens_do_acervo({"anbima": ANBIMA, "b3": {}}, 5, cache_pdf={"anbima": d})[0]
            with open(it["cache_pdf"], "wb") as f:
                f.write(b"%PDF-1.4 fixture")
            with mock.patch.object(tv, "_baixar", side_effect=lambda url, destino: destino), \
                    mock.patch.object(tv, "_pdf_txt", return_value="Art. 1º Código de ofertas públicas da entidade. " * 20), \
                    mock.patch.object(tv, "_pdfkit_txt", return_value=None):
                rel = tv.processar([it], os.path.join(d, "s"), os.path.join(d, "c"))
            self.assertEqual(rel[0]["resultado"], "ok", rel)
            with open(os.path.join(d, "c", it["id"] + ".pdf"), "rb") as f:
                self.assertEqual(f.read(), b"%PDF-1.4 fixture")


class TestRegistroDeAssinaturas(unittest.TestCase):
    def test_corta_do_marcador_ao_fim(self):
        txt = ("Art. 51. Este Código entra em vigor.\n28\n← Escaneie para realizar a validação das assinaturas\n"
               "Assinado Eletronicamente por:\nFulano\nE-mail: fulano@exemplo.com\nIP 10.0.0.1\nLatitude:-23.5\n")
        out, cortou = tv.sem_registro_de_assinaturas(txt)
        self.assertTrue(cortou)
        self.assertNotIn("Fulano", out)
        self.assertNotIn("Latitude", out)
        self.assertIn("entra em vigor", out)

    def test_sem_marcador_nao_muda(self):
        self.assertEqual(tv.sem_registro_de_assinaturas("texto\n"), ("texto\n", False))
        self.assertEqual(tv.sem_registro_de_assinaturas(None), (None, False))


class TestLegibilidadeCodigos(unittest.TestCase):
    def test_tabela_de_tickers_e_legivel(self):
        txt = " ".join(["8 D1OW34 BRD1OWBDR005 500.000,00"] * 40)
        self.assertIsNone(tv.motivo_sem_texto(txt))

    def test_type3_continua_ilegivel(self):
        txt = " ".join(["/12 /34 /56 !$%&"] * 60)
        self.assertIsNotNone(tv.motivo_sem_texto(txt))

    def test_bytes_de_imagem_nao_sao_codigo(self):
        txt = " ".join(["4ß·gø Ôýï¬Aÿ7 ×Û¿‘ëú9 ~ßý‚^’ißô?ê"] * 40)
        self.assertIsNotNone(tv.motivo_sem_texto(txt))


# ---------------------------------------------------------------- Fase 4: caractere de controle e --ids

from controle import contar_controle  # noqa: E402

# Texto sintético do PDFKit e do pypdf para o mesmo PDF (o PDF é falso: os extratores são simulados).
OFICIO = ("Ofício-Circular sobre ofertas públicas de valores mobiliários e o registro automático. " * 8
          + "\nReferência: Processo nº O%scios-Circulares SRE 2024 Documento SEI nº 2190952\n")


class TestGlifoNaoLido(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pdf = _pdf_falso(self.tmp.name)
        self.item = {i["id"]: i for i in tv.itens_do_acervo(ACERVO, 2)}["cvm-oc-sse-0326"]

    def _processar(self, pdfkit, pypdf):
        saida = os.path.join(self.tmp.name, "saida")
        with mock.patch.object(tv, "_baixar", side_effect=lambda url, destino: shutil.copyfile(self.pdf, destino) and destino), \
                mock.patch.object(tv, "_pdfkit_txt", return_value=pdfkit), \
                mock.patch.object(tv, "_pdf_txt", return_value=pypdf), \
                mock.patch.object(tv, "_pdf_type3", return_value=False), \
                mock.patch.object(tv, "_ocr", return_value=None):
            rel = tv.processar([self.item], saida, os.path.join(self.tmp.name, "cache"))
        with open(os.path.join(saida, self.item["arquivo"]), encoding="utf-8") as f:
            return f.read(), rel[0]

    def test_pypdf_le_o_glifo_no_mesmo_trecho_e_ele_volta(self):
        md, rel = self._processar(OFICIO % "\x00", (OFICIO % "fí").replace(" nº O", " nº\nO"))
        self.assertIn("Processo nº Ofícios-Circulares SRE", md)
        self.assertEqual(rel["glifos_recuperados"], 1)
        self.assertNotIn("glifos_nao_lidos", rel)
        self.assertNotIn("não lido", dict(ler_frontmatter(md)[0])["incerteza"])

    def test_sem_recuperacao_vira_marca_e_aviso_no_incerteza(self):
        md, rel = self._processar(OFICIO % "\x00", OFICIO % "\x00")
        self.assertIn("Processo nº O�cios-Circulares", md)
        self.assertEqual(contar_controle(md), 0)
        self.assertEqual(rel["glifos_nao_lidos"], 1)
        self.assertIn("1 glifo não lido no PDF, marcado com �", dict(ler_frontmatter(md)[0])["incerteza"])
        self.assertEqual(validar_norma_em(md, self.tmp.name, self.item["arquivo"]), [])

    def test_leitura_ambigua_nao_recupera(self):
        conf = "Processo nº Ofícios-Circulares SRE e Processo nº Oxcios-Circulares SRE"
        self.assertEqual(tv.recuperar_glifos("Processo nº O\x00cios-Circulares SRE", conf),
                         ("Processo nº O\x00cios-Circulares SRE", 0))
        # contexto curto demais (início do texto) também não
        self.assertEqual(tv.recuperar_glifos("O\x00cios", "Ofícios")[1], 0)
        # dois NUL: cada um com o seu trecho
        txt, n = tv.recuperar_glifos("Processo nº O\x00cios e o arquivo O\x00cio final",
                                     "Processo nº Ofícios e o arquivo Ofício final")
        self.assertEqual((txt, n), ("Processo nº Ofícios e o arquivo Ofício final", 2))

    def test_gravacao_limpa_controle_e_preserva_tab_e_quebra(self):
        md = "---\nid: x\n---\n\nO\x00cios na sexta\x02feira\x0b.\n\tcom tab\r\nfim\x7f\n"
        saida = os.path.join(self.tmp.name, "saida")
        with mock.patch.object(tv, "obter_fonte", return_value=self.pdf), \
                mock.patch.object(tv, "montar", return_value=(md, {"id": self.item["id"], "resultado": "ok"})):
            tv.processar([self.item], saida, os.path.join(self.tmp.name, "cache"))
        with open(os.path.join(saida, self.item["arquivo"]), encoding="utf-8", newline="") as f:
            gravado = f.read()
        self.assertEqual(gravado, "---\nid: x\n---\n\nO�cios na sexta-feira.\n\tcom tab\r\nfim\n")


def validar_norma_em(md, raiz, arquivo):
    caminho = os.path.join(raiz, "validar", *arquivo.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(md)
    return validar_norma(caminho)


class TestIds(unittest.TestCase):
    def setUp(self):
        self.itens = tv.itens_do_acervo(ACERVO, 2)

    def test_filtra_por_id_ou_slug_na_ordem_dos_itens(self):
        escolhidos, faltam = tv.filtrar_ids(self.itens, ["oc-anual-sep-2022", " cvm-oc-sse-0326", "po-35"])
        self.assertEqual([i["id"] for i in escolhidos],
                         ["cvm-po-35", "cvm-oc-sse-0326", "cvm-oc-anual-sep-2022"])
        self.assertEqual(faltam, [])
        self.assertEqual(tv.filtrar_ids(self.itens, ["cvm-oc-sse-0326", "nao-existe"])[1], ["nao-existe"])

    def _main(self, argv_extra, rel_anterior=None):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        acervo = os.path.join(tmp, "acervo.json")
        with open(acervo, "w", encoding="utf-8") as f:
            json.dump(ACERVO, f)
        relpath = os.path.join(tmp, "rel.json")
        if rel_anterior is not None:
            with open(relpath, "w", encoding="utf-8") as f:
                if isinstance(rel_anterior, str):
                    f.write(rel_anterior)  # texto cru (JSON corrompido)
                else:
                    json.dump(rel_anterior, f)
        vistos = []

        def processar(itens, saida, cache, mostrar=False):
            vistos.extend(i["id"] for i in itens)
            return [{"id": i["id"], "resultado": "ok", "novo": True} for i in itens]

        with mock.patch.object(tv, "processar", side_effect=processar), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            rc = tv.main(["texto_vigente.py", "--camada", "2", "--acervo", acervo, "--saida", tmp,
                          "--relatorio", relpath] + argv_extra)
        rel = None
        if os.path.exists(relpath):
            with open(relpath, encoding="utf-8") as f:
                rel = f.read() if isinstance(rel_anterior, str) else json.load(f)
        return rc, vistos, rel

    def test_ids_so_processa_os_escolhidos_e_atualiza_o_relatorio(self):
        anterior = [{"id": "cvm-po-35", "resultado": "ok"}, {"id": "cvm-oc-sse-0326", "resultado": "ok"},
                    {"id": "cvm-oc-anual-sep-2022", "resultado": "ok"}]
        rc, vistos, rel = self._main(["--ids", "oc-sse-0326"], anterior)
        self.assertEqual(rc, 0)
        self.assertEqual(vistos, ["cvm-oc-sse-0326"])
        self.assertEqual([r["id"] for r in rel], ["cvm-po-35", "cvm-oc-sse-0326", "cvm-oc-anual-sep-2022"])
        self.assertEqual([bool(r.get("novo")) for r in rel], [False, True, False])

    def test_sem_ids_nada_muda(self):
        rc, vistos, rel = self._main([], [{"id": "velho"}])
        self.assertEqual(rc, 0)
        self.assertEqual(vistos, ["cvm-po-35", "cvm-oc-sse-0326", "cvm-oc-anual-sep-2022"])
        self.assertEqual([r["id"] for r in rel], vistos)  # relatório da camada inteira, trocado

    def test_id_sem_item_e_erro(self):
        rc, vistos, rel = self._main(["--ids", "cvm-oc-sse-0326,oc-xyz-9999"], [{"id": "velho"}])
        self.assertEqual(rc, 2)
        self.assertEqual(vistos, [])
        self.assertEqual(rel, [{"id": "velho"}])

    def test_relatorio_anterior_corrompido_para_antes_de_gravar(self):
        for ruim in ('[{"id": "cvm-po-35", "resultado": "ok"', '{"id": "cvm-po-35"}', '[{"resultado": "ok"}]'):
            with self.subTest(ruim=ruim):
                rc, vistos, rel = self._main(["--ids", "oc-sse-0326"], ruim)
                self.assertEqual(rc, 1)
                self.assertEqual(vistos, [])  # processar não rodou: nenhum .md gravado
                self.assertEqual(rel, ruim)   # relatório intacto

    def test_ler_relatorio_anterior_diz_o_problema(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        caminho = os.path.join(tmp, "rel.json")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("[{")
        with self.assertRaisesRegex(ValueError, "ilegível"):
            tv.ler_relatorio_anterior(caminho)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump({"id": "x"}, f)
        with self.assertRaisesRegex(ValueError, "fora do formato"):
            tv.ler_relatorio_anterior(caminho)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump([{"id": "x"}], f)
        self.assertEqual(tv.ler_relatorio_anterior(caminho), [{"id": "x"}])
