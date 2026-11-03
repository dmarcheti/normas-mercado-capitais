"""Testes do pacote.py (zip de instalação de plugin), num repo-raiz temporário."""
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import pacote as P  # noqa: E402


def gravar(base, rel, texto):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(texto)


class TestPacote(unittest.TestCase):
    def setUp(self):
        self.raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.raiz, True)
        b = "plugins/meu-plugin/"
        gravar(self.raiz, b + ".claude-plugin/plugin.json", '{"name": "meu-plugin", "version": "0.5.0"}')
        gravar(self.raiz, b + "skills/consultar/SKILL.md", "skill")
        gravar(self.raiz, b + "julgados/indice.md", "indice")
        gravar(self.raiz, b + "julgados/cvm/a.md", "a")
        gravar(self.raiz, b + "julgados/.DS_Store", "lixo")
        gravar(self.raiz, b + ".DS_Store", "lixo")

    def empacotar(self, **kw):
        return P.empacotar("meu-plugin", raiz=self.raiz, log=lambda *a: 0, **kw)

    def test_nome_estrutura_e_ordem(self):
        info = self.empacotar()
        self.assertEqual(os.path.basename(info["zip"]), "meu-plugin-0.5.0.zip")
        self.assertEqual(os.path.dirname(info["zip"]), os.path.join(self.raiz, "dados", "release"))
        self.assertEqual(info["arquivos"], 4)
        with zipfile.ZipFile(info["zip"]) as z:
            nomes = z.namelist()
            self.assertEqual(z.read("meu-plugin/julgados/cvm/a.md"), b"a")
        self.assertEqual(nomes, [
            "meu-plugin/", "meu-plugin/.claude-plugin/", "meu-plugin/.claude-plugin/plugin.json",
            "meu-plugin/julgados/", "meu-plugin/julgados/indice.md", "meu-plugin/julgados/cvm/",
            "meu-plugin/julgados/cvm/a.md", "meu-plugin/skills/", "meu-plugin/skills/consultar/",
            "meu-plugin/skills/consultar/SKILL.md"])
        self.assertFalse(any(".DS_Store" in n for n in nomes))
        self.assertTrue(all(n.startswith("meu-plugin/") for n in nomes))

    def test_deterministico_e_versao(self):
        a = self.empacotar()
        with open(a["zip"], "rb") as f:
            um = f.read()
        os.remove(a["zip"])
        with open(self.empacotar()["zip"], "rb") as f:
            self.assertEqual(f.read(), um)
        outra = os.path.join(self.raiz, "saida")
        b = self.empacotar(versao="9.9.9", saida=outra)
        self.assertEqual(b["zip"], os.path.join(outra, "meu-plugin-9.9.9.zip"))

    def test_limites(self):
        with self.assertRaises(SystemExit):
            self.empacotar(limite_arquivos=3)
        with self.assertRaises(SystemExit):
            self.empacotar(limite_bytes=10)
        self.assertFalse(os.path.exists(os.path.join(self.raiz, "dados", "release",
                                                     "meu-plugin-0.5.0.zip")))

    def test_plugin_inexistente(self):
        with self.assertRaises(SystemExit):
            P.empacotar("nao-existe", raiz=self.raiz, log=lambda *a: 0)


if __name__ == "__main__":
    unittest.main()
