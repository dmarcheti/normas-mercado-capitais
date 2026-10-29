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

from converter import docx_para_md, dou_html_para_md, normalizar_artigos, planalto_html_para_md  # noqa: E402

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def ler(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as f:
        return f.read()


def run(texto, tachado=False):
    rpr = "<w:rPr><w:strike/></w:rPr>" if tachado else ""
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, texto)


def par(*runs, estilo=None, num=None):
    """`num` = (numId, ilvl) cria o w:numPr do parágrafo (lista automática)."""
    ppr = ""
    if estilo or num:
        ppr = "<w:pPr>"
        if estilo:
            ppr += '<w:pStyle w:val="%s"/>' % estilo
        if num:
            ppr += '<w:numPr><w:ilvl w:val="%d"/><w:numId w:val="%d"/></w:numPr>' % (num[1], num[0])
        ppr += "</w:pPr>"
    return "<w:p>%s%s</w:p>" % (ppr, "".join(runs))


def montar_docx(corpo, numeracao=None):
    xml = '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>' % (NS, corpo)
    fd, caminho = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", xml)
        if numeracao:
            z.writestr("word/numbering.xml", '<?xml version="1.0" encoding="UTF-8"?><w:numbering %s>%s</w:numbering>'
                       % (NS, numeracao))
    return caminho


def nivel(ilvl, fmt, texto, inicio=1):
    return ('<w:lvl w:ilvl="%d"><w:start w:val="%d"/><w:numFmt w:val="%s"/><w:lvlText w:val="%s"/></w:lvl>'
            % (ilvl, inicio, fmt, texto))


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


class TestDocxNumeracao(unittest.TestCase):
    """Listas automáticas do Word: o número não está no XML, vem de numbering.xml."""

    NUMERACAO = (
        '<w:abstractNum w:abstractNumId="0">' + nivel(0, "upperRoman", "%1 –") + nivel(1, "lowerLetter", "%2)") + "</w:abstractNum>"
        '<w:abstractNum w:abstractNumId="1">' + nivel(0, "lowerLetter", "%1)") + "</w:abstractNum>"
        '<w:abstractNum w:abstractNumId="2">' + nivel(0, "bullet", "\uf0b7") + "</w:abstractNum>"
        '<w:abstractNum w:abstractNumId="3">' + nivel(0, "decimal", "%1.") + "</w:abstractNum>"
        '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>'
        '<w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
        '<w:num w:numId="3"><w:abstractNumId w:val="2"/></w:num>'
        '<w:num w:numId="4"><w:abstractNumId w:val="3"/></w:num>'
        '<w:num w:numId="5"><w:abstractNumId w:val="3"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
    )

    def md(self, corpo):
        caminho = montar_docx(corpo, self.NUMERACAO)
        self.addCleanup(os.remove, caminho)
        return [l for l in docx_para_md(caminho).split("\n") if l.strip()]

    def test_romano_maiusculo_com_travessao(self):
        linhas = self.md(par(run("agir;"), num=(1, 0)) + par(run("informar;"), num=(1, 0)) + par(run("calar."), num=(1, 0)))
        self.assertEqual(linhas, ["I – agir;", "II – informar;", "III – calar."])

    def test_letra_minuscula_com_parentese(self):
        linhas = self.md(par(run("x;"), num=(2, 0)) + par(run("y."), num=(2, 0)))
        self.assertEqual(linhas, ["a) x;", "b) y."])

    def test_nivel_inferior_reinicia_quando_o_superior_avanca(self):
        corpo = (par(run("um"), num=(1, 0)) + par(run("sub1"), num=(1, 1)) + par(run("sub2"), num=(1, 1))
                 + par(run("dois"), num=(1, 0)) + par(run("sub1 de novo"), num=(1, 1)))
        self.assertEqual(self.md(corpo), ["I – um", "a) sub1", "b) sub2", "II – dois", "a) sub1 de novo"])

    def test_texto_do_meio_nao_zera_a_lista(self):
        corpo = par(run("a1"), num=(2, 0)) + par(run("Texto solto.")) + par(run("a2"), num=(2, 0))
        self.assertEqual(self.md(corpo), ["a) a1", "Texto solto.", "b) a2"])

    def test_marcador_sem_numero_nao_escreve_nada(self):
        self.assertEqual(self.md(par(run("Nota."), num=(3, 0))), ["Nota."])

    def test_paragrafo_todo_tachado_leva_o_numero_dentro_da_marca(self):
        # senão a normalização deixaria uma linha só com "I –"
        corpo = par(run("redação antiga", tachado=True), num=(1, 0)) + par(run("redação nova"), num=(1, 0))
        self.assertEqual(self.md(corpo), ["~~I – redação antiga~~", "II – redação nova"])

    def test_start_override_reinicia_a_contagem(self):
        corpo = par(run("p"), num=(4, 0)) + par(run("q"), num=(4, 0)) + par(run("r"), num=(5, 0))
        self.assertEqual(self.md(corpo), ["1. p", "2. q", "1. r"])

    def test_numeracao_em_tabela(self):
        tbl = "<w:tbl><w:tr><w:tc>" + par(run("campo"), num=(2, 0)) + "</w:tc></w:tr></w:tbl>"
        self.assertEqual(self.md(tbl), ["| a) campo |", "| --- |"])

    def test_tabela_aninhada_vira_tabela_propria_depois_da_externa(self):
        interna = "<w:tbl><w:tr><w:tc>" + par(run("fator")) + "</w:tc><w:tc>" + par(run("cenario")) + "</w:tc></w:tr></w:tbl>"
        externa = ("<w:tbl><w:tr><w:tc>" + par(run("antes")) + interna + par(run("depois")) + "</w:tc>"
                   "<w:tc>" + par(run("x")) + "</w:tc></w:tr></w:tbl>")
        self.assertEqual(self.md(externa), [
            "| antes depois | x |", "| --- | --- |", "| fator | cenario |", "| --- | --- |"])

    def test_docx_sem_numbering_xml_segue_funcionando(self):
        caminho = montar_docx(par(run("Art. 1º X."), num=(1, 0)))
        self.addCleanup(os.remove, caminho)
        self.assertEqual(docx_para_md(caminho).strip(), "Art. 1º X.")


class TestPlanaltoHtml(unittest.TestCase):
    def test_tachado_some_e_nota_de_redacao_fica(self):
        html = (
            "<html><body><p>Art. 2º <strike>O prazo é de 5 dias.</strike> O prazo é de 10 dias. "
            "<a href='x'>(Redação dada pela Lei nº 14.430, de 2022)</a></p>"
            "<p><s>Art. 3º Texto velho.</s></p><p>Art. 4º <del>velho</del>novo.</p></body></html>"
        )
        md = planalto_html_para_md(html)
        self.assertEqual(md.strip().split("\n\n"), [
            "Art. 2º O prazo é de 10 dias. (Redação dada pela Lei nº 14.430, de 2022)",
            "Art. 4º novo.",
        ])

    def test_decodifica_windows_1252_quando_o_meta_pede(self):
        html = ('<html><head><meta http-equiv="Content-Type" content="text/html; charset=windows-1252"></head>'
                "<body><p>Art. 1º Fica instituída a obrigação.</p></body></html>").encode("cp1252")
        self.assertIn("Art. 1º Fica instituída a obrigação.", planalto_html_para_md(html))

    def test_bytes_sem_meta_sao_utf8(self):
        self.assertIn("Fica instituída", planalto_html_para_md("<p>Fica instituída.</p>".encode("utf-8")))

    def test_ordinal_em_sup_vira_simbolo(self):
        md = planalto_html_para_md("<p>Art. 1<sup><u>o</u></sup> Texto.</p><p>§ 2<sup>o</sup> Outro.</p>")
        self.assertEqual(md.strip().split("\n\n"), ["Art. 1º Texto.", "§ 2º Outro."])

    def test_script_style_e_cabecalho_ficam_de_fora(self):
        md = planalto_html_para_md("<html><head><title>Lei</title><style>p{}</style></head>"
                                   "<body><script>var x=1;</script><p>Texto.</p></body></html>")
        self.assertEqual(md.strip(), "Texto.")

    def test_artigo_com_sufixo_e_milhar_vira_heading(self):
        md = normalizar_artigos(planalto_html_para_md(
            "<p>Art. 1.368-C. A empresa individual de responsabilidade limitada.</p><p>Art. 1.368-D. Outro.</p>"))
        self.assertEqual(re.findall(r"^## Art\. .+$", md, flags=re.M), ["## Art. 1.368-C", "## Art. 1.368-D"])

    def test_tabela_vira_tabela_markdown(self):
        md = planalto_html_para_md("<table><tr><td>Faixa</td><td>Taxa</td></tr><tr><td>A</td><td>1</td></tr></table>")
        self.assertIn("| Faixa | Taxa |", md)
        self.assertIn("| A | 1 |", md)

    def test_br_vira_espaco_e_paragrafo_sem_fechar_separa(self):
        md = planalto_html_para_md("<p>Linha um<br>linha dois<p>Outro parágrafo")
        self.assertEqual(md.strip().split("\n\n"), ["Linha um linha dois", "Outro parágrafo"])


if __name__ == "__main__":
    unittest.main()


class TestRotulosDeVigencia(unittest.TestCase):
    """Rótulos de margem do Planalto ("(Vigência)", "Produção de efeito") são links, não texto."""

    HTML = ('<p>Art. 3º Ficam isentos do imposto de renda: '
            '<a href="../mpv1303.htm#art75">Produção de efeitos</a> '
            '<a href="../adc-67.htm"> Vigência encerrada</a></p>'
            '<p>I - os ganhos <a href="../L14112.htm#art7">(Vigência)</a></p>'
            '<p>II - ver <a href="../L13043.htm#art113"> Vigência </a> e '
            '<a href="../L12844.htm#art49"> (Produção de efeito) </a></p>'
            '<p>III - <a href="../L9.htm">Vigência da Lei</a> continua</p>')

    def test_planalto_sem_rotulos(self):
        md = planalto_html_para_md(self.HTML)
        self.assertIn("Art. 3º Ficam isentos do imposto de renda:", md)
        self.assertNotRegex(md, r"Vigência encerrada|Produção de efeito|\(Vigência\)|ver Vigência")
        self.assertIn("Vigência da Lei", md)  # link com outro texto fica

    def test_gabarito_do_teste_lei_sem_rotulos(self):
        from teste_lei import _texto_do_html
        txt = _texto_do_html(self.HTML)
        self.assertNotIn("Produção de efeito", txt)
        self.assertNotIn("(Vigência)", txt)
        self.assertIn("Vigência da Lei", txt)


class TestRotuloDeVigenciaComFonteDentroDoLink(unittest.TestCase):
    """Lei 6.404, art. 136-A: o Planalto põe `<font>` dentro do link "(Vigência)"."""

    HTML = ('<p>§ 1º A convenção somente terá eficácia após 30 dias. '
            '<font size="2"><a href="../L13129.htm#art3">\r\n\t\t(Incluído pela Lei nº 13.129, de 2015)</a>'
            '&nbsp;&nbsp;\r\n\t\t</font><a href="../L13129.htm#art5">\r\n\t\t<font size="2">(Vigência)</font></a></p>'
            '<p>§ 2º Outro. <a href="../L13129.htm#art4"><font size="2">(Incluído pela Lei nº 13.129, de 2015)'
            '</font></a> <a href="x.htm"><span><b> Vigência </b></span></a></p>')

    def test_planalto_sem_rotulo(self):
        md = planalto_html_para_md(self.HTML)
        self.assertNotIn("Vigência", md)
        self.assertIn("(Incluído pela Lei nº 13.129, de 2015)", md)

    def test_gabarito_do_teste_lei_sem_rotulo(self):
        from teste_lei import _texto_do_html
        txt = _texto_do_html(self.HTML)
        self.assertNotIn("Vigência", txt)
        self.assertIn("(Incluído pela Lei nº 13.129, de 2015)", txt)


NS_CAIXA = (NS + ' xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"'
            ' xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"'
            ' xmlns:v="urn:schemas-microsoft-com:vml"')


def caixa_vml(*paragrafos):
    return ("<w:r><w:pict><v:shape><v:textbox><w:txbxContent>%s</w:txbxContent></v:textbox>"
            "</v:shape></w:pict></w:r>" % "".join(par(run(t)) for t in paragrafos))


def caixa_alternativa(*paragrafos):
    """Caixa como o Word grava: DrawingML em mc:Choice e cópia VML em mc:Fallback."""
    conteudo = "<w:txbxContent>%s</w:txbxContent>" % "".join(par(run(t)) for t in paragrafos)
    return ('<w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:wsp><wps:txbx>%s'
            '</wps:txbx></wps:wsp></w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape><v:textbox>%s'
            '</v:textbox></v:shape></w:pict></mc:Fallback></mc:AlternateContent></w:r>' % (conteudo, conteudo))


def docx_extras(corpo, notas=None):
    xml = '<?xml version="1.0" encoding="UTF-8"?><w:document %s><w:body>%s</w:body></w:document>' % (NS_CAIXA, corpo)
    fd, caminho = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    with zipfile.ZipFile(caminho, "w") as z:
        z.writestr("word/document.xml", xml)
        if notas:
            z.writestr("word/footnotes.xml", '<w:footnotes %s>%s</w:footnotes>' % (NS, "".join(
                '<w:footnote w:id="%s">%s</w:footnote>' % (k, par(run(t))) for k, t in notas)))
    return caminho


def ref_nota(k):
    return '<w:r><w:rPr><w:rStyle w:val="Refdenotaderodap"/></w:rPr><w:footnoteReference w:id="%s"/></w:r>' % k


class TestDocxCaixasDeTexto(unittest.TestCase):
    def md(self, corpo, **kw):
        caminho = docx_extras(corpo)
        self.addCleanup(os.remove, caminho)
        return docx_para_md(caminho, **kw)

    def test_caixa_simples_vira_citacao_no_lugar(self):
        corpo = (par(run("Antes.")) + par(run("Figura 1"), caixa_vml("Cedente", "Fundo"))
                 + par(run("Depois.")))
        self.assertEqual(self.md(corpo, caixas=True).split("\n\n"), [
            "Antes.", "Figura 1", "> [Diagrama] Cedente\n> [Diagrama] Fundo", "Depois.\n"])

    def test_caixa_em_alternate_content_sai_uma_vez(self):
        md = self.md(par(caixa_alternativa("Cotista", "Gestor")), caixas=True)
        self.assertEqual(md, "> [Diagrama] Cotista\n> [Diagrama] Gestor\n")

    def test_varias_caixas_viram_blocos_separados(self):
        md = self.md(par(caixa_alternativa("A"), caixa_vml("B")), caixas=True)
        self.assertEqual(md, "> [Diagrama] A\n\n> [Diagrama] B\n")

    def test_caixa_em_celula_vai_depois_da_tabela(self):
        tbl = "<w:tbl><w:tr><w:tc>" + par(run("x"), caixa_vml("C")) + "</w:tc></w:tr></w:tbl>"
        self.assertEqual(self.md(tbl, caixas=True), "| x |\n| --- |\n\n> [Diagrama] C\n")

    def test_padrao_ignora_caixas(self):
        corpo = par(run("Antes.")) + par(caixa_alternativa("Cotista")) + par(run("Figura"), caixa_vml("X"))
        self.assertEqual(self.md(corpo), "Antes.\n\nFigura\n")
        self.assertEqual(self.md(corpo, caixas=False), "Antes.\n\nFigura\n")


class TestDocxAncorasDeNotas(unittest.TestCase):
    def md(self, corpo, rodape, **kw):
        caminho = docx_extras(corpo, rodape)
        self.addCleanup(os.remove, caminho)
        return docx_para_md(caminho, **kw)

    NOTAS = [("-1", "sep"), ("0", "cont"), ("2", "Nota dois."), ("5", "Nota cinco.")]

    def test_ancoras_na_ordem_de_exibicao(self):
        # o id 5 aparece primeiro: é a nota [1]
        corpo = par(run("Art. 1º Texto"), ref_nota(5), run(" meio"), ref_nota(2), run("."))
        self.assertEqual(self.md(corpo, self.NOTAS, notas=True), "Art. 1º Texto [1] meio [2].\n")

    def test_padrao_sem_ancora(self):
        corpo = par(run("Art. 1º Texto"), ref_nota(5), run("."))
        self.assertEqual(self.md(corpo, self.NOTAS), "Art. 1º Texto.\n")

    def test_ordem_das_notas_casa_com_a_ancora(self):
        from converter import ordem_das_notas
        corpo = par(run("a"), ref_nota(5)) + par(run("b"), ref_nota(2), ref_nota(5))
        caminho = docx_extras(corpo, self.NOTAS)
        self.addCleanup(os.remove, caminho)
        with zipfile.ZipFile(caminho) as z:
            self.assertEqual(ordem_das_notas(z.read("word/document.xml")), ["5", "2"])
        self.assertEqual(docx_para_md(caminho, notas=True), "a [1]\n\nb [2] [1]\n")
