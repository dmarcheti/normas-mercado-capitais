"""Testes da montagem das leis (scripts/leis.py) e das regras de conversão do Planalto que ela exige."""
import json
import os
import re
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import leis  # noqa: E402
from converter import com_rotulo_riscado, normalizar_artigos, planalto_html_para_md  # noqa: E402
from teste_lei import diferencas_lei  # noqa: E402
from validar import ler_frontmatter, texto_da_norma, validar_norma  # noqa: E402

FIXTURES = os.path.join(AQUI, "fixtures")


def ler_fixture(nome):
    with open(os.path.join(FIXTURES, nome), "rb") as f:
        return f.read()


ITEM_PARTES = {
    "id": "lei-12345", "numero": 12345, "data": "1976-12-07", "ementa_curta": "Teste", "partes": "capitulo",
    "planalto": ["ccivil_03/leis/l12345compilada.htm", "ccivil_03/leis/l12345.htm"],
}
ITEM_CC = {
    "id": "lei-10406", "numero": 10406, "data": "2002-01-10", "ementa_curta": "Código Civil", "recorte": ["1.368-C", "1.368-F"],
    "planalto": ["ccivil_03/leis/2002/l10406compilada.htm", "ccivil_03/leis/2002/l10406.htm"],
}


def gravar(pasta, arquivos):
    for nome, conteudo in arquivos.items():
        caminho = os.path.join(pasta, *nome.split("/"))
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)


def frontmatter(conteudo):
    pares, _corpo, erro = ler_frontmatter(conteudo)
    assert erro is None, erro
    return dict(pares)


class TestConverterPlanalto(unittest.TestCase):
    def md(self, html, citacoes=True):
        return normalizar_artigos(planalto_html_para_md(html), ignorar_citacoes=citacoes)

    def cabecalhos(self, md):
        return re.findall(r"^## Art\. .+$", md, flags=re.M)

    def test_art_com_espaco_antes_do_ponto(self):
        md = self.md("<p>Art . 3º Texto.</p><p>Art. 104.Outro texto, sem espaço depois do ponto.</p>")
        self.assertEqual(self.cabecalhos(md), ["## Art. 3º", "## Art. 104"])
        self.assertIn("Outro texto, sem espaço", md)

    def test_artigo_entre_aspas_curvas_nao_e_cabecalho(self):
        md = self.md("<p>Art. 1º Altera:</p><p>“Art. 5-A. Citado.</p><p>§ 1º Citado.” (NR)</p><p>Art. 2º Vigor.</p>")
        self.assertEqual(self.cabecalhos(md), ["## Art. 1º", "## Art. 2º"])

    def test_artigo_entre_aspas_retas_nao_e_cabecalho(self):
        md = self.md('<p>Art. 1º Altera:</p><p>"Art. 5-A. Citado.</p><p>Art. 9. Também citado.</p>'
                     '<p>Parágrafo único. Fecha." (NR)</p><p>Art. 2º Vigor.</p>')
        self.assertEqual(self.cabecalhos(md), ["## Art. 1º", "## Art. 2º"])

    def test_aspa_reta_de_fechamento_sem_abertura_nao_prende_o_resto(self):
        md = self.md('<p>Art. 1º A.</p><p>texto que fecha uma citação aberta antes." (Incluído)</p><p>Art. 2º B.</p>')
        self.assertEqual(self.cabecalhos(md), ["## Art. 1º", "## Art. 2º"])

    def test_citacao_sem_fecho_nao_engole_o_artigo_sucessor_do_ultimo(self):
        # Caso da Lei 14.711: "Art. 8º-E" abre aspas e o Planalto não as fecha.
        md = self.md("<p>Art. 6º A.</p><p>“Art. 8º-E Citado, sem fecho.</p><p>Art. 7º B.</p>"
                     "<p>“Art. 7º-A Citado.”</p><p>Art. 8º C.</p>")
        self.assertEqual(self.cabecalhos(md), ["## Art. 6º", "## Art. 7º", "## Art. 8º"])

    def test_sem_ignorar_citacoes_o_artigo_citado_vira_cabecalho(self):
        md = self.md("<p>Art. 1º A.</p><p>“Art. 5-A. Citado.”</p><p>Art. 2º B.</p><p>“Art. 6-A. Citado.</p><p>Art. 7º C.</p>",
                     citacoes=False)
        self.assertIn("## Art. 7º", md)

    def test_span_com_line_through_e_tachado(self):
        md = self.md('<p>Art. 1º <span style="text-decoration:line-through">Antiga.</span> Nova.</p>')
        self.assertIn("Nova.", md)
        self.assertNotIn("Antiga", md)

    def test_span_sem_line_through_fica(self):
        md = self.md('<p>Art. 1º <span style="color:red">Fica.</span> Resto.</p>')
        self.assertIn("Fica. Resto.", md)

    def test_rotulo_riscado_volta_com_a_marca_de_revogacao(self):
        md = self.md("<p><strike>Art. 6º Texto revogado.</strike> (Revogado pela Lei nº 10, de 2001)</p>")
        self.assertEqual(self.cabecalhos(md), ["## Art. 6º"])
        self.assertIn("(Revogado pela Lei nº 10, de 2001)", md)
        self.assertNotIn("Texto revogado", md)

    def test_rotulo_riscado_com_ponto_solto_antes_da_marca(self):
        md = self.md('<p><strike>Art. 7º Outro texto</strike>. <a href="x">(Revogado pela Lei nº 10, de 2001)</a></p>')
        self.assertEqual(self.cabecalhos(md), ["## Art. 7º"])

    def test_com_rotulo_riscado_so_age_quando_o_visivel_e_a_marca(self):
        self.assertEqual(com_rotulo_riscado("(Revogado pela Lei nº 1)", "Art. 6º Velho."), "Art. 6º (Revogado pela Lei nº 1)")
        self.assertEqual(com_rotulo_riscado("Texto novo.", "Art. 6º Velho."), "Texto novo.")
        self.assertEqual(com_rotulo_riscado(". (Revogado pela Lei nº 1)", "§ 2º Velho"), "§ 2º (Revogado pela Lei nº 1)")
        self.assertEqual(com_rotulo_riscado("(Revogado pela Lei nº 1)", "texto sem rótulo"), "(Revogado pela Lei nº 1)")
        self.assertEqual(com_rotulo_riscado("(Revogada)", "Parágrafo único. Velho."), "Parágrafo único. (Revogada)")


class TestTesteLeiPlanalto(unittest.TestCase):
    """Regras de teste_lei.py que as leis do Planalto exigem."""

    def corpo(self, *blocos):
        return "---\nid: lei-1\n---\n\n" + "\n\n".join(blocos) + "\n"

    def test_rotulo_riscado_no_html_bate_com_a_marca_na_norma(self):
        h = "<html><body><p>Art. 1º A.</p><p><strike>Art. 2º Velho.</strike> (Revogado pela Lei nº 3)</p><p>Art. 3º C.</p></body></html>"
        norma = self.corpo("## Art. 1º", "A.", "## Art. 2º", "(Revogado pela Lei nº 3)", "## Art. 3º", "C.")
        self.assertEqual(diferencas_lei(norma, h), [])

    def test_paragrafo_dentro_de_celula_nao_quebra_a_linha(self):
        h = ("<html><body><p>Art. 1º A:</p><table><tr><td><p>Classe</p></td><td><p>Valor</p></td></tr>"
             "<tr><td><p>Até 100</p></td><td><p>600,00</p></td></tr></table><p>Art. 2º B.</p></body></html>")
        norma = self.corpo("## Art. 1º", "A:", "| Classe | Valor |\n| --- | --- |\n| Até 100 | 600,00 |", "## Art. 2º", "B.")
        self.assertEqual(diferencas_lei(norma, h), [])

    def test_ruido_de_pagina_nao_conta(self):
        h = "<html><body><p>Art. 1º A.</p><p>*</p><p>Não remover</p><p>Up</p><p>Down</p><p>Art. 2º B.</p></body></html>"
        norma = self.corpo("## Art. 1º", "A.", "## Art. 2º", "B.")
        self.assertEqual(diferencas_lei(norma, h), [])

    def test_br_vira_espaco_e_artigo_citado_e_texto(self):
        h = "<html><body><p>Art. 1º Altera:<br>“Art. 5-A. Citado.” (NR)</p><p>Art. 2º B.</p></body></html>"
        norma = self.corpo("## Art. 1º", "Altera: “Art. 5-A. Citado.” (NR)", "## Art. 2º", "B.")
        self.assertEqual(diferencas_lei(norma, h), [])

    def test_recorte_ignora_titulo_estrutural_que_precede_o_artigo_seguinte(self):
        h = ("<html><body><p>Art. 1.368-C. C.</p><p>Art. 1.368-D. D.</p><p>Art. 1.368-E. E.</p><p>Art. 1.368-F. F.</p>"
             "<p>TÍTULO IV Da Superfície</p><p>Art. 1.369. Depois.</p></body></html>")
        norma = self.corpo("## Art. 1.368-C", "C.", "## Art. 1.368-D", "D.", "## Art. 1.368-E", "E.", "## Art. 1.368-F", "F.")
        self.assertEqual(diferencas_lei(norma, h), [])

    def test_recorte_nao_apaga_texto_que_nao_e_titulo(self):
        h = ("<html><body><p>Art. 1.368-C. C.</p><p>Art. 1.368-D. D.</p><p>Art. 1.368-E. E.</p><p>Art. 1.368-F. F.</p>"
             "<p>Texto solto do artigo F.</p><p>Art. 1.369. Depois.</p></body></html>")
        norma = self.corpo("## Art. 1.368-C", "C.", "## Art. 1.368-D", "D.", "## Art. 1.368-E", "E.", "## Art. 1.368-F", "F.")
        self.assertTrue(diferencas_lei(norma, h))


class TestMontarLeiEmPartes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = ler_fixture("lei-planalto-duas-partes.html")
        cls.saida = leis.montar_lei(ITEM_PARTES, cls.html)

    def test_index_e_um_arquivo_por_capitulo(self):
        self.assertEqual(sorted(self.saida), ["lei-12345/cap-01.md", "lei-12345/cap-02.md", "lei-12345/index.md"])

    def test_index_lista_as_partes_em_ordem(self):
        index = self.saida["lei-12345/index.md"]
        self.assertRegex(index, r"## Partes\n\n- cap-01\.md\n- cap-02\.md\n")
        self.assertNotIn("## Art.", index)

    def test_parte_abre_com_titulo_e_tem_a_linha_do_capitulo(self):
        cap1 = self.saida["lei-12345/cap-01.md"]
        self.assertTrue(cap1.startswith("# Capítulo I - Disposições Gerais\n"), cap1[:80])
        self.assertIn("\nCAPÍTULO I\n", cap1)
        self.assertTrue(self.saida["lei-12345/cap-02.md"].startswith("# Capítulo II - Das Citações\n"))
        self.assertFalse(cap1.startswith("---"))

    def test_artigos_nos_capitulos_certos(self):
        cap1, cap2 = self.saida["lei-12345/cap-01.md"], self.saida["lei-12345/cap-02.md"]
        self.assertEqual(re.findall(r"^## Art\. .+$", cap1, flags=re.M), ["## Art. 1º", "## Art. 2º"])
        self.assertEqual(re.findall(r"^## Art\. .+$", cap2, flags=re.M),
                         ["## Art. 3º", "## Art. 4º", "## Art. 5º", "## Art. 6º", "## Art. 7º", "## Art. 8º"])

    def test_art_com_espaco_e_citacoes(self):
        cap1, cap2 = self.saida["lei-12345/cap-01.md"], self.saida["lei-12345/cap-02.md"]
        self.assertIn("## Art. 2º\n\nSegundo artigo", cap1)
        self.assertNotIn("## Art. 31-A", cap2)
        self.assertNotIn("## Art. 8-A", cap2)
        self.assertIn("“Art. 31-A. Artigo citado", cap2)

    def test_tachado_sai_e_rotulo_riscado_fica_com_a_marca(self):
        cap2 = self.saida["lei-12345/cap-02.md"]
        self.assertNotIn("Redação antiga", cap2)
        self.assertIn("Redação nova.", cap2)
        self.assertNotIn("Texto revogado", cap2)
        self.assertIn("## Art. 6º\n\n(Revogado pela Lei nº 10, de 2001)", cap2)
        self.assertIn("## Art. 7º\n\n(Revogado pela Lei nº 10, de 2001)", cap2)

    def test_tabela_de_layout_do_fim_vira_texto(self):
        cap2 = self.saida["lei-12345/cap-02.md"]
        self.assertNotRegex(cap2, r"(?m)^\|")
        self.assertIn("Presidência da República Casa Civil", cap2)

    def test_frontmatter(self):
        v = frontmatter(self.saida["lei-12345/index.md"])
        self.assertEqual(v["id"], "lei-12345")
        self.assertEqual((v["orgao"], v["tipo"], v["numero"], v["data"]), ("federal", "lei", "12345", "1976-12-07"))
        self.assertEqual(v["publicacao_dou"], "1976-12-09")
        self.assertEqual(v["ementa"], "Dispõe sobre o teste da conversão.")
        self.assertEqual((v["situacao"], v["versao_texto"], v["vigente_ate_ato"]), ("vigente", "consolidado", ""))
        self.assertEqual((v["aguarda_consolidado_oficial"], v["historico_parcial"]), ("false", "true"))
        self.assertEqual(v["fonte_original"], "https://www.planalto.gov.br/ccivil_03/leis/l12345.htm")
        self.assertEqual(v["fonte_consolidada"], "https://www.planalto.gov.br/ccivil_03/leis/l12345compilada.htm")
        self.assertEqual((v["baixado_em"], v["verificado_em"]), ("2026-10-28", "2026-10-28"))
        self.assertRegex(v["sha256_fonte"], r"^[0-9a-f]{64}$")
        self.assertTrue(v["incerteza"])
        self.assertEqual(v["nivel_verificacao"], "compilado-planalto")
        self.assertEqual(list(v)[-2:], ["incerteza", "nivel_verificacao"])

    def test_sha256_e_do_arquivo_baixado(self):
        import hashlib
        self.assertEqual(frontmatter(self.saida["lei-12345/index.md"])["sha256_fonte"], hashlib.sha256(self.html).hexdigest())

    def test_passa_no_teste_de_conversao(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            index = os.path.join(tmp, "lei-12345", "index.md")
            self.assertEqual(diferencas_lei(texto_da_norma(index), self.html), [])

    def test_valida(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            self.assertEqual(validar_norma(os.path.join(tmp, "lei-12345", "index.md")), [])


class TestMontarLeiSimples(unittest.TestCase):
    def test_sem_partes_gera_um_arquivo_com_corpo_limpo(self):
        item = dict(ITEM_PARTES)
        del item["partes"]
        saida = leis.montar_lei(item, ler_fixture("lei-planalto-duas-partes.html"))
        self.assertEqual(list(saida), ["lei-12345.md"])
        texto = saida["lei-12345.md"]
        corpo = texto.split("\n---\n", 1)[1].lstrip("\n")
        self.assertTrue(corpo.startswith("LEI Nº 12.345, DE 7 DE DEZEMBRO DE 1976.\n\nDispõe sobre o teste da conversão.\n\nO PRESIDENTE"), corpo[:200])
        self.assertNotIn("Presidência da República\n", corpo.split("## Art.")[0])
        self.assertNotIn("Mensagem de veto", corpo)
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, saida)
            caminho = os.path.join(tmp, "lei-12345.md")
            self.assertEqual(validar_norma(caminho), [])
            self.assertEqual(diferencas_lei(texto_da_norma(caminho), ler_fixture("lei-planalto-duas-partes.html")), [])

    def test_ementa_em_paragrafo_sem_tabela(self):
        html = ("<html><body><p>LEI Nº 13.986, DE 7 DE ABRIL DE 2020</p><p>Institui o Fundo.</p><p>Não remover</p>"
                "<p>Texto atualizado Texto compilado</p><p>O PRESIDENTE DA REPÚBLICA Faço saber:</p>"
                "<p>Art. 1º A.</p><p>Este texto não substitui o publicado no DOU de 7.4.2020 - Edição extra</p></body></html>")
        item = {"id": "lei-13986", "numero": 13986, "data": "2020-04-07", "planalto": ["ccivil_03/leis/l13986.htm"]}
        saida = leis.montar_lei(item, html.encode("utf-8"))
        v = frontmatter(saida["lei-13986.md"])
        self.assertEqual(v["ementa"], "Institui o Fundo.")
        self.assertEqual(v["publicacao_dou"], "2020-04-07")
        corpo = saida["lei-13986.md"].split("\n---\n", 1)[1]
        self.assertNotIn("Texto compilado", corpo)

    def test_sem_publicado_no_dou_usa_a_data_da_lei_e_diz_na_incerteza(self):
        html = ("<html><body><p>LEI Nº 1, DE 7 DE ABRIL DE 2020</p><p>Institui.</p>"
                "<p>O PRESIDENTE DA REPÚBLICA Faço saber:</p><p>Art. 1º A.</p></body></html>")
        item = {"id": "lei-1", "numero": 1, "data": "2020-04-07", "planalto": ["ccivil_03/leis/l1.htm"]}
        v = frontmatter(leis.montar_lei(item, html.encode("utf-8"))["lei-00001.md"])
        self.assertEqual(v["publicacao_dou"], "2020-04-07")
        self.assertIn("publicação no DOU", v["incerteza"])

    def test_publicada_no_dou_com_ano_de_dois_digitos(self):
        # Lei 4.728: "Este texto não substitui o publicada no D.O.U. de 16.7.65 e retificado em 16.8.1965"
        html = ("<html><body><p>LEI Nº 4.728, DE 14 DE JULHO DE 1965</p><p>Disciplina o mercado de capitais.</p>"
                "<p>O PRESIDENTE DA REPÚBLICA Faço saber:</p><p>Art. 1º A.</p>"
                "<p>Este texto não substitui o publicada no D.O.U. de 16.7.65 e retificado em 16.8.1965</p></body></html>")
        item = {"id": "lei-4728", "numero": 4728, "data": "1965-07-14", "planalto": ["ccivil_03/leis/l4728.htm"]}
        v = frontmatter(leis.montar_lei(item, html.encode("utf-8"))["lei-04728.md"])
        self.assertEqual(v["publicacao_dou"], "1965-07-16")
        self.assertNotIn("publicação no DOU", v["incerteza"])

    def test_pagina_sem_notas_de_alteracao_e_registrada_na_incerteza(self):
        item = {"id": "lei-14430", "numero": 14430, "data": "2022-08-03", "planalto": ["ccivil_03/lei/l14430.htm"]}
        html = ("<html><body><p>LEI Nº 14.430, DE 3 DE AGOSTO DE 2022</p><p>Dispõe sobre a securitização.</p>"
                "<p>O PRESIDENTE DA REPÚBLICA Faço saber:</p><p>Art. 1º A.</p>"
                "<p>Este texto não substitui o publicado no DOU de 4.8.2022</p></body></html>")
        v = frontmatter(leis.montar_lei(item, html.encode("utf-8"))["lei-14430.md"])
        self.assertIn("sem notas de alteração", v["incerteza"])
        self.assertEqual(v["fonte_original"], v["fonte_consolidada"])

    def test_url_de_compilado_que_nao_respondeu_e_registrada(self):
        item = dict(ITEM_PARTES, url="https://www.planalto.gov.br/ccivil_03/leis/l12345.htm")
        del item["partes"]
        v = frontmatter(leis.montar_lei(item, ler_fixture("lei-planalto-duas-partes.html"))["lei-12345.md"])
        self.assertEqual(v["fonte_consolidada"], "https://www.planalto.gov.br/ccivil_03/leis/l12345.htm")
        self.assertIn("URL de compilado", v["incerteza"])


class TestMontarLeiRecorte(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = ler_fixture("lei-planalto-codigo-civil.html")
        cls.saida = leis.montar_lei(ITEM_CC, cls.html)

    def test_so_os_artigos_do_recorte(self):
        self.assertEqual(list(self.saida), ["lei-10406.md"])
        texto = self.saida["lei-10406.md"]
        self.assertEqual(re.findall(r"^## Art\. .+$", texto, flags=re.M),
                         ["## Art. 1.368-C", "## Art. 1.368-D", "## Art. 1.368-E", "## Art. 1.368-F"])

    def test_corta_antes_do_artigo_seguinte_e_sem_titulo_do_capitulo_seguinte(self):
        corpo = self.saida["lei-10406.md"].split("\n---\n", 1)[1]
        self.assertNotIn("1.369", corpo)
        self.assertNotIn("Superfície", corpo)
        self.assertNotIn("1.368-B", corpo)
        self.assertNotIn("Este texto não substitui", corpo)

    def test_corpo_abre_com_o_titulo_do_capitulo(self):
        corpo = self.saida["lei-10406.md"].split("\n---\n", 1)[1].lstrip("\n")
        self.assertTrue(corpo.startswith("CAPÍTULO X\n\nDO FUNDO DE INVESTIMENTO"), corpo[:120])

    def test_frontmatter_descreve_o_recorte(self):
        v = frontmatter(self.saida["lei-10406.md"])
        self.assertEqual(v["ementa"], "Institui o Código Civil.")
        self.assertIn("1.368-C a 1.368-F", v["incerteza"])
        self.assertEqual(v["publicacao_dou"], "2002-01-11")

    def test_passa_no_teste_de_conversao(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            caminho = os.path.join(tmp, "lei-10406.md")
            self.assertEqual(diferencas_lei(texto_da_norma(caminho), self.html), [])

    def test_valida(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            self.assertEqual(validar_norma(os.path.join(tmp, "lei-10406.md")), [])

    def test_recorte_ausente_no_html_e_erro(self):
        with self.assertRaises(ValueError):
            leis.montar_lei(ITEM_CC, "<html><body><p>Art. 1º A.</p></body></html>".encode("utf-8"))


def corpo_de(conteudo):
    return conteudo.split("\n---\n", 1)[1].lstrip("\n")


class TestMontarDecretoELeiComplementar(unittest.TestCase):
    DECRETO = {"id": "decreto-12345", "numero": 12345, "tipo": "decreto", "data": "2024-03-26",
               "planalto": ["ccivil_03/_ato2023-2026/2024/decreto/d12345.htm"]}
    LCP = {"id": "lcp-123", "numero": 123, "tipo": "lei-complementar", "data": "2001-01-10",
           "planalto": ["ccivil_03/leis/lcp/lcp123.htm"]}

    def test_decreto_vira_decreto_nnnnn_com_frontmatter_de_decreto(self):
        saida = leis.montar_lei(self.DECRETO, ler_fixture("leis-planalto-decreto.html"))
        self.assertEqual(list(saida), ["decreto-12345.md"])
        v = frontmatter(saida["decreto-12345.md"])
        self.assertEqual((v["id"], v["orgao"], v["tipo"], v["numero"]), ("decreto-12345", "federal", "decreto", "12345"))
        self.assertEqual(v["ementa"], "Regulamenta o teste de decreto.")
        self.assertEqual(v["publicacao_dou"], "2024-03-27")
        self.assertEqual((v["vigente_ate_ato"], v["aguarda_consolidado_oficial"], v["historico_parcial"]), ("", "false", "true"))
        self.assertEqual(v["nivel_verificacao"], "compilado-planalto")
        self.assertEqual(list(v)[-1], "nivel_verificacao")

    def test_decreto_corpo_com_titulo_ementa_preambulo_e_decreta(self):
        corpo = corpo_de(leis.montar_lei(self.DECRETO, ler_fixture("leis-planalto-decreto.html"))["decreto-12345.md"])
        self.assertTrue(corpo.startswith("DECRETO Nº 12.345, DE 26 DE MARÇO DE 2024\n\nRegulamenta o teste de decreto.\n\n"
                                         "O PRESIDENTE DA REPÚBLICA, no uso da atribuição"), corpo[:200])
        self.assertIn("\nDECRETA:\n", corpo)
        self.assertEqual(re.findall(r"^## Art\. .+$", corpo, flags=re.M), ["## Art. 1º", "## Art. 2º", "## Art. 3º"])
        self.assertNotIn("Secretaria Especial", corpo)

    def test_lei_complementar_vira_lcp_nnn(self):
        saida = leis.montar_lei(self.LCP, ler_fixture("leis-planalto-lcp.html"))
        self.assertEqual(list(saida), ["lcp-123.md"])
        v = frontmatter(saida["lcp-123.md"])
        self.assertEqual((v["id"], v["tipo"], v["numero"]), ("lcp-123", "lei-complementar", "123"))
        self.assertEqual(v["ementa"], "Dispõe sobre o teste de lei complementar.")
        self.assertEqual(v["publicacao_dou"], "2001-01-11")
        self.assertTrue(corpo_de(saida["lcp-123.md"]).startswith(
            "LEI COMPLEMENTAR Nº 123, DE 10 DE JANEIRO DE 2001.\n\nDispõe sobre o teste de lei complementar.\n\nO PRESIDENTE"))

    def test_titulo_de_outro_tipo_e_erro(self):
        with self.assertRaises(ValueError) as erro:
            leis.montar_lei(self.DECRETO, ler_fixture("leis-planalto-lcp.html"))
        self.assertIn("DECRETO", str(erro.exception))

    def test_tipo_desconhecido_e_erro(self):
        with self.assertRaises(ValueError):
            leis.montar_lei(dict(self.DECRETO, tipo="portaria"), ler_fixture("leis-planalto-decreto.html"))

    def test_passam_no_teste_de_conversao(self):
        for item, fixture in ((self.DECRETO, "leis-planalto-decreto.html"), (self.LCP, "leis-planalto-lcp.html")):
            html = ler_fixture(fixture)
            with tempfile.TemporaryDirectory() as tmp:
                saida = leis.montar_lei(item, html)
                gravar(tmp, saida)
                caminho = os.path.join(tmp, list(saida)[0])
                self.assertEqual(diferencas_lei(texto_da_norma(caminho), html), [], fixture)
                self.assertEqual(validar_norma(caminho), [], fixture)


class TestMontarLeiDeConversao(unittest.TestCase):
    ITEM = {"id": "lei-12346", "numero": 12346, "data": "2001-02-14", "planalto": ["ccivil_03/leis/leis_2001/l12346.htm"]}

    def setUp(self):
        self.html = ler_fixture("leis-planalto-conversao-mp.html")
        self.saida = leis.montar_lei(self.ITEM, self.html)

    def test_tipo_padrao_e_lei(self):
        self.assertEqual(list(self.saida), ["lei-12346.md"])
        self.assertEqual(frontmatter(self.saida["lei-12346.md"])["tipo"], "lei")

    def test_preambulo_faco_saber_e_linha_de_conversao_antes_da_ementa(self):
        corpo = corpo_de(self.saida["lei-12346.md"])
        self.assertTrue(corpo.startswith(
            "LEI Nº 12.346, DE 14 DE FEVEREIRO DE 2001.\n\nConversão da MPv nº 2.110-40, de 2001\n\n"
            "Dispõe sobre os contratos de investimento coletivo, e dá outras providências.\n\n"
            "Faço saber que o PRESIDENTE DA REPÚBLICA adotou a Medida Provisória"), corpo[:300])

    def test_ementa_sem_a_linha_de_conversao_e_dou_com_pontos(self):
        v = frontmatter(self.saida["lei-12346.md"])
        self.assertEqual(v["ementa"], "Dispõe sobre os contratos de investimento coletivo, e dá outras providências.")
        self.assertEqual(v["publicacao_dou"], "2001-02-16")

    def test_passa_no_teste_de_conversao(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            caminho = os.path.join(tmp, "lei-12346.md")
            self.assertEqual(diferencas_lei(texto_da_norma(caminho), self.html), [])
            self.assertEqual(validar_norma(caminho), [])

    def test_conversao_com_preambulo_comum_fica_fora_do_corpo_como_nas_leis_atuais(self):
        # Lei 12.431: a coluna de links do Planalto traz "Conversão da Medida Provisória ..."; a lei
        # sancionada pelo Presidente não leva a linha (o texto das 12 leis atuais não muda).
        html = ("<html><body><p>LEI Nº 1, DE 24 DE JUNHO DE 2011.</p><table><tr><td>Conversão da Medida Provisória "
                "nº 517, de 2010 Mensagem de veto</td><td>Dispõe sobre debêntures.</td></tr></table>"
                "<p>A PRESIDENTA DA REPÚBLICA Faço saber:</p><p>Art. 1º A.</p></body></html>")
        item = {"id": "lei-1", "numero": 1, "data": "2011-06-24", "planalto": ["ccivil_03/l1.htm"]}
        corpo = corpo_de(leis.montar_lei(item, html.encode("utf-8"))["lei-00001.md"])
        self.assertTrue(corpo.startswith("LEI Nº 1, DE 24 DE JUNHO DE 2011.\n\nDispõe sobre debêntures.\n\nA PRESIDENTA"), corpo)


class TestRecorteDeArtigoUnico(unittest.TestCase):
    HTML = ("<html><body><p>LEI Nº 2, DE 1 DE JANEIRO DE 2004.</p><p>Altera a tributação.</p>"
            "<p>O PRESIDENTE DA REPÚBLICA Faço saber:</p><p>Art. 1º Primeiro.</p><p>Art. 2º Segundo.</p>"
            "<p>Art. 3º Ficam isentos:</p><p>I - na fonte, os rendimentos; (Redação dada pela Lei nº 9, de 2005)</p>"
            "<p>Parágrafo único. Fecha o terceiro.</p><p>CAPÍTULO II</p><p>Art. 4º Quarto.</p>"
            "<p>Este texto não substitui o publicado no DOU de 2.1.2004</p></body></html>").encode("utf-8")
    ITEM = {"id": "lei-2", "numero": 2, "data": "2004-01-01", "recorte": ["3º", "3º"], "planalto": ["ccivil_03/l2.htm"]}

    def setUp(self):
        self.saida = leis.montar_lei(self.ITEM, self.HTML)

    def test_so_o_artigo_e_o_texto_dele(self):
        texto = self.saida["lei-00002.md"]
        self.assertEqual(re.findall(r"^## Art\. .+$", texto, flags=re.M), ["## Art. 3º"])
        corpo = corpo_de(texto)
        self.assertTrue(corpo.startswith("## Art. 3º\n\nFicam isentos:"), corpo)
        self.assertTrue(corpo.rstrip().endswith("Parágrafo único. Fecha o terceiro."), corpo)
        self.assertNotIn("CAPÍTULO II", corpo)

    def test_incerteza_descreve_o_artigo_unico(self):
        self.assertIn("Recorte: somente o art. 3º;", frontmatter(self.saida["lei-00002.md"])["incerteza"])

    def test_passa_no_teste_de_conversao(self):
        with tempfile.TemporaryDirectory() as tmp:
            gravar(tmp, self.saida)
            caminho = os.path.join(tmp, "lei-00002.md")
            self.assertEqual(diferencas_lei(texto_da_norma(caminho), self.HTML), [])
            self.assertEqual(validar_norma(caminho), [])


class TestEscreverLeis(unittest.TestCase):
    def test_le_o_json_o_relatorio_e_o_html_e_grava_em_leis(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = ler_fixture("lei-planalto-duas-partes.html")
            gravar(os.path.join(tmp, "dados", "fontes"), {"lei-12345.html": ""})
            with open(os.path.join(tmp, "dados", "fontes", "lei-12345.html"), "wb") as f:
                f.write(html)
            relatorio = {"lei-12345": {"ok": True, "url": "https://www.planalto.gov.br/ccivil_03/leis/l12345.htm",
                                       "arquivo": "dados/fontes/lei-12345.html"}}
            with open(os.path.join(tmp, "dados", "fontes", "relatorio.json"), "w", encoding="utf-8") as f:
                json.dump(relatorio, f)
            itens = [dict(ITEM_PARTES)]
            saida = os.path.join(tmp, "leis")
            gravados = leis.escrever_leis(itens, os.path.join(tmp, "dados", "fontes"), saida)
            self.assertEqual(sorted(gravados), ["lei-12345/cap-01.md", "lei-12345/cap-02.md", "lei-12345/index.md"])
            self.assertTrue(os.path.isfile(os.path.join(saida, "lei-12345", "index.md")))
            with open(os.path.join(saida, "lei-12345", "index.md"), encoding="utf-8") as f:
                v = frontmatter(f.read())
            self.assertEqual(v["fonte_consolidada"], "https://www.planalto.gov.br/ccivil_03/leis/l12345.htm")
            self.assertIn("URL de compilado", v["incerteza"])

    def test_html_ausente_e_erro(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                leis.escrever_leis([dict(ITEM_PARTES)], tmp, os.path.join(tmp, "leis"))


class TestBaixarLeis(unittest.TestCase):
    """baixar.baixar_leis sem rede: com o arquivo no cache, `baixar` não abre conexão."""

    def test_nome_por_tipo_e_so_novas_preserva_a_url_registrada(self):
        import baixar
        from unittest import mock
        itens = [
            {"id": "decreto-11964", "planalto": ["ccivil_03/d11964compilado.htm", "ccivil_03/d11964.htm"]},
            {"id": "lcp-105", "planalto": ["ccivil_03/leis/lcp/lcp105.htm"]},
            {"id": "lei-9514", "planalto": ["ccivil_03/leis/l9514compilado.htm", "ccivil_03/leis/l9514.htm"]},
        ]
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(baixar, "FONTES", tmp):
            for nome in ("decreto-11964.html", "lcp-105.html", "lei-09514.html"):
                with open(os.path.join(tmp, nome), "w") as f:
                    f.write("x")
            anterior = {"ok": True, "url": baixar.PLANALTO + "ccivil_03/leis/l9514.htm", "arquivo": "dados/fontes/lei-09514.html"}
            rel = {"lei-9514": dict(anterior)}
            baixar.baixar_leis(itens, rel, so_novas=True)
        self.assertEqual(rel["lei-9514"], anterior)
        self.assertTrue(rel["decreto-11964"]["ok"])
        self.assertTrue(rel["decreto-11964"]["arquivo"].endswith("decreto-11964.html"))
        self.assertTrue(rel["lcp-105"]["arquivo"].endswith("lcp-105.html"))


class TestGravacaoSemControle(unittest.TestCase):
    """Fase 4: a gravação das leis e a saída do converter.py não levam caractere de controle."""

    def test_escrever_leis_limpa_controle_e_preserva_tab(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            fontes, saida = os.path.join(d, "fontes"), os.path.join(d, "leis")
            os.makedirs(fontes)
            with open(os.path.join(fontes, "relatorio.json"), "w", encoding="utf-8") as f:
                json.dump({"lei-1": {"ok": True, "arquivo": "lei-1.html", "url": "https://x/l1.htm"}}, f)
            with open(os.path.join(fontes, "lei-1.html"), "wb") as f:
                f.write(b"<html></html>")
            conteudo = {"lei-00001.md": "O\x00cios na sexta\x02feira\x1f.\n\tcom tab\n"}
            with mock.patch.object(leis, "montar_lei", return_value=conteudo):
                self.assertEqual(leis.escrever_leis([{"id": "lei-1"}], fontes, saida), ["lei-00001.md"])
            with open(os.path.join(saida, "lei-00001.md"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "O\ufffdcios na sexta-feira.\n\tcom tab\n")

    def test_saida_do_converter_sem_controle(self):
        import contextlib
        import io
        import converter
        with tempfile.TemporaryDirectory() as d:
            html = os.path.join(d, "l.html")
            with open(html, "w", encoding="utf-8") as f:
                f.write("<html><body><p>Art. 1º O\x00cios na sexta\x02feira.</p></body></html>")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(converter.main(["converter.py", html, "--planalto"]), 0)
        self.assertIn("O\ufffdcios na sexta-feira", out.getvalue())
        self.assertNotIn("\x00", out.getvalue())


if __name__ == "__main__":
    unittest.main()
