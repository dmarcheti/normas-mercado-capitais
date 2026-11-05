"""Testes da Fase 3, camada 4: texto vigente pela última versão compilada do BCB (scripts/bcb_versoes.py
e a integração em texto_vigente). Sem rede, sem PDFKit (swift) e sem textutil: download e extração
são substituídos."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import bcb_versoes as bv  # noqa: E402
import texto_vigente as tv  # noqa: E402
from validar import CAMPOS, MARCA_VIGENCIA, ler_frontmatter, validar_norma  # noqa: E402

DOCS = "Res_4734_v1_O.pdf;179#;Res_4734_v2_L.pdf;396#;Res_4734_v2_P.pdf;397#;Res_4734_v6_P.pdf;9#;Res_4734_v6_L.pdf;8#;"

# Texto do PDF L como o PDFKit o dá: páginas separadas por form feed, rodapé com o título curto e
# "Página N de M", número da página grudado no ano, aviso do DOU e notas de redação.
PDF = ("1\nRESOLUÇÃO Nº 4.734, DE 27 DE JUNHO DE 2019\n"
       "Dispõe sobre as condições para a emissão de garantias.\n"
       "O Banco Central do Brasil, na forma do art. 9º da Lei nº 4.595, torna público que o Conselho "
       "Monetário Nacional resolveu:\n"
       "Art. 1º As instituições financeiras podem emitir garantias em favor de terceiros observadas as "
       "condições desta Resolução. (Redação dada pela Resolução CMN nº 4.888, de 21/1/2021.)\n"
       "Resolução nº 4.734, de 27 de junho de 2019 Página 1 de 2\f"
       "Resolução nº 4.734, de 27 de junho de 2019 Página 2 de 2\n"
       "Art. 2º A garantia deve ser registrada em sistema de ob-\njeto autorizado pelo Banco Central.\n"
       "Art. 3º Esta Resolução entra em vigor na data de sua publicação.\n"
       "Este texto não substitui o publicado no DOU de 28/6/2019, Seção 1, p. 45.\n")
HTML = ("O Banco Central do Brasil, na forma do art. 9º da Lei nº 4.595, torna público que o Conselho "
        "Monetário Nacional resolveu:\n\n"
        "Art. 1º As instituições financeiras podem emitir garantias em favor de terceiros observadas as "
        "condições desta Resolução.\n\n"
        "Art. 2º A garantia deve ser registrada em sistema de objeto autorizado pelo Banco Central.\n\n"
        "Art. 3º Esta Resolução entra em vigor na data de sua publicação.\n")


class TestUltimaVersao(unittest.TestCase):
    def test_maior_versao_e_l_antes_de_p_e_o(self):
        docs = tv.documentos_bcb(DOCS)
        self.assertEqual(bv.ultima_versao(docs), ("Res_4734_v6_L.pdf", 6, "L"))
        self.assertEqual(bv.ultima_versao([("X_v3_P.pdf", 3, "P"), ("X_v3_O.pdf", 3, "O"), ("X_v2_L.pdf", 2, "L")]),
                         ("X_v3_O.pdf", 3, "O"))  # sem L na última versão: o de maior versão
        self.assertIsNone(bv.ultima_versao([]))

    def test_precisa_versao(self):
        self.assertTrue(bv.precisa_versao(tv.documentos_bcb(DOCS), ""))
        self.assertFalse(bv.precisa_versao([("A_v1_O.pdf", 1, "O")], ""))
        self.assertTrue(bv.precisa_versao([("A_v1_O.pdf", 1, "O")], "Resolução CMN nº 1/2020 - Alteração;#"))
        self.assertFalse(bv.precisa_versao([], "Resolução CMN nº 1/2020 - Alteração;#"))  # sem PDF


class TestCabecalhoRodape(unittest.TestCase):
    def test_tira_rodape_aviso_e_numero_da_pagina(self):
        t = bv.sem_cabecalho_rodape(PDF, 4734)
        self.assertNotIn("Página", t)
        self.assertNotIn("Este texto não substitui", t)
        self.assertNotIn("de 27 de junho de 2019", t.split("\n", 2)[2])  # só o título fica
        self.assertTrue(t.startswith("RESOLUÇÃO Nº 4.734"))
        self.assertIn("Art. 2º A garantia", t)

    def test_variantes_do_rodape(self):
        for rodape, numero in (("Resolução nº 2907, de 29 de novembro de 2001", 2907),
                               ("Resolução nº 3.334, de 22 de dezembro de 2005 1", 3334),
                               ("Resolução nº 1502, de 28 de julho de 1988.", 1502),
                               ("Resolução nº 102, de 26 de novembro de19682", 102),
                               ("Circular nº 3082, de 30 de janeiro de 2002 Página 3 de 4", 3082)):
            t = bv.sem_cabecalho_rodape("Art. 1º Texto.\n%s\f2\nArt. 2º Mais texto.\n" % rodape, numero)
            self.assertEqual(t, "Art. 1º Texto.\nArt. 2º Mais texto.\n", rodape)

    def test_rodape_grudado_no_texto(self):
        t = bv.sem_cabecalho_rodape(
            "o risco, em particular\nResolução nº 4.734, de 27 de junho de 2019 Página 2 de 7\fem particular", 4734)
        self.assertEqual(t, "o risco, em particular\nem particular\n")
        t = bv.sem_cabecalho_rodape("direitos a eleResolução nº 2907, de 29 de novembro de 2001pertencentes", 2907)
        self.assertEqual(t, "direitos a ele\npertencentes\n")
        t = bv.sem_cabecalho_rodape("Resolução nº 2907, de 29 de novembro de 2001risco de crédito", 2907)
        self.assertEqual(t, "risco de crédito\n")
        t = bv.sem_cabecalho_rodape("Valor 17,02\nCarta Circular nº 3.934, de 21 de fevereiro de 2019 Descrição\n", 3934)
        self.assertEqual(t, "Valor 17,02\nDescrição\n")

    def test_nao_tira_citacao_de_outra_norma(self):
        t = bv.sem_cabecalho_rodape("Resolução nº 4.888, de 21 de janeiro de 2021\nArt. 1º Texto.\n", 4734)
        self.assertIn("4.888", t)

    def test_limpar_une_hifenizacao(self):
        self.assertIn("sistema de objeto autorizado", bv.limpar_pdf(PDF, 4734).replace("\n", " "))


class TestDecisao(unittest.TestCase):
    def test_html_igual_ao_pdf_fica_html(self):
        a, b = bv.coberturas(HTML, PDF, 4734)
        self.assertEqual((a, b), (1.0, 1.0))  # notas, ementa, título, rodapé e aviso fora
        self.assertEqual(bv.decidir(a, b), "html")

    def test_html_atrasado_vai_para_o_pdf(self):
        antigo = HTML.replace("observadas as condições desta Resolução", "nos termos do regulamento")
        a, b = bv.coberturas(antigo, PDF, 4734)
        self.assertLess(b, 0.99)
        self.assertEqual(bv.decidir(a, b), "pdf")
        self.assertEqual(bv.decidir(0.995, 0.99), "html")
        self.assertEqual(bv.decidir(1.0, 0.989), "pdf")

    def _decidir(self, html, conteudo=None, extrair=lambda p: PDF):
        baixados = []

        def baixar(url, destino):
            baixados.append((url, destino))
            return destino
        c = conteudo or {"Id": 50797, "Atualizacoes": ""}
        dec = bv.decidir_fonte({"numero": 4734}, c, tv.documentos_bcb(DOCS), html, extrair,
                               cache="/c", baixar=baixar, data_base="2026-10-30")
        return dec, baixados

    def test_decidir_fonte_baixa_o_l_da_ultima_versao(self):
        dec, baixados = self._decidir(HTML)
        url = "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50797/Res_4734_v6_L.pdf"
        self.assertEqual(baixados, [(url, os.path.join("/c", "Res_4734_v6_L.pdf"))])
        self.assertEqual((dec["decisao"], dec["versao"], dec["url"]), ("html", 6, url))
        self.assertNotIn("notas_vigencia", dec)

    def test_decidir_fonte_sem_pdfkit_mantem_html(self):
        dec, _ = self._decidir(HTML.replace("Banco Central", "BC"), extrair=lambda p: None)
        self.assertEqual(dec["decisao"], "html")
        self.assertIn("PDFKit", dec["motivo"])

    def test_decidir_fonte_sem_versao_nao_baixa(self):
        dec = bv.decidir_fonte({"numero": 1}, {"Id": 1}, [("A_v1_O.pdf", 1, "O")], HTML, None,
                               baixar=lambda u, d: self.fail("baixou"))
        self.assertIsNone(dec)


class TestVigenciaFutura(unittest.TestCase):
    def test_nota_futura_e_passada(self):
        txt = ("Art. 2º Texto novo. (Redação dada, a partir de 1º/1/2027, pela Resolução CMN nº 5.343, "
               "de 4/6/2026.)\nArt. 3º (Revogado, a partir de 1º/1/2025, pela Resolução CMN nº 5.100.)")
        self.assertEqual(bv.vigencias_futuras(txt, "2026-10-30"), [("2027-01-01", "redação dada")])

    def test_bloco_vigencia_segue_a_spec(self):
        bloco = bv.bloco_vigencia("Art. 2º Redação atual.", "Art. 2º Redação futura.", "2027-01-01")
        self.assertTrue(MARCA_VIGENCIA.search(bloco))
        self.assertEqual(tv.vigencia(bloco), ("2027-01-01", [], True))
        self.assertTrue(bloco.startswith("Art. 2º Redação atual.\n\n> Vigente a partir de 1 de janeiro de 2027:"))

    def test_so_uma_redacao_vira_incerteza_sem_texto_inventado(self):
        txt = "Art. 2º Texto novo. (Redação dada, a partir de 1º/1/2027, pela Resolução CMN nº 5.343.)"
        atual = ("Resolução CMN nº 5.343/2026 - Alteração a partir de 1º/1/2027 - Nova redação: art. 2º.;#"
                 "Resolução CMN nº 4.966/2021 - Revogação total, a partir de 1º/7/2027.;#"
                 "Resolução CMN nº 5.100/2023 - Alteração, a partir de 1º/1/2025 - Revogação: art. 3º.;#")
        notas = bv.notas_vigencia(txt, atual, 3, "2026-10-30")
        self.assertEqual(len(notas), 2)
        self.assertIn("redação dada a partir de 1 de janeiro de 2027", notas[0])
        self.assertIn("não foi reconstituída [verificar]", notas[0])
        self.assertIn("Revogação total, a partir de 1º/7/2027", notas[1])  # a de 2027-01-01 já está no PDF
        self.assertNotIn("5.100", " ".join(notas))  # passada


class TestIntegracao(unittest.TestCase):
    ITEM = {"id": "cmn-res-4734", "orgao": "cmn", "tipo": "resolucao-cmn", "numero": 4734,
            "data": "2019-06-27", "dou": "2019-06-28", "ementa": "Dispõe sobre garantias.",
            "situacao": "vigente", "url_pagina": "https://www.bcb.gov.br/estabilidadefinanceira/x",
            "fontes": {"consolidado": {"htm": "https://www.bcb.gov.br/estabilidadefinanceira/x"}},
            "alteradoras": [], "vigente_ate_ato": "", "arquivo": "cmn/resolucoes/4734.md", "notas": [],
            "conversor": "html_bcb", "versao": 6.0}

    def _preparar(self, dec):
        with tempfile.TemporaryDirectory() as d:
            item = dict(self.ITEM, cache_api=os.path.join(d, "api.json"))
            with open(item["cache_api"], "w", encoding="utf-8") as f:
                json.dump({"conteudo": [{"Id": 50797, "Documentos": DOCS, "Texto": "<p>x</p>"}]}, f)
            tv.preparar_bcb(item, versoes=lambda i, c, docs: dec)
        return item

    def test_html_coberto_fica_html(self):
        item = self._preparar({"decisao": "html", "arquivo": "Res_4734_v6_L.pdf", "versao": 6, "sufixo": "L",
                               "url": "u", "path": "/c/Res_4734_v6_L.pdf",
                               "cobertura_html_pdf": 1.0, "cobertura_pdf_html": 1.0})
        self.assertEqual(item["conversor"], "html_bcb")
        self.assertEqual(list(item["fontes"]["consolidado"]), ["htm"])
        self.assertEqual(item["versao_bcb"]["decisao"], "html")

    def test_sem_versao_a_conferir_registra_decisao_html(self):
        item = self._preparar(None)
        self.assertEqual(item["conversor"], "html_bcb")
        self.assertEqual(item["versao_bcb"]["decisao"], "html")
        self.assertIn("sem versão compilada", item["versao_bcb"]["motivo"])

    def test_api_sem_pdf_registra_decisao_html(self):
        with tempfile.TemporaryDirectory() as d:
            item = dict(self.ITEM, cache_api=os.path.join(d, "api.json"))
            with open(item["cache_api"], "w", encoding="utf-8") as f:
                json.dump({"conteudo": [{"Id": 51395, "Documentos": None, "Texto": "<p>x</p>"}]}, f)
            tv.preparar_bcb(item, versoes=lambda i, c, docs: None)
        self.assertEqual(item["versao_bcb"]["decisao"], "html")
        self.assertIn("não lista PDF", item["versao_bcb"]["motivo"])
        self.assertNotIn("aviso", item["versao_bcb"])

    def test_html_atrasado_passa_para_o_pdf_l(self):
        url = "https://normativos.bcb.gov.br/Lists/Normativos/Attachments/50797/Res_4734_v6_L.pdf"
        item = self._preparar({"decisao": "pdf", "arquivo": "Res_4734_v6_L.pdf", "versao": 6, "sufixo": "L",
                               "url": url, "path": "/c/Res_4734_v6_L.pdf", "notas_vigencia": ["Futura."]})
        self.assertNotIn("conversor", item)
        self.assertEqual(item["fontes"], {"consolidado": {"pdf": url}})
        self.assertEqual(item["cache_pdf"], "/c/Res_4734_v6_L.pdf")
        self.assertEqual(item["notas"], [
            "Texto vigente compilado pelo BCB no PDF da versão 6 (`Res_4734_v6_L.pdf`); o campo de texto da "
            "busca de normas do BCB traz a redação original.", "Futura."])
        self.assertTrue(item["fonte_original"].endswith("/Res_4734_v1_O.pdf"))

    def test_montar_pdf_do_bcb_sem_rodape_e_valido(self):
        item = dict(self.ITEM, fontes={"consolidado": {"pdf": "https://n/Res_4734_v6_L.pdf"}},
                    pdf_bcb={"arquivo": "Res_4734_v6_L.pdf", "versao": 6, "sufixo": "L"},
                    notas=[bv.incerteza_pdf(6, "Res_4734_v6_L.pdf")])
        del item["conversor"]
        with tempfile.TemporaryDirectory() as d:
            pdf = os.path.join(d, "f.pdf")
            with open(pdf, "wb") as f:
                f.write(b"%PDF-1.4 falso")
            with mock.patch.object(tv, "_pdfkit_txt", return_value=PDF), \
                    mock.patch.object(tv, "_pdf_txt", return_value=PDF):
                md, rel = tv.montar(item, pdf, "consolidado", "pdf", "https://n/Res_4734_v6_L.pdf")
            destino = os.path.join(d, "saida", item["arquivo"])
            os.makedirs(os.path.dirname(destino))
            with open(destino, "w", encoding="utf-8") as f:
                f.write(md)
            self.assertEqual(validar_norma(destino), [])
        pares, _, _ = ler_frontmatter(md)
        v = dict(pares)
        self.assertEqual([k for k, _ in pares], CAMPOS + ["nivel_verificacao"])
        self.assertEqual((v["nivel_verificacao"], v["versao_texto"], v["fonte_consolidada"]),
                         ("pdf-extraido", "consolidado", "https://n/Res_4734_v6_L.pdf"))
        self.assertIn("no PDF da versão 6 (`Res_4734_v6_L.pdf`)", v["incerteza"])
        self.assertNotIn("Página", md)
        self.assertNotIn("Este texto não substitui", md)
        self.assertIn("## Art. 1º", md)
        self.assertIn("(Redação dada pela Resolução CMN nº 4.888, de 21/1/2021.)", md)
        self.assertIn("sistema de objeto", md)
        self.assertEqual(rel["cobertura"], 1.0)


if __name__ == "__main__":
    unittest.main()
