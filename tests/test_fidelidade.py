"""Testes de fidelidade: normalização, teste 1 (ato) e teste 2 (final).

A fixture `consolidado017-recorte.md` é um recorte real do consolidado da
Res. CVM 17 (convertido do DOCX da CVM) mais trechos da Res. 175, com o
formato real das notas: redação antiga tachada, nota em parágrafo próprio
("Caput com redação dada pela ...") e "REVOGADO" sem parênteses.
"""
import os
import sys
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from converter import normalizar_artigos  # noqa: E402
from normalizar import normalizar_texto  # noqa: E402
from teste_ato import linhas_novas_fora_do_ato  # noqa: E402
from teste_final import diferencas_final  # noqa: E402

CABECALHO = "---\nid: cvm-res-17\n---\n\n"


def ler(nome):
    with open(os.path.join(AQUI, "fixtures", nome), encoding="utf-8") as f:
        return f.read()


class TestNormalizarTexto(unittest.TestCase):
    def test_espacos_aspas_e_travessoes(self):
        self.assertEqual(
            normalizar_texto("II \u2013  “classe”\u00a0de   cotas — ‘x’"),
            'II - "classe" de cotas - \'x\'',
        )

    def test_remove_nota_entre_parenteses(self):
        self.assertEqual(
            normalizar_texto("§ 1º Texto. (Redação dada pela Resolução CVM nº 181, de 2023)"),
            "§ 1º Texto.",
        )
        self.assertEqual(normalizar_texto("I - x; (Incluído pela Resolução CVM nº 8)"), "I - x;")

    def test_remove_nr(self):
        self.assertEqual(normalizar_texto("Art. 4º Texto. (NR)"), "Art. 4º Texto.")

    def test_remove_nota_em_paragrafo_proprio(self):
        md = (
            "Caput com redação dada pela Resolução CVM nº 226 de 6 de março de 2025.\n\n"
            "§ 2º com redação dada pela Resolução CVM nº 162 de 13 de julho de 2022.\n\n"
            "Inciso VI incluído pela Resolução CVM nº 226, de 2025.\n\n"
            "Alínea “b” revogada pela Resolução CVM nº 240, de 05 de março de 2026.\n\n"
            "Art. 73-A incluído pela Resolução CVM nº 214, de 30 de setembro de 2024.\n\n"
            "Texto normativo."
        )
        self.assertEqual(normalizar_texto(md).strip(), "Texto normativo.")

    def test_texto_normativo_parecido_com_nota_fica(self):
        linha = "§ 3º A classe incluída pela administradora deve ser informada."
        self.assertEqual(normalizar_texto(linha), linha)
        linha = "Art. 22. Fica revogada a Instrução CVM nº 583, de 20 de dezembro de 2016."
        self.assertEqual(normalizar_texto(linha), linha)

    def test_remove_redacao_antiga_tachada(self):
        self.assertEqual(normalizar_texto("~~§ 2º Texto antigo.~~\n§ 2º Texto novo."), "\n§ 2º Texto novo.")
        self.assertEqual(normalizar_texto("A ~~antiga~~ regra"), "A regra")

    def test_marca_de_revogacao_unificada(self):
        for entrada in ("VII – REVOGADO", "VII – (Revogado)", "VII - (Revogado pela Resolução CVM nº 181, de 2023)"):
            self.assertEqual(normalizar_texto(entrada), "VII - (Revogado)", entrada)
        self.assertEqual(normalizar_texto("§ 3º REVOGADO"), "§ 3º (Revogado)")
        self.assertEqual(normalizar_texto("Parágrafo único. REVOGADO"), "Parágrafo único (Revogado)")
        self.assertEqual(normalizar_texto("REVOGADO"), "(Revogado)")
        self.assertEqual(normalizar_texto("(Revogado pela Resolução CVM nº 12)"), "(Revogado)")

    def test_idempotente(self):
        md = "VII – REVOGADO\n\nCaput com redação dada pela Resolução CVM nº 1, de 2020.\n\n“x” — y (NR)"
        uma = normalizar_texto(md)
        self.assertEqual(normalizar_texto(uma), uma)


class TestLinhasNovasForaDoAto(unittest.TestCase):
    ATO = (
        "Art. 1º O art. 9º da Resolução CVM nº 17 passa a vigorar com a seguinte redação:\n\n"
        "“Art. 9º  A substituição do agente fiduciário deve ser comunicada à CVM, no prazo de até 7 (sete) dias úteis.\n\n"
        "Parágrafo único. Aplica-se o § 1º do art. 7º. (NR)”\n"
    )
    CABECALHO_DIFF = (
        "diff --git a/plugins/normas/normas/cvm/resolucoes/0017.md b/plugins/normas/normas/cvm/resolucoes/0017.md\n"
        "--- a/plugins/normas/normas/cvm/resolucoes/0017.md\n"
        "+++ b/plugins/normas/normas/cvm/resolucoes/0017.md\n"
        "@@ -10,3 +10,9 @@\n"
    )

    def diff(self, *adicionadas, removidas=()):
        corpo = "".join("-%s\n" % l for l in removidas) + "".join("+%s\n" % l for l in adicionadas)
        return self.CABECALHO_DIFF + " contexto\n" + corpo

    def test_linha_nova_presente_no_ato_nao_e_listada(self):
        d = self.diff(
            "A substituição do agente fiduciário deve ser comunicada à CVM, no prazo de até 7 (sete) dias úteis.",
            "Parágrafo único. Aplica-se o § 1º do art. 7º.",
        )
        self.assertEqual(linhas_novas_fora_do_ato(d, self.ATO), [])

    def test_linha_inventada_e_listada(self):
        d = self.diff(
            "A substituição do agente fiduciário deve ser comunicada à CVM, no prazo de até 7 (sete) dias úteis.",
            "O agente fiduciário responde solidariamente pelos prejuízos.",
        )
        self.assertEqual(
            linhas_novas_fora_do_ato(d, self.ATO),
            ["O agente fiduciário responde solidariamente pelos prejuízos."],
        )

    def test_linha_com_alteracao_sutil_e_listada(self):
        d = self.diff("A substituição do agente fiduciário deve ser comunicada à CVM, no prazo de até 10 (dez) dias úteis.")
        self.assertEqual(len(linhas_novas_fora_do_ato(d, self.ATO)), 1)

    def test_ignora_headings_frontmatter_e_numeracao(self):
        d = self.diff(
            "---", "verificado_em: 2026-10-28", "vigente_ate_ato: 226", "## Art. 9º", "§ 1º", "I –", "a)",
            "Vigente a partir de 2027-03-01:",
        )
        self.assertEqual(linhas_novas_fora_do_ato(d, self.ATO), [])

    def test_ignora_linhas_removidas_e_cabecalho_do_diff(self):
        d = self.diff(removidas=["Texto antigo que não está no ato."])
        self.assertEqual(linhas_novas_fora_do_ato(d, self.ATO), [])

    def test_marca_de_revogacao_nao_precisa_estar_no_ato(self):
        d = self.diff("VII – (Revogado)", "(Revogado)")
        self.assertEqual(linhas_novas_fora_do_ato(d, self.ATO), [])

    def test_diferenca_de_travessao_aspas_e_espacos_nao_conta(self):
        ato = "“II – sua   remuneração, observado o disposto no art. 14; e”"
        d = self.diff('II - sua remuneração, observado o disposto no art. 14; e')
        self.assertEqual(linhas_novas_fora_do_ato(d, ato), [])


class TestDiferencasFinal(unittest.TestCase):
    def test_nota_de_alteracao_inline_no_consolidado_nao_conta(self):
        consolidado = "Art. 4º O agente deve agir. (Redação dada pela Resolução CVM nº 181, de 2023)\n"
        norma = CABECALHO + "## Art. 4º\n\nO agente deve agir.\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_revogado_no_consolidado_e_ausente_na_norma_e_diferenca(self):
        consolidado = (
            "Art. 4º O agente deve:\n\nI – agir;\n\nII – REVOGADO\n\n"
            "Inciso II revogado pela Resolução CVM nº 181, de 2023.\n\nIII – informar.\n"
        )
        norma = CABECALHO + "## Art. 4º\n\nO agente deve:\n\nI - agir;\n\nIII - informar.\n"
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("Revogado", dif[0])
        self.assertIn("Art. 4º", dif[0])

    def test_revogado_nos_dois_lados_com_marcas_diferentes_nao_conta(self):
        consolidado = "Art. 4º O agente deve:\n\nII – REVOGADO\n\nInciso II revogado pela Resolução CVM nº 181, de 2023.\n"
        norma = CABECALHO + "## Art. 4º\n\nO agente deve:\n\nII – (Revogado pela Resolução CVM nº 181)\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_texto_a_mais_na_norma_e_diferenca(self):
        consolidado = "Art. 4º O agente deve agir.\n"
        norma = CABECALHO + "## Art. 4º\n\nO agente deve agir.\n\nParágrafo único. Texto inventado.\n"
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("Texto inventado", dif[0])
        self.assertIn("norma", dif[0])

    def test_redacao_antiga_tachada_do_consolidado_e_ignorada(self):
        consolidado = "~~Art. 9º Texto antigo.~~\n\nArt. 9º Texto novo.\n\nCaput com redação dada pela Resolução CVM nº 226 de 6 de março de 2025.\n"
        norma = CABECALHO + "## Art. 9º\n\nTexto novo.\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_texto_antigo_na_norma_e_diferenca(self):
        consolidado = "~~Art. 9º Texto antigo.~~\n\nArt. 9º Texto novo.\n"
        norma = CABECALHO + "## Art. 9º\n\nTexto antigo.\n"
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 2, dif)

    def test_ementa_e_titulo_antes_do_primeiro_artigo_nao_contam(self):
        consolidado = "Resolução CVM nº 17 com as alterações introduzidas pela 162/22.\n\nDispõe sobre X.\n\nArt. 1º Texto.\n"
        norma = CABECALHO + "Resolução CVM nº 17, de 9 de fevereiro de 2021\n\nArt. 1º Texto.\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_assinatura_final_do_consolidado_e_ignorada(self):
        consolidado = "Art. 1º Texto.\n\nOriginal assinado por\n\nFULANO DE TAL\n\nPresidente\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_recorte_real_contra_si_mesmo_da_zero(self):
        consolidado = ler("consolidado017-recorte.md")
        norma = CABECALHO + normalizar_artigos(consolidado)
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_recorte_real_sem_a_redacao_nova_do_art_9_acusa_diferenca(self):
        consolidado = ler("consolidado017-recorte.md")
        # a norma ficou com a redação ORIGINAL do art. 9º (a tachada no consolidado)
        linhas = consolidado.split("\n\n")
        antigo = next(l for l in linhas if l.startswith("~~Art. 9º")).strip("~")
        novo = next(l for l in linhas if l.startswith("Art. 9º"))
        norma = CABECALHO + normalizar_artigos(consolidado.replace(novo, antigo))
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 2, dif)
        self.assertTrue(all("Art. 9º" in d for d in dif), dif)

    def test_recorte_real_aponta_revogado_ausente(self):
        consolidado = ler("consolidado017-recorte.md")
        norma = CABECALHO + normalizar_artigos(consolidado).replace("VII – REVOGADO", "")
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("Revogado", dif[0])


if __name__ == "__main__":
    unittest.main()
