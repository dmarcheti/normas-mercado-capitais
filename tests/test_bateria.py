"""Testes das funções puras de scripts/bateria.py. Nenhum teste chama o `claude`."""
import os
import sys
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import bateria  # noqa: E402

GAB = {"P01": {"pergunta": "a"}, "P02": {"pergunta": "b"}, "P03": {"pergunta": "c"}}


class TestMontarArgs(unittest.TestCase):
    def test_sem_acervo_nao_tem_ferramentas(self):
        a = bateria.montar_args("sem")
        self.assertEqual(a, ["--model", "sonnet", "--tools", ""])

    def test_com_acervo_traz_os_seis_plugins_na_ordem(self):
        a = bateria.montar_args("com", "/x/plugins")
        self.assertEqual(a[:6], ["--model", "sonnet", "--tools", "Read,Skill", "--allowedTools", "Read,Skill"])
        pastas = [a[i + 1] for i, v in enumerate(a) if v == "--plugin-dir"]
        self.assertEqual(pastas, [os.path.join("/x/plugins", p) for p in bateria.PLUGINS])
        self.assertEqual(len(pastas), 6)

    def test_modo_invalido_ou_sem_pasta_e_erro(self):
        with self.assertRaises(ValueError):
            bateria.montar_args("talvez")
        with self.assertRaises(ValueError):
            bateria.montar_args("com")

    def test_comando_nunca_persiste_sessao(self):
        c = bateria.comando_claude(bateria.montar_args("sem"))
        self.assertEqual(c[:2], ["claude", "-p"])
        self.assertIn("--no-session-persistence", c)

    def test_juiz_sem_ferramentas_e_opus(self):
        self.assertEqual(bateria.montar_args_juiz(), ["--model", "opus", "--tools", ""])


class TestSelecao(unittest.TestCase):
    def test_todos_por_padrao(self):
        for v in (None, "", "todos", "TODOS", []):
            self.assertEqual(bateria.selecionar_ids(GAB, v), ["P01", "P02", "P03"])

    def test_subconjunto_segue_a_ordem_do_gabarito(self):
        self.assertEqual(bateria.selecionar_ids(GAB, "P03, P01"), ["P01", "P03"])

    def test_id_fora_do_gabarito_e_erro(self):
        with self.assertRaises(ValueError) as e:
            bateria.selecionar_ids(GAB, "P01,P99")
        self.assertIn("P99", str(e.exception))

    def test_tarefas_pulam_o_que_ja_existe(self):
        t = bateria.tarefas_de_resposta(GAB, ["P01", "P02"], ("sem", "com"), ["P01-sem.json", "P02-com.jsonl"])
        self.assertEqual(t, [("P01", "com"), ("P02", "sem"), ("P02", "com")])

    def test_modos(self):
        self.assertEqual(bateria.modos_de("sem,com"), ("sem", "com"))
        self.assertEqual(bateria.modos_de(" com "), ("com",))
        self.assertEqual(bateria.modos_de(""), bateria.MODOS)
        with self.assertRaises(ValueError):
            bateria.modos_de("sem,tudo")


class TestIdsCegos(unittest.TestCase):
    ARQ = ["P01-sem.json", "P01-com.json", "P02-sem.json", "P02-com.json"]

    def test_um_id_por_arquivo_sem_repetir(self):
        m = bateria.ids_cegos(self.ARQ)
        self.assertEqual(sorted(m), sorted(self.ARQ))
        self.assertEqual(sorted(m.values()), ["J01", "J02", "J03", "J04"])

    def test_mesma_semente_mesmo_mapa_e_ordem_de_entrada_irrelevante(self):
        self.assertEqual(bateria.ids_cegos(self.ARQ, 7), bateria.ids_cegos(list(reversed(self.ARQ)), 7))

    def test_id_nao_revela_o_modo(self):
        m = bateria.ids_cegos(self.ARQ)
        for arq, jid in m.items():
            self.assertNotIn("sem", jid)
            self.assertNotIn("com", jid)
            self.assertRegex(jid, r"^J\d{2}$")


if __name__ == "__main__":
    unittest.main()
