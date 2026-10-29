"""Testes de fidelidade: normalização, teste 1 (ato) e teste 2 (final).

A fixture `consolidado017-recorte.md` é um recorte real do consolidado da
Res. CVM 17 (convertido do DOCX da CVM) mais trechos da Res. 175, com o
formato real das notas: redação antiga tachada, nota em parágrafo próprio
("Caput com redação dada pela ...") e "REVOGADO" sem parênteses.
"""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

from converter import normalizar_artigos  # noqa: E402
from normalizar import normalizar_texto  # noqa: E402
from teste_ato import argumentos_diff, linhas_novas_fora_do_ato  # noqa: E402
from teste_final import analisar_final, carregar_aceitas, diferencas_final  # noqa: E402
from validar import partes_da_norma, texto_da_norma  # noqa: E402

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

    def test_marca_de_revogacao_do_consolidado_com_travessao(self):
        casos = {
            "§ 4º - REVOGADO": "§ 4º (Revogado)",
            "§ 2º \u2013 REVOGADO": "§ 2º (Revogado)",
            "Seção I - REVOGADA": "Seção I (Revogado)",
            "CAPÍTULO III - REVOGADO": "CAPÍTULO III (Revogado)",
            "SUPLEMENTO H - REVOGADO": "SUPLEMENTO H (Revogado)",
            "Art. 17 - REVOGADO": "Art. 17 (Revogado)",
            "- REVOGADO": "(Revogado)",
            "\u2013 REVOGADO": "(Revogado)",
        }
        for entrada, esperado in casos.items():
            self.assertEqual(normalizar_texto(entrada), esperado, entrada)

    def test_marca_de_revogacao_nao_afrouxa_texto_normativo(self):
        for linha in ("Seção I - Registro de Distribuição", "CAPÍTULO III - OFERTA PÚBLICA DE DISTRIBUIÇÃO",
                      "§ 4º - O prazo é revogado pelo regulamento.", "- revogado o prazo anterior"):
            self.assertEqual(normalizar_texto(linha), linha)

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

    def test_linha_de_tabela_confere_celula_por_celula(self):
        ato = "| 9.3 Caso os auditores tenham sido contratados | X |\n9.4 Fornecer outras informações"
        d = self.diff("| 9.3 Caso os auditores tenham sido contratados |  |", "| 9.4 Fornecer outras informações | X |")
        self.assertEqual(linhas_novas_fora_do_ato(d, ato), [])

    def test_linha_de_tabela_com_celula_inventada_e_listada(self):
        ato = "| 9.3 Caso os auditores tenham sido contratados |"
        d = self.diff("| 9.3 Caso os auditores tenham sido contratados | Texto inventado |")
        self.assertEqual(len(linhas_novas_fora_do_ato(d, ato)), 1)

    def test_item_numerado_e_nota_revogados_nao_precisam_estar_no_ato(self):
        d = self.diff("1.28 (Revogado)", "5.9 (Revogado)", "(90) (Revogado)")
        self.assertEqual(linhas_novas_fora_do_ato(d, self.ATO), [])

    def test_nota_de_rodape_confere_sem_o_numero(self):
        ato = "Quando da apresentação anual do formulário, as informações devem se referir ao exercício."
        d = self.diff("(1) Quando da apresentação anual do formulário, as informações devem se referir ao exercício.")
        self.assertEqual(linhas_novas_fora_do_ato(d, ato), [])
        self.assertEqual(len(linhas_novas_fora_do_ato(self.diff("(1) Texto que não está no ato."), ato)), 1)


class TestTesteAtoDiff(unittest.TestCase):
    def test_diff_do_git_usa_histogram(self):
        args = argumentos_diff("abc123")
        self.assertIn("--diff-algorithm=histogram", args)
        self.assertEqual(args[-1], "abc123")

    def test_lista_de_partes_do_index_nao_conta(self):
        diff = (
            "diff --git a/plugins/normas/normas/cvm/resolucoes/0175/index.md b/plugins/normas/normas/cvm/resolucoes/0175/index.md\n"
            "--- a/plugins/normas/normas/cvm/resolucoes/0175/index.md\n"
            "+++ b/plugins/normas/normas/cvm/resolucoes/0175/index.md\n"
            "@@ -20,0 +21 @@\n"
            "+- anexo-13.md\n"
        )
        self.assertEqual(linhas_novas_fora_do_ato(diff, "Art. 1º Texto."), [])

    def test_item_de_lista_fora_do_index_continua_contando(self):
        diff = (
            "diff --git a/plugins/normas/normas/cvm/resolucoes/0175/parte-geral.md b/plugins/normas/normas/cvm/resolucoes/0175/parte-geral.md\n"
            "+++ b/plugins/normas/normas/cvm/resolucoes/0175/parte-geral.md\n"
            "@@ -20,0 +21 @@\n"
            "+- anexo-13.md\n"
        )
        self.assertEqual(linhas_novas_fora_do_ato(diff, "Art. 1º Texto."), ["- anexo-13.md"])

    def test_linha_de_texto_no_index_continua_contando(self):
        diff = (
            "diff --git a/plugins/normas/normas/cvm/resolucoes/0175/index.md b/plugins/normas/normas/cvm/resolucoes/0175/index.md\n"
            "+++ b/plugins/normas/normas/cvm/resolucoes/0175/index.md\n"
            "@@ -20,0 +21 @@\n"
            "+Texto inventado.\n"
        )
        self.assertEqual(linhas_novas_fora_do_ato(diff, "Art. 1º Texto."), ["Texto inventado."])


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

    def test_revogado_do_consolidado_com_travessao_casa_com_a_norma(self):
        consolidado = (
            "Art. 4º O agente deve:\n\n§ 4º - REVOGADO\n\nParágrafo revogado pela Resolução CVM nº 181.\n\n"
            "Art. 17 - REVOGADO\n\nArt. 18 Texto.\n"
        )
        norma = CABECALHO + "## Art. 4º\n\nO agente deve:\n\n§ 4º (Revogado)\n\n## Art. 17\n\n(Revogado pela Resolução CVM nº 181)\n\n## Art. 18\n\nTexto.\n"
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


class TestAspasDoAto(unittest.TestCase):
    def test_aspas_de_fechamento_do_ato_nao_contam(self):
        from teste_ato import linhas_novas_fora_do_ato
        ato = 'Art. 1º O art. 5º passa a vigorar com a seguinte redação:\n"§ 2º A declaração deve ser apresentada à CVM". (NR)'
        diff = "+§ 2º A declaração deve ser apresentada à CVM."
        self.assertEqual(linhas_novas_fora_do_ato(diff, ato), [])


SETE = {
    "id": "cvm-res-17",
    "dispositivo": "Art. 9º, caput",
    "consolidado": "A substituição deve ser comunicada no prazo de até 7 (sete) dias úteis.",
    "norma": "A substituição deve ser comunicada no prazo de até sete dias úteis.",
    "motivo": "ajuste editorial do consolidado",
    "ref": "fontes/DIVERGENCIAS.md, Res. CVM 17, item 2",
}


def norma_com_incerteza(corpo, incerteza="Art. 9º: o ato diz sete dias úteis."):
    return "---\nid: cvm-res-17\nincerteza: %s\n---\n\n%s" % (incerteza, corpo)


class TestDivergenciasAceitas(unittest.TestCase):
    CONSOLIDADO = "Art. 9º\n\nA substituição deve ser comunicada no prazo de até 7 (sete) dias úteis.\n\nParágrafo único. Fim.\n"
    CORPO = "## Art. 9º\n\nA substituição deve ser comunicada no prazo de até sete dias úteis.\n\nParágrafo único. Fim.\n"

    def test_par_igual_a_entrada_sai_do_diff(self):
        norma = norma_com_incerteza(self.CORPO)
        self.assertEqual(len(diferencas_final(norma, self.CONSOLIDADO)), 2)
        self.assertEqual(diferencas_final(norma, self.CONSOLIDADO, [SETE]), [])
        dif, n = analisar_final(norma, self.CONSOLIDADO, [SETE])
        self.assertEqual((dif, n), ([], 1))

    def test_linha_repetida_e_coberta_por_uma_entrada_e_copia_nao_e_erro(self):
        linha_n, linha_c = SETE["norma"], SETE["consolidado"]
        norma = norma_com_incerteza("## Art. 9º\n\n%s\n\n%s\n\nParágrafo único. Fim.\n" % (linha_n, linha_n))
        cons = "Art. 9º\n\n%s\n\n%s\n\nParágrafo único. Fim.\n" % (linha_c, linha_c)
        self.assertEqual(diferencas_final(norma, cons, [SETE]), [])
        self.assertEqual(diferencas_final(norma, cons, [SETE, dict(SETE)]), [])

    def test_entrada_sem_par_e_erro_de_aceita_nao_usada(self):
        norma = norma_com_incerteza("## Art. 9º\n\nA substituição deve ser comunicada no prazo de até 7 (sete) dias úteis.\n\nParágrafo único. Fim.\n")
        dif = diferencas_final(norma, self.CONSOLIDADO, [SETE])
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("aceita não usada", dif[0])
        self.assertIn("Art. 9º, caput", dif[0])

    def test_so_um_lado_casando_nao_aceita(self):
        norma = norma_com_incerteza(self.CORPO.replace("sete dias", "oito dias"))
        dif = diferencas_final(norma, self.CONSOLIDADO, [SETE])
        self.assertTrue(any("aceita não usada" in d for d in dif), dif)
        self.assertTrue(any("oito dias" in d for d in dif), dif)

    def test_dispositivo_fora_do_incerteza_e_erro(self):
        norma = norma_com_incerteza(self.CORPO, incerteza="Anexo A ausente.")
        dif = diferencas_final(norma, self.CONSOLIDADO, [SETE])
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("incerteza", dif[0])
        self.assertIn("Art. 9º, caput", dif[0])

    def test_outra_diferenca_continua_aparecendo(self):
        norma = norma_com_incerteza(self.CORPO + "\nTexto inventado.\n")
        dif = diferencas_final(norma, self.CONSOLIDADO, [SETE])
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("Texto inventado", dif[0])

    def test_entrada_so_do_lado_da_norma(self):
        so_norma = dict(SETE, consolidado="", norma="Nota que só a norma tem.", dispositivo="Art. 9º")
        norma = norma_com_incerteza(self.CORPO + "\nNota que só a norma tem.\n")
        dif = diferencas_final(norma, self.CONSOLIDADO, [SETE, so_norma])
        self.assertEqual(dif, [])

    def test_carregar_aceitas_filtra_por_id_e_ausente_da_lista_vazia(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "aceitas.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump([SETE, dict(SETE, id="cvm-res-175")], f)
            self.assertEqual(carregar_aceitas(caminho, "cvm-res-17"), [SETE])
            self.assertEqual(carregar_aceitas(caminho, "cvm-res-60"), [])
            self.assertEqual(carregar_aceitas(os.path.join(d, "nao-existe.json"), "cvm-res-17"), [])

    def test_carregar_aceitas_exige_os_seis_campos(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "aceitas.json")
            incompleta = {k: v for k, v in SETE.items() if k != "motivo"}
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump([incompleta], f)
            with self.assertRaises(ValueError):
                carregar_aceitas(caminho, "cvm-res-17")


class TestNormaEmPartes(unittest.TestCase):
    """Res. 175: index.md + parte-geral.md + anexos, cada um com `## Art. 1º`."""

    INDEX = ("---\nid: cvm-res-175\nincerteza:\n---\n\n# Resolução CVM nº 175\n\n## Partes\n\n"
             "- parte-geral.md\n- anexo-01.md\n")
    GERAL = "# Parte geral\n\n## Art. 1º\n\nTexto da parte geral.\n"
    ANEXO = "# Anexo Normativo I\n\n## Art. 1º\n\nTexto do anexo.\n"
    CONSOLIDADO = "Art. 1º Texto da parte geral.\n\nArt. 1º Texto do anexo.\n"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.pasta = os.path.join(self._tmp.name, "0175")
        os.makedirs(self.pasta)
        self.gravar("index.md", self.INDEX)
        self.gravar("parte-geral.md", self.GERAL)
        self.gravar("anexo-01.md", self.ANEXO)
        self.index = os.path.join(self.pasta, "index.md")

    def gravar(self, nome, texto):
        with open(os.path.join(self.pasta, nome), "w", encoding="utf-8") as f:
            f.write(texto)

    def test_partes_na_ordem_do_indice(self):
        self.assertEqual([os.path.basename(p) for p in partes_da_norma(self.index)],
                         ["parte-geral.md", "anexo-01.md"])

    def test_texto_da_norma_concatena_na_ordem_sem_fundir_artigos(self):
        texto = texto_da_norma(self.index)
        self.assertLess(texto.index("Texto da parte geral."), texto.index("Texto do anexo."))
        self.assertEqual(texto.count("## Art. 1º"), 2)

    def test_arquivo_unico_devolve_o_proprio_texto(self):
        self.assertEqual(texto_da_norma(os.path.join(self.pasta, "anexo-01.md")), self.ANEXO)

    def test_teste_2_sobre_as_partes_contra_consolidado_com_as_mesmas_linhas(self):
        self.assertEqual(diferencas_final(texto_da_norma(self.index), self.CONSOLIDADO), [])

    def test_titulos_de_parte_com_um_cerquilha_sao_ignorados_na_norma(self):
        # o "# Anexo Normativo I" não está no consolidado e não conta como diferença
        self.assertNotIn("Anexo Normativo I", self.CONSOLIDADO)
        self.assertEqual(diferencas_final(texto_da_norma(self.index), self.CONSOLIDADO), [])

    def test_partes_fora_de_ordem_acusam_diferenca(self):
        self.gravar("index.md", self.INDEX.replace("- parte-geral.md\n- anexo-01.md", "- anexo-01.md\n- parte-geral.md"))
        dif = diferencas_final(texto_da_norma(self.index), self.CONSOLIDADO)
        self.assertTrue(dif)

    def test_artigo_do_anexo_nao_funde_com_o_da_parte_geral(self):
        # a parte geral perde o texto: sobra só o do anexo, e a diferença aparece
        self.gravar("parte-geral.md", "# Parte geral\n\n## Art. 1º\n")
        dif = diferencas_final(texto_da_norma(self.index), self.CONSOLIDADO)
        self.assertEqual(len(dif), 1, dif)
        self.assertIn("Texto da parte geral.", dif[0])


class TestTabelas(unittest.TestCase):
    def test_numero_de_tabelas_diferente_e_diferenca(self):
        consolidado = "Art. 1º Texto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nMeio.\n\n| C | D |\n| --- | --- |\n| 3 | 4 |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nMeio.\n"
        dif = diferencas_final(norma, consolidado)
        self.assertIn("tabelas: 1 na norma, 2 no consolidado", dif)

    PARTIDA = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n| 3 | 4 |\n"
    INTEIRA = "Art. 1º Texto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
    ACEITA_TABELAS = {"id": "cvm-res-17", "dispositivo": "tabelas", "consolidado": "1", "norma": "2",
                      "motivo": "o DOU parte a tabela em duas", "ref": "teste"}

    def test_aceita_de_tabelas_cobre_a_contagem(self):
        norma = norma_com_incerteza("## Art. 1º\n\nTexto.\n\n" + self.PARTIDA, "tabelas: o DOU parte uma tabela.")
        self.assertEqual(diferencas_final(norma, self.INTEIRA), ["tabelas: 2 na norma, 1 no consolidado"])
        self.assertEqual(diferencas_final(norma, self.INTEIRA, [self.ACEITA_TABELAS]), [])

    def test_aceita_de_tabelas_com_outra_contagem_nao_e_usada(self):
        norma = norma_com_incerteza("## Art. 1º\n\nTexto.\n\n" + self.PARTIDA, "tabelas: o DOU parte uma tabela.")
        aceita = dict(self.ACEITA_TABELAS, norma="3")
        dif = diferencas_final(norma, self.INTEIRA, [aceita])
        self.assertIn("tabelas: 2 na norma, 1 no consolidado", dif)
        self.assertTrue(any(d.startswith("aceita não usada: tabelas") for d in dif), dif)

    def test_aceita_de_tabelas_exige_incerteza(self):
        norma = norma_com_incerteza("## Art. 1º\n\nTexto.\n\n" + self.PARTIDA, "nada aqui")
        dif = diferencas_final(norma, self.INTEIRA, [self.ACEITA_TABELAS])
        self.assertTrue(any("aceita fora do incerteza: tabelas" in d for d in dif), dif)

    def test_mesma_tabela_com_celulas_vazias_a_mais_nao_conta(self):
        consolidado = "Art. 1º Texto.\n\n| A |  | B |\n| --- | --- | --- |\n| 1 |  | 2 |\n|  |  |  |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_celula_diferente_e_diferenca(self):
        consolidado = "Art. 1º Texto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A | B |\n| --- | --- |\n| 1 | 3 |\n"
        dif = diferencas_final(norma, consolidado)
        self.assertEqual(len(dif), 2, dif)

    def test_tabelas_adjacentes_separadas_por_linha_em_branco_contam_duas(self):
        md = "Art. 1º Texto.\n\n| A |\n| --- |\n\n| B |\n| --- |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A |\n| --- |\n"
        self.assertIn("tabelas: 1 na norma, 2 no consolidado", diferencas_final(norma, md))

    def test_anotacao_de_alteracao_dentro_da_tabela_nao_parte_a_tabela(self):
        consolidado = (
            "Art. 1º Texto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
            "| Alínea b.1.10 incluída pela Resolução CVM nº 226, de 6 de março de 2025. |  |\n"
            "| 3 | 4 |\n"
        )
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_anotacao_nao_junta_tabelas_separadas_por_linha_em_branco(self):
        consolidado = "Art. 1º Texto.\n\n| A |\n| --- |\n\n| B |\n| --- |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\n| A |\n| --- |\n"
        self.assertIn("tabelas: 1 na norma, 2 no consolidado", diferencas_final(norma, consolidado))

    def test_tabela_sem_nenhuma_celula_com_texto_nao_conta(self):
        consolidado = (
            "Art. 1º Texto.\n\n| ~~A~~ | ~~B~~ |\n| --- | --- |\n| ~~1~~ |  |\n\n"
            "Meio.\n\n| C |\n| --- |\n| 3 |\n"
        )
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n\nMeio.\n\n| C |\n| --- |\n| 3 |\n"
        self.assertEqual(diferencas_final(norma, consolidado), [])

    def test_tabela_com_texto_so_no_consolidado_continua_sendo_diferenca(self):
        consolidado = "Art. 1º Texto.\n\n| A |\n| --- |\n| 1 |\n"
        norma = CABECALHO + "## Art. 1º\n\nTexto.\n"
        dif = diferencas_final(norma, consolidado)
        self.assertIn("tabelas: 0 na norma, 1 no consolidado", dif)


class TestSoNormas(unittest.TestCase):
    def test_resolucoes_e_instrucoes_sim_alteradoras_nao(self):
        from teste_ato import so_normas
        diff = ("diff --git a/p/cvm/resolucoes/0017.md b/p/cvm/resolucoes/0017.md\n+a\n"
                "diff --git a/p/cvm/instrucoes/0489.md b/p/cvm/instrucoes/0489.md\n+b\n"
                "diff --git a/p/cvm/alteradoras/instrucao-0502.md b/p/cvm/alteradoras/instrucao-0502.md\n+c\n")
        out = so_normas(diff)
        self.assertIn("+a", out)
        self.assertIn("+b", out)
        self.assertNotIn("+c", out)
