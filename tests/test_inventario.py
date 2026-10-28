"""Testes do inventário de atos alteradores (sem rede: usa a página salva)."""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from inventario import carregar_inventario, extrair_pagina, montar_inventario  # noqa: E402


def ler(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as f:
        return f.read()


class TestExtrairPaginaRes17(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pag = extrair_pagina(ler("resol017.html"))

    def test_identificacao(self):
        self.assertEqual(self.pag["numero"], 17)
        self.assertEqual(self.pag["data"], "2021-02-09")
        self.assertEqual(self.pag["dou"], "2021-02-10")

    def test_alteradoras_na_ordem(self):
        self.assertEqual(
            [(a["numero"], a["ano"]) for a in self.pag["alteradoras"]],
            [(162, 2022), (226, 2025)],
        )

    def test_consolidado_docx_e_pdf(self):
        cons = self.pag["url_consolidado"]
        self.assertEqual(
            cons["docx"],
            "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/001/resol017consolid.docx",
        )
        self.assertTrue(cons["pdf"].endswith("/anexos/001/resol017consolid.pdf"))

    def test_original(self):
        self.assertEqual(len(self.pag["url_original"]), 1)
        self.assertTrue(self.pag["url_original"][0].endswith("/anexos/001/resol017.pdf"))

    def test_ementa(self):
        self.assertTrue(self.pag["ementa"].startswith("Dispõe sobre o exercício da função de agente fiduciário"))
        self.assertNotIn("DOU", self.pag["ementa"])


ATO_ALTERADOR = """<html><body><article class="contentTextoGeral">
<h2>Resolução CVM 999</h2>
<section><p><b>Thu Mar 06 16:00:00 BRT 2025</b></p>
<p>Altera as Resoluções CVM n&ordm; <a href="/legislacao/resolucoes/resol017.html">17</a>, de 9 de fevereiro de 2021,
e CVM n&ordm; <a href="/legislacao/resolucoes/resol060.html">60</a>, de 23 de dezembro de 2021.</p>
<p>(Publicada no DOU de 07.03.2025)</p>
<p>- Resolução CVM 999: <a href="/legislacao/resolucoes/anexos/200/resol999.htm">[HTML]</a> /
<a href="/export/sites/cvm/legislacao/resolucoes/anexos/200/resol999.pdf">[PDF]</a> /
<a href="/legislacao/resolucoes/anexos/200/resol999.docx">[DOC]</a></p>
</section></article></body></html>"""

SEM_CONSOLIDADO = """<html><body><article class="contentTextoGeral">
<h2>Resolução CVM 998</h2>
<section><p><b>Tue Feb 09 19:00:00 BRST 2021</b></p>
<p>Dispõe sobre assunto fictício.<br/><br/>(Publicada no DOU de 10.02.2021)<br/><br/>(Retificada no DOU de 04.03.2021 e de 09.03.2021)</p>
</section></article></body></html>"""


class TestExtrairPaginaOutros(unittest.TestCase):
    def test_ato_alterador_lista_normas_da_ementa_e_texto_do_ato(self):
        pag = extrair_pagina(ATO_ALTERADOR)
        self.assertEqual(pag["numero"], 999)
        self.assertEqual(pag["normas_na_ementa"], [17, 60])
        self.assertEqual(pag["alteradoras"], [])
        self.assertTrue(pag["url_ato"]["htm"].endswith("/anexos/200/resol999.htm"))
        self.assertTrue(pag["url_ato"]["pdf"].endswith("/anexos/200/resol999.pdf"))
        self.assertTrue(pag["url_ato"]["docx"].endswith("/anexos/200/resol999.docx"))

    def test_sem_consolidado_e_com_retificacoes(self):
        pag = extrair_pagina(SEM_CONSOLIDADO)
        self.assertEqual(pag["url_consolidado"], {})
        self.assertEqual(pag["retificada_dou"], ["2021-03-04", "2021-03-09"])
        self.assertEqual(pag["normas_na_ementa"], [])


class TestMontarEInventario(unittest.TestCase):
    def test_monta_entrada_com_data_das_alteradoras(self):
        paginas = {
            17: extrair_pagina(ler("resol017.html")),
            162: {"numero": 162, "data": "2022-07-13", "dou": "2022-07-14",
                  "url_pagina": "u162", "normas_na_ementa": [17, 21], "url_ato": {}},
            226: {"numero": 226, "data": "2025-03-06", "dou": "2025-03-07",
                  "url_pagina": "u226", "normas_na_ementa": [17, 60], "url_ato": {}},
        }
        inv = montar_inventario([17], paginas)
        self.assertEqual(len(inv), 1)
        e = inv[0]
        self.assertEqual(e["id"], "cvm-res-17")
        self.assertEqual(e["numero"], 17)
        self.assertEqual(
            [(a["numero"], a["data"], a["dou"]) for a in e["alteradoras"]],
            [(162, "2022-07-13", "2022-07-14"), (226, "2025-03-06", "2025-03-07")],
        )

    def test_carregar_inventario_roundtrip(self):
        dados = [{"id": "cvm-res-1", "numero": 1}]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dados, f)
            caminho = f.name
        try:
            self.assertEqual(carregar_inventario(caminho), dados)
        finally:
            os.unlink(caminho)


if __name__ == "__main__":
    unittest.main()
