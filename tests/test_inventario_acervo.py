"""Testes do inventário do perímetro da v1.0 (sem rede: HTML e planilha montados no teste)."""
import os
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from inventario_acervo import (  # noqa: E402
    detalhes_da_pagina, itens_da_busca, ler_estoque, oficio, situacao_resolucao)

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


class TestPagina(unittest.TestCase):
    def test_detalhes(self):
        d = detalhes_da_pagina(PAGINA)
        self.assertEqual(d["data"], "2020-08-27")
        self.assertEqual(d["dou"], "2020-08-28")
        self.assertEqual(d["revogada"], "REVOGADA pela Resolução 81/22.")
        self.assertEqual(d["alterada_por"], ["10/20", "20/21"])
        self.assertIn("docx", d["arquivos"]["consolidado"])
        self.assertIn("pdf", d["arquivos"]["ato"])

    def test_situacao(self):
        self.assertEqual(situacao_resolucao("Resolução CVM 5 (Revogada)", "", "Altera", True), "revogada")
        self.assertEqual(situacao_resolucao("Resolução CVM 21", "", "Dispõe", True), "vigente")
        self.assertEqual(situacao_resolucao("Resolução CVM 162", "", "Altera a Instrução", False),
                         "so-alteradora")
        self.assertEqual(situacao_resolucao("Resolução CVM 249", "", "Institui", False), "verificar")


class TestEstoque(unittest.TestCase):
    def test_ler_estoque(self):
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ss = ("<sst %s><si><t>(atualizado em 08/09/2026)</t></si>"
              "<si><t>Resolução CVM 21, de 25 de fevereiro de 2021</t></si>"
              "<si><t>Resolução CVM nº 9, de 27 de outubro de 2020</t></si></sst>" % ns)
        sheet = ('<worksheet %s><sheetData><row><c t="s"><v>0</v></c></row>'
                 '<row><c t="s"><v>1</v></c><c t="s"><v>2</v></c></row></sheetData></worksheet>' % ns)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "e.xlsx")
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("xl/sharedStrings.xml", ss)
                z.writestr("xl/worksheets/sheet1.xml", sheet)
            self.assertEqual(ler_estoque(path), ("2026-09-08", [9, 21]))


if __name__ == "__main__":
    unittest.main()
