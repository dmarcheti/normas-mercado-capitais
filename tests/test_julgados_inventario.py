"""Testes do inventário de julgados, com listagens sintéticas no formato das páginas da CVM
(nomes fictícios; sem rede)."""
import io
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_inventario as ji  # noqa: E402


def artigo(url, titulo, data, tipo="Ordinária", desc="Texto."):
    return ('<article> <h3><a href="%s" title="%s"> %s</a></h3> <div class="contentDesc"> %s '
            '</div> <div class="infoItem"> <p><b>Data:</b> %s</p> <p><b>Tipo:</b> %s</p> </div> '
            '</article>' % (url, titulo, titulo, desc, data, tipo))


COLEGIADO = "".join([
    artigo("/decisoes/2018/20180814_R1/20180814_D1109.html",
           "PROPOSTA DE TERMO DE COMPROMISSO – FULANO EXEMPLO – PROC. SEI 19957.011547/2017-16",
           "14/08/2018"),
    artigo("/decisoes/2018/20180814_R1/20180814_D1110.html",
           "RECURSO CONTRA MULTA COMINATÓRIA (SEP) – EMPRESA EXEMPLO S.A. – PROC. SEI "
           "19957.000001/2018-11", "14/08/2018"),
    artigo("/decisoes/2018/20180814_R2/20180814_D1110.html",
           "CONSULTA DA SIN – FUNDO EXEMPLO – PROC. SEI 19957.000002/2018-22", "14/08/2018",
           tipo="Extraordinária"),
    artigo("/decisoes/2019/20190219_R1/20190219_D0007.html",
           "PROPOSTA DE TERMO DE COMPROMISSO – BELTRANO EXEMPLO – PROC. SEI 19957.011587/2017-68",
           "19/02/2019"),
    artigo("/decisoes/2002/20020416_R1/20020416_D09.html",
           "PEDIDO DE RECONSIDERAÇÃO – CIA EXEMPLO – PROC. RJ2001/1111", "16/04/2002"),
])
PAS = "".join([
    artigo("/sancionadores/sancionador/2025/20250527_PAS_19957011607202420.html",
           "19957.011607/2024- 20", "27/05/2025", tipo="Processos Sancionadores Julgados",
           desc="Ementa: Apurar suposto descumprimento. Multa."),
    artigo("/sancionadores/sancionador/2009/20090303_RJ20074665.html",
           "Processo Sancionador RJ2007/4665", "03/03/2009"),
    artigo("/sancionadores/sancionador/2013/20130205_RJ20074665.html",
           "Processo Sancionador RJ2007/4665", "05/02/2013"),
    artigo("/sancionadores/sancionador/2013/20130205_RJ20074665.html",
           "Processo Sancionador RJ2007/4665", "05/02/2013"),
])
TC_ACEITOS = """<table><tr> <td>Número do processo</td> <td>Data de aprovação</td>
<td>Data de assinatura</td> <td>Publicação</td> <td>Compromitentes</td>
<td>Decisão do Colegiado e Parecer do CTC</td> <td>Data de arquivamento</td> </tr>
<tr> <td><a href="https://conteudo.cvm.gov.br/decisoes/2018/20180814_R1/20180814_D1109.html">
19957.011547/2017-16</a></td> <td> 14/08/2018 </td> <td> 25/10/2018 </td> <td> 08/11/2018 </td>
<td> <p>Fulano Exemplo</p> </td> <td> <a href="https://conteudo.cvm.gov.br/decisoes/2018/20180814_R1/20180814_D1109.html">Decisão/Parecer</a> </td> <td> 24/03/2026 </td> </tr>
<tr> <td><a href="/export/sites/cvm/termos_compromisso/anexos/0001/19980603_TC_RJ96-4025.pdf">RJ96/4025 - BANCO EXEMPLO</a></td>
<td> 03/06/1998 </td> <td> 31/08/1998 </td> <td> 14/10/1998 </td> <td> <p>Banco Exemplo</p> </td>
<td> <a href="/decisoes/2002/20020416_R1/20020416_D09.html"></a> </td> <td> </td> </tr>
<tr> <td><a href="/export/sites/cvm/termos_compromisso/anexos/0001/19980603_TC_RJ96-4025_2.pdf">RJ96/4025 - OUTRO</a></td>
<td> 03/06/1998 </td> <td> 31/08/1998 </td> <td> 14/10/1998 </td> <td> <p>Outro</p> </td>
<td> <a href="/decisoes/2002/20020416_R1/20020416_D09.html"></a> </td> <td> </td> </tr>
</table>"""
TC_REJ = """<table><tr><td>Número do processo</td><td>Data de rejeição</td><td>Proponentes</td>
<td>Decisão</td></tr>
<tr> <td> 19957.011587/2017-68 </td> <td> 19/02/2019 </td> <td> <p>Beltrano</p> </td>
<td> <a href="/decisoes/2019/20190219_R1.html">Decisão/Parecer</a> </td> </tr>
<tr> <td> 19957.000999/2016-10 </td> <td> 19/02/2019 </td> <td> <p>Sicrano</p> </td> </tr>
</table>"""
ANTIGAS = ('<a href="/export/sites/cvm/publicacao/decisoes_antigas/anexos/decisoes-1978.pdf">'
           '1978</a> <a href="/export/sites/cvm/publicacao/decisoes_antigas/anexos/'
           'decisoes-1979.pdf">1979</a>')


def planilha_xlsx(linhas):
    """xlsx mínimo com as linhas dadas (lista de dicts coluna -> valor), strings inline."""
    rows = []
    for i, d in enumerate(linhas, 1):
        cs = "".join('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>' % (k, i, v)
                     if not str(v).isdigit() else '<c r="%s%d"><v>%s</v></c>' % (k, i, v)
                     for k, v in d.items())
        rows.append('<row r="%d">%s</row>' % (i, cs))
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetData>%s</sheetData></worksheet>' % "".join(rows))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


PLANILHA = planilha_xlsx([
    {"A": "Processos com julgamento no período"},
    {"C": "Processo SEI", "D": "Tipo", "E": "Rito", "F": "Sup.", "G": "Relator", "H": "Data"},
    {"B": "1", "C": "19957.011607/2024-20", "D": "Termo de Acusação", "E": "Simplificado",
     "F": "SNC", "G": "DIRETOR EXEMPLO", "H": "45804"},
    {"B": "2", "C": "19957.005011/2020-67", "D": "Termo de Acusação", "E": "Ordinário",
     "F": "SRE", "G": "DIRETORA EXEMPLO", "H": "44607"},
])
CSV = ("NUP;Objeto;Ementa;Data_Abertura;Componente_Organizacional_Instrucao;Fase_Atual;"
       "Subfase_Atual;Local_Atual;Data_Ultima_Movimentacao\n"
       "19957011607202420;Apurar;;2024-01-01;SNC;Recurso CRSFN;Aguardando;GCP;2025-06-01\n"
       "19957005011202067;Termo de Acusação (rito ordinário);;2020-01-01;SRE;Julgamento;"
       "Fim (Rito Ordinário);GCP;2022-03-01\n").encode("latin-1")


class ParsersTest(unittest.TestCase):
    def test_artigos(self):
        it = ji.ler_artigos(PAS)[0]
        self.assertEqual(it["data"], "2025-05-27")
        self.assertEqual(it["titulo"], "19957.011607/2024- 20")
        self.assertTrue(it["desc"].startswith("Ementa:"))
        self.assertEqual(ji.ler_artigos(COLEGIADO)[2]["reuniao"], "Extraordinária")

    def test_tc_aceitos_sem_compromitentes(self):
        rs = ji.ler_tc_aceitos(TC_ACEITOS)
        self.assertEqual(len(rs), 3)
        self.assertEqual(rs[0]["proc"], "19957-011547-2017-16")
        self.assertEqual(rs[0]["termo_urls"], [])
        self.assertEqual(rs[1]["processo"], "RJ96/4025")
        self.assertEqual(rs[1]["termo_urls"][0][-9:], "-4025.pdf")
        for r in rs:
            self.assertNotIn("Fulano", repr(r))
            self.assertNotIn("Banco Exemplo", repr(r))

    def test_tc_rejeitados(self):
        rs = ji.ler_tc_rejeitados(TC_REJ)
        self.assertEqual([r["data"] for r in rs], ["2019-02-19", "2019-02-19"])
        self.assertEqual(rs[1]["decisao_urls"], [])

    def test_antigas(self):
        self.assertEqual([a for a, _ in ji.ler_antigas(ANTIGAS)], [1978, 1979])

    def test_planilha(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.xlsx")
            with open(p, "wb") as f:
                f.write(PLANILHA)
            rs = ji.ler_planilha(p)
        self.assertEqual(len(rs), 2)
        self.assertEqual(rs[0]["nup"], "19957-011607-2024-20")
        self.assertEqual(rs[0]["rito"], "simplificado")
        self.assertEqual(rs[1]["data"], "2022-02-15")

    def test_dados_abertos(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.csv")
            with open(p, "wb") as f:
                f.write(CSV)
            ab = ji.ler_dados_abertos(p)
        self.assertTrue(ab["19957-011607-2024-20"]["crsfn"])
        self.assertEqual(ab["19957-005011-2020-67"]["rito"], "ordinario")

    def test_classificar(self):
        self.assertEqual(ji.classificar("PROPOSTA DE TERMO DE COMPROMISSO – X – PROC. 1"),
                         "tc_proposta")
        self.assertEqual(ji.classificar("RECURSO CONTRA MULTA COMINATÓRIA – X"),
                         "recurso_multa_taxa_mre_fg")
        self.assertEqual(ji.classificar("PEDIDO DE RECONSIDERAÇÃO – X"), "pedido_reconsideracao")
        self.assertEqual(ji.classificar("PEDIDO DE DISPENSA DE REQUISITOS – X"), "dispensa")
        self.assertEqual(ji.classificar("ASSUNTO QUALQUER"), "outros")

    def test_arquivos_de_listagem(self):
        arqs = ji.arquivos_de_listagem()
        self.assertEqual(len([a for a in arqs if a[0].startswith("colegiado/")]), 50)
        self.assertIn("dataInicio=01/07/2002&dataFim=31/12/2002", arqs[2][2])
        self.assertEqual(sum(1 for a in arqs if a[1] == "POST"), 2)


class MontarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "p.xlsx")
            with open(p, "wb") as f:
                f.write(PLANILHA)
            planilha = ji.ler_planilha(p)
            c = os.path.join(d, "c.csv")
            with open(c, "wb") as f:
                f.write(CSV)
            abertos = ji.ler_dados_abertos(c)
        cls.regs, cls.resumo = ji.montar(
            ji.ler_artigos(PAS), ji.ler_artigos(COLEGIADO), ji.ler_tc_aceitos(TC_ACEITOS),
            ji.ler_tc_rejeitados(TC_REJ), ji.ler_antigas(ANTIGAS), planilha, abertos)
        cls.por_id = {r["id"]: r for r in cls.regs}

    def test_ids_unicos_e_colisao_de_reuniao(self):
        self.assertEqual(len(self.por_id), len(self.regs))
        self.assertIn("cvm-col-20180814-d1110", self.por_id)
        self.assertIn("cvm-col-20180814-d1110-r2", self.por_id)

    def test_tc_casado_por_link_e_por_data_processo(self):
        r = self.por_id["cvm-col-20180814-d1109"]
        self.assertEqual((r["tipo"], r["resultado"], r["classe"]), ("termo-compromisso", "aceito", ""))
        r2 = self.por_id["cvm-col-20190219-d0007"]
        self.assertEqual(r2["resultado"], "rejeitado")
        self.assertEqual(self.resumo["tc_rejeitado_casado_data-processo"], 1)

    def test_link_suspeito_vira_tc_avulso_com_termos_juntados(self):
        r = self.por_id["cvm-tc-rj1996-4025-19980603"]
        self.assertEqual(r["tipo"], "termo-compromisso")
        self.assertEqual(len(r["termo_urls"]), 2)
        self.assertTrue(any("suspeito" in x for x in r["incerteza"]))
        self.assertEqual(r["plugin"], "julgados-sancionadores")
        # o item de 2002 não vira TC
        self.assertEqual(self.por_id["cvm-col-20020416-d09"]["tipo"], "decisao-colegiado")

    def test_data_da_listagem_contra_url_normalizada(self):
        self.assertFalse([x for r in self.regs for x in r["incerteza"] if "difere da URL" in x])
        col = ji.ler_artigos(artigo("/decisoes/2020/20200915_R1/20200915_D1913.html", "CONSULTA",
                                    "16/09/2020") +
                             artigo("/decisoes/2021/20210105_R1/20210105_D0001.html", "CONSULTA",
                                    ""))
        regs, _ = ji.montar([], col, [], [], [], {}, {})
        por = {r["id"]: r for r in regs}
        self.assertIn("data da listagem 2020-09-16 difere da URL 2020-09-15",
                      por["cvm-col-20200915-d1913"]["incerteza"])
        self.assertEqual(por["cvm-col-20210105-d0001"]["data"], "2021-01-05")

    def test_tc_rejeitado_sem_link_fica_pendente(self):
        r = self.por_id["cvm-tc-19957-000999-2016-10-20190219"]
        self.assertTrue(r["fonte_pendente"])

    def test_pas_duplicado_e_sufixo(self):
        self.assertEqual(self.resumo["pas_url_repetida"], 1)
        self.assertEqual(self.por_id["cvm-pas-rj2007-4665"]["data"], "2009-03-03")
        self.assertEqual(self.por_id["cvm-pas-rj2007-4665-2"]["data"], "2013-02-05")

    def test_planilha_e_dados_abertos(self):
        r = self.por_id["cvm-pas-19957-011607-2024-20"]
        self.assertEqual((r["rito"], r["relator"]), ("simplificado", "DIRETOR EXEMPLO"))
        self.assertIn("recurso ao CRSFN (dados abertos)", r["incerteza"])
        p = self.por_id["cvm-pas-19957-005011-2020-67"]
        self.assertTrue(p["fonte_pendente"])
        self.assertEqual((p["url"], p["data"], p["rito"]), ("", "2022-02-15", "ordinario"))
        self.assertEqual(self.resumo["pas_fonte_pendente"], 1)

    def test_classe_e_plugin(self):
        r = self.por_id["cvm-col-20180814-d1110"]
        self.assertEqual((r["classe"], r["plugin"]),
                         ("multa-cominatoria", "julgados-colegiado-2016-2026"))
        self.assertEqual(self.por_id["cvm-dec-1978"]["plugin"], "julgados-colegiado-2002-2008")

    def test_enxuto_sem_titulo(self):
        e = ji.enxuto(self.regs)
        self.assertEqual(set(e[0]), set(ji.ENXUTO))
        self.assertNotIn("EXEMPLO S.A.", repr(e))
        self.assertNotIn("FULANO", repr(e))

    def test_contagens(self):
        c = ji.contagens(self.regs)
        self.assertEqual(c["decisao-antiga"], {"ate-2009": 2, "total": 2})


class BaixarListagensTest(unittest.TestCase):
    def test_retoma_e_usa_post(self):
        chamadas = []

        class Falso:
            def get(self, url):
                chamadas.append(("GET", url))
                return b"x", {}, url

            def post(self, url, campos):
                chamadas.append(("POST", url))
                return b"y", {}, url

        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "colegiado"))
            with open(os.path.join(d, "pas.html"), "wb") as f:
                f.write(b"ja")
            feitos = ji.baixar_listagens(d, Falso(), log=lambda *a: None)
            self.assertNotIn("pas.html", feitos)
            self.assertEqual(len(feitos), len(ji.arquivos_de_listagem()) - 1)
            self.assertEqual(sum(1 for c in chamadas if c[0] == "POST"), 2)
            self.assertEqual(ji.baixar_listagens(d, Falso(), log=lambda *a: None), [])


if __name__ == "__main__":
    unittest.main()
