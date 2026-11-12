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
import indice_decisoes as idc  # noqa: E402


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

    def anual_com_nome(self, ano=1990):
        # nome fictício montado por concatenação (nenhum dado real no repositório)
        nome = "ZEFE" + "RINO QUAR" + "TAMENTE"
        vocab = "pedido ressarcimento corretora consulta emissão notas promissórias aumento capital"
        corpo = ("# Decisões %d\n\n" % ano + "\n".join([vocab] * 6) + "\n\n## ATA DA REUNIÃO Nº 5 DE 10.04.%d\n\n"
                 "### RECLAMAÇÃO – %s – PEDIDO DE RESSARCIMENTO\n\nO Colegiado decidiu arquivar.\n\n"
                 "### CONSULTA SOBRE EMISSÃO DE NOTAS PROMISSÓRIAS\n\nO Colegiado decidiu responder.\n" % (ano, nome))
        gravar(self.ent, "cvm/decisoes-antigas/%d.md" % ano,
               self.ANUAL.replace("cvm-dec-1995", "cvm-dec-%d" % ano).replace("1995-01-01", "%d-01-01" % ano)
               .split("---\n# Decisões")[0] + "---\n" + corpo)
        return nome

    def test_ementa_com_pessoa_fisica_sai_com_marca_igual_ao_indice_antigo(self):
        nome = self.anual_com_nome()
        self.rodar()
        txt = ler(self.sai, "decisoes-antigas/1990.md")
        self.assertNotIn(nome.split()[0], txt)
        self.assertNotIn(nome.split()[1], txt)
        self.assertIn("- ementa: RECLAMAÇÃO – [pessoa física] – PEDIDO DE RESSARCIMENTO", txt)
        self.assertIn("- ementa: CONSULTA SOBRE EMISSÃO DE NOTAS PROMISSÓRIAS", txt)  # sem nome: intacta
        # o mesmo resultado do filtro que o índice antigo aplicava ao título
        p = os.path.join(self.ent, "cvm", "decisoes-antigas", "1990.md")
        ds, _ = idc.ler_decisoes({1990: p})
        self.assertIn("RECLAMAÇÃO – [pessoa física] – PEDIDO DE RESSARCIMENTO", [d["titulo"] for d in ds])

    def test_conta_as_ementas_trocadas(self):
        self.anual_com_nome()
        _f, info = F.coletar(self.ent)
        self.assertEqual(info["antigas_ementas_trocadas"], 1)

    def test_sem_decisao_antiga_nada_a_filtrar(self):
        gravar(self.ent, "cvm/pas/2020/a.md", julgado("cvm-pas-a", "2020-03-01", tipo="pas", corpo="Decisão: x\n"))
        _f, info = F.coletar(self.ent)
        self.assertEqual(info["antigas_ementas_trocadas"], 0)


class TestVerificar(Base):
    def setUp(self):
        super().setUp()
        gravar(self.ent, "cvm/pas/2020/a.md", julgado("cvm-pas-a", "2020-03-01", tipo="pas", corpo="Decisão: x\n"))
        gravar(self.ent, "cvm/colegiado/2021/b.md", julgado("cvm-col-b", "2021-03-01", corpo="Decisão: y\n"))
        self.args = ["--entrada", self.ent, "--saida", self.sai]

    def main(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = F.main(self.args + list(extra))
        return rc, out.getvalue(), err.getvalue()

    def test_verificar_sem_fichas_no_disco_falha_e_nao_grava(self):
        rc, out, err = self.main("--verificar")
        self.assertEqual(rc, 1)
        self.assertIn("ausente", out + err)
        self.assertFalse(os.path.exists(self.sai))

    def test_verificar_em_dia_devolve_zero(self):
        self.assertEqual(self.main()[0], 0)
        rc, out, _ = self.main("--verificar")
        self.assertEqual(rc, 0)
        self.assertIn("em dia", out)

    def test_verificar_acusa_arquivo_diferente(self):
        self.main()
        antes = todos(self.sai)
        alvo = os.path.join(self.sai, "pas", "2020.md")
        with open(alvo, "a", encoding="utf-8") as f:
            f.write("\nlixo\n")
        rc, out, err = self.main("--verificar")
        self.assertEqual(rc, 1)
        self.assertIn("pas/2020.md (diferente)", out + err)
        self.assertNotEqual(todos(self.sai), antes)  # e o --verificar não corrigiu nada
        self.assertIn(b"lixo", ler_bytes(alvo))

    def test_verificar_acusa_ficha_que_sobrou(self):
        self.main()
        gravar(self.sai, "pas/1999.md", "## velho\n")
        rc, out, err = self.main("--verificar")
        self.assertEqual(rc, 1)
        self.assertIn("pas/1999.md (sobrou de geracao anterior)", out + err)

    def test_verificar_acusa_julgado_novo_sem_ficha_no_disco(self):
        self.main()
        gravar(self.ent, "cvm/pas/2022/c.md", julgado("cvm-pas-c", "2022-01-01", tipo="pas", corpo="Decisão: z\n"))
        rc, out, err = self.main("--verificar")
        self.assertEqual(rc, 1)
        self.assertIn("pas/2022.md (ausente)", out + err)

    def test_verificar_sem_entrada_devolve_2(self):
        shutil.rmtree(self.ent)
        rc, _o, _e = self.main("--verificar")
        self.assertEqual(rc, 2)

    def test_gerar_apos_verificar_vermelho_deixa_em_dia(self):
        self.main()
        gravar(self.ent, "cvm/pas/2022/c.md", julgado("cvm-pas-c", "2022-01-01", tipo="pas", corpo="Decisão: z\n"))
        self.assertEqual(self.main("--verificar")[0], 1)
        self.assertEqual(self.main()[0], 0)
        self.assertEqual(self.main("--verificar")[0], 0)


class TestMontarEIds(Base):
    def test_montar_nao_grava_e_bate_com_o_gerar(self):
        gravar(self.ent, "cvm/pas/2020/a.md", julgado("cvm-pas-a", "2020-03-01", tipo="pas", corpo="Decisão: x\n"))
        fichas, arquivos, info = F.montar(self.ent)
        self.assertEqual(len(fichas), 1)
        self.assertFalse(os.path.exists(self.sai))
        self.rodar()
        self.assertEqual({"%s/%s" % (g, n): t.encode("utf-8") for g, n, t in arquivos},
                         {k.replace(os.sep, "/"): v for k, v in todos(self.sai).items()})
        self.assertEqual(info["ids_duplicados"], [])

    def test_ids_por_arquivo_cita_a_pasta_fichas(self):
        gravar(self.ent, "cvm/pas/2020/a.md", julgado("cvm-pas-a", "2020-03-01", tipo="pas", corpo="Decisão: x\n"))
        gravar(self.ent, "cvm/colegiado/2021/b.md", julgado("cvm-col-b", "2021-03-01", corpo="Decisão: y\n"))
        _f, arquivos, _i = F.montar(self.ent)
        self.assertEqual(F.ids_por_arquivo(arquivos),
                         {"cvm-pas-a": "fichas/pas/2020.md", "cvm-col-b": "fichas/colegiado/2021.md"})

    def test_diferencas_lista_ausente_diferente_e_sobra(self):
        gravar(self.ent, "cvm/pas/2020/a.md", julgado("cvm-pas-a", "2020-03-01", tipo="pas", corpo="Decisão: x\n"))
        _f, arquivos, _i = F.montar(self.ent)
        self.assertEqual(F.diferencas(arquivos, self.sai), ["pas/2020.md (ausente)"])
        F.gravar(self.sai, arquivos)
        self.assertEqual(F.diferencas(arquivos, self.sai), [])
        gravar(self.sai, "pas/2020.md", "outro\n")
        gravar(self.sai, "tc/2001.md", "x\n")
        self.assertEqual(F.diferencas(arquivos, self.sai),
                         ["pas/2020.md (diferente)", "tc/2001.md (sobrou de geracao anterior)"])

    def test_saida_padrao_e_a_pasta_fichas_da_skill(self):
        self.assertEqual(F.SAIDA_PADRAO, os.path.join(F.REPO, "plugins", "normas", "skills",
                                                     "consultar-normas", "julgados", "fichas"))
        self.assertEqual(F.ENTRADA_PADRAO, os.path.join(F.REPO, "julgados"))
        self.assertEqual(F.PASTA_FICHAS, os.path.basename(F.SAIDA_PADRAO))


if __name__ == "__main__":
    unittest.main()
