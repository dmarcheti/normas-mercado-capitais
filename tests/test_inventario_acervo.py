"""Testes do inventário do perímetro da v1.0 (sem rede: HTML e planilha montados no teste)."""
import os
import re
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from inventario_acervo import (  # noqa: E402
    atribuir_slugs, detalhes_da_pagina, itens_da_busca, ler_estoque, normalizar_slug, oficio,
    pdf_do_oficio, situacao_resolucao)

SLUG_OK = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")

BUSCA = """
<article>
  <h3><a href="/legislacao/oficios-circulares/sin/oc-sin-0225.html" title="Ofício-Circular CVM/SIN 02/25"> x</a></h3>
  <div class="contentDesc">
    Interpretação de dispositivos da Resolução CVM nº 175
  </div>
  <div class="infoItem"><p><b>Data:</b> 23/01/2025</p></div>
</article>
<article><p>sem título</p></article>
"""

PAGINA_OC = """
<article class="contentTextoGeral">
<h2>Ofício-Circular CVM/SIN 02/25</h2>
<p><b>Thu Jan 23 16:27:00 BRT 2025</b></p>
<p>&nbsp;Interpretação de dispositivos da Resolução CVM nº 175 e da Instrução CVM nº 555.</p>
<table><tr>
<td><a class="download" href="/export/sites/cvm/legislacao/oficios-circulares/sin/anexos/oc-sin-02-2025-final.pdf">x</a></td>
<td><a href="/export/sites/cvm/legislacao/oficios-circulares/sin/anexos/oc-sin-02-2025-final.pdf">Ofício-Circular CVM/SIN 02/25</a></td>
</tr></table>
</article>
"""

PAGINA = """
<article class="contentTextoGeral">
<h2>Resolução CVM 5</h2>
<p><b>Thu Aug 27 11:30:00 BRT 2020</b></p>
<p>Altera a Instrução CVM nº 481, de 17 de dezembro de 2009. (Publicada no DOU de 28.08.2020)</p>
<p><a href="/export/sites/cvm/legislacao/resolucoes/anexos/001/resol005.pdf">Resolução CVM 5</a></p>
<p><a href="/legislacao/resolucoes/anexos/001/resol005consolid.docx">texto consolidado [DOC]</a></p>
<p>ALTERADA pelas Resoluções <a href="/legislacao/resolucoes/resol010.html">10/20</a> e
<a href="/legislacao/resolucoes/resol020.html">20/21</a>.</p>
<p>REVOGADA pela Resolução 81/22.</p>
</article>
"""


class TestBusca(unittest.TestCase):
    def test_itens_e_oficio(self):
        itens = itens_da_busca(BUSCA)
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["data"], "2025-01-23")
        oc = oficio(itens[0])
        self.assertEqual(oc["superintendencia"], "sin")
        self.assertEqual(oc["cita"], ["Resolução 175"])
        self.assertTrue(oc["url_pdf"].endswith("/oficios-circulares/sin/anexos/oc-sin-0225.pdf"))
        self.assertEqual(oc["url_pdf_origem"], "palpite")
        self.assertEqual(oc["slug"], "oc-sin-0225")
        self.assertEqual(oc["slug_cvm"], "oc-sin-0225")
        self.assertEqual(oc["id"], "cvm-oc-sin-0225")

    def test_pdf_vem_da_pagina(self):
        oc = oficio(itens_da_busca(BUSCA)[0], PAGINA_OC)
        self.assertEqual(oc["url_pdf"], "https://conteudo.cvm.gov.br/export/sites/cvm/legislacao/"
                                        "oficios-circulares/sin/anexos/oc-sin-02-2025-final.pdf")
        self.assertEqual(oc["url_pdf_origem"], "pagina")
        self.assertEqual(oc["ementa"], "Interpretação de dispositivos da Resolução CVM nº 175 e da "
                                       "Instrução CVM nº 555.")
        self.assertEqual(oc["cita"], ["Resolução 175", "Instrução 555"])

    def test_pagina_sem_pdf(self):
        self.assertEqual(pdf_do_oficio("<article class='contentTextoGeral'><h2>x</h2></article>"),
                         {"url_pdf": None, "ementa": ""})


def _oc(pasta, slug_cvm, data):
    return {"superintendencia": pasta, "slug_cvm": slug_cvm, "data": data,
            "url_pagina": "https://x/legislacao/oficios-circulares/%s/%s.html" % (pasta, slug_cvm)}


class TestSlug(unittest.TestCase):
    def test_normalizacao(self):
        casos = {
            "oc_snc_sep_0124": "oc-snc-sep-0124",
            "Oficios-Circulares-0124": "oficios-circulares-0124",
            "oc_snc_sep_0123": "oc-snc-sep-0123",
            "Oficio-Circular-SIN-SSE-01-2022": "oficio-circular-sin-sse-01-2022",
            "OficioCircularCVMSSE0122": "oficio-circular-cvmsse0122",
            "OC_SRE_0118": "oc-sre-0118",
            "oc-sse-0326": "oc-sse-0326",
            "oc__x  y--Z": "oc-x-y-z",
            "anual2023Teste": "anual2023-teste",
        }
        for original, esperado in casos.items():
            self.assertEqual(normalizar_slug(original), esperado, original)
            self.assertTrue(SLUG_OK.fullmatch(normalizar_slug(original)))

    def test_duplicatas_desempate_pela_pasta_e_data(self):
        ocs = [_oc("old-sse-sin-snc", "oc-snc-sse-sin-0125", "2025-06-12"),
               _oc("sse-sin-snc", "oc-snc-sse-sin-0125", "2025-01-24"),
               _oc("sin", "oc-sin-0623", "2023-09-27"),
               _oc("sse1", "oc-sin-0623", "2023-07-05")]
        atribuir_slugs(ocs)
        por = {(o["superintendencia"], o["slug_cvm"]): o for o in ocs}
        self.assertEqual(por[("sse-sin-snc", "oc-snc-sse-sin-0125")]["slug"], "oc-snc-sse-sin-0125")
        self.assertEqual(por[("old-sse-sin-snc", "oc-snc-sse-sin-0125")]["slug"],
                         "oc-snc-sse-sin-0125-old-sse-sin-snc")
        # a pasta que bate com a sigla do slug vence a data (sse1/oc-sin-0623 é o SSE 06/23)
        self.assertEqual(por[("sin", "oc-sin-0623")]["slug"], "oc-sin-0623")
        self.assertEqual(por[("sse1", "oc-sin-0623")]["slug"], "oc-sin-0623-sse1")
        self.assertEqual(por[("sse1", "oc-sin-0623")]["id"], "cvm-oc-sin-0623-sse1")
        self.assertEqual([o["slug_cvm"] for o in ocs][0], "oc-snc-sse-sin-0125")  # ordem mantida

    def test_colisao_depois_da_normalizacao_e_sufixo_numerico(self):
        ocs = [_oc("sre", "OC_SRE_0118", "2018-02-27"),
               _oc("sre", "oc-sre-0118", "2018-01-10"),
               _oc("sre", "oc_sre_0118", "2018-03-01"),
               _oc("sre", "oc-sre-0118-sre", "2017-01-01")]
        atribuir_slugs(ocs)
        slugs = [o["slug"] for o in ocs]
        self.assertEqual(slugs[1], "oc-sre-0118")
        self.assertEqual(slugs[3], "oc-sre-0118-sre")
        self.assertEqual(slugs[0], "oc-sre-0118-sre-2")
        self.assertEqual(slugs[2], "oc-sre-0118-sre-3")

    def test_unicidade_em_600(self):
        pastas = ["sin", "sse1", "sep", "snc-sep", "sre", "old-sse-sin-snc"]
        ocs = []
        for i in range(600):
            n = i % 37  # força muitas repetições, com e sem diferença de caixa e separador
            slug = ["oc-sin-%02d" % n, "OC_SIN_%02d" % n, "OcSin%02d" % n][i % 3]
            ocs.append(_oc(pastas[i % len(pastas)], slug, "20%02d-01-%02d" % (i % 25, 1 + i % 28)))
        atribuir_slugs(ocs)
        slugs = [o["slug"] for o in ocs]
        self.assertEqual(len(set(slugs)), 600)
        self.assertTrue(all(SLUG_OK.fullmatch(s) for s in slugs))
        self.assertTrue(all(o["id"] == "cvm-" + o["slug"] for o in ocs))
        self.assertTrue(all("slug_cvm" in o for o in ocs))


class TestPagina(unittest.TestCase):
    def test_detalhes(self):
        d = detalhes_da_pagina(PAGINA)
        self.assertEqual(d["data"], "2020-08-27")
        self.assertEqual(d["dou"], "2020-08-28")
        self.assertEqual(d["ementa"], "Altera a Instrução CVM nº 481, de 17 de dezembro de 2009.")
        self.assertEqual(d["revogada"], "REVOGADA pela Resolução 81/22.")
        self.assertEqual(d["alterada_por"], ["10/20", "20/21"])
        self.assertIn("docx", d["arquivos"]["consolidado"])
        self.assertIn("pdf", d["arquivos"]["ato"])

    def test_ementa_em_div(self):
        html = ('<article class="contentTextoGeral"><h2>Resolução CVM 122</h2>'
                '<section class="pull-left contentArticle"><p> <b>Fri Jun 03 16:00:00 BRT 2022</b> </p>'
                '<div>Aprova a Consolidação da ICPC 01 (R1) &ndash; CPC, que trata de contratos de'
                '&nbsp;concessão.<br /> <br /> (Publicada no DOU de 06.06.2022)<br /></div>'
                '<div class="contentVejaMais"></div></section></article>')
        d = detalhes_da_pagina(html)
        self.assertEqual(d["ementa"],
                         "Aprova a Consolidação da ICPC 01 (R1) – CPC, que trata de contratos de concessão.")
        self.assertEqual(d["dou"], "2022-06-06")

    def test_situacao(self):
        self.assertEqual(situacao_resolucao("Resolução CVM 5 (Revogada)", "", "Altera", True), "revogada")
        self.assertEqual(situacao_resolucao("Resolução CVM 21", "", "Dispõe", True), "vigente")
        self.assertEqual(situacao_resolucao("Resolução CVM 162", "", "Altera a Instrução", False),
                         "so-alteradora")
        self.assertEqual(situacao_resolucao("Resolução CVM 249", "", "Institui", False), "verificar")
        self.assertEqual(situacao_resolucao("Resolução CVM 26", "", "Dispõe sobre a postergação",
                                            False), "verificar")


class TestEstoque(unittest.TestCase):
    def test_ler_estoque(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ss = ("<sst %s><si><t>(atualizado em 08/09/2026)</t></si>"
              "<si><t>Resolução CVM 21, de 25 de fevereiro de 2021</t></si>"
              "<si><t>Resolução CVM nº 9, de 27 de outubro de 2020</t></si>"
              "<si><t>Grupo temático</t></si><si><t>Norma editada</t></si>"
              "<si><t>Administradores de carteiras</t></si><si><t>Normas contábeis</t></si>"
              "<si><t>Resolução CVM 22, de 25 de fevereiro de 2021</t></si></sst>" % ns)
        sheet = ('<worksheet %s><sheetData><row><c t="s"><v>0</v></c></row>'
                 '<row><c t="s"><v>3</v></c><c t="s"><v>4</v></c></row>'
                 '<row><c t="s"><v>5</v></c><c t="s"><v>1</v></c></row>'
                 '<row><c/><c t="s"><v>7</v></c></row>'
                 '<row><c t="s"><v>6</v></c><c t="s"><v>2</v></c></row>'
                 '</sheetData></worksheet>' % ns)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.xlsx")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("xl/sharedStrings.xml", ss)
                z.writestr("xl/worksheets/sheet1.xml", sheet)
            self.assertEqual(ler_estoque(path), (
                "2026-09-08", [9, 21, 22],
                {21: "Administradores de carteiras", 22: "Administradores de carteiras",
                 9: "Normas contábeis"}))


if __name__ == "__main__":
    unittest.main()


class TestDesempatePelaPasta(unittest.TestCase):
    def test_pasta_que_bate_com_o_slug_fica_com_o_base(self):
        from inventario_acervo import atribuir_slugs
        ocs = [
            {"slug_cvm": "oc-sin-0623", "superintendencia": "sse1", "data": "2023-07-05"},
            {"slug_cvm": "oc-sin-0623", "superintendencia": "sin", "data": "2023-08-01"},
            {"slug_cvm": "oc-snc-sse-sin-0125", "superintendencia": "old-sse-sin-snc", "data": "2025-01-01"},
            {"slug_cvm": "oc-snc-sse-sin-0125", "superintendencia": "sse-sin-snc", "data": "2025-06-12"},
        ]
        atribuir_slugs(ocs)
        self.assertEqual([o["slug"] for o in ocs], [
            "oc-sin-0623-sse1", "oc-sin-0623",
            "oc-snc-sse-sin-0125-old-sse-sin-snc", "oc-snc-sse-sin-0125"])
