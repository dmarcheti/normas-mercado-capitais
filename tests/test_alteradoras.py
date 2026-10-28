"""Testes da conversão e da escrita dos atos alteradores (sem rede).

A fixture `ctresb-ato.md` é um ato fictício no formato do ctresb/leis: frontmatter,
título repetido, `**Art. N**` em negrito, redações novas entre aspas (uma delas com
artigos citados sem aspas de abertura) e notas de rodapé.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))
sys.path.insert(0, AQUI)

from alteradoras import (  # noqa: E402
    artigos_do_ato, ementa_do_ato, escrever_alteradora, md_do_ctresb, md_do_docx,
    restaurar_tabelas, tabelas_do_md,
)
from validar import CAMPOS, ler_frontmatter  # noqa: E402
from test_converter import montar_docx, par, run  # noqa: E402


def ler(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as f:
        return f.read()


def headings(md):
    return [l for l in md.split("\n") if l.startswith("## ")]


ITEM = {
    "numero": 999, "data": "2022-07-13", "dou": "2022-07-14",
    "url_ato": {"docx": "https://conteudo.cvm.gov.br/legislacao/resolucoes/anexos/900/resol999.docx"},
}


class TestMdDoCtresb(unittest.TestCase):
    def setUp(self):
        self.md = md_do_ctresb(ler("ctresb-ato.md"), ato=True)

    def test_tira_frontmatter_titulo_duplicado_negrito_e_cerquilha(self):
        linhas = self.md.split("\n")
        self.assertEqual(linhas[0], "RESOLUÇÃO CVM Nº 999, DE 13 DE JULHO DE 2022")
        self.assertEqual(self.md.count("RESOLUÇÃO CVM Nº 999"), 1)
        self.assertNotIn("**", self.md)
        self.assertNotIn("---", self.md)
        self.assertNotIn("titulo:", self.md)
        self.assertIn("\nCAPÍTULO ÚNICO\n", self.md)
        self.assertIn("\nANEXO\n", self.md)
        self.assertFalse([l for l in linhas if l.startswith("#") and not l.startswith("## Art.")])

    def test_so_artigos_do_proprio_ato_viram_heading(self):
        self.assertEqual(headings(self.md), ["## Art. 1º", "## Art. 2º", "## Art. 3º"])

    def test_artigo_citado_sem_aspa_de_abertura_fica_como_texto(self):
        self.assertIn("\nArt. 7º-B. Caso seja requerida", self.md)
        self.assertIn("\nArt. 8º O prazo é de 10 (dez) dias.", self.md)

    def test_artigo_dentro_do_anexo_do_ato_fica_como_texto(self):
        self.assertIn("\nArt. 4º Artigo do anexo", self.md)
        self.assertEqual(headings(self.md)[-1], "## Art. 3º")

    def test_artigo_citado_com_o_numero_do_proximo_artigo_do_ato_fica_como_texto(self):
        self.assertIn("\nArt. 2º. Texto citado", self.md)

    def test_corpo_do_artigo_vai_na_linha_seguinte(self):
        self.assertIn("## Art. 1º\n\nA Resolução CVM nº 80, de 29 de março de 2022, passa a vigorar", self.md)
        self.assertIn("## Art. 3º\n\nEsta Resolução entra em vigor em 2 de janeiro de 2023.", self.md)

    def test_citacao_entre_aspas_e_notas_ficam_no_texto(self):
        self.assertIn('"Art. 3º................................................................', self.md)
        self.assertIn("(1) Dispositivo modificado apenas para fins de ajuste de pontuação.", self.md)
        self.assertIn("Parágrafo único. Sem prejuízo do disposto no caput.", self.md)

    def test_ementa(self):
        self.assertEqual(ementa_do_ato(self.md), "Altera a Resolução CVM nº 80, de 29 de março de 2022.")

    def test_original_de_resolucao_normaliza_todo_artigo(self):
        md = md_do_ctresb(ler("ctresb-ato.md"))
        self.assertIn("## Art. 7º-B", headings(md))
        self.assertEqual(len(headings(md)), 7)

    def test_tira_a_assinatura_e_mantem_anexo_e_notas(self):
        self.assertNotIn("JOÃO PEDRO", self.md)
        self.assertIn("\nANEXO\n", self.md)
        md = md_do_ctresb("# RESOLUÇÃO CVM Nº 1\n\nRESOLUÇÃO CVM Nº 1\n\nEmenta.\n\n**Art. 1º** Entra em vigor.\n\nMARCELO BARBOSA\n")
        self.assertNotIn("MARCELO", md)

    def test_nome_em_maiusculas_no_meio_do_texto_fica(self):
        md = md_do_ctresb("RESOLUÇÃO CVM Nº 1\n\nEmenta.\n\n**Art. 1º** A.\n\nDISPOSIÇÕES FINAIS\n\n**Art. 2º** B.\n")
        self.assertIn("\nDISPOSIÇÕES FINAIS\n", md)

    def test_escapes_do_markdown_do_ctresb_saem(self):
        self.assertIn("\n1. tenha realizado ofertas; ou\n", self.md)
        self.assertIn("\n2. tenha realizado ____\n", self.md)
        self.assertNotIn("\\", self.md)

    def test_citacao_sem_fecho_nao_engole_o_artigo_seguinte_do_ato(self):
        md = artigos_do_ato(
            'Art. 1º A Resolução X passa a vigorar com a seguinte redação:\n\n"Art. 11. Texto sem fecho.\n\n'
            "IX - fundos.\n\nArt. 2º A Resolução Y passa a vigorar com a seguinte redação:\n")
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])

    def test_idempotente_no_corpo(self):
        self.assertEqual(artigos_do_ato(self.md), self.md)


class TestEmentaComErroDeDigitacao(unittest.TestCase):
    def test_titulo_com_acento_errado_na_fonte(self):
        md = "RESOLUÇÂO CVM nº 245, DE 1º DE JULHO DE 2026\n\nAltera a Resolução CVM nº 50.\n"
        self.assertEqual(ementa_do_ato(md), "Altera a Resolução CVM nº 50.")


class TestEmentaComLinhaDePublicacao(unittest.TestCase):
    def test_pula_a_linha_publicada_no_dou(self):
        md = ("RESOLUÇÃO CVM Nº 59, DE 22 DE DEZEMBRO DE 2021(*)\n\n"
              "(Publicada no DOU de 23-12-2021, Seção 1, páginas 246 a 255)\n\n"
              "Altera as Resoluções CVM nº 80 e nº 81.\n")
        self.assertEqual(ementa_do_ato(md), "Altera as Resoluções CVM nº 80 e nº 81.")


class TestArtigosDoAto(unittest.TestCase):
    def test_sem_artigo_1_levanta_erro(self):
        with self.assertRaises(ValueError):
            artigos_do_ato("RESOLUÇÃO CVM Nº 1\n\nTexto sem artigo.\n")

    def test_numero_fora_de_sequencia_nao_vira_heading(self):
        md = artigos_do_ato("Art. 1º A\n\nArt. 3º B\n\nArt. 2º C\n")
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])

    def test_nota_que_comeca_com_artigo_nao_conta(self):
        md = artigos_do_ato("Art. 1º A\n\nArt. 2º incluído pela Resolução CVM nº 1\n\nArt. 2º C\n")
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])

    def test_citacao_aberta_ate_o_nr(self):
        md = artigos_do_ato('Art. 1º A\n\n"Art. 5º X\n\nArt. 2º citado\n\nY" (NR)\n\nArt. 2º D\n')
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])
        self.assertIn("\nArt. 2º citado\n", md)


def tabela_docx(*linhas):
    def tc(t):
        return "<w:tc>%s</w:tc>" % par(run(t)) if t else "<w:tc><w:p/></w:tc>"
    return "<w:tbl>%s</w:tbl>" % "".join("<w:tr>%s</w:tr>" % "".join(tc(c) for c in l) for l in linhas)


class TestTabelas(unittest.TestCase):
    CORPO = (
        par(run("Art. 1º Antes."))
        + tabela_docx(["Item", "Resposta", "Seção"], ["a) Pergunta?", "Sim/Não", ""])
        + par(run("Depois."))
    )

    def docx(self, corpo):
        caminho = montar_docx(corpo)
        self.addCleanup(os.remove, caminho)
        return caminho

    def test_tabelas_do_md(self):
        from converter import docx_para_md
        t = tabelas_do_md(docx_para_md(self.docx(self.CORPO)))
        self.assertEqual(t, [[["Item", "Resposta", "Seção"], ["a) Pergunta?", "Sim/Não", ""]]])

    def test_restaura_a_tabela_achatada_com_o_texto_do_ctresb(self):
        achatado = "Art. 1º Antes.\n\nItem\n\nResposta\n\nSeção\n\na)  Pergunta?\n\nSim/Não\n\nDepois.\n"
        tabelas = [[["Item", "Resposta", "Seção"], ["a) Pergunta?", "Sim/Não", ""]]]
        md, achadas, total = restaurar_tabelas(achatado, tabelas)
        self.assertEqual((achadas, total), (1, 1))
        self.assertEqual(md, "Art. 1º Antes.\n\n| Item | Resposta | Seção |\n| --- | --- | --- |\n"
                             "| a)  Pergunta? | Sim/Não |  |\n\nDepois.\n")

    def test_tabela_que_nao_casa_fica_achatada_e_e_contada(self):
        achatado = "Antes.\n\nItem\n\nOutra coisa\n\nDepois.\n"
        md, achadas, total = restaurar_tabelas(achatado, [[["Item", "Resposta"]]])
        self.assertEqual((md, achadas, total), (achatado, 0, 1))

    def test_table_html_do_ctresb_vira_tabela_markdown(self):
        html = ('Art. 1º Antes:\n\n"Quadro\n\n<table>    <tbody>     <tr></tr>     <tr>      <td rowspan="1" colspan="1">'
                '<p>Item</p></td>      <td><p>a | b</p></td>     </tr>     <tr><td><p>...&nbsp;" (NR)</p></td><td></td></tr>'
                '    </tbody>   </table>\n\nArt. 2º Entra em vigor.\n')
        md = md_do_ctresb("RESOLUÇÃO CVM Nº 9\n\nEmenta.\n\n" + html, ato=True)
        self.assertIn("\n\n| Item | a \\| b |\n| --- | --- |\n| ... \" (NR) |  |\n\n", md)
        self.assertNotIn("<", md)
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])

    def test_md_do_ctresb_com_docx(self):
        achatado = "RESOLUÇÃO CVM Nº 9\n\nEmenta.\n\nArt. 1º Antes.\n\nItem\n\nResposta\n\nSeção\n\na) Pergunta?\n\nSim/Não\n\nDepois.\n"
        md = md_do_ctresb(achatado, ato=True, docx=self.docx(self.CORPO))
        self.assertIn("| a) Pergunta? | Sim/Não |  |", md)
        self.assertEqual(headings(md), ["## Art. 1º"])


class TestMdDoDocx(unittest.TestCase):
    def test_docx_do_ato(self):
        corpo = (
            par(run("RESOLUÇÃO CVM Nº 999, DE 13 DE JULHO DE 2022"))
            + par(run("Altera a Resolução CVM nº 80, de 29 de março de 2022."))
            + par(run("Art. 1º A Resolução CVM nº 80 passa a vigorar com a seguinte redação:"))
            + par(run('"Art. 3º ................" (NR)'))
            + par(run("Art. 2º Esta Resolução entra em vigor em 2 de janeiro de 2023."))
        )
        caminho = montar_docx(corpo)
        try:
            md = md_do_docx(caminho, ato=True)
        finally:
            os.remove(caminho)
        self.assertEqual(headings(md), ["## Art. 1º", "## Art. 2º"])
        self.assertEqual(ementa_do_ato(md), "Altera a Resolução CVM nº 80, de 29 de março de 2022.")
        self.assertIn("## Art. 2º\n\nEsta Resolução entra em vigor", md)


    def test_docx_sem_assinatura_eletronica(self):
        corpo = (
            par(run("RESOLUÇÃO CVM Nº 999, DE 13 DE JULHO DE 2022"))
            + par(run("Altera a Resolução CVM nº 80, de 29 de março de 2022."))
            + par(run("Art. 1º Esta Resolução entra em vigor em 2 de janeiro de 2023."))
            + par(run("Assinado eletronicamente por"))
            + par(run("FULANO DE TAL"))
            + par(run("Presidente"))
            + par(run("ANEXO A À RESOLUÇÃO CVM Nº 999"))
            + par(run("Texto do anexo."))
        )
        caminho = montar_docx(corpo)
        try:
            md = md_do_docx(caminho, ato=True)
        finally:
            os.remove(caminho)
        self.assertNotIn("Assinado eletronicamente", md)
        self.assertNotIn("FULANO", md)
        self.assertNotIn("Presidente", md)
        self.assertIn("ANEXO A À RESOLUÇÃO CVM Nº 999\n\nTexto do anexo.", md)


class TestEscreverRetificacao(unittest.TestCase):
    def test_id_e_ementa_dados_e_corpo_sem_titulo_de_resolucao(self):
        item = dict(ITEM, numero=175, data="2022-12-23", dou="2023-03-31")
        arq = escrever_alteradora(
            175, "RETIFICAÇÃO\n\nNo texto da Resolução CVM nº 175...\n", item, "https://exemplo/retificacao-1",
            "Retificação.", sha256_fonte="b" * 64, fonte_consolidada="https://exemplo/retificacao-1",
            ementa="Retificação da Resolução CVM nº 175, de 23 de dezembro de 2022.",
            id_ato="cvm-res-175-retificacao-2023-03-31")
        pares, corpo, erro = ler_frontmatter(arq)
        self.assertIsNone(erro)
        self.assertEqual([c for c, _ in pares], CAMPOS)
        d = dict(pares)
        self.assertEqual(d["id"], "cvm-res-175-retificacao-2023-03-31")
        self.assertEqual(d["numero"], "175")
        self.assertEqual((d["data"], d["publicacao_dou"]), ("2022-12-23", "2023-03-31"))
        self.assertEqual(d["ementa"], "Retificação da Resolução CVM nº 175, de 23 de dezembro de 2022.")
        self.assertTrue(corpo.lstrip().startswith("RETIFICAÇÃO"))


class TestEscreverAlteradora(unittest.TestCase):
    def setUp(self):
        self.md = md_do_ctresb(ler("ctresb-ato.md"), ato=True)
        self.url = "https://www.in.gov.br/web/dou/-/resolucao-cvm-n-999-de-13-de-julho-de-2022-111111111"
        self.arq = escrever_alteradora(999, self.md, ITEM, self.url, "Sem ressalva.", sha256_fonte="a" * 64)
        self.pares, self.corpo, self.erro = ler_frontmatter(self.arq)

    def test_frontmatter_no_formato_da_spec(self):
        self.assertIsNone(self.erro)
        self.assertEqual([c for c, _ in self.pares], CAMPOS)
        d = dict(self.pares)
        self.assertEqual(d["id"], "cvm-res-999")
        self.assertEqual((d["orgao"], d["tipo"], d["numero"]), ("cvm", "resolucao", "999"))
        self.assertEqual((d["data"], d["publicacao_dou"]), ("2022-07-13", "2022-07-14"))
        self.assertEqual(d["ementa"], "Altera a Resolução CVM nº 80, de 29 de março de 2022.")
        self.assertEqual((d["situacao"], d["versao_texto"], d["vigente_ate_ato"]), ("vigente", "original", ""))
        self.assertEqual((d["aguarda_consolidado_oficial"], d["historico_parcial"]), ("false", "false"))
        self.assertEqual(d["fonte_original"], self.url)
        self.assertEqual(d["fonte_consolidada"], ITEM["url_ato"]["docx"])
        self.assertEqual(d["sha256_fonte"], "a" * 64)
        self.assertEqual((d["baixado_em"], d["verificado_em"]), ("2026-10-28", "2026-10-28"))
        self.assertEqual(d["incerteza"], "Sem ressalva.")

    def test_corpo_e_o_texto_do_ato(self):
        self.assertEqual(self.corpo.strip("\n"), self.md.strip("\n"))
        self.assertTrue(self.arq.endswith("\n"))
        self.assertIn("\n---\n\nRESOLUÇÃO CVM Nº 999", self.arq)

    def test_incerteza_vazia_deixa_a_chave_sem_valor(self):
        arq = escrever_alteradora(999, self.md, ITEM, self.url, "", sha256_fonte="b" * 64)
        self.assertIn("\nincerteza:\n---\n", arq)

    def test_sem_sha256_levanta_erro(self):
        with self.assertRaises(ValueError):
            escrever_alteradora(999, self.md, ITEM, self.url, "")

    def test_numero_diferente_do_item_levanta_erro(self):
        with self.assertRaises(ValueError):
            escrever_alteradora(998, self.md, ITEM, self.url, "", sha256_fonte="a" * 64)

    def test_fonte_consolidada_explicita(self):
        arq = escrever_alteradora(999, self.md, ITEM, self.url, "", sha256_fonte="c" * 64,
                                  fonte_consolidada="https://exemplo/ctresb.md")
        self.assertEqual(dict(ler_frontmatter(arq)[0])["fonte_consolidada"], "https://exemplo/ctresb.md")


if __name__ == "__main__":
    unittest.main()
