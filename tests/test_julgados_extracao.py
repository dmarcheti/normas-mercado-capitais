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
        aprov, erros = ex.validar_saida(self.LOTE, saida)
        self.assertEqual(aprov["a"], {"resultado": "nao-provido", "relator": "Fulano Exemplo"})
        self.assertEqual(aprov["b"], {"tema": "manipulacao-fraude"})
        self.assertEqual(len(erros), 4)
        self.assertTrue(any("nome de pessoa" in e for e in erros))

    def test_nome_em_caixa_alta_no_texto_e_empresa(self):
        self.assertTrue(ex.tem_nome("Multa a José da Silva Exemplo.", self.LOTE[1]["recorte"]))
        self.assertFalse(ex.tem_nome("Multa à ACME S.A. por fato relevante.",
                                     self.LOTE[1]["recorte"]))
        self.assertFalse(ex.tem_nome("Recurso contra decisão da SEP. Negado provimento.", CORPO))


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
