"""Testes do índice (sem rede): norma de fixture aparece com caminho relativo correto."""
import json
import os
import sys
import tempfile
import unittest

AQUI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(AQUI, "..", "scripts"))

import indice  # noqa: E402
from validar import CAMPOS  # noqa: E402

VALORES = {
    "id": "cvm-res-9", "orgao": "cvm", "tipo": "resolucao", "numero": "9",
    "data": "2020-05-04", "publicacao_dou": "2020-05-05",
    "ementa": "Dispõe sobre assunto de fixture | com barra.", "situacao": "vigente",
    "versao_texto": "consolidado", "vigente_ate_ato": "12",
    "aguarda_consolidado_oficial": "false", "historico_parcial": "false",
    "fonte_original": "https://exemplo.invalid/o", "fonte_consolidada": "https://exemplo.invalid/c",
    "sha256_fonte": "b" * 64, "baixado_em": "2026-10-28", "verificado_em": "2026-10-28",
    "incerteza": "",
}


def gravar(raiz, rel, **mudancas):
    v = dict(VALORES)
    v.update(mudancas)
    caminho = os.path.join(raiz, *rel.split("/"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    linhas = ["---"] + ["%s: %s" % (c, v[c]) if v[c] else "%s:" % c for c in CAMPOS] + ["---", "", "## Art. 1º", "", "Texto."]
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


class TestIndice(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = self._tmp.name
        gravar(self.raiz, "cvm/resolucoes/0009.md")
        gravar(self.raiz, "cvm/resolucoes/0003.md", id="cvm-res-3", numero="3", vigente_ate_ato="")
        gravar(self.raiz, "cvm/alteradoras/0012.md", id="cvm-res-12", numero="12", versao_texto="original")

    def tearDown(self):
        self._tmp.cleanup()

    def test_caminho_relativo_e_campos(self):
        _md, itens = indice.gerar_indice(self.raiz)
        item = next(i for i in itens if i["id"] == "cvm-res-9")
        self.assertEqual(item["caminho"], "cvm/resolucoes/0009.md")
        self.assertEqual(item["titulo"], "Resolução CVM nº 9/2020")
        self.assertEqual(item["situacao"], "vigente")
        self.assertEqual(item["vigente_ate_ato"], "12")
        self.assertIn("fixture", item["ementa"])

    def test_ordem_por_numero_e_sem_alteradoras_no_json(self):
        _md, itens = indice.gerar_indice(self.raiz)
        self.assertEqual([i["id"] for i in itens], ["cvm-res-3", "cvm-res-9"])

    def test_markdown_lista_normas_e_atos(self):
        md, _itens = indice.gerar_indice(self.raiz)
        self.assertIn("cvm/resolucoes/0009.md", md)
        self.assertIn("cvm/alteradoras/0012.md", md)
        self.assertIn("redação original", md)
        self.assertIn("fixture \\| com barra", md)  # a barra da ementa é escapada

    def test_verificar_detecta_indice_desatualizado(self):
        self.assertEqual(indice.main(["indice.py", self.raiz, "--verificar"]), 1)
        self.assertEqual(indice.main(["indice.py", self.raiz]), 0)
        self.assertEqual(indice.main(["indice.py", self.raiz, "--verificar"]), 0)
        with open(os.path.join(self.raiz, "normas.json"), encoding="utf-8") as f:
            self.assertEqual(len(json.load(f)), 2)
        gravar(self.raiz, "cvm/resolucoes/0020.md", id="cvm-res-20", numero="20")
        self.assertEqual(indice.main(["indice.py", self.raiz, "--verificar"]), 1)


if __name__ == "__main__":
    unittest.main()
