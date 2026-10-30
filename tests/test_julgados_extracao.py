"""Testes da extração por LLM: sem rede e sem chamar o claude (subprocess falso)."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_comum as jc  # noqa: E402
import julgados_extracao as ex  # noqa: E402


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def valores(**kw):
    v = {c: "" for c in jc.CAMPOS}
    v.update({"orgao": "cvm", "data": "2025-09-09", "fonte_original": "https://x",
              "sha256_fonte": "0" * 64, "baixado_em": "2026-10-30",
              "nivel_verificacao": "html-convertido"})
    v.update(kw)
    return v


CORPO = ("# RECURSO CONTRA DECISÃO DA SEP – ACME S.A. – PROC. 19957.000001/2025-01\n\n"
         "## Decisão\n\nO Colegiado, acompanhando o voto do Diretor Fulano Exemplo, negou "
         "provimento ao recurso de Beltrano Exemplar contra a multa.\n")


class Arvore(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz)
        self.saida = os.path.join(self.raiz, "dados", "extracao")
        original = ex.Pessoas  # sem ler dados/ (CSV, tabelas, inventário) nos testes
        p = mock.patch.object(ex, "Pessoas",
                              lambda: original(acusados={}, partes_tc={}, descricoes={}))
        p.start()
        self.addCleanup(p.stop)

    def julgado(self, id_, tipo="decisao-colegiado", corpo=CORPO, **kw):
        plug = "julgados-pas" if tipo == "pas" else "julgados-colegiado-2016-2026"
        c = os.path.join(self.raiz, "plugins", plug, "julgados", "cvm", "x", "2025", id_ + ".md")
        os.makedirs(os.path.dirname(c), exist_ok=True)
        ex.gravar(c, valores(id=id_, tipo=tipo, **kw), corpo)
        return c


class RecorteTest(unittest.TestCase):
    def test_extrato_e_sumario(self):
        corpo = ("# PAS 19957.1\n\n## Extrato\n\nExtrato da sessão: multa ao acusado.\n\n"
                 "## Relatório\n\n" + "palavra " * 2000 + "\nSUMÁRIO\nProposta de R$ 100 mil.\n")
        r = ex.recorte(corpo)
        self.assertTrue(r.startswith("PAS 19957.1"))
        self.assertIn("Extrato da sessão", r)
        self.assertNotIn("palavra palavra palavra", r.split("SUMÁRIO")[0])
        self.assertIn("SUMÁRIO: Proposta de R$ 100 mil.", r)

    def test_sem_extrato_inicio_e_fim(self):
        corpo = "# T\n\n## Voto\n\n" + " ".join("p%d" % i for i in range(3000))
        r = ex.recorte(corpo)
        self.assertIn("p0 ", r)
        self.assertIn("p590", r)
        self.assertNotIn("p610 ", r)
        self.assertIn("p2600", r)
        self.assertTrue(r.endswith("p2999"))
        self.assertLess(len(r.split()), 1100)

    def test_temas_iguais_ao_prompt(self):
        with open(ex.PROMPT, encoding="utf-8") as f:
            prompt = f.read()
        self.assertEqual(tuple(re.findall(r"(?m)^\| `([a-z-]+)` \|", prompt)), ex.TEMAS)


class ValidacaoTest(unittest.TestCase):
    LOTE = [{"id": "a", "tipo": "decisao-colegiado", "recorte": CORPO},
            {"id": "b", "tipo": "pas", "recorte": "PAS. A ACME S.A. e JOSÉ DA SILVA EXEMPLO."}]

    def test_ids_incompletos_reprovam_o_lote(self):
        aprov, erros = ex.validar_saida(self.LOTE, [{"id": "a", "tema": "processual"}])
        self.assertEqual(aprov, {})
        self.assertIn("ids faltando: b", erros[0])

    def test_campos_invalidos_saem_do_item(self):
        saida = [{"id": "a", "ementa": "Recurso de Beltrano Exemplar contra multa. Negado.",
                  "tema": "tema-inventado", "resultado": "nao-provido", "relator": "Fulano Exemplo"},
                 {"id": "b", "ementa": " ".join(["palavra"] * 61), "tema": "manipulacao-fraude",
                  "resultado": "aceito"}]
        reprovadas = {}
        aprov, erros = ex.validar_saida(self.LOTE, saida, {"a": ["Beltrano Exemplar"]},
                                        reprovadas)
        self.assertEqual(aprov["a"], {"resultado": "nao-provido", "relator": "Fulano Exemplo"})
        self.assertEqual(aprov["b"], {"tema": "manipulacao-fraude"})
        self.assertEqual(len(erros), 4)
        self.assertEqual(reprovadas, {"a": "ementa com nome de pessoa",
                                      "b": "ementa com mais de 60 palavras"})


class PessoasTest(unittest.TestCase):
    """Lista positiva de pessoas físicas por julgado (nomes sintéticos)."""

    def test_nome_completo_nome_e_sobrenome_e_sobrenome_composto(self):
        lista = ["Fulano Beltrano de Tal Exemplar"]
        for ementa in ("Multa a Fulano Beltrano de Tal Exemplar.", "Multa a Fulano Exemplar.",
                       "Multa ao sr. Tal Exemplar.", "Multa a FULANO BELTRANO."):
            self.assertTrue(ex.tem_nome(ementa, lista), ementa)
        for ementa in ("Multa a Fulano, diretor.", "Exemplar Beltrano não é a ordem do nome.",
                       "Multa a fulano exemplar, em minúsculas.", "Multa ao acusado."):
            self.assertFalse(ex.tem_nome(ementa, lista), ementa)

    def test_empresa_nao_entra_na_lista(self):
        for empresa in ("Exemplo Industrial S.A.", "Construtora Exemplar S.A.", "Acme Ltda.",
                        "Exemplo Mineração e Metálicos S.A.", "Boston Exemplo Plus FIA",
                        "Banco Exemplo de Investimentos", "Fulano Participações",
                        "Exemplo Auditores Independentes", "CONTRA DECISÃO DA SEP",
                        "NBC TA 540", "Credenciamento de Administrador de Carteira"):
            self.assertEqual(ex.pessoa(empresa), "", empresa)
        self.assertEqual(ex.pessoa("Sr. Fulano de Tal (“Proponente”)"), "Fulano de Tal")
        self.assertEqual(ex.separar_partes("FULANO DE TAL, ACME S.A. e Beltrano Exemplar"),
                         ["FULANO DE TAL", "Beltrano Exemplar"])

    def test_fontes(self):
        nup = "19957" + "000001" + "2025" + "01"
        p = ex.Pessoas(acusados={nup: ["Acusado Do Csv"]},
                       partes_tc={"19957-000001-2025-01": ["Compromitente Da Tabela"]},
                       descricoes={"cvm-col-1": ("decisao-colegiado",
                                                 "Proposta apresentada por Cicrano Da Silva "
                                                 "(“Proponente”), na qualidade de diretor.")})
        corpo = ("# RECURSO CONTRA DECISÃO DA SEP – PARTE DO TITULO – PROC. 19957.000001/2025-01"
                 "\n\n## Extrato\n\nAcusados:\nPrimeiro Exemplo Extrato\nAcme S.A.\n"
                 "Ementa: multa.\nAcusado: Segundo Exemplo Extrato\n")
        v = {"id": "cvm-col-1", "tipo": "decisao-colegiado",
             "processo": "19957.000001/2025-01", "nup": "19957-000001-2025-01"}
        self.assertEqual(p.do_julgado(v, corpo),
                         ["Acusado Do Csv", "Compromitente Da Tabela", "Cicrano Da Silva",
                          "Primeiro Exemplo Extrato", "Segundo Exemplo Extrato",
                          "PARTE DO TITULO"])
        pas = ex.partes_da_descricao("FULANO DE TAL, ACME S.A. E OUTROS Abuso de poder. Multa.",
                                     "pas")
        self.assertEqual(pas, ["FULANO DE TAL"])

    def test_carrega_csv_e_tabelas_de_dados(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        nup = "19957" + "000002" + "2024" + "02"
        csvp = os.path.join(d, "acusados.csv")
        with open(csvp, "w", encoding="latin-1") as f:
            f.write("NUP;Nome_Acusado;Situacao;Data_Situacao\n")
            f.write("%s;JOSÉ EXEMPLO TESTE;Julgado;01/01/2025\n%s;ACME S.A.;Julgado;x\n"
                    % (nup, nup))
        os.makedirs(os.path.join(d, "listagens"))
        with open(os.path.join(d, "listagens", "tc_rejeitados.html"), "w",
                  encoding="utf-8") as f:
            f.write("<table><tr><td>19957.000002/2024-02</td><td>02/12/2025</td>"
                    "<td>Fulana Rejeitada Teste</td><td>x</td></tr></table>")
        p = ex.Pessoas(acusados_csv=csvp, listagens=os.path.join(d, "listagens"),
                       inventario=os.path.join(d, "nada.json"))
        self.assertEqual(p.acusados, {nup: ["JOSÉ EXEMPLO TESTE"]})
        self.assertEqual(p.partes_tc, {"19957-000002-2024-02": ["Fulana Rejeitada Teste"]})
        self.assertEqual(p.descricoes, {})


class ExecucaoTest(Arvore):
    def test_simular_monta_lotes_de_25_sem_modelo(self):
        for i in range(30):
            self.julgado("cvm-col-2025%04d-d%d" % (i, i))
        with mock.patch.object(ex.subprocess, "run") as run, redirect_stdout(io.StringIO()):
            rc = ex.main(["--onda", "1", "--simular", "--raiz", self.raiz, "--saida", self.saida])
        self.assertEqual(rc, 0)
        run.assert_not_called()
        lotes = sorted(os.listdir(self.saida))
        self.assertEqual(len(lotes), 2)
        tamanhos = [len(ler(os.path.join(self.saida, d, "lote.json"))) for d in lotes]
        self.assertEqual(tamanhos, [25, 5])
        item = ler(os.path.join(self.saida, lotes[0], "lote.json"))[0]
        self.assertEqual(set(item), {"id", "tipo", "classe", "processo", "data", "titulo",
                                     "recorte"})

    def test_trabalho_dentro_do_repositorio_e_recusado(self):
        with self.assertRaises(ValueError):
            ex.pasta_de_trabalho(os.path.join(jc.RAIZ, "dados"))

    def test_roda_valida_e_aplica(self):
        c_tit = self.julgado("cvm-col-1", ementa="Recurso contra decisão da SEP.",
                             ementa_fonte="titulo", classe="recurso")
        c_mul = self.julgado("cvm-col-2", ementa="Multa cominatória. Recurso.",
                             ementa_fonte="titulo", classe="multa-cominatoria",
                             resultado="provido")
        c_pas = self.julgado("cvm-pas-3", tipo="pas", ementa="Ementa da CVM.", ementa_fonte="cvm",
                             relator="Diretora Sicrana", tema="opa", tema_fonte="extracao")
        chamadas = []

        def falso(cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
            chamadas.append((cmd, cwd))
            self.assertEqual(sorted(os.listdir(cwd)), ["lote.json"])
            self.assertIn("julgados-extracao", cwd)
            self.assertIn("saida.json", input)
            lote = ler(os.path.join(cwd, "lote.json"))
            saida = [{"id": x["id"], "ementa": "Recurso contra multa por atraso; negado.",
                      "tema": "processual", "resultado": "nao-provido" if x["tipo"] != "pas"
                      else "condenacao", "relator": "SEP"} for x in lote]
            with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                json.dump(saida, f)
            log = "\n".join([json.dumps({"type": "system"}),
                             json.dumps({"type": "result", "total_cost_usd": 0.0123})])
            return mock.Mock(returncode=0, stdout=log, stderr="")

        trabalho = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, trabalho)
        with mock.patch.object(ex.subprocess, "run", side_effect=falso), \
                redirect_stdout(io.StringIO()) as out:
            rc = ex.main(["--ids", "cvm-col-1,cvm-col-2,cvm-pas-3", "--model", "haiku",
                          "--raiz", self.raiz, "--saida", self.saida, "--trabalho", trabalho])
        self.assertEqual(rc, 0)
        self.assertEqual(len(chamadas), 1)
        cmd = chamadas[0][0]
        for flag in ("--strict-mcp-config", "stream-json", "Read,Write"):
            self.assertIn(flag, cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "haiku")
        self.assertIn("custo total: US$ 0.0123", out.getvalue())
        lote = os.path.join(self.saida, os.listdir(self.saida)[0])
        self.assertEqual(ler(os.path.join(lote, "execucao.json"))["total_cost_usd"],
                         0.0123)
        self.assertTrue(os.path.exists(os.path.join(lote, "log.jsonl")))

        v1, _ = ex.ler_julgado(c_tit)
        self.assertEqual((v1["ementa"], v1["ementa_fonte"], v1["tema"], v1["tema_fonte"],
                          v1["resultado"], v1["relator"]),
                         ("Recurso contra multa por atraso; negado.", "extracao", "processual",
                          "extracao", "nao-provido", "SEP"))
        v2, _ = ex.ler_julgado(c_mul)  # rotineira: ementa de modelo fica; resultado já havia
        self.assertEqual((v2["ementa"], v2["ementa_fonte"], v2["resultado"], v2["tema"]),
                         ("Multa cominatória. Recurso.", "titulo", "provido", "processual"))
        v3, corpo3 = ex.ler_julgado(c_pas)  # ementa da CVM, tema e relator já preenchidos
        self.assertEqual((v3["ementa_fonte"], v3["tema"], v3["relator"], v3["resultado"]),
                         ("cvm", "opa", "Diretora Sicrana", "condenacao"))
        self.assertEqual(corpo3, CORPO)
        self.assertEqual(list(v3), list(jc.CAMPOS))

    def test_retentativa_uma_vez_e_ementa_do_titulo_se_falhar(self):
        corpo = CORPO.replace("ACME S.A.", "BELTRANO EXEMPLAR")
        c1 = self.julgado("cvm-col-1", corpo=corpo, ementa="Recurso.", ementa_fonte="titulo")
        c2 = self.julgado("cvm-col-2", ementa="Recurso 2.", ementa_fonte="titulo")
        c3 = self.julgado("cvm-pas-3", tipo="pas", corpo=corpo, ementa="Da CVM.",
                          ementa_fonte="cvm")
        chamadas = []

        def falso(cmd, input, cwd, capture_output, text, timeout):  # noqa: A002
            lote = ler(os.path.join(cwd, "lote.json"))
            retentativa = "## Retentativa" in input
            chamadas.append((retentativa, [(x["id"], x.get("motivo_retentativa")) for x in lote]))
            ementas = {"cvm-col-1": "Recurso de Beltrano Exemplar; negado.",
                       "cvm-col-2": " ".join(["longa"] * 70),
                       "cvm-pas-3": "Multa a Beltrano Exemplar."}
            if retentativa:
                ementas["cvm-col-1"] = "Recurso do acusado; negado."
            saida = [{"id": x["id"], "ementa": ementas[x["id"]], "tema": "processual"}
                     for x in lote]
            with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                json.dump(saida, f)
            return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch.object(ex.subprocess, "run", side_effect=falso), \
                redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            rc = ex.main(["--ids", "cvm-col-1,cvm-col-2,cvm-pas-3", "--raiz", self.raiz,
                          "--saida", self.saida, "--trabalho", tempfile.mkdtemp()])
        self.assertEqual(rc, 0)
        # a PAS com ementa da CVM não volta: a extraída não seria usada
        self.assertEqual(chamadas[1], (True, [("cvm-col-1", "ementa com nome de pessoa"),
                                              ("cvm-col-2", "ementa com mais de 60 palavras")]))
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(ex.ler_julgado(c1)[0]["ementa"], "Recurso do acusado; negado.")
        v2 = ex.ler_julgado(c2)[0]
        self.assertEqual((v2["ementa"], v2["ementa_fonte"], v2["tema"]),
                         ("Recurso 2.", "titulo", "processual"))
        self.assertEqual(ex.ler_julgado(c3)[0]["ementa"], "Da CVM.")
        ret = [d for d in os.listdir(self.saida) if "retentativa" in d]
        self.assertEqual(len(ret), 1)
        val = ler(os.path.join(self.saida, ret[0], "validacao.json"))
        self.assertEqual([os.path.basename(c) for c in val["ementa_do_titulo"]],
                         ["cvm-col-2.md"])
        self.assertIn("1 ficaram com a ementa do título", out.getvalue())
        self.assertNotIn("Beltrano", json.dumps(ler(os.path.join(self.saida, ret[0],
                                                                 "lote.json"))[0]["motivo_retentativa"]))

    def test_saida_ausente_nao_aplica_e_falha(self):
        c = self.julgado("cvm-col-9", ementa_fonte="titulo", ementa="X.")
        with open(c, encoding="utf-8") as f:
            antes = f.read()
        with mock.patch.object(ex.subprocess, "run",
                               return_value=mock.Mock(returncode=1, stdout="", stderr="erro")), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            rc = ex.main(["--ids", "cvm-col-9", "--raiz", self.raiz, "--saida", self.saida,
                          "--trabalho", tempfile.mkdtemp()])
        self.assertEqual(rc, 1)
        with open(c, encoding="utf-8") as f:
            self.assertEqual(f.read(), antes)


if __name__ == "__main__":
    unittest.main()
