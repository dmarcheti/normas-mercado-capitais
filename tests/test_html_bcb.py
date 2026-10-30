"""Testes de scripts/html_bcb.py. Os trechos de HTML são recortes reais do campo Texto da API do
BCB (dados/fase-2c/bcb/Resolução_BCB-00277.json e Resolução_CMN-04966.json), sem rede."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import html_bcb  # noqa: E402

# Res. BCB 277: tabela de layout (uma célula) com o título do Anexo III tachado (redação revogada)
LAYOUT_277 = (
    '<table class="MsoTableGrid" border="0" cellspacing="0" cellpadding="0" width="652" '
    'style="border-collapse&#58;collapse;border-width&#58;medium;border-style&#58;none;">\n'
    ' <tbody><tr>\n  <td width="652" valign="top" style="width&#58;489.05pt;padding&#58;0cm 5.4pt;">\n'
    '  <p class="MsoNormal" align="center" style="margin&#58;0cm 0cm 18pt;text-align&#58;center;">'
    '<a name="_Hlk115783484"></a><a name="_Hlk113630273"><s style="font-family&#58;Calibri;'
    'font-size&#58;17.3333px;"><span style="color&#58;red;">ANEXO I</span></s></a><s style="font-'
    'family&#58;Calibri;"><span style="color&#58;red;">II</span></s><s style="font-family&#58;'
    'Calibri;"><span style="color&#58;red;"> À\n  RESOLUÇÃO BCB Nº 277, DE 31 DE DEZEMBRO DE 2022'
    '</span></s></p>\n  <p class="MsoNormal" align="center" style="margin&#58;0cm;"><span style="'
    'font-family&#58;Calibri;"><b style=""><s style=""><span style="line-height&#58;103%;color&#58;'
    'red;">Códigos de classificação da finalidade (natureza) da operação de\n  câmbio de até '
    'US$50.000,00</span></s></b></span></p>\n'
    '  <p class="MsoNormal" style="margin&#58;0cm;text-indent&#58;0cm;"><s style="font-family&#58;'
    'Calibri;"><span style="line-height&#58;103%;color&#58;red;"><span style="text-decoration&#58;'
    'none;">&#160;</span></span></s></p>\n  </td>\n </tr>\n</tbody></table>')

# Res. BCB 277: tabela de dados (Finalidade x Código)
DADOS_277 = (
    '<table class="MsoNormalTable" border="0" cellspacing="0" cellpadding="0" width="614" '
    'style="margin-left&#58;5.8pt;border-collapse&#58;collapse;">\n   <tbody><tr style="height&#58;'
    '20.7pt;">\n    <td width="529" valign="top" style="width&#58;396.85pt;padding&#58;0cm 5.4pt;">\n'
    '    <p class="MsoNormal" style="margin-left&#58;0cm;"><span style="font-family&#58;Calibri;'
    'font-size&#58;17.3333px;">Finalidade</span></p>\n    </td>\n    <td width="85" style="width&#58;'
    '63.8pt;">\n    <p class="MsoNormal" align="center" style="text-align&#58;center;"><span style="'
    'font-family&#58;Calibri;">Código</span></p>\n    </td>\n   </tr>\n   <tr style="height&#58;20.7pt;'
    '">\n    <td width="529" valign="top">\n    <p class="MsoNormal" style="margin-left&#58;8.55pt;">'
    '<span style="font-family&#58;Calibri;">Viagem internacional</span></p>\n    </td>\n    <td '
    'width="85" valign="top">\n    <p class="MsoNormal" align="center"><span style="font-family&#58;'
    'Calibri;">32999</span></p>\n    </td>\n   </tr>\n  </tbody></table>')

# Res. CMN 4.966: art. 76 com a redação antiga em <s> e a nova com o link "Redação dada"
ART76_4966 = (
    '<p class="MsoNormal" style="margin-bottom&#58;6pt;text-indent&#58;70.9pt;text-align&#58;justify;">'
    '<s style="font-family&#58;Calibri;font-size&#58;17.3333px;"><span style="color&#58;red;">Art. 76.'
    '&#160; As instituições mencionadas no art. 1º devem elaborar e remeter ao Banco Central do Brasil, '
    'até 30 de junho de 2022, plano para a implementação da regulamentação contábil estabelecida nesta '
    'Resolução.</span></s></p><div style="text-align&#58;justify;"></div><p class="MsoNormal" style="'
    'margin-bottom&#58;6pt;text-indent&#58;70.9pt;text-align&#58;justify;"><span style="font-family&#58;'
    'Calibri;font-size&#58;17.3333px;">Art. 76.&#160; As instituições mencionadas no art. 1º devem, até '
    '31 de dezembro de 2022, elaborar e manter à disposição do Banco Central do Brasil plano para a '
    'implementação da regulamentação contábil estabelecida nesta Resolução.&#160;</span><a href="https'
    '&#58;//www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&amp;'
    'numero=5019" target="_blank"><span style="font-family&#58;Calibri;font-size&#58;17.3333px;">'
    '(Redação dada pela Resolução CMN nº 5.019, de 23/6/2022.)</span></a></p>')


class TestTabelas(unittest.TestCase):
    def test_tabela_de_layout_vira_paragrafos_com_anexo_tachado(self):
        md = html_bcb.html_para_md(LAYOUT_277)
        self.assertNotIn("|", md)
        self.assertIn("~~ANEXO III À RESOLUÇÃO BCB Nº 277, DE 31 DE DEZEMBRO DE 2022~~", md)
        # dentro do tachado não entra negrito; o parágrafo fica separado por linha em branco
        self.assertIn("\n\n~~Códigos de classificação da finalidade (natureza) da operação de câmbio "
                      "de até US$50.000,00~~", md)
        self.assertNotIn("**", md)
        self.assertNotIn("~~ ~~", md)

    def test_tabela_de_dados_vira_tabela_em_pipes(self):
        self.assertEqual(html_bcb.html_para_md(DADOS_277),
                         "| Finalidade | Código |\n| --- | --- |\n| Viagem internacional | 32999 |\n")

    def test_barra_vertical_escapada_na_celula(self):
        md = html_bcb.html_para_md("<table><tr><td>a</td><td>b</td></tr><tr><td>x | y</td><td>z</td></tr></table>")
        self.assertIn("| x \\| y | z |", md)

    def test_todas_as_linhas_com_uma_celula_e_layout(self):
        md = html_bcb.html_para_md("<table><tr><td><p>Um</p></td></tr><tr><td><p>Dois</p></td></tr></table>")
        self.assertEqual(md, "Um\n\nDois\n")

    def test_tabela_aninhada_achatada_na_celula(self):
        md = html_bcb.html_para_md(
            "<table><tr><td>Item</td><td>Valor</td></tr><tr><td>A</td><td>"
            "<table><tr><td>1</td><td>2</td></tr></table></td></tr></table>")
        linhas = md.strip().split("\n")
        self.assertEqual(linhas[0], "| Item | Valor |")
        self.assertEqual(len(linhas), 3)
        self.assertTrue(linhas[2].startswith("| A | 1") and "2" in linhas[2])


class TestTachadoERedacao(unittest.TestCase):
    def test_art76_redacao_antiga_tachada_e_nova_com_nota(self):
        md = html_bcb.html_para_md(ART76_4966)
        paras = md.strip().split("\n\n")
        self.assertEqual(len(paras), 2)
        self.assertTrue(paras[0].startswith("~~Art. 76. As instituições") and paras[0].endswith("Resolução.~~"))
        self.assertTrue(paras[1].startswith("Art. 76. As instituições mencionadas no art. 1º devem, até 31"))
        # link: só o texto
        self.assertTrue(paras[1].endswith("(Redação dada pela Resolução CMN nº 5.019, de 23/6/2022.)"))
        self.assertNotIn("http", md)

    def test_line_through_no_estilo(self):
        md = html_bcb.html_para_md('<p><span style="text-decoration:line-through">velho</span> novo</p>')
        self.assertEqual(md, "~~velho~~ novo\n")

    def test_strike_e_del(self):
        # trechos tachados vizinhos se juntam num só (o espaço entre eles vai junto)
        self.assertEqual(html_bcb.html_para_md("<p><strike>a</strike> <del>b</del></p>"), "~~a b~~\n")
        self.assertEqual(html_bcb.html_para_md("<p><strike>a</strike> c <del>b</del></p>"), "~~a~~ c ~~b~~\n")

    def test_tachado_multilinha_fecha_por_linha(self):
        md = html_bcb.html_para_md("<p><s>linha um<br>linha dois</s></p>")
        self.assertEqual(md, "~~linha um~~\n~~linha dois~~\n")


class TestInline(unittest.TestCase):
    def test_negrito_e_italico(self):
        self.assertEqual(html_bcb.html_para_md("<p><strong>caput</strong> e <em>hedge</em> <b>x</b> <i>y</i></p>"),
                         "**caput** e *hedge* **x** *y*\n")

    def test_negrito_desligado_por_font_weight_normal(self):
        md = html_bcb.html_para_md('<p><strong>Art. 1º <span style="font-weight:normal">texto</span></strong></p>')
        self.assertEqual(md, "**Art. 1º** texto\n")

    def test_br_listas_nbsp_e_espaco_invisivel(self):
        md = html_bcb.html_para_md("<p>a&nbsp;&nbsp;b​ c<br>d</p><ul><li>um</li><li>dois</li></ul>")
        self.assertEqual(md, "a b c\nd\n\n- um\n\n- dois\n")  # um bloco por item

    def test_paragrafos_separados_por_linha_em_branco(self):
        self.assertEqual(html_bcb.html_para_md("<p>um</p><div>dois</div>"), "um\n\ndois\n")

    def test_style_e_title_fora_do_texto(self):
        md = html_bcb.html_para_md("<title>Resolução</title><style>p{color:red}</style><p>texto</p>")
        self.assertEqual(md, "texto\n")


class TestPre(unittest.TestCase):
    def test_tabela_ascii_vira_bloco_de_codigo(self):
        md = html_bcb.html_para_md("<pre>Titulo\n----------------------\nA    1\nB    2\n</pre>")
        self.assertTrue(md.startswith("```\n") and md.rstrip().endswith("```"))
        self.assertIn("A    1", md)

    def test_titulo_sublinhado_curto_perde_a_regua(self):
        md = html_bcb.html_para_md("<pre>CIRCULAR 1.452\n--------------\n\nArt. 1o Texto do artigo\ncontinua.</pre>")
        self.assertNotIn("```", md)
        self.assertNotIn("-----", md)
        self.assertIn("Art. 1o Texto do artigo continua.", md)


if __name__ == "__main__":
    unittest.main()
