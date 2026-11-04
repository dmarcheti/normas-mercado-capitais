"""Testes do revisor LLM: sem rede, sem macOS e sem chamar o claude (subprocess falso)."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import julgados_comum as jc  # noqa: E402
import revisor as rv  # noqa: E402


def valores(**kw):
    v = {c: "" for c in jc.CAMPOS}
    v.update({"orgao": "cvm", "data": "2025-09-09", "fonte_original": "https://x",
              "sha256_fonte": "0" * 64, "baixado_em": "2026-10-30",
              "nivel_verificacao": "html-convertido"})
    v.update(kw)
    return v


CORPO = ("# RECURSO CONTRA DECISÃO DA SEP – ACME S.A. – PROC. 19957.000001/2025-01\n\n"
         "## Decisão\n\n"
         + "\n".join("Linha %d da qualificação." % i for i in range(1, 120)) + "\n\n"
         "O Colegiado, por unanimidade, negou provimento ao recurso da ACME S.A. contra a "
         "multa cominatória.\n")


def ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.trabalho = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.trabalho, True)

    def julgado(self, id_, corpo=CORPO, **kw):
        c = os.path.join(self.dir, id_ + ".md")
        v = valores(id=id_, tipo=kw.pop("tipo", "decisao-colegiado"),
                    classe=kw.pop("classe", "recurso"), **kw)
        with open(c, "w", encoding="utf-8") as f:
            f.write(jc.frontmatter(v) + corpo)
        return c

    def falso(self, respostas, grava=True):
        """subprocess.run falso: grava `saida.json` na pasta de trabalho (cwd) com a lista que
        `respostas(ids)` devolver, e imita o stream-json com o custo."""
        chamadas = []

        def run(cmd, input=None, cwd=None, **kw):
            chamadas.append({"cmd": cmd, "input": input, "cwd": cwd,
                             "lote": ler(os.path.join(cwd, "lote.json")),
                             "arquivos": sorted(os.listdir(cwd))})
            if grava:
                ids = [x["id"] for x in chamadas[-1]["lote"]]
                saida = respostas(ids)
                if saida is not None:
                    with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                        json.dump(saida, f)
            log = json.dumps({"type": "result", "total_cost_usd": 0.25}) + "\n"
            return subprocess.CompletedProcess(cmd, 0, stdout=log, stderr="")

        run.chamadas = chamadas
        return run


def todos_ok(ids):
    return [{"id": i, "ok": True, "alertas": []} for i in ids]


class MontagemTest(Base):
    def test_item_julgado_traz_frontmatter_qualificacao_decisao_e_fim(self):
        c = self.julgado("cvm-col-20250001-d1", resultado="nao-provido", tema="processual",
                         ementa="O Colegiado negou provimento.", ementa_fonte="extracao")
        item = rv.item_julgado(c)
        self.assertEqual(item["id"], "cvm-col-20250001-d1")
        self.assertEqual(item["modo"], "julgado")
        self.assertEqual(set(item["frontmatter"]), set(rv.CAMPOS_FRONTMATTER))
        self.assertEqual(item["frontmatter"]["resultado"], "nao-provido")
        self.assertEqual(item["frontmatter"]["ementa_fonte"], "extracao")
        linhas = item["qualificacao"].splitlines()
        self.assertEqual(len(linhas), rv.LINHAS_QUALIFICACAO)
        self.assertTrue(linhas[0].startswith("# RECURSO"))
        self.assertIn("DELIBERAÇÃO DO COLEGIADO", item["decisao"])
        self.assertIn("negou provimento", item["decisao"])
        fim = item["fim"].splitlines()
        self.assertEqual(len(fim), rv.LINHAS_FIM)
        self.assertIn("negou provimento", fim[-1])

    def test_texto_do_item_e_um_arquivo_legivel(self):
        item = rv.item_julgado(self.julgado("cvm-col-20250001-d1"))
        t = rv.texto_do_item(item)
        self.assertTrue(t.startswith("MODO: julgado\nID: cvm-col-20250001-d1\n"))
        for secao in ("== FRONTMATTER ==", "== QUALIFICAÇÃO DAS PARTES", "== RECORTE DA DECISÃO ==",
                      "== FIM DO TEXTO"):
            self.assertIn(secao, t)

    def test_item_norma_traz_diff_e_ato_e_corta_diff_enorme(self):
        d = os.path.join(self.dir, "res-cvm-175.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("-art. 1º velho\n+art. 1º novo\n" + "+x" * rv.MAX_DIFF)
        a = os.path.join(self.dir, "ato.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("Art. 1º novo")
        item = rv.item_norma(d, a)
        self.assertEqual(item["id"], "res-cvm-175")
        self.assertEqual(item["modo"], "norma")
        self.assertIn("DIFF CORTADO PELO SCRIPT", item["diff"])
        self.assertEqual(item["ato"], "Art. 1º novo")
        self.assertEqual(rv.item_norma(d)["ato"], "(não informado)")
        t = rv.texto_do_item(item)
        self.assertIn("== DIFF ==", t)
        self.assertIn("== ATO OU FONTE ==", t)

    def test_item_norma_cortado_so_quando_o_diff_passa_do_limite(self):
        d = os.path.join(self.dir, "curto.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+art. novo\n")
        self.assertFalse(rv.item_norma(d)["parcial"])
        grande = os.path.join(self.dir, "grande.diff")
        with open(grande, "w", encoding="utf-8") as f:
            f.write("+" + "x" * (rv.MAX_DIFF + 1))
        self.assertTrue(rv.item_norma(grande)["parcial"])

    def test_aviso_de_corte_do_ato_diz_ato_e_nao_marca_parcial(self):
        d = os.path.join(self.dir, "n.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+art. novo\n")
        a = os.path.join(self.dir, "ato.txt")
        with open(a, "w", encoding="utf-8") as f:
            f.write("y" * (rv.MAX_ATO + 5))
        item = rv.item_norma(d, a)
        self.assertIn("[ATO CORTADO PELO SCRIPT: 5 caracteres omitidos]", item["ato"])
        self.assertNotIn("DIFF CORTADO", item["ato"])
        self.assertFalse(item["parcial"])

    def test_lotes_de_ate_10_sem_perder_item(self):
        itens = [{"id": "i%02d" % n, "modo": "julgado"} for n in range(23)]
        grupos = rv.lotes(itens)
        self.assertEqual([len(g) for g in grupos], [10, 10, 3])
        self.assertEqual([i["id"] for g in grupos for i in g], [i["id"] for i in itens])

    def test_id_repetido_e_erro(self):
        with self.assertRaises(ValueError):
            rv.lotes([{"id": "a"}, {"id": "a"}])

    def test_montar_lote_grava_indice_e_um_arquivo_por_item(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-2025000%d-d%d" % (n, n))) for n in (1, 2)]
        pasta = os.path.join(self.dir, "lote")
        ids = rv.montar_lote(itens, pasta)
        self.assertEqual(ids, ["cvm-col-20250001-d1", "cvm-col-20250002-d2"])
        self.assertEqual(ler(os.path.join(pasta, "lote.json")),
                         [{"id": ids[0], "arquivo": "01.txt"}, {"id": ids[1], "arquivo": "02.txt"}])
        with open(os.path.join(pasta, "02.txt"), encoding="utf-8") as f:
            self.assertIn("ID: " + ids[1], f.read())


class ValidacaoTest(unittest.TestCase):
    def test_saida_valida_passa(self):
        saida = [{"id": "a", "ok": True, "alertas": []},
                 {"id": "b", "ok": False,
                  "alertas": [{"tipo": "dado-pessoal", "trecho": "CPF 1", "motivo": "CPF"}]}]
        r = rv.validar_saida(["a", "b"], saida)
        self.assertEqual(r["a"], {"ok": True, "alertas": []})
        self.assertFalse(r["b"]["ok"])
        self.assertEqual(r["b"]["alertas"][0]["tipo"], "dado-pessoal")

    def test_item_faltante_vira_alerta_nunca_ok(self):
        r = rv.validar_saida(["a", "b"], [{"id": "a", "ok": True, "alertas": []}])
        self.assertTrue(r["a"]["ok"])
        self.assertFalse(r["b"]["ok"])
        self.assertEqual(r["b"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)

    def test_sem_saida_todos_viram_alerta(self):
        r = rv.validar_saida(["a", "b"], None)
        self.assertTrue(all(not x["ok"] and x["alertas"][0]["tipo"] == rv.SEM_RESPOSTA
                            for x in r.values()))
        self.assertEqual(set(r), {"a", "b"})

    def test_saida_que_nao_e_lista_conta_como_sem_resposta(self):
        r = rv.validar_saida(["a"], {"a": {"ok": True}})
        self.assertEqual(r["a"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)

    def test_tipo_fora_da_lista_invalida_o_item(self):
        saida = [{"id": "a", "ok": False,
                  "alertas": [{"tipo": "inventado", "trecho": "x", "motivo": "y"}]}]
        r = rv.validar_saida(["a"], saida)
        self.assertEqual(r["a"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)
        self.assertIn("fora da lista", r["a"]["alertas"][0]["motivo"])

    def test_tipos_do_modo_norma_sao_so_tres(self):
        alerta = {"tipo": "ementa-contraria", "trecho": "x", "motivo": "y"}
        r = rv.validar_saida(["a"], [{"id": "a", "ok": False, "alertas": [alerta]}], "norma")
        self.assertEqual(r["a"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)
        ok = {"tipo": "texto-truncado", "trecho": "x", "motivo": "y"}
        r = rv.validar_saida(["a"], [{"id": "a", "ok": False, "alertas": [ok]}], "norma")
        self.assertEqual(r["a"]["alertas"][0]["tipo"], "texto-truncado")

    def test_ok_incoerente_com_alertas_nao_passa(self):
        a = {"tipo": "dado-pessoal", "trecho": "x", "motivo": "y"}
        r = rv.validar_saida(["a", "b"], [{"id": "a", "ok": True, "alertas": [a]},
                                          {"id": "b", "ok": False, "alertas": []}])
        for i in "ab":
            self.assertFalse(r[i]["ok"])
            self.assertEqual(r[i]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)

    def test_alerta_com_trecho_vazio_invalida(self):
        for trecho in ("", "  "):
            saida = [{"id": "a", "ok": False,
                      "alertas": [{"tipo": "dado-pessoal", "trecho": trecho, "motivo": "y"}]}]
            self.assertEqual(rv.validar_saida(["a"], saida)["a"]["alertas"][0]["tipo"],
                             rv.SEM_RESPOSTA)

    def test_alerta_sem_motivo_invalida(self):
        saida = [{"id": "a", "ok": False,
                  "alertas": [{"tipo": "dado-pessoal", "trecho": "x", "motivo": " "}]}]
        self.assertEqual(rv.validar_saida(["a"], saida)["a"]["alertas"][0]["tipo"],
                         rv.SEM_RESPOSTA)

    def test_id_extra_na_saida_e_ignorado(self):
        r = rv.validar_saida(["a"], [{"id": "a", "ok": True, "alertas": []},
                                     {"id": "zzz", "ok": True, "alertas": []}])
        self.assertEqual(set(r), {"a"})


class ExecucaoTest(Base):
    def revisar(self, itens, falso, **kw):
        log = os.path.join(self.dir, "log")
        with mock.patch.object(rv.subprocess, "run", side_effect=falso):
            r, infos = rv.revisar(itens, saida=log, trabalho=self.trabalho, **kw)
        return r, infos, log

    def test_comando_e_o_do_extrator_com_sonnet_e_prompt_do_revisor(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-20250001-d1"))]
        falso = self.falso(todos_ok)
        r, infos, _ = self.revisar(itens, falso)
        (ch,) = falso.chamadas
        self.assertEqual(ch["cmd"], rv.je.comando("sonnet"))
        self.assertIn("--tools", ch["cmd"])
        self.assertEqual(ch["cmd"][ch["cmd"].index("--tools") + 1], "Read,Write")
        self.assertIn("não roda git", ch["input"])
        self.assertIn("Modo norma", ch["input"])
        self.assertEqual(ch["arquivos"], ["01.txt", "lote.json"])
        self.assertTrue(r["cvm-col-20250001-d1"]["ok"])
        self.assertEqual(infos[0]["total_cost_usd"], 0.25)

    def test_pasta_de_trabalho_fica_fora_do_cofre_e_do_repo_e_e_apagada(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-20250001-d1"))]
        falso = self.falso(todos_ok)
        self.revisar(itens, falso)
        cwd = falso.chamadas[0]["cwd"]
        self.assertFalse(os.path.exists(cwd))
        for proibida in (rv.je.COFRE, os.path.realpath(jc.RAIZ)):
            self.assertFalse(os.path.realpath(cwd).startswith(proibida + os.sep))
        with self.assertRaises(ValueError):
            rv.rodar_lote(itens, trabalho=os.path.join(jc.RAIZ, "dados"))

    def test_23_itens_viram_3_lotes_e_o_resultado_junta_tudo(self):
        itens = [{"id": "i%02d" % n, "modo": "julgado",
                  "frontmatter": {c: "" for c in rv.CAMPOS_FRONTMATTER},
                  "qualificacao": "q", "decisao": "d", "fim": "f"} for n in range(23)]
        falso = self.falso(todos_ok)
        r, infos, log = self.revisar(itens, falso)
        self.assertEqual([len(c["lote"]) for c in falso.chamadas], [10, 10, 3])
        self.assertEqual(len(r), 23)
        self.assertTrue(all(x["ok"] for x in r.values()))
        self.assertEqual(sorted(os.listdir(log)),
                         ["lote-001", "lote-002", "lote-003", "resultado.json"])
        for n in (1, 2, 3):
            pasta = os.path.join(log, "lote-%03d" % n)
            self.assertEqual(sorted(os.listdir(pasta)),
                             ["entrada", "execucao.json", "log.jsonl", "saida.json"])
            self.assertEqual(ler(os.path.join(pasta, "execucao.json"))["total_cost_usd"], 0.25)

    def test_item_faltante_no_saida_vira_alerta(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-2025000%d-d%d" % (n, n))) for n in (1, 2)]
        falso = self.falso(lambda ids: todos_ok(ids[:1]))
        r, _, _ = self.revisar(itens, falso)
        self.assertTrue(r["cvm-col-20250001-d1"]["ok"])
        self.assertFalse(r["cvm-col-20250002-d2"]["ok"])
        self.assertEqual(r["cvm-col-20250002-d2"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)

    def test_modelo_que_nao_grava_saida_marca_todos_sem_resposta(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-2025000%d-d%d" % (n, n))) for n in (1, 2)]
        falso = self.falso(lambda ids: None)
        r, infos, _ = self.revisar(itens, falso)
        self.assertTrue(all(x["alertas"][0]["tipo"] == rv.SEM_RESPOSTA for x in r.values()))
        self.assertFalse(infos[0]["saida"])

    def test_saida_com_json_quebrado_marca_sem_resposta(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-20250001-d1"))]

        def run(cmd, input=None, cwd=None, **kw):
            with open(os.path.join(cwd, "saida.json"), "w", encoding="utf-8") as f:
                f.write("[{")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        r, infos, _ = self.revisar(itens, run)
        self.assertEqual(r["cvm-col-20250001-d1"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)
        self.assertIn("ilegível", infos[0]["erro"])

    def test_timeout_e_claude_ausente_nao_derrubam_o_lote(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-20250001-d1"))]
        for erro in (subprocess.TimeoutExpired("claude", 1), FileNotFoundError("claude")):
            r, infos, _ = self.revisar(itens, mock.Mock(side_effect=erro))
            self.assertEqual(r["cvm-col-20250001-d1"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)
            self.assertTrue(infos[0]["erro"])

    def test_alerta_do_modelo_chega_ao_resultado(self):
        itens = [rv.item_julgado(self.julgado("cvm-col-20250001-d1"))]
        alerta = {"tipo": "dado-pessoal", "trecho": "CPF 1", "motivo": "CPF ficou"}
        falso = self.falso(lambda ids: [{"id": ids[0], "ok": False, "alertas": [alerta]}])
        r, _, _ = self.revisar(itens, falso)
        self.assertEqual(r["cvm-col-20250001-d1"], {"ok": False, "alertas": [alerta]})

    def test_diff_cortado_sai_com_revisor_parcial_mesmo_com_ok_do_modelo(self):
        d = os.path.join(self.dir, "grande.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+" + "x" * (rv.MAX_DIFF + 1))
        c = os.path.join(self.dir, "curto.diff")
        with open(c, "w", encoding="utf-8") as f:
            f.write("+art. novo\n")
        falso = self.falso(todos_ok)
        r, _, _ = self.revisar([rv.item_norma(d), rv.item_norma(c)], falso)
        self.assertFalse(r["grande"]["ok"])
        self.assertEqual([x["tipo"] for x in r["grande"]["alertas"]], [rv.PARCIAL])
        self.assertIn("40000", r["grande"]["alertas"][0]["motivo"])
        self.assertEqual(r["curto"], {"ok": True, "alertas": []})

    def test_diff_cortado_sem_resposta_do_modelo_tem_os_dois_alertas(self):
        d = os.path.join(self.dir, "grande.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+" + "x" * (rv.MAX_DIFF + 1))
        r, _, _ = self.revisar([rv.item_norma(d)], self.falso(lambda ids: None))
        self.assertEqual([x["tipo"] for x in r["grande"]["alertas"]],
                         [rv.SEM_RESPOSTA, rv.PARCIAL])

    def test_modo_norma_usa_a_lista_de_tres_tipos(self):
        d = os.path.join(self.dir, "n1.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+art. novo\n")
        falso = self.falso(lambda ids: [{"id": ids[0], "ok": False, "alertas": [
            {"tipo": "resultado-contrario", "trecho": "x", "motivo": "y"}]}])
        r, _, _ = self.revisar([rv.item_norma(d)], falso)
        self.assertEqual(r["n1"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)


class LinhaDeComandoTest(Base):
    def rodar(self, argv, falso):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(rv.subprocess, "run", side_effect=falso), \
                redirect_stdout(out), redirect_stderr(err):
            rc = rv.main(argv + ["--trabalho", self.trabalho,
                                 "--saida", os.path.join(self.dir, "log")])
        return rc, json.loads(out.getvalue()), err.getvalue()

    def test_arquivos_ok_sai_com_zero(self):
        c = self.julgado("cvm-col-20250001-d1")
        rc, saida, err = self.rodar(["--arquivos", c], self.falso(todos_ok))
        self.assertEqual(rc, 0)
        self.assertEqual(saida, {"cvm-col-20250001-d1": {"ok": True, "alertas": []}})
        self.assertIn("US$ 0.2500", err)

    def test_alerta_sai_com_um(self):
        c = self.julgado("cvm-col-20250001-d1")
        rc, saida, _ = self.rodar(["--arquivos", c], self.falso(lambda ids: None))
        self.assertEqual(rc, 1)
        self.assertEqual(saida["cvm-col-20250001-d1"]["alertas"][0]["tipo"], rv.SEM_RESPOSTA)

    def test_ids_resolve_pelo_acervo(self):
        c = self.julgado("cvm-col-20250001-d1")
        achado = [{"id": "cvm-col-20250001-d1", "url": c}]
        with mock.patch.object(rv.je, "julgados", return_value=achado):
            rc, saida, _ = self.rodar(["--ids", "cvm-col-20250001-d1"], self.falso(todos_ok))
        self.assertEqual(rc, 0)
        self.assertEqual(list(saida), ["cvm-col-20250001-d1"])

    def test_ids_inexistente_e_erro(self):
        with mock.patch.object(rv.je, "julgados", return_value=[]), \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            rv.main(["--ids", "nao-existe"])

    def test_norma_diff(self):
        d = os.path.join(self.dir, "res-cvm-175.diff")
        with open(d, "w", encoding="utf-8") as f:
            f.write("+art. novo\n")
        rc, saida, _ = self.rodar(["--norma-diff", d], self.falso(todos_ok))
        self.assertEqual(rc, 0)
        self.assertEqual(list(saida), ["res-cvm-175"])


if __name__ == "__main__":
    unittest.main()
