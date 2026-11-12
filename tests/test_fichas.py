"""Testes do fichas.py (fichas dos julgados para o plugin), em pastas temporárias."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import fichas as F  # noqa: E402


def gravar(base, rel, texto):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(texto)


def julgado(id_, data, tipo="decisao-colegiado", corpo="", extra=""):
    fm = ["---", "id: %s" % id_, "tipo: %s" % tipo, "processo: RJ2020/1", "data: %s" % data,
          "relator: SEP", "resultado: outro", "ementa: ementa de teste", "tema: outros",
          "dispositivos_citados:", "nivel_verificacao: html-convertido"]
    if extra:
        fm.append(extra)
    return "\n".join(fm + ["---", corpo])


def ler(base, rel):
    with open(os.path.join(base, rel), encoding="utf-8") as f:
        return f.read()


def ler_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def todos(base):
    out = {}
    for raiz, _, nomes in os.walk(base):
        for n in nomes:
            p = os.path.join(raiz, n)
            out[os.path.relpath(p, base)] = ler_bytes(p)
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ent = os.path.join(self.tmp, "julgados")
        self.sai = os.path.join(self.tmp, "fichas")

    def rodar(self, saida=None):
        return F.gerar(self.ent, saida or self.sai, log=lambda *a: None)


class TestTrecho(unittest.TestCase):
    def test_com_marcador_pas(self):
        corpo = ("# PAS 1\n\n## Relatório\n\n" + "texto longo do relatório. " * 20 +
                 "\n\n## Extrato\n\nDecisão: Vistos, relatados e discutidos os autos, o Colegiado, "
                 "por unanimidade, decidiu aplicar a penalidade de advertência ao acusado.\n")
        trecho, regra = F.trecho_decisao(corpo)
        self.assertEqual(regra, "decisao-dois-pontos")
        self.assertTrue(trecho.startswith("Decisão: Vistos"))
        self.assertIn("advertência", trecho)
        self.assertNotIn("relatório", trecho)

    def test_sem_marcador_usa_o_fim(self):
        corpo = "# Caso\n\n" + "inicio sem importancia " * 200 + "\n\nfim da peca com o dispositivo final."
        trecho, regra = F.trecho_decisao(corpo)
        self.assertEqual(regra, "fallback-fim")
        self.assertTrue(trecho.rstrip().endswith("dispositivo final."))
        self.assertLessEqual(len(trecho), F.LIMITE_TRECHO + 10)

    def test_titulo_com_decisao_nao_conta_como_marcador(self):
        corpo = "# Recurso contra DECISÃO da SEP\n\n" + "texto qualquer. " * 300 + "\nfim."
        _, regra = F.trecho_decisao(corpo)
        self.assertEqual(regra, "fallback-fim")

    def test_secao_decisao_pula_participantes(self):
        corpo = ("# Decisão do Colegiado\n\n## Relatório\n\nrelato.\n\n## Decisão\n\n**Participantes**\n\n"
                 "**FULANO - PRESIDENTE**\n**BELTRANO - DIRETOR**\n\n"
                 "Por ser o caso, o Colegiado deliberou negar provimento ao recurso.\n")
        trecho, regra = F.trecho_decisao(corpo)
        self.assertEqual(regra, "secao-decisao")
        self.assertTrue(trecho.startswith("o Colegiado deliberou") or trecho.startswith("Colegiado deliberou"))
        self.assertNotIn("FULANO", trecho)

    def test_secao_acordao_crsfn(self):
        corpo = "# Acórdão\n\n## Relatório\n\nrelato.\n\n## Acórdão\n\nVistos, relatados e discutidos os autos, decidem negar provimento.\n"
        trecho, regra = F.trecho_decisao(corpo)
        self.assertEqual(regra, "secao-acordao")
        self.assertTrue(trecho.startswith("Vistos"))

    def test_corte_em_limite_de_palavra(self):
        corpo = "# X\n\n## Decisão\n\n" + "palavra " * 1000
        trecho, _ = F.trecho_decisao(corpo)
        self.assertTrue(trecho.endswith(" [...]"))
        self.assertLessEqual(len(trecho), F.LIMITE_TRECHO + 6)
        self.assertTrue(trecho[: -len(" [...]")].endswith("palavra"))

    def test_corpo_vazio_nao_vira_ok(self):
        trecho, regra = F.trecho_decisao("# So titulo\n")
        self.assertEqual(regra, "sem-texto")
        self.assertIn("sem texto", trecho)


class TestFichas(Base):
    def test_ficha_campos_e_url(self):
        gravar(self.ent, "cvm/colegiado/2020/col-1.md",
               julgado("cvm-col-1", "2020-01-02", corpo="## Decisão\n\nO Colegiado deliberou aceitar.\n"))
        self.rodar()
        txt = ler(self.sai, "colegiado/2020.md")
        self.assertTrue(txt.startswith("# "))
        self.assertIn("## cvm-col-1\n", txt)
        for campo in F.CAMPOS:
            self.assertIn("- %s:" % campo, txt)
        self.assertIn("- dispositivos_citados:\n", txt)  # opcional vazio fica vazio
        self.assertIn("- texto_integral: https://raw.githubusercontent.com/dmarcheti/"
                      "normas-mercado-capitais/main/julgados/cvm/colegiado/2020/col-1.md\n", txt)
        self.assertIn("- trecho: ", txt)
        self.assertLess(txt.index("- texto_integral:"), txt.index("- trecho:"))

    def test_tc_separado_de_colegiado(self):
        gravar(self.ent, "cvm/colegiado/2013/a.md", julgado("cvm-col-a", "2013-02-19", tipo="termo-compromisso",
                                                            corpo="## Decisão\n\nO Colegiado aceitou.\n"))
        gravar(self.ent, "cvm/colegiado/2013/b.md", julgado("cvm-col-b", "2013-02-20",
                                                            corpo="## Decisão\n\nO Colegiado indeferiu.\n"))
        gravar(self.ent, "cvm/pas/2013/c.md", julgado("cvm-pas-c", "2013-03-01", tipo="pas",
                                                      corpo="Decisão: Vistos, decidiu advertir.\n"))
        gravar(self.ent, "crsfn/2013/9.md", julgado("crsfn-9", "2013-04-01", tipo="acordao-crsfn",
                                                    corpo="## Acórdão\n\nVistos, decidem negar provimento.\n"))
        self.rodar()
        self.assertIn("## cvm-col-a", ler(self.sai, "tc/2013.md"))
        self.assertNotIn("cvm-col-b", ler(self.sai, "tc/2013.md"))
        self.assertIn("## cvm-col-b", ler(self.sai, "colegiado/2013.md"))
        self.assertNotIn("cvm-col-a", ler(self.sai, "colegiado/2013.md"))
        self.assertIn("## cvm-pas-c", ler(self.sai, "pas/2013.md"))
        self.assertIn("## crsfn-9", ler(self.sai, "crsfn/2013.md"))

    def test_ordem_por_data_e_depois_id(self):
        for id_, data in (("z", "2020-05-01"), ("b", "2020-06-01"), ("a", "2020-06-01")):
            gravar(self.ent, "cvm/pas/2020/%s.md" % id_, julgado(id_, data, tipo="pas", corpo="Decisão: ok.\n"))
        self.rodar()
        txt = ler(self.sai, "pas/2020.md")
        self.assertLess(txt.index("## z\n"), txt.index("## a\n"))
        self.assertLess(txt.index("## a\n"), txt.index("## b\n"))


class TestDivisao(Base):
    def test_divide_em_24000_bytes(self):
        corpo = "## Decisão\n\nO Colegiado deliberou " + "acolher o pedido e " * 70 + "encerrar.\n"
        for i in range(60):
            gravar(self.ent, "cvm/colegiado/2021/c%03d.md" % i,
                   julgado("cvm-col-%03d" % i, "2021-01-%02d" % (i % 28 + 1), corpo=corpo))
        self.rodar()
        nomes = sorted(os.listdir(os.path.join(self.sai, "colegiado")))
        self.assertGreater(len(nomes), 1)
        self.assertEqual(nomes[0], "2021-01.md")
        self.assertEqual(nomes[1], "2021-02.md")
        ids = []
        for n in nomes:
            b = ler_bytes(os.path.join(self.sai, "colegiado", n))
            self.assertLessEqual(len(b), F.LIMITE_ARQUIVO, n)
            t = b.decode("utf-8")
            self.assertTrue(t.startswith("# "), n)
            ids += [l[3:] for l in t.split("\n") if l.startswith("## ")]
        self.assertEqual(len(ids), 60)
        self.assertEqual(len(set(ids)), 60)

    def test_sem_divisao_usa_nome_do_ano(self):
        gravar(self.ent, "cvm/pas/2019/a.md", julgado("a", "2019-01-01", tipo="pas", corpo="Decisão: ok.\n"))
        self.rodar()
        self.assertEqual(os.listdir(os.path.join(self.sai, "pas")), ["2019.md"])


class TestDeterminismoEErros(Base):
    def test_determinismo(self):
        for i in range(25):
            gravar(self.ent, "cvm/colegiado/2018/c%02d.md" % i,
                   julgado("cvm-col-%02d" % i, "2018-02-%02d" % (i % 27 + 1),
                           corpo="## Decisão\n\nO Colegiado deliberou " + "x " * 600 + "\n"))
        gravar(self.ent, "crsfn/2018/1.md", julgado("crsfn-1", "2018-05-05", tipo="acordao-crsfn", corpo="sem marcador\n"))
        self.rodar(os.path.join(self.tmp, "s1"))
        self.rodar(os.path.join(self.tmp, "s2"))
        a, b = todos(os.path.join(self.tmp, "s1")), todos(os.path.join(self.tmp, "s2"))
        self.assertEqual(a, b)
        self.assertTrue(a)

    def test_falha_sem_id_e_nomeia_o_arquivo(self):
        gravar(self.ent, "cvm/pas/2020/bom.md", julgado("bom", "2020-01-01", tipo="pas", corpo="Decisão: ok.\n"))
        gravar(self.ent, "cvm/pas/2020/ruim.md", "---\ntipo: pas\ndata: 2020-01-02\n---\nDecisão: ok.\n")
        with self.assertRaises(F.ErroFicha) as cm:
            self.rodar()
        self.assertIn("ruim.md", str(cm.exception))
        self.assertIn("id", str(cm.exception))

    def test_falha_sem_data(self):
        gravar(self.ent, "cvm/pas/2020/x.md", "---\nid: x\ntipo: pas\ndata:\n---\nDecisão: ok.\n")
        with self.assertRaises(F.ErroFicha) as cm:
            self.rodar()
        self.assertIn("x.md", str(cm.exception))

    def test_main_retorna_erro_sem_id(self):
        gravar(self.ent, "cvm/pas/2020/ruim.md", "---\ntipo: pas\ndata: 2020-01-02\n---\nx\n")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(F.main(["--entrada", self.ent, "--saida", self.sai]), 1)


class TestDecisoesAntigas(Base):
    ANUAL = ("---\nid: cvm-dec-1995\ntipo: decisao-antiga\ndata: 1995-01-01\nrelator:\nresultado:\n"
             "ementa: ano\ntema:\ndispositivos_citados:\nnivel_verificacao: pdf-extraido\n---\n"
             "# Decisões 1995\n\n## ATA DA REUNIÃO Nº 1 DE 06.09.1995\n\n"
             "### RECURSO CONTRA A DECISÃO DA SEP - EMPRESA A S.A. - PROC. 95/0712\n\nReg. nº 1/95\nRelator: DLC\n"
             "O Colegiado, acompanhando o Diretor, aprovou a republicação.\n\n"
             "### CONSULTA DA EMPRESA B S.A.\n\nO Colegiado decidiu responder à consulta.\n")

    def test_uma_ficha_por_decisao_com_link_do_anual(self):
        gravar(self.ent, "cvm/decisoes-antigas/1995.md", self.ANUAL)
        self.rodar()
        txt = ler(self.sai, "decisoes-antigas/1995.md")
        self.assertIn("## cvm-dec-1995-0001", txt)
        self.assertIn("## cvm-dec-1995-0002", txt)
        self.assertEqual(txt.count("julgados/cvm/decisoes-antigas/1995.md"), 2)
        self.assertIn("- data: 1995-09-06", txt)
        self.assertIn("aprovou a republicação", txt)
        self.assertIn("decidiu responder", txt)


if __name__ == "__main__":
    unittest.main()
