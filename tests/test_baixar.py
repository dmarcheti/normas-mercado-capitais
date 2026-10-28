import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from baixar import baixar, permitido, slug_ctresb, slugs_da_busca  # noqa: E402


class TestBaixar(unittest.TestCase):
    def test_permitido_so_dominios_da_lista_e_https(self):
        self.assertTrue(permitido("https://www.in.gov.br/web/dou/-/x"))
        self.assertTrue(permitido("https://www.planalto.gov.br/ccivil_03/leis/l6385.htm"))
        self.assertFalse(permitido("http://www.in.gov.br/web/dou/-/x"))
        self.assertFalse(permitido("https://in.gov.br.exemplo.com/x"))
        self.assertFalse(permitido("https://exemplo.com/?u=www.in.gov.br"))

    def test_baixar_recusa_dominio_fora_da_lista_sem_rede(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                baixar("https://exemplo.com/a.html", os.path.join(d, "a.html"))

    def test_baixar_usa_cache_sem_rede(self):
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "a.html")
            with open(arq, "w") as f:
                f.write("x")
            self.assertEqual(baixar("https://exemplo.com/a.html", arq), arq)

    def test_slug_ctresb(self):
        nomes = [
            "resolucao-cvm-n-16-de-9-de-fevereiro-de-2021-303005223.md",
            "resolucao-cvm-n-162-de-13-de-julho-de-2022-415108961.md",
            "resolucao-cvm-n-17-de-9-de-fevereiro-de-2021-303005375.md",
        ]
        self.assertEqual(slug_ctresb(nomes, 162), "resolucao-cvm-n-162-de-13-de-julho-de-2022-415108961")
        self.assertEqual(slug_ctresb(nomes, 17), "resolucao-cvm-n-17-de-9-de-fevereiro-de-2021-303005375")
        self.assertIsNone(slug_ctresb(nomes, 175))

    def test_slugs_da_busca(self):
        html = ('{"jsonArray":[{"urlTitle":"resolucao-cvm-n-1750-de-1-de-janeiro-de-2030-1"},'
                '{"urlTitle":"resolucao-cvm-n-175-de-23-de-dezembro-de-2022-454036148"},'
                '{"urlTitle":"retificacao-455555555"}]}')
        ato, retif = slugs_da_busca(html, 175)
        self.assertEqual(ato, "resolucao-cvm-n-175-de-23-de-dezembro-de-2022-454036148")
        self.assertEqual(retif, ["retificacao-455555555"])


if __name__ == "__main__":
    unittest.main()
