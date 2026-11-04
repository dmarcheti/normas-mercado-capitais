import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_comum as jc  # noqa: E402


class PluginTest(unittest.TestCase):
    def test_pas_e_tc_crsfn(self):
        self.assertEqual(jc.plugin_do_julgado("pas", 1999), "julgados-pas")
        for t in ("termo-compromisso", "acordao-crsfn"):
            self.assertEqual(jc.plugin_do_julgado(t, 2025), "julgados-tc-crsfn")
        self.assertEqual(len(jc.PLUGINS_JULGADOS), 5)

    def test_cinco_plugins_com_a_mesma_skill_e_no_marketplace(self):
        import json
        repo = os.path.join(os.path.dirname(__file__), "..")
        skills = []
        for p in jc.PLUGINS_JULGADOS:
            with open(os.path.join(repo, "plugins", p, "skills", "consultar-julgados",
                                   "SKILL.md"), encoding="utf-8") as f:
                skills.append(f.read())
            with open(os.path.join(repo, "plugins", p, ".claude-plugin", "plugin.json"),
                      encoding="utf-8") as f:
                self.assertEqual(json.load(f)["name"], p)
            self.assertIn("`%s`" % p, skills[0].replace("`-2009-2015`", "`julgados-colegiado-"
                                                                     "2009-2015`").replace(
                "`-2016-2026`", "`julgados-colegiado-2016-2026`"))
        self.assertEqual(len(set(skills)), 1, "SKILL.md difere entre os plugins de julgados")
        with open(os.path.join(repo, ".claude-plugin", "marketplace.json"), encoding="utf-8") as f:
            m = {x["name"]: x["source"] for x in json.load(f)["plugins"]}
        for p in jc.PLUGINS_JULGADOS:
            self.assertEqual(m.get(p), "./plugins/" + p)
        self.assertEqual(sorted(x for x in m if x.startswith("julgados-")),
                         sorted(jc.PLUGINS_JULGADOS))

    def test_colegiado_por_periodo(self):
        p = jc.plugin_do_julgado
        self.assertEqual(p("decisao-colegiado", 2002), "julgados-colegiado-2002-2008")
        self.assertEqual(p("decisao-colegiado", 2008), "julgados-colegiado-2002-2008")
        self.assertEqual(p("decisao-antiga", 1978), "julgados-colegiado-2002-2008")
        self.assertEqual(p("decisao-colegiado", 2009), "julgados-colegiado-2009-2015")
        self.assertEqual(p("decisao-colegiado", "2015"), "julgados-colegiado-2009-2015")
        self.assertEqual(p("decisao-colegiado", 2016), "julgados-colegiado-2016-2026")
        self.assertEqual(p("decisao-colegiado", 2026), "julgados-colegiado-2016-2026")

    def test_tipo_invalido(self):
        with self.assertRaises(ValueError):
            jc.plugin_do_julgado("parecer", 2020)


class ProcessoTest(unittest.TestCase):
    def test_nup(self):
        self.assertEqual(jc.normalizar_processo("19957.011607/2024-20"), "19957-011607-2024-20")
        self.assertEqual(jc.normalizar_processo("19957.011607/2024- 20"), "19957-011607-2024-20")
        self.assertEqual(jc.normalizar_processo("PAS CVM nº 19957003190/2019-64"),
                         "19957-003190-2019-64")
        self.assertEqual(jc.normalizar_processo("19957.005740_2020_13"), "19957-005740-2020-13")

    def test_antigos(self):
        for t in ("RJ2015/1234", "RJ-2015-1234", "PAS CVM nº RJ2015/1234",
                  "Processo Sancionador RJ2015/1234"):
            self.assertEqual(jc.normalizar_processo(t), "rj2015-1234", t)
        self.assertEqual(jc.normalizar_processo("SP97/00250"), "sp1997-0250")
        self.assertEqual(jc.normalizar_processo("SP2018-15"), "sp2018-0015")
        self.assertEqual(jc.normalizar_processo("IA 2016/5452"), "ia2016-5452")
        self.assertEqual(jc.normalizar_processo("RJ 01/08489"), "rj2001-8489")

    def test_nup_com_ruido_da_tabela(self):
        self.assertEqual(jc.processos("19957. 000441/2022-54 e 19957. 009424/2021-00"),
                         ["19957-000441-2022-54", "19957-009424-2021-00"])
        self.assertEqual(jc.normalizar_processo("19957.006799-2019-95"), "19957-006799-2019-95")
        self.assertEqual(jc.normalizar_processo("19957.006910/2019-3"), "19957-006910-2019-3")

    def test_celula_nn_aa(self):
        self.assertEqual(jc.normalizar_processo("12/09"), "12-2009")
        self.assertEqual(jc.normalizar_processo("TC 12/09 de algo"), "")

    def test_curto(self):
        self.assertEqual(jc.normalizar_processo("Processo Sancionador 22/1996"), "22-1996")
        self.assertEqual(jc.normalizar_processo("PAS 6/2007"), "06-2007")

    def test_protocolo_antigo_sem_prefixo_nao_casa(self):
        # "AA/NNNN" é protocolo (RJ ou SP, sem dizer qual); os PAS antigos guardam "NN/AAAA"
        # (nº/ano) e não o protocolo: não há como casar com segurança, nem virar "nº/ano"
        for t in ("98/3431", "Processo CVM 97/0873", "96/2035", "99/1946", "00/32"):
            self.assertEqual(jc.normalizar_processo(t), "", t)
        self.assertEqual(jc.normalizar_processo("PAS 08/2000"), "08-2000")
        self.assertEqual(jc.normalizar_processo("RJ98/4966"), "rj1998-4966")

    def test_celula_com_dois_numeros(self):
        cel = "19957.010135/2018-40 (RJ2018/7396)"
        self.assertEqual(jc.processos(cel), ["19957-010135-2018-40", "rj2018-7396"])
        self.assertEqual(jc.normalizar_processo(cel), "19957-010135-2018-40")
        self.assertEqual(jc.nup(cel), "19957-010135-2018-40")
        cel2 = "RJ2012/1131 e RJ2012/4412"
        self.assertEqual(jc.processos(cel2), ["rj2012-1131", "rj2012-4412"])
        self.assertEqual(jc.nup(cel2), "")
        self.assertEqual(jc.processo_publicado(cel2), "RJ2012/1131; RJ2012/4412")
        # dígito verificador truncado na fonte: processo como publicado, sem NUP
        cel3 = "19957.004598/2020-9"
        self.assertEqual(jc.nup(cel3), "")
        self.assertEqual(jc.processo_publicado(cel3), "19957.004598/2020-9")

    def test_publicado_sem_nome(self):
        self.assertEqual(jc.processo_publicado("RJ2016/5039 - FULANO DE TAL e BELTRANO"),
                         "RJ2016/5039")
        self.assertEqual(jc.processo_publicado("Sem número"), "")

    def test_pas_do_titulo(self):
        # título do Colegiado de 2004–2006: "PAS nº/AA" com ano de dois dígitos, ou "TA" + antigo
        t = "APRECIAÇÃO DE PROPOSTA DE TERMO DE COMPROMISSO - PAS %s - FULANO S.A."
        self.assertEqual(jc.pas_do_titulo(t % "06/01"), "06/01")
        self.assertEqual(jc.pas_do_titulo(t % "CVM Nº 27/99"), "27/99")
        self.assertEqual(jc.pas_do_titulo(t % "Nº TARJ2001/7557"), "TARJ2001/7557")
        self.assertEqual(jc.pas_do_titulo(t % "CVM Nº TASP2001/0034"), "TASP2001/0034")
        self.assertEqual(jc.pas_do_titulo("ALTERAÇÃO DA DELIBERAÇÃO 390/01 - TERMO DE COMPROMISSO"), "")


class IdsTest(unittest.TestCase):
    def test_colegiado(self):
        u = "https://conteudo.cvm.gov.br/decisoes/2025/20251202_R1/20251202_D3228.html"
        self.assertEqual(jc.id_colegiado(u), "cvm-col-20251202-d3228")
        u2 = "/decisoes/2003/20030115_R1/20030115_D07.html"
        self.assertEqual(jc.id_colegiado(u2), "cvm-col-20030115-d07")
        u3 = "/decisoes/2010/20100105_R1/20100105_D9198-9199.html"
        self.assertEqual(jc.id_colegiado(u3), "cvm-col-20100105-d9198-9199")
        u4 = "/decisoes/2008/20080311_R1/4321.html"
        self.assertEqual(jc.id_colegiado(u4), "cvm-col-20080311-d4321")
        self.assertEqual(jc.id_colegiado("/decisoes/2015/20151124_e_25/20151124_e_25_D5229B.html"),
                         "cvm-col-20151124-d5229b")
        self.assertEqual(jc.id_colegiado("/decisoes/2016/20161006_D1/20161006_D0391.html"),
                         "cvm-col-20161006-d0391")
        self.assertEqual(jc.id_colegiado("/decisoes/2021/20210303_R1/20210303_D1472"),
                         "cvm-col-20210303-d1472")
        self.assertEqual(jc.slug_colegiado("/decisoes/2010/20100105_R2/20100105_D01.html"),
                         ("20100105", "d01", 2))
        with self.assertRaises(ValueError):
            jc.id_colegiado("/decisoes/2019/20190219_R1.html")

    def test_reparar_url(self):
        ruim = ("https://sei.cvm.gov.br/https://sei.cvm.gov.br/sei/publicacoes/x.php?a=1"
                "&id_orgao_publicacao=0sei/publicacoes/x.php?a=1&id_orgao_publicacao=0")
        self.assertEqual(jc.reparar_url(ruim),
                         "https://sei.cvm.gov.br/sei/publicacoes/x.php?a=1&id_orgao_publicacao=0")
        self.assertEqual(jc.reparar_url("/a/b.pdf"), "/a/b.pdf")

    def test_caminhos(self):
        self.assertEqual(
            jc.caminho_relativo("pas", "cvm-pas-rj2015-1234", 2017),
            "julgados-pas/julgados/cvm/pas/2017/rj2015-1234.md")
        self.assertEqual(
            jc.caminho_relativo("decisao-colegiado", "cvm-col-20251202-d3228", 2025),
            "julgados-colegiado-2016-2026/julgados/cvm/colegiado/2025/col-20251202-d3228.md")
        self.assertEqual(
            jc.caminho_relativo("termo-compromisso", "cvm-tc-rj2005-0001-20050310", 2005),
            "julgados-tc-crsfn/julgados/cvm/colegiado/2005/tc-rj2005-0001-20050310.md")
        self.assertEqual(
            jc.caminho_relativo("decisao-antiga", jc.id_decisao_antiga(1990), 1990),
            "julgados-colegiado-2002-2008/julgados/cvm/decisoes-antigas/1990.md")
        self.assertEqual(jc.id_decisao_antiga(1990, 7), "cvm-dec-1990-007")
        with self.assertRaises(ValueError):
            jc.caminho_relativo("pas", "cvm-col-20251202-d3228", 2025)


class FrontmatterTest(unittest.TestCase):
    def test_ordem_e_vazios(self):
        fm = jc.frontmatter({"tipo": "pas", "id": "cvm-pas-rj2015-1234", "orgao": "cvm",
                             "ementa": "Linha\num  dois"})
        self.assertTrue(fm.endswith("---\n\n"))
        linhas = fm.strip().splitlines()
        self.assertEqual(linhas[0], "---")
        self.assertEqual([x.split(":")[0] for x in linhas[1:-1]], list(jc.CAMPOS))
        self.assertIn("id: cvm-pas-rj2015-1234", linhas)
        self.assertIn("classe:", linhas)
        self.assertIn("ementa: Linha um dois", linhas)
        self.assertEqual(linhas[-1], "---")

    def test_campo_fora(self):
        with self.assertRaises(ValueError):
            jc.frontmatter({"partes": "x"})


class EmentaTest(unittest.TestCase):
    def test_titulo_sem_partes(self):
        t = "RECURSO CONTRA MULTA COMINATÓRIA (SEP) – EMPRESA EXEMPLO S.A. – PROC. RJ2010/1234"
        self.assertEqual(jc.ementa_de_titulo(t),
                         "Recurso contra multa cominatória (SEP). Proc. RJ2010/1234.")

    def test_titulo_nup(self):
        t = "PROPOSTA DE TERMO DE COMPROMISSO – FULANO DE TAL – PROC. SEI 19957.000001/2021-11"
        self.assertEqual(jc.ementa_de_titulo(t),
                         "Proposta de termo de compromisso. Proc. SEI 19957.000001/2021-11.")

    def test_titulo_sem_processo(self):
        self.assertEqual(jc.ementa_de_titulo("CONSULTA DA SIN – FUNDO X"), "Consulta da SIN.")
        self.assertEqual(jc.ementa_de_titulo(""), "")

    def test_normativo_mantem_assunto(self):
        t = "AUDIÊNCIA PÚBLICA SDM – MINUTA DE RESOLUÇÃO SOBRE FIDC"
        self.assertEqual(jc.ementa_de_titulo(t, "normativo"),
                         "Audiência pública SDM – minuta de resolução sobre FIDC.")

    def test_ementa_sem_partes(self):
        e = "NÚCLEO DTVM LTDA., FULANO DE TAL E OUTROS - Ocorrência de operações fraudulentas."
        self.assertEqual(jc.ementa_sem_partes(e), "Ocorrência de operações fraudulentas.")
        e2 = "FULANO DE TAL, BELTRANO DA SILVA\nInfração ao art. 155 da Lei 6.404/76."
        self.assertEqual(jc.ementa_sem_partes(e2), "Infração ao art. 155 da Lei 6.404/76.")
        e3 = "Insider trading. Condenação."
        self.assertEqual(jc.ementa_sem_partes(e3), e3)


class SelecaoTest(unittest.TestCase):
    ITENS = [
        {"id": "a", "tipo": "pas", "data": "2020-01-02", "url": "u"},
        {"id": "b", "tipo": "pas", "data": "2012-01-02", "url": "u"},
        {"id": "c", "tipo": "decisao-colegiado", "data": "2005-03-04", "url": "u"},
        {"id": "d", "tipo": "pas", "data": "2021-03-04", "url": ""},
    ]

    def test_filtros(self):
        ids = lambda **kw: [i["id"] for i in jc.selecionar(self.ITENS, **kw)]  # noqa: E731
        self.assertEqual(ids(onda=1), ["a"])
        self.assertEqual(ids(onda=2), ["b"])
        self.assertEqual(ids(onda=3), ["c"])
        self.assertEqual(ids(tipo="pas"), ["a", "b"])
        self.assertEqual(ids(ano=2005), ["c"])
        self.assertEqual(ids(ids=["d", "a"]), ["a", "d"])
        self.assertEqual(ids(limite=1), ["a"])

    def test_anexo_alheio(self):
        self.assertTrue(jc.anexo_alheio("TERMO ADITIVO AO CONVÊNIO"))
        self.assertTrue(jc.anexo_alheio("Convênio CVM-BCB"))
        self.assertTrue(jc.anexo_alheio("ACORDO DE COOPERAÇÃO TÉCNICA"))
        self.assertFalse(jc.anexo_alheio("VOTO DO RELATOR"))
        self.assertFalse(jc.anexo_alheio("PARECER DO COMITÊ"))



class SemControleTest(unittest.TestCase):
    def test_nul_vira_marca_visivel_e_stx_vira_hifen(self):
        self.assertEqual(jc.sem_controle("O\x00cios na sexta\x02feira\x0b."), "O\ufffdcios na sexta-feira.")
        self.assertEqual(jc.sem_controle("linha\n\ttab\r\n"), "linha\n\ttab\r\n")

if __name__ == "__main__":
    unittest.main()
