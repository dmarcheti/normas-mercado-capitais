"""Testes da conversão para Markdown (sem rede).

A fixture do DOU é um recorte real da página da Res. CVM 17. O DOCX de teste
é montado aqui com `zipfile`, no formato do consolidado da CVM (runs, sdt,
tachado para a redação antiga, tabela).
"""
import os
import re
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from converter import docx_para_md, dou_html_para_md, normalizar_artigos  # noqa: E402

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def ler(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as f:
        return f.read()


def run(texto, tachado=False):
    rpr = "<w:rPr><w:strike/></w:rPr>" if tachado else ""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, texto)


def par(*runs, estilo=None):
    ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % estilo if estilo else ""
    return "<w:p>%s%s</w:p>" % (ppr, "".join(runs))


def montar_docx(corpo):
    xml = '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>' % (NS, corpo)
    fd, caminho = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", xml)
    return caminho


class TestDouHtml(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.md = dou_html_para_md(ler("dou017.html"))

    def test_nbsp_e_espacos_viram_espaco_simples(self):
        self.assertNotIn("\xa0", self.md)
        self.assertNotIn("  ", self.md)
        self.assertIn("Art. 1º A presente Resolução regulamenta", self.md)
        self.assertIn("Art. 17. O agente fiduciário deve manter", self.md)

    def test_um_paragrafo_por_linha_e_sem_assinatura(self):
        linhas = [l for l in self.md.split("\n") if l.strip()]
        self.assertTrue(linhas[0].startswith("RESOLUÇÃO CVM Nº 17"))
        self.assertTrue(linhas[1].startswith("Dispõe sobre"))
        self.assertNotIn("MARCELO BARBOSA", self.md)
        self.assertIn("I - os deveres e responsabilidades do agente fiduciário;", linhas)

    def test_tabela_vira_tabela_markdown(self):
        html = (
            '<div class="texto-dou"><p class="dou-paragraph">Veja:</p>'
            "<table><tr><td>Prazo</td><td>Dias</td></tr>"
            "<tr><td>Envio</td><td>7</td></tr></table></div>"
        )
        md = dou_html_para_md(html)
        self.assertIn("| Prazo | Dias |", md)
        self.assertIn("| --- | --- |", md)
        self.assertIn("| Envio | 7 |", md)

    def test_html_sem_texto_do_dou_levanta_erro(self):
        with self.assertRaises(ValueError):
            dou_html_para_md("<html><body><p>nada</p></body></html>")


class TestNormalizarArtigos(unittest.TestCase):
    def test_ordinal(self):
        self.assertEqual(normalizar_artigos("Art. 1º A norma.").split("\n"),
                         ["## Art. 1º", "", "A norma."])

    def test_numero_com_ponto(self):
        md = normalizar_artigos("Art. 10.  As assembleias.")
        self.assertIn("## Art. 10\n", md)
        self.assertNotIn("## Art. 10.", md)
        self.assertIn("As assembleias.", md)

    def test_sufixo_letra(self):
        md = normalizar_artigos("Art. 12-A  Texto novo.")
        self.assertTrue(md.startswith("## Art. 12-A\n"))
        self.assertIn("Texto novo.", md)

    def test_ordinal_com_sufixo(self):
        self.assertTrue(normalizar_artigos("Art. 5º-A Texto.").startswith("## Art. 5º-A\n"))

    def test_artigo_sozinho_na_linha(self):
        self.assertEqual(normalizar_artigos("Art. 9º"), "## Art. 9º")

    def test_milhar(self):
        self.assertTrue(normalizar_artigos("Art. 1.001. Texto.").startswith("## Art. 1.001\n"))

    def test_citacao_no_meio_da_frase_nao_vira_heading(self):
        md = normalizar_artigos("Art. 2º Nos termos do art. 5º, aplica-se.\n\nII - conforme o Art. 7º desta.")
        self.assertEqual(md.count("## "), 1)
        self.assertIn("Nos termos do art. 5º, aplica-se.", md)
        self.assertIn("II - conforme o Art. 7º desta.", md)

    def test_paragrafos_incisos_e_alineas_ficam_como_texto(self):
        md = normalizar_artigos("Art. 2º Caput.\n\n§ 1º Texto.\n\nI - inciso;\n\na) alínea.\n\nParágrafo único. Fim.")
        self.assertEqual(md.count("## "), 1)
        for t in ("§ 1º Texto.", "I - inciso;", "a) alínea.", "Parágrafo único. Fim."):
            self.assertIn(t, md)

    def test_riscado_nao_vira_heading(self):
        self.assertEqual(normalizar_artigos("~~Art. 9º Texto antigo.~~").count("## "), 0)

    def test_nota_de_alteracao_que_comeca_com_artigo_nao_vira_heading(self):
        md = normalizar_artigos(
            "Art. 73-A incluído pela Resolução CVM nº 214, de 30 de setembro de 2024.\n\n"
            "Art. 9º revogado pela Resolução CVM nº 181, de 28 de março de 2023.\n\n"
            "Art. 9º REVOGADO"
        )
        self.assertEqual(md.count("## "), 1)
        self.assertIn("## Art. 9º\n\nREVOGADO", md)

    def test_idempotente(self):
        md = normalizar_artigos("Art. 1º A.\n\nArt. 10. B.")
        self.assertEqual(normalizar_artigos(md), md)

    def test_contagem_de_headings_igual_a_de_artigos_da_fixture(self):
        html = ler("dou017.html")
        n_artigos = len(re.findall(r">Art\. \d", html))
        md = normalizar_artigos(dou_html_para_md(html))
        headings = re.findall(r"^## Art\. .+$", md, flags=re.M)
        self.assertEqual(n_artigos, 5)
        self.assertEqual(len(headings), n_artigos)
        self.assertEqual(headings, ["## Art. 1º", "## Art. 2º", "## Art. 3º", "## Art. 10", "## Art. 17"])
        # a citação "art. 7º" no meio do Art. 3º não virou heading
        self.assertIn("na forma do art. 7º.", md)


class TestDocx(unittest.TestCase):
    def setUp(self):
        corpo = (
            par(run("Resolução CVM nº "), "<w:sdt><w:sdtContent>", run("17, DE 9 de fevereiro DE 2021"),
                "</w:sdtContent></w:sdt>", estilo="TtulodaResoluo")
            + par(run("CAPÍTULO I – ÂMBITO"), estilo="Captulo")
            + par(run("Art. 1º"), "<w:r><w:tab/></w:r>", run("A norma regula X."))
            + par(run("Art. 9º  texto antigo", tachado=True), run(" continua", tachado=True))
            + par(run("Art. 9º  Texto novo."))
            + par(run("Caput com redação dada pela Resolução CVM nº 226 de 6 de março de 2025."))
            + "<w:tbl><w:tr><w:tc>" + par(run("Prazo")) + "</w:tc><w:tc>" + par(run("Dias"))
            + "</w:tc></w:tr><w:tr><w:tc>" + par(run("Envio")) + "</w:tc><w:tc>" + par(run("7"))
            + "</w:tc></w:tr></w:tbl>"
            + par(run("Art. 12-A  Incluído."))
        )
        self.caminho = montar_docx(corpo)
        self.addCleanup(os.remove, self.caminho)
        self.md = docx_para_md(self.caminho)

    def test_um_paragrafo_por_linha_com_sdt_e_tab(self):
        linhas = [l for l in self.md.split("\n") if l.strip()]
        self.assertEqual(linhas[0], "Resolução CVM nº 17, DE 9 de fevereiro DE 2021")
        self.assertIn("Art. 1º A norma regula X.", linhas)

    def test_tachado_vira_marca_unica(self):
        self.assertIn("~~Art. 9º texto antigo continua~~", self.md)
        self.assertIn("Art. 9º Texto novo.", self.md)

    def test_notas_de_alteracao_ficam_no_texto(self):
        self.assertIn("Caput com redação dada pela Resolução CVM nº 226 de 6 de março de 2025.", self.md)

    def test_tabela(self):
        self.assertIn("| Prazo | Dias |", self.md)
        self.assertIn("| --- | --- |", self.md)
        self.assertIn("| Envio | 7 |", self.md)

    def test_artigos_apos_normalizar(self):
        md = normalizar_artigos(self.md)
        self.assertEqual(re.findall(r"^## Art\. .+$", md, flags=re.M),
                         ["## Art. 1º", "## Art. 9º", "## Art. 12-A"])


if __name__ == "__main__":
    unittest.main()
