"""Testes das leis: validador, conversão do HTML do Planalto e teste 2 de conversão (sem rede)."""
import os
import re
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

from converter import normalizar_artigos, planalto_html_para_md  # noqa: E402
import teste_lei  # noqa: E402
from teste_lei import diferencas_lei, nome_do_arquivo  # noqa: E402
from test_validar import CORPO, VALORES, montar  # noqa: E402
from validar import CAMPOS, validar_norma  # noqa: E402

LEI = {
    "id": "lei-6385", "orgao": "federal", "tipo": "lei", "numero": "6385",
    "data": "1976-12-07", "publicacao_dou": "1976-12-09",
    "ementa": "Dispõe sobre o mercado de valores mobiliários e cria a Comissão de Valores Mobiliários.",
    "situacao": "vigente", "versao_texto": "consolidado", "vigente_ate_ato": "",
    "aguarda_consolidado_oficial": "false", "historico_parcial": "true",
    "fonte_original": "https://www.planalto.gov.br/ccivil_03/leis/l6385.htm",
    "fonte_consolidada": "https://www.planalto.gov.br/ccivil_03/leis/l6385compilada.htm",
    "baixado_em": "2026-10-28", "verificado_em": "2026-10-28",
}


def gravar(pasta, nome, texto):
    caminho = os.path.join(pasta, *nome.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)
    return caminho


class TestValidarLei(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def erros(self, valores=None, nome="lei-06385.md", corpo=CORPO):
        v = dict(VALORES)
        v.update(LEI)
        v.update(valores or {})
        caminho = gravar(self._tmp.name, nome, montar(v, corpo=corpo))
        return validar_norma(caminho)

    def test_frontmatter_de_lei_valido(self):
        self.assertEqual(self.erros(), [])

    def test_lei_em_partes_na_pasta_lei_nnnnn(self):
        corpo = "\n# Lei 6.404\n\n## Partes\n\n- cap-01.md\n"
        pasta = os.path.join(self._tmp.name, "lei-06404")
        gravar(pasta, "cap-01.md", "# Capítulo I\n\n## Art. 1º\n\nTexto.\n")
        v = dict(VALORES, **dict(LEI, id="lei-6404", numero="6404"))
        caminho = gravar(pasta, "index.md", montar(v, corpo=corpo))
        self.assertEqual(validar_norma(caminho), [])

    def test_vigente_ate_ato_em_lei_e_erro(self):
        erros = self.erros({"vigente_ate_ato": "5"})
        self.assertTrue(any("vigente_ate_ato" in e for e in erros), erros)

    def test_orgao_e_tipo_de_lei(self):
        self.assertTrue(any("orgao" in e for e in self.erros({"orgao": "cvm"})))
        self.assertTrue(any("tipo" in e for e in self.erros({"tipo": "resolucao"})))

    def test_id_de_lei_e_lei_numero(self):
        self.assertTrue(any("id" in e for e in self.erros({"id": "cvm-res-6385"})))
        self.assertTrue(any("id" in e for e in self.erros({"id": "lei-6386"})))

    def test_nome_do_arquivo_de_lei_tem_cinco_digitos(self):
        erros = self.erros(nome="lei-6385.md")
        self.assertTrue(any("lei-06385.md" in e for e in erros), erros)

    def test_resolucao_continua_sem_aceitar_orgao_federal(self):
        caminho = gravar(self._tmp.name, "0017.md", montar({"orgao": "federal"}))
        self.assertTrue(any("orgao" in e for e in validar_norma(caminho)))


class TestConversaoDeLei(unittest.TestCase):
    HTML = (
        "<html><body>"
        "<p>Art. 1.368-B. <strike>Texto velho do artigo.</strike> A empresa pode ser constituída. "
        "<a href='x'>(Redação dada pela Lei nº 14.430, de 2022)</a></p>"
        "<p>Art. 1.368-C. A empresa individual de responsabilidade limitada.</p></body></html>"
    )

    def test_strike_some_e_nota_de_redacao_fica(self):
        md = planalto_html_para_md(self.HTML)
        self.assertNotIn("Texto velho", md)
        self.assertIn("(Redação dada pela Lei nº 14.430, de 2022)", md)

    def test_artigo_1368_c_vira_heading(self):
        md = normalizar_artigos(planalto_html_para_md(self.HTML))
        self.assertEqual(re.findall(r"^## Art\. .+$", md, flags=re.M), ["## Art. 1.368-B", "## Art. 1.368-C"])


def lei_md(corpo):
    return "---\nid: lei-6385\n---\n\n# Lei nº 6.385\n\n" + corpo


def html(*paragrafos):
    return "<html><body>" + "".join("<p>%s</p>" % p for p in paragrafos) + "</body></html>"


class TestDiferencasLei(unittest.TestCase):
    HTML = html(
        "LEI Nº 6.385, DE 7 DE DEZEMBRO DE 1976", "O PRESIDENTE DA REPÚBLICA faço saber:",
        "Art. 1º Serão disciplinadas as seguintes atividades:",
        "I - a emissão <strike>antiga</strike> e distribuição de valores;",
        "Art. 2º São valores mobiliários as ações. (Redação dada pela Lei nº 10.303, de 2001)",
        "Art. 3º <strike>Texto velho.</strike> Compete ao Conselho.",
        "Brasília, 7 de dezembro de 1976.",
    )
    CORPO = (
        "## Art. 1º\n\nSerão disciplinadas as seguintes atividades:\n\nI - a emissão e distribuição de valores;\n\n"
        "## Art. 2º\n\nSão valores mobiliários as ações. (Redação dada pela Lei nº 10.303, de 2001)\n\n"
        "## Art. 3º\n\nCompete ao Conselho.\n\nBrasília, 7 de dezembro de 1976.\n"
    )

    def test_conversao_fiel_da_zero(self):
        self.assertEqual(diferencas_lei(lei_md(self.CORPO), self.HTML), [])

    def test_texto_tachado_na_norma_e_diferenca(self):
        norma = lei_md(self.CORPO.replace("Compete ao Conselho.", "Texto velho. Compete ao Conselho."))
        dif = diferencas_lei(norma, self.HTML)
        self.assertTrue(any("Texto velho" in d for d in dif), dif)

    def test_nota_de_redacao_perdida_e_diferenca(self):
        norma = lei_md(self.CORPO.replace(" (Redação dada pela Lei nº 10.303, de 2001)", ""))
        self.assertTrue(diferencas_lei(norma, self.HTML))

    def test_ordinal_em_sup_do_html_bate_com_o_simbolo_da_norma(self):
        h = html("Art. 1<sup><u>o</u></sup> Texto.")
        self.assertEqual(diferencas_lei(lei_md("## Art. 1º\n\nTexto.\n"), h), [])

    def test_artigo_fora_de_ordem(self):
        norma = lei_md("## Art. 1º\n\nA.\n\n## Art. 3º\n\nC.\n\n## Art. 2º\n\nB.\n")
        dif = diferencas_lei(norma, html("Art. 1º A.", "Art. 3º C.", "Art. 2º B."))
        self.assertTrue(any("ordem" in d for d in dif), dif)

    def test_lacuna_entre_artigos(self):
        norma = lei_md("## Art. 1º\n\nA.\n\n## Art. 2º\n\nB.\n\n## Art. 4º\n\nD.\n")
        dif = diferencas_lei(norma, html("Art. 1º A.", "Art. 2º B.", "Art. 4º D."))
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("lacuna", dif[0])
        self.assertIn("2", dif[0])
        self.assertIn("4", dif[0])

    def test_sufixos_de_letra_em_sequencia_nao_sao_lacuna(self):
        corpo = "## Art. 9º\n\nA.\n\n## Art. 9º-A\n\nB.\n\n## Art. 9º-B\n\nC.\n\n## Art. 10\n\nD.\n\n## Art. 11\n\nE.\n"
        h = html("Art. 9º A.", "Art. 9º-A B.", "Art. 9º-B C.", "Art. 10. D.", "Art. 11. E.")
        self.assertEqual(diferencas_lei(lei_md(corpo), h), [])

    def test_letra_pulada_e_lacuna(self):
        corpo = "## Art. 9º\n\nA.\n\n## Art. 9º-A\n\nB.\n\n## Art. 9º-C\n\nC.\n"
        h = html("Art. 9º A.", "Art. 9º-A B.", "Art. 9º-C C.")
        self.assertTrue(any("lacuna" in d for d in diferencas_lei(lei_md(corpo), h)))

    def test_milhar_e_letra(self):
        corpo = "## Art. 1.368-C\n\nC.\n\n## Art. 1.368-D\n\nD.\n"
        self.assertEqual(diferencas_lei(lei_md(corpo), html("Art. 1.368-C. C.", "Art. 1.368-D. D.")), [])

    def test_recorte_compara_so_o_trecho_da_norma(self):
        # Código Civil: a norma só tem 1.368-C a 1.368-F; o HTML tem o resto do Código
        h = html("Art. 1.368-B. Antes.", "Art. 1.368-C. C.", "§ 1º Parágrafo de C.", "Art. 1.368-D. D.",
                 "Art. 1.368-E. E.", "Art. 1.368-F. F.", "Parágrafo único. Fim de F.", "Art. 1.369. Depois.")
        corpo = ("## Art. 1.368-C\n\nC.\n\n§ 1º Parágrafo de C.\n\n## Art. 1.368-D\n\nD.\n\n"
                 "## Art. 1.368-E\n\nE.\n\n## Art. 1.368-F\n\nF.\n\nParágrafo único. Fim de F.\n")
        self.assertEqual(diferencas_lei(lei_md(corpo), h), [])

    def test_recorte_com_texto_a_menos_e_diferenca(self):
        h = html("Art. 1.368-C. C.", "Art. 1.368-D. D.", "Art. 1.369. Depois.")
        dif = diferencas_lei(lei_md("## Art. 1.368-C\n\nC.\n"), h)
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("1.368-D", dif[0])

    def test_norma_sem_artigo(self):
        self.assertEqual(diferencas_lei(lei_md("Sem artigo.\n"), self.HTML), ["norma sem nenhum artigo (## Art.)"])

    def test_html_sem_o_primeiro_artigo(self):
        dif = diferencas_lei(lei_md("## Art. 7º\n\nX.\n"), html("Art. 1º A."))
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("7º", dif[0])


class TestIdsDeLeiDecretoELeiComplementar(unittest.TestCase):
    def test_nome_do_arquivo_por_tipo(self):
        self.assertEqual(nome_do_arquivo("lei-6385"), "lei-06385")
        self.assertEqual(nome_do_arquivo("decreto-11964"), "decreto-11964")
        self.assertEqual(nome_do_arquivo("lcp-105"), "lcp-105")
        self.assertEqual(nome_do_arquivo("lcp-7"), "lcp-007")
        self.assertIsNone(nome_do_arquivo("cvm-res-17"))
        self.assertIsNone(nome_do_arquivo("decreto-x"))

    def test_main_aceita_decreto(self):
        with tempfile.TemporaryDirectory() as tmp:
            norma = gravar(tmp, "decreto-11964.md", "---\nid: decreto-11964\n---\n\n## Art. 1º\n\nA.\n")
            h = gravar(tmp, "decreto-11964.html", html("DECRETO Nº 11.964", "Art. 1º A."))
            self.assertEqual(teste_lei.main(["teste_lei.py", "decreto-11964", "--norma", norma, "--html", h]), 0)

    def test_main_recusa_id_de_resolucao(self):
        self.assertEqual(teste_lei.main(["teste_lei.py", "cvm-res-17"]), 2)


if __name__ == "__main__":
    unittest.main()
