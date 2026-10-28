"""Testes da varredura de termos proibidos (CNPJ e lista de nomes)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from varrer_termos import carregar_termos, varrer  # noqa: E402

TERMOS = ["Fundo Exemplo Alfa", "Gestora Exemplo"]
# CNPJ fictício montado em pedaços, para que este arquivo não dispare o próprio hook.
CNPJ_FORMATADO = "12.345.678/" + "0001-95"
CNPJ_PURO = "12345678" + "000195"


class TestVarrer(unittest.TestCase):
    def test_cnpj_formatado_e_achado(self):
        achados = varrer({"a.md": "Inscrito no CNPJ " + CNPJ_FORMATADO + "."}, TERMOS)
        self.assertEqual(len(achados), 1)
        self.assertTrue(achados[0].startswith("a.md: "))

    def test_cnpj_sem_pontuacao_e_achado(self):
        achados = varrer({"a.md": "cnpj " + CNPJ_PURO}, [])
        self.assertEqual(len(achados), 1)

    def test_termo_da_lista_sem_diferenciar_maiusculas(self):
        achados = varrer({"b.md": "O FUNDO EXEMPLO ALFA pagou."}, TERMOS)
        self.assertEqual(achados, ["b.md: Fundo Exemplo Alfa"])

    def test_termo_nao_casa_no_meio_de_palavra(self):
        achados = varrer({"c.md": "Um contraexemplo qualquer"}, ["exemplo"])
        self.assertEqual(achados, [])

    def test_texto_limpo_passa(self):
        achados = varrer({"d.md": "Art. 1º Esta Resolução dispõe sobre fundos."}, TERMOS)
        self.assertEqual(achados, [])

    def test_varios_arquivos_e_ordem_estavel(self):
        achados = varrer(
            {"z.md": "Gestora Exemplo", "a.md": "Fundo Exemplo Alfa"}, TERMOS
        )
        self.assertEqual(achados, ["a.md: Fundo Exemplo Alfa", "z.md: Gestora Exemplo"])

    def test_numero_longo_que_nao_e_cnpj(self):
        # Número de processo/ato com formato diferente não deve disparar.
        achados = varrer({"e.md": "Processo SEI 19957.001234/2023-10"}, [])
        self.assertEqual(achados, [])


class TestCarregarTermos(unittest.TestCase):
    def test_ignora_comentarios_e_linhas_vazias(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("# comentário\n\nFundo Exemplo Alfa\n  Gestora Exemplo  \n")
            caminho = f.name
        try:
            self.assertEqual(carregar_termos(caminho), ["Fundo Exemplo Alfa", "Gestora Exemplo"])
        finally:
            os.unlink(caminho)

    def test_arquivo_ausente_devolve_none(self):
        self.assertIsNone(carregar_termos("/caminho/que/nao/existe.txt"))


if __name__ == "__main__":
    unittest.main()


class TestCnpjDentroDeHash(unittest.TestCase):
    def test_hash_hexadecimal_nao_e_cnpj(self):
        from varrer_termos import varrer
        texto = "sha256_fonte: 29653ca2f0300a653b7cf646db92a1f9cf6794a72540926012984b67b7c62e73"
        self.assertEqual(varrer({"a.md": texto}, []), [])

    def test_cnpj_solto_continua_bloqueado(self):
        from varrer_termos import varrer
        self.assertEqual(varrer({"a.md": "CNPJ %s." % CNPJ_PURO}, []), ["a.md: " + CNPJ_PURO])


class TestCnpjDeDigitoRepetido(unittest.TestCase):
    def test_sequencia_de_um_digito_nao_e_cnpj(self):
        from varrer_termos import varrer
        self.assertEqual(varrer({"a.md": "repetidos (p.ex., " + "9" * 14 + ")"}, []), [])
