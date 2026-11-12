"""Testes da montagem do histórico (sem git: só o plano dos commits e os comandos)."""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import montar_historico as mh  # noqa: E402

RES = "plugins/normas/skills/consultar-normas/normas/cvm/resolucoes/%s"
ALT = "plugins/normas/skills/consultar-normas/normas/cvm/alteradoras/%s"


def entrada(ato, tipo, data, norma, origem, mensagem=None):
    return {
        "ato": ato, "tipo": tipo, "data_dou": data,
        "mensagem": mensagem or "Res. CVM %d/%s (DOU %s): %s" % (
            ato, data[:4], data, "publicacao original" if tipo == "original" else "altera Res. CVM 17 e 60"),
        "arquivos": {RES % norma: origem},
    }


ALTERADORAS = {162: ALT % "0162.md", 207: ALT % "0207.md", 208: ALT % "0208.md", 226: ALT % "0226.md"}


class TestPlanejarCommits(unittest.TestCase):
    def test_ato_em_duas_cadeias_vira_um_commit_com_os_dois_arquivos_e_o_ato(self):
        c17 = [entrada(17, "original", "2021-02-10", "0017.md", "dados/replay-0017/v0.md"),
               entrada(162, "alteracao", "2022-07-14", "0017.md", "dados/replay-0017/v1.md")]
        c60 = [entrada(60, "original", "2021-12-23", "0060.md", "dados/replay-0060/v0.md"),
               entrada(162, "alteracao", "2022-07-14", "0060.md", "dados/replay-0060/v1.md")]
        commits = mh.planejar_commits([c17, c60], ALTERADORAS)
        self.assertEqual([(c["ato"], c["tipo"]) for c in commits],
                         [(17, "original"), (60, "original"), (162, "alteracao")])
        arquivos = commits[2]["arquivos"]
        self.assertEqual(sorted(arquivos), [ALT % "0162.md", RES % "0017.md", RES % "0060.md"])
        self.assertEqual(arquivos[RES % "0017.md"], "dados/replay-0017/v1.md")
        self.assertEqual(arquivos[RES % "0060.md"], "dados/replay-0060/v1.md")
        self.assertEqual(arquivos[ALT % "0162.md"], ALT % "0162.md")  # já está no repo

    def test_ato_que_altera_quatro_normas_e_um_commit_so(self):
        cadeias = [[entrada(226, "alteracao", "2025-03-07", n, "dados/replay-%s/v9.md" % n[:4])]
                   for n in ("0017.md", "0060.md", "0080.md", "0160.md")]
        commits = mh.planejar_commits(cadeias, ALTERADORAS)
        self.assertEqual(len(commits), 1)
        self.assertEqual(len(commits[0]["arquivos"]), 5)

    def test_160_original_e_162_no_mesmo_dia_sao_dois_commits_na_ordem_do_numero(self):
        c17 = [entrada(162, "alteracao", "2022-07-14", "0017.md", "dados/replay-0017/v1.md")]
        c160 = [entrada(160, "original", "2022-07-14", "0160.md", "dados/replay-0160/v0.md")]
        commits = mh.planejar_commits([c17, c160], ALTERADORAS)  # ordem de entrada invertida de propósito
        self.assertEqual([c["ato"] for c in commits], [160, 162])
        self.assertEqual([c["tipo"] for c in commits], ["original", "alteracao"])

    def test_207_e_208_no_mesmo_dia_ordenam_por_numero(self):
        c1 = [entrada(208, "alteracao", "2024-08-14", "0017.md", "a")]
        c2 = [entrada(207, "alteracao", "2024-08-14", "0060.md", "b")]
        commits = mh.planejar_commits([c1, c2], ALTERADORAS)
        self.assertEqual([c["ato"] for c in commits], [207, 208])

    def test_ordem_global_por_data_e_original_antes_de_alteracao_do_mesmo_ato(self):
        cadeia = [
            entrada(300, "alteracao", "2026-01-10", "0017.md", "x"),
            entrada(100, "alteracao", "2025-05-05", "0017.md", "y"),
            entrada(100, "original", "2025-05-05", "0100.md", "z"),
        ]
        alt = {100: ALT % "0100.md", 300: ALT % "0300.md"}
        commits = mh.planejar_commits([cadeia], alt)
        self.assertEqual([(c["ato"], c["tipo"]) for c in commits],
                         [(100, "original"), (100, "alteracao"), (300, "alteracao")])

    def test_original_e_retificacao_nao_ganham_arquivo_do_ato(self):
        retif = entrada(160, "retificacao", "2022-08-01", "0160.md", "r")
        retif["arquivos"][ALT % "0160-retificacao-2022-08-01.md"] = ALT % "0160-retificacao-2022-08-01.md"
        original = entrada(160, "original", "2022-07-14", "0160.md", "o")
        commits = mh.planejar_commits([[retif, original]], {})
        self.assertEqual([c["tipo"] for c in commits], ["original", "retificacao"])
        self.assertEqual(sorted(commits[0]["arquivos"]), [RES % "0160.md"])
        self.assertEqual(len(commits[1]["arquivos"]), 2)

    def test_retificacao_ganha_o_arquivo_da_retificacao(self):
        retif = entrada(175, "retificacao", "2023-03-31", "0175/index.md", "r")
        commits = mh.planejar_commits([[retif]], {})
        self.assertIn(ALT % "0175-retificacao-2023-03-31.md", commits[0]["arquivos"])

    def test_duas_retificacoes_do_mesmo_ato_sao_dois_commits_na_ordem_das_datas(self):
        msg = "Retificacao da Res. CVM 19/2021 (DOU %s)"
        r2 = entrada(19, "retificacao", "2021-04-01", "0019.md", "dados/replay-0019/v2.md", msg % "2021-04-01")
        r1 = entrada(19, "retificacao", "2021-03-02", "0019.md", "dados/replay-0019/v1.md", msg % "2021-03-02")
        commits = mh.planejar_commits([[r2, r1]], {})  # ordem de entrada invertida de propósito
        self.assertEqual([(c["ato"], c["tipo"], c["data_dou"]) for c in commits],
                         [(19, "retificacao", "2021-03-02"), (19, "retificacao", "2021-04-01")])
        self.assertEqual(commits[0]["arquivos"], {
            RES % "0019.md": "dados/replay-0019/v1.md",
            ALT % "0019-retificacao-2021-03-02.md": ALT % "0019-retificacao-2021-03-02.md"})
        self.assertEqual(commits[1]["arquivos"], {
            RES % "0019.md": "dados/replay-0019/v2.md",
            ALT % "0019-retificacao-2021-04-01.md": ALT % "0019-retificacao-2021-04-01.md"})

    def test_mensagem_soma_ementa_e_normas_do_commit(self):
        msg = "Res. CVM 179/2023 (DOU 2023-02-15): altera Res. CVM 35 e 60"
        cadeias = [[entrada(179, "alteracao", "2023-02-15", n, "x" + n, msg)]
                   for n in ("0021.md", "0030.md", "0050.md", "0060.md")]
        commits = mh.planejar_commits(cadeias, {179: ALT % "0179.md"})
        self.assertEqual(commits[0]["mensagem"],
                         "Res. CVM 179/2023 (DOU 2023-02-15): altera Res. CVM 21, 30, 35, 50 e 60")

    def test_mensagem_com_norma_em_partes_conta_uma_vez(self):
        msg = "Res. CVM 181/2023 (DOU 2023-03-30): altera Res. CVM 175"
        e = entrada(181, "alteracao", "2023-03-30", "0175/index.md", "a", msg)
        e["arquivos"][RES % "0175/anexo-01.md"] = "b"
        commits = mh.planejar_commits([[e]], {181: ALT % "0181.md"})
        self.assertEqual(commits[0]["mensagem"], msg)

    def test_alteracao_sem_arquivo_do_ato_e_erro(self):
        with self.assertRaises(ValueError) as e:
            mh.planejar_commits([[entrada(999, "alteracao", "2025-01-01", "0017.md", "x")]], ALTERADORAS)
        self.assertIn("999", str(e.exception))

    def test_mesmo_ato_com_data_ou_mensagem_diferente_e_erro(self):
        a = entrada(162, "alteracao", "2022-07-14", "0017.md", "x")
        b = entrada(162, "alteracao", "2022-07-15", "0060.md", "y")
        with self.assertRaises(ValueError):
            mh.planejar_commits([[a], [b]], ALTERADORAS)
        c = entrada(162, "alteracao", "2022-07-14", "0060.md", "y", mensagem="outra mensagem")
        with self.assertRaises(ValueError):
            mh.planejar_commits([[a], [c]], ALTERADORAS)

    def test_mesmo_arquivo_com_origens_diferentes_no_mesmo_commit_e_erro(self):
        a = entrada(162, "alteracao", "2022-07-14", "0017.md", "x")
        b = entrada(162, "alteracao", "2022-07-14", "0017.md", "y")
        with self.assertRaises(ValueError):
            mh.planejar_commits([[a], [b]], ALTERADORAS)

    def test_nao_altera_a_entrada(self):
        a = entrada(162, "alteracao", "2022-07-14", "0017.md", "x")
        copia = json.loads(json.dumps(a))
        mh.planejar_commits([[a]], ALTERADORAS)
        self.assertEqual(a, copia)


class TestComandosGit(unittest.TestCase):
    COMMIT = {
        "ato": 162, "tipo": "alteracao", "data_dou": "2022-07-14",
        "mensagem": "Res. CVM 162/2022 (DOU 2022-07-14): altera Res. CVM 17 e 60",
        "arquivos": {RES % "0060.md": "dados/replay-0060/v1.md", RES % "0017.md": "dados/replay-0017/v1.md",
                     ALT % "0162.md": ALT % "0162.md"},
    }

    def test_ambiente_com_identidade_de_replay_e_data_do_dou_ao_meio_dia(self):
        env = mh.ambiente_git(self.COMMIT)
        nome, email = "Historico normativo (replay)", "replay@normas-mercado-capitais.invalid"
        data = "2022-07-14 12:00:00 -0300"
        self.assertEqual(env, {
            "GIT_AUTHOR_NAME": nome, "GIT_AUTHOR_EMAIL": email, "GIT_AUTHOR_DATE": data,
            "GIT_COMMITTER_NAME": nome, "GIT_COMMITTER_EMAIL": email, "GIT_COMMITTER_DATE": data,
        })

    def test_comandos_add_e_commit_com_o_env_no_commit(self):
        cmds = mh.comandos_git(self.COMMIT)
        self.assertEqual(len(cmds), 2)
        self.assertEqual(cmds[0], ["git", "add", "--", RES % "0017.md", RES % "0060.md", ALT % "0162.md"])
        commit = cmds[1]
        self.assertEqual(commit[0], "env")
        atribuicoes = [a for a in commit[1:] if "=" in a.split(" ")[0] and a.startswith("GIT_")]
        self.assertEqual(len(atribuicoes), 6)
        self.assertIn("GIT_AUTHOR_DATE=2022-07-14 12:00:00 -0300", commit)
        self.assertIn("GIT_COMMITTER_EMAIL=replay@normas-mercado-capitais.invalid", commit)
        self.assertEqual(commit[-4:], ["git", "commit", "-m", self.COMMIT["mensagem"]])

    def test_copias_ignoram_arquivo_que_ja_esta_no_repo(self):
        self.assertEqual(mh.copias_do_commit(self.COMMIT), [
            ("dados/replay-0017/v1.md", RES % "0017.md"),
            ("dados/replay-0060/v1.md", RES % "0060.md"),
        ])

    def test_nao_executa_nada(self):
        # só devolve listas e dicts; nenhum processo é criado
        self.assertIsInstance(mh.comandos_git(self.COMMIT), list)


class TestCarregarCadeias(unittest.TestCase):
    def gravar(self, d, conteudo):
        caminho = os.path.join(d, "commits.json")
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(conteudo, f)
        return caminho

    def test_carrega_formato_novo(self):
        with tempfile.TemporaryDirectory() as d:
            e = entrada(17, "original", "2021-02-10", "0017.md", "dados/replay-0017/v0.md")
            self.assertEqual(mh.carregar_cadeia(self.gravar(d, [e])), [e])

    def test_formato_antigo_sem_ato_e_tipo_e_erro_claro(self):
        with tempfile.TemporaryDirectory() as d:
            antigo = [{"mensagem": "x", "data_dou": "2021-02-10", "arquivos": {"a": "b"}}]
            with self.assertRaises(ValueError) as e:
                mh.carregar_cadeia(self.gravar(d, antigo))
            self.assertIn("formato antigo", str(e.exception))

    def test_tipo_invalido_e_data_invalida(self):
        with tempfile.TemporaryDirectory() as d:
            ruim = entrada(17, "original", "2021-02-10", "0017.md", "o")
            for campo, valor in (("tipo", "outro"), ("data_dou", "10/02/2021"), ("arquivos", {})):
                with self.assertRaises(ValueError, msg=campo):
                    mh.carregar_cadeia(self.gravar(d, [dict(ruim, **{campo: valor})]))


class TestCli(unittest.TestCase):
    def test_sem_simular_recusa_rodar(self):
        self.assertEqual(mh.main(["montar_historico.py"]), 2)

    def test_simular_imprime_a_lista(self):
        with tempfile.TemporaryDirectory() as d:
            e = [entrada(17, "original", "2021-02-10", "0017.md", "dados/replay-0017/v0.md"),
                 entrada(162, "alteracao", "2022-07-14", "0017.md", "dados/replay-0017/v1.md")]
            caminho = os.path.join(d, "commits.json")
            with open(caminho, "w", encoding="utf-8") as f:
                json.dump(e, f)
            alt = os.path.join(d, "alteradoras")
            os.makedirs(alt)
            with open(os.path.join(alt, "0162.md"), "w") as f:
                f.write("x")
            import contextlib
            import io
            saida = io.StringIO()
            with contextlib.redirect_stdout(saida):
                codigo = mh.main(["montar_historico.py", "--simular", "--alteradoras", alt, caminho])
            self.assertEqual(codigo, 0)
            texto = saida.getvalue()
            self.assertIn("2021-02-10", texto)
            self.assertIn("2022-07-14", texto)
            self.assertIn("2 commit(s)", texto)
            self.assertIn("1 original", texto)


if __name__ == "__main__":
    unittest.main()
